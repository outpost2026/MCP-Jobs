from .bazos import BazosScraper
from .jenprace import JenpraceScraper
from .jobs import JobsScraper
from .pracecz import PraceczScraper

REGISTRY: dict[str, type] = {
    "bazos": BazosScraper,
    "jenprace": JenpraceScraper,
    "jobs": JobsScraper,
    "pracecz": PraceczScraper,
}

ACTIVE_PORTALS: dict[str, type] = dict(REGISTRY)

__all__ = [
    "ACTIVE_PORTALS",
    "REGISTRY",
    "BazosScraper",
    "JenpraceScraper",
    "JobsScraper",
    "PraceczScraper",
]
