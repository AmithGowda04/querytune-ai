from analyzer.status import MATCHED, PERF, PROPOSED, SYNTAX, status_for


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def test_ladder():
    assert status_for(False).status == PROPOSED
    assert status_for(True).status == SYNTAX
    assert status_for(True, "matched").status == MATCHED
    assert status_for(True, "matched", "measured_faster").status == PERF


def test_different_results_never_rise_above_proposed():
    s = status_for(True, "different")
    assert s.status == PROPOSED and "DIFFER" in s.flags[0]


def test_unparsable_stays_proposed_even_if_claimed_matched():
    assert status_for(False, "matched").status == PROPOSED


def test_not_exercised_is_flagged_and_not_matched():
    s = status_for(True, "not_exercised")
    assert s.status == SYNTAX and s.flags


def test_benchmark_needs_matched_and_reports_no_gain():
    assert _raises(lambda: status_for(True, None, "measured_faster"))
    assert _raises(lambda: status_for(True, "not_exercised", "measured_faster"))
    s = status_for(True, "matched", "measured_no_gain")
    assert s.status == PERF and "no gain" in s.flags[0]
    assert "SLOWER" in status_for(True, "matched", "measured_slower").flags[0]


def test_bad_values_rejected():
    assert _raises(lambda: status_for(True, "maybe"))
    assert _raises(lambda: status_for(True, "matched", "fast"))
