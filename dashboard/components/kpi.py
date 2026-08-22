"""KPI cards for MCP-Jobs dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import streamlit as st


def render_kpi(df: pd.DataFrame) -> None:
    """Render KPI cards from filtered DataFrame."""
    total = len(df)
    portals = df["portal"].nunique()
    companies = df["company"].nunique()
    new_today = len(df[df["first_seen"] == datetime.now(tz=UTC).date()])
    with_salary = df["salary"].notna().sum()
    with_desc = (df["description"].fillna("").str.len() > 50).sum()
    salary_pct = round(100 * with_salary / total, 1) if total > 0 else 0
    desc_pct = round(100 * with_desc / total, 1) if total > 0 else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Celkem inzeratu</div>
            <div class="metric-value">{total}</div></div>""",
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Portalu</div>
            <div class="metric-value">{portals}</div></div>""",
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Unikatnich firem</div>
            <div class="metric-value">{companies}</div></div>""",
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Novych (dnes)</div>
            <div class="metric-value">{new_today}</div></div>""",
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">Se mzdou</div>
            <div class="metric-value">{with_salary}</div>
            <div class="metric-label">{salary_pct}% coverage</div></div>""",
            unsafe_allow_html=True,
        )
    with k6:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-label">S popisem</div>
            <div class="metric-value">{with_desc}</div>
            <div class="metric-label">{desc_pct}% coverage</div></div>""",
            unsafe_allow_html=True,
        )
