"""Styling helpers for MCP-Jobs dashboard."""

from __future__ import annotations


def completeness_color(val: str) -> str:
    """CSS color for completeness label — green/orange/red."""
    try:
        n = int(val.replace("%", ""))
    except (ValueError, AttributeError):
        return ""
    if n >= 83:
        return "background-color: #064E3B; color: #10B981"
    if n >= 66:
        return "background-color: #78350F; color: #F59E0B"
    return "background-color: #4C0519; color: #F43F5E"
