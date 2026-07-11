"""
/logs <bot> [--n=100]

Fetches and displays recent log lines from a Zeabur deployment.
If output is too long for a message, sends as a .txt file.

Examples:
  /logs miguquest
  /logs apod --n=200
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import LOG_LINES_DEFAULT, LOG_LINES_MAX
from bot_registry import resolve_bot
from services import zeabur
from handlers.utils import parse_bot_arg, send_or_file


def _parse_n(args: list[str]) -> int:
    """Extracts --n=N or positional int from args."""
    for arg in args[1:]:
        if arg.startswith("--n="):
            try:
                return min(int(arg.split("=")[1]), LOG_LINES_MAX)
            except ValueError:
                pass
        try:
            return min(int(arg), LOG_LINES_MAX)
        except ValueError:
            pass
    return LOG_LINES_DEFAULT


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    bot, err = parse_bot_arg(args)
    if err:
        await update.message.reply_text(err, parse_mode=ParseMode.MARKDOWN)
        return

    n = _parse_n(args)
    msg = await update.message.reply_text(
        f"📋 Fetching last {n} lines from *{bot.name}*...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # First get the service to find the latest deployment ID
        info = await zeabur.get_service_status(bot.zeabur_service_id)
        dep = info.get("latestDeployment")
        if not dep:
            await msg.edit_text(f"❌ *{bot.name}* has no deployments.", parse_mode=ParseMode.MARKDOWN)
            return

        deployment_id = dep["id"]
        status = dep.get("status", "UNKNOWN")

        # Fetch logs
        log_entries = await zeabur.get_service_logs(bot.zeabur_service_id, deployment_id, n)
        lines = zeabur.format_log_lines(log_entries)

        if not lines:
            await msg.edit_text(
                f"📋 *{bot.name}* — no logs available for current deployment\\.\n"
                f"Status: `{status}`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        log_text = "\n".join(lines)
        header = f"── {bot.name} · last {len(lines)} lines · status {status} ──\n\n"

        await msg.delete()
        await send_or_file(
            update,
            text=header + log_text,
            filename=f"{bot.key}-logs.txt",
            caption=f"{bot.name} logs — {len(lines)} lines",
        )

    except Exception as e:
        await msg.edit_text(
            f"❌ Failed to fetch logs for *{bot.name}*:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
