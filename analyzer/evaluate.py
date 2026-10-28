"""Corpus evaluation scorer. Pure Python; the analyzer is passed in as a function.

Scoring rules (also stated in docs/corpus_design.md)
- Catch: a planted query is caught if EVERY expected rule id (of the scored kinds) fires.
  A planted query that could not be analysed counts as a MISS.
- Planted queries with no expected rule of the scored kinds are excluded from the catch rate.
- False alarm: a clean query with at least one finding (of the scored kinds). Clean queries
  that could not be analysed are NOT counted as alarms; they are reported separately and
  excluded from the false-alarm denominator.
- Parse-success rate: share of all queries in the split whose status is "analysed".
- All rates are counts with Wilson 95% confidence intervals.
- The held-out split can only be scored with confirm_heldout=True (speed bump, not a lock).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

SPLITS = ("dev", "heldout", "all")


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for k successes out of n. n == 0 gives the vacuous (0, 1)."""
    if n < 0 or k < 0 or k > n:
        raise ValueError("need 0 <= k <= n")
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


@dataclass(frozen=True)
class Rate:
    k: int
    n: int

    @property
    def low(self) -> float:
        return wilson(self.k, self.n)[0]

    @property
    def high(self) -> float:
        return wilson(self.k, self.n)[1]

    def __str__(self) -> str:
        if self.n == 0:
            return "n/a (0 queries)"
        return f"{self.k}/{self.n} ({100*self.k/self.n:.1f}%, 95% CI {100*self.low:.1f}-{100*self.high:.1f}%)"


@dataclass
class Report:
    split: str
    kinds: tuple
    catch: Rate
    false_alarm: Rate
    parse_success: Rate
    per_rule_recall: dict = field(default_factory=dict)       # rule_id -> Rate
    false_alarms_by_rule: dict = field(default_factory=dict)  # rule_id -> count over clean queries
    missed: list = field(default_factory=list)                # planted files not caught
    false_alarm_files: list = field(default_factory=list)     # [(file, [rule ids])]
    extras_on_planted: list = field(default_factory=list)     # [(file, [unexpected rule ids])]
    not_analysed: list = field(default_factory=list)          # [(file, label, reason)]


def load_corpus(root) -> tuple:
    root = Path(root)
    tax = json.loads((root / "taxonomy.json").read_text())
    kinds = {r["id"]: r["kind"] for r in tax["rules"]}
    entries = json.loads((root / "expected.json").read_text())["queries"]
    return kinds, entries


def _select(entries: list, split: str, confirm_heldout: bool) -> list:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    if split in ("heldout", "all") and not confirm_heldout:
        raise PermissionError(
            "held-out score is computed once, at the end of Stage 1: pass confirm_heldout=True")
    return [e for e in entries if split == "all" or e["split"] == split]


def score(entries: list, results: dict, rule_kinds: dict,
          kinds: Iterable[str] = ("syntactic", "schema"), split: str = "dev") -> Report:
    """Score already-computed results. `results` maps entry file -> object with
    .status ("analysed"|"not_analysed"), .findings (each with .rule_id), .reason."""
    kinds = tuple(kinds)
    in_view = lambda rid: rule_kinds[rid] in kinds

    catch_k = catch_n = fa_k = fa_n = 0
    recall = {rid: [0, 0] for rid in rule_kinds if in_view(rid)}
    fa_by_rule: dict = {}
    missed, fa_files, extras, not_analysed = [], [], [], []
    parsed = 0

    for e in entries:
        res = results[e["file"]]
        analysed = res.status == "analysed"
        parsed += analysed
        if not analysed:
            not_analysed.append((e["file"], e["label"], getattr(res, "reason", None)))
        fired = {f.rule_id for f in res.findings if in_view(f.rule_id)} if analysed else set()

        if e["label"] == "planted":
            expected = [r for r in e["rules"] if in_view(r)]
            if not expected:
                continue
            caught = analysed and all(r in fired for r in expected)
            catch_n += 1
            catch_k += caught
            if not caught:
                missed.append(e["file"])
            for r in expected:
                recall[r][1] += 1
                recall[r][0] += analysed and r in fired
            unexpected = sorted(fired - set(expected))
            if unexpected:
                extras.append((e["file"], unexpected))
        else:
            if not analysed:
                continue
            fa_n += 1
            if fired:
                fa_k += 1
                fa_files.append((e["file"], sorted(fired)))
                for r in fired:
                    fa_by_rule[r] = fa_by_rule.get(r, 0) + 1

    return Report(
        split=split, kinds=kinds,
        catch=Rate(catch_k, catch_n), false_alarm=Rate(fa_k, fa_n),
        parse_success=Rate(parsed, len(entries)),
        per_rule_recall={r: Rate(k, n) for r, (k, n) in sorted(recall.items()) if n},
        false_alarms_by_rule=dict(sorted(fa_by_rule.items())),
        missed=missed, false_alarm_files=fa_files, extras_on_planted=extras,
        not_analysed=not_analysed)


def evaluate(root, analyze_fn: Callable, split: str = "dev",
             kinds: Iterable[str] = ("syntactic", "schema"),
             confirm_heldout: bool = False) -> Report:
    """Run analyze_fn(sql_text, entry) -> result over a corpus split and score it."""
    root = Path(root)
    rule_kinds, entries = load_corpus(root)
    chosen = _select(entries, split, confirm_heldout)
    results = {e["file"]: analyze_fn((root / e["file"]).read_text(), e) for e in chosen}
    return score(chosen, results, rule_kinds, kinds, split)


def render_markdown(r: Report, title: str = "Analyzer evaluation") -> str:
    lines = [f"# {title}", "",
             f"Split: **{r.split}**. Rule kinds scored: {', '.join(r.kinds)}.", "",
             "| Metric | Result |", "|---|---|",
             f"| Catch rate (planted) | {r.catch} |",
             f"| False-alarm rate (clean, analysed) | {r.false_alarm} |",
             f"| Parse success (all queries) | {r.parse_success} |", ""]
    if r.per_rule_recall:
        lines += ["## Per-rule recall", "", "| Rule | Recall |", "|---|---|"]
        lines += [f"| {rid} | {rate} |" for rid, rate in r.per_rule_recall.items()]
        lines.append("")
    if r.missed:
        lines += ["## Missed planted queries", ""] + [f"- {f}" for f in r.missed] + [""]
    if r.false_alarm_files:
        lines += ["## False alarms on clean queries", ""]
        lines += [f"- {f}: {', '.join(ids)}" for f, ids in r.false_alarm_files] + [""]
    if r.extras_on_planted:
        lines += ["## Unexpected extra findings on planted queries", ""]
        lines += [f"- {f}: {', '.join(ids)}" for f, ids in r.extras_on_planted] + [""]
    if r.not_analysed:
        lines += ["## Not analysed", ""]
        lines += [f"- {f} ({label}): {why or 'no reason given'}" for f, label, why in r.not_analysed] + [""]
    lines += ["## Limits", "",
              "- Single-author corpus; the author also designed the rules, so rates lean optimistic.",
              "- The clean set is adversarial (mostly near-misses); false-alarm rate is not a",
              "  prediction for real-world code.",
              "- Not-analysed planted queries count as misses; not-analysed clean queries are",
              "  excluded from the false-alarm denominator.", ""]
    return "\n".join(lines)
