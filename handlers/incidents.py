"""
/incidents — Shows the current state of all tracked incidents from the DB.

Useful after a restart to confirm MonitoringMiku picked up its prior state.
"""

from datetime import datetime, timezone
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot_registry import all_bots
from monitor.health_monitor import _get_state, _fmt_duration


async def incidents_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(tz=timezone.utc)
    lines = ["*MonitoringMiku · Incident State*\n"]

    any_incident = False
    for bot in all_bots():
        state = _get_state(bot.key)
        down_since = state["down_since"]
        last_alerted = state["last_alerted"]
        last_status = state.get("last_status") or "—"

        if down_since:
            any_incident = True
            duration = _fmt_duration(int((now - down_since).total_seconds()))
            alerted_str = ""
            if last_alerted:
                mins_ago = int((now - last_alerted).total_seconds() / 60)
                alerted_str = f"  ·  last alerted {mins_ago}m ago"
            lines.append(
                f"🚨 *{bot.name}*  `{last_status}`\n"
                f"   Down since: {down_since.strftime('%d %b %H:%M UTC')} ({duration}){alerted_str}"
            )
        else:
            lines.append(f"✅ *{bot.name}*  `{last_status}`  — no active incident")

    if not any_incident:
        lines.append("\n_No active incidents tracked._")

    lines.append("\n_State persisted in monitor\\_state.db_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
