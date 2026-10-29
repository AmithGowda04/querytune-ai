from analyzer.report import ChangeItem, build_change_report
from analyzer.rules import Finding
from analyzer.status import StatusInfo, status_for

ORIG = "SELECT * FROM t"
NEW = "SELECT a FROM t"


def test_report_sections_and_status():
    md = build_change_report(ORIG, NEW, "T-SQL (SQL Server)", status_for(True),
                             [ChangeItem("Explicit columns", "Avoid SELECT *", "none")],
                             [Finding("QT001", "low", "SELECT * used", line=1)], ["check indexes"])
    for part in ("# SQL change report", "## Original", "## Proposed rewrite", "## Changes",
                 "## Rule findings", "## Notes", "## What was NOT verified"):
        assert part in md
    assert "**Validation status: Syntax checked**" in md
    assert "QT001" in md and "line 1" in md
    assert "Results were NOT compared" in md and "Performance was NOT measured" in md


def test_matched_status_still_says_not_proof_and_no_perf():
    md = build_change_report(ORIG, NEW, "T-SQL", status_for(True, "matched"))
    assert "evidence, not proof" in md and "Performance was NOT measured" in md
    assert "Results were NOT compared" not in md


def test_perf_verified_drops_perf_disclaimer_only():
    md = build_change_report(ORIG, NEW, "T-SQL", status_for(True, "matched", "measured_no_gain"))
    assert "Performance verified" in md and "measured: no gain" in md
    assert "Performance was NOT measured" not in md and "not run against the real database" in md


def test_flags_shown_and_no_rewrite_case():
    md = build_change_report(ORIG, NEW, "T-SQL", status_for(True, "different"))
    assert "DIFFER" in md and "Validation status: Proposed" in md
    md2 = build_change_report(ORIG, None, "T-SQL", None)
    assert "No rewrite was proposed" in md2 and "Proposed rewrite" not in md2


def test_backticks_in_sql_do_not_break_the_fence():
    md = build_change_report("SELECT '```' AS x", None, "T-SQL", None)
    assert "````sql" in md


def test_no_performance_numbers_invented():
    md = build_change_report(ORIG, NEW, "T-SQL", StatusInfo("Proposed"))
    import re
    assert not re.search(r"\d+\s*(%|ms|x faster)", md)
