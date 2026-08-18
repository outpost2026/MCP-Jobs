from .bazos import BazosScraper
from .jobs import JobsScraper
from .pracecz import PraceczScraper

REGISTRY: dict[str, type] = {
    "bazos": BazosScraper,
    "jobs": JobsScraper,
    "pracecz": PraceczScraper,
}

ACTIVE_PORTALS: dict[str, type] = dict(REGISTRY)

__all__ = [
    "ACTIVE_PORTALS",
    "REGISTRY",
    "BazosScraper",
    "JobsScraper",
    "PraceczScraper",
]
