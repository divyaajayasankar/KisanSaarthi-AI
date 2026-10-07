"""Writes real sample inputs and outputs for every crop, from YOUR registry.

Run from the project folder:
    .\\.venv\\Scripts\\python.exe make_samples.py

For each verified registry row it sends one typed question through the chat
engine (same code as the web page, same database, live weather if your key is
set) and records the reply. Crops with no registry row get one question that
shows the safe refusal. Output: reports/sample_inputs_outputs.md
Takes a few minutes because each question calls the weather service.
"""
import sys
import time
from pathlib import Path

root = Path.cwd()
if not (root / "app" / "main.py").exists():
    sys.exit("Run this from the project folder (the one that contains app\\main.py).")
sys.path.insert(0, str(root))

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import RegistryEntry

CROPS = ["Rice", "Wheat", "Maize", "Tomato", "Chilli", "Brinjal", "Onion", "Potato", "Okra",
         "Cabbage", "Groundnut", "Chickpea", "Mustard", "Cotton", "Banana"]
PLACE = "Chennai, Tamil Nadu"
ANSWERS = {"location": PLACE, "land_area": "1 acre", "land_unit": "acre", "harvest_days": "200",
           "growth_stage": "vegetative", "previous_treatment": "no", "days_since_last_application": "30",
           "confirm_pest": "yes", "pest_name": "I do not know"}
client = TestClient(app)


def ask(first):
    session, text, reply = None, first, None
    for _ in range(9):
        reply = client.post("/api/chat/message", json={"session_id": session, "text": text, "language": "en"}).json()
        session = reply["session_id"]
        if reply.get("decision") != "ASK_FOLLOW_UP":
            break
        text = ANSWERS.get(reply.get("follow_up_field"), "no")
    body = "\n\n".join(m["text"] for m in reply["messages"] if m.get("kind") not in ("info", "knowledge"))
    return reply.get("decision"), body


with SessionLocal() as db:
    rows = [(r.crop, r.pest, r.active_ingredient, r.dose_min_per_hectare, r.dose_max_per_hectare, r.dose_unit, r.phi_days)
            for r in db.query(RegistryEntry).filter(RegistryEntry.verified.is_(True)).order_by(RegistryEntry.crop, RegistryEntry.pest)]
have = {}
for row in rows:
    have.setdefault(row[0].strip().lower(), []).append(row)

out = [f"# Sample inputs and outputs (real replies, generated {time.strftime('%Y-%m-%d %H:%M')})", "",
       f"Every question uses 1 acre, {PLACE}, harvest in 200 days, vegetative stage, no earlier spray. "
       "Weather is live at the time of the run, so a rain or wind hold can appear. "
       "Quantities are the registry label dose per hectare scaled to 1 acre.", ""]
print("Crops WITH registry rows:", ", ".join(sorted(c.title() for c in have)))
missing = [c for c in CROPS if c.lower() not in have]
print("Crops WITHOUT registry rows:", ", ".join(missing) or "none")
out += ["## Crops that give a dose when you type the problem",
        ", ".join(sorted(c.title() for c in have)) or "none", "",
        "## Crops that do not (no verified registry row)", ", ".join(missing) or "none", ""]
for crop in sorted(have):
    out.append(f"## {crop.title()}")
    for (c, pest, ai, dmin, dmax, unit, phi) in have[crop]:
        name = pest.split(";")[0].strip()
        question = f"{c} {name} 1 acre {PLACE} harvest in 200 days"
        print("Asking:", question)
        decision, body = ask(question)
        out += [f"**Input:** {question}", f"(registry: {ai}, {dmin} {unit} per hectare, PHI {phi} days)", "",
                f"**Decision:** {decision}", "", "```", body, "```", ""]
for crop in missing:
    question = f"{crop} leaf spot 1 acre {PLACE} harvest in 200 days"
    print("Asking:", question)
    decision, body = ask(question)
    out += [f"## {crop} (no registry row)", f"**Input:** {question}", "", f"**Decision:** {decision}", "", "```", body, "```", ""]
target = root / "reports" / "sample_inputs_outputs.md"
target.parent.mkdir(exist_ok=True)
target.write_text("\n".join(out), encoding="utf-8")
print("\nWrote", target)
