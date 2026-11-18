"""QueryTune AI: Streamlit app. Thin UI over app_logic. No AI, no database, nothing stored."""
import streamlit as st

import app_logic as logic

SEV_ICON = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}


def _load_example():
    sql, ddl = logic.EXAMPLES[st.session_state["example"]]
    st.session_state["sql"], st.session_state["ddl"] = sql, ddl


def main():
    st.set_page_config(page_title="QueryTune AI", layout="wide")
    st.title("QueryTune AI")
    st.caption("Rule-based SQL checks with explicit limits. No AI model is used in this version, nothing is "
               "sent to any third party by this app, and it has no database connection.")

    st.session_state.setdefault("sql", "")
    st.session_state.setdefault("ddl", "")

    with st.sidebar:
        st.header("Settings")
        keys = [k for k, _ in logic.DIALECT_CHOICES]
        labels = dict(logic.DIALECT_CHOICES)
        dialect = st.selectbox("SQL dialect", keys, index=0, format_func=lambda k: labels[k])
        sub = None
        if dialect == "other":
            names = dict(logic.OTHER_CHOICES)
            sub = st.selectbox("Which one?", [k for k, _ in logic.OTHER_CHOICES], format_func=lambda k: names[k])
        st.caption("T-SQL is the only dialect evaluated. PostgreSQL: syntactic rules, not yet evaluated. "
                   "Others: experimental.")
        with st.expander("Rules (switch off any you do not want)"):
            disabled = []
            for r in logic.rule_catalog():
                on = st.checkbox(f"{r['id']} {r['name']}", value=True, key=f"rule_{r['id']}")
                if not on:
                    disabled.append(r["id"])

    st.selectbox("Load an example", list(logic.EXAMPLES), key="example", on_change=_load_example)
    left, right = st.columns(2)
    with left:
        sql = st.text_area("SQL query", key="sql", height=320, max_chars=logic.MAX_CHARS)
    with right:
        ddl = st.text_area("Table definitions (optional: CREATE TABLE statements; enables 3 extra rules)",
                           key="ddl", height=320, max_chars=logic.MAX_CHARS)

    snapshot = (sql, ddl, dialect, sub, tuple(disabled))
    if st.button("Analyze", type="primary"):
        if not sql.strip():
            st.warning("Paste a query first.")
            return
        # Kept in session memory only, so results survive reruns (download click, rule toggles).
        st.session_state["analysis"] = (snapshot, logic.run_analysis(sql, dialect, sub, ddl, disabled))
    saved = st.session_state.get("analysis")
    if not saved:
        return
    snap, a = saved
    if snap != snapshot:
        st.caption("The query or settings changed since this analysis. Press Analyze to refresh it.")
    st.caption(f"Dialect: {a.dialect_label}. {a.dialect_status}.")
    for w in a.warnings:
        st.warning(w)
    if a.status != "analysed":
        st.error(f"Not analysed: {a.reason}. This is NOT a clean result.")
    elif not a.rows:
        st.info(f"None of the {len(a.rules_run)} rules that ran fired. This does not mean the query is "
                "correct or fast.")
    else:
        st.subheader(f"{len(a.rows)} finding(s)")
        for row in a.rows:
            where = f" (line {row['line']})" if row["line"] else ""
            st.markdown(f"**{row['rule_id']} {SEV_ICON[row['severity']]}**{where}")
            st.text(row["message"])
            with st.expander(f"Why this matters ({row['rule_id']})"):
                st.text(row["rationale"])
                st.text("Pattern to avoid:")
                st.code(row["bad"], language="sql")
                st.text("Better:")
                st.code(row["good"], language="sql")
    if a.skipped:
        with st.expander("Rules that did not run"):
            for rid, why in a.skipped:
                st.text(f"{rid}: {why}")
    for rid, msg in a.rule_errors:
        st.warning(f"Rule {rid} failed and was skipped ({msg}).")
    st.download_button("Download report (markdown)", a.report_md, file_name="sql_analysis_report.md",
                       mime="text/markdown")
    with st.expander("What this tool does not do"):
        st.markdown("- It does not run your query or connect to any database.\n"
                    "- It does not prove a query is correct, equivalent after a change, or faster.\n"
                    "- It is heuristic: it has misses and false alarms. See docs/KNOWN_LIMITATIONS.md.\n"
                    "- INSERT, UPDATE, DELETE, MERGE, EXEC and PIVOT are not analysed.")


if __name__ == "__main__":
    main()
