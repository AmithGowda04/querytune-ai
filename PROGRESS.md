# PROGRESS: QueryTune AI

Resume file. Read this first in any new session. Source of truth for status.

## Current status
- Stage 0: CLOSED BY OWNER DECISION, but 'pytest runs' still UNVERIFIED (no network in sandbox). Pins pending.
  - [x] 0a layout, .gitignore, .env.example, LICENSE
  - [~] 0b requirements.txt (UNPINNED) + trivial pytest test. Written, NOT run
        under pytest (sandbox had no network, pytest not installable). The 3 test
        functions were called directly with plain python3 and passed.
  - [x] 0c CI workflow written (.github/workflows/tests.yml). YAML parses; CI NOT run
        (no GitHub repo yet).

## Stage 1 (analyzer, corpus first)
  - [x] 1a corpus design: docs/corpus_design.md, corpus/schema_tsql.sql,
        corpus/taxonomy.json (12 rule ids), empty corpus/expected.json,
        tests/test_corpus.py (checked by calling test functions directly, not pytest).
  - [x] 1b 30 planted queries (P001-P030) + expected.json. 18 dev / 12 heldout.
        taxonomy.json now has a precise 'description' per rule (defines what is planted).
        T-SQL syntax NOT machine-validated (no sqlglot/SQL Server in sandbox); validate at 1e.
        QT102 queries expect ["QT003","QT102"] (QT102 fires in addition to QT003).
  - [ ] 1c clean queries (~30, >=half near-misses) + expected.json entries
  - [ ] 1d freeze: commit + tag corpus-frozen
  - [ ] 1e rule framework (analyzer/parser.py, rules.py; dialect config object) - needs sqlglot
  - [ ] 1f rules, tuned on dev only; 1g evaluation script + report (needs sqlglot)
  Optional high-value: owner writes ~10 held-out queries independently.

## Next action
1. Do 1c (clean queries, >=half near-misses). Do NOT write any rule code before 1d.
2. OWNER (any time): run pytest + pip freeze locally and paste output so pins/Stage 0 can be closed.
   1e-1g are untestable in a sandbox without network (sqlglot).

## Delivery
No GitHub repo yet (owner creates an EMPTY repo at the end). Work is delivered
as a zip (includes .git) in /mnt/user-data/outputs after each step.
To resume in a new session: upload the zip, unzip, read this file.

## Revised decisions (override the original handoff where they differ)
1. Status name "Results verified" -> "Matched on generated data". Statuses:
   Proposed / Syntax checked / Matched on generated data / Performance verified.
2. Equivalence runner only trusts an ALLOWLIST of tested T-SQL constructs
   (DuckDB != SQL Server: int division, collation, NULL ordering, ISNULL/TOP/dates).
   Anything outside the allowlist stays "Proposed".
3. Datagen must respect PK/FK/unique/check from DDL, draw join keys from a small
   shared domain, and flag comparisons where both results are empty/trivial as
   "not exercised".
4. Stage 1 rules split: syntactic (SQL only) vs schema-dependent (needs DDL).
   "Missing date filter on large fact tables" is dropped (needs row counts).
5. Parse failure (DECLARE, temp tables, CROSS APPLY, MERGE...) -> "not analysed
   deterministically", fall back to AI-only. Parse-success rate is a corpus metric.
6. Deploy right after Stage 1 (analyzer needs no AI). Stages 0+1+4 = shippable project.
7. Corpus: based on public schemas (AdventureWorks/Northwind); freeze held-out set
   (tag/commit hash) BEFORE rule work; report counts with Wilson 95% CIs.
   Analyzer and AI results published separately.
8. Sandbox runner: separate subprocess with hard timeout + resource limits, DuckDB
   in-memory, external access disabled.
9. Scrubber: does not hide table/column names (say so in PRIVACY.md); keep a
   placeholder map and validate rewrites against original literals.
10. Render model output as plain/escaped text. No rate-limit promise on Streamlit
    Cloud; keep input-size cap only.
11. Stage 6 shrinks to 3-5 documented case studies, optional.
12. Dialect dropdown: T-SQL (default) / PostgreSQL / Other (experimental, sub-dropdown).
    No "plain SQL". Dialect config object drives parser, rule set, equivalence
    eligibility, perf claims. Warn on dialect mismatch (TOP, [brackets], GETDATE()).
    Pass dialect explicitly to model prompt and re-parse. PostgreSQL = "supported,
    not yet evaluated".

## Revised stage order
0 scaffold -> 1 analyzer (corpus first) -> minimal UI + deploy -> 2 sandbox ->
3 AI layer -> 5 plan-paste -> 6 benchmark (optional) -> 7 polish.

## Log
- 0a done: folder created from empty, layout per handoff section 4.
- 0b written: requirements.txt (unpinned), pytest.ini, tests/test_smoke.py. Sandbox
  network disabled (pip: Name or service not known), so pytest NOT run. Pins pending.
- 0c written: CI workflow (checkout, python 3.12, pip install, pytest -q). YAML parse-checked only.
- Stage 0 closed by owner decision (pytest unverified). 1a done: corpus design, schema, taxonomy, corpus test.
- 1b done: 30 planted queries, taxonomy descriptions, expected.json (corpus test passed via direct call).
