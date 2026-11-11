"""Run the corpus evaluation. `python -m analyzer.run_eval --split dev [--out FILE]`.

Held-out needs --confirm-heldout (computed once, at the end). Two views are scored:
syntactic rules with NO schema, and all rules with the corpus schema supplied.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from analyzer.api import analyze_sql
from analyzer.dialects import get_dialect
from analyzer.evaluate import evaluate, render_markdown

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"


def run(split: str, confirm: bool):
    ddl = (CORPUS / "schema_tsql.sql").read_text()
    tsql = get_dialect("tsql")
    syn = evaluate(CORPUS, lambda sql, e: analyze_sql(sql, tsql), split, ("syntactic",), confirm)
    full = evaluate(CORPUS, lambda sql, e: analyze_sql(sql, tsql, ddl), split, ("syntactic", "schema"), confirm)
    return syn, full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "heldout"])
    ap.add_argument("--confirm-heldout", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    syn, full = run(a.split, a.confirm_heldout)
    md = (render_markdown(syn, f"Syntactic rules, no schema ({a.split})") + "\n---\n\n" +
          render_markdown(full, f"All rules, schema supplied ({a.split})"))
    print(md)
    if a.out:
        Path(a.out).write_text(md)


if __name__ == "__main__":
    main()
