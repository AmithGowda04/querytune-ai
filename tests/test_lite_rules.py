"""Rule behaviour on NEW inputs (not corpus queries): tricky positives and negatives. Stdlib only."""
from analyzer.api import analyze_sql
from analyzer.dialects import get_dialect

T = get_dialect("tsql")
DDL = """
CREATE TABLE u (id INT NOT NULL PRIMARY KEY, g INT NOT NULL, mgr INT NULL, code VARCHAR(10) NULL,
                nm NVARCHAR(10) NOT NULL, d DATETIME NOT NULL, a INT NOT NULL);
CREATE TABLE v (id INT NOT NULL PRIMARY KEY, g INT NOT NULL);
CREATE TABLE d2 (a INT NOT NULL, b INT NOT NULL, PRIMARY KEY (a, b));
"""


def fired(sql, ddl=None):
    r = analyze_sql(sql, T, ddl)
    assert r.status == "analysed", r.reason
    return sorted({f.rule_id for f in r.findings})


def test_qt001():
    assert fired("SELECT t.* FROM t") == ["QT001"]
    assert fired("SELECT * FROM (SELECT a FROM t) x") == ["QT001"]
    assert fired("SELECT a * b FROM t") == []
    assert fired("SELECT COUNT(*) FROM t") == []
    assert fired("SELECT 1 FROM x WHERE EXISTS (SELECT * FROM y)") == []
    assert fired("SELECT 1 FROM x WHERE NOT EXISTS (SELECT * FROM y)") == []


def test_qt002():
    assert fired("SELECT a FROM t WHERE LEFT(Name, 3) = 'abc'") == ["QT002"]
    assert fired("SELECT a FROM t WHERE DATEDIFF(day, OrderDate, GETDATE()) > 30") == ["QT002"]
    assert fired("SELECT a FROM t JOIN u ON t.x = UPPER(u.y)") == ["QT002"]
    assert fired("SELECT a FROM t WHERE UPPER(LTRIM(n)) = 'A'") == ["QT002"]
    assert fired("SELECT a FROM t WHERE n = LTRIM(@p)") == []
    assert fired("SELECT a FROM t WHERE d = CAST(@d AS DATE)") == []
    assert fired("SELECT a FROM t WHERE x IN (1, 2)") == []
    assert fired("SELECT UPPER(n) FROM t") == []
    assert fired("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.k = t.k)") == []
    # columns that happen to be called like date parts / types are still columns
    assert fired("SELECT a FROM t WHERE Date > '2024-01-01' AND Year = 5 AND n LIKE 'x%'") == []
    assert fired("SELECT a FROM t WHERE CAST(OrderDate AS DATE) = '2024-03-01'") == ["QT002"]
    assert fired("SELECT a FROM t WHERE DATEPART(month, OrderDate) = 3") == ["QT002"]
    assert fired("SELECT a FROM t WHERE Name COLLATE Latin1_General_CI_AS = 'x' OR Name = 'y'") == []


def test_qt003():
    assert fired("SELECT a FROM t WHERE a NOT IN (SELECT b FROM u)") == ["QT003"]
    assert fired("SELECT a FROM t WHERE a NOT IN (1, 2)") == []
    assert fired("SELECT a FROM t WHERE a IN (SELECT b FROM u)") == []


def test_qt004():
    assert fired("SELECT DISTINCT a FROM t JOIN u ON u.k = t.k") == ["QT004"]
    assert fired("SELECT DISTINCT a FROM t") == []
    assert fired("SELECT COUNT(DISTINCT a) FROM t JOIN u ON u.k = t.k") == []


def test_qt005():
    assert fired("SELECT a FROM t WHERE a = 1 OR b = 2") == ["QT005"]
    assert fired("SELECT a FROM t WHERE a = 1 OR a = 2") == []
    assert fired("SELECT a FROM t WHERE (a = 1 AND b = 2) OR (a = 3 AND b = 4)") == []
    assert fired("SELECT a FROM t WHERE x BETWEEN 1 AND 2 OR y = 3") == ["QT005"]
    assert fired("SELECT a FROM t WHERE a = 1 AND (b = 2 OR c = 3)") == ["QT005"]
    assert fired("SELECT a FROM t WHERE a = 1 AND b BETWEEN 1 AND 5") == []


def test_qt006():
    assert fired("SELECT c.id, (SELECT MAX(o.x) FROM o WHERE o.cid = c.id) FROM c") == ["QT006"]
    assert fired("SELECT c.id, ISNULL((SELECT MAX(o.x) FROM o WHERE o.cid = c.id), 0) FROM c") == ["QT006"]
    assert fired("SELECT c.id, (SELECT MAX(o.x) FROM o) FROM c") == []
    assert fired("SELECT c.id FROM c WHERE c.v > (SELECT AVG(o.x) FROM o WHERE o.cid = c.id)") == []


def test_qt007():
    assert fired("SELECT x.a FROM (SELECT TOP 100 PERCENT a FROM t ORDER BY a) x") == ["QT007"]
    assert fired("SELECT x.a FROM (SELECT TOP 5 a FROM t ORDER BY a) x") == []
    assert fired("SELECT TOP 100 PERCENT a FROM t ORDER BY a") == []


