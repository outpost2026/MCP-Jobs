from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

from .utils import strip_emoji


@dataclass
class Ad:
    title: str
    url: str
    portal: str
    date: str | None = None
    company: str | None = None
    location: str | None = None
    salary: str | None = None
    price: str | None = None
    description: str | None = None
    category_name: str | None = None
    matched_keyword: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    OPTIONAL_FIELDS: ClassVar[set[str]] = {
        "date",
        "company",
        "location",
        "salary",
        "price",
        "description",
        "category_name",
    }

    def to_dict(self) -> dict:
        d = {}
        missing = []
        for k in (
            "title",
            "url",
            "portal",
            "date",
            "company",
            "location",
            "salary",
            "price",
            "description",
            "category_name",
            "matched_keyword",
            "scraped_at",
        ):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = strip_emoji(v) if isinstance(v, str) else v
            elif k in self.OPTIONAL_FIELDS:
                d[k] = None
                missing.append(k)
        if missing:
            d["missing_fields"] = missing
            d["_flags"] = {"partial": True}
        return d


@dataclass
class SearchResult:
    query: str
    portal: str
    ads: list[Ad] = field(default_factory=list)
    total_found: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "portal": self.portal,
            "total_found": self.total_found,
            "results": [a.to_dict() for a in self.ads],
            "errors": self.errors,
        }
