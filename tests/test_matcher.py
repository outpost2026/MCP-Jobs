from mcp_jobs.matcher import Matcher, matches_ad, evaluate_boolean, parse_boolean
from mcp_jobs.models import Ad


# ── Old Matcher backward compat ────────────────────────────────────────

def test_and_logic():
    assert Matcher.match_keywords("Python Developer", "python+developer") == (True, "python+developer")


def test_word_boundary_title():
    assert Matcher.match_keywords("Elektro CNC operátor", "cnc") == (True, "cnc")
    assert Matcher.match_keywords("elektrocnc", "cnc") == (False, "")


def test_exclude():
    assert Matcher.has_exclude("Senior Test Engineer", "senior|lead") is True
    assert Matcher.has_exclude("Test Engineer", "senior|lead") is False


def test_case_insensitive():
    assert Matcher.match_keywords("PYTHON DEVELOPER", "python") == (True, "python")
    assert Matcher.match_keywords("Python Developer", "PYTHON") == (True, "PYTHON")


def test_empty_query():
    assert Matcher.match_keywords("Python Developer", "") == (False, "")


def test_multiple_and_terms():
    assert Matcher.match_keywords("Python Django Developer", "python+django") == (True, "python+django")
    assert Matcher.match_keywords("Python Developer", "python+django") == (False, "")


def test_exclude_pipe():
    assert Matcher.has_exclude("Lead Python Developer", "junior|lead") is True
    assert Matcher.has_exclude("Python Developer", "junior|lead") is False


# ── New boolean matcher ────────────────────────────────────────────────

def test_boolean_simple_word():
    assert evaluate_boolean("Python Developer", "python") is True
    assert evaluate_boolean("Java Developer", "python") is False


def test_boolean_word_boundary():
    assert evaluate_boolean("CNC fréza", "cnc") is True
    assert evaluate_boolean("elektrocnc", "cnc") is False


def test_boolean_and():
    assert evaluate_boolean("Python Developer", "python AND developer") is True
    assert evaluate_boolean("Java Developer", "python AND developer") is False


def test_boolean_or():
    assert evaluate_boolean("Python Developer", "python OR java") is True
    assert evaluate_boolean("Java Developer", "python OR java") is True
    assert evaluate_boolean("C++ Developer", "python OR java") is False


def test_boolean_not():
    assert evaluate_boolean("Senior Test Engineer", "test NOT senior") is False
    assert evaluate_boolean("Test Engineer", "test NOT senior") is True


def test_boolean_parentheses():
    expr = "(python OR java) AND developer NOT senior"
    assert evaluate_boolean("Python Developer", expr) is True
    assert evaluate_boolean("Senior Java Developer", expr) is False
    assert evaluate_boolean("Python Junior", expr) is False


def test_boolean_case_insensitive():
    assert evaluate_boolean("PYTHON DEVELOPER", "python") is True
    assert evaluate_boolean("Python Developer", "PYTHON") is True


def test_boolean_empty():
    assert evaluate_boolean("Python Developer", "") is True
    assert evaluate_boolean("Python Developer", "   ") is True


def test_boolean_matches_ad():
    ad1 = Ad(title="Python Developer", url="http://x", portal="jobs", company="Acme Corp")
    ad2 = Ad(title="Java Developer", url="http://y", portal="jobs", company="Acme Corp")

    assert matches_ad(ad1, "python AND developer") is True
    assert matches_ad(ad2, "python AND developer") is False


def test_boolean_matches_ad_description():
    ad = Ad(title="Název pozice", url="http://x", portal="jobs",
            description="Hledáme autoelektrikáře do týmu")
    assert matches_ad(ad, "autoelektrikáře") is True
    assert matches_ad(ad, "autoelektrikáře AND python") is False


def test_boolean_matches_ad_company():
    ad = Ad(title="Engineer", url="http://x", portal="jobs", company="Siemens")
    assert matches_ad(ad, "siemens") is True
    assert matches_ad(ad, "siemens AND engineer") is True


def test_precedence_and_over_or():
    assert evaluate_boolean("Python", "python OR java AND developer") is True
    assert evaluate_boolean("Java Developer", "python OR java AND developer") is True
    assert evaluate_boolean("Java Junior", "python OR java AND developer") is False


def test_complex_nested():
    expr = "(python OR java OR go) AND (developer OR engineer) NOT (senior OR lead)"
    assert evaluate_boolean("Python Developer", expr) is True
    assert evaluate_boolean("Senior Java Engineer", expr) is False
    assert evaluate_boolean("Go Engineer", expr) is True
    assert evaluate_boolean("Lead Python Developer", expr) is False
    assert evaluate_boolean("Python Tester", expr) is False


# ── Diacritics normalization ────────────────────────────────────────

def test_strip_diacritics():
    from mcp_jobs.matcher import strip_diacritics
    assert strip_diacritics("programátor") == "programator"
    assert strip_diacritics("\u010d\u010f\u011b\u0148\u0159\u0161\u0165\u017e") == "cdenrstz"
    assert strip_diacritics("\u013e\u0161\u010d\u0165\u017e\u00fd\u00e1\u00ed\u00e9\u00fa\u00f4\u00e4\u0148") == "lsctzyaieuoan"
    assert strip_diacritics("ASCII") == "ASCII"
    assert strip_diacritics("") == ""


def test_boolean_diacritics_in_text():
    assert evaluate_boolean("Programátor Python", "programator") is True
    assert evaluate_boolean("Programator Python", "programátor") is True


def test_boolean_diacritics_in_query():
    assert evaluate_boolean("Programátor Python", "programátor") is True
    assert evaluate_boolean("Programator Python", "programator") is True


def test_boolean_diacritics_and():
    assert evaluate_boolean("Programátor Python", "programátor AND python") is True
    assert evaluate_boolean("Programátor Java", "programator AND python") is False


def test_boolean_diacritics_or():
    assert evaluate_boolean("Programátor", "programator OR vyvojar") is True
    assert evaluate_boolean("Vývojář", "programator OR vyvojar") is True
    assert evaluate_boolean("Účetní", "programator OR vyvojar") is False


def test_boolean_diacritics_word_boundary():
    assert evaluate_boolean("ňářa", "nara") is True
    assert evaluate_boolean("blanář", "nara") is False


def test_boolean_diacritics_not():
    assert evaluate_boolean("Junior programátor", "programator NOT junior") is False
    assert evaluate_boolean("Programátor", "programator NOT junior") is True


def test_boolean_diacritics_matches_ad():
    from mcp_jobs.matcher import matches_ad
    ad = Ad(title="Programátor Python", url="http://x", portal="jobs")
    assert matches_ad(ad, "programator AND python") is True
    assert matches_ad(ad, "programator AND java") is False


def test_has_exclude_diacritics():
    assert Matcher.has_exclude("Senior vývojář", "senior") is True
    assert Matcher.has_exclude("Junior vývojář", "senior") is False
    assert Matcher.has_exclude("Vedoucí vývojář", "vedoucí") is True
