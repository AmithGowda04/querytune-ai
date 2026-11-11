# Syntactic rules, no schema (dev)

Split: **dev**. Rule kinds scored: syntactic.

| Metric | Result |
|---|---|
| Catch rate (planted) | 16/16 (100.0%, 95% CI 80.6-100.0%) |
| False-alarm rate (clean, analysed) | 0/22 (0.0%, 95% CI 0.0-14.9%) |
| Parse success (all queries) | 40/40 (100.0%, 95% CI 91.2-100.0%) |

## Per-rule recall

| Rule | Recall |
|---|---|
| QT001 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT002 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT003 | 3/3 (100.0%, 95% CI 43.8-100.0%) |
| QT004 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT005 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT006 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT007 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT008 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT009 | 1/1 (100.0%, 95% CI 20.7-100.0%) |

## Limits

- Single-author corpus; the author also designed the rules, so rates lean optimistic.
- The clean set is adversarial (mostly near-misses); false-alarm rate is not a
  prediction for real-world code.
- Not-analysed planted queries count as misses; not-analysed clean queries are
  excluded from the false-alarm denominator.

---

# All rules, schema supplied (dev)

Split: **dev**. Rule kinds scored: syntactic, schema.

| Metric | Result |
|---|---|
| Catch rate (planted) | 18/18 (100.0%, 95% CI 82.4-100.0%) |
| False-alarm rate (clean, analysed) | 0/22 (0.0%, 95% CI 0.0-14.9%) |
| Parse success (all queries) | 40/40 (100.0%, 95% CI 91.2-100.0%) |

## Per-rule recall

| Rule | Recall |
|---|---|
| QT001 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT002 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT003 | 3/3 (100.0%, 95% CI 43.8-100.0%) |
| QT004 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT005 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT006 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT007 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT008 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT009 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT101 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT102 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT103 | 1/1 (100.0%, 95% CI 20.7-100.0%) |

## Limits

- Single-author corpus; the author also designed the rules, so rates lean optimistic.
- The clean set is adversarial (mostly near-misses); false-alarm rate is not a
  prediction for real-world code.
- Not-analysed planted queries count as misses; not-analysed clean queries are
  excluded from the false-alarm denominator.
