"""Public entry point: analyze_sql(sql, dialect, ddl_text) using the lightweight parser."""
from __future__ import annotations

from analyzer import lite_rules  # noqa: F401  (registers the rules)
from analyzer.parser import AnalysisResult, analyze
from analyzer.rules import DEFAULT_REGISTRY
from analyzer.tsql_lite import LiteParseError, parse_schema, parse_sql


def analyze_sql(sql, dialect, ddl_text=None, disabled=(), enabled=()) -> AnalysisResult:
    schema, warnings = None, []
    if ddl_text and ddl_text.strip():
        try:
            schema = parse_schema(ddl_text)
        except LiteParseError as e:
            warnings.append(f"Table definitions were ignored: {e}")
    res = analyze(sql, dialect, parse_sql, DEFAULT_REGISTRY, schema, disabled, enabled)
    res.warnings = warnings + res.warnings
    return res
