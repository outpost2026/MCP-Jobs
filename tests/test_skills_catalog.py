"""Tests for skills_catalog module (skill extraction + tech scoring)."""

import pytest

from mcp_jobs.skills_catalog import (
    SkillsCatalog,
    TechScoreResult,
    _load_config,
    get_catalog,
)

# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def catalog() -> SkillsCatalog:
    """Shared catalog instance for all tests (module scope = single load)."""
    return SkillsCatalog()


@pytest.fixture
def sample_it_ad() -> str:
    return (
        "Hledame Python developera s zkusenostmi s Docker, Kubernetes a CI/CD. "
        "Prace na Azure cloud, PostgreSQL, Git. Bonus: LLM, RAG, embeddings. "
        "Angular preferred but not required."
    )


@pytest.fixture
def sample_cnc_ad() -> str:
    return (
        "Programator CNC obrabeciho centra. Znalost Heidenhain, Siemens, Fanuc. "
        "CNC frézka, soustruh. Technicka dokumentace, mereni."
    )


@pytest.fixture
def sample_empty_ad() -> str:
    return ""


@pytest.fixture
def sample_no_skills() -> str:
    return "Hledame sikovneho cloveka do naseho tymu. Prace v kancelari."


# --- Config loading ---------------------------------------------------------


def test_load_config_returns_dict():
    cfg = _load_config()
    assert isinstance(cfg, dict)
    assert "skills" in cfg
    assert "domain_keywords" in cfg
    assert "scoring" in cfg


def test_config_has_scoring_weights():
    cfg = _load_config()
    weights = cfg["scoring"]["weights"]
    assert abs(sum(weights.values()) - 1.0) < 0.01


# --- Catalog initialization -------------------------------------------------


def test_catalog_loads_skills(catalog: SkillsCatalog):
    assert catalog.skill_count >= 90  # we have 94 skills


def test_catalog_has_patterns(catalog: SkillsCatalog):
    assert len(catalog._patterns) == catalog.skill_count


def test_catalog_max_possible_positive(catalog: SkillsCatalog):
    assert catalog._max_possible > 0


# --- match_description ------------------------------------------------------


def test_match_python(catalog: SkillsCatalog):
    matches = catalog.match_description("Python developer wanted")
    ids = [m.skill_id for m in matches]
    assert "Python" in ids


def test_match_multiple_skills(catalog: SkillsCatalog, sample_it_ad: str):
    matches = catalog.match_description(sample_it_ad)
    ids = {m.skill_id for m in matches}
    assert "Python" in ids
    assert "Docker" in ids
    assert "Kubernetes" in ids
    assert "CICD" in ids
    assert "Azure" in ids
    assert "PostgreSQL" in ids
    assert "Git" in ids


def test_match_case_insensitive(catalog: SkillsCatalog):
    matches = catalog.match_description("PYTHON developer wanted")
    ids = [m.skill_id for m in matches]
    assert "Python" in ids


def test_match_aliases(catalog: SkillsCatalog):
    matches = catalog.match_description("K8s a Docker kontejnery")
    ids = {m.skill_id for m in matches}
    assert "Kubernetes" in ids  # K8s is alias
    assert "Docker" in ids


def test_match_no_skills(catalog: SkillsCatalog, sample_no_skills: str):
    matches = catalog.match_description(sample_no_skills)
    assert len(matches) == 0


def test_match_empty(catalog: SkillsCatalog, sample_empty_ad: str):
    matches = catalog.match_description(sample_empty_ad)
    assert len(matches) == 0


def test_match_none_text(catalog: SkillsCatalog):
    matches = catalog.match_description(None)  # type: ignore[arg-type]
    assert len(matches) == 0


def test_match_sorted_by_weight(catalog: SkillsCatalog, sample_it_ad: str):
    matches = catalog.match_description(sample_it_ad)
    weights = [m.weight for m in matches]
    assert weights == sorted(weights, reverse=True)


def test_match_cnc(catalog: SkillsCatalog, sample_cnc_ad: str):
    matches = catalog.match_description(sample_cnc_ad)
    ids = {m.skill_id for m in matches}
    assert "CNC" in ids
    assert "Heidenhain" in ids


def test_match_confidence_exact(catalog: SkillsCatalog):
    matches = catalog.match_description("Python")
    py = next(m for m in matches if m.skill_id == "Python")
    assert py.confidence == 1.0


def test_match_confidence_alias(catalog: SkillsCatalog):
    matches = catalog.match_description("K8s cluster")
    k8s = next(m for m in matches if m.skill_id == "Kubernetes")
    assert k8s.confidence < 1.0  # alias match


def test_match_context_not_empty(catalog: SkillsCatalog):
    matches = catalog.match_description("Python developer wanted")
    assert len(matches) > 0
    assert len(matches[0].context) > 0


# --- tech_score -------------------------------------------------------------


def test_tech_score_basic(catalog: SkillsCatalog, sample_it_ad: str):
    result = catalog.tech_score(sample_it_ad)
    assert isinstance(result, TechScoreResult)
    assert result.score > 0
    assert len(result.matches) > 0
    assert result.detail != ""


