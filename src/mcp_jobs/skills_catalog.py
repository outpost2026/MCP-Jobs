"""Standalone skill catalog for IT stack extraction from job descriptions.

Loads skills_config.json (bundled), builds regex patterns, and provides:
  - SkillsCatalog.match_description(text) -> list[SkillMatch]
  - SkillsCatalog.tech_score(text) -> (score, matches, detail)

Scoring formula adapted from linkedin-mcp-custom/analysis/tech.py:
  score = coverage_multiplier * 100.0
  coverage_multiplier = min(1.0, coverage * 5.0)
  coverage = mentioned_weighted / max_possible
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).parent / "skills_config.json"


@dataclass
class SkillMatch:
    """Result of matching one skill against text."""

    skill_id: str
    display_name: str
    category: str
    weight: float
    match_type: str  # direct_match | partial_match | no_match
    confidence: float  # 0.0-1.0 (regex match quality)
    context: str = ""  # matched substring snippet


@dataclass
class TechScoreResult:
    """Aggregated tech score for a job description."""

    score: float  # 0-100
    matches: list[SkillMatch] = field(default_factory=list)
    detail: str = ""
    mentioned_weighted: float = 0.0
    coverage: float = 0.0


def _load_config(path: Path | None = None) -> dict[str, Any]:
    """Load skills_config.json. Returns raw dict."""
    p = path or _CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Skills config not found: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _build_pattern(skill_id: str, aliases: list[str]) -> re.Pattern[str]:
    """Build a compiled regex pattern for a skill + its aliases.

    Uses lookbehind/lookahead for word boundary, but handles terms starting
    or ending with non-word chars (CI/CD, C++, .NET, C#) by using
    (?<![A-Za-z0-9]) prefix and (?![A-Za-z0-9]) suffix.
    """
    terms = [skill_id, *aliases]
    # Escape and join with OR, longest first to prefer specific matches
    terms_sorted = sorted(set(terms), key=len, reverse=True)
    escaped = [re.escape(t) for t in terms_sorted]
    pattern_str = "|".join(escaped)
    # Boundary: no alphanumeric immediately before/after.
    # Terms like CI/CD, C++, C#, .NET contain non-alnum chars that are
    # part of the term itself — only block pure alnum adjacency.
    return re.compile(
        rf"(?<![A-Za-z0-9])(?:{pattern_str})(?![A-Za-z0-9])", re.IGNORECASE
    )


class SkillsCatalog:
    """Singleton-ready skill catalog with regex matching and scoring.

    Usage:
        catalog = SkillsCatalog()  # loads bundled config
        result = catalog.match_description("Python, Docker, Kubernetes required")
        score = catalog.tech_score("Python, Docker, Kubernetes required")
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config = _load_config(config_path)
        self._skills: dict[str, dict] = self._config.get("skills", {})
        self._domain_keywords: dict[str, list[str]] = self._config.get(
            "domain_keywords", {}
        )
        self._employer_tiers: dict[str, list[str]] = self._config.get(
            "employer_tiers", {}
        )
        self._remote_keywords: list[str] = self._config.get("remote_keywords", [])
        self._czech_keywords: list[str] = self._config.get("czech_keywords", [])
        self._fake_engineer: list[str] = self._config.get("fake_engineer_keywords", [])

        # Pre-compile regex patterns for each skill
        self._patterns: dict[str, re.Pattern[str]] = {}
        for skill_id, skill_data in self._skills.items():
            aliases = skill_data.get("aliases", [])
            self._patterns[skill_id] = _build_pattern(skill_id, aliases)

        # Max possible weight (sum of all skill weights)
        self._max_possible = sum(s.get("weight", 0.0) for s in self._skills.values())

    @property
    def skill_count(self) -> int:
        return len(self._skills)

    @property
    def skills(self) -> dict[str, dict]:
        return dict(self._skills)

    def match_description(self, text: str) -> list[SkillMatch]:
        """Match all skills in a job description text.

        Returns list of SkillMatch, sorted by weight descending.
        """
        if not text:
            return []

        matches: list[SkillMatch] = []
        for skill_id, pattern in self._patterns.items():
            m = pattern.search(text)
            if m:
                matched_text = m.group(0)
                # Guard: skip single-char false positives (R, C, etc.)
                if len(matched_text) < 2:
                    continue
                skill_data = self._skills[skill_id]
                # Confidence based on match quality:
                # exact match = 1.0, case-insensitive = 0.9, alias = 0.8
                if matched_text == skill_id:
                    confidence = 1.0
                elif matched_text.lower() == skill_id.lower():
                    confidence = 0.95
                else:
                    confidence = 0.85  # alias match

                # Extract context: 40 chars around match
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                context = text[start:end].replace("\n", " ").strip()

                matches.append(
                    SkillMatch(
                        skill_id=skill_id,
                        display_name=skill_data.get("display_name", skill_id),
                        category=skill_data.get("category", "UNKNOWN"),
                        weight=skill_data.get("weight", 0.0),
                        match_type=skill_data.get("match_type", "no_match"),
                        confidence=confidence,
                        context=context,
                    )
                )

        matches.sort(key=lambda x: x.weight, reverse=True)
        return matches

    def tech_score(self, text: str) -> TechScoreResult:
        """Compute tech score for a job description.

        Returns TechScoreResult with score 0-100.

        Scoring formula (adapted from linkedin-mcp-custom):
          mentioned_weighted = sum of weights of all matched skills
          coverage = mentioned_weighted / max_possible
          coverage_multiplier = min(1.0, coverage * 5.0)
          score = coverage_multiplier * 100.0
        """
        matches = self.match_description(text)

        if not matches:
            return TechScoreResult(
                score=0.0,
                matches=[],
                detail="No skills detected",
                mentioned_weighted=0.0,
                coverage=0.0,
            )

        mentioned_weighted = sum(m.weight for m in matches)
        coverage = (
            mentioned_weighted / self._max_possible if self._max_possible > 0 else 0.0
        )
        coverage_multiplier = min(1.0, coverage * 5.0)
        score = coverage_multiplier * 100.0

        direct = sum(1 for m in matches if m.match_type == "direct_match")
        partial = sum(1 for m in matches if m.match_type == "partial_match")
        gap = sum(1 for m in matches if m.match_type == "no_match")
        detail = f"{len(matches)} skills: {direct} direct, {partial} partial, {gap} gap"

        return TechScoreResult(
            score=round(min(score, 100.0), 1),
            matches=matches,
            detail=detail,
            mentioned_weighted=round(mentioned_weighted, 2),
            coverage=round(coverage, 4),
        )

    def domain_score(self, text: str) -> tuple[float, str]:
        """Score how 'industrial' a job description is.

        Returns (score 0-100, detail_string).

        Logic:
          - Count hits in core_industrial, adjacent, non_industrial
          - >=3 core = 80+, >=1 core = 45-70, adjacent only = 30-45,
            non-industrial = 10-20, none = 25
        """
        lowered = text.lower()
        core_hits = sum(
            1
            for kw in self._domain_keywords.get("core_industrial", [])
            if kw.lower() in lowered
        )
        adjacent_hits = sum(
            1
            for kw in self._domain_keywords.get("adjacent_industrial", [])
            if kw.lower() in lowered
        )
        non_industrial_hits = sum(
            1
            for kw in self._domain_keywords.get("non_industrial", [])
            if kw.lower() in lowered
        )

        if core_hits >= 5:
            score = 85.0
        elif core_hits >= 3:
            score = 70.0
        elif core_hits >= 1:
            score = 45.0 + min(core_hits * 10, 25)
        elif adjacent_hits >= 2:
            score = 40.0
        elif adjacent_hits >= 1:
            score = 30.0
        elif non_industrial_hits >= 2:
            score = 15.0
        elif non_industrial_hits >= 1:
            score = 20.0
        else:
            score = 25.0

        # Pure noise: no core + only non-industrial
        if core_hits == 0 and adjacent_hits == 0 and non_industrial_hits > 0:
            score = min(score, 15.0)

        detail = f"core={core_hits}, adjacent={adjacent_hits}, non_industrial={non_industrial_hits}"
        return round(score, 1), detail

    def employer_tier(self, company: str) -> str:
        """Classify company as strategic/growth/unknown."""
        if not company:
            return "unknown"
        company_lower = company.lower()
        for name in self._employer_tiers.get("strategic", []):
            if name.lower() in company_lower:
                return "strategic"
        for name in self._employer_tiers.get("growth", []):
            if name.lower() in company_lower:
                return "growth"
        return "unknown"

    def is_fake_engineer(self, title: str) -> bool:
        """Detect fake engineer titles (sales/support in disguise)."""
        if not title:
            return False
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in self._fake_engineer)

    def location_score(self, text: str) -> tuple[float, str]:
        """Score location/remote favorability.

        Returns (score 0-100, detail_string).
        """
        lowered = text.lower()
        remote_hits = sum(1 for kw in self._remote_keywords if kw.lower() in lowered)
        czech_hits = sum(1 for kw in self._czech_keywords if kw.lower() in lowered)

        if remote_hits >= 2:
            score = 95.0
            detail = "strong remote"
        elif remote_hits >= 1:
            score = 80.0
            detail = "remote/hybrid"
        elif czech_hits >= 1:
            score = 50.0 + min(czech_hits * 10, 20)
            detail = f"CZ-based ({czech_hits} signals)"
        else:
            score = 35.0
            detail = "no location signal"

        return round(score, 1), detail

    def has_emoji(self, text: str) -> bool:
        """Check if text contains emoji (for data quality filtering)."""
        emoji_pattern = re.compile(
            "[\U0001f600-\U0001f64f"
            "\U0001f300-\U0001f5ff"
            "\U0001f680-\U0001f6ff"
            "\U0001f1e0-\U0001f1ff"
            "\U00002702-\U000027b0"
            "\U0001f900-\U0001f9ff"
            "\U0001fa00-\U0001fa6f"
            "\U0001fa70-\U0001faff]",
            flags=re.UNICODE,
        )
        return bool(emoji_pattern.search(text))


# Module-level singleton (lazy init)
_catalog: SkillsCatalog | None = None


def get_catalog() -> SkillsCatalog:
    """Get or create the singleton SkillsCatalog instance."""
    global _catalog
    if _catalog is None:
        _catalog = SkillsCatalog()
    return _catalog
