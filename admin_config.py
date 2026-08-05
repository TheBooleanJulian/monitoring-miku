"""
Admin-configurable Zeabur discovery settings.

Replaces the old ZEABUR_PROJECT_IDS / ZEABUR_EXCLUDED_SERVICE_IDS CSV env vars
with a single-row SQLite table, editable from the /admin web page instead of
by hand-editing the Zeabur dashboard's environment variables.

On first run (empty table), seeds itself from those env vars if they're set,
so existing deployments keep working without any manual migration step.
"""

import json
import sqlite3
from pathlib import Path

import config

_DB_PATH = Path(__file__).parent / "monitor_state.db"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discovery_config (
                id                   INTEGER PRIMARY KEY CHECK (id = 1),
                project_ids          TEXT NOT NULL DEFAULT '[]',
                excluded_service_ids TEXT NOT NULL DEFAULT '[]'
            )
        """)


def get_config() -> dict:
    """Returns {"project_ids": [...], "excluded_service_ids": [...]}.

    Seeds from the legacy CSV env vars the first time this is called if the
    table is still empty, so existing deployments don't lose their settings."""
    _ensure_table()
    with _db() as conn:
        row = conn.execute("SELECT * FROM discovery_config WHERE id = 1").fetchone()

    if row is None:
        seeded = {
            "project_ids": list(config.ZEABUR_PROJECT_IDS),
            "excluded_service_ids": sorted(config.ZEABUR_EXCLUDED_SERVICE_IDS),
        }
        set_config(seeded["project_ids"], seeded["excluded_service_ids"])
        return seeded

    return {
        "project_ids": json.loads(row["project_ids"]),
        "excluded_service_ids": json.loads(row["excluded_service_ids"]),
    }


def set_config(project_ids: list[str], excluded_service_ids: list[str]) -> None:
    _ensure_table()
    with _db() as conn:
        conn.execute("""
            INSERT INTO discovery_config (id, project_ids, excluded_service_ids)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_ids          = excluded.project_ids,
                excluded_service_ids = excluded.excluded_service_ids
        """, (json.dumps(project_ids), json.dumps(excluded_service_ids)))
