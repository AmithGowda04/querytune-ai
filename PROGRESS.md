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
  - [x] 1c 32 clean queries (C001-C032) + expected.json. 22 dev / 10 heldout.
        29 are near-misses, 2 plain, 2 tagged parse-risk (DECLARE, CROSS APPLY; also VALUES grid).
        Corpus is ADVERSARIAL, not representative: false-alarm rate will read worse than on
        real code. Report it with that caveat. Two QT103 HAZARD queries (C027 dev, C028 heldout)
        are correct queries a naive QT103 will flag; that is deliberate.
        tests/test_corpus.py has a balance check (run directly, not pytest).
  - [x] 1d FROZEN 2026-10-28. git tag corpus-frozen. corpus/FROZEN.md, corpus/HELDOUT.sha256
        (22 held-out files hashed; test_heldout_files_unchanged enforces). 30 planted (12 heldout),
        32 clean (10 heldout). No owner-written queries were added (single-author corpus).
        Any post-freeze corpus change must be listed in corpus/FROZEN.md.
  - [x] 1e-i analyzer/dialects.py: Dialect config (tsql / postgres / other+sub-dialect), status labels,
        dialect-mismatch warning (regex, literals/comments stripped). Pure Python, no sqlglot.
        tests/test_dialects.py (9 tests, called directly, NOT pytest; uses DEV corpus only).
        sqlglot_read strings ("tsql","postgres","mysql"...) are UNVERIFIED until sqlglot runs.
  - [x] 1e-ii analyzer/rules.py (Rule/Finding/Context/RuleRegistry; DEFAULT_REGISTRY is EMPTY until 1f)
        + analyzer/parser.py analyze() with INJECTED parse_fn(sql, sqlglot_read_name) -> tree.
        Behaviour: empty/oversized (20,000 chars) input -> not_analysed; parse exception -> not_analysed
        (never reported as clean); rule crash/misbehaviour isolated into rule_errors (message holds only
        the exception type, no query text); select() honours dialect kinds, schema availability,
        on/off switches, off-by-default rules; unknown ids raise. "analysed + no findings" = no rule fired.
        tests/test_rules_engine.py: 17 tests, all earlier suites re-run (17), all called DIRECTLY not pytest.
  - [x] 1e-iii analyzer/evaluate.py: wilson(), Rate, score(), evaluate(), render_markdown().
        Catch = all expected ids of scored kinds fire; not-analysed planted = miss; not-analysed clean
        excluded from false-alarm denominator (reported separately); parse-success over all queries;
        schema-only planted excluded in syntactic view; held-out needs confirm_heldout=True (speed bump).
        tests/test_evaluate.py: 10 tests (incl. oracle/silent/noisy analyzers on the real DEV corpus).
        Total 44 tests, all called DIRECTLY (not pytest).
  - [ ] 1f rules, tuned on dev only; 1g evaluation script + report (needs sqlglot)
  Optional high-value: owner writes ~10 held-out queries independently.

## Next action
BLOCKED on sqlglot (sandbox DNS cannot reach PyPI; owner cannot run locally now).
Everything in Stage 1 that does not need sqlglot is DONE (corpus, dialects, framework, scorer).
Remaining and why it needs sqlglot:
  - 1f rules: AST logic + tuning on dev needs real parses (node names unverified).
  - 1g real evaluation: needs the rules + the real parse_fn(sql, read) -> sqlglot tree.
  - first parse of all 62 corpus queries (may expose invalid T-SQL; fix + list in corpus/FROZEN.md).
To unblock: enable package-registry network access for the sandbox (account setting), OR owner runs
  pip install -r requirements.txt; pytest; pip freeze   and pastes output (+ corpus parse results).
Then: pin requirements.txt, close Stage 0, do 1f/1g.
Do NOT write 1f rules blind: they cannot be tuned or verified without parsing.

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
- 1c done: 32 clean queries (29 near-miss), balance test added.
- 1d done: corpus frozen, tagged corpus-frozen, held-out hashes enforced by test.
- 1e-i done: dialect config + mismatch warning, 9 tests passed via direct calls. Network re-checked: still no route to PyPI.
- 1e-ii done: rule framework + analyze() with injected parser; 17 new tests, 34 total, all passed via direct calls.
- 1e-iii done: evaluation scorer, 10 tests; 44 total passed via direct calls. Stage 1 blocked on sqlglot.
- Docs: PRIVACY.md (DRAFT, requirements for final code) and README.md (status table, limits, no results claimed) written.
