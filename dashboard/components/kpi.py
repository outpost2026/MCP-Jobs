"""KPI cards for MCP-Jobs dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import streamlit as st


def render_kpi(df: pd.DataFrame) -> None:
    """Render KPI cards from filtered DataFrame (compact, for main area)."""
    total = len(df)
    portals = df["portal"].nunique()
    companies = df["company"].nunique()
    with_salary = df["salary"].notna().sum()
    salary_pct = round(100 * with_salary / total, 1) if total > 0 else 0

    # Tech score metrics (v2)
    if "tech_score" in df.columns:
        scores = df["tech_score"].dropna()
        high_tech = len(scores[scores >= 60])
        avg_score = round(scores.mean(), 1) if len(scores) > 0 else 0
    else:
        high_tech = 0
        avg_score = 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Inzeratu</div>
            <div class="metric-value">{total}</div></div>""",
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Firem</div>
            <div class="metric-value">{companies}</div></div>""",
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Se mzdou</div>
            <div class="metric-value">{salary_pct}%</div></div>""",
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">High-tech</div>
            <div class="metric-value">{high_tech}</div></div>""",
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Avg Score</div>
            <div class="metric-value">{avg_score}</div></div>""",
            unsafe_allow_html=True,
        )


def render_kpi_sidebar(df: pd.DataFrame) -> None:
    """Render compact KPI in sidebar."""
    total = len(df)
    if "tech_score" in df.columns:
        scores = df["tech_score"].dropna()
        high_tech = len(scores[scores >= 60])
    else:
        high_tech = 0

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Prehled**")
    st.sidebar.markdown(f"Inzeratu: **{total}**")
    st.sidebar.markdown(f"High-tech (60+): **{high_tech}**")
