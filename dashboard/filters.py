"""Shared filter state and high-signal domain definitions for MCP-Jobs dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import streamlit as st

# -- Domain taxonomy (high-signal only) --
# Legacy / noise domains (udrzbar, spravce_budov, zahradnik, ...) are intentionally
# excluded from HIGH_SIGNAL_QUERIES. They remain queryable via explicit filter.

HIGH_SIGNAL_QUERIES: list[str] = [
    "ai_llm_engineer",
    "python_ai_engineer",
    "data_engineering",
    "devops_ci_cd",
    "mcp_agentic",
    "reverse_engineering",
    "prumyslova_automatizace",
    "cnc_cam_automation",
    "cnc_jobs",
]

DOMAIN_MAP: dict[str, str] = {
    "ai_llm_engineer": "AI / LLM",
    "python_ai_engineer": "AI / LLM",
    "mcp_agentic": "AI / LLM",
    "data_engineering": "Data",
    "devops_ci_cd": "DevOps",
    "reverse_engineering": "Security / RE",
    "prumyslova_automatizace": "Industrial",
    "cnc_cam_automation": "CNC / CAM",
    "cnc_jobs": "CNC / CAM",
}

DOMAIN_OPTIONS: list[str] = sorted(set(DOMAIN_MAP.values()))


def init_filter_state() -> None:
    """Initialize session_state keys once."""
    defaults: dict[str, Any] = {
        "filter_portals": [],  # empty = all
        "filter_queries": [],  # empty = all (or high-signal if toggle on)
        "filter_domains": [],  # empty = all domains
        "filter_status": "Vše",
        "filter_search": "",
        "filter_days": 14,  # first_seen lookback
        "filter_high_signal_only": True,
        "filter_min_completeness": 0,
        "last_visit": None,  # date of previous session
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_active_queries() -> list[str] | None:
    """
    Return list of query_name values to filter on, or None = no query filter.
    When high_signal_only is on and no explicit queries selected -> HIGH_SIGNAL_QUERIES.
    """
    explicit = st.session_state.get("filter_queries") or []
    if explicit:
        return explicit
    if st.session_state.get("filter_high_signal_only", True):
        return HIGH_SIGNAL_QUERIES
    return None  # all queries


def get_date_from() -> date:
    days = int(st.session_state.get("filter_days") or 14)
    return datetime.now(tz=UTC).date() - timedelta(days=days)


def render_sidebar_filters(
    available_portals: list[str], available_queries: list[str]
) -> None:
    """Render filter controls in sidebar. Call once per run after init_filter_state()."""
    st.sidebar.markdown("### Filtry")

    st.session_state.filter_high_signal_only = st.sidebar.toggle(
        "Jen high-signal domény",
        value=st.session_state.filter_high_signal_only,
        help="AI/LLM, Data, DevOps, RE, Industrial, CNC -- vypne legacy noise query",
    )

    st.session_state.filter_days = st.sidebar.slider(
        "Období (dny)",
        min_value=3,
        max_value=60,
        value=st.session_state.filter_days,
    )

    st.session_state.filter_portals = st.sidebar.multiselect(
        "Portály",
        options=available_portals,
        default=st.session_state.filter_portals,
    )

    # Domain multiselect -> expands to query list
    selected_domains = st.sidebar.multiselect(
        "Domény",
        options=DOMAIN_OPTIONS,
        default=st.session_state.filter_domains,
    )
    st.session_state.filter_domains = selected_domains

    if selected_domains:
        derived = [q for q, d in DOMAIN_MAP.items() if d in selected_domains]
        st.session_state.filter_queries = derived
    else:
        st.session_state.filter_queries = st.sidebar.multiselect(
            "Query (explicit)",
            options=available_queries,
            default=st.session_state.filter_queries
            if not st.session_state.filter_high_signal_only
            else [],
        )

    st.session_state.filter_status = st.sidebar.selectbox(
        "Status",
        ["Vše", "new", "seen", "applied", "rejected"],
        index=["Vše", "new", "seen", "applied", "rejected"].index(
            st.session_state.filter_status
        ),
    )

    st.session_state.filter_search = st.sidebar.text_input(
        "Hledat v názvu / firmě",
        value=st.session_state.filter_search,
    )

    st.session_state.filter_min_completeness = st.sidebar.slider(
        "Min. completeness %",
        0,
        100,
        st.session_state.filter_min_completeness,
        10,
    )


def build_where_clause() -> tuple[str, list]:
    """
    Build SQL WHERE fragment + params from current session_state.
    Returns (where_sql, params). where_sql never empty (at least '1=1').
    """
    clauses: list[str] = []
    params: list = []

    portals = st.session_state.get("filter_portals") or []
    if portals:
        clauses.append("portal = ANY(%s)")
        params.append(portals)

    queries = get_active_queries()
    if queries is not None:
        clauses.append("query_name = ANY(%s)")
        params.append(queries)

    status = st.session_state.get("filter_status")
    if status and status != "Vše":
        clauses.append("status = %s")
        params.append(status)

    search = (st.session_state.get("filter_search") or "").strip()
    if search:
        clauses.append("(title ILIKE %s OR company ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    date_from = get_date_from()
    clauses.append("first_seen >= %s")
    params.append(date_from)

    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params
