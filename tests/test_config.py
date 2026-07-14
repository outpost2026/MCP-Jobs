from pathlib import Path

import yaml

from mcp_jobs.config import UserConfig, PortalConfig, CategoryConfig, QueryConfig

SAMPLE_YAML = """
user: test_user
portals:
  jobs:
    enabled: true
    categories:
      - url: "https://www.jobs.cz/prace/"
        pages: 3
  bazos:
    enabled: true
    categories:
      - url: "https://prace.bazos.cz/"
        pages: 5
  nyx:
    enabled: false
    categories: []

queries:
  python_jobs:
    boolean: "python AND developer NOT senior"
    min_salary: 0
    locations: []
    portals: ["jobs"]

  cnc_jobs:
    boolean: "(cnc OR frezar) AND programovani"
    min_salary: 40000
    locations: ["brno", "ostrava"]
    portals: ["bazos"]
"""


def test_config_from_yaml(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(SAMPLE_YAML, encoding="utf-8")

    config = UserConfig.from_yaml(config_path)
    assert config.user == "test_user"
    assert "jobs" in config.portals
    assert "bazos" in config.portals
    assert "nyx" in config.portals


def test_config_portal_categories():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_YAML)
        config_path = f.name

    config = UserConfig.from_yaml(config_path)
    jobs = config.portals["jobs"]
    assert jobs.enabled is True
    assert len(jobs.categories) == 1
    assert jobs.categories[0].url == "https://www.jobs.cz/prace/"
    assert jobs.categories[0].pages == 3

    nyx = config.portals["nyx"]
    assert nyx.enabled is False

    Path(config_path).unlink()


def test_config_queries():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_YAML)
        config_path = f.name

    config = UserConfig.from_yaml(config_path)
    assert "python_jobs" in config.queries
    assert "cnc_jobs" in config.queries

    py = config.queries["python_jobs"]
    assert py.boolean == "python AND developer NOT senior"
    assert py.min_salary == 0
    assert py.locations == []
    assert py.portals == ["jobs"]

    cnc = config.queries["cnc_jobs"]
    assert cnc.boolean == "(cnc OR frezar) AND programovani"
    assert cnc.min_salary == 40000
    assert "brno" in cnc.locations

    Path(config_path).unlink()


def test_config_not_found():
    import pytest
    with pytest.raises(FileNotFoundError):
        UserConfig.from_yaml("/nonexistent/path.yaml")


def test_config_empty(tmp_path: Path):
    import pytest
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        UserConfig.from_yaml(empty)


def test_config_default_user():
    import tempfile
    minimal = "portals: {}\nqueries: {}\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(minimal)
        config_path = f.name

    config = UserConfig.from_yaml(config_path)
    assert config.user == "default"

    Path(config_path).unlink()


def test_from_yaml_string():
    config = UserConfig.from_yaml_string(SAMPLE_YAML)
    assert config.user == "test_user"
    assert "jobs" in config.portals
    assert "python_jobs" in config.queries
    assert config.queries["cnc_jobs"].min_salary == 40000


def test_from_yaml_string_empty():
    import pytest
    with pytest.raises(ValueError, match="Empty YAML"):
        UserConfig.from_yaml_string("")


def test_from_yaml_string_invalid_yaml():
    import pytest
    with pytest.raises(Exception):
        UserConfig.from_yaml_string(": broken yaml :")
