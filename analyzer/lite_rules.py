"""The 12 rules (QT001-QT009 syntactic, QT101-QT103 schema-dependent) on the lightweight parser.

Heuristics, not proofs: each rule says "may" and has known blind spots (see docs/KNOWN_LIMITATIONS.md).
Rule ids and definitions come from corpus/taxonomy.json.
"""
from __future__ import annotations

from analyzer.rules import DEFAULT_REGISTRY, Context, Finding, Rule, RuleRegistry
from analyzer.tsql_lite import (
    bool_tree, column_refs, is_kw, is_punct, is_tok, leaves, literal_kind, outer_function_calls,
    simple_column, split_comparison, split_top,
)

JOINS = ("INNER", "LEFT", "RIGHT", "FULL")


def _on_regions(b):
    regions = [b.where] if b.where else []
    regions += [fi.on for fi in b.from_items if fi.on]
    return regions


# ---------- QT001 ----------
def check_select_star(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        if b.prev and b.prev[-1] == "EXISTS":
            continue
        for item in b.select_items:
            star = len(item) == 1 and is_tok(item[0], "op") and item[0].text == "*"
            qstar = (len(item) in (3, 5) and is_tok(item[-1], "op") and item[-1].text == "*"
                     and is_punct(item[-2], "."))
            if star or qstar:
                out.append(Finding("QT001", "low", "SELECT * returns every column; list only the columns you need.",
                                   item[0].line))
    return out


# ---------- QT002 ----------
def check_function_on_column(ctx: Context) -> list:
    out, seen = [], set()
    for b in ctx.tree.blocks():
        for items in _on_regions(b):
            for leaf in leaves(bool_tree(items)):
                for name, grp in outer_function_calls(leaf):
                    cols = column_refs([name, grp])      # keeps date-part/type handling for DATEADD, CAST, CONVERT
                    if cols and (name.line, name.text) not in seen:
                        seen.add((name.line, name.text))
                        q, c, _ = cols[0]
                        col = f"{q}.{c}" if q else c
                        out.append(Finding("QT002", "high",
                                           f"{name.text.upper()}() is applied to column {col} in a filter or join "
                                           f"condition; this may prevent an index seek on that column.", name.line))
    return out


# ---------- QT003 ----------
def check_not_in_subquery(ctx: Context) -> list:
    return [Finding("QT003", "high",
                    "NOT IN (subquery) returns no rows if the subquery yields any NULL; consider NOT EXISTS.",
                    b.prev_line or b.line)
            for b in ctx.tree.blocks() if tuple(b.prev[-2:]) == ("NOT", "IN")]


# ---------- QT004 ----------
def check_distinct_with_join(ctx: Context) -> list:
    return [Finding("QT004", "medium",
                    "SELECT DISTINCT together with a JOIN can hide duplicate rows produced by the join; "
                    "check whether EXISTS or a different join would be correct.", b.line)
            for b in ctx.tree.blocks()
            if b.distinct and any(fi.join in JOINS + ("CROSS",) for fi in b.from_items)]


# ---------- QT005 ----------
def _colset(tree) -> set:
    s = set()
    for leaf in leaves(tree):
        for q, c, _ in column_refs(leaf):
            s.add(f"{q}.{c}" if q else c)
    return s


def _or_nodes(tree):
    if tree[0] == "or":
        yield tree
    if tree[0] in ("or", "and"):
        for c in tree[1]:
            yield from _or_nodes(c)


def check_or_across_columns(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        if not b.where:
            continue
        for node in _or_nodes(bool_tree(b.where)):
            sets = [frozenset(_colset(c)) for c in node[1]]
            sets = [s for s in sets if s]
            if len(sets) >= 2 and len(set(sets)) > 1:
                out.append(Finding("QT005", "medium",
                                   "OR across different columns often prevents index use; consider UNION ALL "
                                   "of separate seeks.", node[2]))
    return out


# ---------- QT006 ----------
def _own_items(b) -> list:
    items = [x for it in b.select_items for x in it] + list(b.where) + list(b.group_by) + list(b.having) + list(b.order_by)
    for fi in b.from_items:
        if fi.on:
            items += fi.on
    return items


def check_scalar_subquery(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        outer, p = set(), b
        while p is not None:
            outer |= p.aliases()
            p = p.parent
        for c in b.children:
            if c.clause_ctx != "select":
                continue
            inner, quals = set(), set()
            for x in c.walk():
                inner |= x.aliases()
                quals |= {q for q, _, _ in column_refs(_own_items(x)) if q}
            if (quals - inner) & outer:
                out.append(Finding("QT006", "medium",
                                   "Correlated scalar subquery in the SELECT list runs once per outer row; "
                                   "consider a JOIN with GROUP BY or APPLY.", c.line))
    return out


# ---------- QT007 ----------
def check_order_by_in_subquery(ctx: Context) -> list:
    return [Finding("QT007", "low",
                    "TOP 100 PERCENT ... ORDER BY inside a subquery or CTE has no effect on the result order.",
                    b.line)
            for b in ctx.tree.blocks()
            if not b.root and b.percent and (b.top or "").strip("() ") == "100" and b.order_by]


# ---------- QT008 ----------
def check_leading_wildcard_like(ctx: Context) -> list:
    out, t = [], ctx.tree.tokens
    for i in range(len(t) - 1):
        if is_kw(t[i], "LIKE") and t[i + 1].kind == "string":
            txt = t[i + 1].text
            inner = txt[txt.index("'") + 1:-1]
            if inner.startswith("%") and inner.strip("%_"):
                out.append(Finding("QT008", "medium",
                                   "LIKE pattern starts with %, so an index on the column cannot be used for a seek.",
                                   t[i + 1].line))
    return out


# ---------- QT009 ----------
def check_missing_join_condition(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        fis = b.from_items
        cgs = sorted({fi.cg for fi in fis})
        if len(cgs) >= 2:
            alias_cg = {fi.alias: fi.cg for fi in fis if fi.alias}
            comp = {c: c for c in cgs}

            def find(x):
                while comp[x] != x:
                    x = comp[x]
                return x
            unknown = False
            for conj in (split_top(b.where, "AND") if b.where else []):
                refs = column_refs(conj)
                if any(q is None for q, _, _ in refs):
                    unknown = True
                linked = sorted({alias_cg[q] for q, _, _ in refs if q in alias_cg})
                for other in linked[1:]:
                    comp[find(other)] = find(linked[0])
            if not unknown and len({find(c) for c in cgs}) > 1:
                second = next(fi for fi in fis if fi.cg == cgs[1])
                out.append(Finding("QT009", "high",
                                   "Comma-separated tables have no condition linking them, which produces a "
                                   "cross product.", second.line))
        for idx, fi in enumerate(fis):
            if fi.join not in JOINS or fi.on is None or not fi.alias:
                continue
            refs = column_refs(fi.on)
            if any(q is None for q, _, _ in refs):
                continue
            quals = {q for q, _, _ in refs}
            earlier = {x.alias for x in fis[:idx] if x.alias}
            if fi.alias not in quals or not (quals & earlier):
                out.append(Finding("QT009", "high",
                                   f"The ON condition of the join to {fi.alias} does not relate it to the "
                                   f"earlier tables, which can produce a cross product.", fi.line))
    return out


# ---------- schema helpers ----------
def _resolve(block, qual, name, schema):
    """(TableDef, Column) for a column reference, or None if unknown or ambiguous."""
    b = block
    while b is not None:
        tabs = [(fi.alias, schema.tables.get(fi.name) if fi.kind == "table" else None, fi) for fi in b.from_items]
        if qual:
            for alias, t, fi in tabs:
                if alias == qual or (fi.kind == "table" and fi.name == qual):
                    col = t.columns.get(name) if t is not None else None
                    return (t, col) if col is not None else None
        else:
            cands = [(t, t.columns[name]) for _, t, _ in tabs if t is not None and name in t.columns]
            unknown = any(t is None for _, t, _ in tabs)
            if len(cands) == 1 and not unknown:
                return cands[0]
            if cands or unknown:
                return None
        b = b.parent
    return None


# ---------- QT101 ----------
def check_implicit_conversion(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        for items in _on_regions(b):
            for leaf in leaves(bool_tree(items)):
                cmpn = split_comparison(leaf)
                if not cmpn:
                    continue
                left, _, right = cmpn
                for colside, litside in ((left, right), (right, left)):
                    sc, lk = simple_column(colside), literal_kind(litside)
                    if not sc or not lk:
                        continue
                    res = _resolve(b, sc[0], sc[1], ctx.schema)
                    if res and res[1].family == "ansi_str" and lk in ("num", "nstr"):
                        what = "a number" if lk == "num" else "an NVARCHAR literal"
                        out.append(Finding("QT101", "high",
                                           f"Column {sc[1]} is {res[1].type_base.upper()} but is compared with {what}; "
                                           f"SQL Server converts the column, which can prevent an index seek.",
                                           leaf[0].line))
    return out


# ---------- QT102 ----------
def check_not_in_nullable(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        if tuple(b.prev[-2:]) != ("NOT", "IN") or len(b.select_items) != 1:
            continue
        item = b.select_items[0]
        if len(item) >= 3 and is_kw(item[-2], "AS"):
            item = item[:-2]
        sc = simple_column(item)
        res = _resolve(b, sc[0], sc[1], ctx.schema) if sc else None
        if res and res[1].nullable:
            out.append(Finding("QT102", "high",
                               f"The subquery column {sc[1]} is nullable, so NOT IN can silently return no rows.",
                               b.prev_line or b.line))
    return out


# ---------- QT103 ----------
def check_join_non_unique_key(ctx: Context) -> list:
    out = []
    for b in ctx.tree.blocks():
        tab_of = {fi.alias: ctx.schema.tables.get(fi.name) for fi in b.from_items if fi.alias and fi.kind == "table"}
        for fi in b.from_items:
            if fi.join not in JOINS or not fi.on or not fi.alias:
                continue
            J, eq, neq = fi.alias, {}, []
            for conj in split_top(fi.on, "AND"):
                cmpn = split_comparison(conj)
                if not cmpn:
                    continue
                a, c = simple_column(cmpn[0]), simple_column(cmpn[2])
                if not a or not c or a[0] is None or c[0] is None or a[0] == c[0] or J not in (a[0], c[0]):
                    continue
                (_, jn), (kq, kn) = (a, c) if a[0] == J else (c, a)
                if cmpn[1] == "=":
                    sets = eq.setdefault(kq, [set(), set()])
                    sets[0].add(jn)
                    sets[1].add(kn)
                else:
                    neq.append((kq, jn, kn))
            for K, (cj, ck) in eq.items():
                tj, tk = tab_of.get(J), tab_of.get(K)
                if tj is None or tk is None:
                    continue
                if any(key <= cj for key in tj.keys()) or any(key <= ck for key in tk.keys()):
                    continue
                if tj is tk and any(k == K and jn == kn and jn in tj.pk for k, jn, kn in neq):
                    continue                      # self-join comparing a table with itself on its own key
                out.append(Finding("QT103", "high",
                                   f"The join between {K} and {J} is on columns that are not a unique key on "
                                   f"either side, so rows can multiply.", fi.line))
    return out


RULES = [
    Rule("QT001", "select_star", "low", "syntactic", "SELECT * returns columns you do not need, breaks when the table changes and blocks covering-index use.",
         "SELECT * FROM dbo.Customer", "SELECT CustomerID, LastName FROM dbo.Customer", check_select_star),
    Rule("QT002", "function_on_filtered_column", "high", "syntactic", "Wrapping a column in a function in a filter usually forces a scan instead of an index seek.",
         "WHERE YEAR(OrderDate) = 2024", "WHERE OrderDate >= '2024-01-01' AND OrderDate < '2025-01-01'", check_function_on_column),
    Rule("QT003", "not_in_subquery", "high", "syntactic", "If the subquery returns a NULL, NOT IN evaluates to unknown for every row and returns nothing.",
         "WHERE id NOT IN (SELECT id FROM t)", "WHERE NOT EXISTS (SELECT 1 FROM t WHERE t.id = x.id)", check_not_in_subquery),
    Rule("QT004", "distinct_with_join", "medium", "syntactic", "DISTINCT after a JOIN often hides accidental row multiplication and costs a sort.",
         "SELECT DISTINCT c.id FROM c JOIN o ON o.cid = c.id", "SELECT c.id FROM c WHERE EXISTS (SELECT 1 FROM o WHERE o.cid = c.id)", check_distinct_with_join),
    Rule("QT005", "or_across_columns", "medium", "syntactic", "OR over different columns rarely lets the optimizer use one index.",
         "WHERE a = 1 OR b = 2", "SELECT ... WHERE a = 1 UNION ALL SELECT ... WHERE b = 2 AND a <> 1", check_or_across_columns),
    Rule("QT006", "scalar_subquery_in_select", "medium", "syntactic", "A correlated scalar subquery in the SELECT list can run once per outer row.",
         "SELECT c.id, (SELECT SUM(x) FROM o WHERE o.cid = c.id) FROM c", "SELECT c.id, SUM(o.x) FROM c LEFT JOIN o ON o.cid = c.id GROUP BY c.id", check_scalar_subquery),
    Rule("QT007", "order_by_in_subquery", "low", "syntactic", "TOP 100 PERCENT with ORDER BY in a subquery or CTE does not guarantee any order.",
         "SELECT * FROM (SELECT TOP 100 PERCENT a FROM t ORDER BY a) x", "SELECT a FROM t ORDER BY a", check_order_by_in_subquery),
    Rule("QT008", "leading_wildcard_like", "medium", "syntactic", "A leading % prevents an index seek on the column.",
         "WHERE Name LIKE '%bike%'", "WHERE Name LIKE 'bike%'   (or use full-text search)", check_leading_wildcard_like),
    Rule("QT009", "missing_join_condition", "high", "syntactic", "A join with no condition relating the tables returns the cross product.",
         "FROM a, b WHERE a.x > 1", "FROM a JOIN b ON b.a_id = a.id WHERE a.x > 1", check_missing_join_condition),
    Rule("QT101", "implicit_conversion", "high", "schema", "Comparing a VARCHAR column with a number or NVARCHAR value makes SQL Server convert the column, which can prevent an index seek.",
         "WHERE Phone = 5551234", "WHERE Phone = '5551234'", check_implicit_conversion),
    Rule("QT102", "not_in_nullable_column", "high", "schema", "NOT IN over a nullable column can silently return no rows.",
         "WHERE id NOT IN (SELECT manager_id FROM emp)", "WHERE NOT EXISTS (SELECT 1 FROM emp m WHERE m.manager_id = e.id)", check_not_in_nullable),
    Rule("QT103", "join_on_non_unique_key", "high", "schema", "Joining on columns that are unique on neither side multiplies rows.",
         "JOIN p ON d.UnitPrice = p.ListPrice", "JOIN p ON d.ProductID = p.ProductID", check_join_non_unique_key),
]


def register_all(registry: RuleRegistry) -> RuleRegistry:
    for r in RULES:
        if r.id not in registry.ids():
            registry.register(r)
    return registry


register_all(DEFAULT_REGISTRY)
