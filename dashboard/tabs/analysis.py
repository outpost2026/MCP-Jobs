"""Analyza tab for MCP-Jobs dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard.filters import HIGH_SIGNAL_QUERIES
from dashboard.metrics import (
    company_signal,
    cross_stack_companies,
    portal_effectiveness,
    portal_quality,
    salary_by_domain,
    stale_vs_fresh,
    status_funnel,
    velocity,
)


def render_analysis_tab(conn, active_queries) -> None:
    """Render the Analyza tab."""
    st.markdown("### Analyza trhu (high-signal kontext)")

    # -- Velocity
    st.markdown("---")
    st.markdown("**Freshness / velocity (posledni N dni)**")
    df_vel = velocity(conn, active_queries, days=st.session_state.filter_days)
    if not df_vel.empty:
        st.dataframe(df_vel, use_container_width=True, hide_index=True)
        st.bar_chart(df_vel.groupby("day")["new_ads"].sum())
    else:
        st.info("Zadna data pro velocity.")

    # -- Salary by domain
    st.markdown("---")
    st.markdown("**Salary coverage & median podle query**")
    df_sal = salary_by_domain(conn, active_queries)
    if not df_sal.empty:
        st.dataframe(df_sal, use_container_width=True, hide_index=True)
    else:
        st.info("Zadna salary data.")

    # -- Company signal
    st.markdown("---")
    st.markdown("**Company signal (opakovany / multi-query hiring)**")
    df_co = company_signal(conn, active_queries)
    if not df_co.empty:
        st.dataframe(df_co, use_container_width=True, hide_index=True)
    else:
        st.info("Zadne company signals.")

    # -- Portal effectiveness
    st.markdown("---")
    st.markdown("**Portal effectiveness (signal %)**")
    df_pe = portal_effectiveness(conn, HIGH_SIGNAL_QUERIES)
    if not df_pe.empty:
        st.dataframe(df_pe, use_container_width=True, hide_index=True)
    else:
        st.info("Zadna data pro portal effectiveness.")

    # -- Status funnel
    st.markdown("---")
    st.markdown("**Status funnel**")
    df_funnel = status_funnel(conn, active_queries)
    if not df_funnel.empty:
        st.dataframe(df_funnel, use_container_width=True, hide_index=True)
    else:
        st.info("Zadne data pro funnel.")

    # -- Stale vs fresh
    st.markdown("---")
    st.markdown("**Stale vs fresh**")
    df_sf = stale_vs_fresh(conn, active_queries)
    if not df_sf.empty:
        st.dataframe(df_sf, use_container_width=True, hide_index=True)
    else:
        st.info("Zadna data pro stale/fresh.")

    # -- Cross-stack companies
    st.markdown("---")
    st.markdown("**Cross-stack companies (>=2 domeny)**")
    df_cs = cross_stack_companies(conn, active_queries)
    if not df_cs.empty:
        st.dataframe(df_cs, use_container_width=True, hide_index=True)
    else:
        st.info("Zadne cross-stack firmy.")

    # -- Portal quality (legacy)
    st.markdown("---")
    st.markdown("**Portal quality (legacy)**")
    df_pq = portal_quality(conn)
    if not df_pq.empty:
        st.dataframe(df_pq, use_container_width=True, hide_index=True)
    else:
        st.info("Zadna portal quality data.")
