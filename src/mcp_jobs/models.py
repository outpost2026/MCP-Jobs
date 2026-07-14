from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .utils import strip_emoji


@dataclass
class Ad:
    title: str
    url: str
    portal: str
    date: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    category_name: Optional[str] = None
    matched_keyword: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = {}
        for k in ("title", "url", "portal", "date", "company", "location",
                   "salary", "price", "description", "category_name",
                   "matched_keyword", "scraped_at"):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = strip_emoji(v) if isinstance(v, str) else v
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
