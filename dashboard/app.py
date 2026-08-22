"""MCP-Jobs Dashboard -- Streamlit frontend for job listing analytics.

Usage:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# -- Encoding safety (Windows cp1250) --
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from dashboard.filters import (  # noqa: E402
    build_where_clause,
    get_active_queries,
    init_filter_state,
    render_sidebar_filters,
)
from dashboard.tabs.ads import render_ads_tab  # noqa: E402
from dashboard.tabs.analysis import render_analysis_tab  # noqa: E402
from dashboard.tabs.runs import render_runs_tab  # noqa: E402
from mcp_jobs.db import connect, get_database_url, init_db  # noqa: E402


def main():
    # -- Authentication --
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("MCP-Jobs Dashboard")
        pwd = st.text_input("Pristupove heslo", type="password")
        if st.button("Prisloupit"):
            if pwd == os.environ.get("MCPJOBS_DASH_PWD", "mcpjobs-demo-2026"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Nespravne heslo")
        st.stop()

    # -- Filter state --
    init_filter_state()

    # -- Page config --
    st.set_page_config(
        page_title="MCP-Jobs Dashboard",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # -- Dark theme CSS --
    _theme_css = (_REPO_ROOT / "dashboard" / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{_theme_css}</style>", unsafe_allow_html=True)

    st.markdown(
        "<h1 style='text-align: center; margin-bottom: 5px;'>MCP-Jobs Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #94A3B8; font-size: 16px; "
        "margin-bottom: 10px;'>CZ job portal analytics | EROI-scored listings</p>",
        unsafe_allow_html=True,
    )

    # -- DB connection --
    DB_URL = get_database_url()
    if not DB_URL:
        st.error("DATABASE_URL neni nastaven. Uprav .env soubor.")
        st.stop()

    try:
        conn = connect(DB_URL)
        init_db(conn)
    except Exception as e:
        st.error(f"Chyba pripojeni k DB: {e}")
        st.stop()

    # -- Cached query helper --
    @st.cache_data(ttl=300, show_spinner=False)
    def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
        """Cached SQL -> DataFrame. Invalidate via st.cache_data.clear() after writes."""
        return pd.read_sql(sql, conn, params=params)

    # -- Sidebar filters --
    _portals = run_query(
        "SELECT DISTINCT portal FROM ads WHERE portal IS NOT NULL ORDER BY portal"
    )["portal"].tolist()
    _queries = run_query(
        "SELECT DISTINCT query_name FROM ads WHERE query_name IS NOT NULL ORDER BY query_name"
    )["query_name"].tolist()

    render_sidebar_filters(_portals, _queries)

    # Shared WHERE for all tabs
    where_sql, where_params = build_where_clause()
    active_queries = get_active_queries()

    # -- Tabs --
    tab_ads, tab_analysis, tab_runs = st.tabs(["Inzeraty", "Analyza", "Historie behu"])

    with tab_ads:
        render_ads_tab(conn, run_query, where_sql, where_params)

    with tab_analysis:
        render_analysis_tab(conn, active_queries)

    with tab_runs:
        render_runs_tab(run_query)


if __name__ == "__main__":
    main()
