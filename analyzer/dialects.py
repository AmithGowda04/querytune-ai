"""Dialect configuration for QueryTune AI.

Pure Python: does NOT import sqlglot. `sqlglot_read` is just the name string that
the parser layer will pass to sqlglot (UNVERIFIED until sqlglot is available).

The selected dialect changes behaviour, not just a label: parser dialect, which
rule kinds run, whether equivalence checking is attempted, and benchmark support.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional

# name shown to the user -> name passed to sqlglot (verify at first real parse)
OTHER_DIALECTS = {
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "redshift": "Redshift",
}


@dataclass(frozen=True)
class Dialect:
    key: str                      # "tsql" | "postgres" | "other"
    label: str
    sqlglot_read: Optional[str]   # None = sqlglot's generic parser
    status: str                   # "supported" | "experimental"
    evaluated: bool               # has its own published corpus results?
    rule_kinds: frozenset         # subset of {"syntactic", "schema"}
    equivalence_check: str        # "allowlist" | "never"
    benchmark_supported: bool     # local SQL Server benchmark can apply


TSQL = Dialect("tsql", "T-SQL (SQL Server)", "tsql", "supported", True,
               frozenset({"syntactic", "schema"}), "allowlist", True)
POSTGRES = Dialect("postgres", "PostgreSQL", "postgres", "supported", False,
                   frozenset({"syntactic"}), "allowlist", False)
OTHER = Dialect("other", "Other (experimental)", None, "experimental", False,
                frozenset({"syntactic"}), "never", False)

DIALECTS = {d.key: d for d in (TSQL, POSTGRES, OTHER)}


def get_dialect(key: str, sub: Optional[str] = None) -> Dialect:
    if key not in DIALECTS:
        raise ValueError(f"unknown dialect: {key!r}")
    d = DIALECTS[key]
    if key != "other":
        if sub is not None:
            raise ValueError(f"{key} takes no sub-dialect")
        return d
    if sub is None:
        return d
    if sub not in OTHER_DIALECTS:
        raise ValueError(f"unknown sub-dialect: {sub!r}")
    return replace(d, label=f"{OTHER_DIALECTS[sub]} (experimental)", sqlglot_read=sub)


def status_label(d: Dialect) -> str:
    if d.status == "experimental":
        return "Experimental: syntactic checks only, no performance claims"
    if d.evaluated:
        return "Supported, evaluated on the published corpus"
    return "Supported, not yet evaluated"


# ---- dialect mismatch warning (heuristic, regex on text with literals/comments removed) ----

_TSQL_MARKERS = [
    (r"\bTOP\s*\(?\s*\d+", "TOP n"),
    (r"\[[A-Za-z_][A-Za-z0-9_ ]*\]", "[bracketed] identifiers"),
    (r"\bGETDATE\s*\(", "GETDATE()"),
    (r"\bISNULL\s*\(", "ISNULL()"),
    (r"@[A-Za-z_]\w*", "@variables"),
    (r"\b(?:CROSS|OUTER)\s+APPLY\b", "APPLY"),
    (r"\(\s*NOLOCK\s*\)", "NOLOCK hint"),
]
_PG_MARKERS = [
    (r"::\s*[A-Za-z_]", "::type casts"),
    (r"\bILIKE\b", "ILIKE"),
    (r"\bLIMIT\s+\d+", "LIMIT n"),
    (r"\bRETURNING\b", "RETURNING"),
    (r"\bNOW\s*\(\s*\)", "NOW()"),
    (r"\$\d+", "$1 parameters"),
]

# one pass so ordering is right: string literal | "quoted ident" | -- comment | /* comment */
_STRIP = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/", re.DOTALL)


def _strip(sql: str) -> str:
    return _STRIP.sub(" ", sql)


def detect_mismatch(sql: str, key: str) -> list:
    """Names of syntax markers from a DIFFERENT dialect than the one selected."""
    if key == "postgres":
        markers, other = _TSQL_MARKERS, "T-SQL"
    elif key == "tsql":
        markers, other = _PG_MARKERS, "PostgreSQL"
    else:
        return []
    text = _strip(sql)
    return [name for pattern, name in markers if re.search(pattern, text, re.IGNORECASE)]


def mismatch_warning(sql: str, key: str) -> Optional[str]:
    found = detect_mismatch(sql, key)
    if not found:
        return None
    selected = DIALECTS[key].label
    other = "T-SQL" if key == "postgres" else "PostgreSQL"
    return (f"Selected {selected}, but the query looks like {other} "
            f"({', '.join(found)}). Check the dialect dropdown.")