def test_qt008():
    assert fired("SELECT a FROM t WHERE n LIKE '%x'") == ["QT008"]
    assert fired("SELECT a FROM t WHERE n NOT LIKE '%abc%'") == ["QT008"]
    assert fired("SELECT a FROM t WHERE n LIKE 'x%'") == []
    assert fired("SELECT a FROM t WHERE n LIKE '%'") == []


def test_qt009():
    assert fired("SELECT t.a FROM t, u WHERE t.a > 1") == ["QT009"]
    assert fired("SELECT t.a FROM t, u WHERE t.k = u.k") == []
    assert fired("SELECT t.a FROM t, u, w WHERE t.k = u.k") == ["QT009"]
    assert fired("SELECT t.a FROM t JOIN u ON t.a > 1") == ["QT009"]
    assert fired("SELECT t.a FROM t JOIN u ON 1 = 1") == ["QT009"]
    assert fired("SELECT t.a FROM t CROSS JOIN u") == []
    assert fired("SELECT t.a FROM t JOIN u ON k = j") == []           # unqualified: cannot tell
    assert fired("SELECT t.a FROM t LEFT JOIN u ON u.k = t.k AND u.z = 1") == []


def test_qt101():
    assert fired("SELECT id FROM u WHERE code = 5", DDL) == ["QT101"]
    assert fired("SELECT id FROM u WHERE code = N'x'", DDL) == ["QT101"]
    assert fired("SELECT id FROM u WHERE code = 'x'", DDL) == []
    assert fired("SELECT id FROM u WHERE nm = 'x'", DDL) == []
    assert fired("SELECT id FROM u WHERE d = '2024-01-01'", DDL) == []
    assert fired("SELECT id FROM u WHERE id = '5'", DDL) == []
    assert fired("SELECT id FROM u WHERE code = 5") == []              # no schema: rule skipped


def test_qt102():
    assert fired("SELECT id FROM u WHERE id NOT IN (SELECT mgr FROM u)", DDL) == ["QT003", "QT102"]
    assert fired("SELECT id FROM u WHERE id NOT IN (SELECT id FROM u)", DDL) == ["QT003"]
    assert fired("SELECT id FROM u WHERE id NOT IN (SELECT mgr FROM u)") == ["QT003"]


def test_qt103():
    assert fired("SELECT 1 FROM u JOIN v ON u.g = v.g", DDL) == ["QT103"]
    assert fired("SELECT 1 FROM u JOIN v ON u.id = v.id", DDL) == []
    assert fired("SELECT 1 FROM u JOIN v ON u.g = v.id", DDL) == []
    assert fired("SELECT 1 FROM u JOIN d2 ON d2.a = u.g", DDL) == ["QT103"]
    assert fired("SELECT 1 FROM u JOIN d2 ON d2.a = u.id AND d2.b = u.g", DDL) == []
    assert fired("SELECT 1 FROM u x JOIN u y ON x.g = y.g AND x.id < y.id", DDL) == []   # pairs of one table
    assert fired("SELECT 1 FROM u x JOIN u y ON x.g = y.g", DDL) == ["QT103"]


def test_structure_and_robustness():
    assert fired("DECLARE @x INT = 5; SELECT a FROM t WHERE b = @x") == []
    assert fired("SELECT * FROM t; SELECT a FROM t WHERE LEFT(n,1)='a'") == ["QT001", "QT002"]
    assert fired("WITH c AS (SELECT * FROM t) SELECT a FROM c") == ["QT001"]
    assert fired("SELECT a FROM t UNION ALL SELECT * FROM u") == ["QT001"]
    assert fired("-- it's fine\nSELECT a FROM t /* don't */") == []
    assert fired("SELECT a FROM t\nGO\nSELECT * FROM u") == ["QT001"]


def test_unparsable_input_is_not_analysed_never_clean():
    for bad, why in (("SELECT (a FROM t", "unbalanced"), ("SELECT 'x FROM t", "unterminated"),
                     ("INSERT INTO t VALUES (1)", "unsupported"), ("-- only a comment", "no SQL"),
                     ("DECLARE @x INT = 1", "no SELECT")):
        r = analyze_sql(bad, T)
        assert r.status == "not_analysed" and r.findings == [] and why in r.reason, (bad, r.reason)


def test_bad_ddl_is_ignored_with_a_warning():
    r = analyze_sql("SELECT * FROM t", T, "this is not ddl")
    assert r.status == "analysed" and any("Table definitions were ignored" in w for w in r.warnings)
    assert [f.rule_id for f in r.findings] == ["QT001"]


def test_dialect_mismatch_warning_and_schema_rules_skipped_for_postgres():
    r = analyze_sql("SELECT TOP 5 * FROM t", get_dialect("postgres"), DDL)
    assert any("T-SQL" in w for w in r.warnings)
    assert all(rid not in r.rules_run for rid in ("QT101", "QT102", "QT103"))
