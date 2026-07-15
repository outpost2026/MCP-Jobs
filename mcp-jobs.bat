@echo off
REM MCP-Jobs server launcher
REM Encoding fix: prevents cp1250 UnicodeEncodeError on Windows console
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
"%~dp0.venv\Scripts\mcp-jobs.exe" %*
