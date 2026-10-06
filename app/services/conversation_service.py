"""Conversation state (multi-turn memory) stored in the existing database.

The state remembers crop, symptoms, pest, language, location, land area,
growth stage, harvest timing, previous treatment, image reference and
vision result, so the farmer is never asked twice for the same value.

Relative values (days to harvest, days since last spray) are stored with
the date they were stated and aged on every turn.

The same API serves the web chat now and a WhatsApp adapter later
(channel="whatsapp", session id = phone number hash).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models_conversation import ConversationSession


HISTORY_LIMIT = 40

CONTEXT_FIELDS = (
    "crop", "symptoms", "pest_canonical", "pest_phrase", "pest_source", "registry_pest",
    "land_area", "land_unit", "growth_stage", "harvest_days", "harvest_recorded_on",
    "location", "previous_treatment", "previous_treatment_days_ago", "previous_treatment_recorded_on",
    "previous_treatment_none", "previous_application_count", "symptom_onset_days_ago",
    "soil_type", "soil_ph", "image", "vision",
)


def new_state(session_id: str, language: str = "en") -> dict[str, Any]:
    return {
        "session_id": session_id,
        "language": language,
        "language_locked": False,
        "symptoms": [],
        "asked": [],
        "pending_field": None,
        "turns": 0,
        "follow_up_turns": 0,
        "history": [],
        "last_result": None,
    }


def load_state(db: Session, session_id: str | None, channel: str = "web") -> dict[str, Any]:
    if session_id:
        row = db.get(ConversationSession, session_id)
        if row is not None:
            expired = row.updated_at and datetime.utcnow() - row.updated_at > timedelta(hours=settings.conversation_ttl_hours)
            if not expired:
                state = json.loads(row.state_json or "{}")
                state.setdefault("session_id", session_id)
                return state
    session_id = session_id or uuid.uuid4().hex
    return new_state(session_id)


def save_state(db: Session, state: dict[str, Any], channel: str = "web") -> None:
    state["history"] = state.get("history", [])[-HISTORY_LIMIT:]
    payload = json.dumps(state, ensure_ascii=False, default=str)
    row = db.get(ConversationSession, state["session_id"])
    if row is None:
        row = ConversationSession(id=state["session_id"], channel=channel, state_json=payload)
        db.add(row)
    else:
        row.state_json = payload
        row.updated_at = datetime.utcnow()
    db.commit()


def reset_state(state: dict[str, Any]) -> dict[str, Any]:
    fresh = new_state(state["session_id"], state.get("language", "en"))
    fresh["language_locked"] = state.get("language_locked", False)
    return fresh


def add_history(state: dict[str, Any], role: str, text: str, **extra: Any) -> None:
    entry = {"role": role, "text": text, "at": datetime.utcnow().isoformat(timespec="seconds")}
    entry.update({key: value for key, value in extra.items() if value is not None})
    state.setdefault("history", []).append(entry)


def aged_days(value: int | None, recorded_on: str | None, today: date | None = None, direction: int = -1) -> int | None:
    """Age a relative day count. direction=-1 for 'days until' (shrinks),
    +1 for 'days since' (grows)."""
    if value is None:
        return None
    if not recorded_on:
        return int(value)
    today = today or date.today()
    try:
        elapsed = (today - date.fromisoformat(recorded_on)).days
    except ValueError:
        return int(value)
    return int(value) + direction * max(0, elapsed)


def context_summary(state: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    location = state.get("location") or {}
    return {
        "crop": state.get("crop"),
        "symptoms": state.get("symptoms") or [],
        "pest": state.get("pest_canonical"),
        "pest_source": state.get("pest_source"),
        "registry_pest": state.get("registry_pest"),
        "land_area": state.get("land_area"),
        "land_unit": state.get("land_unit"),
        "growth_stage": state.get("growth_stage"),
        "days_to_harvest": aged_days(state.get("harvest_days"), state.get("harvest_recorded_on"), today, -1),
        "location": ", ".join(part for part in (location.get("district"), location.get("state")) if part) or None,
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "previous_treatment": state.get("previous_treatment") or ("none" if state.get("previous_treatment_none") else None),
        "days_since_previous_treatment": aged_days(
            state.get("previous_treatment_days_ago"), state.get("previous_treatment_recorded_on"), today, +1
        ),
        "previous_application_count": state.get("previous_application_count"),
        "soil_type": state.get("soil_type"),
        "soil_ph": state.get("soil_ph"),
        "image": (state.get("image") or {}).get("filename"),
        "vision": state.get("vision"),
        "language": state.get("language"),
    }
