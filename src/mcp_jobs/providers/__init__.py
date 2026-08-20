from .bazos import BazosScraper
from .jenprace import JenpraceScraper
from .jobs import JobsScraper
from .pracecz import PraceczScraper
from .profesia import ProfesiaScraper
from .volnamista import VolnamistaScraper

REGISTRY: dict[str, type] = {
    "bazos": BazosScraper,
    "jenprace": JenpraceScraper,
    "jobs": JobsScraper,
    "pracecz": PraceczScraper,
    "profesia": ProfesiaScraper,
    "volnamista": VolnamistaScraper,
}

ACTIVE_PORTALS: dict[str, type] = dict(REGISTRY)

__all__ = [
    "ACTIVE_PORTALS",
    "REGISTRY",
    "BazosScraper",
    "JenpraceScraper",
    "JobsScraper",
    "PraceczScraper",
    "ProfesiaScraper",
    "VolnamistaScraper",
]
