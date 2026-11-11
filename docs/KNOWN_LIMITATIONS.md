# Known limitations (observed, not guessed)

The analyzer is a **heuristic, standard-library T-SQL analyzer**. It is not SQLGlot and not a full
T-SQL grammar. It does not validate that your SQL is valid T-SQL. A result of "no findings" means
*none of the 12 rules fired*, never "the query is correct or fast".

## Evidence behind these notes
Besides the frozen corpus, I ran an informal probe of realistic queries that are NOT in the corpus.
It is too small to be a rate; treat it as a list of observed behaviours.

## Observed misses (the rule exists but did not fire)
- **QT002**: a function is detected, but arithmetic on a column (`WHERE total * 1.1 > 100`) is not.
- **QT006**: correlation is detected only through qualified references (`c.id`). A correlated subquery
  that uses only bare column names is missed.
- **QT009**: a comma join whose WHERE uses unqualified columns is skipped on purpose, because the
  analyzer cannot tell which table a bare column belongs to.
- **QT101 / QT103**: only column-versus-literal and column-equals-column joins; no other forms.

## Statements it will not analyse (reported as "not analysed", never as clean)
`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `EXEC`, `CREATE`, and `PIVOT`/`UNPIVOT` in FROM. A `SELECT` inside
an `INSERT ... SELECT` is therefore not checked.

## Likely false alarms (by design of the rule)
- **QT004** flags every `SELECT DISTINCT` that has a JOIN. Many are legitimate.
- **QT003** flags every `NOT IN (subquery)`, even when the subquery column is `NOT NULL`
  (QT102 only adds a stronger warning when the column is nullable).
- **QT103** is a heuristic. A genuine many-to-many join will be flagged; the self-join "pairs of rows on
  the same key" pattern is exempted only when the ON clause also compares the table's own key.

## Schema-dependent rules
Run only when you paste `CREATE TABLE` statements. `ALTER TABLE ... ADD CONSTRAINT` is not read, so a primary
key added that way is unknown and may cause QT103 to over-report.

## Corpus and results
See `docs/RESULTS_dev.md` (rules were tuned on this split: not evidence) and `docs/RESULTS_heldout.md`.
Both come from a single-author, 62-query corpus written by the same person (an AI assistant) who designed the
rules, so they lean optimistic and have wide confidence intervals. The corpus T-SQL has never been checked
by SQL Server or a full T-SQL parser. "Parse success" is weak evidence because the lite parser is tolerant.
