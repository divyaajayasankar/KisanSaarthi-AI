"""Conversational decision controller.

Adds ANSWER / ASK_FOLLOW_UP / ABSTAIN on top of the existing engine
statuses (recommend / delay / abstain), which are kept unchanged.

    recommend                                 -> ANSWER
    delay (unsafe weather, still advice)      -> ANSWER
    abstain caused by farmer-fixable context  -> ASK_FOLLOW_UP
    any other abstain                         -> ABSTAIN

Vision evidence is gated before the engine is consulted:

    confidence >= vision_answer_threshold     -> usable evidence
    ask <= confidence < answer                -> ASK_FOLLOW_UP (confirm)
    confidence < vision_ask_threshold         -> ABSTAIN on image
    no validated model for crop               -> ABSTAIN on image

All thresholds come from settings (.env), never from an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings


ANSWER = "ANSWER"
ASK_FOLLOW_UP = "ASK_FOLLOW_UP"
ABSTAIN = "ABSTAIN"

# Engine abstain rules the farmer can resolve by answering a question.
FIXABLE_ABSTAIN_RULES: dict[str, str] = {
    "weather_context_missing": "location",
    "treatment_interval_context_missing": "days_since_last_application",
    "multiple_candidates_require_context": "pest",
    "area_unit_unsupported": "land_area",
}


@dataclass
class Decision:
    decision: str
    reason: str
    follow_up_field: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "follow_up_field": self.follow_up_field,
            "details": self.details,
        }


def thresholds() -> dict[str, float]:
    return {
        "answer": float(settings.vision_answer_threshold),
        "ask": float(settings.vision_ask_threshold),
    }


def decide_vision(
    *,
    model_supported: bool,
    confidence: float | None,
    image_valid: bool = True,
) -> Decision:
    """Decision for the image evidence alone."""
    if not image_valid:
        return Decision(ABSTAIN, "image_invalid")
    if not model_supported:
        return Decision(ABSTAIN, "image_model_not_validated_for_crop")
    if confidence is None:
        return Decision(ABSTAIN, "image_confidence_unavailable")

    limits = thresholds()
    if confidence >= limits["answer"]:
        return Decision(ANSWER, "image_confidence_high", details={"confidence": confidence, **limits})
    if confidence >= limits["ask"]:
        return Decision(
            ASK_FOLLOW_UP,
            "image_confidence_medium",
            follow_up_field="confirm_pest",
            details={"confidence": confidence, **limits},
        )
    return Decision(ABSTAIN, "image_confidence_low", details={"confidence": confidence, **limits})


def decide_engine(
    *,
    status: str | None,
    fired_rules: list[str] | None,
) -> Decision:
    """Decision for one advisory-engine result."""
    rules = list(fired_rules or [])
    engine_status = (status or "").strip().lower()

    if engine_status == "recommend":
        return Decision(ANSWER, "engine_recommend", details={"engine_status": engine_status})
    if engine_status == "delay":
        return Decision(ANSWER, "engine_delay", details={"engine_status": engine_status})

    if engine_status == "abstain":
        for rule in reversed(rules):
            if rule in FIXABLE_ABSTAIN_RULES:
                return Decision(
                    ASK_FOLLOW_UP,
                    f"engine_needs_{FIXABLE_ABSTAIN_RULES[rule]}",
                    follow_up_field=FIXABLE_ABSTAIN_RULES[rule],
                    details={"engine_status": engine_status, "rule": rule},
                )
        blocking = rules[-1] if rules else "unknown"
        return Decision(ABSTAIN, f"engine_abstain:{blocking}", details={"engine_status": engine_status})

    return Decision(ABSTAIN, "engine_status_unknown", details={"engine_status": engine_status})


def decide_missing(missing_fields: list[str]) -> Decision | None:
    if missing_fields:
        return Decision(ASK_FOLLOW_UP, "context_missing", follow_up_field=missing_fields[0], details={"missing": missing_fields})
    return None
