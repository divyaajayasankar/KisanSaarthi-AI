"""Context Agent: free farmer text -> structured advisory context.

Mode B (default): deterministic multilingual lexicon (data/i18n/lexicon.json)
for English, Hindi, Tamil and Telugu.
Mode A (optional): app.services.llm_service may fill fields that Mode B
missed; its output is validated against the same vocabularies and never
overrides a deterministic value.

Only fields actually found are returned. Nothing is defaulted, so the
conversation layer can ask for exactly what is missing.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from app.services.language_service import detect_language, load_lexicon
from app.services.pest_alias_service import find_alias_in_text
from app.services.text_utils import contains_phrase, normalize_text


INDIAN_STATES = {
    "Andhra Pradesh": ["andhra pradesh", "andhra", "आंध्र प्रदेश", "ஆந்திரா", "ఆంధ్రప్రదేశ్", "ఆంధ్ర ప్రదేశ్"],
    "Arunachal Pradesh": ["arunachal pradesh", "arunachal"],
    "Assam": ["assam", "असम"],
    "Bihar": ["bihar", "बिहार"],
    "Chhattisgarh": ["chhattisgarh", "छत्तीसगढ़"],
    "Goa": ["goa"],
    "Gujarat": ["gujarat", "गुजरात"],
    "Haryana": ["haryana", "हरियाणा"],
    "Himachal Pradesh": ["himachal pradesh", "himachal", "हिमाचल"],
    "Jharkhand": ["jharkhand", "झारखंड"],
    "Karnataka": ["karnataka", "कर्नाटक", "கர்நாடகா", "కర్ణాటక"],
    "Kerala": ["kerala", "केरल", "கேரளா", "కేరళ"],
    "Madhya Pradesh": ["madhya pradesh", "मध्य प्रदेश", "मध्यप्रदेश"],
    "Maharashtra": ["maharashtra", "महाराष्ट्र", "மகாராஷ்டிரா", "మహారాష్ట్ర"],
    "Manipur": ["manipur"],
    "Meghalaya": ["meghalaya"],
    "Mizoram": ["mizoram"],
    "Nagaland": ["nagaland"],
    "Odisha": ["odisha", "orissa", "ओडिशा"],
    "Punjab": ["punjab", "पंजाब"],
    "Rajasthan": ["rajasthan", "राजस्थान"],
    "Sikkim": ["sikkim"],
    "Tamil Nadu": ["tamil nadu", "tamilnadu", "तमिलनाडु", "तमिल नाडु", "தமிழ்நாடு", "தமிழ் நாடு", "తమిళనాడు"],
    "Telangana": ["telangana", "तेलंगाना", "தெலங்கானா", "తెలంగాణ"],
    "Tripura": ["tripura"],
    "Uttar Pradesh": ["uttar pradesh", "उत्तर प्रदेश"],
    "Uttarakhand": ["uttarakhand", "उत्तराखंड"],
    "West Bengal": ["west bengal", "पश्चिम बंगाल"],
    "Delhi": ["delhi", "दिल्ली"],
    "Jammu and Kashmir": ["jammu and kashmir", "jammu kashmir"],
    "Puducherry": ["puducherry", "pondicherry", "புதுச்சேரி"],
}

_CLAUSE_SPLIT = re.compile(
    r"[.,;!?\n।]|\b(?:and|but|also|then)\b|\s(?:और|लेकिन|मற்றும்|மற்றும்|ஆனால்|మరియు|కానీ)\s",
    re.IGNORECASE,
)
_NUMBER = r"\d+(?:\.\d+)?"


@dataclass
class ExtractedContext:
    language: str | None = None
    intent: str | None = None
    crop: str | None = None
    symptoms: list[str] = field(default_factory=list)
    pest_canonical: str | None = None
    pest_phrase: str | None = None
    land_area: float | None = None
    land_unit: str | None = None
    growth_stage: str | None = None
    harvest_days: int | None = None
    location_text: str | None = None
    state: str | None = None
    previous_treatment: str | None = None
    previous_treatment_days_ago: int | None = None
    previous_treatment_none: bool = False
    previous_application_count: int | None = None
    symptom_onset_days_ago: int | None = None
    soil_type: str | None = None
    soil_ph: float | None = None
    answer_yes: bool | None = None
    bare_number: float | None = None
    source: dict[str, str] = field(default_factory=dict)

    def found(self) -> dict[str, Any]:
        data = asdict(self)
        return {
            key: value
            for key, value in data.items()
            if value not in (None, [], {}, False) or key == "answer_yes" and value is False
        }


# ------------------------------------------------------------
# Lexicon helpers
# ------------------------------------------------------------

@lru_cache(maxsize=1)
def _lex() -> dict:
    return load_lexicon()


def _number_words() -> list[tuple[str, float]]:
    pairs = [
        (normalize_text(word), float(value))
        for value, words in _lex()["number_words"].items()
        for word in words
    ]
    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


def _alternation(words: list[str]) -> str:
    parts = sorted({normalize_text(word) for word in words if word}, key=len, reverse=True)
    escaped = []
    for part in parts:
        if part.isascii():
            escaped.append(r"\b" + re.escape(part) + r"\b")
        else:
            escaped.append(re.escape(part))
    return "(?:" + "|".join(escaped) + ")"


def _find_first(text: str, mapping: dict[str, list[str]]) -> tuple[str | None, str | None]:
    """Longest matching term across all keys -> (key, term)."""
    best: tuple[str | None, str | None] = (None, None)
    for key, terms in mapping.items():
        for term in terms:
            needle = normalize_text(term)
            if contains_phrase(text, needle) and (best[1] is None or len(needle) > len(best[1])):
                best = (key, needle)
    return best


def _remove(text: str, needle: str | None) -> str:
    if not needle:
        return text
    if needle.isascii():
        return re.sub(r"\b" + re.escape(needle) + r"\b", " ", text)
    # Indic: drop the whole word that carries the term plus its suffix
    # (బెండకాయ -> removes 'కాయ' too, so it is not read as 'fruiting').
    return re.sub(r"\S*" + re.escape(needle) + r"\S*", " ", text)


def _parse_number(token: str) -> float | None:
    token = normalize_text(token)
    try:
        return float(token)
    except ValueError:
        pass
    for word, value in _number_words():
        if token == word:
            return value
    return None


def _number_pattern() -> str:
    words = [word for word, _ in _number_words() if word not in ("a", "an")]
    return "(?:" + _NUMBER + "|" + _alternation(words)[3:-1] + ")"


# ------------------------------------------------------------
# Field extractors
# ------------------------------------------------------------

def _extract_crop(text: str) -> tuple[str | None, str | None]:
    return _find_first(text, _lex()["crops"])


def _extract_area(text: str) -> tuple[float | None, str | None, str | None]:
    unit_map = _lex()["area_units"]
    unit_words = [word for words in unit_map.values() for word in words]
    pattern = re.compile(
        "(?P<num>" + _number_pattern() + r")\s*(?:(?:an|a)\s+)?(?P<unit>" + _alternation(unit_words) + ")"
    )
    match = pattern.search(text)
    if not match:
        # "an acre" / "one acre" without explicit number
        single = re.search(r"\b(?:an|a)\s+(?P<unit>acre|hectare)\b", text)
        if single:
            return 1.0, single.group("unit"), single.group(0)
        return None, None, None
    value = _parse_number(match.group("num"))
    unit_term = normalize_text(match.group("unit"))
    unit = next(
        (key for key, words in unit_map.items() if unit_term in {normalize_text(word) for word in words}),
        None,
    )
    if value is None or value <= 0 or unit is None:
        return None, None, None
    return value, unit, match.group(0)


def _durations(clause: str) -> list[int]:
    """All 'N day/week/month' durations in a clause, in days."""
    units = _lex()["time_units"]
    factor = {"day": 1, "week": 7, "month": 30}
    out: list[int] = []
    for unit, words in units.items():
        pattern = re.compile("(?P<num>" + _number_pattern() + r")\s*(?P<unit>" + _alternation(words) + ")")
        for match in pattern.finditer(clause):
            value = _parse_number(match.group("num"))
            if value is not None and value >= 0:
                out.append(int(round(value * factor[unit])))
    return out


def _relative_past(clause: str) -> int | None:
    key, _ = _find_first(clause, _lex()["relative_past"])
    return int(key) if key is not None else None


def _has_any(clause: str, words: list[str]) -> bool:
    return any(contains_phrase(clause, normalize_text(word)) for word in words)


def _extract_dates(raw: str, today: date) -> list[int]:
    days: list[int] = []
    for match in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", raw):
        try:
            days.append((date(int(match[1]), int(match[2]), int(match[3])) - today).days)
        except ValueError:
            continue
    for match in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", raw):
        try:
            days.append((date(int(match[3]), int(match[2]), int(match[1])) - today).days)
        except ValueError:
            continue
    return days


def _active_ingredients(extra: list[str] | None) -> list[str]:
    names = list(_lex()["common_active_ingredients"]) + list(extra or [])
    expanded: list[str] = []
    for name in names:
        for part in re.split(r"\s*\+\s*", name):
            if part.strip():
                expanded.append(part.strip())
    return sorted({normalize_text(name) for name in expanded}, key=len, reverse=True)


def _extract_location(raw: str) -> str | None:
    match = re.search(
        r"\b(?:in|at|near|from)\s+((?:[A-Z][\w.]+)(?:[\s,]+(?:[A-Z][\w.]+)){0,3})",
        raw,
    )
    if match:
        candidate = match.group(1).strip(" ,.")
        first = candidate.split()[0].lower()
        if first not in {"the", "my", "our", "this", "last", "next"}:
            return candidate
    match = re.search(r"([A-Z][\w]+(?:\s+[A-Z][\w]+)?)\s+district\b", raw)
    if match:
        return match.group(1)
    # "Erode, Tamil Nadu" with no preposition: capitalised place right
    # before a named state.
    state_aliases = sorted(
        {alias for aliases in INDIAN_STATES.values() for alias in aliases if alias.isascii()}
        | {state for state in INDIAN_STATES if state.isascii()},
        key=len,
        reverse=True,
    )
    if state_aliases:
        state_pattern = "|".join(re.escape(alias) for alias in state_aliases)
        match = re.search(
            r"([A-Z][\w.]+(?:\s+[A-Z][\w.]+)?)\s*,\s*(?:" + state_pattern + r")\b",
            raw,
            flags=0,
        )
        if match:
            return match.group(0).strip(" ,.")
    for marker in ("जिला", "जिले", "மாவட்டம்", "மாவட்ட", "జిల్లా"):
        index = raw.find(marker)
        if index > 0:
            before = raw[:index].strip().split()
            if before:
                return before[-1].strip(" ,.")
    return None


def _extract_state(text: str) -> tuple[str | None, str | None]:
    return _find_first(text, INDIAN_STATES)


# ------------------------------------------------------------
# Main entry
# ------------------------------------------------------------

def extract_context(
    text: str,
    *,
    pending_field: str | None = None,
    known_crop: str | None = None,
    extra_active_ingredients: list[str] | None = None,
    today: date | None = None,
) -> ExtractedContext:
    today = today or datetime.now().date()
    raw = (text or "").strip()
    norm = normalize_text(raw)
    ctx = ExtractedContext(language=detect_language(raw))
    if not norm:
        return ctx

    lex = _lex()
    working = norm

    # intent ---------------------------------------------------
    if _has_any(norm, lex["reset_words"]):
        ctx.intent = "reset"
        return ctx

    # crop -----------------------------------------------------
    crop, crop_term = _extract_crop(working)
    if crop:
        ctx.crop = crop
        working = _remove(working, crop_term)
        # remove every other synonym of the same crop (e.g. both 'paddy' and 'rice')
        for term in lex["crops"][crop]:
            working = _remove(working, normalize_text(term))

    crop_for_alias = ctx.crop or known_crop

    # pest / disease alias ---------------------------------------
    alias = find_alias_in_text(crop_for_alias, working) if crop_for_alias else None
    if alias:
        ctx.pest_canonical = alias.canonical
        ctx.pest_phrase = alias.alias
        working_wo_pest = _remove(working, alias.alias)
    else:
        working_wo_pest = working

    # previous treatment (active ingredient) ---------------------
    for name in _active_ingredients(extra_active_ingredients):
        if contains_phrase(working_wo_pest, name):
            ctx.previous_treatment = name
            working_wo_pest = _remove(working_wo_pest, name)
            break

    # area -------------------------------------------------------
    area, unit, area_text = _extract_area(working_wo_pest)
    if area is not None:
        ctx.land_area, ctx.land_unit = area, unit
        working_wo_pest = working_wo_pest.replace(normalize_text(area_text), " ")

    # growth stage -----------------------------------------------
    stage, _ = _find_first(working_wo_pest, lex["growth_stages"])
    if stage:
        ctx.growth_stage = stage

    # symptoms ---------------------------------------------------
    for symptom, terms in lex["symptoms"].items():
        if any(contains_phrase(working, normalize_text(term)) for term in terms):
            ctx.symptoms.append(symptom)

    # soil -------------------------------------------------------
    soil_type, _ = _find_first(working_wo_pest, lex["soil_types"])
    ctx.soil_type = soil_type
    ph = re.search(r"\bph\s*(?:is|of|=|:)?\s*(" + _NUMBER + ")", norm)
    if ph:
        value = float(ph.group(1))
        if 3.0 <= value <= 10.5:
            ctx.soil_ph = value

    # clause-level time reasoning ----------------------------------
    spray_words = lex["spray_words"]
    harvest_words = lex["harvest_words"]
    ago_words = lex["ago_markers"]
    for raw_clause in _CLAUSE_SPLIT.split(raw):
        clause = normalize_text(raw_clause)
        if not clause:
            continue
        durations = _durations(clause)
        dates = _extract_dates(raw_clause, today)
        is_harvest = _has_any(clause, harvest_words)
        is_spray = _has_any(clause, spray_words) or (
            ctx.previous_treatment is not None and contains_phrase(clause, ctx.previous_treatment)
        )
        is_ago = _has_any(clause, ago_words)
        relative = _relative_past(clause)

        if is_harvest and not is_ago:
            future = [value for value in dates if value >= 0] or durations
            if future and ctx.harvest_days is None:
                ctx.harvest_days = int(future[0])
            continue

        is_onset = _has_any(clause, lex["symptom_onset_words"])
        past = durations if (durations and (is_ago or is_spray or is_onset)) else []
        past_days = past[0] if past else relative
        if past_days is None:
            continue
        if is_spray:
            ctx.previous_treatment_days_ago = past_days
        elif is_onset or ctx.symptoms or is_ago:
            ctx.symptom_onset_days_ago = past_days

    # application count --------------------------------------------
    times_pattern = re.compile("(?P<num>" + _number_pattern() + r")\s*" + _alternation(lex["times_words"]))
    times = times_pattern.search(working_wo_pest)
    if times:
        value = _parse_number(times.group("num"))
        if value is not None and value >= 0:
            ctx.previous_application_count = int(value)
    elif re.search(r"\b(twice)\b", norm):
        ctx.previous_application_count = 2
    elif re.search(r"\b(thrice)\b", norm):
        ctx.previous_application_count = 3
    elif re.search(r"\b(once)\b", norm) and ctx.previous_treatment:
        ctx.previous_application_count = 1

    # location -----------------------------------------------------
    state, state_term = _extract_state(norm)
    ctx.state = state
    location = _extract_location(raw)
    if location:
        ctx.location_text = location

    # yes / no -----------------------------------------------------
    words = norm.split()
    if len(words) <= 4:
        if any(normalize_text(word) in words or normalize_text(word) == norm for word in lex["no"]):
            ctx.answer_yes = False
        elif any(normalize_text(word) in words or normalize_text(word) == norm for word in lex["yes"]):
            ctx.answer_yes = True

    # bare answers to the pending question ---------------------------
    bare = re.fullmatch(r"\s*(" + _NUMBER + r")\s*", norm)
    if bare:
        ctx.bare_number = float(bare.group(1))
    elif len(words) <= 3:
        word_value = _parse_number(norm)
        if word_value is not None:
            ctx.bare_number = word_value

    if pending_field == "previous_treatment" and ctx.answer_yes is False and not ctx.previous_treatment:
        ctx.previous_treatment_none = True

    if pending_field == "location" and not ctx.location_text:
        candidate = raw
        if state_term and candidate:
            pass
        if ctx.crop is None and not ctx.symptoms and ctx.bare_number is None and ctx.answer_yes is None:
            ctx.location_text = candidate.strip(" .")

    # intent -------------------------------------------------------
    if ctx.intent is None:
        has_content = any(
            [
                ctx.crop, ctx.symptoms, ctx.pest_canonical, ctx.land_area, ctx.growth_stage,
                ctx.harvest_days is not None, ctx.previous_treatment, ctx.location_text,
            ]
        )
        if _has_any(norm, lex["greetings"]) and not has_content and len(words) <= 3:
            ctx.intent = "greeting"
        elif _has_any(norm, lex["weather_words"]) and not ctx.symptoms and not ctx.pest_canonical:
            ctx.intent = "weather"
        else:
            ctx.intent = "advisory"

    for key in ctx.found():
        if key not in ("source", "language", "intent"):
            ctx.source[key] = "lexicon"
    return ctx
