"""Direct tests of the lightweight parser: tokens, groups, blocks, FROM items, schema reader."""
from analyzer.tsql_lite import LiteParseError, build_groups, parse_schema, parse_sql, tokenize


def _raises(fn):
    try:
        fn()
    except LiteParseError:
        return True
    return False


def test_tokens_lines_and_comments():
    toks = tokenize("SELECT a -- c'omment\nFROM t /* x\ny */ WHERE b = N'it''s'")
    assert [t.text for t in toks] == ["SELECT", "a", "FROM", "t", "WHERE", "b", "=", "N'it''s'"]
    assert [t.line for t in toks][:3] == [1, 1, 2] and toks[4].line == 3
    assert toks[-1].kind == "string"


def test_unterminated_and_unbalanced():
    assert _raises(lambda: tokenize("SELECT 'abc"))
    assert _raises(lambda: build_groups(tokenize("SELECT (a")))
    assert _raises(lambda: build_groups(tokenize("SELECT a)")))


def test_block_structure():
    p = parse_sql("SELECT DISTINCT TOP 5 a, b AS c FROM dbo.t x JOIN u ON u.k = x.k "
                  "LEFT OUTER JOIN w ON w.k = u.k WHERE a = 1 GROUP BY a HAVING COUNT(*) > 1 ORDER BY a")
    b = p.roots[0]
    assert b.distinct and b.top == "5" and len(b.select_items) == 2
    assert [(f.name, f.alias, f.join) for f in b.from_items] == [
        ("t", "x", None), ("u", "u", "INNER"), ("w", "w", "LEFT")]
    assert b.where and b.group_by and b.having and b.order_by


def test_comma_groups_derived_and_cte():
    p = parse_sql("WITH c AS (SELECT a FROM t) SELECT 1 FROM c, (SELECT b FROM u) AS d, v")
    root = p.roots[0]
    assert [f.cg for f in root.from_items] == [0, 1, 2]
    assert root.from_items[1].kind == "derived" and root.from_items[1].alias == "d"
    assert sorted(c.clause_ctx for c in root.children) == ["cte", "from"]
    assert len(list(p.blocks())) == 3


def test_union_members_and_statements():
    assert len(parse_sql("SELECT a FROM t UNION ALL SELECT b FROM u").roots) == 2
    assert len(parse_sql("SELECT a FROM t; SELECT b FROM u").roots) == 2


def test_left_function_is_not_a_join():
    p = parse_sql("SELECT a FROM t JOIN u ON LEFT(u.k, 2) = t.k")
    assert len(p.roots[0].from_items) == 2


def test_schema_reader():
    s = parse_schema("""CREATE TABLE dbo.[Order] (
        Id INT NOT NULL PRIMARY KEY, Code VARCHAR(10) NULL UNIQUE, Amt DECIMAL(10,2) NOT NULL,
        Note NVARCHAR(50), CONSTRAINT uq UNIQUE (Amt, Note));
        CREATE TABLE x (a INT, b INT, PRIMARY KEY (a, b));""")
    o = s.tables["order"]
    assert o.pk == ("id",) and ("code",) in o.uniques and ("amt", "note") in o.uniques
    assert not o.columns["id"].nullable and o.columns["note"].nullable and o.columns["code"].nullable
    assert o.columns["amt"].type_base == "decimal" and o.columns["code"].family == "ansi_str"
    x = s.tables["x"]
    assert x.pk == ("a", "b") and not x.columns["a"].nullable
    assert _raises(lambda: parse_schema("SELECT 1")) and _raises(lambda: parse_schema(""))
