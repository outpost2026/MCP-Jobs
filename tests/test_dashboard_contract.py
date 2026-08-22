"""Contract / purity / layer tests for dashboard modular package.

hSNR: each test checks ONE invariant. No fixtures, no DB, no Streamlit.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

_DASH = Path(__file__).resolve().parents[1] / "dashboard"

# ---------------------------------------------------------------------------
# 1. PURITY — metrics.py must not import streamlit
# ---------------------------------------------------------------------------


class _NoStreamlitVisitor(ast.NodeVisitor):
    def __init__(self):
        self.found: list[str] = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "streamlit":
                self.found.append(f"line {node.lineno}: import streamlit")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and "streamlit" in node.module:
            self.found.append(f"line {node.lineno}: from {node.module}")
        self.generic_visit(node)


def _ast_purity(mod_name: str) -> list[str]:
    src = (_DASH / f"{mod_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    v = _NoStreamlitVisitor()
    v.visit(tree)
    return v.found


class TestPurity:
    @pytest.mark.parametrize("module", ["metrics", "components/styling"])
    def test_no_streamlit(self, module: str):
        violations = _ast_purity(module)
        assert not violations, f"{module} imports streamlit: {violations}"


# ---------------------------------------------------------------------------
# 2. INTERFACE — function signatures & return hints
# ---------------------------------------------------------------------------


class TestInterface:
    def test_metrics_fetch_ads(self):
        from dashboard.metrics import fetch_ads

        sig = inspect.signature(fetch_ads)
        assert set(sig.parameters) == {
            "conn",
            "where_sql",
            "params",
            "min_completeness",
        }

    def test_metrics_velocity(self):
        from dashboard.metrics import velocity

        sig = inspect.signature(velocity)
        assert "days" in sig.parameters

    def test_filters_build_where(self):
        from dashboard.filters import build_where_clause

        sig = inspect.signature(build_where_clause)
        assert len(sig.parameters) == 0  # no required args

    def test_filters_init_filter_state(self):
        from dashboard.filters import init_filter_state

        sig = inspect.signature(init_filter_state)
        assert len(sig.parameters) == 0


# ---------------------------------------------------------------------------
# 3. LAYER — import direction enforcement
# ---------------------------------------------------------------------------

_LAYER_MAP = {
    "dashboard.tabs": [
        "dashboard.components",
        "dashboard.metrics",
        "dashboard.filters",
        "dashboard.components.styling",
    ],
    "dashboard.components": [],
    "dashboard.metrics": [],
    "dashboard.filters": [],
}


def _get_imports(module_path: Path) -> set[str]:
    src = module_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("dashboard"):
                imports.add(
                    node.module.split(".")[0]
                    + "."
                    + ".".join(node.module.split(".")[1:])
                )
    return imports


class TestLayers:
    def test_metrics_no_dashboard_imports(self):
        imports = _get_imports(_DASH / "metrics.py")
        bad = [
            i
            for i in imports
            if i.startswith("dashboard.tabs") or i.startswith("dashboard.components")
        ]
        assert not bad, f"metrics.py imports higher layers: {bad}"

    def test_filters_no_tab_imports(self):
        imports = _get_imports(_DASH / "filters.py")
        bad = [i for i in imports if i.startswith("dashboard.tabs")]
        assert not bad, f"filters.py imports tabs: {bad}"

    def test_components_no_tab_or_metrics(self):
        comp_dir = _DASH / "components"
        for f in comp_dir.glob("*.py"):
            imports = _get_imports(f)
            bad = [i for i in imports if "tabs" in i or "metrics" in i]
            assert not bad, f"{f.name} imports tabs/metrics: {bad}"
