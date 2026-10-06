"""Pest/disease alias layer.

Maps farmer phrases and vision-model labels to the exact pest string
stored in the verified registry.

Two stages:
  1. alias table (data/registry/pest_aliases.csv)
       farmer/model phrase -> canonical pest name
  2. registry token match
       canonical pest name -> registry row whose compound pest string
       ("Blast; Sheath blight") contains that canonical as a token

The canonical names in the alias table are standard disease/pest names.
Whether a canonical name is actually registered for a crop is decided
only by the live registry. scripts/validate_pest_aliases.py reports
aliases that have no registry match.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import RegistryEntry
from app.services.text_utils import contains_phrase, normalize_text


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIAS_FILE = PROJECT_ROOT / "data" / "registry" / "pest_aliases.csv"

_SPLIT_PATTERN = re.compile(r"\s*(?:;|,|/|\band\b|&)\s*", re.IGNORECASE)


def normalize(value: str | None) -> str:
    return normalize_text(value)


def split_registry_pest(pest: str | None) -> list[str]:
    """'Blast; Sheath blight' -> ['blast', 'sheath blight']."""
    if not pest:
        return []
    return [normalize(part) for part in _SPLIT_PATTERN.split(pest) if normalize(part)]


@dataclass(frozen=True)
class PestAlias:
    crop: str
    alias: str
    canonical: str
    language: str


@dataclass
class PestResolution:
    crop: str
    query: str
    canonical_pest: str | None
    registry_pest: str | None
    matched_token: str | None
    method: str  # alias+registry | direct+registry | alias_unregistered | not_found

    @property
    def resolved(self) -> bool:
        return self.registry_pest is not None


@lru_cache(maxsize=1)
def load_aliases(path: str | None = None) -> tuple[PestAlias, ...]:
    file_path = Path(path) if path else ALIAS_FILE
    if not file_path.exists():
        return tuple()
    rows: list[PestAlias] = []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            crop = normalize(row.get("crop"))
            alias = normalize(row.get("input_alias"))
            canonical = (row.get("canonical_pest") or "").strip()
            if crop and alias and canonical:
                rows.append(PestAlias(crop, alias, canonical, (row.get("language") or "").strip()))
    return tuple(rows)


def aliases_for_crop(crop: str | None) -> list[PestAlias]:
    target = normalize(crop)
    return [alias for alias in load_aliases() if alias.crop == target]


def find_alias_in_text(crop: str | None, text: str | None) -> PestAlias | None:
    """Longest alias for this crop that occurs in free text."""
    haystack = normalize(text)
    if not haystack:
        return None
    best: PestAlias | None = None
    for alias in aliases_for_crop(crop):
        needle = alias.alias
        if contains_phrase(haystack, needle) and (best is None or len(needle) > len(best.alias)):
            best = alias
    return best


def _registry_rows(db: Session, crop: str) -> list[RegistryEntry]:
    return (
        db.query(RegistryEntry)
        .filter(func.lower(func.trim(RegistryEntry.crop)) == normalize(crop))
        .filter(RegistryEntry.verified.is_(True))
        .filter(RegistryEntry.is_test_data.is_(False))
        .all()
    )


def match_registry(db: Session, crop: str, canonical: str) -> tuple[str | None, str | None]:
    """Return (registry_pest, matched_token) for a canonical pest name.

    1. exact token equality ('blast' == 'blast')
    2. word-subset, only if exactly one registry token qualifies
       ('rust' within 'yellow rust')
    """
    target = normalize(canonical)
    if not target:
        return None, None

    rows = _registry_rows(db, crop)

    for row in rows:
        if normalize(row.pest) == target:
            return row.pest, target
        for token in split_registry_pest(row.pest):
            if token == target:
                return row.pest, token

    target_words = set(target.split())
    partial: list[tuple[str, str]] = []
    for row in rows:
        for token in split_registry_pest(row.pest):
            if target_words and target_words.issubset(set(token.split())):
                partial.append((row.pest, token))
    if len({pest for pest, _ in partial}) == 1:
        return partial[0]

    return None, None


def resolve_pest(db: Session, crop: str | None, query: str | None) -> PestResolution:
    crop_name = (crop or "").strip()
    raw = (query or "").strip()
    empty = PestResolution(crop_name, raw, None, None, None, "not_found")
    if not crop_name or not raw:
        return empty

    alias = find_alias_in_text(crop_name, raw)
    if alias is not None:
        registry_pest, token = match_registry(db, crop_name, alias.canonical)
        if registry_pest:
            return PestResolution(crop_name, raw, alias.canonical, registry_pest, token, "alias+registry")
        return PestResolution(crop_name, raw, alias.canonical, None, None, "alias_unregistered")

    registry_pest, token = match_registry(db, crop_name, raw)
    if registry_pest:
        return PestResolution(crop_name, raw, raw, registry_pest, token, "direct+registry")

    return empty


def registered_pests_for_crop(db: Session, crop: str) -> list[str]:
    return [row.pest for row in _registry_rows(db, crop)]
