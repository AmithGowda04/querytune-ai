"""Scrubber tests. Stdlib only. Real-corpus round trip uses the DEV split only."""
import json
from pathlib import Path

from ai.scrub import scrub

ROOT = Path(__file__).resolve().parent.parent


def test_basic_strings_and_numbers_replaced():
    r = scrub("SELECT a FROM t1 WHERE name = 'Alice' AND age > 42 AND col2 = 7")
    assert r.ok
    assert "Alice" not in r.text and "42" not in r.text
    assert "t1" in r.text and "col2" in r.text            # digits inside identifiers untouched
    assert r.strings == 1 and r.numbers == 2           # 42 and 7


def test_round_trip_exact():
    sql = "SELECT a FROM t WHERE n = N'Zoë' AND x = 3.5e2 AND y = 0xFF AND s = 'it''s'"
    r = scrub(sql)
    assert r.ok and r.text != sql
    back, left = r.restore(r.text)
    assert back == sql and left == []


def test_escaped_quote_is_one_literal():
    r = scrub("SELECT 1 FROM t WHERE n = 'O''Brien'")
    assert r.ok and "Brien" not in r.text and r.strings == 1


def test_n_prefix_kept():
    r = scrub("SELECT 1 FROM t WHERE n = N'Secret'")
    assert r.ok and "N'__S1__'" in r.text


def test_same_literal_same_placeholder():
    r = scrub("SELECT 1 FROM t WHERE a = 'x1' OR b = 'x1' OR c = 99 OR d = 99")
    assert r.ok and r.strings == 1 and r.numbers == 2   # the 1 in SELECT 1, and 99 (deduped)


def test_comments_with_quotes_do_not_break_tokenizing():
    sql = "-- don't panic\nSELECT 1 FROM t WHERE n = 'v' /* it's 5 */"
    r = scrub(sql)
    assert r.ok and "don't panic" in r.text and "'v'" not in r.text   # comment kept by default
    r2 = scrub(sql, strip_comments=True)
    assert r2.ok and "panic" not in r2.text and r2.comments_removed == 2


def test_string_containing_comment_markers_is_one_token():
    r = scrub("SELECT 1 FROM t WHERE n = 'a -- b /* c */'")
    assert r.ok and "a --" not in r.text and r.strings == 1


def test_structural_numbers_kept():
    sql = ("SELECT TOP 10 CAST(x AS VARCHAR(20)) AS a, CAST(y AS DECIMAL(10,2)) AS b FROM t "
           "ORDER BY a OFFSET 20 ROWS FETCH NEXT 5 ROWS ONLY")
    r = scrub(sql)
    assert r.ok and r.numbers == 0
    assert r.text == sql
    r2 = scrub("SELECT TOP (10) a FROM t WHERE b > 10")
    assert r2.ok and "TOP (10)" in r2.text and r2.numbers == 1


def test_like_patterns_keep_wildcards():
    r = scrub("SELECT 1 FROM t WHERE a LIKE '%secret%' AND b LIKE 'abc%' AND c LIKE '%'")
    assert r.ok
    assert "'%__S1__%'" in r.text and "'__S2__%'" in r.text and "LIKE '%'" in r.text
    assert "secret" not in r.text and "abc" not in r.text
    assert r.restore(r.text)[0] == "SELECT 1 FROM t WHERE a LIKE '%secret%' AND b LIKE 'abc%' AND c LIKE '%'"


def test_scrub_numbers_off():
    r = scrub("SELECT 1 FROM t WHERE a = 'x1' AND b = 99", scrub_numbers=False)
    assert r.ok and "99" in r.text and "x1" not in r.text


def test_dollar_quoted_string():
    r = scrub("SELECT $$top secret$$ AS s, $tag$more$tag$ AS t")
    assert r.ok and "secret" not in r.text and "more" not in r.text
    assert r.restore(r.text)[0] == "SELECT $$top secret$$ AS s, $tag$more$tag$ AS t"


def test_fail_safe_on_unbalanced_or_backslash_escape():
    for bad in ("SELECT 'abc FROM t", "SELECT * FROM t WHERE n = 'it\\'s secret'"):
        r = scrub(bad)
        assert not r.ok and r.text == "" and r.reason, bad


def test_placeholder_collision_handled():
    sql = "SELECT __S1__ FROM t WHERE a = 'v' AND b = 5"
    r = scrub(sql)
    assert r.ok and r.tag != ""
    assert r.restore(r.text) == (sql, [])


def test_restore_reports_unresolved_placeholders():
    r = scrub("SELECT 1 FROM t WHERE a = 'x1'")
    mangled = r.text.replace("'__S1__'", '"__S1__"')      # model changed the quoting
    back, left = r.restore(mangled)
    assert left == ["__S1__"]


def test_empty_string_and_non_text():
    assert scrub("SELECT '' AS e").ok
    assert not scrub(None).ok


def test_dev_corpus_round_trips_and_leaks_no_literals():
    exp = json.loads((ROOT / "corpus" / "expected.json").read_text())["queries"]
    for q in exp:
        if q["split"] != "dev":
            continue
        sql = (ROOT / "corpus" / q["file"]).read_text()
        r = scrub(sql)
        assert r.ok, q["file"]
        back, left = r.restore(r.text)
        assert back == sql and left == [], q["file"]
    r = scrub((ROOT / "corpus" / "planted" / "P001_select_star.sql").read_text())
    assert "TerritoryID" in r.text and "= 5" not in r.text   # names kept, value scrubbed
