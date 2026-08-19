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


def profile_tag_from_profile(profile: str) -> str:
    """Semantic file tag from a config profile.

    'AI-NATIVE' -> 'AI_NATIVE', 'LEGACY-MANUAL' -> 'LEGACY_MANUAL', else 'DEFAULT'.
    """
    tag = profile.upper()
    for ch in ("-", " ", "/", "\\", ":", "."):
        tag = tag.replace(ch, "_")
    tag = "_".join(p for p in tag.split("_") if p)
    return tag or "DEFAULT"


class Storage:
    @staticmethod
    def save_outputs(
        data: list[dict],
        output_dir: Path,
        profile: str = "default",
        meta_overrides: dict | None = None,
    ) -> list[Path]:
        """Save run outputs (JSON + MD + HTML) with unified naming and dedup.

        Single convention for both CLI and MCP:
          etl_{PROFILE_TAG}_{ts}.{json,md,html}
        No `etl_latest_*` copies (removed 2026-08-19).
        HTML is always generated (derived from the unified renderer).

        Dedup: if the *normalized* payload (volatile keys like query_id,
        resource_uri, scraped_at stripped) matches the most recent run of
        the same profile, nothing is written (returns []).

        `meta_overrides` feeds the report header (timestamp, elapsed_seconds,
        config_file, total_raw, portals, queries) for the CLI path.
        """
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        profile_tag = profile_tag_from_profile(profile)
        output_dir.mkdir(parents=True, exist_ok=True)

        json_text = json.dumps(data, ensure_ascii=False, indent=2)
        norm_now = _normalize_json(data)

        prev = _latest_run(output_dir, profile_tag)
        if prev is not None:
            try:
                prev_norm = _normalize_json(
                    json.loads(prev.read_text(encoding="utf-8"))
                )
                if prev_norm == norm_now:
                    logger.info(
                        "Dedup: output identical to %s — nothing written", prev.name
                    )
                    return []
            except Exception as e:
                logger.warning(
                    "Dedup compare failed (%s) — writing anyway: %s", prev, e
                )

        json_path = output_dir / f"etl_{profile_tag}_{ts}.json"
        with json_path.open("w", encoding="utf-8", newline="") as f:
            f.write(json_text)

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

        ov = meta_overrides or {}
        meta = ReportMeta(
            timestamp=ov.get("timestamp", datetime.now(UTC).isoformat()),
            elapsed_seconds=ov.get("elapsed_seconds", 0.0),
            total_matched=total_raw,
            total_raw=ov.get("total_raw", total_raw),
            precision=round((total_raw / total_raw) * 100, 1) if total_raw else 0.0,
            profile=profile,
            config_file=ov.get("config_file", ""),
            json_link=json_path.name,
            portals=sorted(
                {a.portal for ads in ads_by_query.values() for a in ads if a.portal}
            ),
            queries=list(ads_by_query.keys()),
        )
        report = render_report(ads_by_query, meta)

        md_path = output_dir / f"etl_{profile_tag}_{ts}.md"
        with md_path.open("w", encoding="utf-8", newline="") as f:
            f.write(report.markdown)

        html_path = output_dir / f"etl_{profile_tag}_{ts}.html"
        with html_path.open("w", encoding="utf-8", newline="") as f:
            f.write(report.html)

        return [json_path, md_path, html_path]

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


def _latest_run(output_dir: Path, profile_tag: str) -> Path | None:
    """Most recent saved JSON for a profile tag (name sort = chrono sort)."""
    candidates = sorted(output_dir.glob(f"etl_{profile_tag}_*.json"))
    return candidates[-1] if candidates else None


_VOLATILE_KEYS = frozenset(
    {
        "query_id",
        "resource_uri",
        "scraped_at",
        "elapsed_s",
        "submitted_at",
        "finished_at",
    }
)


def _normalize_json(value):
    """Recursively strip volatile per-run keys so dedup compares real content.

    query_id/resource_uri differ every run (uuid), scraped_at records the
    exact scrape time — all must be ignored for content-identity dedup.
    """
    if isinstance(value, dict):
        return {
            k: _normalize_json(v) for k, v in value.items() if k not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_normalize_json(v) for v in value]
    return value
