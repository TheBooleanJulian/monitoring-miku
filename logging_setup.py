"""
Centralised logging configuration for MonitoringMiku.

Outputs to:
  - stdout (INFO+) — captured by Zeabur's log viewer
  - logs/monitoringmiku.log (DEBUG+) — rotating, 5 MB × 3 backups

Call setup_logging() once at the top of main.py before anything else.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "monitoringmiku.log"
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # Capture everything; handlers filter below

    # ── Stdout handler (INFO+) ────────────────────────────────────────────────
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # ── Rotating file handler (DEBUG+) ────────────────────────────────────────
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "apscheduler.executors", "telegram.ext.Updater"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)

    logging.getLogger(__name__).info(
        f"Logging initialised — file: {LOG_FILE}, level: {logging.getLevelName(level)}"
    )
