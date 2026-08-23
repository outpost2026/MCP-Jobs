"""Inzeraty tab for MCP-Jobs dashboard (v2 layout -- table-first)."""

from __future__ import annotations

import html as _html

import pandas as pd
import streamlit as st

from dashboard.components.kpi import render_kpi
from dashboard.metrics import fetch_ads

_STATUS_EMOJI = {
    "new": "\U0001f535",
    "seen": "\U0001f7e1",
    "hot": "\U0001f525",
    "applied": "\U0001f7e2",
    "rejected": "\U0001f534",
}


def _render_detail(r: pd.Series) -> None:
    """Render single ad detail inline (tags after header, before description)."""
    import json as _json

    # H3 title as hyperlink
    url = r.get("url", "#")
    title = _html.escape(str(r["title"]))
    st.markdown(
        f"<h3 style='margin-bottom:4px;'><a href='{url}' target='_blank' "
        f"style='color:#E2E8F0;text-decoration:none;'>{title}</a></h3>",
        unsafe_allow_html=True,
    )

    # IT Stack tags -- immediately after header for quick orientation
    skills = None
    skills_raw = r.get("skills")
    if skills_raw and skills_raw != "[]" and skills_raw is not None:
        if isinstance(skills_raw, str):
            skills = _json.loads(skills_raw)
        elif isinstance(skills_raw, dict):
            skills = skills_raw
    if skills and skills.get("matches"):
        tags_html = " ".join(
            f'<span style="background:#1e40af;color:#fff;'
            f"padding:3px 12px;border-radius:6px;font-size:18px;"
            f'margin:3px;">{m["skill_id"]}</span>'
            for m in skills["matches"][:12]
        )
        st.markdown(tags_html, unsafe_allow_html=True)

    # Metadata columns
    score_val = skills.get("score", 0) if skills else 0
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
        st.markdown(f"**Datum:** {r['first_seen']}")
        st.markdown(f"**Keyword:** {r['matched_keyword'] or '-'}")
        st.markdown(f"**Tech Score:** {score_val:.1f}")
    st.markdown("---")

    # Description
    st.markdown("**Popis:**")
    st.markdown(
        f"""<div class="detail-desc"><textarea
        style="width:100%;height:300px;font-size:14px;color:#CBD5E1;
        background:#1E293B;border:1px solid #334155;border-radius:8px;
        padding:12px;resize:vertical;" disabled>{_html.escape(str(r["description"] or "Zadny popis."))}</textarea></div>""",
        unsafe_allow_html=True,
    )

    # Skills metrics
    if skills and skills.get("matches"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tech Score", f"{skills.get('score', 0):.1f}")
        c2.metric("Coverage", f"{skills.get('coverage', 0):.1%}")
        domain = skills.get("domain", {})
        c3.metric("Domain Score", f"{domain.get('score', 0):.0f}")
        c4.metric("Employer Tier", skills.get("employer_tier", "-"))


def render_ads_tab(conn, run_query, where_sql: str, where_params: list) -> None:
    """Render the Inzeraty tab (v2 -- table-first layout)."""
    df_ads = fetch_ads(
        conn,
        where_sql=where_sql,
        params=where_params,
        min_completeness=st.session_state.get("filter_min_completeness", 0),
    )

    # New since last visit badge
    last_visit = st.session_state.get("last_visit")
    if last_visit and len(df_ads) > 0:
        new_since = df_ads[df_ads["first_seen"] > last_visit]
        if len(new_since) > 0:
            st.info(
                f"{len(new_since)} novych inzeratu od posledni navstevy ({last_visit})"
            )

    # KPI row
    render_kpi(df_ads)

    st.markdown("---")

    # === TABLE (top priority -- user sees this first) ===
    if len(df_ads) == 0:
        st.info("Zadne inzeraty pro vybrane filtry.")
        return

    df_ads["status_badge"] = df_ads["status"].map(
        lambda s: f"{_STATUS_EMOJI.get(s, '')} {s}" if s else ""
    )

    display_cols = [
        "id",
        "title",
        "company",
        "location",
        "salary",
        "status_badge",
        "tech_score",
        "first_seen",
        "portal",
        "query_name",
    ]

    # Row selection via on_select (Streamlit 1.33+)
    event = st.dataframe(
        df_ads[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "title": st.column_config.TextColumn("Nazev", width="large"),
            "company": st.column_config.TextColumn("Firma"),
            "location": st.column_config.TextColumn("Lokace"),
            "salary": st.column_config.TextColumn("Mzda"),
            "status_badge": st.column_config.TextColumn("Status"),
            "tech_score": st.column_config.NumberColumn(
                "Score", format="%.1f", width="small"
            ),
            "first_seen": st.column_config.DateColumn("Datum"),
            "portal": st.column_config.TextColumn("Portal"),
            "query_name": st.column_config.TextColumn("Query"),
        },
    )

    # Get selected row IDs from selection
    selected_indices = event.selection.rows if event and event.selection else []
    selected_ids = (
        df_ads.iloc[selected_indices]["id"].tolist() if selected_indices else []
    )

    # === QUICK ACTIONS (below table -- detail + status) ===
    if selected_ids:
        st.markdown("---")

        # Single row selected -> show detail + status change
        if len(selected_ids) == 1:
            sel_id = selected_ids[0]
            df_detail = run_query("SELECT * FROM ads WHERE id = %s", (sel_id,))
            if len(df_detail) > 0:
                r = df_detail.iloc[0]

                # Status change inline
                sc1, sc2, sc3 = st.columns([2, 2, 1])
                with sc1:
                    st.markdown(f"**#{sel_id} -- {r['title'][:50]}**")
                with sc2:
                    new_status = st.selectbox(
                        "Zmenit status",
                        ["new", "seen", "hot", "applied", "rejected"],
                        index=["new", "seen", "hot", "applied", "rejected"].index(
                            r["status"] or "new"
                        ),
                        key=f"status_{sel_id}",
                        label_visibility="collapsed",
                    )
                with sc3:
                    if st.button("Ulozit", key=f"save_{sel_id}"):
                        conn.execute(
                            "UPDATE ads SET status = %s WHERE id = %s",
                            (new_status, sel_id),
                        )
                        st.cache_data.clear()
                        st.success(f"#{sel_id} -> {new_status}")
                        st.rerun()

                st.markdown("---")
                _render_detail(r)

        # Multiple rows selected -> bulk status change
        elif len(selected_ids) > 1:
            st.markdown(f"**Vybrano: {len(selected_ids)} inzeratu**")
            bc1, bc2, bc3 = st.columns([3, 2, 1])
            with bc1:
                bulk_status = st.selectbox(
                    "Novy status", ["new", "seen", "hot", "applied", "rejected"]
                )
            with bc2:
                st.write("")
                st.write("")
                id_list = ", ".join(str(i) for i in selected_ids[:10])
                suffix = (
                    f" (+{len(selected_ids) - 10}...)" if len(selected_ids) > 10 else ""
                )
                st.caption(f"ID: {id_list}{suffix}")
            with bc3:
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
                    st.rerun()

    # === DOWNLOAD (bottom) ===
    st.markdown("---")
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
