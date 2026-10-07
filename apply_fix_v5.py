"""KisanSaarthi fix v5: verified guidance is shown only when it mentions the problem itself.

Run from the project folder with the project's Python:
    .\\.venv\\Scripts\\python.exe apply_fix_v5.py

Safe to run twice. Backs up every file it edits into _backup_addons_<time>/.
If any edited Python file fails to compile, every edit is rolled back.
"""
import base64
import json
import py_compile
import shutil
import sys
import time
import zlib
from pathlib import Path

EMBEDDED = {'tests/test_knowledge_relevance.py': 'eNrlVE1v2zAMvedXENrFKYKg6XYKkEsL9Nyhwy5FISgWY3OWJVeSkwVF//so203tfmC9DnMCOOHHE8n3KCHET/S0I9RQtKSVzREoQCjdwYKz5giHEi1QhBptJGcDxBKh8W5rsF6AdRF+tSF21ty7ZimEmM123tWgmmYZ0O8pxwBUN85HyEsVpfN5iSF6FZ3/ONSrQg62PihyjnwD8BweEDV3AV+4pge1hutv56vZbJYbFQLIH6236xnwo3EHUpKlKGUW0OzmvT096e/SKFu0qkDYgEArps4aQ2BfYOfd/dQVIjbv2XFPGnmukvTgPtWRUroaeJCqxgWcnVWH1/V0uEueEFqdZX0cR81HMOo4oET8HdlLVm+E0nsKzh/F+7DPnZyQU1aPkLBn3Zx2qsKMItZhSPcYeZJgVL3VCh5a9MdFxztnukZWm4s1PIoQVWyDWINwFR8vPIbWxGTosJ4G+I7Q1no0KqKWHnPntaQgNQM2qLPa2QqPjYp5OZzf5acpPgrSjLdi9FRyOutS5WRMy+ptt5EMy5i//GJs2LFQLpXlD6hCkWXF3lLB+qnUMlUYXOtzTCg3N99vxVPP4eh8lic3FX02kmXXWfSEe5T7YY3kM92MOh7fvAPshrfp5Zj1pjeCXsrKuoNBXWCW4heps1R5qvPSq5x30QVFOezJ85R7GFY58hakhJFIT2ocu6eC7BX5wkeduiVbjOiosImf4OJixMVVaZxXljuyzARfFwZfsXFVMll0YuPat3zJbJ1H/w8Q0hef6ty91D1lwqDNJmzM06xXoKwGMepWANkpbXfn93erT9B2MeEtLaFMN7bkRaRcpis8SL6fE5mfYO/r/8je8OuvK/QHWzBg9Q=='}
PATCHES = [('app/services/chat_orchestrator.py', '    # Show a record only when it mentions the problem itself (not just the crop):\n    # keyword retrieval can return a record for the same crop and a different pest.\n    crop_words = set(normalize_text(crop).split())\n    topic_words = [w for w in normalize_text(topic).split() if len(w) >= 4 and w not in crop_words]\n    retrieved = len(items)\n    items = [\n        item for item in items\n        if any(word in normalize_text(str(item.get("text") or "")) for word in topic_words)\n    ]\n    turn.step("Knowledge Agent", status=result.get("status"), results=len(items), retrieved=retrieved)\n', '        turn.step("Knowledge Agent", status="unavailable", error=exc.__class__.__name__)\n        return\n    items = result.get("results") or []\n    turn.step("Knowledge Agent", status=result.get("status"), results=len(items))\n    turn.evidence_ids = [item.get("id") for item in items if item.get("id") is not None]\n    if not items:\n        return\n', '        turn.step("Knowledge Agent", status="unavailable", error=exc.__class__.__name__)\n        return\n    items = result.get("results") or []\n    # Show a record only when it mentions the problem itself (not just the crop):\n    # keyword retrieval can return a record for the same crop and a different pest.\n    crop_words = set(normalize_text(crop).split())\n    topic_words = [w for w in normalize_text(topic).split() if len(w) >= 4 and w not in crop_words]\n    retrieved = len(items)\n    items = [\n        item for item in items\n        if any(word in normalize_text(str(item.get("text") or "")) for word in topic_words)\n    ]\n    turn.step("Knowledge Agent", status=result.get("status"), results=len(items), retrieved=retrieved)\n    turn.evidence_ids = [item.get("id") for item in items if item.get("id") is not None]\n    if not items:\n        return\n')]
MESSAGES = {}
README_SRC = 'pass'
ENV_MARKER = "WHATSAPP_VERIFY_TOKEN"
ENV_APPEND = ''

root = Path.cwd()
if not (root / "app" / "main.py").exists():
    sys.exit("Run this from the project folder (the one that contains app\\main.py).")
stamp = time.strftime("%Y%m%d_%H%M%S")
backup = root / f"_backup_addons_{stamp}"
touched = []
created = []
report = []


def save_backup(rel):
    src = root / rel
    if src.exists() and rel not in touched:
        dest = backup / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        touched.append(rel)