def test_tech_score_empty(catalog: SkillsCatalog, sample_empty_ad: str):
    result = catalog.tech_score(sample_empty_ad)
    assert result.score == 0.0
    assert len(result.matches) == 0


def test_tech_score_no_skills(catalog: SkillsCatalog, sample_no_skills: str):
    result = catalog.tech_score(sample_no_skills)
    assert result.score == 0.0


def test_tech_score_more_skills_higher(catalog: SkillsCatalog):
    r1 = catalog.tech_score("Python")
    r2 = catalog.tech_score("Python Docker Kubernetes CI/CD Git SQL Azure")
    assert r2.score >= r1.score


def test_tech_score_coverage(catalog: SkillsCatalog, sample_it_ad: str):
    result = catalog.tech_score(sample_it_ad)
    assert result.coverage > 0
    assert result.coverage <= 1.0


def test_tech_score_mentioned_weighted(catalog: SkillsCatalog, sample_it_ad: str):
    result = catalog.tech_score(sample_it_ad)
    assert result.mentioned_weighted > 0


def test_tech_score_max_100(catalog: SkillsCatalog):
    # Many skills should still cap at 100
    text = " ".join(
        [
            "Python",
            "Docker",
            "Kubernetes",
            "CI/CD",
            "Git",
            "Linux",
            "Azure",
            "AWS",
            "GCP",
            "PostgreSQL",
            "Kafka",
            "Spark",
            "Airflow",
            "Terraform",
            "Prometheus",
            "Grafana",
            "ML",
            "AI",
            "LLM",
            "RAG",
            "PyTorch",
            "TensorFlow",
            "Selenium",
            "CNC",
            "PLC",
            "SCADA",
            "MCP",
            "FastMCP",
            "agentic",
        ]
    )
    result = catalog.tech_score(text)
    assert result.score <= 100.0


# --- domain_score -----------------------------------------------------------


def test_domain_score_industrial(catalog: SkillsCatalog):
    score, detail = catalog.domain_score("PLC programming, SCADA system, CNC machine")
    assert score >= 50.0
    assert "core=" in detail


def test_domain_score_non_industrial(catalog: SkillsCatalog):
    score, _detail = catalog.domain_score(
        "Customer service, sales, account management, help desk"
    )
    assert score <= 20.0


def test_domain_score_adjacent(catalog: SkillsCatalog):
    score, _detail = catalog.domain_score("Automotive, embedded systems, IoT")
    assert 25.0 <= score <= 50.0


def test_domain_score_empty(catalog: SkillsCatalog):
    score, _ = catalog.domain_score("")
    assert score == 25.0  # default no signal


# --- employer_tier ----------------------------------------------------------


def test_employer_tier_strategic(catalog: SkillsCatalog):
    assert catalog.employer_tier("Siemens") == "strategic"
    assert catalog.employer_tier("Siemens, s.r.o.") == "strategic"
    assert catalog.employer_tier("Bosch") == "strategic"


def test_employer_tier_growth(catalog: SkillsCatalog):
    assert catalog.employer_tier("Honeywell") == "growth"
    assert catalog.employer_tier("Fanuc") == "growth"


def test_employer_tier_unknown(catalog: SkillsCatalog):
    assert catalog.employer_tier("Acme Corp") == "unknown"
    assert catalog.employer_tier("") == "unknown"
    assert catalog.employer_tier(None) == "unknown"  # type: ignore[arg-type]


# --- is_fake_engineer -------------------------------------------------------


def test_is_fake_engineer_true(catalog: SkillsCatalog):
    assert catalog.is_fake_engineer("Customer Service Engineer") is True
    assert catalog.is_fake_engineer("Sales Engineer") is True
    assert catalog.is_fake_engineer("Help Desk Engineer") is True


def test_is_fake_engineer_false(catalog: SkillsCatalog):
    assert catalog.is_fake_engineer("Python Developer") is False
    assert catalog.is_fake_engineer("Test Automation Engineer") is False
    assert catalog.is_fake_engineer("") is False


# --- location_score ---------------------------------------------------------


def test_location_score_remote(catalog: SkillsCatalog):
    score, detail = catalog.location_score("Remote work, home office available")
    assert score >= 80.0
    assert "remote" in detail.lower()


def test_location_score_czech(catalog: SkillsCatalog):
    score, detail = catalog.location_score("Praha, Brno")
    assert score >= 40.0
    assert "CZ" in detail


def test_location_score_no_signal(catalog: SkillsCatalog):
    score, _detail = catalog.location_score("Some random text")
    assert score <= 40.0


# --- has_emoji --------------------------------------------------------------


def test_has_emoji_true(catalog: SkillsCatalog):
    assert catalog.has_emoji("Hello \U0001f600 world") is True


def test_has_emoji_false(catalog: SkillsCatalog):
    assert catalog.has_emoji("Hello world") is False
    assert catalog.has_emoji("Python Docker") is False


# --- get_catalog singleton --------------------------------------------------


def test_get_catalog_singleton():
    c1 = get_catalog()
    c2 = get_catalog()
    assert c1 is c2
