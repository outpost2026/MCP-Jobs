from __future__ import annotations

import functools
import logging
import re
import unicodedata
from typing import Optional

from .models import Ad

logger = logging.getLogger(__name__)


def strip_diacritics(text: str) -> str:
    """Remove diacritics (accents) from text, preserving base ASCII letters.
    
    'programátor' -> 'programator', 'č' -> 'c', 'ň' -> 'n', etc.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))

# ── Tokenizer ──────────────────────────────────────────────────────────

_TOKEN_SPEC = [
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("AND", r"\bAND\b"),
    ("OR", r"\bOR\b"),
    ("NOT", r"\bNOT\b"),
    ("WORD", r"[^\s()]+"),
]

_TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC), re.IGNORECASE)


def _tokenize(text: str) -> list[tuple[str, str]]:
    return [(m.lastgroup, m.group()) for m in _TOKEN_RE.finditer(text)]


# ── AST nodes ──────────────────────────────────────────────────────────

class _Node:
    def evaluate(self, text: str) -> bool:
        raise NotImplementedError


class _Word(_Node):
    def __init__(self, word: str):
        self.word = word

    def evaluate(self, text: str) -> bool:
        normalized_word = strip_diacritics(self.word.lower())
        normalized_text = strip_diacritics(text.lower())
        return bool(re.search(r"\b" + re.escape(normalized_word) + r"\b", normalized_text))


class _Not(_Node):
    def __init__(self, child: _Node):
        self.child = child

    def evaluate(self, text: str) -> bool:
        return not self.child.evaluate(text)


class _And(_Node):
    def __init__(self, left: _Node, right: _Node):
        self.left = left
        self.right = right

    def evaluate(self, text: str) -> bool:
        return self.left.evaluate(text) and self.right.evaluate(text)


class _Or(_Node):
    def __init__(self, left: _Node, right: _Node):
        self.left = left
        self.right = right

    def evaluate(self, text: str) -> bool:
        return self.left.evaluate(text) or self.right.evaluate(text)


# ── Recursive-descent parser ───────────────────────────────────────────

class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("EOF", "")

    def consume(self, expected: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if expected and tok[0] != expected:
            raise ValueError(f"Expected {expected}, got {tok[0]}")
        self.pos += 1
        return tok

    def parse(self) -> _Node:
        node = self._parse_expr()
        if self.peek()[0] != "EOF":
            raise ValueError(f"Unexpected trailing token: {self.peek()}")
        return node

    def _parse_expr(self) -> _Node:
        left = self._parse_term()
        while self.peek()[0] == "OR":
            self.consume()
            right = self._parse_term()
            left = _Or(left, right)
        return left

    def _parse_term(self) -> _Node:
        left = self._parse_factor()
        while self.peek()[0] == "AND":
            self.consume()
            right = self._parse_factor()
            left = _And(left, right)
        return left

    def _parse_factor(self) -> _Node:
        if self.peek()[0] == "NOT":
            self.consume()
            child = self._parse_atom()
            return _Not(child)
        return self._parse_atom()

    def _parse_atom(self) -> _Node:
        tok = self.peek()
        if tok[0] == "LPAREN":
            self.consume()
            node = self._parse_expr()
            self.consume("RPAREN")
            return node
        if tok[0] == "WORD":
            self.consume()
            return _Word(tok[1])
        raise ValueError(f"Unexpected token: {tok}")


@functools.lru_cache(maxsize=128)
def parse_boolean(expression: str) -> _Node:
    tokens = _tokenize(expression)
    parser = _Parser(tokens)
    return parser.parse()


def validate_boolean(expression: str) -> bool:
    """Validate boolean expression syntax. Returns True if valid, False + log if malformed."""
    if not expression or not expression.strip():
        return True
    try:
        parse_boolean(expression)
        return True
    except (ValueError, IndexError) as e:
        logger.warning("Malformed boolean expression %r: %s", expression, e)
        return False


def evaluate_boolean(text: str, expression: str) -> bool:
    if not expression or not expression.strip():
        return True
    try:
        ast = parse_boolean(expression)
        return ast.evaluate(text)
    except (ValueError, IndexError) as e:
        logger.warning("Boolean parse error for %r: %s", expression, e)
        return False


def matches_ad(ad: Ad, boolean_query: str) -> bool:
    text = " ".join(filter(None, [ad.title, ad.description, ad.company]))
    return evaluate_boolean(text, boolean_query)


def has_exclude_terms(
    title: str,
    exclude_terms: list[str],
    description: str = "",
) -> bool:
    """Check if any exclude term matches in title or description.
    
    Uses word boundaries on title, substring matching on description
    (Czech inflection handling — 'autoelektrikáře' matches 'autoelektrikář').
    Both sides are NFKD-normalized for diacritics.
    """
    if not exclude_terms:
        return False

    normalized_title = strip_diacritics(title.lower())
    normalized_desc = strip_diacritics(description.lower()) if description else ""

    for term in exclude_terms:
        t = strip_diacritics(term.strip().lower())
        if not t:
            continue
        if re.search(r"\b" + re.escape(t) + r"\b", normalized_title):
            return True
        if normalized_desc and t in normalized_desc:
            return True

    return False


# ── Legacy compatibility ──────────────────────────────────────────────

class Matcher:
    @staticmethod
    def match_keywords(
        title: str,
        query: str,
        description: str = "",
        exclude: str = "",
    ) -> tuple[bool, str]:
        required_terms = [t.strip() for t in query.split("+") if t.strip()]
        if not required_terms:
            return False, ""

        title_lower = title.lower()
        for term in required_terms:
            pattern = r"\b" + re.escape(term.lower()) + r"\b"
            if not re.search(pattern, title_lower):
                return False, ""

        desc_lower = description.lower()
        for term in required_terms:
            if term.lower() in desc_lower:
                return True, query

        return True, query

    @staticmethod
    def has_exclude(title: str, exclude_pattern: str) -> bool:
        if not exclude_pattern:
            return False
        title_normalized = strip_diacritics(title.lower())
        for term in exclude_pattern.split("|"):
            term = term.strip().lower()
            if not term:
                continue
            if re.search(r"\b" + re.escape(strip_diacritics(term)) + r"\b", title_normalized):
                return True
        return False
