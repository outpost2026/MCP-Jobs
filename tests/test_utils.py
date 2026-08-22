from mcp_jobs.models import Ad
from mcp_jobs.utils import fuzzy_key, normalize_url, strip_emoji

# Emoji test strings use \U escapes to avoid putting emoji
# literal in source code (encoding-safe per guardrails).
EMOJI_ROCKET = "\U0001f680"  # rocket
EMOJI_GLOBE = "\U0001f310"  # globe
EMOJI_MONEY = "\U0001f4b8"  # money


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


def test_normalize_url_strips_search_id():
    assert (
        normalize_url("https://www.jobs.cz/rpd/123/?searchId=abc123")
        == "https://www.jobs.cz/rpd/123/"
    )


def test_normalize_url_strips_rps():
    assert (
        normalize_url("https://www.prace.cz/nabidka/x/?rps=2077")
        == "https://www.prace.cz/nabidka/x/"
    )


def test_normalize_url_strips_search_id_profesia():
    assert (
        normalize_url("https://www.profesia.cz/prace/x/O1?search_id=abc")
        == "https://www.profesia.cz/prace/x/O1"
    )


def test_normalize_url_strips_utm_keeps_other_params():
    assert (
        normalize_url("https://www.jobs.cz/rpd/123/?utm_source=linkedin&page=2")
        == "https://www.jobs.cz/rpd/123/?page=2"
    )


def test_normalize_url_keeps_clean_url():
    assert (
        normalize_url("https://www.volnamista.cz/nabidka-prace/x/210961200")
        == "https://www.volnamista.cz/nabidka-prace/x/210961200"
    )


def test_normalize_url_empty():
    assert normalize_url("") == ""


def test_ad_post_init_normalizes_url():
    """Ad.__post_init__ canonicalizuje URL pred tim, nez je pouzit jako dedup klic."""
    ad = Ad(
        title="Job",
        url="https://www.jobs.cz/rpd/2001109039/?searchId=37cd4ab2",
        portal="jobs",
    )
    assert ad.url == "https://www.jobs.cz/rpd/2001109039/"


def test_ad_same_canonical_url_dedup():
    """Ruzne searchId na stejnem rpd = stejna canonical URL -> dedup funguje."""
    a1 = Ad(
        title="Senior AI Engineer",
        url="https://www.jobs.cz/rpd/2001265820/?searchId=7e79bbb0",
        portal="jobs",
    )
    a2 = Ad(
        title="Senior AI Engineer",
        url="https://www.jobs.cz/rpd/2001265820/?searchId=2b3bea27",
        portal="jobs",
    )
    assert a1.url == a2.url


def test_fuzzy_key_normalizes_diacritics():
    a1 = Ad(title="Servisni technik vytahu", url="https://x/1", portal="p")
    a2 = Ad(title="Servisní technik výtahů", url="https://x/2", portal="p")
    assert fuzzy_key(a1) == fuzzy_key(a2)


def test_fuzzy_key_normalizes_en_dash():
    a1 = Ad(title="Job", url="https://x/1", portal="p", location="Praha-Uhrineves")
    a2 = Ad(
        title="Job", url="https://x/2", portal="p", location="Praha \u2013 Uhrineves"
    )
    assert fuzzy_key(a1) == fuzzy_key(a2)


def test_fuzzy_key_normalizes_case_and_space():
    a1 = Ad(title="  Python   Developer ", url="https://x/1", portal="p")
    a2 = Ad(title="python developer", url="https://x/2", portal="p")
    assert fuzzy_key(a1) == fuzzy_key(a2)


def test_fuzzy_key_empty_fields():
    ad = Ad(title="Only title", url="https://x/1", portal="p")
    k = fuzzy_key(ad)
    assert k[0] == "only title"
    assert k[1] == ""  # company None -> ""
    assert len(k) == 2  # fuzzy_key returns (title, company) only
