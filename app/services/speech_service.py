"""Speech-to-text with faster-whisper on CPU.

Model size, device and compute type come from .env
(WHISPER_MODEL=small|base, WHISPER_DEVICE=cpu, WHISPER_COMPUTE_TYPE=int8).
The model downloads once on first use and is cached by faster-whisper.

The transcript is returned to the UI for the farmer to read, correct and
send. Transcription never triggers an advisory by itself.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, dataclass
from functools import lru_cache

from app.config import settings
from app.services.language_service import SUPPORTED_LANGUAGES, detect_language


class SpeechUnavailableError(RuntimeError):
    pass


class SpeechInputError(ValueError):
    pass


ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg",
    "audio/mp3", "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/aac", "video/webm",
}


@dataclass
class Transcript:
    text: str
    language: str
    whisper_language: str | None
    language_probability: float | None
    duration_seconds: float | None
    model: str
    requires_confirmation: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


def speech_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


@lru_cache(maxsize=2)
def _load_model(name: str, device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise SpeechUnavailableError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc
    try:
        return WhisperModel(name, device=device, compute_type=compute_type)
    except Exception as exc:  # first use downloads the model; fails offline
        raise SpeechUnavailableError(
            f"Whisper model '{name}' could not be loaded ({exc.__class__.__name__}). "
            "The first use needs internet access to download it (about 480 MB for 'small', "
            "145 MB for 'base'). Check the connection or set WHISPER_MODEL=base in .env. "
            "You can type your message instead."
        ) from exc


def get_model():
    return _load_model(settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)


def transcribe(audio_bytes: bytes, content_type: str | None, language_hint: str | None = None) -> Transcript:
    if not audio_bytes:
        raise SpeechInputError("Audio is empty.")
    if len(audio_bytes) > settings.max_audio_mb * 1024 * 1024:
        raise SpeechInputError(f"Audio exceeds {settings.max_audio_mb} MB.")
    media = (content_type or "").split(";")[0].strip().lower()
    if media and media not in ALLOWED_AUDIO_TYPES:
        raise SpeechInputError(f"Unsupported audio type: {media}")

    hint = (language_hint or "").strip().lower()[:2]
    hint = hint if hint in SUPPORTED_LANGUAGES else None

    model = get_model()
    suffix = ".webm" if "webm" in media else ".ogg" if "ogg" in media else ".wav" if "wav" in media else ".audio"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(audio_bytes)
        handle.close()
        segments, info = model.transcribe(
            handle.name,
            language=hint,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass

    whisper_language = getattr(info, "language", None)
    detected = detect_language(text)
    if whisper_language in SUPPORTED_LANGUAGES:
        language = whisper_language
    else:
        language = detected or hint or "en"

    return Transcript(
        text=text,
        language=language,
        whisper_language=whisper_language,
        language_probability=getattr(info, "language_probability", None),
        duration_seconds=getattr(info, "duration", None),
        model=settings.whisper_model,
    )
