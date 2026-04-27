import re
from typing import List

PROMPT_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"do not follow any previous instructions",
    r"ignore all previous instructions",
    r"disregard previous instructions",
    r"you are an assistant",
    r"you are a helpful assistant",
    r"please answer the following question",
    r"system prompt",
    r"instruction:",
    r"ignore this",
    r"do not obey the previous prompt",
    r"this is not a part of the message",
]

CONTROL_CHARACTERS_RE = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029]+")
WHITESPACE_RE = re.compile(r"\s+")
PROMPT_INJECTION_RE = re.compile("|".join(PROMPT_INJECTION_PATTERNS), re.IGNORECASE)

MAX_PAGE_CHARS = 12_000  # ~3 000 tokens at 4 chars/token


def sanitize_message(raw_message: str) -> str:
    """Clean a raw LINE message before analysis.

    The sanitizer removes control characters, collapses whitespace, and strips
    obvious prompt-injection phrases while preserving readable Chinese text.
    """
    if not isinstance(raw_message, str):
        return ""

    text = raw_message.replace("\r", " ")
    text = CONTROL_CHARACTERS_RE.sub(" ", text)
    text = PROMPT_INJECTION_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text).strip()

    return text


def sanitize_page_content(text: str) -> str:
    """Strip prompt-injection patterns and cap page text at ~3 000 tokens.

    The scraper already converts HTML to plain text; this function applies the
    same injection filter used for message input and enforces the token budget.
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    text = CONTROL_CHARACTERS_RE.sub(" ", text)
    text = PROMPT_INJECTION_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text).strip()

    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS].rstrip() + "..."

    return text


def sanitize_lines(raw_message: str) -> List[str]:
    """Split sanitized message into logical lines for downstream use."""
    sanitized = sanitize_message(raw_message)
    if not sanitized:
        return []
    return [line.strip() for line in sanitized.split("\n") if line.strip()]
