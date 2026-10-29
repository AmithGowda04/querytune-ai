"""Model client layer: request building, strict JSON validation, safe handling of output.

Pure Python. No provider SDK is imported at module level. AnthropicClient imports lazily and is
UNTESTED in the build sandbox (no network, no SDK). Tests use FakeClient.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from ai.prompts import TASKS, build_messages, markers, new_nonce
from ai.scrub import ScrubResult, scrub
from analyzer.dialects import Dialect
from analyzer.status import StatusInfo, status_for

MAX_INPUT_CHARS = 20_000
MAX_STR = 4_000
MAX_LIST = 50
SEVERITIES = ("low", "medium", "high")


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class FakeClient:
    """Test double. `responses`: list of strings (consumed in order) or fn(system, user) -> str."""
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if callable(self.responses):
            return self.responses(system, user)
        return self.responses.pop(0)


class AnthropicClient:
    """UNTESTED here (needs `anthropic` SDK + network). Model name comes from the caller/env;
    no default is guessed."""
    def __init__(self, api_key: str, model: Optional[str] = None, max_tokens: int = 2000):
        import anthropic  # lazy
        self._c = anthropic.Anthropic(api_key=api_key)
        self._model = model or os.environ.get("LLM_MODEL")
        if not self._model:
            raise ValueError("model name required (argument or LLM_MODEL)")
        self._max = max_tokens

    def complete(self, system: str, user: str) -> str:
        r = self._c.messages.create(model=self._model, max_tokens=self._max, system=system,
                                    messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


# ---------- JSON parsing and validation ----------
def parse_model_json(text: str):
    """Return (obj, error). Accepts a bare JSON object, optionally fenced or with stray prose."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    for candidate in (t, t[t.find("{"): t.rfind("}") + 1] if "{" in t and "}" in t else ""):
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj, None
        return None, "model output is not a JSON object"
    return None, "model output is not valid JSON"


def _str(v, name, allow_none=False):
    if v is None and allow_none:
        return None
    if not isinstance(v, str):
        raise ValueError(f"{name} must be a string")
    return v[:MAX_STR]


def _str_list(v, name):
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"{name} must be a list of strings")
    return [x[:MAX_STR] for x in v[:MAX_LIST]]


def _obj_list(v, name):
    if not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
        raise ValueError(f"{name} must be a list of objects")
    return v[:MAX_LIST]


def validate(task: str, obj: dict) -> dict:
    """Return a cleaned dict with only the known keys; raise ValueError on any schema violation."""
    if task == "explain":
        return {"summary": _str(obj["summary"], "summary"),
                "steps": _str_list(obj["steps"], "steps"),
                "assumptions": _str_list(obj["assumptions"], "assumptions")}
    if task == "debug":
        issues = []
        for it in _obj_list(obj["issues"], "issues"):
            line = it.get("line")
            if line is not None and (not isinstance(line, int) or isinstance(line, bool)):
                raise ValueError("line must be an integer or null")
            sev = it["severity"]
            if sev not in SEVERITIES:
                raise ValueError("bad severity")
            issues.append({"title": _str(it["title"], "title"),
                           "explanation": _str(it["explanation"], "explanation"),
                           "line": line, "severity": sev})
        return {"issues": issues, "fixed_sql": _str(obj["fixed_sql"], "fixed_sql", True),
                "notes": _str_list(obj["notes"], "notes")}
    if task == "optimise":
        changes = [{"title": _str(c["title"], "title"),
                    "explanation": _str(c["explanation"], "explanation"),
                    "risk": _str(c["risk"], "risk")} for c in _obj_list(obj["changes"], "changes")]
        return {"changes": changes,
                "rewritten_sql": _str(obj["rewritten_sql"], "rewritten_sql", True),
                "notes": _str_list(obj["notes"], "notes")}
    raise ValueError(f"unknown task {task!r}")


# ---------- text safety ----------
def sanitize_text(s: str) -> str:
    """Make model prose safe to show as plain text: no HTML, no markdown links/images."""
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    s = re.sub(r"</?[A-Za-z!][^>]*>", "", s)
    s = s.replace("![", "[image ").replace("](", "] (")
    s = re.sub(r"(?i)javascript:", "", s)
    return s


_PERF = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|x\b|times\b|ms\b|milliseconds?\b|seconds?\b)", re.I)


def find_perf_claims(texts) -> list:
    return [m.group(0) for t in texts for m in _PERF.finditer(t)]


# ---------- request building (also used for the preview shown to the user) ----------
@dataclass
class Request:
    ok: bool
    system: str = ""
    user: str = ""
    scrubbed: Optional[ScrubResult] = None
    error: Optional[str] = None


