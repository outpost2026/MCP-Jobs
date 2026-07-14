"""
Test that the exclude mechanism works correctly in the pipeline.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mcp_jobs.matcher import has_exclude_terms

tests = [
    ("Hledám nové zakázky elektro", ["hledam praci"], "", "hledam praci in title"),
    ("Hledám práci jako elektrikář", ["hledam praci"], "", "hledam praci SHOULD match"),
    ("Python developer - hledáme kolegu", ["hledame kolegu", "agentura"], "Chybí nám pythonista", "hledame kolegu SHOULD match"),
    ("CNC frézař - Nábor", ["nabor"], "", "nabor SHOULD match"),
    ("Python developer senior", ["agentura", "firmy"], "", "clean title - NO exclude"),
    ("Autoelektrikář Škoda Auto", ["autoskola", "revize"], "", "clean title - NO exclude"),
    ("Nabízím elektroinstalace", ["nabizim", "nabizime"], "", "nabizim SHOULD match"),
    ("Seřizovač CNC strojů", ["agentura", "personalni", "pronajem"], "Hledáme zkušeného seřizovače", "clean - NO exclude"),
    ("Hledáme programátora do týmu", ["hledame kolegu", "agentura"], "", "genuine posting - NO exclude (no 'kolegu' in title)"),
    ("Prodám CNC frézku", ["prodavame", "prodavame"], "", "prodavame vs prodam - test"),
]

print("Testing has_exclude_terms:")
print("=" * 60)
all_pass = True
for title, exclude, desc, note in tests:
    result = has_exclude_terms(title, exclude, description=desc)
    expected = "SHOULD match" in note
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"  [{status}] {note}")
    print(f"    title: {title}")
    print(f"    exclude: {exclude}")
    print(f"    result: {result} (expected {expected})")
    print()

print(f"\nAll tests passed: {all_pass}")
sys.exit(0 if all_pass else 1)
