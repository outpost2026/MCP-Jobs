from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .models import Ad

logger = logging.getLogger(__name__)


@dataclass
class CorrelationRecord:
    query: str
    portal: str
    total_found: int
    total_scraped: int
    errors: int = 0
    profile: str = "default"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def hit_rate(self) -> float:
        if self.total_scraped == 0:
            return 0.0
        return round(self.total_found / self.total_scraped, 4)


class Storage:
    @staticmethod
    def save_timestamped(data: list[dict], output_dir: Path) -> list[Path]:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / f"etl_{timestamp}.json"
        with json_path.open("w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        latest_json = output_dir / "etl_latest.json"
        with latest_json.open("w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Build per-query ad mapping for the unified renderer
        ads_by_query: dict[str, list[Ad]] = {}
        total_raw = 0
        for entry in data:
            qname = entry.get("query", "query")
            ads = []
            for ad_dict in entry.get("results", []):
                ads.append(
                    Ad(
                        title=ad_dict.get("title", ""),
                        url=ad_dict.get("url", ""),
                        portal=ad_dict.get("portal", ""),
                        date=ad_dict.get("date"),
                        company=ad_dict.get("company"),
                        location=ad_dict.get("location"),
                        salary=ad_dict.get("salary"),
                        price=ad_dict.get("price"),
                        description=ad_dict.get("description"),
                        category_name=ad_dict.get("category_name"),
                        matched_keyword=ad_dict.get("matched_keyword", ""),
                    )
                )
            ads_by_query[qname] = ads
            total_raw += len(ads)

        from .report import ReportMeta, render_report

        total_matched = total_raw
        precision = round((total_matched / total_raw) * 100, 1) if total_raw else 0.0
        meta = ReportMeta(
            timestamp=datetime.now(UTC).isoformat(),
            elapsed_seconds=0.0,
            total_matched=total_matched,
            total_raw=total_raw,
            precision=precision,
            profile="default",
            json_link=f"etl_{timestamp}.json",
            portals=sorted(
                {a.portal for ads in ads_by_query.values() for a in ads if a.portal}
            ),
            queries=list(ads_by_query.keys()),
        )
        report = render_report(ads_by_query, meta)

        md_path = output_dir / f"etl_{timestamp}.md"
        with md_path.open("w", encoding="utf-8", newline="") as f:
            f.write(report.markdown)
        latest_md = output_dir / "etl_latest.md"
        with latest_md.open("w", encoding="utf-8", newline="") as f:
            f.write(report.markdown)

        html_path = output_dir / f"etl_{timestamp}.html"
        with html_path.open("w", encoding="utf-8", newline="") as f:
            f.write(report.html)
        latest_html = output_dir / "etl_latest.html"
        with latest_html.open("w", encoding="utf-8", newline="") as f:
            f.write(report.html)

        return [json_path, md_path]

    @staticmethod
    def save_correlation(records: list[CorrelationRecord], path: Path) -> None:
        existing: list[dict] = []
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception as e:
                logger.warning(
                    "Failed to load correlation cache %s — starting fresh: %s", path, e
                )

        for r in records:
            existing.append(
                {
                    "query": r.query,
                    "portal": r.portal,
                    "profile": r.profile,
                    "total_found": r.total_found,
                    "total_scraped": r.total_scraped,
                    "hit_rate": r.hit_rate,
                    "errors": r.errors,
                    "timestamp": r.timestamp,
                }
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
