"""
/commits <bot> [--n=5]

Shows the most recent GitHub commits for a bot's repo.

Examples:
  /commits apod
  /commits miguquest --n=10
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services import github
from handlers.utils import parse_bot_arg


def _parse_n(args: list[str]) -> int:
    for arg in args[1:]:
        if arg.startswith("--n="):
            try:
                return min(int(arg.split("=")[1]), 20)
            except ValueError:
                pass
        try:
            return min(int(arg), 20)
        except ValueError:
            pass
    return 5


async def commits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    bot, err = parse_bot_arg(args)
    if err:
        await update.message.reply_text(err, parse_mode=ParseMode.MARKDOWN)
        return

    n = _parse_n(args)
    msg = await update.message.reply_text(
        f"📦 Fetching commits for *{bot.name}*...", parse_mode=ParseMode.MARKDOWN
    )

    try:
        commits = await github.get_recent_commits(bot.github_repo, count=n)
        if not commits:
            await msg.edit_text(
                f"No commits found for `{bot.github_repo}`.", parse_mode=ParseMode.MARKDOWN
            )
            return

        lines = [f"📦 *{bot.name}* · last {len(commits)} commits\n"]
        for c in commits:
            msg_text = c["message"][:72]
            lines.append(f"`{c['sha']}` {c['date']} — {msg_text}")

        lines.append(f"\n[View on GitHub](https://github.com/TheBooleanJulian/{bot.github_repo}/commits)")

        await msg.edit_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    except Exception as e:
        await msg.edit_text(
            f"❌ Failed to fetch commits for *{bot.name}*:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
