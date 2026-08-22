"""Query catalog + pure transforms for MCP-Jobs dashboard analytics.

All functions accept an open psycopg connection and optional filter params.
They return pandas DataFrames and contain zero Streamlit calls -> unit-testable.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

# -- Low-level helper -----------------------------------------------------------

def _read(conn, sql: str, params: tuple | list | None = None) -> pd.DataFrame:
    return pd.read_sql(sql, conn, params=params or ())


# -- Core listing query ---------------------------------------------------------

def fetch_ads(
    conn,
    where_sql: str = "1=1",
    params: Sequence = (),
    min_completeness: int = 0,
) -> pd.DataFrame:
    """Filtered ads with computed completeness."""
    sql = f"""
        SELECT
            id, title, url, company, location, salary, status,
            first_seen, description, portal, query_name, matched_keyword
        FROM ads
        WHERE {where_sql}
        ORDER BY first_seen DESC, title
    """
    df = _read(conn, sql, list(params))
    if df.empty:
        return df

    df["desc_preview"] = df["description"].fillna("").str[:80]
    has_title = df["title"].notna()
    has_company = df["company"].notna() & (df["company"] != "")
    has_location = df["location"].notna() & (df["location"] != "")
    has_salary = df["salary"].notna() & (df["salary"] != "")
    has_desc = df["description"].fillna("").str.len() > 50
    has_kw = df["matched_keyword"].notna()
    df["completeness"] = (
        has_title.astype(int)
        + has_company.astype(int)
        + has_location.astype(int)
        + has_salary.astype(int)
        + has_desc.astype(int)
        + has_kw.astype(int)
    ) * 100 // 6
    df["completeness_label"] = df["completeness"].apply(lambda x: f"{x}%")

    if min_completeness > 0:
        df = df[df["completeness"] >= min_completeness]
    return df


# -- High-SNR analytical queries ------------------------------------------------

def velocity(
    conn,
    queries: list[str] | None,
    days: int = 14,
) -> pd.DataFrame:
    """Daily new-ad counts for high-signal queries (last N days)."""
    sql = """
        SELECT
            first_seen::date AS day,
            query_name,
            COUNT(*) AS new_ads,
            COUNT(*) FILTER (
                WHERE salary IS NOT NULL AND salary != ''
            ) AS with_salary
        FROM ads
        WHERE first_seen >= CURRENT_DATE - (%s || ' days')::interval
          AND (%s::text[] IS NULL OR query_name = ANY(%s))
        GROUP BY 1, 2
        ORDER BY 1 DESC, 3 DESC
    """
    return _read(conn, sql, (days, queries, queries))


def salary_by_domain(
    conn,
    queries: list[str] | None,
) -> pd.DataFrame:
    """Median / avg / coverage of parsed salaries per query_name."""
    sql = """
        WITH parsed AS (
            SELECT
                query_name,
                portal,
                CASE
                    WHEN salary ~ '(\\d[\\d\\s\u00a0]{2,})'
                    THEN CAST(
                        REGEXP_REPLACE(
                            (REGEXP_MATCH(salary, '(\\d[\\d\\s\u00a0]{2,})'))[1],
                            '[^0-9]', '', 'g'
                        ) AS numeric
                    )
                    ELSE NULL
                END AS salary_num
            FROM ads
            WHERE (%s::text[] IS NULL OR query_name = ANY(%s))
        )
        SELECT
            query_name,
            COUNT(*) AS total,
            COUNT(salary_num) AS with_salary,
            ROUND(100.0 * COUNT(salary_num) / NULLIF(COUNT(*), 0), 1) AS coverage_pct,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_num)) AS median,
            ROUND(AVG(salary_num)) AS avg,
            MIN(salary_num) AS min,
            MAX(salary_num) AS max
        FROM parsed
        GROUP BY query_name
        ORDER BY median DESC NULLS LAST
    """
    return _read(conn, sql, (queries, queries))


def company_signal(
    conn,
    queries: list[str] | None,
    min_ads: int = 2,
) -> pd.DataFrame:
    """Companies posting repeatedly / across multiple query domains."""
    sql = """
        SELECT
            company,
            COUNT(*) AS ads,
            COUNT(DISTINCT query_name) AS query_diversity,
            COUNT(DISTINCT portal) AS portal_reach,
            ARRAY_AGG(DISTINCT query_name ORDER BY query_name) AS queries,
            MAX(first_seen) AS last_seen,
            MIN(first_seen) AS first_seen
        FROM ads
        WHERE company IS NOT NULL AND company != ''
          AND (%s::text[] IS NULL OR query_name = ANY(%s))
        GROUP BY company
        HAVING COUNT(*) >= %s
        ORDER BY query_diversity DESC, ads DESC
        LIMIT 25
    """
    return _read(conn, sql, (queries, queries, min_ads))


def portal_effectiveness(
    conn,
    high_signal_queries: list[str],
) -> pd.DataFrame:
    """Signal-to-noise and salary coverage per portal."""
    sql = """
        SELECT
            portal,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE query_name = ANY(%s)) AS high_signal,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE query_name = ANY(%s))
                / NULLIF(COUNT(*), 0), 1
            ) AS signal_pct,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE salary IS NOT NULL AND salary != ''
                ) / NULLIF(COUNT(*), 0), 1
            ) AS salary_pct
        FROM ads
        GROUP BY portal
        ORDER BY signal_pct DESC
    """
    return _read(conn, sql, (high_signal_queries, high_signal_queries))


def status_funnel(
    conn,
    queries: list[str] | None,
) -> pd.DataFrame:
    """Career pipeline distribution."""
    sql = """
        SELECT
            status,
            COUNT(*) AS cnt,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM ads
        WHERE (%s::text[] IS NULL OR query_name = ANY(%s))
        GROUP BY status
        ORDER BY CASE status
            WHEN 'new' THEN 1
            WHEN 'seen' THEN 2
            WHEN 'applied' THEN 3
            WHEN 'rejected' THEN 4
            ELSE 5
        END
    """
    return _read(conn, sql, (queries, queries))


def stale_vs_fresh(
    conn,
    queries: list[str] | None,
) -> pd.DataFrame:
    """last_7d / prev_7d / older split per query."""
    sql = """
        SELECT
            query_name,
            COUNT(*) FILTER (WHERE first_seen >= CURRENT_DATE - 7) AS last_7d,
            COUNT(*) FILTER (
                WHERE first_seen >= CURRENT_DATE - 14
                  AND first_seen < CURRENT_DATE - 7
            ) AS prev_7d,
            COUNT(*) FILTER (WHERE first_seen < CURRENT_DATE - 14) AS older
        FROM ads
        WHERE (%s::text[] IS NULL OR query_name = ANY(%s))
        GROUP BY query_name
        ORDER BY last_7d DESC
    """
    return _read(conn, sql, (queries, queries))


def cross_stack_companies(
    conn,
    queries: list[str] | None,
) -> pd.DataFrame:
    """Companies hiring across >=2 high-signal stacks."""
    sql = """
        SELECT
            company,
            ARRAY_AGG(DISTINCT query_name ORDER BY query_name) AS stacks,
            COUNT(DISTINCT query_name) AS stack_count
        FROM ads
        WHERE company IS NOT NULL AND company != ''
          AND (%s::text[] IS NULL OR query_name = ANY(%s))
        GROUP BY company
        HAVING COUNT(DISTINCT query_name) >= 2
        ORDER BY stack_count DESC, company
        LIMIT 20
    """
    return _read(conn, sql, (queries, queries))


def portal_quality(conn) -> pd.DataFrame:
    """Original portal quality score (kept for compatibility)."""
    sql = """
        SELECT portal,
            COUNT(*) AS total_ads,
            COUNT(DISTINCT company) AS unique_companies,
            ROUND(100.0 * COUNT(CASE WHEN salary IS NOT NULL AND salary != '' THEN 1 END)
                  / NULLIF(COUNT(*), 0), 1) AS salary_pct,
            ROUND(100.0 * COUNT(CASE WHEN description IS NOT NULL
                  AND length(description) > 50 THEN 1 END)
                  / NULLIF(COUNT(*), 0), 1) AS desc_pct,
            ROUND((COUNT(CASE WHEN salary IS NOT NULL AND salary != '' THEN 1 END)
                 + COUNT(CASE WHEN description IS NOT NULL
                   AND length(description) > 50 THEN 1 END))
                 * 100.0 / (2 * NULLIF(COUNT(*), 0)), 1) AS quality_score
        FROM ads
        GROUP BY portal
        ORDER BY quality_score DESC
    """
    return _read(conn, sql)


def last_run_status(conn) -> str | None:
    df = _read(conn, "SELECT status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
    if df.empty:
        return None
    return df.iloc[0]["status"]
