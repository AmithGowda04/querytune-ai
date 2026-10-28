# QueryTune AI

Debug, explain and optimise SQL, with honest limits. Portfolio project (Python, Streamlit,
SQLGlot, DuckDB). **Status: work in progress. Nothing is deployed.**

Principle: do not just rewrite SQL. Explain each change, preserve the intended logic, validate
where possible, and say exactly what was NOT verified. No performance gain is claimed unless it
was measured.

## Validation statuses (planned, shown on every suggestion)
1. **Proposed**: model or rule output, nothing checked.
2. **Syntax checked**: the rewrite parses in the selected dialect.
3. **Matched on generated data**: original and rewrite returned the same results on generated
   edge-case data in an in-memory DuckDB. Evidence, not proof.
4. **Performance verified**: measured with the local SQL Server benchmark script. Never claimed
   by the hosted app.

## What is built and tested so far
| Part | State |
|---|---|
| Evaluation corpus: 30 planted + 32 clean T-SQL queries, frozen (tag `corpus-frozen`) | Written. NOT yet parsed by a real T-SQL parser |
| Dialect config + dialect-mismatch warning | Built; tests passed |
| Rule framework + `analyze()` (parser injected) | Built; tests passed with fake rules/parser |
| Evaluation scorer (catch rate, false-alarm rate, Wilson CIs) | Built; tests passed with fake analyzers |
| Actual analyzer rules (SQLGlot) | NOT built |
| Test-data generator + DuckDB equivalence runner | NOT built |
| AI layer, Streamlit UI, deployment | NOT built |
| Local SQL Server benchmark | NOT built |

"Tests passed" means the test functions were called directly with plain Python in a sandbox
without package access. The full suite has not been run under `pytest` yet.

## Published results
None yet. Catch and false-alarm rates will be published with confidence intervals once the
analyzer exists and is run on the corpus. Misses will be listed.

## Known limits (final README must keep these)
- The corpus is single-author, and the same author designs the rules, so rates lean optimistic.
- The clean set is adversarial (mostly near-misses), so its false-alarm rate is not a prediction
  for real code.
- n is about 30 per class; confidence intervals are wide.
- Equivalence on generated data is not proof. T-SQL features that cannot be transpiled stay "Proposed".
- Benchmark results (when they exist) come from one machine and one data distribution.
- The hosted app has no database connection by design.

## Run the tests
```
pip install -r requirements.txt
pytest
```

See `PRIVACY.md`, `PROGRESS.md`, `docs/corpus_design.md`, `corpus/FROZEN.md`.
