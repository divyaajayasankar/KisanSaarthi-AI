"""Conversational endpoints used by the chat UI (and later a WhatsApp adapter)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import conversation_service as conv
from app.services import trace_service
from app.services.chat_orchestrator import ImageInput, handle_turn
from app.services.language_service import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, t


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    session_id: str | None = None
    text: str | None = Field(default=None, max_length=2000)
    language: str | None = Field(default="auto", description="auto | en | hi | ta | te")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


@router.get("/languages")
def languages():
    return {"languages": [{"code": code, "name": LANGUAGE_NAMES[code]} for code in SUPPORTED_LANGUAGES]}


@router.get("/greeting")
def greeting(language: str = "en"):
    return {"text": t("greeting", language)}


@router.post("/message")
def chat_message(payload: ChatMessage, db: Session = Depends(get_db)):
    if not (payload.text or "").strip() and payload.latitude is None:
        raise HTTPException(status_code=400, detail="Send text or a location.")
    return handle_turn(
        db,
        session_id=payload.session_id,
        text=payload.text,
        language=payload.language,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )


@router.post("/turn")
async def chat_turn(
    session_id: str | None = Form(default=None),
    text: str | None = Form(default=None),
    language: str | None = Form(default="auto"),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    """Multipart turn: any of text, image and coordinates together."""
    image_input = None
    if image is not None and image.filename:
        try:
            image_input = ImageInput(
                content=await image.read(),
                filename=image.filename or "uploaded_image",
                content_type=image.content_type or "",
            )
        finally:
            await image.close()
    if not (text or "").strip() and image_input is None and latitude is None:
        raise HTTPException(status_code=400, detail="Send text, an image or a location.")
    return handle_turn(
        db,
        session_id=session_id or None,
        text=text,
        language=language,
        image=image_input,
        latitude=latitude,
        longitude=longitude,
    )


@router.get("/session/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    state = conv.load_state(db, session_id)
    return {
        "session_id": state["session_id"],
        "context": conv.context_summary(state),
        "history": state.get("history", []),
        "pending_field": state.get("pending_field"),
    }


@router.delete("/session/{session_id}")
def reset_session(session_id: str, db: Session = Depends(get_db)):
    state = conv.reset_state(conv.load_state(db, session_id))
    conv.save_state(db, state)
    return {"session_id": session_id, "status": "reset"}


@router.get("/profile/{session_id}")
def saved_profile(session_id: str, db: Session = Depends(get_db)):
    """The field context saved for this conversation."""
    profile = trace_service.get_profile(db, session_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No saved profile for this session.")
    return profile


@router.get("/trace/{session_id}")
def saved_trace(session_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """Per-turn audit rows: query, context, agent trace, rules, evidence, decision."""
    return {"session_id": session_id, "turns": trace_service.get_traces(db, session_id, limit=max(1, min(limit, 200)))}
