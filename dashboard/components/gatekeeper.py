"""Pipeline health gatekeeper for MCP-Jobs dashboard."""

from __future__ import annotations

import streamlit as st


def render_gatekeeper(total_ads: int, last_run_status: str | None) -> None:
    """Render pipeline health gatekeeper."""
    if last_run_status == "completed" and total_ads > 10:
        st.markdown(
            """<div class="gatekeeper-ok"><h4 style="color: #10B981 !important; margin-top: 0;">
            Pipeline OK</h4><p style="color: #94A3B8; font-size: 14px;">
            Posledni beh uspesny, data aktualni.</p></div>""",
            unsafe_allow_html=True,
        )
    elif last_run_status == "completed" and total_ads <= 10:
        st.markdown(
            f"""<div class="gatekeeper-warn"><h4 style="color: #F59E0B !important; margin-top: 0;">
            Pipeline OK, ale malo dat ({total_ads} inzeratu)</h4><p style="color: #94A3B8; font-size: 14px;">
            Beh uspesny, ale vysledky chybi. Zkontroluj config.yaml nebo pridej query.</p></div>""",
            unsafe_allow_html=True,
        )
    elif last_run_status == "failed":
        st.markdown(
            """<div class="gatekeeper-critical"><h4 style="color: #F43F5E !important; margin-top: 0;">
            Pipeline FAILED</h4><p style="color: #94A3B8; font-size: 14px;">
            Posledni beh selhal. Zkontroluj logy.</p></div>""",
            unsafe_allow_html=True,
        )
    elif total_ads <= 10:
        st.markdown(
            f"""<div class="gatekeeper-warn"><h4 style="color: #F59E0B !important; margin-top: 0;">
            Malo dat ({total_ads} inzeratu)</h4><p style="color: #94A3B8; font-size: 14px;">
            Spust ETL pipeline pro naplneni DB.</p></div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """<div class="gatekeeper-warn"><h4 style="color: #F59E0B !important; margin-top: 0;">
            Zadny beh v historii</h4><p style="color: #94A3B8; font-size: 14px;">
            Spust pipeline poprve.</p></div>""",
            unsafe_allow_html=True,
        )
