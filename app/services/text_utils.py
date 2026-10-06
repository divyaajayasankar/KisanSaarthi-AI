"""Script-safe text normalization shared by the multilingual layers.

Regex \\w drops Indic vowel signs and viramas (Unicode Mn/Mc), which
corrupts Hindi, Tamil and Telugu words. This module removes only
punctuation (P*) and symbols (S*) and keeps every letter and mark.
"""

from __future__ import annotations

import re
import unicodedata

_SPACE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value)).lower()
    text = text.replace("_", " ").replace("-", " ")
    kept = []
    for char in text:
        category = unicodedata.category(char)
        if category[0] in ("P", "S") and char not in ".":
            kept.append(" ")
        else:
            kept.append(char)
    text = "".join(kept)
    # keep decimal points inside numbers only
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return _SPACE.sub(" ", text).strip()


def contains_phrase(haystack_normalized: str, needle_normalized: str) -> bool:
    """Word-bounded match for Latin text, substring match for Indic text
    (Indic words take suffixes: நெல்லில், వరికి)."""
    if not needle_normalized:
        return False
    if needle_normalized.isascii():
        return f" {needle_normalized} " in f" {haystack_normalized} "
    return needle_normalized in haystack_normalized
