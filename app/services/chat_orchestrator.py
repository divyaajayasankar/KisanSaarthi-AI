"""KisanSaarthi agentic chat orchestrator.

One farmer turn (text, image, GPS, or any combination) passes through:

    Multilingual Agent    language detection / selection
    Context Agent         lexicon extraction (+ optional LLM fill-in)
    Location Agent        place name or GPS -> district/state/lat/lon
    Vision/Disease Agent  crop-aware model registry, calibrated confidence
    Pest Alias Layer      farmer/model phrase -> verified registry pest
    Treatment History     same active ingredient? same mode-of-action group?
    Safety Engine         existing /api/advisory pipeline: registry, dose
                          scaling, PHI, growth stage, application history,
                          resistance, weather, soil (unchanged)
    Decision Controller   ANSWER / ASK_FOLLOW_UP / ABSTAIN
    Knowledge Agent       verified RAG evidence
    Advisory Agent        localized reply from templates

Every safety number (dose, PHI, interval, thresholds) comes from the
deterministic engine. The web chat and a future WhatsApp adapter call
the same handle_turn().
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import RegistryEntry
from app.models_resistance import ResistanceRule
from app.schemas import AdvisoryRequest
from app.services import conversation_service as conv
from app.services import decision_controller as dc
from app.services import llm_service
from app.services.context_extraction_service import _find_first, extract_context
from app.services.image_quality_service import ImageValidationError, validate_image
from app.services.language_service import (
    crop_list,
    display_term,
    load_lexicon,
    normalize_language,
    t,
    translate_protected,
)
from app.services.location_service import resolve_coordinates, resolve_place
from app.services.pest_alias_service import find_alias_in_text, match_registry, resolve_pest
from app.services.text_utils import normalize_text
from app.services.vision_inference_service import analyze_image


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

REQUIRED_ORDER = ("location", "land_area", "harvest_days")
OPTIONAL_ONCE = ("growth_stage", "previous_treatment")


@dataclass
class ImageInput:
    content: bytes
    filename: str
    content_type: str


@dataclass
class Turn:
    state: dict[str, Any]
    language: str
    today: date
    messages: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    decision: str | None = None
    reason: str | None = None
    follow_up_field: str | None = None
    advisory: dict[str, Any] | None = None
    vision: dict[str, Any] | None = None
    details: str | None = None

    def say(self, text: str, kind: str = "text", **extra: Any) -> None:
        if text:
            self.messages.append({"role": "assistant", "kind": kind, "text": text, **extra})

    def step(self, agent: str, **result: Any) -> None:
        self.trace.append({"agent": agent, **result})


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------

def _registry_active_ingredients(db: Session) -> list[str]:
    """Ingredients the farmer may name as a previous spray: everything in
    the verified registry plus everything in the verified IRAC/FRAC table
    (a farmer may have used a product we do not recommend)."""
    registry = db.query(RegistryEntry.active_ingredient).filter(RegistryEntry.verified.is_(True)).distinct().all()
    resistance = db.query(ResistanceRule.active_ingredient).filter(ResistanceRule.verified.is_(True)).distinct().all()
    names = {row[0].strip() for row in (*registry, *resistance) if row[0] and row[0].strip()}
    return sorted(names)


def _registry_row(db: Session, crop: str, pest: str) -> RegistryEntry | None:
    return (
        db.query(RegistryEntry)
        .filter(func.lower(RegistryEntry.crop) == crop.lower())
        .filter(func.lower(RegistryEntry.pest) == pest.lower())
        .filter(RegistryEntry.verified.is_(True))
        .filter(RegistryEntry.is_test_data.is_(False))
        .first()
    )


def _components(active_ingredient: str | None) -> list[str]:
    return [normalize_text(part) for part in (active_ingredient or "").split("+") if part.strip()]


def _moa_group(db: Session, active_ingredient: str) -> str | None:
    target = normalize_text(active_ingredient)
    for rule in db.query(ResistanceRule).filter(ResistanceRule.verified.is_(True)).all():
        if normalize_text(rule.active_ingredient) == target:
            return f"{rule.framework} {rule.moa_group}"
    return None


def _ask(turn: Turn, field_name: str, text: str) -> None:
    state = turn.state
    state["pending_field"] = field_name
    if field_name not in state.setdefault("asked", []):
        state["asked"].append(field_name)
    state["follow_up_turns"] = state.get("follow_up_turns", 0) + 1
    turn.decision = dc.ASK_FOLLOW_UP
    turn.reason = f"missing:{field_name}"
    turn.follow_up_field = field_name
    turn.say(text, kind="question")
    turn.step("Decision Controller", decision=dc.ASK_FOLLOW_UP, follow_up_field=field_name)


def _abstain(turn: Turn, reason: str, text: str) -> None:
    turn.state["pending_field"] = None
    turn.decision = dc.ABSTAIN
    turn.reason = reason
    turn.say(text, kind="abstain")
    turn.step("Decision Controller", decision=dc.ABSTAIN, reason=reason)


def _fmt_conf(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _fmt_prob(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number * 100:.0f}%" if number <= 1 else f"{number:.0f}%"


def _fmt_num(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:g}"


def _pest_display(canonical: str | None) -> str:
    return (canonical or "").replace("_", " ")


# ------------------------------------------------------------
# state updates
# ------------------------------------------------------------

def _apply_pending(turn: Turn, db: Session, ctx, raw_text: str) -> None:
    state = turn.state
    pending = state.get("pending_field")
    if not pending:
        return
    norm = normalize_text(raw_text)

    if pending == "land_area" and ctx.land_area is None and ctx.bare_number:
        state["land_area"] = ctx.bare_number
        state["land_unit"] = None
    elif pending == "land_unit" and ctx.land_unit is None:
        unit, _ = _find_first(norm, load_lexicon()["area_units"])
        if unit:
            state["land_unit"] = unit
    elif pending == "harvest_days" and ctx.harvest_days is None and ctx.bare_number is not None:
        state["harvest_days"] = int(ctx.bare_number)
        state["harvest_recorded_on"] = turn.today.isoformat()
    elif pending == "days_since_last_application" and ctx.bare_number is not None:
        state["previous_treatment_days_ago"] = int(ctx.bare_number)
        state["previous_treatment_recorded_on"] = turn.today.isoformat()
    elif pending == "days_since_last_application" and ctx.previous_treatment_days_ago is None:
        days = ctx.symptom_onset_days_ago
        if days is not None:
            state["previous_treatment_days_ago"] = days
            state["previous_treatment_recorded_on"] = turn.today.isoformat()
    elif pending == "previous_treatment":
        if ctx.previous_treatment_none or ctx.answer_yes is False:
            state["previous_treatment_none"] = True
        elif ctx.previous_treatment is None and ctx.previous_treatment_days_ago is not None:
            state["previous_treatment_days_ago"] = ctx.previous_treatment_days_ago
            state["previous_treatment_recorded_on"] = turn.today.isoformat()
    elif pending == "confirm_pest":
        if ctx.answer_yes is True:
            state["pest_source"] = "vision_confirmed"
            state["pest_canonical"] = state.get("vision_pest")
        elif ctx.answer_yes is False:
            state["vision_rejected"] = True
            state["pest_canonical"] = None
            state["pest_source"] = None
    elif pending == "pest_name" and not ctx.pest_canonical and state.get("crop"):
        resolution = resolve_pest(db, state["crop"], raw_text)
        if resolution.canonical_pest:
            state["pest_canonical"] = resolution.canonical_pest
            state["pest_phrase"] = raw_text.strip()
            state["pest_source"] = "text"


def _merge(turn: Turn, ctx) -> None:
    state = turn.state
    today = turn.today.isoformat()

    if ctx.crop and ctx.crop != state.get("crop"):
        if state.get("crop"):
            for key in ("pest_canonical", "pest_phrase", "pest_source", "registry_pest", "vision", "vision_pest", "vision_rejected"):
                state.pop(key, None)
            state["asked"] = [item for item in state.get("asked", []) if item not in ("photo", "pest_name", "confirm_pest")]
        state["crop"] = ctx.crop
    if ctx.symptoms:
        state["symptoms"] = sorted(set(state.get("symptoms", [])) | set(ctx.symptoms))
    if ctx.pest_canonical:
        state["pest_canonical"] = ctx.pest_canonical
        state["pest_phrase"] = ctx.pest_phrase
        state["pest_source"] = "text"
        state["vision_rejected"] = False
    if ctx.land_area is not None:
        state["land_area"], state["land_unit"] = ctx.land_area, ctx.land_unit
    if ctx.growth_stage:
        state["growth_stage"] = ctx.growth_stage
    if ctx.harvest_days is not None:
        state["harvest_days"], state["harvest_recorded_on"] = ctx.harvest_days, today
    if ctx.previous_treatment:
        state["previous_treatment"] = ctx.previous_treatment
        state["previous_treatment_none"] = False
    if ctx.previous_treatment_days_ago is not None and (ctx.previous_treatment or state.get("previous_treatment")):
        state["previous_treatment_days_ago"] = ctx.previous_treatment_days_ago
        state["previous_treatment_recorded_on"] = today
    if ctx.previous_application_count is not None:
        state["previous_application_count"] = ctx.previous_application_count
    if ctx.symptom_onset_days_ago is not None and state.get("pending_field") != "days_since_last_application":
        state["symptom_onset_days_ago"] = ctx.symptom_onset_days_ago
    if ctx.soil_type:
        state["soil_type"] = ctx.soil_type
    if ctx.soil_ph is not None:
        state["soil_ph"] = ctx.soil_ph


def _merge_llm(ctx, llm_fields: dict[str, Any] | None, crop_hint: str | None) -> None:
    """Fill only what the lexicon missed; vocabulary-validated values."""
    if not llm_fields:
        return
    for key in ("crop", "growth_stage", "harvest_days", "location_text", "previous_treatment",
                "previous_treatment_days_ago", "previous_application_count"):
        if getattr(ctx, key, None) in (None, "", []) and key in llm_fields:
            setattr(ctx, key, llm_fields[key])
            ctx.source[key] = "llm"
    if ctx.land_area is None and "land_area" in llm_fields:
        ctx.land_area, ctx.land_unit = llm_fields["land_area"], llm_fields["land_unit"]
        ctx.source["land_area"] = "llm"
    if not ctx.symptoms and llm_fields.get("symptoms"):
        ctx.symptoms = llm_fields["symptoms"]
        ctx.source["symptoms"] = "llm"
    if not ctx.pest_canonical and llm_fields.get("pest_phrase"):
        alias = find_alias_in_text(ctx.crop or crop_hint, llm_fields["pest_phrase"])
        if alias:
            ctx.pest_canonical, ctx.pest_phrase = alias.canonical, llm_fields["pest_phrase"]
            ctx.source["pest_canonical"] = "llm+alias"


def _set_location(turn: Turn, resolved) -> None:
    location = resolved.as_dict()
    previous = turn.state.get("location") or {}
    if location.get("latitude") is None and previous.get("latitude") is not None:
        location["latitude"], location["longitude"] = previous["latitude"], previous["longitude"]
    turn.state["location"] = location
    turn.step("Location Agent", **{key: location.get(key) for key in ("status", "district", "state", "latitude", "longitude", "method")})


def _location_ready(state: dict[str, Any]) -> bool:
    location = state.get("location") or {}
    return location.get("status") == "resolved" and bool(location.get("district")) and bool(location.get("state"))


def _save_image(session_id: str, image: ImageInput) -> str:
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(image.content_type, ".img")
    folder = UPLOAD_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(image.content)
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:  # upload dir configured outside the project
        return str(path).replace("\\", "/")


def _run_vision(turn: Turn, image_bytes: bytes) -> None:
    state = turn.state
    result = analyze_image(state.get("crop"), image_bytes)
    vision = result.as_dict()
    state["vision"] = vision
    state["vision_rejected"] = False
    if result.model_supported and result.prediction:
        alias = find_alias_in_text(state["crop"], result.prediction)
        state["vision_pest"] = alias.canonical if alias else result.prediction.replace("_", " ").capitalize()
    else:
        state["vision_pest"] = None
    turn.vision = vision
    turn.step(
        "Vision/Disease Agent",
        model_supported=result.model_supported,
        prediction=result.prediction,
        confidence=result.confidence,
        decision=result.decision,
        reason=result.reason,
    )


# ------------------------------------------------------------
# knowledge
# ------------------------------------------------------------

def _knowledge(turn: Turn, crop: str, topic: str) -> None:
    try:
        from app.services.rag_service import retrieve_verified_evidence

        result = retrieve_verified_evidence(query=topic, crop=crop, top_k=2)
    except Exception as exc:  # knowledge base missing or unreadable
        turn.step("Knowledge Agent", status="unavailable", error=exc.__class__.__name__)
        return
    items = result.get("results") or []
    turn.step("Knowledge Agent", status=result.get("status"), results=len(items))
    if not items:
        return
    translator = llm_service.translator_or_none()
    lines = []
    for item in items:
        text = str(item.get("text") or "").strip()
        localized, _ = translate_protected(text, turn.language, translator)
        source = item.get("source") or item.get("source_type") or ""
        lines.append(f"- {localized}" + (f" ({source})" if source else ""))
    turn.say(t("knowledge_header", turn.language) + "\n" + "\n".join(lines), kind="knowledge",
             sources=[item.get("source_url") for item in items if item.get("source_url")])


# ------------------------------------------------------------
# engine + reply
# ------------------------------------------------------------

def _run_engine(turn: Turn, db: Session) -> None:
    from app.routers.advisory import get_advisory

    state = turn.state
    location = state.get("location") or {}
    crop = state["crop"]
    registry_pest = state["registry_pest"]
    row = _registry_row(db, crop, registry_pest)
    harvest_days = conv.aged_days(state.get("harvest_days"), state.get("harvest_recorded_on"), turn.today, -1)
    harvest_days = max(0, harvest_days or 0)

    previous_count = None
    days_since = None
    same_ai = False
    previous_ai = state.get("previous_treatment")
    recommended_components = _components(row.active_ingredient if row else None)
    if previous_ai:
        same_ai = any(
            normalize_text(previous_ai) in component or component in normalize_text(previous_ai)
            for component in recommended_components
        )
        if same_ai:
            previous_count = int(state.get("previous_application_count") or 1)
            days_since = conv.aged_days(
                state.get("previous_treatment_days_ago"), state.get("previous_treatment_recorded_on"), turn.today, +1
            )
        else:
            previous_count = 0
    elif state.get("previous_treatment_none"):
        previous_count = 0

    turn.step(
        "Treatment History Agent",
        previous_treatment=previous_ai,
        same_active_ingredient=same_ai,
        previous_application_count=previous_count,
        days_since_last_application=days_since,
    )

    # Repeating the same active ingredient needs the gap since the last
    # spray. Ask once; if the farmer cannot say, the engine proceeds with
    # the unknown interval and applies its own conservative rules.
    if same_ai and days_since is None and "days_since_last_application" not in state.get("asked", []):
        _ask(
            turn,
            "days_since_last_application",
            t("ask_days_since_last_application", turn.language, ai=row.active_ingredient if row else previous_ai),
        )
        return

    request = AdvisoryRequest(
        crop=crop,
        pest=registry_pest,
        field_area=float(state["land_area"]),
        area_unit=state["land_unit"],
        expected_harvest_days=harvest_days,
        state=location.get("state"),
        district=location.get("district"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        growth_stage=state.get("growth_stage"),
        previous_application_count=previous_count,
        days_since_last_application=days_since,
    )
    turn.say(t("checking", turn.language), kind="info")
    response = get_advisory(request=request, db=db)
    advisory = response.model_dump()
    turn.advisory = advisory
    turn.details = advisory.get("explanation")
    turn.step(
        "Safety Engine",
        status=advisory["status"],
        fired_rules=advisory["fired_rules"],
        request={key: value for key, value in request.model_dump().items() if value is not None},
    )

    decision = dc.decide_engine(status=advisory["status"], fired_rules=advisory["fired_rules"])
    turn.step("Decision Controller", **decision.as_dict())
    state["last_result"] = {"status": advisory["status"], "decision": decision.decision, "fired_rules": advisory["fired_rules"]}

    if decision.decision == dc.ASK_FOLLOW_UP:
        field_name = decision.follow_up_field
        if field_name == "location":
            state["location"] = None
            _ask(turn, "location", t("ask_location", turn.language))
        elif field_name == "days_since_last_application":
            _ask(turn, field_name, t("ask_days_since_last_application", turn.language, ai=row.active_ingredient if row else previous_ai))
        elif field_name == "land_area":
            state["land_area"] = None
            _ask(turn, "land_area", t("ask_land_area", turn.language))
        else:
            _abstain(turn, decision.reason, t("abstain_generic", turn.language))
        return

    turn.decision = decision.decision
    turn.reason = decision.reason
    state["pending_field"] = None
    crop_label = display_term("crops", crop, turn.language)
    pest_label = _pest_display(state.get("pest_canonical"))
    weather = advisory.get("weather_summary") or {}

    if advisory["status"] == "recommend":
        dose_min, dose_max = advisory["scaled_dose_min"], advisory["scaled_dose_max"]
        dose = _fmt_num(dose_min) if dose_min == dose_max else f"{_fmt_num(dose_min)}-{_fmt_num(dose_max)}"
        if row is not None and row.phi_not_applicable:
            phi_line = t("phi_na_line", turn.language)
        else:
            phi_line = t("phi_line", turn.language, phi_days=row.phi_days if row else "n/a", harvest_days=harvest_days)
        turn.say(
            t(
                "answer_recommend", turn.language, crop=crop_label, pest=pest_label,
                ai=advisory["active_ingredient"], area=_fmt_num(state["land_area"]), unit=state["land_unit"],
                dose=dose, dose_unit=advisory["dose_unit"], phi_line=phi_line,
            ),
            kind="advisory",
        )
        _weather_line(turn, weather)
        _notes(turn, db, advisory, row, previous_ai, same_ai)
        turn.say(t("note_label", turn.language), kind="note")
    else:  # delay
        if "weather_high_wind_delay" in advisory["fired_rules"] and "weather_rain_delay" not in advisory["fired_rules"]:
            reason = t("reason_weather_high_wind_delay", turn.language, wind=_fmt_num(weather.get("max_wind_speed_m_s")))
        else:
            reason = t(
                "reason_weather_rain_delay", turn.language,
                rain_prob=_fmt_prob(weather.get("max_rain_probability")), rain_mm=_fmt_num(weather.get("rain_total_mm")),
            )
        turn.say(t("answer_delay", turn.language, crop=crop_label, pest=pest_label, reason=reason), kind="advisory")
        _weather_line(turn, weather)

    if decision.decision == dc.ABSTAIN:
        _engine_abstain(turn, advisory, row, harvest_days, crop_label, pest_label)


def _engine_abstain(turn: Turn, advisory, row, harvest_days, crop_label, pest_label) -> None:
    rules = advisory.get("fired_rules") or []
    turn.messages = [message for message in turn.messages if message.get("kind") == "info"]
    header = t("abstain_header", turn.language, crop=crop_label, pest=pest_label)
    if "registration_missing" in rules:
        body = t("abstain_registration_missing", turn.language)
    elif "phi_rejected" in rules:
        body = t("abstain_phi_rejected", turn.language, phi_days=row.phi_days if row else "n/a", harvest_days=harvest_days)
    elif "growth_stage_outside_application_window" in rules:
        body = t("abstain_growth_stage_outside_application_window", turn.language,
                 stage=display_term("growth_stages", turn.state.get("growth_stage"), turn.language))
    elif "maximum_application_frequency_reached" in rules:
        body = t("abstain_maximum_application_frequency_reached", turn.language)
    elif "minimum_treatment_interval_not_met" in rules:
        body = t("abstain_minimum_treatment_interval_not_met", turn.language)
    elif "weather_unavailable" in rules:
        body = t("abstain_weather_unavailable", turn.language)
    elif any(rule.startswith("soil_ph_") for rule in rules):
        body = t("abstain_soil", turn.language)
    else:
        body = t("abstain_generic", turn.language)
    turn.say(header + "\n" + body, kind="abstain")


def _weather_line(turn: Turn, weather: dict[str, Any]) -> None:
    if not weather:
        return
    location = turn.state.get("location") or {}
    turn.say(
        t(
            "weather_line", turn.language,
            place=location.get("district") or weather.get("city") or "",
            rain_prob=_fmt_prob(weather.get("max_rain_probability")),
            rain_mm=_fmt_num(weather.get("rain_total_mm")),
            wind=_fmt_num(weather.get("max_wind_speed_m_s")),
            tmin=_fmt_num(weather.get("min_temperature_c")),
            tmax=_fmt_num(weather.get("max_temperature_c")),
        ),
        kind="weather",
    )


def _notes(turn: Turn, db: Session, advisory, row, previous_ai, same_ai) -> None:
    state = turn.state
    if state.get("growth_stage") == "flowering":
        turn.say(t("note_pollinator", turn.language), kind="note")
    recommended_ai = advisory.get("active_ingredient") or ""
    if previous_ai and not same_ai and recommended_ai:
        previous_group = _moa_group(db, previous_ai)
        groups = {_moa_group(db, part) for part in recommended_ai.split("+")}
        if previous_group and previous_group in groups:
            turn.say(t("note_same_moa", turn.language, prev_ai=previous_ai, ai=recommended_ai, moa=previous_group), kind="note")
    if "resistance_rotation_recommended" in (advisory.get("fired_rules") or []):
        groups = [group for group in (_moa_group(db, part) for part in recommended_ai.split("+")) if group]
        turn.say(t("note_rotation", turn.language, moa=", ".join(groups) or "MoA"), kind="note")
    vision = state.get("vision") or {}
    if state.get("pest_source") in ("vision", "vision_confirmed") and vision.get("prediction"):
        turn.say(t("image_evidence", turn.language, pest=_pest_display(state.get("pest_canonical")),
                   confidence=_fmt_conf(vision.get("confidence"))), kind="note")


# ------------------------------------------------------------
# pest step
# ------------------------------------------------------------

def _pest_step(turn: Turn, db: Session, has_new_image: bool) -> bool:
    """Return True when a pest is settled; otherwise a question or
    abstention has been issued."""
    state = turn.state
    crop = state["crop"]
    crop_label = display_term("crops", crop, turn.language)
    asked = state.setdefault("asked", [])

    if state.get("pest_canonical"):
        return True

    vision = state.get("vision") or {}
    if vision and not state.get("vision_rejected"):
        if vision.get("model_supported") and state.get("vision_pest"):
            confidence = vision.get("confidence")
            if vision.get("decision") == dc.ANSWER:
                state["pest_canonical"], state["pest_source"] = state["vision_pest"], "vision"
                return True
            if vision.get("decision") == dc.ASK_FOLLOW_UP and "confirm_pest" not in asked:
                _ask(turn, "confirm_pest", t("ask_confirm_pest", turn.language,
                                             pest=_pest_display(state["vision_pest"]), confidence=_fmt_conf(confidence)))
                return False
            if has_new_image:
                turn.say(t("image_low_confidence", turn.language, confidence=_fmt_conf(confidence)), kind="note")
        elif has_new_image:
            turn.say(t("image_not_validated", turn.language, crop=crop_label), kind="note")

        if "pest_name" not in asked:
            _ask(turn, "pest_name", t("ask_pest_name", turn.language, crop=crop_label))
            return False
        _abstain(turn, "pest_unknown", t("abstain_pest_unknown", turn.language, crop=crop_label))
        _knowledge(turn, crop, " ".join(state.get("symptoms") or []) or crop)
        return False

    if "photo" not in asked:
        if not state.get("symptoms") and "problem" not in asked:
            _ask(turn, "problem", t("ask_problem", turn.language, crop=crop_label))
            return False
        if state.get("symptoms"):
            turn.say(t("note_symptom_only", turn.language, symptoms=", ".join(state["symptoms"])), kind="note")
        _ask(turn, "photo", t("ask_photo", turn.language))
        return False

    if "pest_name" not in asked:
        _ask(turn, "pest_name", t("ask_pest_name", turn.language, crop=crop_label))
        return False

    _abstain(turn, "pest_unknown", t("abstain_pest_unknown", turn.language, crop=crop_label))
    _knowledge(turn, crop, " ".join(state.get("symptoms") or []) or crop)
    return False


# ------------------------------------------------------------
# main entry
# ------------------------------------------------------------

def handle_turn(
    db: Session,
    *,
    session_id: str | None = None,
    text: str | None = None,
    language: str | None = None,
    image: ImageInput | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    channel: str = "web",
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    state = conv.load_state(db, session_id, channel)

    explicit = (language or "").strip().lower()
    if explicit and explicit != "auto":
        state["language"] = normalize_language(explicit)
        state["language_locked"] = True
    elif explicit == "auto":
        state["language_locked"] = False

    turn = Turn(state=state, language=state.get("language", "en"), today=today)
    text = (text or "").strip()
    ctx = None

    # ---------------- Context Agent ----------------
    if text:
        ctx = extract_context(
            text,
            pending_field=state.get("pending_field"),
            known_crop=state.get("crop"),
            extra_active_ingredients=_registry_active_ingredients(db),
            today=today,
        )
        if llm_service.is_active():
            _merge_llm(ctx, llm_service.extract_fields(text), state.get("crop"))
        if not state.get("language_locked") and ctx.language:
            state["language"] = ctx.language
        turn.language = state["language"]
        turn.step("Multilingual Agent", language=turn.language, detected=ctx.language, locked=state.get("language_locked"))
        found = ctx.found()
        found.pop("source", None)
        turn.step("Context Agent", mode="llm+lexicon" if llm_service.is_active() else "lexicon", extracted=found)
        conv.add_history(state, "user", text)

        if ctx.intent == "reset":
            state = conv.reset_state(state)
            turn.state = state
            turn.say(t("reset_done", turn.language))
            turn.decision = dc.ASK_FOLLOW_UP
            turn.follow_up_field = "crop"
            return _finish(db, turn, channel)

        _apply_pending(turn, db, ctx, text)
        _merge(turn, ctx)

    # ---------------- Location Agent ----------------
    if latitude is not None and longitude is not None:
        _set_location(turn, resolve_coordinates(latitude, longitude))
        if (state.get("location") or {}).get("status") == "resolved":
            turn.say(t("location_saved", turn.language, place=_place(state)), kind="info")

    if ctx is not None and (ctx.location_text or (ctx.state and (state.get("location") or {}).get("status") == "needs_state")):
        previous = state.get("location") or {}
        query = ctx.location_text or ""
        if previous.get("status") == "needs_state" and ctx.state and previous.get("place"):
            query = f"{previous['place']}, {ctx.state}"
        elif ctx.state and ctx.state.lower() not in query.lower():
            query = f"{query}, {ctx.state}".strip(", ")
        resolved = resolve_place(query)
        _set_location(turn, resolved)
        if resolved.status == "resolved":
            turn.say(t("location_saved", turn.language, place=_place(state)), kind="info")

    # ---------------- Image ----------------
    image_bytes = None
    if image is not None:
        try:
            meta = validate_image(filename=image.filename, content_type=image.content_type, image_bytes=image.content)
            reference = _save_image(state["session_id"], image)
            state["image"] = {"filename": meta.filename, "path": reference, "width": meta.width,
                              "height": meta.height, "format": meta.image_format, "analyzed": False}
            image_bytes = image.content
            turn.step("Image Quality", status="valid", width=meta.width, height=meta.height, format=meta.image_format)
            conv.add_history(state, "user", "[image]", image=reference)
        except ImageValidationError as exc:
            turn.step("Image Quality", status="invalid", error=str(exc))
            turn.say(t("image_invalid", turn.language, error=str(exc)), kind="note")
            state["image"] = None

    # ---------------- Greeting ----------------
    if ctx is not None and ctx.intent == "greeting" and not state.get("crop"):
        turn.say(t("greeting", turn.language))
        turn.decision = dc.ASK_FOLLOW_UP
        turn.follow_up_field = "crop"
        return _finish(db, turn, channel)

    # ---------------- Crop ----------------
    if not state.get("crop"):
        if state.get("follow_up_turns", 0) >= _max_turns():
            _abstain(turn, "too_many_turns", t("too_many_turns", turn.language))
            return _finish(db, turn, channel)
        _ask(turn, "crop", t("ask_crop", turn.language, crops=crop_list(turn.language)))
        return _finish(db, turn, channel)

    # ---------------- Vision/Disease Agent ----------------
    pending_image = state.get("image") or {}
    has_new_image = False
    if image_bytes is not None or (pending_image and not pending_image.get("analyzed") and pending_image.get("path")):
        data = image_bytes
        if data is None:
            path = PROJECT_ROOT / pending_image["path"]
            data = path.read_bytes() if path.exists() else None
        if data is not None:
            _run_vision(turn, data)
            state["image"]["analyzed"] = True
            has_new_image = True

    if ctx is not None and ctx.intent == "weather" and not state.get("pest_canonical"):
        _weather_only(turn)
        return _finish(db, turn, channel)

    # ---------------- Pest ----------------
    if not _pest_step(turn, db, has_new_image):
        return _finish(db, turn, channel)

    crop_label = display_term("crops", state["crop"], turn.language)
    pest_label = _pest_display(state["pest_canonical"])
    registry_pest, token = match_registry(db, state["crop"], state["pest_canonical"])
    state["registry_pest"] = registry_pest
    turn.step("Pest Alias Layer", canonical=state["pest_canonical"], source=state.get("pest_source"),
              registry_pest=registry_pest, matched_token=token)
    if registry_pest is None:
        _abstain(turn, "engine_abstain:registration_missing",
                 t("abstain_header", turn.language, crop=crop_label, pest=pest_label)
                 + "\n" + t("abstain_registration_missing", turn.language))
        turn.step("Safety Engine", status="abstain", fired_rules=["registration_missing"])
        _knowledge(turn, state["crop"], state["pest_canonical"])
        return _finish(db, turn, channel)

    # ---------------- Required context ----------------
    if state.get("follow_up_turns", 0) >= _max_turns() and _missing(state):
        _abstain(turn, "too_many_turns", t("too_many_turns", turn.language))
        return _finish(db, turn, channel)

    location = state.get("location") or {}
    if not _location_ready(state):
        if location.get("status") == "needs_state":
            _ask(turn, "location", t("ask_location_state", turn.language, place=location.get("place") or ""))
        else:
            _ask(turn, "location", t("ask_location", turn.language))
        return _finish(db, turn, channel)
    if not state.get("land_area"):
        _ask(turn, "land_area", t("ask_land_area", turn.language))
        return _finish(db, turn, channel)
    if not state.get("land_unit"):
        _ask(turn, "land_unit", t("ask_land_unit", turn.language, area=_fmt_num(state["land_area"])))
        return _finish(db, turn, channel)
    if state.get("harvest_days") is None:
        _ask(turn, "harvest_days", t("ask_harvest_days", turn.language))
        return _finish(db, turn, channel)

    asked = state.setdefault("asked", [])
    if not state.get("growth_stage") and "growth_stage" not in asked:
        _ask(turn, "growth_stage", t("ask_growth_stage", turn.language))
        return _finish(db, turn, channel)
    if not state.get("previous_treatment") and not state.get("previous_treatment_none") and "previous_treatment" not in asked:
        _ask(turn, "previous_treatment", t("ask_previous_treatment", turn.language))
        return _finish(db, turn, channel)

    # ---------------- Safety Engine ----------------
    _run_engine(turn, db)
    if turn.decision in (dc.ANSWER, dc.ABSTAIN) and turn.advisory is not None:
        _knowledge(turn, state["crop"], state["pest_canonical"])
    return _finish(db, turn, channel)


def _missing(state: dict[str, Any]) -> list[str]:
    missing = []
    if not _location_ready(state):
        missing.append("location")
    if not state.get("land_area") or not state.get("land_unit"):
        missing.append("land_area")
    if state.get("harvest_days") is None:
        missing.append("harvest_days")
    return missing


def _max_turns() -> int:
    from app.config import settings

    return int(settings.max_follow_up_turns) + 4


def _place(state: dict[str, Any]) -> str:
    location = state.get("location") or {}
    return ", ".join(part for part in (location.get("district"), location.get("state")) if part) or location.get("place") or ""


def _weather_only(turn: Turn) -> None:
    from app.services.weather_service import get_location_weather

    if not _location_ready(turn.state):
        _ask(turn, "location", t("ask_location", turn.language))
        return
    location = turn.state["location"]
    try:
        data = get_location_weather(district=location["district"], state=location["state"])
    except Exception:
        _abstain(turn, "weather_unavailable", t("abstain_weather_unavailable", turn.language))
        return
    _weather_line(turn, data.get("weather") or {})
    turn.decision = dc.ANSWER
    turn.reason = "weather_only"


def _finish(db: Session, turn: Turn, channel: str) -> dict[str, Any]:
    state = turn.state
    for message in turn.messages:
        conv.add_history(state, "assistant", message["text"], kind=message.get("kind"))
    state["turns"] = state.get("turns", 0) + 1
    conv.save_state(db, state, channel)
    return {
        "session_id": state["session_id"],
        "language": turn.language,
        "decision": turn.decision,
        "reason": turn.reason,
        "follow_up_field": turn.follow_up_field,
        "messages": turn.messages,
        "advisory": turn.advisory,
        "vision": turn.vision,
        "details_label": t("english_details", turn.language),
        "details": turn.details,
        "context": conv.context_summary(state, turn.today),
        "agent_trace": turn.trace,
        "llm_mode": "A" if llm_service.is_active() else "B",
    }
