"""Rule framework + analyze() tested with fake rules and a fake parser. No sqlglot."""
import json
from pathlib import Path

from analyzer.dialects import get_dialect
from analyzer.parser import MAX_SQL_CHARS, analyze
from analyzer.rules import (
    DEFAULT_REGISTRY, Context, Finding, Rule, RuleRegistry,
)

ROOT = Path(__file__).resolve().parent.parent
TSQL = get_dialect("tsql")
PG = get_dialect("postgres")


def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False


def _rule(rid="QT001", kind="syntactic", check=None, **kw):
    if check is None:
        check = lambda ctx: [Finding(rid, "low", f"{rid} fired", line=1)]
    base = dict(id=rid, name="n", severity="low", kind=kind, rationale="why",
                bad_example="bad", good_example="good", check=check)
    base.update(kw)
    return Rule(**base)


def _fake_parse(sql, read):
    return "TREE"


# ---- Rule / Finding validation ----
def test_rule_validation():
    assert _raises(lambda: _rule(rid="X1"))
    assert _raises(lambda: _rule(severity="critical"))
    assert _raises(lambda: _rule(kind="magic"))
    assert _raises(lambda: _rule(rationale=" "))
    assert _raises(lambda: _rule(bad_example=""))
    assert _raises(lambda: _rule(good_example=""))
    assert _raises(lambda: _rule(check="nope"))
    _rule()  # valid one constructs


def test_finding_validation():
    assert _raises(lambda: Finding("QT001", "urgent", "m"))
    assert _raises(lambda: Finding("QT001", "low", "  "))


def test_duplicate_registration_rejected():
    reg = RuleRegistry()
    reg.register(_rule("QT001"))
    assert _raises(lambda: reg.register(_rule("QT001")))


# ---- selection ----
def _reg():
    reg = RuleRegistry()
    reg.register(_rule("QT001"))
    reg.register(_rule("QT101", kind="schema"))
    reg.register(_rule("QT004", enabled_by_default=False))
    return reg


def test_select_tsql_without_schema():
    run, skipped = _reg().select(TSQL, has_schema=False)
    assert [r.id for r in run] == ["QT001"]
    reasons = dict(skipped)
    assert "needs table definitions" in reasons["QT101"]
    assert reasons["QT004"] == "off by default"


def test_select_tsql_with_schema_and_enabled_override():
    run, _ = _reg().select(TSQL, has_schema=True, enabled=["QT004"])
    assert [r.id for r in run] == ["QT001", "QT004", "QT101"]


def test_select_postgres_never_runs_schema_rules():
    run, skipped = _reg().select(PG, has_schema=True)
    assert [r.id for r in run] == ["QT001"]
    assert "not available for PostgreSQL" in dict(skipped)["QT101"]


def test_disable_switch_and_unknown_ids():
    run, skipped = _reg().select(TSQL, True, disabled=["QT001"])
    assert "QT001" not in [r.id for r in run]
    assert dict(skipped)["QT001"] == "switched off"
    assert _raises(lambda: _reg().select(TSQL, True, disabled=["QT999"]))
    assert _raises(lambda: _reg().select(TSQL, True, enabled=["QT998"]))


# ---- running ----
def test_crashing_rule_is_isolated():
    def boom(ctx):
        raise RuntimeError("secret sql text must not leak")
    reg = RuleRegistry()
    reg.register(_rule("QT001", check=boom))
    reg.register(_rule("QT002"))
    res = analyze("SELECT 1", TSQL, _fake_parse, registry=reg)
    assert res.status == "analysed"
    assert [f.rule_id for f in res.findings] == ["QT002"]
    assert res.rule_errors == [("QT001", "rule crashed: RuntimeError")]
    assert "secret" not in str(res.rule_errors)


def test_misbehaving_rules_recorded():
    reg = RuleRegistry()
    reg.register(_rule("QT001", check=lambda ctx: "not a list"))
    reg.register(_rule("QT002", check=lambda ctx: [Finding("QT003", "low", "wrong id")]))
    res = analyze("SELECT 1", TSQL, _fake_parse, registry=reg)
    assert res.findings == []
    assert {e[0] for e in res.rule_errors} == {"QT001", "QT002"}


# ---- analyze() ----
def test_empty_and_oversized_input_not_analysed():
    for bad in ("", "   \n", None):
        r = analyze(bad, TSQL, _fake_parse, registry=_reg())
        assert r.status == "not_analysed" and r.reason == "empty input"
    big = "SELECT 1 " + "-" * MAX_SQL_CHARS
    r = analyze(big, TSQL, _fake_parse, registry=_reg())
    assert r.status == "not_analysed" and "too large" in r.reason


def test_parse_failure_is_not_analysed_not_clean():
    def bad_parse(sql, read):
        raise ValueError("Invalid expression near X")
    r = analyze("SELECT FROM", TSQL, bad_parse, registry=_reg())
    assert r.status == "not_analysed"
    assert r.findings == [] and r.rules_run == []
    assert "not analysed as T-SQL" in r.reason and "Invalid expression" in r.reason


def test_parser_returning_none_not_analysed():
    r = analyze("SELECT 1", TSQL, lambda s, rd: None, registry=_reg())
    assert r.status == "not_analysed" and "nothing" in r.reason


def test_parse_fn_receives_dialect_read_name():
    seen = []
    def spy(sql, read):
        seen.append(read)
        return "T"
    analyze("SELECT 1", TSQL, spy, registry=_reg())
    analyze("SELECT 1", PG, spy, registry=_reg())
    analyze("SELECT 1", get_dialect("other"), spy, registry=_reg())
    analyze("SELECT 1", get_dialect("other", "mysql"), spy, registry=_reg())
    assert seen == ["tsql", "postgres", None, "mysql"]


def test_findings_sorted_and_rules_run_reported():
    reg = RuleRegistry()
    reg.register(_rule("QT002", check=lambda c: [Finding("QT002", "low", "m", line=5)]))
    reg.register(_rule("QT001", check=lambda c: [Finding("QT001", "low", "m", line=2),
                                                  Finding("QT001", "low", "m", line=9)]))
    r = analyze("SELECT 1", TSQL, _fake_parse, registry=reg)
    assert [(f.rule_id, f.line) for f in r.findings] == [("QT001", 2), ("QT002", 5), ("QT001", 9)]
    assert r.rules_run == ["QT001", "QT002"]


def test_rule_sees_tree_dialect_and_schema_only_when_given():
    got = {}
    def check(ctx: Context):
        got["tree"], got["schema"], got["dialect"] = ctx.tree, ctx.schema, ctx.dialect.key
        return []
    reg = RuleRegistry()
    reg.register(_rule("QT101", kind="schema", check=check))
    analyze("SELECT 1", TSQL, _fake_parse, registry=reg)           # no schema -> rule skipped
    assert got == {}
    analyze("SELECT 1", TSQL, _fake_parse, registry=reg, schema={"t": 1})
    assert got == {"tree": "TREE", "schema": {"t": 1}, "dialect": "tsql"}


def test_mismatch_warning_surfaces_in_result():
    r = analyze("SELECT TOP 5 [a] FROM t", PG, _fake_parse, registry=_reg())
    assert r.status == "analysed" and r.warnings and "T-SQL" in r.warnings[0]


def test_default_registry_ids_are_in_taxonomy():
    tax = json.loads((ROOT / "corpus" / "taxonomy.json").read_text())
    assert DEFAULT_REGISTRY.ids() <= {r["id"] for r in tax["rules"]}
