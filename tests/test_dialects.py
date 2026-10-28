"""Dialect config + mismatch warning. Stdlib only; no sqlglot."""
import json
from pathlib import Path

from analyzer.dialects import (
    detect_mismatch, get_dialect, mismatch_warning, status_label,
)

ROOT = Path(__file__).resolve().parent.parent


def _raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    return False


def test_tsql_config():
    d = get_dialect("tsql")
    assert d.sqlglot_read == "tsql" and d.status == "supported" and d.evaluated
    assert d.rule_kinds == frozenset({"syntactic", "schema"})
    assert d.benchmark_supported and d.equivalence_check == "allowlist"


def test_postgres_config():
    d = get_dialect("postgres")
    assert d.rule_kinds == frozenset({"syntactic"})
    assert not d.evaluated and not d.benchmark_supported
    assert status_label(d) == "Supported, not yet evaluated"


def test_other_config():
    g = get_dialect("other")
    assert g.sqlglot_read is None and g.equivalence_check == "never"
    m = get_dialect("other", "mysql")
    assert m.sqlglot_read == "mysql" and "experimental" in m.label.lower()
    assert "no performance claims" in status_label(m)
    assert not m.benchmark_supported


def test_invalid_selection_rejected():
    assert _raises(lambda: get_dialect("plainsql"), ValueError)
    assert _raises(lambda: get_dialect("other", "cobol"), ValueError)
    assert _raises(lambda: get_dialect("tsql", "mysql"), ValueError)


def test_tsql_syntax_warns_under_postgres():
    sql = "SELECT TOP 10 [Name] FROM dbo.Product WHERE d < GETDATE()"
    found = detect_mismatch(sql, "postgres")
    assert {"TOP n", "[bracketed] identifiers", "GETDATE()"} <= set(found)
    assert "T-SQL" in mismatch_warning(sql, "postgres")


def test_postgres_syntax_warns_under_tsql():
    sql = "SELECT x::int FROM t WHERE n ILIKE 'a%' LIMIT 5"
    assert {"::type casts", "ILIKE", "LIMIT n"} <= set(detect_mismatch(sql, "tsql"))


def test_no_warning_when_dialect_matches_or_other():
    assert mismatch_warning("SELECT TOP 5 * FROM t", "tsql") is None
    assert mismatch_warning("SELECT x::int FROM t LIMIT 5", "postgres") is None
    assert mismatch_warning("SELECT TOP 5 * FROM t", "other") is None


def test_markers_inside_literals_and_comments_ignored():
    sql = "SELECT 'TOP 5 GETDATE()' AS s FROM t -- [x] @v\n/* ISNULL( */"
    assert detect_mismatch(sql, "postgres") == []


def test_dev_corpus_gives_no_false_mismatch_under_tsql():
    # DEV split only: held-out files are not read during rule/tool design.
    exp = json.loads((ROOT / "corpus" / "expected.json").read_text())["queries"]
    for q in exp:
        if q["split"] != "dev":
            continue
        sql = (ROOT / "corpus" / q["file"]).read_text()
        assert detect_mismatch(sql, "tsql") == [], q["file"]
