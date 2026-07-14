from .bazos import BazosScraper
from .jobs import JobsScraper
from .pracecz import PraceczScraper
from .nyx import NyxScraper

REGISTRY: dict[str, type] = {
    "bazos": BazosScraper,
    "jobs": JobsScraper,
    "pracecz": PraceczScraper,
    "nyx": NyxScraper,  # DEPRECATED — requires auth, not a job portal
}

ACTIVE_PORTALS: dict[str, type] = {k: v for k, v in REGISTRY.items() if k != "nyx"}

__all__ = ["REGISTRY", "ACTIVE_PORTALS", "BazosScraper", "JobsScraper", "PraceczScraper", "NyxScraper"]
