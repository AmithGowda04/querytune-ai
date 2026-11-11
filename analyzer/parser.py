"""analyze(): parse, select rules, run them, report honestly.

The parser is INJECTED (`parse_fn(sql, sqlglot_read_name) -> tree`) so this
module has no sqlglot dependency and is testable with fakes. Stage 1f supplies
the real sqlglot-backed parse_fn.

Status "analysed" with no findings means "none of the N rules fired", not
"the query is correct".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from analyzer.dialects import Dialect, mismatch_warning
from analyzer.rules import DEFAULT_REGISTRY, Context, RuleRegistry

MAX_SQL_CHARS = 20_000


@dataclass
class AnalysisResult:
    status: str                      # "analysed" | "not_analysed"
    dialect_key: str
    findings: list = field(default_factory=list)
    rules_run: list = field(default_factory=list)       # rule ids executed
    skipped: list = field(default_factory=list)         # [(rule_id, reason)]
    rule_errors: list = field(default_factory=list)     # [(rule_id, message)]
    warnings: list = field(default_factory=list)        # e.g. dialect mismatch
    reason: Optional[str] = None                        # why not analysed


def _not_analysed(dialect: Dialect, reason: str, warnings: list) -> AnalysisResult:
    return AnalysisResult("not_analysed", dialect.key, reason=reason, warnings=warnings)


def analyze(sql: str, dialect: Dialect, parse_fn: Callable,
            registry: RuleRegistry = DEFAULT_REGISTRY, schema=None,
            disabled: Iterable[str] = (), enabled: Iterable[str] = ()) -> AnalysisResult:
    if not isinstance(sql, str) or not sql.strip():
        return _not_analysed(dialect, "empty input", [])
    if len(sql) > MAX_SQL_CHARS:
        return _not_analysed(dialect, f"input too large (limit {MAX_SQL_CHARS} characters)", [])

    warnings = []
    w = mismatch_warning(sql, dialect.key)
    if w:
        warnings.append(w)

    try:
        tree = parse_fn(sql, dialect.sqlglot_read)
    except Exception as e:
        msg = " ".join(str(e).split())[:200]
        reason = f"not analysed as {dialect.label}: {msg or type(e).__name__}"
        return _not_analysed(dialect, reason, warnings)
    if tree is None:
        return _not_analysed(dialect, "parser returned nothing", warnings)

    rules, skipped = registry.select(dialect, schema is not None, disabled, enabled)
    findings, errors = registry.run(rules, Context(sql=sql, tree=tree, dialect=dialect, schema=schema))
    findings.sort(key=lambda f: (f.line if f.line is not None else 10**9, f.rule_id))
    return AnalysisResult("analysed", dialect.key, findings=findings,
                          rules_run=[r.id for r in rules], skipped=skipped,
                          rule_errors=errors, warnings=warnings)
