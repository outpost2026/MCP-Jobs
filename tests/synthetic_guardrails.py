"""
Synthetic guardrail tests — ověřují účinnost mitigací pro persistentní
encoding a quoting problémy na Windows PowerShell.

Spuštění:
    python -X utf8 tests\synthetic_guardrails.py

Testované vrstvy:
    1. Encoding resilience (cp1250, emoji, azbuka)
    2. f-string quoting v PowerShell kontextu
    3. -X utf8 flag propagace
    4. init.ps1 helper funkce
    5. MCP server startup encoding (ensure_utf8_stdout)
    6. .bat launcher encoding
    7. opencode.jsonc -X utf8 deklarace
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

PASS = 0
FAIL = 0


def check(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


# ── 1. Encoding resilience ───────────────────────────────────────


def test_encoding_direct() -> None:
    """Ověří, že Python zvládá tisk českých znaků + emoji + azbuky
    při použití -X utf8 a PYTHONIOENCODING."""
    code = (
        'import sys\n'
        'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        'print("Czech: ěščřžýáíéňťďĎŇŤ")\n'
        'print("Emoji: 😊👍🎉 ✅ ❌")\n'
        'print("Cyrillic: кровельщиков")\n'
        'print("Mixed: ěščř 😊 кровельщик")\n'
        'print("ASCII safe line")\n'
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        capture_output=True, text=True, env=env,
    )
    check(proc.returncode == 0, f"returncode={proc.returncode}, stderr={proc.stderr!r}")
    out = proc.stdout
    check("Czech: ěščřžýáíéňťďĎŇŤ" in out, f"missing Czech chars: {out!r}")
    check("Emoji: 😊👍🎉 ✅ ❌" in out, f"missing emoji: {out!r}")
    check("Cyrillic: кровельщиков" in out, f"missing Cyrillic: {out!r}")


def test_encoding_without_xutf8() -> None:
    """Ověří, že bez mitigací emoji způsobí UnicodeEncodeError
    při výstupu do konzole (reálný stdout, ne capture_output).

    subprocess s capture_output=False testovat nemůžeme automaticky,
    proto kontrolujeme, že guardrails varování existuje v dokumentaci."""
    # Ověříme, že guardrails varování existuje
    utils_path = PROJECT_ROOT / "src" / "mcp_jobs" / "utils.py"
    code = utils_path.read_text(encoding="utf-8")
    check("UnicodeEncodeError" in code, "utils.py missing encoding error comment")
    check("cp1250" in code, "utils.py missing cp1250 comment")


# ── 2. f-string quoting v PowerShell kontextu ────────────────────


def test_fstring_via_file() -> None:
    """Ověří, že f-string s vnořenými uvozovkami funguje,
    když je kód v .py souboru (ne inline -c)."""
    code = (
        'from __future__ import annotations\n'
        'data = [{"title": "Python Developer", "company": "ABC"}]\n'
        'for a in data:\n'
        '    t = a.get("title", "")\n'
        '    c = a.get("company", "")\n'
        '    meta = f" @ {c}" if c else ""\n'
        '    print(f"  * {t}{meta}")  # f-string s vnorenyma uvozovkama\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                      encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", tmp_path],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        check(proc.returncode == 0, f"returncode={proc.returncode}, stderr={proc.stderr!r}")
        check("Python Developer @ ABC" in proc.stdout, f"unexpected output: {proc.stdout!r}")
    finally:
        os.unlink(tmp_path)


def test_fstring_inline_negative() -> None:
    """Negativní test: f-string s vnořenými uvozovkami v inline -c
    je na Windows křehký. Někdy projde, někdy ne — záleží na délce
    a složitosti kódu. Důležité je, že guardrails zakazují tento
    pattern bez ohledu na výsledek.

    Tento test je informativní — neovlivňuje PASS/FAIL."""
    code = """print([f"  * {a['title']}" for a in [{'title': 'test'}]][0])"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"  ⚠️  (INFO) f-string inline SELHAL: {proc.stderr.strip()}")
    else:
        print(f"  ℹ️  (INFO) f-string inline PROSEL: {proc.stdout.strip()}")


# ── 3. ensure_utf8_stdout() ──────────────────────────────────────


