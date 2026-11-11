"""App tests. app_logic is tested directly. app.py is exercised against a STUB streamlit module:
this catches crashes and wrong names in OUR code; it does not verify the real Streamlit API."""
import contextlib
import importlib
import re
import sys

import app_logic as logic


def _rule_ids(a):
    return sorted({r["rule_id"] for r in a.rows})


def test_examples_produce_expected_findings():
    sql, ddl = logic.EXAMPLES["Non-sargable date filter + SELECT *"]
    assert _rule_ids(logic.run_analysis(sql, "tsql", None, ddl)) == ["QT001", "QT002"]
    sql, ddl = logic.EXAMPLES["NOT IN over a nullable column (needs table definitions)"]
    assert _rule_ids(logic.run_analysis(sql, "tsql", None, ddl)) == ["QT003", "QT102"]
    assert _rule_ids(logic.run_analysis(sql, "tsql", None, "")) == ["QT003"]           # no schema: QT102 skipped
    sql, ddl = logic.EXAMPLES["VARCHAR column compared with a number (needs table definitions)"]
    assert _rule_ids(logic.run_analysis(sql, "tsql", None, ddl)) == ["QT101"]
    sql, ddl = logic.EXAMPLES["Correlated subquery + DISTINCT with a join"]
    assert _rule_ids(logic.run_analysis(sql, "tsql", None, ddl)) == ["QT004", "QT006"]


def test_switches_limits_and_dialects():
    sql = "SELECT * FROM t WHERE YEAR(d) = 1"
    assert _rule_ids(logic.run_analysis(sql, "tsql", None, "", disabled=["QT001"])) == ["QT002"]
    big = logic.run_analysis("SELECT 1 " + "x" * logic.MAX_CHARS, "tsql", None, "")
    assert big.status == "rejected" and "too large" in big.reason
    a = logic.run_analysis(sql, "other", "mysql", "")
    assert "MySQL" in a.dialect_label and "Experimental" in a.dialect_status
    a = logic.run_analysis("SELECT TOP 5 [a] FROM t", "postgres", None, "")
    assert any("T-SQL" in w for w in a.warnings)


def test_not_analysed_and_report():
    a = logic.run_analysis("UPDATE t SET a = 1", "tsql", None, "")
    assert a.status == "not_analysed" and a.rows == [] and "unsupported statement" in a.reason
    assert "was not analysed" in a.report_md
    a = logic.run_analysis("SELECT * FROM t", "tsql", None, "")
    for part in ("SQL analysis report", "QT001", "No AI model was used", "What was NOT verified"):
        assert part in a.report_md


class _FakeSt:
    def __init__(self, press=True, sql="", ddl="", overrides=None):
        self.session_state = {"sql": sql, "ddl": ddl}
        self.press, self.calls, self.overrides = press, [], overrides or {}
        self.sidebar = contextlib.nullcontext()

    def _rec(self, name, *a, **k):
        self.calls.append((name, a, k))

    def __getattr__(self, name):
        if name in ("set_page_config", "title", "caption", "header", "subheader", "markdown", "text", "code",
                    "warning", "info", "error", "success", "download_button"):
            return lambda *a, **k: self._rec(name, *a, **k)
        raise AttributeError(name)

    def selectbox(self, label, options, index=0, format_func=None, key=None, on_change=None):
        options = list(options)
        if key:
            self.session_state.setdefault(key, options[index])
            return self.session_state[key]
        return self.overrides.get(label, options[index])

    def text_area(self, label, key=None, height=None, max_chars=None, value=""):
        return self.session_state.get(key, value)

    def checkbox(self, label, value=True, key=None):
        return self.overrides.get(key, value)

    def button(self, label, type=None):
        return self.press

    def expander(self, label):
        return contextlib.nullcontext()

    def columns(self, n):
        return [contextlib.nullcontext() for _ in range(n)]

    def named(self, name):
        return [c for c in self.calls if c[0] == name]


def _run_app(**kw):
    fake = _FakeSt(**kw)
    saved = sys.modules.get("streamlit")
    sys.modules["streamlit"] = fake
    sys.modules.pop("app", None)
    try:
        importlib.import_module("app").main()
    finally:
        sys.modules.pop("app", None)
        if saved is None:
            sys.modules.pop("streamlit", None)
        else:
            sys.modules["streamlit"] = saved
    return fake


def test_app_runs_and_shows_findings_and_report():
    fake = _run_app(sql="SELECT * FROM t WHERE YEAR(d) = 1")
    assert fake.named("subheader") and "2 finding" in fake.named("subheader")[0][1][0]
    dl = fake.named("download_button")
    assert dl and "QT002" in dl[0][1][1]
    texts = " ".join(c[1][0] for c in fake.named("text"))
    assert "SELECT * returns every column" in texts


def test_app_not_clean_wording_for_unanalysed_and_clean_cases():
    fake = _run_app(sql="UPDATE t SET a = 1")
    assert any("NOT a clean result" in c[1][0] for c in fake.named("error"))
    fake = _run_app(sql="SELECT a FROM t WHERE a = 1")
    assert any("does not mean the query is correct" in c[1][0] for c in fake.named("info"))


def test_app_idle_and_empty_paths():
    assert _run_app(press=False, sql="SELECT * FROM t").named("download_button") == []
    fake = _run_app(press=True, sql="   ")
    assert any("Paste a query" in c[1][0] for c in fake.named("warning"))


def test_user_controlled_text_never_goes_through_markdown():
    fake = _run_app(sql="SELECT * FROM t WHERE UPPER([x](http://evil)) = 1 OR a = 1")
    for _, args, kw in fake.named("markdown"):
        assert "unsafe_allow_html" not in kw
        s = args[0]
        assert re.fullmatch(r"\*\*QT\d{3} (HIGH|MEDIUM|LOW)\*\*( \(line \d+\))?", s) or s.startswith("- It does not run")
