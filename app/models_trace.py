"""Audit tables written after every chat turn.

advisory_traces  one row per turn: query, extracted context, agent trace,
                 rule results, retrieved evidence ids, decision and reason.
field_profiles   one row per conversation: the field context the farmer
                 has given so far (crop, place, area, stage, history).

Both tables are created on demand (see app/services/trace_service.py), so
an existing database needs no migration.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AdvisoryTrace(Base):
    __tablename__ = "advisory_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    language: Mapped[str | None] = mapped_column(String(8))
    user_text: Mapped[str | None] = mapped_column(Text)
    had_image: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(200))
    follow_up_field: Mapped[str | None] = mapped_column(String(60))
    engine_status: Mapped[str | None] = mapped_column(String(20))
    fired_rules: Mapped[str | None] = mapped_column(Text)
    context_json: Mapped[str | None] = mapped_column(Text)
    trace_json: Mapped[str | None] = mapped_column(Text)
    evidence_ids: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float)


class FieldProfile(Base):
    __tablename__ = "field_profiles"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    language: Mapped[str | None] = mapped_column(String(8))
    state: Mapped[str | None] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(80))
    crop: Mapped[str | None] = mapped_column(String(60))
    pest: Mapped[str | None] = mapped_column(String(120))
    land_area: Mapped[float | None] = mapped_column(Float)
    land_unit: Mapped[str | None] = mapped_column(String(20))
    growth_stage: Mapped[str | None] = mapped_column(String(30))
    days_to_harvest: Mapped[int | None] = mapped_column(Integer)
    previous_treatment: Mapped[str | None] = mapped_column(String(120))
    days_since_previous_treatment: Mapped[int | None] = mapped_column(Integer)
    soil_type: Mapped[str | None] = mapped_column(String(60))
    soil_ph: Mapped[float | None] = mapped_column(Float)
    last_decision: Mapped[str | None] = mapped_column(String(20))
