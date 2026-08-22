"""MCP-Jobs Dashboard — Streamlit frontend for job listing analytics.

Pandas-powered: proper DataFrames, groupby, time series, merge.
Adapted from vcf_integrace/app.py patterns (dark theme, KPI cards, gatekeeper).

Usage:
    streamlit run dashboard.py
"""

from __future__ import annotations

import html as _html
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# -- Encoding safety (Windows cp1250) --
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from dashboard.filters import (
    HIGH_SIGNAL_QUERIES,
    build_where_clause,
    get_active_queries,
    init_filter_state,
    render_sidebar_filters,
)
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
from mcp_jobs.db import connect, get_database_url, init_db

# ─── Authentication ──────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("MCP-Jobs Dashboard")
    pwd = st.text_input("Pristupove heslo", type="password")
    if st.button("Pristoupit"):
        if pwd == os.environ.get("MCPJOBS_DASH_PWD", "mcpjobs-demo-2026"):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Nespravne heslo")
    st.stop()

# ── Filter state ──────────────────────────────────────────────────────────────
init_filter_state()

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCP-Jobs Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Dark theme CSS (loaded from theme.css) ────────────────────────────────
_theme_css = (_REPO_ROOT / "dashboard" / "theme.css").read_text(encoding="utf-8")
st.markdown(f"<style>{_theme_css}</style>", unsafe_allow_html=True)

st.markdown(
    "<h1 style='text-align: center; margin-bottom: 5px;'>MCP-Jobs Dashboard</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #94A3B8; font-size: 16px; "
    "margin-bottom: 10px;'>CZ job portal analytics | EROI-scored listings</p>",
    unsafe_allow_html=True,
)

# ─── DB connection ────────────────────────────────────────────────────────────
DB_URL = get_database_url()
if not DB_URL:
    st.error("DATABASE_URL neni nastaven. Uprav .env soubor.")
    st.stop()

try:
    conn = connect(DB_URL)
    init_db(conn)
except Exception as e:
    st.error(f"Chyba pripojeni k DB: {e}")
    st.stop()


# ─── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Cached SQL -> DataFrame. Invalidate via st.cache_data.clear() after writes."""
    return pd.read_sql(sql, conn, params=params)


# ── Available dimension values for multiselects ──────────────────────────────
_portals = run_query(
    "SELECT DISTINCT portal FROM ads WHERE portal IS NOT NULL ORDER BY portal"
)["portal"].tolist()
_queries = run_query(
    "SELECT DISTINCT query_name FROM ads WHERE query_name IS NOT NULL ORDER BY query_name"
)["query_name"].tolist()

render_sidebar_filters(_portals, _queries)

# Shared WHERE for all tabs
where_sql, where_params = build_where_clause()
active_queries = get_active_queries()


# ─── KPI metrics ──────────────────────────────────────────────────────────────
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


# ─── Gatekeeper: pipeline health ──────────────────────────────────────────────
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


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_ads, tab_analysis, tab_runs = st.tabs(["Inzeraty", "Analyza", "Historie behu"])

# ─── TAB: Inzeraty ────────────────────────────────────────────────────────────
with tab_ads:
    # Shared filters from sidebar (filters.py)
    sql = f"SELECT * FROM ads WHERE {where_sql} ORDER BY first_seen DESC, title"
    df_ads = run_query(sql, tuple(where_params))

    # Gatekeeper (cached — only re-queries after status update)
    if "last_run_status" not in st.session_state:
        df_runs = run_query(
            "SELECT status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        )
        st.session_state.last_run_status = (
            df_runs.iloc[0]["status"] if len(df_runs) > 0 else None
        )
    last_status = st.session_state.last_run_status
    render_gatekeeper(len(df_ads), last_status)

    # KPI
    render_kpi(df_ads)

    st.markdown("---")

    # Table
    if len(df_ads) > 0:
        df_ads["desc_preview"] = df_ads["description"].fillna("").str[:80]
        has_title = df_ads["title"].notna()
        has_company = df_ads["company"].notna() & (df_ads["company"] != "")
        has_location = df_ads["location"].notna() & (df_ads["location"] != "")
        has_salary = df_ads["salary"].notna() & (df_ads["salary"] != "")
        has_desc = df_ads["description"].fillna("").str.len() > 50
        has_keyword = df_ads["matched_keyword"].notna()
        df_ads["completeness"] = (
            (
                has_title.astype(int)
                + has_company.astype(int)
                + has_location.astype(int)
                + has_salary.astype(int)
                + has_desc.astype(int)
                + has_keyword.astype(int)
            )
            * 100
            // 6
        )
        df_ads["completeness_label"] = df_ads["completeness"].apply(lambda x: f"{x}%")
        display_cols = [
            "id",
            "title",
            "url",
            "company",
            "location",
            "salary",
            "status",
            "completeness_label",
            "first_seen",
            "desc_preview",
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
                "url": st.column_config.LinkColumn("Odkaz", display_text="url"),
                "company": st.column_config.TextColumn("Firma"),
                "location": st.column_config.TextColumn("Lokace"),
                "salary": st.column_config.TextColumn("Mzda"),
                "status": st.column_config.TextColumn("Status"),
                "completeness_label": st.column_config.TextColumn("Data %"),
                "first_seen": st.column_config.DateColumn("Prvni videni"),
                "desc_preview": st.column_config.TextColumn("Popis"),
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

    # Status update
    if len(df_ads) > 0:
        st.markdown("---")
        st.markdown(
            "<p class='section-header'>Zmena statusu</p>", unsafe_allow_html=True
        )
        up_col1, up_col2, up_col3 = st.columns([2, 2, 1])
        with up_col1:
            update_id = st.number_input("ID inzeratu", min_value=1, step=1)
        with up_col2:
            new_status = st.selectbox(
                "Novy status", ["new", "seen", "applied", "rejected"]
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

# ─── TAB: Historie behu ───────────────────────────────────────────────────────
with tab_runs:
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
                [
                    "id",
                    "profile",
                    "status",
                    "matched",
                    "raw",
                    "new_ads",
                    "elapsed_s",
                    "started_at",
                ]
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


# === TAB: Analyza ===
with tab_analysis:
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

