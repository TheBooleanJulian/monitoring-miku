"""
/start and /help handlers.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot_registry import bot_list_text

_HELP_TEXT = """
🎐 *MonitoringMiku*
_Your fleet command centre_

*Commands:*
`/status` — health of all bots at a glance
`/logs <bot>` — tail recent logs  _(add `--n=200` for more)_
`/debug <bot>` — 🤖 Claude AI diagnosis
`/commits <bot>` — recent GitHub commits
`/restart <bot>` — hot-restart a service
`/deploy <bot>` — full redeploy from latest commit
`/incidents` — show persisted incident state

*Bots you can target:*
{bot_list}

*Examples:*
`/debug miguquest`
`/logs apod --n=200`
`/commits nac`
`/restart mkmon`
""".strip()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        _HELP_TEXT.format(bot_list=bot_list_text()),
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        _HELP_TEXT.format(bot_list=bot_list_text()),
        parse_mode=ParseMode.MARKDOWN,
    )