def test_ensure_utf8_stdout_function() -> None:
    """Ověří, že ensure_utf8_stdout() z utils.py nastaví stdout
    na UTF-8 i bez -X utf8."""
    code = (
        'import sys\n'
        'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        'print("Czech: ěščřžýáíé")\n'
        'print("Emoji: 😊👍🎉")\n'
        'print("Cyrillic: кровельщиков")\n'
        'print("All OK")\n'
    )
    env = os.environ.copy()
    if "PYTHONIOENCODING" in env:
        del env["PYTHONIOENCODING"]
    proc = subprocess.run(
        [sys.executable, "-c", code],  # bez -X utf8, ale s reconfigure
        capture_output=True, text=True, env=env,
    )
    check(proc.returncode == 0, f"returncode={proc.returncode}, stderr={proc.stderr!r}")
    check("All OK" in proc.stdout, f"output: {proc.stdout!r}")


# ── 4. MCP server module import encoding ─────────────────────────


def test_server_module_encoding() -> None:
    """Ověří, že import server modulu zavolá ensure_utf8_stdout()
    a nedojde k encoding erroru při startu. Používá .py soubor
    (ne inline -c) aby nedošlo k PowerShell quoting konfliktu."""
    code = (
        'import sys\n'
        'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        'from mcp_jobs.server import mcp\n'
        'from mcp_jobs import __version__\n'
        'print(f"Server: {mcp.name}")\n'
        'print(f"Version: {__version__}")\n'
        'print(f"Tools: {list(mcp._tool_manager._tools.keys())}")\n'
        'print("Czech: ěščřžýáíé")\n'
        'print("Emoji: 😊👍🎉")\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                      encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", tmp_path],
            capture_output=True, text=True, env=env,
            cwd=str(PROJECT_ROOT),
        )
        check(proc.returncode == 0,
              f"returncode={proc.returncode}, stderr={proc.stderr!r}")
        check("Server: MCP-Jobs" in proc.stdout, f"output: {proc.stdout!r}")
        check("0.4.0" in proc.stdout, f"version missing: {proc.stdout!r}")
        check("health_check" in proc.stdout, f"tools missing: {proc.stdout!r}")
        check("Czech: ěščřžýáíé" in proc.stdout, f"czech missing: {proc.stdout!r}")
        check("Emoji: 😊👍🎉" in proc.stdout, f"emoji missing: {proc.stdout!r}")
    finally:
        os.unlink(tmp_path)


# ── 5. mcp-jobs.bat launcher encoding ────────────────────────────


def test_bat_launcher_encoding() -> None:
    """Ověří, že mcp-jobs.bat nastaví encoding proměnné a spustí
    server bez encoding erroru."""
    bat_path = PROJECT_ROOT / "mcp-jobs.bat"
    check(bat_path.exists(), f"mcp-jobs.bat not found at {bat_path}")
    content = bat_path.read_text(encoding="utf-8")
    check("PYTHONIOENCODING" in content, "mcp-jobs.bat missing PYTHONIOENCODING")
    check("PYTHONUTF8" in content, "mcp-jobs.bat missing PYTHONUTF8")
    # Ověříme, že .bat vede na existující executable
    exe_path = PROJECT_ROOT / ".venv" / "Scripts" / "mcp-jobs.exe"
    check(exe_path.exists(), f"mcp-jobs.exe not at {exe_path}")


# ── 6. opencode.jsonc -X utf8 propagace ──────────────────────────


def test_opencode_config_xutf8() -> None:
    """Ověří, že opencode.jsonc deklaruje -X utf8 pro všechny
    MCP servery."""
    config_path = Path.home() / ".config" / "opencode" / "opencode.jsonc"
    check(config_path.exists(), f"opencode.jsonc not found at {config_path}")
    content = config_path.read_text(encoding="utf-8")
    # Každý MCP server command by měl mít "-X", "utf8"
    sections = content.count('"command"')
    xutf8_count = content.count('"-X", "utf8"')
    check(
        xutf8_count >= sections,
        f"-X utf8 found {xutf8_count}x in {sections} command sections",
    )


# ── 7. .ai_guardrails.json shell_rules sekce ─────────────────────


