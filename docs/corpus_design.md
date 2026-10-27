# Evaluation corpus design (T-SQL)

Status: design only (Stage 1a). Queries are added in 1b (planted) and 1c (clean).

## Purpose
Measure the deterministic analyzer honestly: how many planted problems it catches
AND how often it flags correct queries. Without this the catch rate is anecdote.
The analyzer and the AI layer are evaluated separately; this corpus covers the
analyzer only.

## Files
- `corpus/schema_tsql.sql`  schema every query targets (AdventureWorks-style, hand-written,
  simplified; not Microsoft's original DDL).
- `corpus/taxonomy.json`    rule ids used to plant problems (12 ids: 9 syntactic, 3 schema-dependent).
- `corpus/planted/P###_<rule>.sql`   queries with a known planted problem.
- `corpus/clean/C###_<note>.sql`     correct queries; at least half are NEAR-MISSES
  (look like a problem but are fine, e.g. `SELECT *` inside `EXISTS`, a function applied
  to a constant not a column, `NOT IN` over a literal list).
- `corpus/expected.json`    one entry per query:
  `{"file","label":"planted|clean","rules":[ids],"split":"dev|heldout","needs_schema":bool,"note"}`.
  Clean queries have `rules: []`.

## Targets
- About 30 planted (2-3 per rule) and about 30 clean.
- Split about 2/3 dev, 1/3 heldout, stratified by rule. Rules are designed and tuned
  on `dev` only.

## Metrics (reported separately for syntactic and schema-dependent rules)
- Catch rate: planted query counts as caught if EVERY expected rule id fires on it.
- Per-rule recall.
- False-alarm rate: share of clean queries with at least one finding. Also list which rule fired.
- Extra findings on planted queries (unexpected rule ids) reported separately, not hidden.
- Parse-success rate: share of all queries SQLGlot parses with `read="tsql"`.
- All rates as counts with Wilson 95% confidence intervals, e.g. 27/30.
- Schema rules run only with the schema supplied; syntactic rules run without it.

## Freeze procedure
1. Finish all queries and `expected.json`.
2. Commit, then tag `corpus-frozen`.
3. Held-out files are not read during rule design. The held-out score is computed once, at the end.
4. Any later change to a held-out query is disclosed in the README.

## Known limitations (state in README)
- One author writes both the problems and the rules, so the catch rate is biased upward.
  The dev/heldout split and near-miss clean queries reduce this; they do not remove it.
- Recommended: the project owner writes about 10 held-out queries independently, without
  seeing the rule list. That is the single biggest credibility gain.
- Small n: 90% and 80% are barely distinguishable at n=30; the confidence intervals say so.
- Synthetic queries on a simplified schema are not production T-SQL.
