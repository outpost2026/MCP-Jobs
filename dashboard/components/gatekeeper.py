"""Pipeline health gatekeeper for MCP-Jobs dashboard."""

from __future__ import annotations

import streamlit as st


def render_gatekeeper(total_ads: int, last_run_status: str | None) -> None:
    """Render pipeline health gatekeeper — compact production style."""
    if last_run_status == "completed" and total_ads > 10:
        st.markdown(
            """<div class="gatekeeper-ok"><span style="font-size: 13px; font-weight: 600; color: #10B981;">
            Pipeline OK</span> <span style="font-size: 12px; color: #64748B;">
            — data aktualni</span></div>""",
            unsafe_allow_html=True,
        )
    elif last_run_status == "completed" and total_ads <= 10:
        st.markdown(
            f"""<div class="gatekeeper-warn"><span style="font-size: 13px; font-weight: 600; color: #F59E0B;">
            Pipeline OK, malo dat ({total_ads})</span> <span style="font-size: 12px; color: #64748B;">
            — zkontroluj config</span></div>""",
            unsafe_allow_html=True,
        )
    elif last_run_status == "failed":
        st.markdown(
            """<div class="gatekeeper-critical"><span style="font-size: 13px; font-weight: 600; color: #F43F5E;">
            Pipeline FAILED</span> <span style="font-size: 12px; color: #64748B;">
            — zkontroluj logy</span></div>""",
            unsafe_allow_html=True,
        )
    elif total_ads <= 10:
        st.markdown(
            f"""<div class="gatekeeper-warn"><span style="font-size: 13px; font-weight: 600; color: #F59E0B;">
            Malo dat ({total_ads})</span> <span style="font-size: 12px; color: #64748B;">
            — spust ETL</span></div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """<div class="gatekeeper-warn"><span style="font-size: 13px; font-weight: 600; color: #F59E0B;">
            Zadny beh v historii</span> <span style="font-size: 12px; color: #64748B;">
            — spust pipeline</span></div>""",
            unsafe_allow_html=True,
        )
