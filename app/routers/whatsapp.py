"""WhatsApp Cloud API adapter.

Receives WhatsApp messages (text, photo, shared location) from Meta's webhook,
runs them through the same conversation engine as the web chat
(`handle_turn`, channel="whatsapp") and sends the reply back. One WhatsApp
number is one conversation session, so the field context persists between
messages exactly as in the browser.

Configuration (environment, see .env.example):
    WHATSAPP_VERIFY_TOKEN     token you type into the Meta webhook setup page
    WHATSAPP_APP_SECRET       optional; when set, every POST must carry a valid
                              X-Hub-Signature-256 header
    WHATSAPP_ACCESS_TOKEN     permanent token for sending replies and reading photos
    WHATSAPP_PHONE_NUMBER_ID  the sending phone number id from Meta

Without the access token and phone number id the adapter still processes the
message and returns the reply in the HTTP response ("dry run"). It has been
tested with simulated Meta payloads only; it has not been run against live
WhatsApp.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any, Iterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.chat_orchestrator import ImageInput, handle_turn

logger = logging.getLogger("kisansaarthi.whatsapp")
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

GRAPH = "https://graph.facebook.com/v20.0"
MAX_BODY = 4000

UNSUPPORTED = {
    "audio": "Voice messages are not supported yet. Please type your question or send a photo.",
    "default": "I can read text, photos and shared locations. Please send one of those.",
}


def _cfg(name: str) -> str:
    return os.getenv(name, "").strip()


def verify_signature(secret: str, raw: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


def iter_messages(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                yield message


def _download_photo(media_id: str) -> ImageInput | None:
    token = _cfg("WHATSAPP_ACCESS_TOKEN")
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=20.0) as client:
            meta = client.get(f"{GRAPH}/{media_id}", headers=headers)
            meta.raise_for_status()
            info = meta.json()
            data = client.get(info["url"], headers=headers)
            data.raise_for_status()
        return ImageInput(content=data.content, filename=f"{media_id}.jpg", content_type=info.get("mime_type", "image/jpeg"))
    except (httpx.HTTPError, KeyError, ValueError):
        logger.warning("could not download WhatsApp media")
        return None


def _send(to: str, body: str) -> dict[str, Any]:
    token, phone_id = _cfg("WHATSAPP_ACCESS_TOKEN"), _cfg("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        return {"sent": False, "reason": "not_configured"}
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{GRAPH}/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}},
            )
            response.raise_for_status()
        return {"sent": True}
    except httpx.HTTPError:
        logger.warning("WhatsApp send failed")
        return {"sent": False, "reason": "send_failed"}


def reply_text(turn: dict[str, Any]) -> str:
    parts = [m["text"] for m in turn.get("messages", []) if m.get("text") and m.get("kind") != "info"]
    return "\n\n".join(parts)[:MAX_BODY]


def handle_message(db: Session, message: dict[str, Any]) -> dict[str, Any]:
    sender = str(message.get("from", "")).strip()
    kind = message.get("type")
    if not sender:
        return {"handled": False, "reason": "no_sender"}
    text, image, latitude, longitude = None, None, None, None
    if kind == "text":
        text = (message.get("text") or {}).get("body")
    elif kind == "image":
        photo = message.get("image") or {}
        text = photo.get("caption")
        image = _download_photo(photo.get("id", "")) if photo.get("id") else None
        if image is None and not text:
            body = "I could not open the photo. Please send it again or type the problem."
            return {"handled": True, "to": sender, "reply": body, **_send(sender, body)}
    elif kind == "location":
        place = message.get("location") or {}
        latitude, longitude = place.get("latitude"), place.get("longitude")
    else:
        body = UNSUPPORTED["audio"] if kind == "audio" else UNSUPPORTED["default"]
        return {"handled": True, "to": sender, "reply": body, **_send(sender, body)}

    turn = handle_turn(
        db, session_id=f"wa-{sender}", text=text, language="auto",
        image=image, latitude=latitude, longitude=longitude, channel="whatsapp",
    )
    body = reply_text(turn)
    return {"handled": True, "to": sender, "decision": turn.get("decision"), "reply": body, **_send(sender, body)}


@router.get("/webhook")
def verify(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    expected = _cfg("WHATSAPP_VERIFY_TOKEN")
    if mode == "subscribe" and expected and hmac.compare_digest(token or "", expected):
        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed.")


@router.post("/webhook")
async def receive(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    secret = _cfg("WHATSAPP_APP_SECRET")
    if secret and not verify_signature(secret, raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Bad signature.")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Body is not JSON.")
    results = [handle_message(db, message) for message in iter_messages(payload)]
    configured = bool(_cfg("WHATSAPP_ACCESS_TOKEN") and _cfg("WHATSAPP_PHONE_NUMBER_ID"))
    response: dict[str, Any] = {"status": "ok", "messages": len(results)}
    if not configured:
        response["dry_run"] = True
        response["results"] = results
    return response
