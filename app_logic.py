"""UI-independent logic for the Streamlit app (testable without Streamlit)."""
from __future__ import annotations

from dataclasses import dataclass, field

from analyzer.api import analyze_sql
from analyzer.dialects import OTHER_DIALECTS, get_dialect, status_label
from analyzer.report import build_change_report
from analyzer.rules import DEFAULT_REGISTRY

MAX_CHARS = 20_000
DIALECT_CHOICES = [("tsql", "T-SQL (SQL Server)"), ("postgres", "PostgreSQL"), ("other", "Other (experimental)")]
OTHER_CHOICES = sorted(OTHER_DIALECTS.items())

DDL_EXAMPLE = """CREATE TABLE dbo.Employee (
    EmployeeID INT NOT NULL PRIMARY KEY,
    FullName   NVARCHAR(100) NOT NULL,
    ManagerID  INT NULL,
    Phone      VARCHAR(20) NULL
);
CREATE TABLE dbo.SalesOrderHeader (
    OrderID       INT NOT NULL PRIMARY KEY,
    SalesPersonID INT NULL,
    OrderDate     DATETIME NOT NULL
);"""

EXAMPLES = {
    "(blank)": ("", ""),
    "Non-sargable date filter + SELECT *": (
        "SELECT *\nFROM dbo.SalesOrderHeader\nWHERE YEAR(OrderDate) = 2024;", ""),
    "NOT IN over a nullable column (needs table definitions)": (
        "SELECT EmployeeID, FullName\nFROM dbo.Employee\n"
        "WHERE EmployeeID NOT IN (SELECT ManagerID FROM dbo.Employee);", DDL_EXAMPLE),
    "VARCHAR column compared with a number (needs table definitions)": (
        "SELECT EmployeeID\nFROM dbo.Employee\nWHERE Phone = 5551234;", DDL_EXAMPLE),
    "Correlated subquery + DISTINCT with a join": (
        "SELECT DISTINCT e.EmployeeID,\n"
        "       (SELECT MAX(h.OrderDate) FROM dbo.SalesOrderHeader h WHERE h.SalesPersonID = e.EmployeeID) AS LastSale\n"
        "FROM dbo.Employee e\nJOIN dbo.SalesOrderHeader h2 ON h2.SalesPersonID = e.EmployeeID;", DDL_EXAMPLE),
}

NOTES = ["No AI model was used. Findings come from 12 fixed rules and are heuristic.",
         "No rule firing does not mean the query is correct or fast."]


@dataclass
class Analysis:
    status: str                                   # "analysed" | "not_analysed" | "rejected"
    dialect_label: str = ""
    dialect_status: str = ""
    reason: str | None = None
    warnings: list = field(default_factory=list)
    rows: list = field(default_factory=list)      # finding rows for display
    skipped: list = field(default_factory=list)   # [(rule_id, reason)]
    rule_errors: list = field(default_factory=list)
    rules_run: list = field(default_factory=list)
    report_md: str = ""


def rule_catalog() -> list:
    return [{"id": r.id, "name": r.name, "severity": r.severity, "kind": r.kind,
             "rationale": r.rationale, "bad": r.bad_example, "good": r.good_example}
            for r in DEFAULT_REGISTRY.all()]


def run_analysis(sql: str, dialect_key: str, sub: str | None, ddl_text: str, disabled=()) -> Analysis:
    d = get_dialect(dialect_key, sub if dialect_key == "other" else None)
    base = dict(dialect_label=d.label, dialect_status=status_label(d))
    if len(sql or "") + len(ddl_text or "") > MAX_CHARS:
        return Analysis("rejected", reason=f"input too large (limit {MAX_CHARS} characters)", **base)
    res = analyze_sql(sql, d, ddl_text or None, disabled=disabled)
    meta = {r.id: r for r in DEFAULT_REGISTRY.all()}
    rows = [{"rule_id": f.rule_id, "name": meta[f.rule_id].name, "severity": f.severity, "line": f.line,
             "message": f.message, "rationale": meta[f.rule_id].rationale,
             "bad": meta[f.rule_id].bad_example, "good": meta[f.rule_id].good_example} for f in res.findings]
    notes = list(NOTES) + [base["dialect_status"]]
    if res.status != "analysed":
        notes.append(f"The query was not analysed: {res.reason}")
    report = build_change_report(sql, None, d.label, None, findings=res.findings, notes=notes,
                                 title="SQL analysis report")
    return Analysis(res.status, reason=res.reason, warnings=res.warnings, rows=rows, skipped=res.skipped,
                    rule_errors=res.rule_errors, rules_run=res.rules_run, report_md=report, **base)
