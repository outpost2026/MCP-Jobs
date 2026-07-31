from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def hit_rate(self) -> float:
        if self.total_scraped == 0:
            return 0.0
        return round(self.total_found / self.total_scraped, 4)


class Storage:
    PORTAL_FIELDS: dict[str, list[str]] = {
        "bazos": [
            "title",
            "url",
            "date",
            "matched_keyword",
            "location",
            "price",
            "category_name",
            "description",
            "scraped_at",
        ],
        "jobs": [
            "title",
            "url",
            "date",
            "salary",
            "company",
            "location",
            "matched_keyword",
            "category_name",
            "scraped_at",
        ],
        "pracecz": [
            "title",
            "url",
            "salary",
            "company",
            "location",
            "matched_keyword",
            "category_name",
            "scraped_at",
        ],
        "nyx": [
            "title",
            "url",
            "date",
            "price",
            "description",
            "matched_keyword",
            "scraped_at",
        ],
    }

    @staticmethod
    def load_csv(csv_path: Path) -> list[dict[str, Any]]:
        if not csv_path.exists():
            return []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return [row for row in reader if any(v.strip() for v in row.values())]

    @staticmethod
    def save_incremental(ads: list[Ad], csv_path: Path) -> int:
        existing = Storage.load_csv(csv_path)
        existing_urls = {r.get("url", "") for r in existing if r.get("url")}

        portal = ads[0].portal if ads else "unknown"
        fieldnames = Storage.PORTAL_FIELDS.get(portal, Storage.PORTAL_FIELDS["bazos"])

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        new_count = 0
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in existing:
                writer.writerow(row)

            for ad in ads:
                if ad.url not in existing_urls:
                    writer.writerow(ad.to_dict())
                    existing_urls.add(ad.url)
                    new_count += 1

        return new_count

    @staticmethod
    def save_timestamped(data: list[dict], output_dir: Path) -> list[Path]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / f"etl_{timestamp}.json"
        with json_path.open("w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        latest_json = output_dir / "etl_latest.json"
        with latest_json.open("w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        all_ads: list[Ad] = []
        for entry in data:
            for ad_dict in entry.get("results", []):
                all_ads.append(
                    Ad(
                        title=ad_dict.get("title", ""),
                        url=ad_dict.get("url", ""),
                        portal=ad_dict.get("portal", ""),
                        company=ad_dict.get("company"),
                        location=ad_dict.get("location"),
                        salary=ad_dict.get("salary"),
                        price=ad_dict.get("price"),
                        description=ad_dict.get("description"),
                        matched_keyword=ad_dict.get("matched_keyword", ""),
                    )
                )

        md_body = Storage.markdown_report(all_ads)
        header = f"> Generated: {timestamp} | Queries: {len(data)} | Total ads: {len(all_ads)}\n\n"
        md_text = header + md_body

        md_path = output_dir / f"etl_{timestamp}.md"
        with md_path.open("w", encoding="utf-8", newline="") as f:
            f.write(md_text)
        latest_md = output_dir / "etl_latest.md"
        with latest_md.open("w", encoding="utf-8", newline="") as f:
            f.write(md_text)

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

    @staticmethod
    def markdown_report(ads: list[Ad]) -> str:
        lines = [f"# Search Results ({len(ads)} ads)", ""]
        for ad in ads:
            meta = f" portal={ad.portal}"
            if ad.company:
                meta += f" | company={ad.company}"
            if ad.location:
                meta += f" | location={ad.location}"
            if ad.salary:
                meta += f" | salary={ad.salary}"
            if ad.price:
                meta += f" | price={ad.price}"
            lines.append(f"## [{ad.title}]({ad.url})")
            lines.append(meta)
            if ad.description:
                desc = ad.description[:200].replace("\n", " ")
                lines.append(f"> {desc}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def rag_index_md(ads: list[Ad], title: str = "RAG INDEX") -> str:
        lines = [
            f"# {title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
        ]
        for i, ad in enumerate(ads, 1):
            meta_parts = []
            if ad.date:
                meta_parts.append(f"**Datum:** {ad.date}")
            if ad.salary:
                meta_parts.append(f"**Plat:** {ad.salary}")
            elif ad.price:
                meta_parts.append(f"**Cena:** {ad.price}")
            if ad.company:
                meta_parts.append(f"**Společnost:** {ad.company}")
            if ad.location:
                meta_parts.append(f"**Lokalita:** {ad.location}")
            if ad.matched_keyword:
                meta_parts.append(f"**Klíč:** {ad.matched_keyword}")

            lines.append(f"{i}. **[{ad.title}]({ad.url})**")
            if meta_parts:
                lines.append(f"   - {' | '.join(meta_parts)}")
            if ad.description:
                desc = ad.description.replace("\n", " ").replace("\r", "")
                lines.append(f"   - {desc}")
            lines.append("")
        return "\n".join(lines)
