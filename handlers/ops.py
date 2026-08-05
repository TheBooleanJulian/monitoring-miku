"""
/restart <bot>          — Hot-restarts the service process (no new deployment)
/deploy  <bot>          — Triggers a full redeploy from the latest Git commit
/refresh_registry       — Re-runs bot auto-discovery against Zeabur + GitHub now
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import bot_registry
from services import zeabur
from handlers.utils import parse_bot_arg


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    bot, err = parse_bot_arg(args)
    if err:
        await update.message.reply_text(err, parse_mode=ParseMode.MARKDOWN)
        return

    msg = await update.message.reply_text(
        f"🔄 Restarting *{bot.name}*...", parse_mode=ParseMode.MARKDOWN
    )
    try:
        await zeabur.restart_service(bot.zeabur_service_id)
        await msg.edit_text(
            f"✅ *{bot.name}* restart triggered\\.\n"
            f"_Use /status in ~15s to confirm it's running\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        await msg.edit_text(
            f"❌ Restart failed for *{bot.name}*:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def deploy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    bot, err = parse_bot_arg(args)
    if err:
        await update.message.reply_text(err, parse_mode=ParseMode.MARKDOWN)
        return

    msg = await update.message.reply_text(
        f"🚀 Triggering redeploy for *{bot.name}*...", parse_mode=ParseMode.MARKDOWN
    )
    try:
        await zeabur.redeploy_service(bot.zeabur_service_id)
        await msg.edit_text(
            f"✅ *{bot.name}* redeploy triggered\\.\n"
            f"_Use /status in ~60s to confirm the new deployment is running\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        await msg.edit_text(
            f"❌ Redeploy failed for *{bot.name}*:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def refresh_registry_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("🔎 Re-running bot auto-discovery...", parse_mode=ParseMode.MARKDOWN)
    try:
        count = await bot_registry.refresh_registry()
        await msg.edit_text(
            f"✅ Registry refreshed — {count} bot(s) discovered.\n\n"
            "*Bots:*\n" + bot_registry.bot_list_text(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await msg.edit_text(
            f"❌ Registry refresh failed:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
