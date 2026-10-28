"""Scorer tests with fake analyzer outputs. No sqlglot. Dev split only on the real corpus."""
import json
from pathlib import Path

from analyzer.evaluate import (
    Rate, evaluate, render_markdown, score, wilson,
)
from analyzer.parser import AnalysisResult
from analyzer.rules import Finding

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
KINDS = {"QT001": "syntactic", "QT002": "syntactic", "QT003": "syntactic",
         "QT004": "syntactic", "QT101": "schema", "QT102": "schema"}


def _res(*ids, status="analysed", reason=None):
    return AnalysisResult(status, "tsql", findings=[Finding(i, "low", "m") for i in ids], reason=reason)


def _e(file, label, rules=(), split="dev"):
    return {"file": file, "label": label, "rules": list(rules), "split": split,
            "needs_schema": False, "note": ""}


def _raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    return False


def test_wilson_known_values():
    lo, hi = wilson(27, 30)
    assert abs(lo - 0.7438) < 0.001 and abs(hi - 0.9654) < 0.001
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == 1.0
    assert wilson(0, 0) == (0.0, 1.0)
    assert _raises(lambda: wilson(5, 3), ValueError)


def test_rate_string():
    assert str(Rate(27, 30)).startswith("27/30 (90.0%, 95% CI 74.4-96.5%)")
    assert "n/a" in str(Rate(0, 0))


def _scenario():
    entries = [
        _e("p/A", "planted", ["QT001"]),
        _e("p/B", "planted", ["QT002"]),
        _e("p/C", "planted", ["QT001", "QT002"]),
        _e("p/D", "planted", ["QT004"]),                 # will be not analysed -> miss
        _e("p/E", "planted", ["QT003", "QT102"]),        # mixed kinds
        _e("c/F", "clean"), _e("c/G", "clean"), _e("c/H", "clean"),
    ]
    results = {
        "p/A": _res("QT001"),
        "p/B": _res(),                                    # missed
        "p/C": _res("QT001", "QT002", "QT004"),           # caught + 1 extra
        "p/D": _res(status="not_analysed", reason="parse"),
        "p/E": _res("QT003"),                             # syntactic part only
        "c/F": _res("QT004"),                             # false alarm
        "c/G": _res(),
        "c/H": _res(status="not_analysed", reason="parse"),
    }
    return entries, results


def test_score_both_kinds():
    entries, results = _scenario()
    r = score(entries, results, KINDS)
    assert (r.catch.k, r.catch.n) == (2, 5)               # A, C caught; B, D, E missed
    assert sorted(r.missed) == ["p/B", "p/D", "p/E"]
    assert (r.false_alarm.k, r.false_alarm.n) == (1, 2)   # H excluded (not analysed)
    assert (r.parse_success.k, r.parse_success.n) == (6, 8)
    assert r.false_alarms_by_rule == {"QT004": 1}
    assert r.extras_on_planted == [("p/C", ["QT004"])]
    assert {f for f, _, _ in r.not_analysed} == {"p/D", "c/H"}


def test_score_syntactic_view_only():
    entries, results = _scenario()
    r = score(entries, results, KINDS, kinds=("syntactic",))
    assert (r.catch.k, r.catch.n) == (3, 5)               # E now expects only QT003 -> caught
    assert "p/E" not in r.missed
    assert "QT102" not in r.per_rule_recall


def test_schema_only_planted_excluded_in_syntactic_view():
    entries = [_e("p/X", "planted", ["QT101"]), _e("p/Y", "planted", ["QT001"])]
    results = {"p/X": _res(), "p/Y": _res("QT001")}
    r = score(entries, results, KINDS, kinds=("syntactic",))
    assert (r.catch.k, r.catch.n) == (1, 1)


def test_findings_outside_scored_kinds_ignored():
    entries = [_e("c/Z", "clean")]
    r = score(entries, {"c/Z": _res("QT101")}, KINDS, kinds=("syntactic",))
    assert (r.false_alarm.k, r.false_alarm.n) == (0, 1)


def test_per_rule_recall():
    entries, results = _scenario()
    r = score(entries, results, KINDS)
    assert (r.per_rule_recall["QT001"].k, r.per_rule_recall["QT001"].n) == (2, 2)
    assert (r.per_rule_recall["QT002"].k, r.per_rule_recall["QT002"].n) == (1, 2)
    assert (r.per_rule_recall["QT004"].k, r.per_rule_recall["QT004"].n) == (0, 1)


def test_heldout_guard():
    nothing = lambda sql, entry: _res()
    assert _raises(lambda: evaluate(CORPUS, nothing, split="heldout"), PermissionError)
    assert _raises(lambda: evaluate(CORPUS, nothing, split="all"), PermissionError)
    assert _raises(lambda: evaluate(CORPUS, nothing, split="test"), ValueError)


def test_real_corpus_dev_oracle_and_silent_analyzer():
    exp = {e["file"]: e for e in json.loads((CORPUS / "expected.json").read_text())["queries"]}

    def oracle(sql, entry):          # fires exactly the expected rules (planted) / nothing (clean)
        return _res(*entry["rules"])
    r = evaluate(CORPUS, oracle, split="dev")
    assert (r.catch.k, r.catch.n) == (18, 18)             # 18 planted dev queries
    assert (r.false_alarm.k, r.false_alarm.n) == (0, 22)  # 22 clean dev queries
    assert r.parse_success.k == r.parse_success.n == 40

    silent = evaluate(CORPUS, lambda sql, entry: _res(), split="dev")
    assert silent.catch.k == 0 and len(silent.missed) == 18

    noisy = evaluate(CORPUS, lambda sql, entry: _res("QT001"), split="dev")
    assert noisy.false_alarm.k == 22                      # flags everything -> 100% false alarms


def test_markdown_report_contents():
    entries, results = _scenario()
    md = render_markdown(score(entries, results, KINDS), "Test")
    assert "2/5" in md and "Missed planted queries" in md and "False alarms" in md
    assert "Not analysed" in md and "Single-author" in md and "adversarial" in md
