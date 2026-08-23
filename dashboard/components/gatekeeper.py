"""Pipeline health gatekeeper for MCP-Jobs dashboard."""

from __future__ import annotations

import streamlit as st


def render_gatekeeper(total_ads: int, last_run_status: str | None) -> None:
    """Render pipeline health gatekeeper -- compact sidebar style."""
    if last_run_status == "completed" and total_ads > 10:
        st.sidebar.success("Pipeline OK", icon=":material/check_circle:")
    elif last_run_status == "completed" and total_ads <= 10:
        st.sidebar.warning(f"Pipeline OK, malo dat ({total_ads})")
    elif last_run_status == "failed":
        st.sidebar.error("Pipeline FAILED", icon=":material/error:")
    elif total_ads <= 10:
        st.sidebar.warning(f"Malo dat ({total_ads}) -- spust ETL")
    else:
        st.sidebar.warning("Zadny beh -- spust pipeline")
