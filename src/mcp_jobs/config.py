from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


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
class UserConfig:
    user: str = "default"
    portals: dict[str, PortalConfig] = field(default_factory=dict)
    queries: dict[str, QueryConfig] = field(default_factory=dict)

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
                "        - url: \"https://...\"\n"
                "          pages: 5"
            )
        portals = {}
        for name, pdata in raw_portals.items():
            cats = [CategoryConfig(**c) for c in pdata.get("categories", [])]
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
                "      boolean: \"(python AND developer) NOT senior\"\n"
                "      exclude: [\"agentura\"]\n"
                "      portals: [\"jobs\", \"pracecz\"]"
            )
        queries = {}
        for name, qdata in raw_queries.items():
            queries[name] = QueryConfig(**qdata)

        return cls(
            user=raw.get("user", "default"),
            portals=portals,
            queries=queries,
        )
