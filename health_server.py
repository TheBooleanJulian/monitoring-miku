"""
Health HTTP server.

Exposes two endpoints so Zeabur (or UptimeRobot / BetterStack) can monitor
MonitoringMiku itself — the watcher needs watching too.

  GET /health  → 200 { "status": "ok", "uptime_seconds": N }
  GET /status  → 200 { "bots": [ { "key", "name", "status", "down_since" } ] }
  GET /        → public landing page — fleet status + a link to /admin

Also mounts the admin discovery-config UI (see admin_ui.py):
  GET  /admin                     → HTML page for picking Zeabur projects/services
  POST /admin/login               → sign in with ADMIN_TOKEN, sets session cookie
  GET  /admin/logout              → clears the session cookie
  GET  /admin/api/projects        → list Zeabur projects
  GET  /admin/api/services        → list services in selected projects
  GET  /admin/api/config          → current discovery config
  POST /admin/api/config          → save config + refresh bot registry

Port is controlled by HEALTH_SERVER_PORT env var (default 8080).
Zeabur expects the app to bind on the PORT env var — set HEALTH_SERVER_PORT=8080
and expose port 8080 in your Zeabur service settings.
"""

import asyncio
import json
import logging
import time
from aiohttp import web

from config import HEALTH_SERVER_PORT
from bot_registry import all_bots
from monitor.health_monitor import _get_state
from admin_ui import add_admin_routes
from landing import landing_page

log = logging.getLogger(__name__)
_start_time = time.time()


async def _health(request: web.Request) -> web.Response:
    payload = {
        "status": "ok",
        "service": "MonitoringMiku",
        "uptime_seconds": int(time.time() - _start_time),
    }
    return web.Response(
        text=json.dumps(payload),
        content_type="application/json",
        status=200,
    )


async def _status(request: web.Request) -> web.Response:
    bots = []
    for bot in all_bots():
        state = _get_state(bot.key)
        down_since = state.get("down_since")
        bots.append({
            "key": bot.key,
            "name": bot.name,
            "status": state.get("last_status") or "UNKNOWN",
            "down_since": down_since.isoformat() if down_since else None,
        })

    payload = {
        "service": "MonitoringMiku",
        "uptime_seconds": int(time.time() - _start_time),
        "bots": bots,
    }
    return web.Response(
        text=json.dumps(payload, default=str),
        content_type="application/json",
        status=200,
    )


def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", landing_page)
    app.router.add_get("/health", _health)
    app.router.add_get("/status", _status)
    add_admin_routes(app)
    return app


async def start_health_server() -> web.AppRunner:
    """
    Starts the aiohttp server as an asyncio task alongside the Telegram bot.
    Returns the runner so it can be cleanly stopped on shutdown.
    """
    app = _build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=HEALTH_SERVER_PORT)
    await site.start()
    log.info(f"[health_server] Listening on 0.0.0.0:{HEALTH_SERVER_PORT} — /health · /status")
    return runner
