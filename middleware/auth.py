"""
Auth middleware — two-tier access model.

COMMUNITY commands (/status, /logs, /commits, /incidents, /help)
  → community_filter: passes for any user in an allowed chat
  → Curated channels and groups can use these freely

OWNER-ONLY commands (/debug, /restart, /deploy)
  → owner_filter: passes only if sender's user ID matches TELEGRAM_OWNER_USER_ID
  → Works across DMs, groups, and channels — identity check, not chat check

Allowed chats are configured via TELEGRAM_ALLOWED_CHAT_IDS (comma-separated
chat IDs). The owner's private chat is always included automatically.

Adding a group/channel to the allowed list:
  1. Add MonitoringMiku as an admin in that chat
  2. Get the chat ID (forward a message to @userinfobot, or use /getid bots)
  3. Add it to TELEGRAM_ALLOWED_CHAT_IDS in your .env and redeploy
"""

import logging
import functools
from telegram import Update
from telegram.ext import ContextTypes, filters as tg_filters

import config

log = logging.getLogger(__name__)


# ── Community filter ──────────────────────────────────────────────────────────

class _CommunityFilter(tg_filters.BaseFilter):
    """
    Passes for any message originating from an allowed chat.
    Covers: owner's DMs, curated group chats, and channel posts.

    Re-reads config.TELEGRAM_ALLOWED_CHAT_IDS at call time so the set
    can be updated without restarting the process in tests.
    """
    def filter(self, message) -> bool:
        chat_id = message.chat_id
        allowed = chat_id in config.TELEGRAM_ALLOWED_CHAT_IDS
        if not allowed:
            user = message.from_user
            uid = user.id if user else "unknown"
            uname = f"@{user.username}" if user and user.username else ""
            log.info(
                f"[auth] Ignored community command from unlisted "
                f"chat_id={chat_id} (user {uid} {uname})"
            )
        return allowed


# ── Owner filter ──────────────────────────────────────────────────────────────

class _OwnerFilter(tg_filters.BaseFilter):
    """
    Passes only if the sender's user ID matches TELEGRAM_OWNER_USER_ID.
    Used for dev/ops commands: /debug, /restart, /deploy.
    Chat type is irrelevant — this is an identity check, not a chat check.
    """
    def filter(self, message) -> bool:
        user = message.from_user
        if user is None:
            return False
        allowed = user.id == config.TELEGRAM_OWNER_USER_ID
        if not allowed:
            log.warning(
                f"[auth] Dev command blocked — user_id={user.id} "
                f"(@{user.username}) in chat_id={message.chat_id}"
            )
        return allowed


community_filter = _CommunityFilter()
owner_filter = _OwnerFilter()


# ── Decorator — belt-and-suspenders for owner commands ───────────────────────

def owner_only(handler):
    """
    Runtime guard for dev/ops handlers. Silently drops non-owner callers.
    Use alongside owner_filter at CommandHandler registration.
    """
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None or user.id != config.TELEGRAM_OWNER_USER_ID:
            log.warning(
                f"[auth] @owner_only blocked user_id={getattr(user, 'id', 'unknown')}"
            )
            return
        return await handler(update, context)
    return wrapper
