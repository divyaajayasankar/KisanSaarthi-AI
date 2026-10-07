"""Post-deployment smoke test for a running KisanSaarthi AI server.

    python -m scripts.smoke_test --base-url http://127.0.0.1:8000

Checks, in order: health, status, a full chat conversation, the saved trace and
profile, and the WhatsApp webhook (simulated Meta payloads, dry run). Exits 0
when every check passes, 1 when any check fails.

Chat outcome rule: a normal recommendation must carry a dose; a weather delay
or an unverified forecast must carry the planned dose (marked "do not apply
now"); any other safe abstain (PHI, growth stage, interval) is reported as a
WARN, not a failure, because it depends on the data in that deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import uuid

import httpx

DEFAULT_MESSAGE = "banana sigatoka 1 acre Theni, Tamil Nadu harvest in 30 days"
ANSWERS = {
    "location": "Theni, Tamil Nadu",
    "land_area": "1 acre",
    "land_unit": "acre",
    "harvest_days": "30",
    "growth_stage": "vegetative",
    "previous_treatment": "no",
    "days_since_last_application": "30",
    "confirm_pest": "yes",
    "pest_name": "sigatoka",
}

results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"[{status}] {name}" + (f": {detail}" if detail else ""))


def check_health(client: httpx.Client) -> None:
    response = client.get("/health")
    ok = response.status_code == 200 and response.json().get("status") == "ok"
    record("PASS" if ok else "FAIL", "GET /health", f"HTTP {response.status_code}")


def check_status(client: httpx.Client) -> None:
    response = client.get("/api/status")
    if response.status_code != 200:
        record("FAIL", "GET /api/status", f"HTTP {response.status_code}")
        return
    body = response.json()
    brief = {key: body[key] for key in list(body)[:6]}
    record("PASS", "GET /api/status", json.dumps(brief, default=str)[:200])


def chat(client: httpx.Client, session, text):
    response = client.post("/api/chat/message", json={"session_id": session, "text": text, "language": "en"})
    response.raise_for_status()
    return response.json()


def check_chat(client: httpx.Client, message: str) -> str | None:
    session, reply, text = None, None, message
    for _ in range(9):
        reply = chat(client, session, text)
        session = reply["session_id"]
        if reply.get("decision") != "ASK_FOLLOW_UP":
            break
        text = ANSWERS.get(reply.get("follow_up_field"))
        if text is None:
            record("FAIL", "chat follow-up", f"no canned answer for {reply.get('follow_up_field')}")
            return session
    decision, advisory = reply.get("decision"), reply.get("advisory") or {}
    status, rules = advisory.get("status"), advisory.get("fired_rules") or []
    if decision == "ANSWER" and status == "recommend" and advisory.get("scaled_dose_min"):
        record("PASS", "chat: recommendation with dose",
               f"{advisory.get('active_ingredient')} {advisory.get('scaled_dose_min')} {advisory.get('dose_unit')}")
    elif status == "delay" or "weather_unavailable" in rules:
        planned = advisory.get("planned_dose")
        if planned and planned.get("dose_min") and planned.get("apply_now") is False:
            record("PASS", "chat: weather hold still shows planned dose",
                   f"{planned['active_ingredient']} {planned['dose_min']} {planned['dose_unit']} (status={status or 'abstain'})")
        else:
            record("FAIL", "chat: weather hold shows no planned dose", f"status={status} rules={rules}")
    else:
        record("WARN", "chat: safe abstain", f"decision={decision} rules={rules}")
    return session


def check_trace(client: httpx.Client, session: str | None) -> None:
    if not session:
        record("FAIL", "trace", "no session")
        return
    trace = client.get(f"/api/chat/trace/{session}")
    turns = trace.json().get("turns", []) if trace.status_code == 200 else []
    record("PASS" if turns else "FAIL", "GET /api/chat/trace", f"{len(turns)} turns saved")
    profile = client.get(f"/api/chat/profile/{session}")
    record("PASS" if profile.status_code == 200 else "FAIL", "GET /api/chat/profile", f"HTTP {profile.status_code}")


def check_whatsapp(client: httpx.Client, secret: str | None, verify_token: str | None) -> None:
    sender = "9199" + uuid.uuid4().hex[:8].translate(str.maketrans("abcdef", "123456"))
    body = {"entry": [{"changes": [{"value": {"messages": [
        {"from": sender, "id": "wamid.smoke", "type": "text", "text": {"body": "Hello"}}]}}]}]}
    raw = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    response = client.post("/api/whatsapp/webhook", content=raw, headers=headers)
    if response.status_code == 403 and not secret:
        record("WARN", "POST /api/whatsapp/webhook", "server requires a signature; pass --whatsapp-secret")
    else:
        ok = response.status_code == 200 and response.json().get("messages") == 1
        record("PASS" if ok else "FAIL", "POST /api/whatsapp/webhook", f"HTTP {response.status_code}")
    if verify_token:
        handshake = client.get("/api/whatsapp/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": verify_token, "hub.challenge": "smoke"})
        record("PASS" if handshake.status_code == 200 and handshake.text == "smoke" else "FAIL",
               "GET /api/whatsapp/webhook handshake", f"HTTP {handshake.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="first chat message (crop, pest, place)")
    parser.add_argument("--whatsapp-secret", default=None)
    parser.add_argument("--verify-token", default=None)
    args = parser.parse_args()
    try:
        with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
            check_health(client)
            check_status(client)
            session = check_chat(client, args.message)
            check_trace(client, session)
            check_whatsapp(client, args.whatsapp_secret, args.verify_token)
    except httpx.HTTPError as exc:
        record("FAIL", "connection", f"{exc.__class__.__name__}: {exc}")
    failed = sum(1 for status, _, _ in results if status == "FAIL")
    warned = sum(1 for status, _, _ in results if status == "WARN")
    print(f"\n{len(results) - failed - warned} passed, {warned} warnings, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
