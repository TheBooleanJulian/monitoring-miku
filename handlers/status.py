"""
/status — Shows health of all bots at a glance.

Usage: /status
"""

from datetime import datetime, timezone
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot_registry import all_bots
from services import zeabur

_STATUS_EMOJI = {
    "RUNNING": "✅",
    "STOPPED": "❌",
    "SLEEPING": "💤",
    "DEPLOYING": "🔄",
    "FAILED": "⚠️",
    "REMOVED": "🗑️",
}


def _fmt_deploy_time(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M")
    except Exception:
        return iso[:16]


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("🔍 Checking fleet status\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    lines = ["*MonitoringMiku · Fleet Status*", ""]
    all_ok = True

    for bot in all_bots():
        try:
            info = await zeabur.get_service_status(bot.zeabur_service_id)
            dep = info.get("latestDeployment") or {}
            status = dep.get("status", "UNKNOWN")
            deploy_time = _fmt_deploy_time(dep.get("createdAt", ""))

            emoji = _STATUS_EMOJI.get(status, "❓")
            if status != "RUNNING":
                all_ok = False

            deploy_str = f"  ·  deployed {deploy_time}" if deploy_time else ""
            lines.append(f"{emoji} *{bot.name}*  `{status}`{deploy_str}")

        except Exception as e:
            all_ok = False
            err = str(e)[:50]
            lines.append(f"⚠️ *{bot.name}*  `FETCH ERROR` — {err}")

    lines.append("")
    if all_ok:
        lines.append("_All systems operational_")
    else:
        lines.append("_Run /debug <bot> for AI analysis_")

    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
