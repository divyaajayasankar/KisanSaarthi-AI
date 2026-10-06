"""Language detection, template rendering and protected translation.

Detection is by Unicode script, which is deterministic and needs no
model: Devanagari -> hi, Tamil -> ta, Telugu -> te, otherwise en.
New languages are added by extending SCRIPT_RANGES and the JSON files.

Responses are built from templates in data/i18n/messages.json. Values
such as active ingredients, doses, units, dates and confidences are
inserted verbatim, so they are never translated.

For free text that has no template (an engine explanation), the
optional LLM translator is wrapped by protect()/restore(): every
protected value is replaced by an opaque marker before translation and
the translation is rejected if any marker is lost or altered.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
I18N_DIR = PROJECT_ROOT / "data" / "i18n"

SUPPORTED_LANGUAGES = ("en", "hi", "ta", "te")
DEFAULT_LANGUAGE = "en"

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "हिन्दी",
    "ta": "தமிழ்",
    "te": "తెలుగు",
}

SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
}

# Script ranges used to pick a display word in the target language.
_DISPLAY_SCRIPT = {"en": None, **SCRIPT_RANGES}


@lru_cache(maxsize=1)
def load_messages() -> dict:
    return json.loads((I18N_DIR / "messages.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_lexicon() -> dict:
    return json.loads((I18N_DIR / "lexicon.json").read_text(encoding="utf-8"))


def normalize_language(code: str | None) -> str:
    value = (code or "").strip().lower()[:2]
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def detect_language(text: str | None) -> str | None:
    """Return hi/ta/te for Indic script text, en for Latin text,
    None when the text has no letters (numbers only, empty)."""
    if not text:
        return None
    counts = {code: 0 for code in SCRIPT_RANGES}
    latin = 0
    for char in text:
        point = ord(char)
        for code, (low, high) in SCRIPT_RANGES.items():
            if low <= point <= high:
                counts[code] += 1
                break
        else:
            if char.isascii() and char.isalpha():
                latin += 1
    best = max(counts, key=counts.get)
    if counts[best] > 0 and counts[best] >= latin * 0.3:
        return best
    if latin > 0:
        return "en"
    return None


def t(key: str, language: str, **values) -> str:
    """Render a template; unknown language falls back to English."""
    messages = load_messages()
    entry = messages.get(key)
    if entry is None:
        raise KeyError(f"Unknown message key: {key}")
    template = entry.get(normalize_language(language)) or entry["en"]
    safe = {name: ("" if value is None else value) for name, value in values.items()}
    return template.format(**safe).strip()


def _in_script(word: str, language: str) -> bool:
    script = _DISPLAY_SCRIPT.get(language)
    if script is None:
        return word.isascii()
    low, high = script
    return any(low <= ord(char) <= high for char in word)


def display_term(category: str, canonical: str | None, language: str) -> str:
    """Localized display word for a crop or growth stage, e.g.
    display_term('crops', 'Chilli', 'ta') -> 'மிளகாய்'."""
    if not canonical:
        return ""
    language = normalize_language(language)
    if language == "en":
        return canonical.replace("_", " ")
    terms = load_lexicon().get(category, {}).get(canonical, [])
    for term in terms:
        if _in_script(term, language):
            return term
    return canonical.replace("_", " ")


def crop_list(language: str) -> str:
    crops = load_lexicon()["crops"].keys()
    return ", ".join(display_term("crops", crop, language) for crop in crops)


# ------------------------------------------------------------
# Protected translation (used only by the optional LLM path)
# ------------------------------------------------------------

_NUMBER_WITH_UNIT = re.compile(
    r"\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*"
    r"(?:%|°C|mm|m/s|ml|mL|l|L|g|kg|days?|hectares?|ha|acres?|cents?|guntha)?",
)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def protect(text: str, protected_terms: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """Replace safety-critical substrings with ⟦n⟧ markers.

    Spans are collected on the original text in priority order
    (named terms, dates, numbers with units) and must not overlap,
    so a marker is never itself re-masked.
    """
    spans: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= s0 or start >= e0 for s0, e0 in spans)

    for term in sorted({term for term in (protected_terms or []) if term}, key=len, reverse=True):
        for match in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
            if free(match.start(), match.end()):
                spans.append((match.start(), match.end()))
    for pattern in (_DATE, _NUMBER_WITH_UNIT):
        for match in pattern.finditer(text):
            value = match.group(0).rstrip()
            if value and free(match.start(), match.start() + len(value)):
                spans.append((match.start(), match.start() + len(value)))

    mapping: dict[str, str] = {}
    pieces: list[str] = []
    cursor = 0
    for start, end in sorted(spans):
        marker = f"⟦{len(mapping)}⟧"
        mapping[marker] = text[start:end]
        pieces.append(text[cursor:start])
        pieces.append(marker)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), mapping


def restore(text: str, mapping: dict[str, str]) -> str | None:
    """Put protected values back. None if any marker went missing or
    was duplicated, which means the translator altered protected data."""
    for marker in mapping:
        if text.count(marker) != 1:
            return None
    if re.search(r"⟦\d+⟧", re.sub("|".join(re.escape(m) for m in mapping) or r"(?!)", "", text)):
        return None
    for marker, value in mapping.items():
        text = text.replace(marker, value)
    return text


def translate_protected(
    text: str,
    target_language: str,
    translator: Callable[[str, str], str | None] | None,
    protected_terms: list[str] | None = None,
) -> tuple[str, bool]:
    """Translate free text with protected values.

    Returns (text, translated). On any failure the English original is
    returned with translated=False; the protected values are never
    passed through the translator in clear form.
    """
    language = normalize_language(target_language)
    if language == "en" or translator is None or not text.strip():
        return text, False
    masked, mapping = protect(text, protected_terms)
    try:
        candidate = translator(masked, language)
    except Exception:
        return text, False
    if not candidate:
        return text, False
    restored = restore(candidate, mapping)
    if restored is None:
        return text, False
    return restored, True
