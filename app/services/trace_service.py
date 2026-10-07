"""Persist one audit row per chat turn and keep a saved field profile.

Everything here is best-effort. A failure is logged and swallowed, so
trace storage can never change or break the farmer's reply.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models_trace import AdvisoryTrace, FieldProfile
from app.services import conversation_service as conv

log = logging.getLogger("kisansaarthi.trace")

_READY: set[str] = set()


def ensure_tables(db: Session) -> None:
    bind = db.get_bind()
    key = str(bind.url)
    if key in _READY:
        return
    AdvisoryTrace.__table__.create(bind=bind, checkfirst=True)
    FieldProfile.__table__.create(bind=bind, checkfirst=True)
    _READY.add(key)


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def record_turn(db: Session, turn: Any, channel: str, user_text: str | None, had_image: bool, latency_ms: float | None) -> None:
    """Write the trace row and upsert the field profile. Never raises."""
    try:
        ensure_tables(db)
        state = turn.state
        advisory = turn.advisory or {}
        context = conv.context_summary(state, turn.today)
        db.add(
            AdvisoryTrace(
                session_id=state["session_id"],
                turn_no=int(state.get("turns", 0)),
                channel=channel,
                language=turn.language,
                user_text=user_text,
                had_image=1 if had_image else 0,
                decision=turn.decision,
                reason=(str(turn.reason)[:200] if turn.reason else None),
                follow_up_field=turn.follow_up_field,
                engine_status=advisory.get("status"),
                fired_rules=_j(advisory.get("fired_rules") or []),
                context_json=_j(context),
                trace_json=_j(turn.trace),
                evidence_ids=_j(getattr(turn, "evidence_ids", []) or []),
                latency_ms=latency_ms,
            )
        )
        location = state.get("location") or {}
        profile = db.get(FieldProfile, state["session_id"])
        if profile is None:
            profile = FieldProfile(session_id=state["session_id"])
            db.add(profile)
        profile.language = turn.language
        profile.state = location.get("state")
        profile.district = location.get("district")
        profile.crop = state.get("crop")
        profile.pest = state.get("pest_canonical")
        profile.land_area = state.get("land_area")
        profile.land_unit = state.get("land_unit")
        profile.growth_stage = state.get("growth_stage")
        profile.days_to_harvest = context.get("days_to_harvest")
        profile.previous_treatment = context.get("previous_treatment")
        profile.days_since_previous_treatment = context.get("days_since_previous_treatment")
        profile.soil_type = state.get("soil_type")
        profile.soil_ph = state.get("soil_ph")
        profile.last_decision = turn.decision
        from datetime import datetime

        profile.updated_at = datetime.utcnow()
        db.commit()
        log.info(
            "turn session=%s n=%s decision=%s reason=%s rules=%s",
            state["session_id"][:8], state.get("turns"), turn.decision, turn.reason, advisory.get("fired_rules"),
        )
    except Exception as exc:  # pragma: no cover - defensive by design
        try:
            db.rollback()
        except Exception:
            pass
        log.warning("trace not saved: %s", exc.__class__.__name__)


def get_profile(db: Session, session_id: str) -> dict[str, Any] | None:
    ensure_tables(db)
    row = db.get(FieldProfile, session_id)
    if row is None:
        return None
    return {column.name: getattr(row, column.name) for column in FieldProfile.__table__.columns}


def get_traces(db: Session, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    ensure_tables(db)
    rows = (
        db.query(AdvisoryTrace)
        .filter(AdvisoryTrace.session_id == session_id)
        .order_by(AdvisoryTrace.id.asc())
        .limit(limit)
        .all()
    )
    out = []
    for row in rows:
        item = {column.name: getattr(row, column.name) for column in AdvisoryTrace.__table__.columns}
        for key in ("fired_rules", "context_json", "trace_json", "evidence_ids"):
            try:
                item[key] = json.loads(item[key]) if item.get(key) else None
            except ValueError:
                pass
        out.append(item)
    return out
