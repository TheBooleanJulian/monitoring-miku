"""Shared utilities for command handlers."""

import io
from telegram import Update
from telegram.constants import ParseMode
from bot_registry import BotInfo, resolve_bot, bot_list_text

MAX_TELEGRAM_MESSAGE = 4000  # Telegram's actual limit is 4096; leave buffer


def parse_bot_arg(args: list[str]) -> tuple[BotInfo | None, str | None]:
    """
    Extracts bot key from command args.
    Returns (BotInfo, None) on success or (None, error_message) on failure.
    """
    if not args:
        return None, (
            "Please specify a bot\\.\n\n"
            "*Available bots:*\n" + bot_list_text()
        )
    bot = resolve_bot(args[0])
    if not bot:
        return None, (
            f"Unknown bot: `{args[0]}`\n\n"
            "*Available bots:*\n" + bot_list_text()
        )
    return bot, None


async def send_or_file(
    update: Update,
    text: str,
    filename: str = "output.txt",
    caption: str = "",
) -> None:
    """
    Sends text as a message if short enough, otherwise as a .txt file attachment.
    """
    if len(text) <= MAX_TELEGRAM_MESSAGE:
        await update.message.reply_text(
            f"```\n{text}\n```",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        buf = io.BytesIO(text.encode("utf-8"))
        buf.name = filename
        await update.message.reply_document(
            document=buf,
            filename=filename,
            caption=caption or f"Output too long — sent as {filename}",
        )
