"""Stage 0 smoke tests: project skeleton is intact and importable."""
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["analyzer", "sandbox", "ai", "plans", "benchmark"]


def test_packages_importable():
    for name in PACKAGES:
        importlib.import_module(name)


def test_corpus_dirs_exist():
    assert (ROOT / "corpus" / "planted").is_dir()
    assert (ROOT / "corpus" / "clean").is_dir()


def test_progress_file_exists():
    assert (ROOT / "PROGRESS.md").is_file()
