"""Lightweight, stdlib-only T-SQL tokenizer and structural parser.

NOT a full T-SQL grammar and NOT SQLGlot. It builds just enough structure for the rules:
statements -> query blocks (SELECT list, FROM items with joins, WHERE, GROUP BY, HAVING,
ORDER BY, CTEs, set operations, nested subqueries) plus a CREATE TABLE reader for schema rules.
It does not validate syntax; it is tolerant, and raises LiteParseError only for things it cannot
structure (unbalanced parentheses, unterminated literals, unsupported statement types).
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from typing import Iterator, Optional


class LiteParseError(Exception):
    pass


@dataclass(frozen=True)
class Tok:
    kind: str       # ident | qident | string | number | op | punct
    text: str
    line: int

    @property
    def up(self) -> str:
        return self.text.upper() if self.kind == "ident" else self.text


@dataclass
class Group:
    items: list
    line: int


_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<lc>--[^\n]*)
  | (?P<bc>/\*.*?\*/)
  | (?P<string>[Nn]?'(?:[^']|'')*')
  | (?P<dq>"(?:[^"]|"")*")
  | (?P<br>\[[^\]]*\])
  | (?P<number>0[xX][0-9A-Fa-f]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<ident>[A-Za-z_@\#][\w$@\#]*)
  | (?P<op><>|<=|>=|!=|!<|!>|\|\||[=<>+\-*/%&|^~])
  | (?P<punct>[(),.;])
  | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)


def tokenize(sql: str) -> list:
    starts = [0] + [m.end() for m in re.finditer("\n", sql)]
    toks = []
    for m in _TOKEN.finditer(sql):
        k = m.lastgroup
        if k in ("ws", "lc", "bc"):
            continue
        text = m.group(0)
        line = bisect.bisect_right(starts, m.start())
        if k == "other":
            if text in "'\"[":
                raise LiteParseError(f"unterminated string or identifier near line {line}")
            k = "op"
        elif k in ("br", "dq"):
            k = "qident"
        toks.append(Tok(k, text, line))
    return toks


def build_groups(toks: list) -> list:
    stack, opens = [[]], []
    for t in toks:
        if t.kind == "punct" and t.text == "(":
            stack.append([])
            opens.append(t)
        elif t.kind == "punct" and t.text == ")":
            if len(stack) == 1:
                raise LiteParseError(f"unbalanced ')' near line {t.line}")
            items, o = stack.pop(), opens.pop()
            stack[-1].append(Group(items, o.line))
        else:
            stack[-1].append(t)
    if len(stack) > 1:
        raise LiteParseError(f"unbalanced '(' near line {opens[-1].line}")
    return stack[0]


# ---------------- small helpers ----------------
def is_tok(x, kind=None) -> bool:
    return isinstance(x, Tok) and (kind is None or x.kind == kind)


def is_kw(x, *words) -> bool:
    return isinstance(x, Tok) and x.kind == "ident" and x.up in words


def is_punct(x, ch) -> bool:
    return isinstance(x, Tok) and x.kind == "punct" and x.text == ch


def is_query(g) -> bool:
    return isinstance(g, Group) and bool(g.items) and is_kw(g.items[0], "SELECT", "WITH")


def nm(t: Tok) -> str:
    """Lower-cased identifier name without [] or "" quoting."""
    s = t.text
    if t.kind == "qident":
        s = s[1:-1]
    return s.lower()


def split_commas(items: list) -> list:
    parts = [[]]
    for it in items:
        if is_punct(it, ","):
            parts.append([])
        else:
            parts[-1].append(it)
    return [p for p in parts if p]


def split_top(items: list, word: str) -> list:
    """Split on a top-level AND/OR keyword (an AND that belongs to BETWEEN stays attached)."""
    parts, between = [[]], 0
    for it in items:
        if is_kw(it, "BETWEEN"):
            between += 1
        elif is_kw(it, "AND") and word == "AND" and between:
            between -= 1
            parts[-1].append(it)
            continue
        if is_kw(it, word):
            parts.append([])
            continue
        parts[-1].append(it)
    return [p for p in parts if p]


def first_line(items: list, default: int = 0) -> int:
    for it in items:
        return it.line
    return default


# ---------------- boolean expression tree ----------------
def bool_tree(items: list):
    ors = split_top(items, "OR")
    if len(ors) > 1:
        return ("or", [_and_tree(p) for p in ors], first_line(items))
    return _and_tree(items)


def _and_tree(items: list):
    ands = split_top(items, "AND")
    if len(ands) > 1:
        return ("and", [_leaf_tree(p) for p in ands], first_line(items))
    return _leaf_tree(items)


def _leaf_tree(items: list):
    if len(items) == 1 and isinstance(items[0], Group) and not is_query(items[0]):
        return bool_tree(items[0].items)
    return ("leaf", items, first_line(items))


def leaves(tree) -> Iterator[list]:
    if tree[0] == "leaf":
        yield tree[1]
    else:
        for c in tree[1]:
            yield from leaves(c)


# ---------------- identifiers / columns / functions ----------------
KEYWORDS = {
    "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE", "BETWEEN", "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END",
    "ASC", "DESC", "AS", "DISTINCT", "ALL", "ANY", "SOME", "TOP", "SELECT", "FROM", "WHERE", "ON", "JOIN", "OVER",
    "PARTITION", "BY", "ESCAPE", "COLLATE", "CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_USER", "TRUE", "FALSE",
    "PERCENT", "ROWS", "ONLY", "NEXT", "FIRST", "FETCH", "OFFSET", "UNION", "INTERSECT", "EXCEPT", "WITH", "TIES"}
# Date parts and type names are NOT global keywords (a column may be called n, date, year ...);
# they are skipped contextually inside these functions.
DATE_FUNCS = {"DATEADD", "DATEDIFF", "DATEDIFF_BIG", "DATEPART", "DATENAME", "DATETRUNC", "DATE_BUCKET"}
CAST_FUNCS = {"CAST", "TRY_CAST", "PARSE", "TRY_PARSE"}
CONVERT_FUNCS = {"CONVERT", "TRY_CONVERT"}
NON_FUNCTION_WORDS = {"IN", "EXISTS", "NOT", "AND", "OR", "ANY", "ALL", "SOME", "VALUES", "ON", "WHEN", "THEN",
                      "ELSE", "CASE", "BETWEEN", "LIKE", "IS", "SELECT", "WITH", "OVER", "AS", "WHERE", "FROM",
                      "JOIN", "BY", "END", "TOP", "DISTINCT", "SET", "ESCAPE"}


def column_refs(items: list) -> list:
    """[(qualifier|None, column, line)] for column-looking identifiers. Skips keywords, @variables,
    function names and subquery groups."""
    refs, n, i = [], len(items), 0
    while i < n:
        it = items[i]
        if isinstance(it, Group):
            if not is_query(it):
                refs += column_refs(it.items)
            i += 1
            continue
        if it.kind in ("ident", "qident"):
            if it.kind == "ident" and it.up == "COLLATE":
                i += 2                                          # skip the collation name
                continue
            if it.kind == "ident" and i + 1 < n and isinstance(items[i + 1], Group) and not is_query(items[i + 1]):
                grp, f = items[i + 1], it.up
                if f in DATE_FUNCS or f in CONVERT_FUNCS:       # first argument is a date part / a type
                    refs += column_refs([x for a in split_commas(grp.items)[1:] for x in a])
                    i += 2
                    continue
                if f in CAST_FUNCS:                              # everything after AS is a type
                    pre = []
                    for x in grp.items:
                        if is_kw(x, "AS"):
                            break
                        pre.append(x)
                    refs += column_refs(pre)
                    i += 2
                    continue
            if it.kind == "ident" and (it.up in KEYWORDS or it.text[0] in "@#"):
                i += 1
                continue
            parts, j = [it], i
            while (j + 2 < n and is_punct(items[j + 1], ".") and isinstance(items[j + 2], Tok)
                   and items[j + 2].kind in ("ident", "qident")):
                parts.append(items[j + 2])
                j += 2
            nxt = items[j + 1] if j + 1 < n else None
            if isinstance(nxt, Group) and not is_query(nxt):      # function call, not a column
                i = j + 1
                continue
            qual = nm(parts[-2]) if len(parts) > 1 else None
            refs.append((qual, nm(parts[-1]), it.line))
            i = j + 1
            continue
        i += 1
    return refs


def outer_function_calls(items: list) -> Iterator[tuple]:
    """Yield (name_tok, group) for outermost function calls; skips subquery groups."""
    i, n = 0, len(items)
    while i < n:
        it = items[i]
        if isinstance(it, Group):
            if not is_query(it):
                yield from outer_function_calls(it.items)
        elif (it.kind == "ident" and i + 1 < n and isinstance(items[i + 1], Group)
              and not is_query(items[i + 1]) and it.up not in NON_FUNCTION_WORDS):
            yield it, items[i + 1]
            i += 2
            continue
        i += 1


_CMP = {"=", "<>", "!=", "<", ">", "<=", ">=", "!<", "!>"}


def split_comparison(items: list):
    """If items are `left <op> right` with exactly one top-level comparison op, return (left, op, right)."""
    idx = [k for k, it in enumerate(items) if is_tok(it, "op") and it.text in _CMP]
    if len(idx) != 1:
        return None
    k = idx[0]
    return items[:k], items[k].text, items[k + 1:]


def simple_column(side: list):
    """(qualifier|None, column) if the side is exactly one (possibly qualified) column reference."""
    if not side or not all(isinstance(x, Tok) for x in side):
        return None
    toks = side
    if len(toks) == 1 and toks[0].kind in ("ident", "qident"):
        t = toks[0]
        if t.kind == "ident" and (t.up in KEYWORDS or t.text[0] in "@#"):
            return None
        return None, nm(t)
    if (len(toks) == 3 and toks[0].kind in ("ident", "qident") and is_punct(toks[1], ".")
            and toks[2].kind in ("ident", "qident")):
        return nm(toks[0]), nm(toks[2])
    if (len(toks) == 5 and is_punct(toks[1], ".") and is_punct(toks[3], ".")
            and toks[0].kind in ("ident", "qident") and toks[4].kind in ("ident", "qident")):
        return nm(toks[2]), nm(toks[4])
    return None


def literal_kind(side: list):
    """'num' | 'nstr' | 'str' | None for a side that is exactly one literal."""
    s = side
    if len(s) == 2 and is_tok(s[0], "op") and s[0].text in "+-" and is_tok(s[1], "number"):
        return "num"
    if len(s) == 1 and isinstance(s[0], Tok):
        if s[0].kind == "number":
            return "num"
        if s[0].kind == "string":
            return "nstr" if s[0].text[0] in "Nn" else "str"
    return None


# ---------------- query blocks ----------------
@dataclass
class FromItem:
    kind: str                 # table | derived | values | function | other
    name: Optional[str]       # table name, lower, schema stripped
    schema: Optional[str]
    alias: Optional[str]      # lower; defaults to name
    join: Optional[str]       # None (first of comma group) | INNER LEFT RIGHT FULL CROSS "CROSS APPLY" "OUTER APPLY"
    on: Optional[list]
    cg: int                   # comma-group index
    line: int
    block: Optional["Block"] = None


@dataclass
class Block:
    line: int
    root: bool = False
    clause_ctx: str = ""      # clause of the parent in which this block appears
    prev: tuple = ()          # up to 2 preceding tokens (upper-case text) in the parent sequence
    prev_line: Optional[int] = None
    parent: Optional["Block"] = None
    distinct: bool = False
    top: Optional[str] = None
    percent: bool = False
    select_items: list = field(default_factory=list)
    from_items: list = field(default_factory=list)
    where: list = field(default_factory=list)
    group_by: list = field(default_factory=list)
    having: list = field(default_factory=list)
    order_by: list = field(default_factory=list)
    children: list = field(default_factory=list)

    def walk(self) -> Iterator["Block"]:
        yield self
        for c in self.children:
            yield from c.walk()

    def aliases(self) -> set:
        return {fi.alias for fi in self.from_items if fi.alias}


@dataclass
class Parsed:
    roots: list
    tokens: list

    def blocks(self) -> Iterator[Block]:
        for r in self.roots:
            yield from r.walk()


_JOIN_WORDS = {"INNER", "LEFT", "RIGHT", "FULL", "CROSS", "JOIN", "OUTER"}
_ALIAS_STOP = {"ON", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "OUTER", "WHERE", "GROUP", "ORDER",
               "HAVING", "UNION", "INTERSECT", "EXCEPT", "WITH", "OPTION", "FOR", "APPLY", "SET", "TABLESAMPLE"}


def _is_join_start(items: list, j: int) -> bool:
    it = items[j]
    if not (is_tok(it, "ident") and it.up in _JOIN_WORDS):
        return False
    if it.up in ("LEFT", "RIGHT") and j + 1 < len(items) and isinstance(items[j + 1], Group):
        return False           # LEFT(...) / RIGHT(...) function call
    return True


def _scan(items: list, block: Block, clause: str) -> None:
    """Find subquery groups inside a clause (recursing through plain groups) and parse them."""
    prev, prev_lines = [], []
    for it in items:
        if isinstance(it, Group):
            if is_query(it):
                tail = tuple(prev[-2:])
                pl = prev_lines[-2] if len(prev_lines) >= 2 and tail == ("NOT", "IN") else (prev_lines[-1] if prev_lines else it.line)
                block.children.extend(parse_query(it.items, block, clause, tail, pl))
            else:
                _scan(it.items, block, clause)
            prev.append("(")
            prev_lines.append(it.line)
        else:
            prev.append(it.up if it.kind == "ident" else it.text)
            prev_lines.append(it.line)


def parse_from(items: list, block: Block) -> list:
    out, i, n, cg, start = [], 0, len(items), 0, True
    while i < n:
        if is_punct(items[i], ","):
            cg += 1
            start = True
            i += 1
            continue
        join = None
        if start:
            start = False
        else:
            words = []
            while i < n and isinstance(items[i], Tok) and items[i].kind == "ident" and items[i].up in (_JOIN_WORDS | {"APPLY"}):
                words.append(items[i].up)
                i += 1
                if words[-1] in ("JOIN", "APPLY"):
                    break
            if not words or words[-1] not in ("JOIN", "APPLY"):
                raise LiteParseError(f"unexpected tokens in FROM clause near line {items[min(i, n - 1)].line}")
            if words[-1] == "APPLY":
                join = "CROSS APPLY" if "CROSS" in words else "OUTER APPLY"
            elif "CROSS" in words:
                join = "CROSS"
            else:
                join = next((w for w in ("LEFT", "RIGHT", "FULL") if w in words), "INNER")
        if i >= n:
            raise LiteParseError("FROM clause ends after a join keyword")
        src = items[i]
        kind = name = schema = None
        blk = None
        line = src.line
        if isinstance(src, Group):
            if is_query(src):
                kind = "derived"
                bl = parse_query(src.items, block, "from", (), None)
                block.children.extend(bl)
                blk = bl[0]
            elif src.items and is_kw(src.items[0], "VALUES"):
                kind = "values"
            else:
                kind = "other"
            i += 1
        elif isinstance(src, Tok) and src.kind in ("ident", "qident"):
            parts = [nm(src)]
            i += 1
            while i + 1 < n and is_punct(items[i], ".") and isinstance(items[i + 1], Tok) and items[i + 1].kind in ("ident", "qident"):
                parts.append(nm(items[i + 1]))
                i += 2
            if i < n and isinstance(items[i], Group) and not is_query(items[i]):
                kind = "function"
                i += 1
            else:
                kind = "table"
            name, schema = parts[-1], (parts[-2] if len(parts) > 1 else None)
        else:
            raise LiteParseError(f"unexpected token in FROM clause near line {src.line}")
        alias = None
        explicit_as = i < n and is_kw(items[i], "AS")
        if explicit_as:
            i += 1
        if i < n and isinstance(items[i], Tok) and items[i].kind in ("ident", "qident") and (
                explicit_as or items[i].kind == "qident" or items[i].up not in _ALIAS_STOP):
            alias = nm(items[i])
            i += 1
            if i < n and isinstance(items[i], Group) and not is_query(items[i]):
                i += 1                                    # derived-table column list
        if i + 1 < n and is_kw(items[i], "WITH") and isinstance(items[i + 1], Group):
            i += 2                                        # table hint, e.g. WITH (NOLOCK)
        on = None
        if i < n and is_kw(items[i], "ON"):
            i += 1
            j = i
            while j < n and not is_punct(items[j], ",") and not _is_join_start(items, j):
                j += 1
            on = items[i:j]
            i = j
            _scan(on, block, "from")
        fi = FromItem(kind, name, schema, alias or (name if kind == "table" else None), join, on, cg, line, blk)
        out.append(fi)
    return out


def _split_set_ops(items: list) -> list:
    members, cur, i, n = [], [], 0, len(items)
    while i < n:
        it = items[i]
        if is_kw(it, "UNION", "INTERSECT", "EXCEPT"):
            members.append(cur)
            cur = []
            i += 1
            if i < n and is_kw(items[i], "ALL"):
                i += 1
            continue
        cur.append(it)
        i += 1
    members.append(cur)
    return members


def parse_query(items: list, parent, clause: str, prev: tuple = (), prev_line=None, root: bool = False) -> list:
    ctes, i, n = [], 0, len(items)
    if n and is_kw(items[0], "WITH"):
        i = 1
        while True:
            if i >= n:
                raise LiteParseError("incomplete WITH clause")
            name = items[i]
            i += 1
            if i < n and isinstance(items[i], Group) and not is_query(items[i]):
                i += 1
            if not (i < n and is_kw(items[i], "AS")):
                raise LiteParseError(f"expected AS in WITH clause near line {name.line}")
            i += 1
            if not (i < n and is_query(items[i])):
                raise LiteParseError(f"expected a query in WITH clause near line {name.line}")
            ctes.append(items[i])
            i += 1
            if i < n and is_punct(items[i], ","):
                i += 1
                continue
            break
    blocks = []
    for m in _split_set_ops(items[i:]):
        if len(m) == 1 and is_query(m[0]):
            blocks.extend(parse_query(m[0].items, parent, clause, prev, prev_line, root))
        else:
            blocks.append(_parse_member(m, parent, clause, prev, prev_line, root))
    for body in ctes:
        blocks[0].children.extend(parse_query(body.items, blocks[0], "cte", (), None))
    return blocks


def _parse_member(items: list, parent, clause, prev, prev_line, root) -> Block:
    if not items or not is_kw(items[0], "SELECT"):
        raise LiteParseError(f"expected SELECT near line {items[0].line if items else 0}")
    b = Block(items[0].line, root, clause, prev, prev_line, parent)
    cl = {"select": [], "into": [], "from": [], "where": [], "group": [], "having": [], "order": [], "tail": []}
    cur, i, n = "select", 1, len(items)
    while i < n:
        it = items[i]
        if is_tok(it, "ident"):
            u = it.up
            nxt_by = i + 1 < n and is_kw(items[i + 1], "BY")
            if u == "INTO" and cur == "select":
                cur = "into"; i += 1; continue
            if u == "FROM" and cur in ("select", "into"):
                cur = "from"; i += 1; continue
            if u == "WHERE" and cur in ("select", "into", "from"):
                cur = "where"; i += 1; continue
            if u == "GROUP" and nxt_by:
                cur = "group"; i += 2; continue
            if u == "HAVING" and cur in ("select", "into", "from", "where", "group"):
                cur = "having"; i += 1; continue
            if u == "ORDER" and nxt_by:
                cur = "order"; i += 2; continue
            if u in ("OPTION", "FOR") and cur != "select":
                cur = "tail"; i += 1; continue
        cl[cur].append(it)
        i += 1
    sel, j = cl["select"], 0
    if j < len(sel) and is_kw(sel[j], "DISTINCT", "ALL"):
        b.distinct = sel[j].up == "DISTINCT"
        j += 1
    if j < len(sel) and is_kw(sel[j], "TOP"):
        j += 1
        if j < len(sel):
            x = sel[j]
            if isinstance(x, Group) and not is_query(x):
                b.top = " ".join(t.text for t in x.items if isinstance(t, Tok))
                j += 1
            elif isinstance(x, Tok):
                b.top = x.text
                j += 1
        if j < len(sel) and is_kw(sel[j], "PERCENT"):
            b.percent = True
            j += 1
        if j + 1 < len(sel) and is_kw(sel[j], "WITH") and is_kw(sel[j + 1], "TIES"):
            j += 2
    b.select_items = split_commas(sel[j:])
    b.from_items = parse_from(cl["from"], b)
    b.where, b.group_by, b.having, b.order_by = cl["where"], cl["group"], cl["having"], cl["order"]
    for clause_name, its in (("select", sel[j:]), ("where", cl["where"]), ("group", cl["group"]),
                             ("having", cl["having"]), ("order", cl["order"])):
        _scan(its, b, clause_name)
    return b


# ---------------- statements ----------------
def _split_statements(items: list) -> list:
    stmts = [[]]
    for it in items:
        if is_punct(it, ";") or (is_tok(it, "ident") and it.up == "GO"):
            stmts.append([])
        else:
            stmts[-1].append(it)
    return [s for s in stmts if s]


def _split_declare(stmt: list) -> list:
    if is_kw(stmt[0], "DECLARE", "SET"):
        for i in range(1, len(stmt)):
            if is_kw(stmt[i], "SELECT", "WITH"):
                return [stmt[:i], stmt[i:]]
    return [stmt]


def parse_sql(sql: str, read=None) -> Parsed:
    """The parse_fn used by analyze(). `read` is accepted for interface compatibility and ignored."""
    if not isinstance(sql, str):
        raise LiteParseError("input is not text")
    toks = tokenize(sql)
    if not toks:
        raise LiteParseError("no SQL found (only comments or whitespace)")
    roots = []
    for stmt in _split_statements(build_groups(toks)):
        for part in _split_declare(stmt):
            head = part[0]
            if not is_tok(head, "ident"):
                raise LiteParseError(f"unsupported statement near line {head.line}")
            if head.up in ("SELECT", "WITH"):
                roots.extend(parse_query(part, None, "root", root=True))
            elif head.up in ("DECLARE", "SET"):
                continue
            else:
                raise LiteParseError(f"unsupported statement type: {head.up}")
    if not roots:
        raise LiteParseError("no SELECT statement found")
    return Parsed(roots, toks)


# ---------------- schema (CREATE TABLE) ----------------
@dataclass
class Column:
    name: str
    type_base: str
    nullable: bool = True

    @property
    def family(self) -> str:
        t = self.type_base
        if t in ("varchar", "char", "text"):
            return "ansi_str"
        if t in ("nvarchar", "nchar", "ntext"):
            return "uni_str"
        if t in ("int", "integer", "bigint", "smallint", "tinyint", "decimal", "numeric", "dec", "float", "real",
                 "money", "smallmoney", "bit"):
            return "num"
        if t in ("date", "datetime", "datetime2", "smalldatetime", "time", "datetimeoffset"):
            return "date"
        return "other"


@dataclass
class TableDef:
    name: str
    columns: dict = field(default_factory=dict)
    pk: tuple = ()
    uniques: list = field(default_factory=list)

    def keys(self) -> list:
        return ([set(self.pk)] if self.pk else []) + [set(u) for u in self.uniques if u]


@dataclass
class Schema:
    tables: dict = field(default_factory=dict)


def _paren_cols(g) -> tuple:
    return tuple(nm(t) for t in g.items if isinstance(t, Tok) and t.kind in ("ident", "qident")
                 and not (t.kind == "ident" and t.up in ("ASC", "DESC")))


def parse_schema(ddl: str) -> Schema:
    if not isinstance(ddl, str) or not ddl.strip():
        raise LiteParseError("empty table definitions")
    items = build_groups(tokenize(ddl))
    sch, i, n = Schema(), 0, len(items)
    while i < n:
        if is_kw(items[i], "CREATE") and i + 1 < n and is_kw(items[i + 1], "TABLE"):
            j = i + 2
            parts = []
            while j < n and isinstance(items[j], Tok) and items[j].kind in ("ident", "qident"):
                parts.append(nm(items[j]))
                j += 1
                if j < n and is_punct(items[j], "."):
                    j += 1
                else:
                    break
            if not parts or j >= n or not isinstance(items[j], Group):
                raise LiteParseError("could not read a CREATE TABLE statement")
            t = TableDef(parts[-1])
            for col in split_commas(items[j].items):
                _read_column_or_constraint(col, t)
            for c in t.pk:
                if c in t.columns:
                    t.columns[c].nullable = False
            sch.tables[t.name] = t
            i = j + 1
        else:
            i += 1
    if not sch.tables:
        raise LiteParseError("no CREATE TABLE statements found")
    return sch


def _read_column_or_constraint(col: list, t: TableDef) -> None:
    k = 0
    if is_kw(col[0], "CONSTRAINT"):
        k = 2
    head = col[k] if k < len(col) else None
    if is_kw(head, "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "INDEX"):
        grp = next((x for x in col[k:] if isinstance(x, Group)), None)
        if is_kw(head, "PRIMARY") and grp is not None:
            t.pk = _paren_cols(grp)
        elif is_kw(head, "UNIQUE") and grp is not None:
            t.uniques.append(_paren_cols(grp))
        return
    if not (is_tok(col[0]) and col[0].kind in ("ident", "qident")):
        return
    name = nm(col[0])
    type_base = "?"
    if len(col) > 1 and is_tok(col[1], "ident"):
        type_base = col[1].text.lower()
    nullable = type_base != "?" and not is_kw(col[1], "AS")
    rest = col[2:]
    for idx, x in enumerate(rest):
        if is_kw(x, "NOT") and idx + 1 < len(rest) and is_kw(rest[idx + 1], "NULL"):
            nullable = False
        elif is_kw(x, "PRIMARY") and idx + 1 < len(rest) and is_kw(rest[idx + 1], "KEY"):
            t.pk = (name,)
            nullable = False
        elif is_kw(x, "UNIQUE"):
            t.uniques.append((name,))
    t.columns[name] = Column(name, type_base, nullable)
