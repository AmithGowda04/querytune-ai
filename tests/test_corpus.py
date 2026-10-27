"""Corpus consistency checks. Stdlib only. Runs on whatever is in corpus/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"


def _load():
    tax = json.loads((CORPUS / "taxonomy.json").read_text())
    exp = json.loads((CORPUS / "expected.json").read_text())
    return {r["id"] for r in tax["rules"]}, exp["queries"]


def test_schema_and_taxonomy_exist():
    assert (CORPUS / "schema_tsql.sql").is_file()
    ids, _ = _load()
    assert len(ids) == 12


def test_entries_are_well_formed():
    ids, queries = _load()
    seen = set()
    for q in queries:
        assert q["file"] not in seen, f"duplicate {q['file']}"
        seen.add(q["file"])
        assert (CORPUS / q["file"]).is_file(), f"missing file {q['file']}"
        assert q["label"] in ("planted", "clean")
        assert q["split"] in ("dev", "heldout")
        assert isinstance(q["needs_schema"], bool)
        assert set(q["rules"]) <= ids, f"unknown rule in {q['file']}"
        if q["label"] == "clean":
            assert q["rules"] == []
            assert q["file"].startswith("clean/")
        else:
            assert q["rules"], f"planted query without rules: {q['file']}"
            assert q["file"].startswith("planted/")


def test_no_orphan_sql_files():
    _, queries = _load()
    listed = {q["file"] for q in queries}
    on_disk = {
        str(p.relative_to(CORPUS)).replace("\\", "/")
        for sub in ("planted", "clean")
        for p in (CORPUS / sub).glob("*.sql")
    }
    assert on_disk == listed
