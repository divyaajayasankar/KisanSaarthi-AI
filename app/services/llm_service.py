"""Optional LLM (Mode A).

Enabled only when LLM_ENABLED=true and LLM_API_KEY is set; otherwise
every function returns None and the deterministic Mode B is used.
Works with any OpenAI-compatible /chat/completions endpoint
(LLM_BASE_URL, LLM_MODEL).

The LLM is used for two things only:
  1. extract_fields: structured context from free text, merged only
     into fields the lexicon did not find, after vocabulary validation
  2. translate: wording of free-text explanations, wrapped by
     language_service.translate_protected so doses, units, dates and
     active ingredients cannot change

It never computes doses, PHI, intervals, area conversions, thresholds
or the ANSWER / ASK_FOLLOW_UP / ABSTAIN decision.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings
from app.services.language_service import LANGUAGE_NAMES, load_lexicon


VALID_UNITS = {"acre", "hectare", "cent", "guntha", "sqm"}
VALID_STAGES = {"seedling", "vegetative", "flowering", "fruiting", "pre_harvest"}


def is_active() -> bool:
    return settings.llm_active


def _chat(messages: list[dict[str, str]], max_tokens: int = 400) -> str | None:
    if not is_active():
        return None
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


def _parse_json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def validate_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only values inside the system vocabularies and sane ranges."""
    crops = {crop.lower(): crop for crop in load_lexicon()["crops"]}
    clean: dict[str, Any] = {}

    crop = str(raw.get("crop") or "").strip().lower()
    if crop in crops:
        clean["crop"] = crops[crop]

    for key in ("pest_phrase", "location_text", "previous_treatment"):
        value = raw.get(key)
        if isinstance(value, str) and 0 < len(value.strip()) <= 80:
            clean[key] = value.strip()

    unit = str(raw.get("land_unit") or "").strip().lower()
    try:
        area = float(raw.get("land_area"))
    except (TypeError, ValueError):
        area = None
    if area is not None and 0 < area <= 1000 and unit in VALID_UNITS:
        clean["land_area"], clean["land_unit"] = area, unit

    stage = str(raw.get("growth_stage") or "").strip().lower().replace(" ", "_")
    if stage in VALID_STAGES:
        clean["growth_stage"] = stage

    for key, upper in (("harvest_days", 400), ("previous_treatment_days_ago", 365), ("previous_application_count", 20)):
        try:
            number = int(raw.get(key))
        except (TypeError, ValueError):
            continue
        if 0 <= number <= upper:
            clean[key] = number

    symptoms = raw.get("symptoms")
    known = set(load_lexicon()["symptoms"].keys())
    if isinstance(symptoms, list):
        picked = [item for item in symptoms if isinstance(item, str) and item in known]
        if picked:
            clean["symptoms"] = picked
    return clean


def extract_fields(text: str) -> dict[str, Any] | None:
    if not is_active() or not text.strip():
        return None
    crops = ", ".join(load_lexicon()["crops"].keys())
    symptoms = ", ".join(load_lexicon()["symptoms"].keys())
    prompt = (
        "Extract farm advisory context from the farmer message. The message may be in English, Hindi, "
        "Tamil or Telugu. Reply with one JSON object only. Use null for anything not stated. Do not guess.\n"
        f"crop: one of [{crops}]\n"
        f"symptoms: list from [{symptoms}]\n"
        "pest_phrase: disease or pest name exactly as the farmer said it, in English if you can translate it\n"
        "land_area: number; land_unit: one of [acre, hectare, cent, guntha, sqm]\n"
        "growth_stage: one of [seedling, vegetative, flowering, fruiting, pre_harvest]\n"
        "harvest_days: days until harvest (integer)\n"
        "location_text: village/town/district named by the farmer\n"
        "previous_treatment: pesticide or fungicide active ingredient name\n"
        "previous_treatment_days_ago: integer; previous_application_count: integer\n\n"
        f"Message: {text}"
    )
    parsed = _parse_json(_chat([{"role": "user", "content": prompt}]))
    return validate_fields(parsed) if parsed else None


def translate(masked_text: str, target_language: str) -> str | None:
    """Translate text containing ⟦n⟧ markers; markers must be kept."""
    if not is_active():
        return None
    language = LANGUAGE_NAMES.get(target_language, target_language)
    prompt = (
        f"Translate into simple {language} for a farmer. Keep every marker like ⟦0⟧ exactly as it is, "
        "once each, and do not add any facts. Reply with the translation only.\n\n" + masked_text
    )
    return _chat([{"role": "user", "content": prompt}], max_tokens=800)


def translator_or_none():
    return translate if is_active() else None
