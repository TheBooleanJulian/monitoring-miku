"""
Error boundary middleware.

Wraps handlers so any unhandled exception:
  1. Gets logged with full traceback (DEBUG level)
  2. Sends a friendly error card to the user instead of silently failing
  3. Never leaks stack traces or internal details to Telegram

Usage:
    @error_boundary
    async def my_command(update, context): ...
"""

import logging
import traceback
import functools
from telegram import Update
from telegram.ext import ContextTypes, Application

log = logging.getLogger(__name__)

_FRIENDLY = (
    "⚠️ *Something went wrong.*\n"
    "_The error has been logged. If it persists, check `/logs` or restart the service._"
)


def error_boundary(handler):
    """Per-handler error catch. Use as a decorator on individual command handlers."""
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            return await handler(update, context)
        except Exception as exc:
            log.error(
                f"[error_boundary] Unhandled exception in {handler.__name__}: {exc}\n"
                + traceback.format_exc()
            )
            if update and update.message:
                try:
                    await update.message.reply_text(_FRIENDLY, parse_mode="Markdown")
                except Exception:
                    pass  # Don't let the error handler itself crash
    return wrapper


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    PTB's application-level error handler. Catches errors not caught by
    individual @error_boundary decorators (e.g. network-level errors).

    Register with: app.add_error_handler(global_error_handler)
    """
    log.error(
        f"[global_error_handler] Unhandled PTB error: {context.error}\n"
        + traceback.format_exc()
    )
    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text(_FRIENDLY, parse_mode="Markdown")
        except Exception:
            pass
