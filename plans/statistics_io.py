"""Parse SET STATISTICS IO / TIME text pasted from SQL Server Management Studio. Stdlib only.

UNVERIFIED AGAINST REAL OUTPUT: the line formats below are written from knowledge of SQL Server
messages and exercised only against hand-written samples. Field names vary by version (e.g.
'page server reads' exists only in newer versions), so parsing is key/value based and tolerant.
The owner should validate with real pasted output before relying on it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_CHARS = 200_000
_TABLE = re.compile(r"Table\s+'([^']+)'\.\s*(.*)")
_PAIR = re.compile(r"([A-Za-z][A-Za-z\- ]*?)\s+(\d+)")
_TIME = re.compile(r"CPU time\s*=\s*(\d+)\s*ms,\s*elapsed time\s*=\s*(\d+)\s*ms", re.I)


@dataclass
class TableIO:
    name: str
    counters: dict = field(default_factory=dict)   # snake_case counter -> int

    @property
    def logical_reads(self) -> int:
        return self.counters.get("logical_reads", 0)

    @property
    def scan_count(self) -> int:
        return self.counters.get("scan_count", 0)


@dataclass
class StatsFacts:
    tables: list = field(default_factory=list)     # list[TableIO], aggregated per table name
    times: list = field(default_factory=list)      # [{"kind","cpu_ms","elapsed_ms"}]
    warnings: list = field(default_factory=list)

    def top_by_logical_reads(self, n: int = 3) -> list:
        return sorted(self.tables, key=lambda t: t.logical_reads, reverse=True)[:n]

    @property
    def total_logical_reads(self) -> int:
        return sum(t.logical_reads for t in self.tables)

    def to_facts(self) -> list:
        out = [f"Table {t.name}: {t.logical_reads} logical reads, scan count {t.scan_count}"
               for t in self.top_by_logical_reads(5)]
        ex = [t for t in self.times if t["kind"] == "execution"]
        if ex:
            out.append(f"Execution time: CPU {ex[-1]['cpu_ms']} ms, elapsed {ex[-1]['elapsed_ms']} ms (one run)")
        return out


def _snake(k: str) -> str:
    return re.sub(r"[\s\-]+", "_", k.strip().lower())


def parse_statistics(text: str) -> StatsFacts:
    facts = StatsFacts()
    if not isinstance(text, str) or not text.strip():
        facts.warnings.append("empty input")
        return facts
    if len(text) > MAX_CHARS:
        facts.warnings.append("input too large; not parsed")
        return facts
    by_name: dict = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _TABLE.search(line)
        if m:
            name, rest = m.group(1), m.group(2)
            counters = {_snake(k): int(v) for k, v in _PAIR.findall(rest)}
            t = by_name.setdefault(name, TableIO(name))
            for k, v in counters.items():
                t.counters[k] = t.counters.get(k, 0) + v
            continue
        tm = _TIME.search(line)
        if tm:
            head = " ".join(lines[max(0, i - 1): i + 1]).lower()
            kind = "parse_compile" if "parse and compile" in head else "execution"
            facts.times.append({"kind": kind, "cpu_ms": int(tm.group(1)), "elapsed_ms": int(tm.group(2))})
    facts.tables = list(by_name.values())
    if not facts.tables and not facts.times:
        facts.warnings.append("no STATISTICS IO/TIME lines recognised")
    return facts
