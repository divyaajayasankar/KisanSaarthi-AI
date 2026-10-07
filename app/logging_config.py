"""One-call logging setup. Logs go to the console and logs/kisansaarthi.log."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger("kisansaarthi")
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        handler = RotatingFileHandler(log_dir / "kisansaarthi.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(fmt)
        root.addHandler(handler)
    except OSError:
        pass  # read-only folder: console logging only
    root.propagate = False
    _CONFIGURED = True
