"""Literal scrubber: replace string and number literals with placeholders before text
is sent to a model provider. Pure Python (stdlib re).

What it does NOT do: it does not touch table, column, schema or alias names, and it does not
touch comments unless strip_comments=True. It FAILS SAFE: if it cannot prove the output holds
no string literal other than placeholders, ok=False and the caller must not send anything.

Kept as-is (structural, not data): numbers after TOP / OFFSET / FETCH NEXT|FIRST / LIMIT,
numbers inside type arguments like VARCHAR(10) / DECIMAL(10,2), the empty string '', and
wildcard-only patterns. For LIKE patterns the leading/trailing % are kept outside the placeholder.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN = re.compile(
    r"""
    (?P<line_comment>--[^\n]*)
  | (?P<block_comment>/\*.*?\*/)
  | (?P<dollar>\$(?P<tag>[A-Za-z_]*)\$.*?\$(?P=tag)\$)
  | (?P<string>[NnEe]?'(?:[^']|'')*')
  | (?P<dquote>"(?:[^"]|"")*")
  | (?P<bracket>\[[^\]]*\])
  | (?P<ident>[A-Za-z_@\#][\w$@\#]*)
  | (?P<number>0[xX][0-9A-Fa-f]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
    """,
    re.VERBOSE | re.DOTALL,
)
_KINDS = ("line_comment", "block_comment", "dollar", "string", "dquote", "bracket", "ident", "number")
_STRUCT_WORDS = {"TOP", "OFFSET", "LIMIT", "NEXT", "FIRST"}
_TYPES = {"DECIMAL", "NUMERIC", "DEC", "VARCHAR", "NVARCHAR", "CHAR", "NCHAR", "VARBINARY",
          "BINARY", "FLOAT", "DATETIME2", "DATETIMEOFFSET", "TIME"}


def _kind(m) -> str:
    return next(k for k in _KINDS if m.group(k) is not None)


@dataclass
class ScrubResult:
    ok: bool
    text: str = ""
    mapping: dict = field(default_factory=dict)   # replacement fragment -> original fragment
    tag: str = ""
    strings: int = 0
    numbers: int = 0
    comments_removed: int = 0
    reason: str | None = None

    def restore(self, text: str):
        """Put original literals back. Returns (text, unresolved_placeholders)."""
        for key in sorted(self.mapping, key=len, reverse=True):
            text = text.replace(key, self.mapping[key])
        left = re.findall(rf"__[SN]{self.tag}\d+__", text)
        return text, left


def _fail(reason: str) -> ScrubResult:
    return ScrubResult(ok=False, reason=reason)


def scrub(sql: str, scrub_numbers: bool = True, strip_comments: bool = False) -> ScrubResult:
    if not isinstance(sql, str):
        return _fail("input is not text")
    tag = ""
    while f"__S{tag}" in sql or f"__N{tag}" in sql:
        tag += "Q"

    out, mapping, seen = [], {}, {}
    ns = nn = nc = kept_numbers = 0
    pos = 0
    since_real = ""            # gaps since the last real (non-comment) token
    prev_word, prev_type, type_args = None, False, False

    for m in _TOKEN.finditer(sql):
        gap = sql[pos:m.start()]
        pos = m.end()
        out.append(gap)
        since_real += gap
        kind = _kind(m)
        tok = m.group(0)

        if kind in ("line_comment", "block_comment"):
            if strip_comments:
                nc += 1
                out.append(" " if kind == "block_comment" else "")
            else:
                out.append(tok)
            continue

        if ")" in since_real:
            type_args = False
        if prev_type and since_real.strip().startswith("("):
            type_args = True
        gap_s = since_real.strip()
        struct_prev = prev_word in _STRUCT_WORDS and gap_s in ("", "(")
        like_prev = prev_word == "LIKE" and gap_s == ""
        since_real = ""
        new_word, new_type = None, False

        if kind == "ident":
            out.append(tok)
            new_word = tok.upper()
            new_type = new_word in _TYPES
        elif kind in ("dquote", "bracket"):
            out.append(tok)
        elif kind == "number":
            if (not scrub_numbers) or struct_prev or type_args:
                out.append(tok)
                kept_numbers += 1
            else:
                if tok not in seen:
                    nn += 1
                    seen[tok] = f"__N{tag}{nn}__"
                    mapping[seen[tok]] = tok
                out.append(seen[tok])
        elif kind == "dollar":
            if tok not in seen:
                ns += 1
                ph = f"__S{tag}{ns}__"
                seen[tok] = f"'{ph}'"
                mapping[seen[tok]] = tok
            out.append(seen[tok])
        else:  # string
            q = tok.index("'")
            prefix, inner = tok[:q], tok[q + 1:-1]
            lead = trail = ""
            core = inner
            if like_prev:
                core = inner.strip("%")
                lead = inner[: len(inner) - len(inner.lstrip("%"))]
                trail = inner[len(inner.rstrip("%")):] if core else ""
            if core == "" or set(core) <= set("%_"):
                out.append(tok)             # no information in it: keep
            else:
                if tok not in seen:
                    ns += 1
                    ph = f"__S{tag}{ns}__"
                    seen[tok] = f"{prefix}'{lead}{ph}{trail}'"
                    mapping[seen[tok]] = tok
                out.append(seen[tok])
        prev_word, prev_type = new_word, new_type

    out.append(sql[pos:])
    text = "".join(out)

    problem = _verify(text, tag, kept_numbers)
    if problem:
        return _fail(problem)
    res = ScrubResult(True, text, mapping, tag, ns, nn, nc)
    if not strip_comments:
        back, left = res.restore(text)
        if back != sql or left:
            return _fail("internal round-trip check failed")
    return res


def _verify(text: str, tag: str, kept_numbers: int):
    """Return a problem description, or None if the text provably holds no raw literal."""
    ph = re.compile(rf"__S{tag}\d+__")
    residual, pos, numbers = [], 0, 0
    for m in _TOKEN.finditer(text):
        residual.append(text[pos:m.start()])
        pos = m.end()
        kind = _kind(m)
        if kind == "dollar":
            return "dollar-quoted string survived scrubbing"
        if kind == "number":
            numbers += 1
        if kind == "string":
            tok = m.group(0)
            inner = tok[tok.index("'") + 1:-1]
            if not (ph.search(inner) or set(inner) <= set("%_")):
                return "a string literal survived scrubbing"
    residual.append(text[pos:])
    if "'" in "".join(residual):
        return "could not tokenize the SQL safely (unbalanced quote or unsupported escape syntax)"
    if numbers != kept_numbers:
        return "unexpected numeric literal in scrubbed text"
    return None
