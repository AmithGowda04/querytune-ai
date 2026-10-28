# Corpus freeze

Date: 2026-10-28. Git tag: `corpus-frozen`.

Contents at freeze: 30 planted (12 held-out) and 32 clean (10 held-out) T-SQL queries,
12 rule ids in `taxonomy.json`. All written by one author (the assistant) in one session,
before any rule code existed. No independent (owner-written) queries were added.

Policy
- Rules are designed and tuned on `split: dev` only. Held-out files are not read during rule design.
- The held-out score is computed once, at the end of Stage 1.
- `HELDOUT.sha256` holds SHA-256 hashes of every held-out file; `tests/test_corpus.py` fails if one changes.
- If a held-out query must change (e.g. a T-SQL syntax error found when SQLGlot first parses it),
  update the hash in the same commit and list the change under "Post-freeze changes" below.
  Dev queries may be fixed the same way; list those too.

Known limits: single author, adversarial clean set (see docs/corpus_design.md).

## Post-freeze changes
(none)
