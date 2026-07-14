from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Optional

from .models import Ad


class Storage:
    PORTAL_FIELDS: dict[str, list[str]] = {
        "bazos":   ["title", "url", "date", "matched_keyword", "location",
                     "price", "category_name", "description", "scraped_at"],
        "jobs":    ["title", "url", "date", "salary", "company",
                     "location", "matched_keyword", "category_name", "scraped_at"],
        "pracecz": ["title", "url", "salary", "company",
                     "location", "matched_keyword", "category_name", "scraped_at"],
        "nyx":     ["title", "url", "date", "price", "description",
                     "matched_keyword", "scraped_at"],
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
        lines = [f"# {title} - {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}", "---", ""]
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
