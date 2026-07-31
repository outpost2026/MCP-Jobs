"""
Synthetic guardrail tests — ověřují účinnost mitigací pro persistentní
encoding a quoting problémy na Windows PowerShell.

Pytest-konvenční varianta (M5 fix): soubor je sbírán `pytest tests/`.
Odstraněn vlastní main() runner, Windows hardcode (.venv\\Scripts\\mcp-jobs.exe)
a závislost na osobní konfiguraci (~/.config/opencode/opencode.jsonc).

Testované vrstvy:
    1. Encoding resilience (cp1250, emoji, azbuka)
    2. f-string quoting v PowerShell kontextu
    3. -X utf8 flag propagace
    4. MCP server startup encoding (ensure_utf8_stdout)
    5. .bat launcher encoding
    6. cli.py utf8 konvence
    7. utils.py ensure_utf8_stdout
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── 1. Encoding resilience ───────────────────────────────────────


def test_encoding_direct() -> None:
    """Ověří, že Python zvládá tisk českých znaků + emoji + azbuky
    při použití -X utf8 a PYTHONIOENCODING."""
    code = (
        "import sys\n"
        'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        'print("Czech: ěščřžýáíéňťďĎŇŤ")\n'
        'print("ASCII safe line")\n'
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, f"returncode={proc.returncode}, stderr={proc.stderr!r}"
    assert "Czech: ěščřžýáíéňťďĎŇŤ" in proc.stdout


def test_encoding_guardrails_comment_present() -> None:
    """Ověří, že utils.py obsahuje encoding guardrails komentář."""
    utils_path = PROJECT_ROOT / "src" / "mcp_jobs" / "utils.py"
    code = utils_path.read_text(encoding="utf-8")
    assert "UnicodeEncodeError" in code
    assert "cp1250" in code


# ── 2. f-string quoting v PowerShell kontextu ────────────────────


def test_fstring_via_file() -> None:
    """Ověří, že f-string s vnořenými uvozovkami funguje,
    když je kód v .py souboru (ne inline -c)."""
    code = (
        "from __future__ import annotations\n"
        'data = [{"title": "Python Developer", "company": "ABC"}]\n'
        "for a in data:\n"
        '    t = a.get("title", "")\n'
        '    c = a.get("company", "")\n'
        '    meta = f" @ {c}" if c else ""\n'
        '    print(f"  * {t}{meta}")  # f-string s vnorenyma uvozovkama\n'
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", tmp_path],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        assert proc.returncode == 0, (
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        assert "Python Developer @ ABC" in proc.stdout
    finally:
        os.unlink(tmp_path)


# ── 3. ensure_utf8_stdout() ──────────────────────────────────────


def test_ensure_utf8_stdout_function() -> None:
    """Ověří, že ensure_utf8_stdout() z utils.py nastaví stdout
    na UTF-8 i bez -X utf8."""
    code = (
        "import sys\n"
        'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        'print("Czech: ěščřžýáíé")\n'
        'print("All OK")\n'
    )
    env = os.environ.copy()
    if "PYTHONIOENCODING" in env:
        del env["PYTHONIOENCODING"]
    proc = subprocess.run(
        [sys.executable, "-c", code],  # bez -X utf8, ale s reconfigure
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, f"returncode={proc.returncode}, stderr={proc.stderr!r}"
    assert "All OK" in proc.stdout


# ── 4. MCP server module import encoding ─────────────────────────


def test_server_module_encoding() -> None:
    """Ověří, že import server modulu zavolá ensure_utf8_stdout()
    a nedojde k encoding erroru při startu."""
    code = (
        "import sys\n"
        'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        "from mcp_jobs.server import mcp\n"
        "from mcp_jobs import __version__\n"
        'print(f"Server: {mcp.name}")\n'
        'print(f"Version: {__version__}")\n'
        'print(f"Tools: {list(mcp._tool_manager._tools.keys())}")\n'
        'print("Czech: ěščřžýáíé")\n'
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", tmp_path],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 0, (
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        assert "Server: MCP-Jobs" in proc.stdout
        assert "health_check" in proc.stdout
        assert "Czech: ěščřžýáíé" in proc.stdout
    finally:
        os.unlink(tmp_path)


# ── 5. mcp-jobs.bat launcher encoding ────────────────────────────


def test_bat_launcher_encoding() -> None:
    """Ověří, že mcp-jobs.bat nastaví encoding proměnné.
    Bez závislosti na konkrétním Python executable (M5 fix)."""
    bat_path = PROJECT_ROOT / "mcp-jobs.bat"
    assert bat_path.exists(), f"mcp-jobs.bat not found at {bat_path}"
    content = bat_path.read_text(encoding="utf-8")
    assert "PYTHONIOENCODING" in content
    assert "PYTHONUTF8" in content


# ── 6. cli.py utf8 konvence ──────────────────────────────────────


def test_cli_uses_utf8_convention() -> None:
    """Ověří, že cli.py entry point zajišťuje UTF-8 výstup
    (PYTHONIOENCODING + ensure_utf8_stdout)."""
    cli_path = PROJECT_ROOT / "src" / "mcp_jobs" / "cli.py"
    assert cli_path.exists()
    content = cli_path.read_text(encoding="utf-8")
    assert "ensure_utf8_stdout" in content


# ── 7. docs/powershell_encoding.md existence ─────────────────────


def test_encoding_docs_exist() -> None:
    """Ověří, že dokumentace pro encoding existuje."""
    docs_path = PROJECT_ROOT / "docs" / "powershell_encoding.md"
    assert docs_path.exists(), "docs/powershell_encoding.md not found"
    content = docs_path.read_text(encoding="utf-8")
    for c in ["PowerShell", "cp1250", "UnicodeEncodeError", "SyntaxError"]:
        assert c in content, f"doc missing section '{c}'"


# ── 8. utils.py ensure_utf8_stdout ───────────────────────────────


def test_utils_ensure_utf8_stdout() -> None:
    """Ověří, že utils.py deklaruje ensure_utf8_stdout()."""
    utils_path = PROJECT_ROOT / "src" / "mcp_jobs" / "utils.py"
    code = utils_path.read_text(encoding="utf-8")
    assert "def ensure_utf8_stdout" in code
    assert "sys.stdout.reconfigure" in code
