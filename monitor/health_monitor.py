"""
Background health monitor.

Runs every HEALTH_CHECK_INTERVAL seconds and DMs Julian if any bot goes down.
Tracks state to avoid spam — alerts once on first failure, then again if still
down after ALERT_REPEAT_MINUTES, then every ALERT_REPEAT_MINUTES thereafter.

State is persisted to SQLite so incident tracking survives MonitoringMiku restarts.
DB file: monitor_state.db (next to main.py, auto-created on first run).
"""

import logging
import sqlite3
import httpx
from datetime import datetime, timezone
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from telegram.constants import ParseMode

from config import (
    TELEGRAM_OWNER_CHAT_ID,
    HEALTH_CHECK_INTERVAL_SECONDS,
    ALERT_REPEAT_MINUTES,
)
from bot_registry import all_bots, BotInfo
from services import zeabur

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "monitor_state.db"
_ISO = "%Y-%m-%dT%H:%M:%S+00:00"


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates the incidents table if it doesn't exist. Called at startup."""
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                bot_key      TEXT PRIMARY KEY,
                down_since   TEXT,          -- ISO datetime or NULL
                last_alerted TEXT,          -- ISO datetime or NULL
                last_status  TEXT
            )
        """)
    log.info(f"[health] State DB ready at {_DB_PATH}")


def _get_state(key: str) -> dict:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE bot_key = ?", (key,)
        ).fetchone()
    if row is None:
        return {"down_since": None, "last_alerted": None, "last_status": None}
    return {
        "down_since":   _parse_dt(row["down_since"]),
        "last_alerted": _parse_dt(row["last_alerted"]),
        "last_status":  row["last_status"],
    }


def _save_state(key: str, down_since: datetime | None, last_alerted: datetime | None, last_status: str) -> None:
    with _db() as conn:
        conn.execute("""
            INSERT INTO incidents (bot_key, down_since, last_alerted, last_status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bot_key) DO UPDATE SET
                down_since   = excluded.down_since,
                last_alerted = excluded.last_alerted,
                last_status  = excluded.last_status
        """, (
            key,
            down_since.strftime(_ISO) if down_since else None,
            last_alerted.strftime(_ISO) if last_alerted else None,
            last_status,
        ))


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


async def _check_bot(app: Application, bot: BotInfo) -> None:
    state = _get_state(bot.key)
    now = datetime.now(tz=timezone.utc)

    try:
        info = await zeabur.get_service_status(bot.zeabur_service_id)
        dep = info.get("latestDeployment") or {}
        status = dep.get("status", "UNKNOWN")
        is_up = status == zeabur.RUNNING

    except Exception as fetch_err:
        log.warning(f"[health] Failed to check {bot.name} via Zeabur API: {fetch_err}")
        is_up = False
        status = "FETCH_ERROR"

    # Secondary: if bot exposes a /health URL, ping it too
    # A bot can be "RUNNING" on Zeabur but deadlocked internally
    if is_up and bot.health_url:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(bot.health_url)
            if resp.status_code >= 500:
                log.warning(f"[health] {bot.name} /health returned HTTP {resp.status_code}")
                is_up = False
                status = f"HTTP_{resp.status_code}"
        except Exception as http_err:
            log.warning(f"[health] {bot.name} /health ping failed: {http_err}")
            is_up = False
            status = "HEALTH_ENDPOINT_UNREACHABLE"

    if is_up:
        # Recovered — send recovery message if we were tracking an incident
        if state["down_since"] is not None:
            downtime_secs = int((now - state["down_since"]).total_seconds())
            await app.bot.send_message(
                chat_id=TELEGRAM_OWNER_CHAT_ID,
                text=(
                    f"✅ *{bot.name}* is back online\n"
                    f"_Was down for {_fmt_duration(downtime_secs)}_"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        _save_state(bot.key, down_since=None, last_alerted=None, last_status=status)
        return

    # Bot is down — open incident if not already tracking
    down_since = state["down_since"] or now

    should_alert = False
    if state["last_alerted"] is None:
        should_alert = True  # First alert for this incident
    else:
        mins_since_alert = (now - state["last_alerted"]).total_seconds() / 60
        if mins_since_alert >= ALERT_REPEAT_MINUTES:
            should_alert = True

    if should_alert:
        down_for = _fmt_duration(int((now - down_since).total_seconds()))
        await app.bot.send_message(
            chat_id=TELEGRAM_OWNER_CHAT_ID,
            text=(
                f"🚨 *{bot.name}* is DOWN\n"
                f"Status: `{status}`  ·  Down for: {down_for}\n\n"
                f"_/debug {bot.key}  ·  /restart {bot.key}_"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        log.warning(f"[health] Alert sent: {bot.name} is {status}")
        _save_state(bot.key, down_since=down_since, last_alerted=now, last_status=status)
    else:
        # Update last_status in DB even if not alerting
        _save_state(bot.key, down_since=down_since, last_alerted=state["last_alerted"], last_status=status)


async def run_health_checks(app: Application) -> None:
    """Called by the scheduler — checks all bots in sequence."""
    log.info("[health] Running scheduled health check")
    for bot in all_bots():
        await _check_bot(app, bot)


def start_health_monitor(app: Application) -> AsyncIOScheduler:
    """
    Initialises the SQLite state DB, then starts the APScheduler background job.
    Returns the scheduler so it can be stopped on shutdown.
    """
    init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_health_checks,
        trigger="interval",
        seconds=HEALTH_CHECK_INTERVAL_SECONDS,
        args=[app],
        id="health_check",
        name="Bot fleet health monitor",
        misfire_grace_time=60,
    )
    scheduler.start()
    log.info(
        f"[health] Monitor started — checking every {HEALTH_CHECK_INTERVAL_SECONDS}s, "
        f"alerting owner chat {TELEGRAM_OWNER_CHAT_ID}"
    )
    return scheduler


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m"
