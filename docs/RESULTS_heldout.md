# Syntactic rules, no schema (heldout)

Split: **heldout**. Rule kinds scored: syntactic.

| Metric | Result |
|---|---|
| Catch rate (planted) | 10/10 (100.0%, 95% CI 72.2-100.0%) |
| False-alarm rate (clean, analysed) | 0/10 (0.0%, 95% CI 0.0-27.8%) |
| Parse success (all queries) | 22/22 (100.0%, 95% CI 85.1-100.0%) |

## Per-rule recall

| Rule | Recall |
|---|---|
| QT001 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT002 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT003 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT004 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT005 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT006 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
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

# All rules, schema supplied (heldout)

Split: **heldout**. Rule kinds scored: syntactic, schema.

| Metric | Result |
|---|---|
| Catch rate (planted) | 12/12 (100.0%, 95% CI 75.7-100.0%) |
| False-alarm rate (clean, analysed) | 0/10 (0.0%, 95% CI 0.0-27.8%) |
| Parse success (all queries) | 22/22 (100.0%, 95% CI 85.1-100.0%) |

## Per-rule recall

| Rule | Recall |
|---|---|
| QT001 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT002 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT003 | 2/2 (100.0%, 95% CI 34.2-100.0%) |
| QT004 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT005 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
| QT006 | 1/1 (100.0%, 95% CI 20.7-100.0%) |
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
