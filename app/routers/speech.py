"""Voice input: audio -> transcript for the farmer to confirm.

The transcript is returned to the UI and placed in the message box.
Nothing is sent to the advisory pipeline until the farmer presses Send.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.services.speech_service import (
    SpeechInputError,
    SpeechUnavailableError,
    speech_available,
    transcribe,
)


router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.get("/status")
def status():
    return {
        "available": speech_available(),
        "engine": "faster-whisper",
        "model": settings.whisper_model,
        "device": settings.whisper_device,
        "compute_type": settings.whisper_compute_type,
    }


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
):
    try:
        data = await audio.read()
    finally:
        await audio.close()
    try:
        result = transcribe(data, audio.content_type, language_hint=language)
    except SpeechInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SpeechUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # decoding failures, missing ffmpeg codecs etc.
        raise HTTPException(status_code=422, detail=f"Could not transcribe audio: {exc.__class__.__name__}") from exc
    return result.as_dict()