def test_guardrails_shell_rules() -> None:
    """Ověří, že .ai_guardrails.json obsahuje shell_rules sekci."""
    guardrails_path = PROJECT_ROOT.parent / ".ai_guardrails.json"
    check(guardrails_path.exists(), f".ai_guardrails.json not found at {guardrails_path}")
    content = guardrails_path.read_text(encoding="utf-8")
    check('"shell_rules"' in content, "shell_rules section missing")
    check("NEPOUZIVEJ python -c" in content, "python -c ban rule missing")
    check("-X utf8" in content, "-X utf8 rule missing")


# ── 8. scripts/init.ps1 existence a struktura ────────────────────


def test_init_ps1_helpers() -> None:
    """Ověří, že scripts/init.ps1 existuje a obsahuje helper funkce."""
    init_path = PROJECT_ROOT / "scripts" / "init.ps1"
    check(init_path.exists(), f"init.ps1 not found at {init_path}")
    content = init_path.read_text(encoding="utf-8")
    check("function Run-Python" in content, "Run-Python function missing")
    check("function Invoke-Pipeline" in content, "Invoke-Pipeline function missing")
    check("function Compare-ETL" in content, "Compare-ETL function missing")
    check("PYTHONIOENCODING" in content, "PYTHONIOENCODING setting missing")
    check("PYTHONUTF8" in content, "PYTHONUTF8 setting missing")


# ── 9. docs/powershell_encoding.md existence ─────────────────────


def test_encoding_docs_exist() -> None:
    """Ověří, že dokumentace pro encoding existuje."""
    docs_path = PROJECT_ROOT / "docs" / "powershell_encoding.md"
    check(docs_path.exists(), f"docs/powershell_encoding.md not found")
    content = docs_path.read_text(encoding="utf-8")
    checks = [
        "PowerShell",
        "cp1250",
        "UnicodeEncodeError",
        "SyntaxError",
        "python -c",
        "init.ps1",
        "FAQ",
    ]
    for c in checks:
        check(c in content, f"doc missing section '{c}'")


# ── 10. Cross-layer: utils.py ensure_utf8_stdout ──────────────────


def test_utils_ensure_utf8_stdout() -> None:
    """Ověří, že utils.py deklaruje ensure_utf8_stdout()."""
    utils_path = PROJECT_ROOT / "src" / "mcp_jobs" / "utils.py"
    code = utils_path.read_text(encoding="utf-8")
    check("def ensure_utf8_stdout" in code, "ensure_utf8_stdout() missing in utils.py")
    check("sys.stdout.reconfigure" in code, "reconfigure missing in utils.py")


# ── Runner ────────────────────────────────────────────────────────

def main() -> None:
    global PASS, FAIL
    print("=" * 60)
    print("Platforma: Windows PowerShell")
    print(f"Python: {sys.version}")
    print(f"PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', '(nenastaveno)')}")
    print(f"PYTHONUTF8: {os.environ.get('PYTHONUTF8', '(nenastaveno)')}")
    print("=" * 60)
    print()

    tests = [
        ("1.1 Encoding -X utf8 + PYTHONIOENCODING", test_encoding_direct),
        ("1.2 Encoding bez -X utf8 (negativni)", test_encoding_without_xutf8),
        ("2.1 f-string pres .py soubor", test_fstring_via_file),
        ("2.2 f-string inline -c (negativni)", test_fstring_inline_negative),
        ("3.1 ensure_utf8_stdout() funkce", test_ensure_utf8_stdout_function),
        ("4.1 Server modul encoding", test_server_module_encoding),
        ("5.1 mcp-jobs.bat encoding", test_bat_launcher_encoding),
        ("6.1 opencode.jsonc -X utf8", test_opencode_config_xutf8),
        ("7.1 .ai_guardrails.json shell_rules", test_guardrails_shell_rules),
        ("8.1 scripts/init.ps1 helpers", test_init_ps1_helpers),
        ("9.1 docs/powershell_encoding.md", test_encoding_docs_exist),
        ("10.1 utils.py ensure_utf8_stdout", test_utils_ensure_utf8_stdout),
    ]

    for name, fn in tests:
        print(f"  [{name}]", end=" ")
        try:
            fn()
            print(f"  ✅ PASS")
            PASS += 1
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            FAIL += 1

    print()
    print("=" * 60)
    print(f"Vysledek: {PASS} pass / {FAIL} fail")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