def restore_all():
    for rel in touched:
        if (backup / rel).exists():
            shutil.copy2(backup / rel, root / rel)
    for rel in created:
        (root / rel).unlink(missing_ok=True)


# 1 new files
for rel, blob in EMBEDDED.items():
    data = zlib.decompress(base64.b64decode(blob))
    target = root / rel
    if target.exists() and target.read_bytes() == data:
        report.append(f"unchanged  {rel}")
        continue
    if not target.exists():
        created.append(rel)
    save_backup(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    report.append(f"written    {rel}")

# 2 anchored patches on existing files
failed = []
texts = {}
for rel, marker, anchor, new in PATCHES:
    path = root / rel
    if not path.exists():
        failed.append(f"{rel}: file not found")
        continue
    if rel not in texts:
        texts[rel] = path.read_bytes().decode("utf-8")
    text = texts[rel]
    crlf = "\r\n" in text
    work = text.replace("\r\n", "\n")
    if marker in work:
        report.append(f"already    {rel}: {(marker.strip().splitlines() or [""])[0][:48]}")
        continue
    if anchor in work:
        work = work.replace(anchor, new, 1)
    else:
        failed.append(f"{rel}: anchor not found for '{(marker.strip().splitlines() or [""])[0][:48]}'")
        continue
    texts[rel] = work.replace("\n", "\r\n") if crlf else work
    report.append(f"patched    {rel}: {(marker.strip().splitlines() or [""])[0][:48]}")
for rel, text in texts.items():
    if text != (root / rel).read_bytes().decode("utf-8"):
        save_backup(rel)
        (root / rel).write_bytes(text.encode("utf-8"))

# 3 reply text in four languages (data/i18n/messages.json)
msg_path = root / "data" / "i18n" / "messages.json"
if msg_path.exists():
    raw = msg_path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    data = json.loads(raw)
    added = [key for key in MESSAGES if key not in data]
    if added:
        for key in added:
            data[key] = MESSAGES[key]
        out = json.dumps(data, indent=2, ensure_ascii=False)
        if raw.endswith("\n"):
            out += "\n"
        save_backup("data/i18n/messages.json")
        msg_path.write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
        report.append(f"patched    data/i18n/messages.json: {len(added)} keys added")
    else:
        report.append("already    data/i18n/messages.json")
else:
    failed.append("data/i18n/messages.json not found")

# 4 README, .env.example, .gitignore (best effort, never fatal)
readme = root / "README.md"
if readme.exists():
    before = readme.read_bytes()
    save_backup("README.md")
    import io
    import contextlib
    ns = {"__name__": "readme_edit"}
    argv = sys.argv
    sys.argv = ["readme_edit", str(readme)]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(README_SRC, "readme_edit", "exec"), ns)
    except SystemExit:
        pass
    except Exception as exc:
        report.append(f"SKIPPED    README.md: {exc.__class__.__name__}: {exc} (edit by hand if wanted)")
    sys.argv = argv
    if readme.read_bytes() != before:
        report.append("patched    README.md: brief vs delivered, planned dose, deployment")
    else:
        touched.remove("README.md")
        report.append("already    README.md")
envf = root / ".env.example"
if envf.exists():
    raw = envf.read_bytes().decode("utf-8")
    if ENV_MARKER not in raw:
        save_backup(".env.example")
        crlf = "\r\n" in raw
        add = ENV_APPEND.replace("\n", "\r\n") if crlf else ENV_APPEND
        envf.write_bytes((raw.rstrip("\r\n") + ("\r\n" if crlf else "\n") + add).encode("utf-8"))
        report.append("patched    .env.example: WhatsApp variables")
    else:
        report.append("already    .env.example")
gitignore = root / ".gitignore"
if gitignore.exists():
    gi = gitignore.read_text(encoding="utf-8")
    if "logs/" not in gi:
        save_backup(".gitignore")
        gitignore.write_text(gi.rstrip("\n") + "\nlogs/\n_backup_*/\n", encoding="utf-8")
        report.append("patched    .gitignore: logs/ and _backup_*/")

# 5 compile check, roll back on failure
bad = []
for rel in list(EMBEDDED) + [p[0] for p in PATCHES]:
    if rel.endswith(".py"):
        try:
            py_compile.compile(str(root / rel), doraise=True, cfile=str(backup / "_pyc" / (rel.replace("/", "_") + "c")))
        except py_compile.PyCompileError as exc:
            bad.append(f"{rel}: {exc.msg}")
try:
    json.loads(msg_path.read_text(encoding="utf-8"))
except Exception as exc:
    bad.append(f"data/i18n/messages.json: {exc}")
print("\n".join(report))
if failed or bad:
    restore_all()
    print("\nROLLED BACK. Nothing was changed.")
    for line in failed + bad:
        print("  problem:", line)
    sys.exit(1)
shutil.rmtree(backup / "_pyc", ignore_errors=True)
if not touched:
    shutil.rmtree(backup, ignore_errors=True)
print("\nFIX V5 APPLIED." + (f" Backup of edited files: {backup.name}" if touched else " Nothing needed changing."))
