"""Rule framework: Rule, Finding, Context, RuleRegistry.

Pure Python: does NOT import sqlglot. `Context.tree` is an opaque parse tree;
the actual rules (Stage 1f) will interpret it. Rule ids must exist in
corpus/taxonomy.json (enforced by a test).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from analyzer.dialects import Dialect

SEVERITIES = ("low", "medium", "high")
KINDS = ("syntactic", "schema")
_ID = re.compile(r"^QT\d{3}$")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    line: Optional[int] = None      # 1-based
    snippet: Optional[str] = None

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"bad severity: {self.severity!r}")
        if not self.message or not self.message.strip():
            raise ValueError("finding needs a message")


@dataclass
class Context:
    sql: str
    tree: Any
    dialect: Dialect
    schema: Optional[Any] = None    # parsed DDL; only schema-kind rules may use it


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    kind: str                       # "syntactic" | "schema"
    rationale: str
    bad_example: str
    good_example: str
    check: Callable[[Context], list]
    enabled_by_default: bool = True

    def __post_init__(self):
        if not _ID.match(self.id or ""):
            raise ValueError(f"rule id must look like QT001, got {self.id!r}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"{self.id}: bad severity {self.severity!r}")
        if self.kind not in KINDS:
            raise ValueError(f"{self.id}: bad kind {self.kind!r}")
        for field in ("name", "rationale", "bad_example", "good_example"):
            v = getattr(self, field)
            if not isinstance(v, str) or not v.strip():
                raise ValueError(f"{self.id}: {field} is required")
        if not callable(self.check):
            raise ValueError(f"{self.id}: check must be callable")


class RuleRegistry:
    def __init__(self):
        self._rules: dict = {}

    def register(self, rule: Rule) -> Rule:
        if rule.id in self._rules:
            raise ValueError(f"duplicate rule id {rule.id}")
        self._rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def all(self) -> list:
        return [self._rules[k] for k in sorted(self._rules)]

    def ids(self) -> set:
        return set(self._rules)

    def select(self, dialect: Dialect, has_schema: bool,
               disabled: Iterable[str] = (), enabled: Iterable[str] = ()):
        """Return (rules_to_run, skipped) where skipped = [(rule_id, reason)]."""
        disabled, enabled = set(disabled), set(enabled)
        unknown = (disabled | enabled) - self.ids()
        if unknown:
            raise ValueError(f"unknown rule ids: {sorted(unknown)}")
        run, skipped = [], []
        for r in self.all():
            if r.id in disabled:
                skipped.append((r.id, "switched off"))
            elif not r.enabled_by_default and r.id not in enabled:
                skipped.append((r.id, "off by default"))
            elif r.kind not in dialect.rule_kinds:
                skipped.append((r.id, f"not available for {dialect.label}"))
            elif r.kind == "schema" and not has_schema:
                skipped.append((r.id, "needs table definitions (paste CREATE TABLE statements)"))
            else:
                run.append(r)
        return run, skipped

    def run(self, rules: Iterable[Rule], ctx: Context):
        """Run rules; a crashing or misbehaving rule is recorded, never raised.

        Returns (findings, errors) where errors = [(rule_id, message)].
        """
        findings, errors = [], []
        for r in rules:
            try:
                out = r.check(ctx)
            except Exception as e:  # isolate: one bad rule must not break the analysis
                errors.append((r.id, f"rule crashed: {type(e).__name__}"))
                continue
            if not isinstance(out, list) or not all(isinstance(f, Finding) for f in out):
                errors.append((r.id, "rule returned something other than a list of Finding"))
                continue
            if any(f.rule_id != r.id for f in out):
                errors.append((r.id, "rule returned a finding with a different rule_id"))
                continue
            findings.extend(out)
        return findings, errors


# Empty until Stage 1f. Rules are registered there, tuned on the dev split only.
DEFAULT_REGISTRY = RuleRegistry()
