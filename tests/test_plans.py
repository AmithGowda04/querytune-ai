"""Plan / STATISTICS parsers on HAND-WRITTEN samples (formats from memory; NOT real SQL Server output)."""
from plans.sqlserver_plan import parse_plan
from plans.statistics_io import parse_statistics

NS = 'xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan"'
PLAN = f"""<ShowPlanXML {NS} Version="1.5" Build="16.0.1000.6">
<BatchSequence><Batch><Statements>
<StmtSimple StatementText="SELECT ..." StatementType="SELECT">
<QueryPlan>
<Warnings NoJoinPredicate="true">
  <PlanAffectingConvert ConvertIssue="Seek Plan" Expression="CONVERT_IMPLICIT(nvarchar(25),[p].[ProductNumber],0)=[@1]"/>
</Warnings>
<MissingIndexes><MissingIndexGroup Impact="85.3"><MissingIndex Database="[db]" Schema="[dbo]" Table="[SalesOrderHeader]"/></MissingIndexGroup></MissingIndexes>
<RelOp NodeId="0" PhysicalOp="Nested Loops" LogicalOp="Inner Join" EstimateRows="5000" EstimatedTotalSubtreeCost="0.5">
 <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="5000" ActualExecutions="1"/></RunTimeInformation>
 <NestedLoops>
  <RelOp NodeId="1" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimateRows="120000" EstimatedTotalSubtreeCost="1.2">
   <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="120000" ActualExecutions="1"/></RunTimeInformation>
   <IndexScan><Object Database="[db]" Schema="[dbo]" Table="[SalesOrderDetail]" Index="[PK_SOD]"/></IndexScan>
  </RelOp>
  <RelOp NodeId="2" PhysicalOp="Index Seek" LogicalOp="Index Seek" EstimateRows="1" EstimatedTotalSubtreeCost="0.003">
   <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="5000" ActualExecutions="5000"/></RunTimeInformation>
   <IndexScan><Object Database="[db]" Schema="[dbo]" Table="[Product]" Index="[PK_P]"/></IndexScan>
  </RelOp>
  <RelOp NodeId="3" PhysicalOp="Key Lookup" LogicalOp="Clustered Index Seek" EstimateRows="1" EstimatedTotalSubtreeCost="0.003">
   <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="500000" ActualExecutions="1"/></RunTimeInformation>
   <IndexScan><Object Database="[db]" Schema="[dbo]" Table="[Customer]" Index="[PK_C]"/></IndexScan>
  </RelOp>
 </NestedLoops>
</RelOp>
<ParameterList><ColumnReference Column="@1" ParameterCompiledValue="'secret-value'"/></ParameterList>
</QueryPlan></StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


def test_plan_facts_extracted():
    pf = parse_plan(PLAN)
    assert pf.ok and pf.is_actual and pf.statements == 1 and len(pf.operators) == 4
    assert [o.target for o in pf.scans] == ["dbo.SalesOrderDetail"]
    assert [o.target for o in pf.seeks] == ["dbo.Product"]
    assert [o.target for o in pf.lookups] == ["dbo.Customer"]
    assert pf.scans[0].index == "[PK_SOD]"
    assert pf.missing_indexes == [{"table": "dbo.SalesOrderHeader", "impact": "85.3"}]
    assert any("no join predicate" in w for w in pf.warnings)
    assert any("implicit conversion" in w and "Seek Plan" in w for w in pf.warnings)


def test_parent_does_not_absorb_child_counters_and_mismatch_logic():
    pf = parse_plan(PLAN)
    by_id = {o.node_id: o for o in pf.operators}
    assert by_id["0"].actual_rows == 5000 and by_id["1"].actual_rows == 120000
    assert [o.node_id for o in pf.mismatches] == ["3"]      # est 1 vs actual 500000
    # node 2: est 1 x 5000 executions == 5000 actual -> not a mismatch


def test_estimated_plan_has_no_actuals_or_mismatches():
    est = PLAN.replace("RunTimeInformation", "Ignored").replace("RunTimeCountersPerThread", "Ign")
    pf = parse_plan(est)
    assert pf.ok and not pf.is_actual and pf.mismatches == []


def test_parameter_values_never_extracted():
    text = " ".join(parse_plan(PLAN).to_facts())
    assert "secret-value" not in text
    assert "Clustered Index Scan on dbo.SalesOrderDetail" in text


def test_hostile_or_bad_input_rejected():
    assert parse_plan("").error == "empty input"
    bomb = '<!DOCTYPE x [<!ENTITY a "aaaa">]><ShowPlanXML/>'
    assert "DOCTYPE" in parse_plan(bomb).error
    assert parse_plan("<ShowPlanXML><oops>").error == "not well-formed XML"
    assert "not a SQL Server execution plan" in parse_plan("<html/>").error
    assert parse_plan("<a>" + "x" * 2_100_000 + "</a>").error == "plan too large"


# ---------------- STATISTICS IO / TIME ----------------
STATS = """(5 rows affected)
Table 'SalesOrderDetail'. Scan count 1, logical reads 1237, physical reads 3, page server reads 0, read-ahead reads 1220, page server read-ahead reads 0, lob logical reads 0, lob physical reads 0, lob page server reads 0, lob read-ahead reads 0, lob page server read-ahead reads 0.
Table 'Product'. Scan count 1, logical reads 15, physical reads 0, read-ahead reads 0.
Table 'Worktable'. Scan count 0, logical reads 0, physical reads 0.
Table 'Product'. Scan count 2, logical reads 5, physical reads 0, read-ahead reads 0.

 SQL Server parse and compile time:
   CPU time = 0 ms, elapsed time = 4 ms.

 SQL Server Execution Times:
   CPU time = 31 ms,  elapsed time = 52 ms.
"""


def test_statistics_io_parsed_and_aggregated():
    s = parse_statistics(STATS)
    names = {t.name: t for t in s.tables}
    assert names["SalesOrderDetail"].logical_reads == 1237
    assert names["SalesOrderDetail"].counters["read_ahead_reads"] == 1220
    assert names["Product"].logical_reads == 20 and names["Product"].scan_count == 3   # aggregated
    assert s.total_logical_reads == 1257
    assert [t.name for t in s.top_by_logical_reads(2)] == ["SalesOrderDetail", "Product"]


def test_statistics_time_parsed():
    s = parse_statistics(STATS)
    assert s.times == [{"kind": "parse_compile", "cpu_ms": 0, "elapsed_ms": 4},
                       {"kind": "execution", "cpu_ms": 31, "elapsed_ms": 52}]
    facts = s.to_facts()
    assert facts[0].startswith("Table SalesOrderDetail: 1237 logical reads")
    assert any("elapsed 52 ms (one run)" in f for f in facts)


def test_statistics_bad_input():
    assert "empty input" in parse_statistics("").warnings
    assert "no STATISTICS" in parse_statistics("hello world").warnings[0]
    assert "too large" in parse_statistics("x" * 300_000).warnings[0]
