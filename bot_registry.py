"""
Bot registry — auto-discovered from Zeabur + GitHub instead of hand-maintained.

Every service found across the admin-selected Zeabur projects is treated as a
monitored bot unless its service ID is excluded (non-bot infra sharing those
projects — databases, monitoring-miku itself, repo-tracker, etc). Both lists
are picked from the /admin web page and persisted via admin_config.py — no
manual env var editing. New bots need zero code changes: deploy them into a
tracked project and they show up on the next refresh.

Discovered data is cached in monitor_state.db (same file/connection pattern as
monitor/health_monitor.py) so startup never blocks on Zeabur/GitHub being
reachable, and so a bot's `key` — the incidents table's primary key — stays
stable across restarts even if discovery re-runs or the service gets renamed
(lookup is keyed on zeabur_service_id, not name).

Public API (all_bots, resolve_bot, bot_list_text) is unchanged from the old
static-dict version — every existing call site keeps working untouched.
"""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from services import zeabur, github
import admin_config

_DB_PATH = Path(__file__).parent / "monitor_state.db"


@dataclass
class BotInfo:
    name: str
    key: str                  # canonical key used in commands
    zeabur_service_id: str    # from Zeabur dashboard > service > settings
    github_repo: str          # repo name under TheBooleanJulian
    description: str
    emoji: str
    health_url: str = ""      # Optional HTTP /health endpoint — if set, monitor pings it too


BOTS: Dict[str, BotInfo] = {}


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registry (
                zeabur_service_id TEXT PRIMARY KEY,
                bot_key           TEXT NOT NULL,
                name              TEXT,
                github_repo       TEXT,
                description       TEXT,
                emoji             TEXT,
                health_url        TEXT,
                last_discovered   TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registry_overrides (
                zeabur_service_id TEXT PRIMARY KEY,
                emoji             TEXT,
                description       TEXT,
                github_repo       TEXT
            )
        """)


def _load_registry_rows() -> list[sqlite3.Row]:
    with _db() as conn:
        return conn.execute("SELECT * FROM registry").fetchall()


def _load_overrides() -> Dict[str, dict]:
    with _db() as conn:
        rows = conn.execute("SELECT * FROM registry_overrides").fetchall()
    return {row["zeabur_service_id"]: dict(row) for row in rows}


def _upsert_registry(bots: list[BotInfo]) -> None:
    import datetime
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    with _db() as conn:
        for bot in bots:
            conn.execute("""
                INSERT INTO registry
                    (zeabur_service_id, bot_key, name, github_repo, description, emoji, health_url, last_discovered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(zeabur_service_id) DO UPDATE SET
                    bot_key         = excluded.bot_key,
                    name            = excluded.name,
                    github_repo     = excluded.github_repo,
                    description     = excluded.description,
                    emoji           = excluded.emoji,
                    health_url      = excluded.health_url,
                    last_discovered = excluded.last_discovered
            """, (
                bot.zeabur_service_id, bot.key, bot.name, bot.github_repo,
                bot.description, bot.emoji, bot.health_url, now,
            ))


# ── Name matching / slugging ──────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Case/punctuation-insensitive form used for both repo matching and lookup."""
    return re.sub(r"[-_\s]", "", s.lower())


def _slugify(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "bot"
    candidate = base
    i = 2
    while candidate in taken:
        candidate = f"{base}-{i}"
        i += 1
    return candidate


# ── Discovery ─────────────────────────────────────────────────────────────────

async def discover_bots() -> list[BotInfo]:
    """Queries Zeabur + GitHub and builds the fleet's BotInfo list."""
    _ensure_tables()

    discovery = admin_config.get_config()
    excluded = set(discovery["excluded_service_ids"])
    services = await zeabur.list_all_services(discovery["project_ids"])
    services = [s for s in services if s["id"] not in excluded]

    try:
        repos = await github.list_repos()
    except Exception:
        repos = []
    repo_index = {_normalize(r["name"]): r["name"] for r in repos}

    previous_keys = {row["zeabur_service_id"]: row["bot_key"] for row in _load_registry_rows()}
    overrides = _load_overrides()

    used_keys = set(previous_keys.values())
    bots = []
    for service in services:
        sid = service["id"]
        name = service["name"]

        key = previous_keys.get(sid)
        if not key:
            key = _slugify(name, used_keys)
            used_keys.add(key)

        override = overrides.get(sid, {})
        matched_repo = repo_index.get(_normalize(name), "")

        bots.append(BotInfo(
            name=name,
            key=key,
            zeabur_service_id=sid,
            github_repo=override.get("github_repo") or matched_repo,
            description=override.get("description") or "",
            emoji=override.get("emoji") or "🤖",
            health_url="",
        ))
    return bots


def load_cached_registry() -> None:
    """Sync, instant — populates BOTS from the last-known-good SQLite cache."""
    global BOTS
    _ensure_tables()
    rows = _load_registry_rows()
    overrides = _load_overrides()
    cached = {}
    for row in rows:
        sid = row["zeabur_service_id"]
        override = overrides.get(sid, {})
        cached[row["bot_key"]] = BotInfo(
            name=row["name"],
            key=row["bot_key"],
            zeabur_service_id=sid,
            github_repo=override.get("github_repo") or row["github_repo"] or "",
            description=override.get("description") or row["description"] or "",
            emoji=override.get("emoji") or row["emoji"] or "🤖",
            health_url=row["health_url"] or "",
        )
    BOTS = cached


async def refresh_registry() -> int:
    """Async — re-runs discovery, persists it, and swaps BOTS. Returns bot count."""
    global BOTS
    discovered = await discover_bots()
    _upsert_registry(discovered)
    BOTS = {bot.key: bot for bot in discovered}
    return len(BOTS)


# ── Public lookup API (unchanged shape — every call site keeps working) ──────

def resolve_bot(raw: str) -> Optional[BotInfo]:
    """Case/punctuation-insensitive lookup by key or bot name."""
    norm = _normalize(raw)
    for bot in BOTS.values():
        if bot.key == raw or _normalize(bot.key) == norm or _normalize(bot.name) == norm:
            return bot
    return None


def all_bots() -> list[BotInfo]:
    return list(BOTS.values())


def bot_list_text() -> str:
    """Returns a formatted string listing all bots for help messages."""
    if not BOTS:
        return "  _(none discovered yet — try /refresh_registry)_"
    return "\n".join(
        f"  {b.emoji} `{b.key}` — {b.name}" for b in BOTS.values()
    )
