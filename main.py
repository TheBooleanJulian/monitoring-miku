"""
MonitoringMiku — Production-ready fleet ops bot for TheBooleanJulian.

Monitors MiguQuest, Miku Monday, NAC Busker, and NASA APOD on Zeabur.
Provides health checks, log tailing, and Claude-powered AI debugging.

Production features:
  - Rotating file + stream logging
  - Owner-only auth guard (works in DMs, groups, and channels)
  - Per-command rate limiting
  - Per-handler error boundaries + global PTB error handler
  - API token validation at startup
  - SQLite-persisted incident state
  - aiohttp /health + /status endpoints for Zeabur uptime monitoring
  - Graceful shutdown via SIGINT / SIGTERM
  - Polling (no webhook, no public IP required)
"""

import asyncio
import logging
import signal
import sys
from urllib.parse import urlparse

from telegram import BotCommand
from telegram.ext import Application, CommandHandler

import config
import bot_registry
from logging_setup import setup_logging
from middleware.auth import community_filter, owner_filter
from middleware.error_boundary import global_error_handler, error_boundary
from middleware.rate_limit import rate_limit
from health_server import start_health_server

from handlers.help import start_command, help_command
from handlers.status import status_command
from handlers.logs import logs_command
from handlers.debug import debug_command
from handlers.ops import restart_command, deploy_command, refresh_registry_command
from handlers.commits import commits_command
from handlers.incidents import incidents_command
from monitor.health_monitor import start_health_monitor
from services.zeabur import validate_token as validate_zeabur_token
from services.tls_diag import diagnose_tls

setup_logging()
log = logging.getLogger(__name__)


# ── Command tables ────────────────────────────────────────────────────────────
#
# COMMUNITY — any user in an allowed chat (TELEGRAM_ALLOWED_CHAT_IDS)
#   Informational, read-only, safe for your groups and channels.
#
# OWNER ONLY — sender must be TELEGRAM_OWNER_USER_ID
#   Dev/ops commands; destructive or expensive (Claude API).
#
# Each entry: (name, handler_fn, rate_limit_key | None)
# All handlers get @error_boundary automatically in build_app().

_COMMUNITY_COMMANDS = [
    ("start",     start_command,     None),
    ("help",      help_command,      None),
    ("status",    status_command,    None),
    ("logs",      logs_command,      None),
    ("commits",   commits_command,   None),
    ("incidents", incidents_command, None),
]

_OWNER_COMMANDS = [
    ("debug",            debug_command,            "debug"),    # Claude API — rate limited 1/15s
    ("restart",          restart_command,           "restart"),  # Zeabur restart — rate limited 2/30s
    ("deploy",           deploy_command,            "deploy"),   # Zeabur redeploy — rate limited 1/60s
    ("refresh_registry", refresh_registry_command,  "refresh_registry"),  # re-run bot auto-discovery now
]


async def _set_commands(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("status",    "Health of all bots at a glance"),
        BotCommand("logs",      "Tail recent logs — /logs <bot>"),
        BotCommand("debug",     "AI diagnosis — /debug <bot>"),
        BotCommand("commits",   "Recent commits — /commits <bot>"),
        BotCommand("restart",   "Hot-restart a service — /restart <bot>"),
        BotCommand("deploy",    "Full redeploy — /deploy <bot>"),
        BotCommand("incidents", "Show tracked incident state"),
        BotCommand("refresh_registry", "Re-run bot auto-discovery now"),
        BotCommand("help",      "Show all commands"),
    ])
    log.info("[main] Bot command menu registered")


def build_app() -> Application:
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_set_commands)
        .build()
    )

    app.add_error_handler(global_error_handler)

    def _register(commands, auth):
        for name, handler_fn, rl_key in commands:
            fn = error_boundary(handler_fn)
            if rl_key:
                fn = rate_limit(rl_key)(fn)
            app.add_handler(CommandHandler(name, fn, filters=auth))

    _register(_COMMUNITY_COMMANDS, community_filter)
    _register(_OWNER_COMMANDS, owner_filter)

    log.info(
        f"[main] {len(_COMMUNITY_COMMANDS)} community commands, "
        f"{len(_OWNER_COMMANDS)} owner-only commands registered"
    )
    return app


async def _startup_checks() -> None:
    """Validates external API tokens before the bot goes live. Non-fatal."""
    log.info("[main] Running startup API validation...")
    try:
        await validate_zeabur_token()
    except RuntimeError as e:
        log.warning(f"[main] Zeabur validation: {e} — Zeabur calls will error at runtime")
        if "ssl" in str(e).lower() or "certificate" in str(e).lower():
            host = urlparse(config.ZEABUR_GRAPHQL_URL).hostname
            if host:
                await asyncio.get_running_loop().run_in_executor(None, diagnose_tls, host)
    log.info("[main] Startup checks done")


async def _load_bot_registry() -> None:
    """Loads the cached fleet immediately, then refreshes from Zeabur/GitHub.
    Refresh failures are non-fatal — the bot keeps serving the cached registry."""
    bot_registry.load_cached_registry()
    try:
        count = await bot_registry.refresh_registry()
        log.info(f"[main] Bot registry discovered {count} bot(s)")
    except Exception as e:
        log.warning(f"[main] Bot registry refresh failed, using cached data: {e}")


async def _run() -> None:
    """
    Main async coroutine. Runs Telegram polling, health HTTP server,
    and background scheduler concurrently. Shuts down cleanly on signal.
    """
    missing = config.validate()
    if missing:
        log.error(f"[main] Missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    await _startup_checks()
    await _load_bot_registry()

    app = build_app()
    scheduler = start_health_monitor(app)
    scheduler.add_job(
        bot_registry.refresh_registry,
        trigger="interval",
        seconds=config.REGISTRY_REFRESH_INTERVAL_SECONDS,
        id="registry_refresh",
        name="Bot registry auto-discovery",
        misfire_grace_time=60,
    )
    health_runner = await start_health_server()

    # ── Signal handling ───────────────────────────────────────────────────────
    stop_event = asyncio.Event()

    def _on_signal(sig: signal.Signals) -> None:
        log.info(f"[main] {sig.name} received — shutting down gracefully")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal, sig)
        except (NotImplementedError, OSError):
            signal.signal(sig, lambda s, f: stop_event.set())

    # ── Start polling ─────────────────────────────────────────────────────────
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("[main] MonitoringMiku is live 🎐")

    await stop_event.wait()

    # ── Teardown ──────────────────────────────────────────────────────────────
    log.info("[main] Stopping services...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    scheduler.shutdown(wait=False)
    await health_runner.cleanup()
    log.info("[main] Clean shutdown complete.")


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("[main] Interrupted")


if __name__ == "__main__":
    main()
