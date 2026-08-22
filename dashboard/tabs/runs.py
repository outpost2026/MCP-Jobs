"""Historie behu tab for MCP-Jobs dashboard."""

from __future__ import annotations

import streamlit as st


def render_runs_tab(run_query) -> None:
    """Render the Historie behu tab."""
    st.markdown("### Historie pipeline behu")
    df_runs = run_query(
        "SELECT id, profile, status, matched, raw, "
        "started_at, completed_at, metadata "
        "FROM pipeline_runs ORDER BY started_at DESC LIMIT 50"
    )
    if len(df_runs) > 0:
        df_display = df_runs.copy()
        df_display["new_ads"] = df_display["metadata"].apply(
            lambda x: x.get("new_ads", 0) if isinstance(x, dict) else 0
        )
        df_display["elapsed_s"] = df_display["metadata"].apply(
            lambda x: x.get("elapsed_seconds", 0) if isinstance(x, dict) else 0
        )
        st.dataframe(
            df_display[
                ["id", "profile", "status", "matched", "raw", "new_ads", "elapsed_s", "started_at"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("Run ID"),
                "profile": st.column_config.TextColumn("Profil"),
                "status": st.column_config.TextColumn("Status"),
                "matched": st.column_config.NumberColumn("Matched"),
                "raw": st.column_config.NumberColumn("Raw"),
                "new_ads": st.column_config.NumberColumn("Novych"),
                "elapsed_s": st.column_config.NumberColumn("Cas (s)"),
                "started_at": st.column_config.DatetimeColumn("Zacatek"),
            },
        )
    else:
        st.info("Zadne behy v historii.")
