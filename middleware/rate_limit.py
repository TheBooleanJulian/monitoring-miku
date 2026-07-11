"""
Rate limiting middleware.

Uses a simple token-bucket per (user_id, command) pair.
Since MonitoringMiku is owner-only, this mainly guards against accidental
command flooding (e.g. spamming /debug during an incident).

Default: 3 calls per 10 seconds per command.
/debug is stricter (1 per 15s) due to Claude API cost.
"""

import time
import logging
import functools
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# { (user_id, command): [timestamp, ...] }
_call_log: dict[tuple, list[float]] = defaultdict(list)

# command → (max_calls, window_seconds)
_LIMITS: dict[str, tuple[int, int]] = {
    "debug":   (1, 15),   # 1 per 15s — Claude calls are expensive
    "restart": (2, 30),   # 2 per 30s — prevent restart loops
    "deploy":  (1, 60),   # 1 per 60s — prevent deploy thrashing
    "_default": (3, 10),  # everything else: 3 per 10s
}


def rate_limit(command: str | None = None):
    """
    Decorator factory. Usage:

        @rate_limit("debug")
        async def debug_command(update, context): ...

        @rate_limit()   # uses _default limits
        async def status_command(update, context): ...
    """
    def decorator(handler):
        cmd = command or "_default"
        max_calls, window = _LIMITS.get(cmd, _LIMITS["_default"])

        @functools.wraps(handler)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id if update.effective_user else 0
            key = (user_id, cmd)
            now = time.monotonic()

            # Evict timestamps outside the window
            _call_log[key] = [t for t in _call_log[key] if now - t < window]

            if len(_call_log[key]) >= max_calls:
                oldest = _call_log[key][0]
                wait = int(window - (now - oldest)) + 1
                log.info(f"[rate_limit] user={user_id} cmd={cmd} throttled, retry in {wait}s")
                await update.message.reply_text(
                    f"⏳ Slow down — retry `/{cmd}` in {wait}s.",
                    parse_mode="Markdown",
                )
                return

            _call_log[key].append(now)
            return await handler(update, context)

        return wrapper
    return decorator