def build_request(task: str, sql: str, dialect: Dialect, scrub_literals: bool = True,
                  schema_text: Optional[str] = None, evidence_text: Optional[str] = None,
                  unscrubbed_evidence_ok: bool = False, nonce: Optional[str] = None) -> Request:
    """Build exactly what would be sent. Nothing is sent here."""
    if task not in TASKS:
        return Request(False, error=f"unknown task {task!r}")
    total = len(sql or "") + len(schema_text or "") + len(evidence_text or "")
    if not sql or not sql.strip():
        return Request(False, error="empty input")
    if total > MAX_INPUT_CHARS:
        return Request(False, error=f"input too large (limit {MAX_INPUT_CHARS} characters)")
    sc = None
    if scrub_literals:
        if evidence_text and not unscrubbed_evidence_ok:
            return Request(False, error="execution evidence cannot be literal-scrubbed reliably; "
                                        "remove it or confirm you accept sending it as is")
        sc = scrub(sql)
        if not sc.ok:
            return Request(False, error=f"literal scrubbing failed, nothing was sent: {sc.reason}")
        sql_out = sc.text
        if schema_text:
            ds = scrub(schema_text, scrub_numbers=False)
            if not ds.ok:
                return Request(False, error=f"table definitions could not be scrubbed: {ds.reason}")
            schema_text = ds.text
    else:
        sql_out = sql
    system, user = build_messages(task, sql_out, dialect.label, schema_text, evidence_text, nonce)
    return Request(True, system, user, sc)


# ---------- running a task ----------
@dataclass
class TaskResult:
    ok: bool
    task: str
    data: dict = field(default_factory=dict)
    rewrite_sql: Optional[str] = None
    rewrite_status: Optional[StatusInfo] = None
    warnings: list = field(default_factory=list)
    error: Optional[str] = None


def run_task(client: LLMClient, task: str, sql: str, dialect: Dialect, parse_fn: Callable,
             scrub_literals: bool = True, schema_text=None, evidence_text=None,
             unscrubbed_evidence_ok: bool = False, request: Optional[Request] = None) -> TaskResult:
    """Pass `request` (from build_request, the one the user previewed) to send exactly that."""
    req = request or build_request(task, sql, dialect, scrub_literals, schema_text, evidence_text,
                                   unscrubbed_evidence_ok)
    if not req.ok:
        return TaskResult(False, task, error=req.error)
    try:
        raw = client.complete(req.system, req.user)
    except Exception as e:  # never echo the exception text: it may contain request content
        return TaskResult(False, task, error=f"model call failed: {type(e).__name__}")

    obj, err = parse_model_json(raw)
    if err:
        return TaskResult(False, task, error=err)
    try:
        data = validate(task, obj)
    except (KeyError, ValueError) as e:
        return TaskResult(False, task, error=f"model output did not match the expected format ({type(e).__name__})")

    warnings = []
    restore = (lambda t: req.scrubbed.restore(t)) if req.scrubbed else (lambda t: (t, []))

    def restore_text(t):
        out, left = restore(t)
        return out

    rewrite_key = {"debug": "fixed_sql", "optimise": "rewritten_sql"}.get(task)
    rewrite_sql, unresolved = None, []
    if rewrite_key and data.get(rewrite_key):
        rewrite_sql, unresolved = restore(data[rewrite_key])
        data[rewrite_key] = rewrite_sql

    prose = []
    for k, v in list(data.items()):
        if k == rewrite_key:
            continue
        data[k] = _map_text(v, lambda t: sanitize_text(restore_text(t)))
        prose.extend(_flatten(data[k]))
    claims = find_perf_claims(prose)
    if claims:
        warnings.append("The model stated numeric performance claims (" + ", ".join(claims[:5]) +
                        "). These are NOT measured; ignore them.")

    status = None
    if rewrite_sql:
        if unresolved:
            status = StatusInfo("Proposed", ("rewrite still contains unresolved placeholders",))
        else:
            try:
                tree = parse_fn(rewrite_sql, dialect.sqlglot_read)
                ok = tree is not None
            except Exception:
                ok = False
            status = status_for(ok)
    return TaskResult(True, task, data, rewrite_sql, status, warnings)


def _map_text(v, fn):
    if isinstance(v, str):
        return fn(v)
    if isinstance(v, list):
        return [_map_text(x, fn) for x in v]
    if isinstance(v, dict):
        return {k: (_map_text(x, fn) if isinstance(x, (str, list, dict)) else x) for k, x in v.items()}
    return v


def _flatten(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [s for x in v for s in _flatten(x)]
    if isinstance(v, dict):
        return [s for x in v.values() for s in _flatten(x)]
    return []
