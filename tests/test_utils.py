from mcp_jobs.utils import strip_emoji

# Emoji test strings use \U escapes to avoid putting emoji
# literal in source code (encoding-safe per guardrails).
EMOJI_ROCKET = "\U0001F680"  # rocket
EMOJI_GLOBE = "\U0001F310"   # globe
EMOJI_MONEY = "\U0001F4B8"   # money


def test_strip_emoji_removes_emoji():
    assert strip_emoji(f"Hello {EMOJI_GLOBE}") == "Hello "


def test_strip_emoji_preserves_ascii():
    assert strip_emoji("Hello World") == "Hello World"


def test_strip_emoji_preserves_czech():
    assert strip_emoji("Programtor") == "Programtor"
    assert strip_emoji("elostnih") == "elostnih"


def test_strip_emoji_empty():
    assert strip_emoji("") == ""
    assert strip_emoji("  ") == "  "


def test_strip_emoji_mixed():
    text = f"Python Developer {EMOJI_ROCKET} {EMOJI_MONEY}"
    result = strip_emoji(text)
    assert "Python Developer" in result
    assert EMOJI_ROCKET not in result
    assert EMOJI_MONEY not in result


def test_strip_emoji_preserves_czech_with_diacritics():
    text = "Programtor v jazyce Python"
    assert strip_emoji(text) == text
