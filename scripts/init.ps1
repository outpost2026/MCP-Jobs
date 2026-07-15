<#
.SYNOPSIS
    MCP-Jobs project initialization — encoding + helper functions.
.DESCRIPTION
    Dot-source this script at session start to:
    1. Set encoding environment variables (prevents cp1250 UnicodeEncodeError)
    2. Define helper wrappers for pipeline commands (prevents f-string quoting issues)
    
    Usage:
        . .\scripts\init.ps1         # dot-source from repo root
        scripts\init.ps1             # or run as script (sets env only)

    Run this ONCE per PowerShell session.
#>

# ── Encoding: prevent cp1250 UnicodeEncodeError ───────────────────
# Root cause: Windows console uses cp1250, Python uses UTF-8.
# $env:PYTHONIOENCODING forces Python's stdout/stderr/stdin to UTF-8.
# $env:PYTHONUTF8 = 1 tells Python 3.7+ to assume UTF-8 everywhere.
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Write-Host "[init.ps1] PYTHONIOENCODING=utf-8, PYTHONUTF8=1" -ForegroundColor Green

# ── Helper: run Python script from project ────────────────────────
# Usage:   Run-Python scripts\my_script.py [args...]
# Purpose: Avoids fragile python -c "..." inline code in PowerShell.
#           Inline f-strings with nested quotes cause SyntaxError
#           because Windows command-line parsing splits arguments
#           before Python sees them.
function Run-Python {
    param(
        [Parameter(Mandatory, Position=0)]
        [string]$Script,
        [Parameter(ValueFromRemainingArguments)]
        [string[]]$Args
    )
    $project_root = Split-Path -Parent $PSScriptRoot
    $script_path = Join-Path $project_root $Script
    if (-not (Test-Path $script_path)) {
        Write-Error "Script not found: $script_path"
        return
    }
    & "$project_root\.venv\Scripts\python.exe" -X utf8 $script_path @Args
}

# ── Helper: run ETL pipeline with timestamped output ─────────────
# Usage:   Invoke-Pipeline
function Invoke-Pipeline {
    Run-Python scripts\run_etl.py
}

# ── Helper: compare two ETL runs ─────────────────────────────────
# Usage:   Compare-ETL [-New <path>] [-Old <path>]
function Compare-ETL {
    param(
        [string]$New = "",
        [string]$Old = ""
    )
    $project_root = Split-Path -Parent $PSScriptRoot
    $output_dir = Join-Path $project_root "output"
    
    if (-not $New) {
        $latest = Get-ChildItem -Path $output_dir -Filter "etl_2026*.json" |
            Where-Object { $_.Name -notmatch "latest|metrics" } |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $New = $latest.FullName
    }
    if (-not $Old) {
        $prev = Get-ChildItem -Path $output_dir -Filter "etl_2026*.json" |
            Where-Object { $_.Name -notmatch "latest|metrics" } |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1 -Skip 1
        $Old = $prev.FullName
    }
    
    Write-Host "Comparing:" -ForegroundColor Cyan
    Write-Host "  New: $New"
    Write-Host "  Old: $Old"
    
    # Use a temp Python script to avoid inline quoting issues
    $tmpScript = Join-Path ([System.IO.Path]::GetTempPath()) "compare_etl.py"
    @"
import json
from pathlib import Path

new_p = Path(r"$New")
old_p = Path(r"$Old")
current = json.loads(new_p.read_text(encoding="utf-8"))
previous = json.loads(old_p.read_text(encoding="utf-8"))

print(f"Predchozi: {old_p.name} ({previous['timestamp']}, {previous['total_matched']} ads)")
print(f"Aktualni:  {new_p.name} ({current['timestamp']}, {current['total_matched']} ads)")
print()

prev_urls = {a['url'] for r in previous['results'].values() for a in r}
new_total = 0
for qname, ads in current['results'].items():
    new_ads = [a for a in ads if a['url'] not in prev_urls]
    if not new_ads: continue
    print(f"--- {qname}: {len(new_ads)} novych ---")
    for a in new_ads:
        t = a.get('title',''); c = a.get('company','')
        l = a.get('location',''); s = a.get('salary',''); u = a.get('url','')
        meta = ''
        if c: meta += f' @ {c}'
        if l: meta += f' [{l}]'
        if s: meta += f' {s}'
        print(f'  * {t}{meta}')
        print(f'    {u}')
    new_total += len(new_ads)
print(f"Celkem novych: {new_total} z {current['total_matched']}")
"@ | Set-Content -Path $tmpScript -Encoding UTF8
    
    $project_root = Split-Path -Parent $PSScriptRoot
    & "$project_root\.venv\Scripts\python.exe" -X utf8 $tmpScript
    
    Remove-Item $tmpScript -Force -ErrorAction SilentlyContinue
}

Write-Host "[init.ps1] Helpers: Run-Python, Invoke-Pipeline, Compare-ETL" -ForegroundColor Green
