# QueryTune AI

Rule-based SQL checks for data analysts, with explicit limits. Python, Streamlit, standard library only.
**Status: first version built, not yet deployed.** No AI model is used in the app yet.

Principle: do not claim what was not verified. Every result says what it did NOT check.

## What it does today
- Paste T-SQL (PostgreSQL and others: experimental) and get findings from 12 fixed rules:
  9 that need only the SQL, and 3 that run only if you also paste `CREATE TABLE` statements.
- Dialect dropdown with a mismatch warning (for example T-SQL pasted while PostgreSQL is selected).
- Per-rule on/off switches, a "why this matters" bad/good example for each finding, and a markdown report.
- Anything it cannot analyse is reported as "not analysed", never as clean.
- No database connection, no query execution, nothing sent to any third party by the app.

## Results (corpus: 30 planted + 32 clean T-SQL queries, frozen, single author)
| Split | Planted caught | False alarms on clean |
|---|---|---|
| Dev (rules were tuned on it, so NOT evidence) | 18/18 | 0/22 |
| Held-out | 12/12 (95% CI 75.7-100%) | 0/10 (95% CI 0-27.8%) |

Read these carefully: the same author wrote the queries and the rules; the sample is tiny; the clean set is
adversarial; the corpus has never been run on SQL Server. A realistic probe outside the corpus found misses and
likely false alarms: see `docs/KNOWN_LIMITATIONS.md`. Expect real-world accuracy to be lower.
The held-out split was run twice (the first result was lost when the build sandbox reset and was regenerated
with identical code and identical numbers); see `corpus/FROZEN.md`.

## Not built / not verified
| Item | State |
|---|---|
| Real-Streamlit behaviour of `app.py` | Tested only against a stub module |
| `pytest` and CI | Never run in the build sandbox (no network); first real run is on GitHub |
| SQLGlot-based parsing | Not used. A hand-written lightweight parser is used instead (heuristic, not validating) |
| AI layer (explain / debug / optimise), literal scrubber, prompts | Code and fake-client tests exist; NOT wired into the app; never run against a real model |
| Test-data generator + DuckDB equivalence checking | Not built |
| Execution-plan / STATISTICS parsers | Built; tested on hand-written samples only; not wired in |
| Local SQL Server benchmark | Not built. "Performance verified" can therefore never appear |

## Limits
See `docs/KNOWN_LIMITATIONS.md`. In short: heuristic rules with misses and false alarms; INSERT / UPDATE /
DELETE / MERGE / EXEC / PIVOT are not analysed; a clean result is not a correctness or speed guarantee.

## Run the tests
```
pip install -r requirements-dev.txt
pytest
```

## Run the app
```
pip install -r requirements.txt
streamlit run app.py
```
See `docs/DEPLOY.md`, `PRIVACY.md`, `PROGRESS.md`, `docs/corpus_design.md`, `corpus/FROZEN.md`.
