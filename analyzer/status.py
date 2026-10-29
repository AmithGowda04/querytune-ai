"""Validation status ladder shown on every suggestion. Pure Python.

Proposed < Syntax checked < Matched on generated data < Performance verified.
Only the LOCAL SQL Server benchmark may produce "Performance verified"; the hosted app must
never pass a benchmark value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PROPOSED = "Proposed"
SYNTAX = "Syntax checked"
MATCHED = "Matched on generated data"
PERF = "Performance verified"
STATUSES = (PROPOSED, SYNTAX, MATCHED, PERF)

EQUIVALENCE_VALUES = (None, "matched", "different", "not_exercised")
BENCHMARK_VALUES = (None, "measured_faster", "measured_no_gain", "measured_slower")


@dataclass(frozen=True)
class StatusInfo:
    status: str
    flags: tuple = field(default_factory=tuple)


def status_for(syntax_ok: bool, equivalence=None, benchmark=None) -> StatusInfo:
    """equivalence: None (not run) | "matched" | "different" | "not_exercised".
    benchmark: None | measured_* (local script only)."""
    if equivalence not in EQUIVALENCE_VALUES:
        raise ValueError(f"bad equivalence value: {equivalence!r}")
    if benchmark not in BENCHMARK_VALUES:
        raise ValueError(f"bad benchmark value: {benchmark!r}")
    if not syntax_ok:
        return StatusInfo(PROPOSED, ("does not parse in the selected dialect",))
    flags = []
    if equivalence == "different":
        return StatusInfo(PROPOSED, ("results DIFFER from the original on generated data",))
    if equivalence == "not_exercised":
        flags.append("generated data did not exercise the query (empty or trivial results)")
    if equivalence == "matched":
        status = MATCHED
    else:
        status = SYNTAX
    if benchmark is not None:
        if equivalence != "matched":
            raise ValueError("a benchmark result needs a matched equivalence check")
        status = PERF
        if benchmark == "measured_no_gain":
            flags.append("measured: no gain")
        elif benchmark == "measured_slower":
            flags.append("measured: SLOWER than the original")
    return StatusInfo(status, tuple(flags))
