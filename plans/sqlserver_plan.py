"""Extract facts from a pasted SQL Server execution plan (ShowPlan XML). Stdlib only.

UNVERIFIED AGAINST REAL PLANS: element/attribute names (RelOp, PhysicalOp, EstimateRows,
RunTimeCountersPerThread/ActualRows, Warnings/PlanAffectingConvert, MissingIndexes ...) are
written from knowledge of the ShowPlan schema and tested only on hand-written samples. The owner
should validate with real plans.

Safety: the plan is untrusted XML. DOCTYPE/ENTITY declarations are rejected before parsing and
input size is capped. Literal parameter VALUES are never extracted.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_BYTES = 2_000_000
SCAN_OPS = {"Table Scan", "Clustered Index Scan", "Index Scan", "Columnstore Index Scan"}
SEEK_OPS = {"Index Seek", "Clustered Index Seek"}
LOOKUP_OPS = {"Key Lookup", "RID Lookup"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class Operator:
    node_id: str
    physical_op: str
    logical_op: str
    est_rows: float | None
    est_cost: float | None
    actual_rows: float | None = None
    actual_executions: float | None = None
    schema: str | None = None
    table: str | None = None
    index: str | None = None

    @property
    def target(self) -> str:
        parts = [p.strip("[]") for p in (self.schema, self.table) if p]
        return ".".join(parts) if parts else "?"


@dataclass
class PlanFacts:
    ok: bool
    error: str | None = None
    is_actual: bool = False
    statements: int = 0
    operators: list = field(default_factory=list)
    scans: list = field(default_factory=list)
    seeks: list = field(default_factory=list)
    lookups: list = field(default_factory=list)
    mismatches: list = field(default_factory=list)      # operators with large estimate error
    warnings: list = field(default_factory=list)
    missing_indexes: list = field(default_factory=list)  # [{"table","impact"}]

    def to_facts(self) -> list:
        out = []
        for o in self.scans:
            rows = f", est {o.est_rows:,.0f} rows" if o.est_rows is not None else ""
            out.append(f"{o.physical_op} on {o.target}{rows}")
        for o in self.lookups:
            out.append(f"{o.physical_op} on {o.target}")
        for o in self.mismatches:
            out.append(f"Row estimate off on {o.physical_op} ({o.target}): est {o.est_rows:,.0f}, actual {o.actual_rows:,.0f}")
        out += self.warnings
        out += [f"Missing index suggested on {m['table']} (impact {m['impact']})" for m in self.missing_indexes]
        return out


def parse_plan(xml_text: str, mismatch_ratio: float = 10.0, min_rows: float = 100.0) -> PlanFacts:
    if not isinstance(xml_text, str) or not xml_text.strip():
        return PlanFacts(False, "empty input")
    if len(xml_text.encode("utf-8", "ignore")) > MAX_BYTES:
        return PlanFacts(False, "plan too large")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", xml_text, re.I):
        return PlanFacts(False, "DOCTYPE/ENTITY declarations are not accepted")
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        return PlanFacts(False, "not well-formed XML")
    if _local(root.tag) != "ShowPlanXML":
        return PlanFacts(False, "not a SQL Server execution plan (no ShowPlanXML root)")

    pf = PlanFacts(True)
    for el in root.iter():
        name = _local(el.tag)
        if name == "StmtSimple":
            pf.statements += 1
        elif name == "RunTimeInformation" or name == "RunTimeCountersPerThread":
            pf.is_actual = True
        elif name == "RelOp":
            pf.operators.append(_operator(el))
        elif name == "Warnings":
            if el.get("NoJoinPredicate") in ("true", "1"):
                pf.warnings.append("Warning: a join has no join predicate")
            for ch in el:
                cn = _local(ch.tag)
                if cn == "PlanAffectingConvert":
                    pf.warnings.append(f"Warning: implicit conversion affects the plan "
                                       f"({ch.get('ConvertIssue', '?')}: {ch.get('Expression', '?')})")
                elif cn in ("SpillToTempDb", "SortSpillDetails", "HashSpillDetails"):
                    pf.warnings.append(f"Warning: {cn} (memory spill to tempdb)")
                elif cn == "ColumnsWithNoStatistics":
                    pf.warnings.append("Warning: columns with no statistics")
        elif name == "MissingIndexGroup":
            impact = el.get("Impact", "?")
            for mi in el:
                if _local(mi.tag) == "MissingIndex":
                    tbl = ".".join(x.strip("[]") for x in (mi.get("Schema"), mi.get("Table")) if x)
                    pf.missing_indexes.append({"table": tbl or "?", "impact": impact})
    pf.warnings = list(dict.fromkeys(pf.warnings))
    for o in pf.operators:
        if o.physical_op in SCAN_OPS:
            pf.scans.append(o)
        elif o.physical_op in SEEK_OPS:
            pf.seeks.append(o)
        elif o.physical_op in LOOKUP_OPS:
            pf.lookups.append(o)
        if pf.is_actual and o.est_rows is not None and o.actual_rows is not None:
            est_total = o.est_rows * max(o.actual_executions or 1, 1)   # simplification, see docstring
            hi, lo = max(est_total, o.actual_rows), max(min(est_total, o.actual_rows), 1.0)
            if hi >= min_rows and hi / lo >= mismatch_ratio:
                pf.mismatches.append(o)
    return pf


def _operator(el) -> Operator:
    rows = execs = None
    for rti in el:                                   # this operator's OWN runtime info only
        if _local(rti.tag) != "RunTimeInformation":
            continue
        for rc in rti:
            if _local(rc.tag) == "RunTimeCountersPerThread":
                rows = (rows or 0.0) + (_f(rc.get("ActualRows")) or 0.0)
                execs = (execs or 0.0) + (_f(rc.get("ActualExecutions")) or 0.0)
    schema = table = index = None
    for child in el:
        if _local(child.tag) in ("RunTimeInformation", "OutputList", "Warnings", "RelOp"):
            continue
        for obj in child:
            if _local(obj.tag) == "Object":
                schema, table, index = obj.get("Schema"), obj.get("Table"), obj.get("Index")
    return Operator(el.get("NodeId", "?"), el.get("PhysicalOp", "?"), el.get("LogicalOp", "?"),
                    _f(el.get("EstimateRows")), _f(el.get("EstimatedTotalSubtreeCost")),
                    rows, execs, schema, table, index)
