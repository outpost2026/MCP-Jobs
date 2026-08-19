from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .matcher import validate_boolean

logger = logging.getLogger(__name__)


def _flatten_exclude(items: list) -> list[str]:
    """Flatten nested exclude lists (YAML anchor merges like [*a, *b, 'x'])."""
    flat: list[str] = []
    for it in items:
        if isinstance(it, list):
            flat.extend(_flatten_exclude(it))
        elif isinstance(it, str) and it.strip():
            flat.append(it)
    return flat


@dataclass
class CategoryConfig:
    url: str
    pages: int = 5
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class PortalConfig:
    enabled: bool = True
    categories: list[CategoryConfig] = field(default_factory=list)


@dataclass
class QueryConfig:
    boolean: str = ""
    min_salary: int = 0
    locations: list[str] = field(default_factory=list)
    portals: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class PipelineSettings:
    """Mira soubeznosti a throttle politika pipeline pri scrapingu portalu.

    max_workers: 0 = auto (pocet ozbrojenych portalu), 1 = sekvencne,
                 2+ = vice portalu soucasne (kazdy v samostatnem vlakne).
    request_delay: minimalni odstup mezi 2 requesty na PORTAL (s).
                  Zachovava scrape politiku (slusnost vuci server), jen
                  zkracuje cekaci okno. 429/5xx stale kryptuje urllib3 Retry.
                  Clamp: max(0.2, request_delay) — zabrani request_delay=0.
    url_allowlist: mnozina povolenych domen pro scraping. Prazdna = bez
                  validace (pro testy). Vychozi = bazos.cz, jobs.cz, prace.cz.
    """

    max_workers: int = 0
    request_delay: float = 0.5
    url_allowlist: list[str] = field(
        default_factory=lambda: ["bazos.cz", "jobs.cz", "prace.cz", "jenprace.cz"]
    )

    def __post_init__(self) -> None:
        self.request_delay = max(0.2, self.request_delay)


@dataclass
class UserConfig:
    user: str = "default"
    profile: str = "default"
    portals: dict[str, PortalConfig] = field(default_factory=dict)
    queries: dict[str, QueryConfig] = field(default_factory=dict)
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)

    @classmethod
    def from_yaml(cls, path: str | Path) -> UserConfig:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        return cls._from_raw(raw)

    @classmethod
    def from_yaml_string(cls, yaml_content: str) -> UserConfig:
        raw = yaml.safe_load(yaml_content)
        if not raw:
            raise ValueError("Empty YAML content")
        return cls._from_raw(raw)

    @classmethod
    def _from_raw(cls, raw: dict) -> UserConfig:
        if not raw:
            raise ValueError("Empty config data")

        raw_portals = raw.get("portals", {})
        if not isinstance(raw_portals, dict):
            raise TypeError(
                f"'portals' must be a YAML mapping (dict), got {type(raw_portals).__name__}. "
                "Expected format:\n"
                "  portals:\n"
                "    portal_name:\n"
                "      enabled: true\n"
                "      categories:\n"
                '        - url: "https://..."\n'
                "          pages: 5"
            )
        portals = {}
        for name, pdata in raw_portals.items():
            try:
                cats = [CategoryConfig(**c) for c in pdata.get("categories", [])]
            except TypeError as e:
                raise TypeError(f"Portal {name!r}: invalid category config: {e}") from e
            portals[name] = PortalConfig(
                enabled=pdata.get("enabled", True),
                categories=cats,
            )

        raw_queries = raw.get("queries", {})
        if not isinstance(raw_queries, dict):
            raise TypeError(
                f"'queries' must be a YAML mapping (dict), got {type(raw_queries).__name__}. "
                "Expected format:\n"
                "  queries:\n"
                "    query_name:\n"
                '      boolean: "(python AND developer) NOT senior"\n'
                '      exclude: ["agentura"]\n'
                '      portals: ["jobs", "pracecz"]'
            )
        queries = {}
        for name, qdata in raw_queries.items():
            try:
                qdata = dict(qdata)
            except (TypeError, ValueError):
                pass
            if isinstance(qdata.get("exclude"), list):
                qdata["exclude"] = _flatten_exclude(qdata["exclude"])
            try:
                qc = QueryConfig(**qdata)
            except TypeError as e:
                raise TypeError(f"Query {name!r}: invalid query config: {e}") from e
            if qc.boolean and not validate_boolean(qc.boolean):
                raise ValueError(
                    f"Query {name!r}: malformed boolean expression: {qc.boolean!r}"
                )
            queries[name] = qc

        raw_pipeline = raw.get("pipeline", {}) or {}
        try:
            pipeline = PipelineSettings(**raw_pipeline)
        except TypeError as e:
            raise TypeError(f"Invalid pipeline config: {e}") from e

        return cls(
            user=raw.get("user", "default"),
            profile=raw.get("profile", "default"),
            portals=portals,
            queries=queries,
            pipeline=pipeline,
        )
