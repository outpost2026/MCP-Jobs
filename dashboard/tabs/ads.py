"""Inzeraty tab for MCP-Jobs dashboard."""

from __future__ import annotations

import html as _html

import pandas as pd
import streamlit as st

from dashboard.components.gatekeeper import render_gatekeeper
from dashboard.components.kpi import render_kpi
from dashboard.metrics import fetch_ads


def render_ads_tab(conn, run_query, where_sql: str, where_params: list) -> None:
    """Render the Inzeraty tab."""
    # Use metrics.fetch_ads for completeness computation
    df_ads = fetch_ads(
        conn,
        where_sql=where_sql,
        params=where_params,
        min_completeness=st.session_state.get("filter_min_completeness", 0),
    )

    # Gatekeeper (cached -- only re-queries after status update)
    if "last_run_status" not in st.session_state:
        df_runs = run_query(
            "SELECT status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        )
        st.session_state.last_run_status = (
            df_runs.iloc[0]["status"] if len(df_runs) > 0 else None
        )
    last_status = st.session_state.last_run_status
    render_gatekeeper(len(df_ads), last_status)

    # New since last visit badge
    last_visit = st.session_state.get("last_visit")
    if last_visit and len(df_ads) > 0:
        new_since = df_ads[df_ads["first_seen"] > last_visit]
        if len(new_since) > 0:
            st.info(
                f"🆕 {len(new_since)} nových inzerátů od poslední návštěvy ({last_visit})"
            )

    # KPI
    render_kpi(df_ads)

    st.markdown("---")

    # Table
    if len(df_ads) > 0:
        # Status badge coloring
        _status_emoji = {
            "new": "\U0001f535",
            "seen": "\U0001f7e1",
            "applied": "\U0001f7e2",
            "rejected": "\U0001f534",
        }
        df_ads["status_badge"] = df_ads["status"].map(
            lambda s: f"{_status_emoji.get(s, '')} {s}" if s else ""
        )

        display_cols = [
            "id",
            "title",
            "url",
            "company",
            "location",
            "salary",
            "status_badge",
            "completeness_label",
            "first_seen",
            "portal",
            "query_name",
        ]
        st.dataframe(
            df_ads[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "title": st.column_config.TextColumn("Nazev", width="large"),
                "url": st.column_config.LinkColumn("Odkaz", display_text="\U0001f517"),
                "company": st.column_config.TextColumn("Firma"),
                "location": st.column_config.TextColumn("Lokace"),
                "salary": st.column_config.TextColumn("Mzda"),
                "status_badge": st.column_config.TextColumn("Status"),
                "completeness_label": st.column_config.TextColumn("Data %"),
                "first_seen": st.column_config.DateColumn("Prvni videni"),
                "portal": st.column_config.TextColumn("Portal"),
                "query_name": st.column_config.TextColumn("Query"),
            },
        )
    else:
        st.info("Zadne inzeraty pro vybrane filtry.")

    # Detail view
    if len(df_ads) > 0:
        st.markdown("---")
        st.markdown(
            "<p class='section-header'>Detail inzeratu</p>", unsafe_allow_html=True
        )
        detail_col1, detail_col2 = st.columns([1, 3])
        with detail_col1:
            detail_id = st.number_input(
                "Zadej ID pro detail", min_value=1, step=1, key="detail_id"
            )
        with detail_col2:
            st.write("")
            st.write("")
            show_detail = st.button("Zobrazit detail")
        if show_detail:
            df_detail = run_query("SELECT * FROM ads WHERE id = %s", (detail_id,))
            if len(df_detail) > 0:
                r = df_detail.iloc[0]
                st.markdown(f"### {r['title']}")
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(f"**Firma:** {r['company'] or '-'}")
                    st.markdown(f"**Lokace:** {r['location'] or '-'}")
                    st.markdown(f"**Portal:** {r['portal'] or '-'}")
                with m2:
                    st.markdown(f"**Mzda:** {r['salary'] or '-'}")
                    st.markdown(f"**Query:** {r['query_name'] or '-'}")
                    st.markdown(f"**Status:** {r['status'] or '-'}")
                with m3:
                    st.markdown(f"**Prvni videni:** {r['first_seen']}")
                    st.markdown(f"**Keyword:** {r['matched_keyword'] or '-'}")
                st.markdown("---")
                st.markdown("**Popis:**")
                st.markdown(
                    f"""<div class="detail-desc"><textarea
                    style="width:100%;height:300px;font-size:14px;color:#CBD5E1;
                    background:#1E293B;border:1px solid #334155;border-radius:8px;
                    padding:12px;resize:vertical;" disabled>{_html.escape(str(r["description"] or "Zadny popis."))}</textarea></div>""",
                    unsafe_allow_html=True,
                )
                st.markdown(f"[Otevrit na portale]({r['url']})")
            else:
                st.warning(f"Inzerat s ID {detail_id} nebyl nalezen.")

    # Bulk status update
    if len(df_ads) > 0:
        st.markdown("---")
        st.markdown(
            "<p class='section-header'>Zmena statusu (bulk)</p>", unsafe_allow_html=True
        )
        # Multi-select checkboxes
        selected_ids = st.multiselect(
            "Vyber inzeraty pro hromadnou zmenu",
            options=df_ads["id"].tolist(),
            format_func=lambda x: (
                f"#{x} - {df_ads[df_ads['id'] == x]['title'].values[0] if len(df_ads[df_ads['id'] == x]) > 0 else x}"
            ),
        )
        if selected_ids:
            b1, b2 = st.columns([3, 1])
            with b1:
                bulk_status = st.selectbox(
                    "Novy status", ["new", "seen", "applied", "rejected"]
                )
            with b2:
                st.write("")
                st.write("")
                if st.button(f"Aktualizovat {len(selected_ids)} inzeratu"):
                    placeholders = ",".join(["%s"] * len(selected_ids))
                    conn.execute(
                        f"UPDATE ads SET status = %s WHERE id IN ({placeholders})",
                        [bulk_status, *selected_ids],
                    )
                    st.cache_data.clear()
                    st.success(f"{len(selected_ids)} inzeratu -> {bulk_status}")
                    st.session_state.pop("last_run_status", None)
                    st.rerun()

        # Single status update
        st.markdown("**Nebo jednotlively:**")
        up_col1, up_col2, up_col3 = st.columns([2, 2, 1])
        with up_col1:
            update_id = st.number_input("ID inzeratu", min_value=1, step=1)
        with up_col2:
            new_status = st.selectbox(
                "Novy status",
                ["new", "seen", "applied", "rejected"],
                key="single_status",
            )
        with up_col3:
            st.write("")
            st.write("")
            if st.button("Aktualizovat"):
                conn.execute(
                    "UPDATE ads SET status = %s WHERE id = %s", (new_status, update_id)
                )
                st.cache_data.clear()
                st.success(f"Inzerat #{update_id} -> {new_status}")
                st.session_state.pop("last_run_status", None)
                st.rerun()

    # Download
    st.markdown("---")
    st.markdown("<div class='download-section'>", unsafe_allow_html=True)
    st.markdown("<p class='section-header'>Stahnout data</p>", unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        csv_data = df_ads.to_csv(index=False).encode("utf-8")
        st.download_button(
            "CSV export", data=csv_data, file_name="mcpjobs_ads.csv", mime="text/csv"
        )
    with d2:
        json_data = df_ads.to_json(
            orient="records", force_ascii=False, indent=2
        ).encode("utf-8")
        st.download_button(
            "JSON export",
            data=json_data,
            file_name="mcpjobs_ads.json",
            mime="application/json",
        )
    with d3:
        md_lines = ["# MCP-Jobs Report\n"]
        md_lines.append(f"**Celkem inzeratu:** {len(df_ads)}\n")
        md_lines.append(f"**Portalu:** {df_ads['portal'].nunique()}\n")
        md_lines.append(f"**Firem:** {df_ads['company'].nunique()}\n\n")
        md_lines.append("## Inzeraty\n\n")
        for _, row in df_ads.head(50).iterrows():
            md_lines.append(
                f"- **{row['title']}** - {row['company']}, {row['location']}"
            )
            if pd.notna(row["salary"]):
                md_lines.append(f"  - Mzda: {row['salary']}")
            md_lines.append("")
        st.download_button(
            "Markdown report",
            data="".join(md_lines).encode("utf-8"),
            file_name="mcpjobs_report.md",
            mime="text/markdown",
        )
    st.markdown("</div>", unsafe_allow_html=True)
