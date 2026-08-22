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

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCP-Jobs Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Dark theme CSS (adapted from vcf_integrace) ─────────────────────────────
st.markdown(
    """
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    h1, h2, h3, h4 { font-family: 'Inter', -apple-system, sans-serif !important;
                       font-weight: 700 !important; color: #F8FAFC !important; }
    .metric-card {
        background-color: #1E293B; border: 1px solid #334155;
        border-radius: 12px; padding: 24px; text-align: center;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .metric-value { font-size: 32px; font-weight: 800; color: #10B981; }
    .metric-label { font-size: 14px; color: #94A3B8; text-transform: uppercase;
                    letter-spacing: 0.05em; }
    .gatekeeper-ok {
        background-color: #064E3B; border-left: 6px solid #10B981;
        border-radius: 8px; padding: 20px; margin-bottom: 20px;
    }
    .gatekeeper-warn {
        background-color: #1E2030; border-left: 6px solid #F59E0B;
        border-radius: 8px; padding: 20px; margin-bottom: 20px;
    }
    .gatekeeper-critical {
        background-color: #1E2030; border-left: 6px solid #F43F5E;
        border-radius: 8px; padding: 20px; margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { color: #94A3B8; font-weight: 600; }
    .stTabs [aria-selected="true"] { color: #10B981 !important; }
    .stButton > button {
        background-color: #10B981; color: #0F172A; font-weight: 700;
        border: none; border-radius: 8px;
    }
    .stButton > button:hover { background-color: #059669; }
    .section-header {
        font-size: 14px; font-weight: 700; color: #94A3B8;
        margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .detail-desc textarea {
        font-size: 14px !important;
        color: #CBD5E1 !important;
    }
    .download-section {
        margin-top: 24px; padding: 16px; background: #111827;
        border-radius: 10px; border: 1px solid #1E293B;
    }
</style>
""",
    unsafe_allow_html=True,
)

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
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute SQL, return DataFrame."""
    return pd.read_sql(sql, conn, params=params)


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
    # Filters
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        portals = run_query(
            "SELECT DISTINCT portal FROM ads WHERE portal IS NOT NULL ORDER BY portal"
        )["portal"].tolist()
        portal_filter = st.selectbox("Portal", ["Vse", *portals])
    with f2:
        queries = run_query(
            "SELECT DISTINCT query_name FROM ads WHERE query_name IS NOT NULL ORDER BY query_name"
        )["query_name"].tolist()
        query_filter = st.selectbox("Query", ["Vse", *queries])
    with f3:
        status_filter = st.selectbox(
            "Status", ["Vse", "new", "seen", "applied", "rejected"]
        )
    with f4:
        search = st.text_input("Hledat v nazvu/firme")

    # Build query
    where_clauses = []
    params: list = []
    if portal_filter != "Vse":
        where_clauses.append("portal = %s")
        params.append(portal_filter)
    if query_filter != "Vse":
        where_clauses.append("query_name = %s")
        params.append(query_filter)
    if status_filter != "Vse":
        where_clauses.append("status = %s")
        params.append(status_filter)
    if search:
        where_clauses.append("(title ILIKE %s OR company ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    sql = f"SELECT * FROM ads WHERE {where_sql} ORDER BY first_seen DESC, title"
    df_ads = run_query(sql, tuple(params))

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

# ─── TAB: Analyza ─────────────────────────────────────────────────────────────
with tab_analysis:
    st.markdown("### Analyza trhu a datove kvality")

    # ── Portal Quality ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Portal Quality Score</p>",
        unsafe_allow_html=True,
    )
    df_portal_quality = run_query(
        "SELECT portal, "
        "COUNT(*) AS total_ads, "
        "COUNT(DISTINCT company) AS unique_companies, "
        "ROUND(100.0 * COUNT(CASE WHEN salary IS NOT NULL AND salary != '' THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS salary_pct, "
        "ROUND(100.0 * COUNT(CASE WHEN description IS NOT NULL AND length(description) > 50 THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS desc_pct, "
        "ROUND((COUNT(CASE WHEN salary IS NOT NULL AND salary != '' THEN 1 END) + "
        "COUNT(CASE WHEN description IS NOT NULL AND length(description) > 50 THEN 1 END)) "
        "* 100.0 / (2 * NULLIF(COUNT(*), 0)), 1) AS quality_score "
        "FROM ads GROUP BY portal ORDER BY quality_score DESC"
    )
    if len(df_portal_quality) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                df_portal_quality,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "portal": st.column_config.TextColumn("Portal"),
                    "total_ads": st.column_config.NumberColumn("Inzeratu"),
                    "unique_companies": st.column_config.NumberColumn("Firem"),
                    "salary_pct": st.column_config.NumberColumn("Mzda %"),
                    "desc_pct": st.column_config.NumberColumn("Popis %"),
                    "quality_score": st.column_config.NumberColumn("Quality Score"),
                },
            )
        with col2:
            st.bar_chart(
                df_portal_quality.set_index("portal")[["salary_pct", "desc_pct"]]
            )
    else:
        st.info("Zadna data pro analyzu portalu.")

    # ── Cross-Portal Duplicates (true overlap signal) ────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Cross-Portal Overlap (same job on multiple portals)</p>",
        unsafe_allow_html=True,
    )
    df_overlap = run_query(
        "SELECT title, company, "
        "ARRAY_AGG(DISTINCT portal) AS portals, "
        "ARRAY_AGG(DISTINCT query_name) AS matched_queries, "
        "COUNT(DISTINCT portal) AS portal_count "
        "FROM ads "
        "GROUP BY title, company "
        "HAVING COUNT(DISTINCT portal) > 1 "
        "ORDER BY portal_count DESC LIMIT 20"
    )
    if len(df_overlap) > 0:
        st.metric("Prazdnich inzeratu napric portaly", len(df_overlap))
        st.dataframe(
            df_overlap,
            use_container_width=True,
            hide_index=True,
            column_config={
                "title": st.column_config.TextColumn("Nazev"),
                "company": st.column_config.TextColumn("Firma"),
                "portals": st.column_config.TextColumn("Portaly"),
                "matched_queries": st.column_config.TextColumn("Query"),
                "portal_count": st.column_config.NumberColumn("Pocet portalu"),
            },
        )
    else:
        st.info("Zadne duplicity napric portaly.")

    # ── Salary Distribution ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Salary Analysis</p>",
        unsafe_allow_html=True,
    )
    df_salary = run_query(
        "WITH salary_parts AS ("
        "  SELECT portal, query_name, salary,"
        "    REGEXP_SPLIT_TO_ARRAY(salary, '[-\u2013]') AS parts"
        "  FROM ads WHERE salary IS NOT NULL AND salary ~ '\\d'"
        "), salary_parsed AS ("
        "  SELECT portal, query_name, salary,"
        "    REGEXP_REPLACE(parts[1], '[^0-9]', '', 'g') AS num1,"
        "    CASE WHEN array_length(parts, 1) > 1"
        "      THEN REGEXP_REPLACE(parts[2], '[^0-9]', '', 'g')"
        "      ELSE '' END AS num2"
        "  FROM salary_parts WHERE REGEXP_REPLACE(parts[1], '[^0-9]', '', 'g') != ''"
        ")"
        "SELECT portal, query_name,"
        "  COUNT(*) AS ads_with_salary,"
        "  ROUND(AVG(CASE WHEN num2 != '' THEN (CAST(num1 AS NUMERIC) + CAST(num2 AS NUMERIC)) / 2"
        "                  ELSE CAST(num1 AS NUMERIC) END), 0) AS avg_salary,"
        "  MIN(CAST(num1 AS NUMERIC)) AS min_salary,"
        "  MAX(CASE WHEN num2 != '' THEN CAST(num2 AS NUMERIC) ELSE CAST(num1 AS NUMERIC) END) AS max_salary"
        " FROM salary_parsed GROUP BY portal, query_name ORDER BY avg_salary DESC"
    )
    if len(df_salary) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                df_salary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "portal": st.column_config.TextColumn("Portal"),
                    "query_name": st.column_config.TextColumn("Query"),
                    "ads_with_salary": st.column_config.NumberColumn("Pocet"),
                    "avg_salary": st.column_config.NumberColumn("Avg Kc"),
                    "min_salary": st.column_config.NumberColumn("Min Kc"),
                    "max_salary": st.column_config.NumberColumn("Max Kc"),
                },
            )
        with col2:
            df_salary_chart = (
                df_salary.groupby("portal")
                .apply(
                    lambda g: pd.Series(
                        {
                            "avg_salary": round(
                                (g["avg_salary"] * g["ads_with_salary"]).sum()
                                / g["ads_with_salary"].sum(),
                                0,
                            ),
                            "ads": g["ads_with_salary"].sum(),
                        }
                    )
                )
                .reset_index()
            )
            st.bar_chart(df_salary_chart.set_index("portal")["avg_salary"])
    else:
        st.info("Zadna data o mzdach k analyze.")

    # ── Freshness Analysis ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Freshness (casova analyza)</p>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Poznamka: 'Jen 1 den' znamena inzerat nalezen jen pri jednom behu pipeline. Zavisi na frekvenci behu."
    )
    df_freshness = run_query(
        "SELECT first_seen, "
        "COUNT(*) AS new_ads, "
        "COUNT(CASE WHEN last_seen > first_seen THEN 1 END) AS still_live, "
        "COUNT(CASE WHEN last_seen = first_seen THEN 1 END) AS one_day_only, "
        "ROUND(100.0 * COUNT(CASE WHEN last_seen = first_seen THEN 1 END) / "
        "NULLIF(COUNT(*), 0), 1) AS churn_pct "
        "FROM ads WHERE first_seen IS NOT NULL "
        "GROUP BY first_seen ORDER BY first_seen DESC"
    )
    if len(df_freshness) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                df_freshness.head(15),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "first_seen": st.column_config.DateColumn("Datum"),
                    "new_ads": st.column_config.NumberColumn("Novych"),
                    "still_live": st.column_config.NumberColumn("Zije"),
                    "one_day_only": st.column_config.NumberColumn("1 den"),
                    "churn_pct": st.column_config.NumberColumn("Churn %"),
                },
            )
        with col2:
            df_freshness_chart = df_freshness.set_index("first_seen")[
                ["new_ads", "still_live"]
            ]
            st.line_chart(df_freshness_chart)
    else:
        st.info("Zadna data pro freshness analyzu.")

    # ── Status Funnel ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Status Funnel</p>",
        unsafe_allow_html=True,
    )
    df_funnel = run_query(
        "SELECT COALESCE(status, '(bez statusu)') AS status, COUNT(*) AS count, "
        "ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ads), 1) AS pct "
        "FROM ads GROUP BY status "
        "ORDER BY CASE status "
        "WHEN 'new' THEN 1 WHEN 'seen' THEN 2 "
        "WHEN 'applied' THEN 3 WHEN 'rejected' THEN 4 ELSE 5 END"
    )
    if len(df_funnel) > 0:
        cols = st.columns(len(df_funnel))
        for i, (_, row) in enumerate(df_funnel.iterrows()):
            with cols[i]:
                st.metric(
                    label=row["status"],
                    value=row["count"],
                    help=f"{row['pct']}% of all ads",
                )
    else:
        st.info("Zadne data pro funnel.")

    # ── Query Efficiency ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Query Efficiency (ktere dotazy jsou produktivni)</p>",
        unsafe_allow_html=True,
    )
    df_query_eff = run_query(
        "SELECT query_name,"
        "  COUNT(*) AS total_ads,"
        "  COUNT(DISTINCT portal) AS portals,"
        "  COUNT(DISTINCT company) AS companies,"
        "  ROUND(100.0 * COUNT(CASE WHEN salary IS NOT NULL AND salary != '' THEN 1 END) / COUNT(*), 1) AS salary_pct,"
        "  ROUND(AVG(LENGTH(description)), 0) AS avg_desc_len"
        " FROM ads WHERE query_name IS NOT NULL"
        " GROUP BY query_name ORDER BY total_ads DESC"
    )
    if len(df_query_eff) > 0:
        st.dataframe(
            df_query_eff,
            use_container_width=True,
            hide_index=True,
            column_config={
                "query_name": st.column_config.TextColumn("Query"),
                "total_ads": st.column_config.NumberColumn("Inzeratu"),
                "portals": st.column_config.NumberColumn("Portalu"),
                "companies": st.column_config.NumberColumn("Firem"),
                "salary_pct": st.column_config.NumberColumn("Mzda %"),
                "avg_desc_len": st.column_config.NumberColumn("Avg popis (znaky)"),
            },
        )
    else:
        st.info("Zadna data pro query effektivitu.")

    # ── Location Analysis ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Location Analysis (top lokace)</p>",
        unsafe_allow_html=True,
    )
    df_locations = run_query(
        "SELECT location, COUNT(*) AS ads,"
        "  COUNT(DISTINCT company) AS companies,"
        "  COUNT(DISTINCT portal) AS portals"
        " FROM ads WHERE location IS NOT NULL AND location != ''"
        " GROUP BY location ORDER BY ads DESC LIMIT 15"
    )
    if len(df_locations) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                df_locations,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "location": st.column_config.TextColumn("Lokace"),
                    "ads": st.column_config.NumberColumn("Inzeratu"),
                    "companies": st.column_config.NumberColumn("Firem"),
                    "portals": st.column_config.NumberColumn("Portalu"),
                },
            )
        with col2:
            st.bar_chart(df_locations.set_index("location")["ads"])
    else:
        st.info("Zadna data o lokacich.")

    # ── Company Frequency ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Company Frequency (top firmy)</p>",
        unsafe_allow_html=True,
    )
    df_companies = run_query(
        "SELECT company, COUNT(*) AS ads,"
        "  ARRAY_AGG(DISTINCT portal) AS portals,"
        "  ARRAY_AGG(DISTINCT query_name) AS queries"
        " FROM ads WHERE company IS NOT NULL AND company != ''"
        " GROUP BY company ORDER BY ads DESC LIMIT 15"
    )
    if len(df_companies) > 0:
        st.dataframe(
            df_companies,
            use_container_width=True,
            hide_index=True,
            column_config={
                "company": st.column_config.TextColumn("Firma"),
                "ads": st.column_config.NumberColumn("Inzeratu"),
                "portals": st.column_config.TextColumn("Portaly"),
                "queries": st.column_config.TextColumn("Query"),
            },
        )
    else:
        st.info("Zadna data o firmach.")

    # ── Portal x Query Matrix ───────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<p class='section-header'>Portal x Query Matrix (kdo co pokryva)</p>",
        unsafe_allow_html=True,
    )
    df_matrix = run_query(
        "SELECT portal, query_name, COUNT(*) AS ads"
        " FROM ads WHERE query_name IS NOT NULL"
        " GROUP BY portal, query_name ORDER BY portal, ads DESC"
    )
    if len(df_matrix) > 0:
        df_pivot = df_matrix.pivot_table(
            index="portal", columns="query_name", values="ads", fill_value=0
        )
        st.dataframe(
            df_pivot,
            use_container_width=True,
        )
    else:
        st.info("Zadna data pro matrix.")
