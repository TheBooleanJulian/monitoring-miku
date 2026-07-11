"""
/debug <bot>

The star feature. Fetches logs + recent commits and sends everything to Claude
for AI-powered root cause analysis. Returns a structured diagnosis.

Examples:
  /debug miguquest
  /debug nac
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import LOG_LINES_DEFAULT
from services import zeabur, github
from services.claude_debug import debug_bot_logs
from handlers.utils import parse_bot_arg


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    bot, err = parse_bot_arg(args)
    if err:
        await update.message.reply_text(err, parse_mode=ParseMode.MARKDOWN)
        return

    msg = await update.message.reply_text(
        f"🔬 Diagnosing *{bot.name}*...\n\n"
        f"_Step 1/3: Fetching service status_",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # ── Step 1: Zeabur status + logs ────────────────────────────────────
        info = await zeabur.get_service_status(bot.zeabur_service_id)
        dep = info.get("latestDeployment") or {}
        deployment_id = dep.get("id")
        zeabur_status = dep.get("status", "UNKNOWN")

        await msg.edit_text(
            f"🔬 Diagnosing *{bot.name}*...\n\n"
            f"✅ Status: `{zeabur_status}`\n"
            f"_Step 2/3: Fetching logs + commits_",
            parse_mode=ParseMode.MARKDOWN,
        )

        log_lines = []
        if deployment_id:
            log_entries = await zeabur.get_service_logs(
                bot.zeabur_service_id, deployment_id, LOG_LINES_DEFAULT
            )
            log_lines = zeabur.format_log_lines(log_entries)

        # ── Step 2: GitHub context ───────────────────────────────────────────
        recent_commits = []
        latest_diff = ""
        try:
            recent_commits = await github.get_recent_commits(bot.github_repo, count=5)
            latest_diff = await github.get_latest_diff(bot.github_repo)
        except Exception as gh_err:
            # GitHub context is best-effort — don't fail the whole debug
            pass

        await msg.edit_text(
            f"🔬 Diagnosing *{bot.name}*...\n\n"
            f"✅ Status: `{zeabur_status}`\n"
            f"✅ Collected {len(log_lines)} log lines · {len(recent_commits)} commits\n"
            f"_Step 3/3: Asking Claude..._",
            parse_mode=ParseMode.MARKDOWN,
        )

        # ── Step 3: Claude analysis ──────────────────────────────────────────
        diagnosis = await debug_bot_logs(
            bot_name=bot.name,
            description=bot.description,
            log_lines=log_lines,
            recent_commits=recent_commits,
            latest_diff=latest_diff,
        )

        result = (
            f"🤖 *{bot.name} · AI Diagnosis*\n"
            f"_Zeabur status: `{zeabur_status}` · {len(log_lines)} log lines analysed_\n\n"
            f"{diagnosis}"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(
            f"❌ Debug failed for *{bot.name}*:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
