"""Tests for the unified report renderer (MD source + HTML/CSS render)."""

from __future__ import annotations

from mcp_jobs.models import Ad
from mcp_jobs.report import ReportMeta, render_report


def _ad(
    title="Python Developer",
    portal="jobs",
    company="ACME",
    url="https://jobs.cz/x",
    location="Praha",
    salary="50 000",
    description="Popis pozice",
    date=None,
    matched="python",
):
    return Ad(
        title=title,
        url=url,
        portal=portal,
        company=company,
        location=location,
        salary=salary,
        description=description,
        date=date,
        matched_keyword=matched,
    )


def _meta(**kw):
    base = dict(
        timestamp="2026-08-15T09:15:15",
        elapsed_seconds=10.0,
        total_matched=3,
        total_raw=100,
        precision=3.0,
        profile="test",
        json_link="etl_test_20260815.json",
        portals=["jobs", "pracecz"],
        queries=["q1", "q2"],
    )
    base.update(kw)
    return ReportMeta(**base)


def test_render_markdown_header_and_sections():
    ads = {"q1": [_ad()], "q2": [_ad(title="Data Engineer")]}
    out = render_report(ads, _meta())
    md = out.markdown
    assert "# Job Hunt Report — 2026-08-15" in md
    assert "✅ Matched 3" in md
    assert "## 🔴 Priority" in md
    assert "## 📊 Přehled" in md
    assert "## 📂 q1 — 1" in md
    assert "## 📂 q2 — 1" in md
    assert "🔑 match:" in md
    assert "Precision: 3.0%" in md


def test_render_dedup_across_queries():
    ad = _ad()
    # Same ad (same URL+title+company+location) appears in both queries.
    out = render_report({"q1": [ad], "q2": [ad]}, _meta())
    md = out.markdown
    # match tag aggregates both queries
    assert "🔑 match: q1, q2" in md
    # each query section still lists its own ads
    assert "## 📂 q1 — 1" in md
    assert "## 📂 q2 — 1" in md


def test_render_priority_flag_new_today():
    today = __import__("datetime").date.today().isoformat()
    ad = _ad(date=today)
    out = render_report({"q1": [ad]}, _meta())
    assert "Nové dnes" in out.markdown
    assert "🔴 Priority" in out.markdown


def test_render_html_structure_and_css():
    out = render_report({"q1": [_ad()]}, _meta())
    html = out.html
    assert html.startswith("<!DOCTYPE html>")
    assert "<h1>Job Hunt Report" in html
    assert 'font-family: "Calibri"' in html
    assert "font-size: 8pt" in html
    assert 'class="match"' in html
    assert 'class="meta"' in html
    assert "<table>" in html
    # Links are escaped properly
    assert 'href="https://jobs.cz/x"' in html


def test_render_html_escapes_html_chars():
    ad = _ad(title="<script>alert(1)</script>", company="A & B")
    out = render_report({"q1": [ad]}, _meta())
    html = out.html
    assert "&lt;script&gt;" in html
    assert "A &amp; B" in html
    assert "<script>alert(1)</script>" not in html


def test_render_empty():
    out = render_report({}, _meta(total_matched=0, total_raw=0, precision=0.0))
    md = out.markdown
    assert "## 📊 Přehled" in md
    assert "## 📂 " not in md
