# 🎐 MonitoringMiku

> Fleet operations bot for the TheBooleanJulian Telegram bot ecosystem.

MonitoringMiku watches over your four Zeabur-hosted bots — **MiguQuest**, **Miku Monday**, **NAC Busker**, and **NASA APOD** — from a single Telegram interface. It polls health, tails logs, triggers restarts and redeploys, and uses Claude AI to diagnose failures automatically.

---

## Features

| Feature | Description |
|---|---|
| `/status` | Live health of all 4 bots — Zeabur deployment status at a glance |
| `/logs <bot>` | Tail the last N log lines; sends as `.txt` if over Telegram's message limit |
| `/debug <bot>` | 🤖 Claude AI analysis — fetches logs + recent commits, returns a structured root-cause diagnosis |
| `/commits <bot>` | Last N GitHub commits for any bot's repo |
| `/restart <bot>` | Hot-restarts a Zeabur service without a new deployment |
| `/deploy <bot>` | Triggers a full redeploy from the latest Git commit |
| `/incidents` | Shows current incident state from the SQLite DB — survives restarts |
| Proactive alerts | DMs you when any bot goes down; re-alerts every 30 min if still down; sends recovery notice |
| `/health` HTTP | `GET /health` and `GET /status` endpoints for Zeabur uptime monitoring |

---

## Production Architecture

```
monitoringmiku/
├── main.py                    # Entry point — async lifecycle, signal handling, middleware wiring
├── config.py                  # All env vars, startup validation
├── logging_setup.py           # Rotating file handler + stdout stream
├── health_server.py           # aiohttp /health + /status HTTP endpoints
├── bot_registry.py            # Canonical list of monitored bots + alias resolution
│
├── middleware/
│   ├── auth.py                # Owner-only filter (works in DMs, groups, channels)
│   ├── rate_limit.py          # Token-bucket rate limiting per command
│   └── error_boundary.py      # Per-handler + global PTB error handling
│
├── handlers/
│   ├── help.py                # /start, /help
│   ├── status.py              # /status
│   ├── logs.py                # /logs <bot> [--n=N]
│   ├── debug.py               # /debug <bot>
│   ├── ops.py                 # /restart, /deploy
│   ├── commits.py             # /commits <bot>
│   ├── incidents.py           # /incidents
│   └── utils.py               # send_or_file, parse_bot_arg
│
├── services/
│   ├── zeabur.py              # Zeabur GraphQL API client
│   ├── github.py              # GitHub REST API client
│   └── claude_debug.py        # Anthropic API — AI log analysis
│
├── monitor/
│   └── health_monitor.py      # APScheduler cron, SQLite incident state
│
├── logs/                      # Auto-created — rotating log files (gitignored)
├── monitor_state.db           # Auto-created — SQLite incident persistence (gitignored)
│
├── requirements.txt
├── .env.example
├── .gitignore
└── zeabur.json
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/TheBooleanJulian/monitoringmiku.git
cd monitoringmiku
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create your bot

1. Open Telegram → search `@BotFather` → `/newbot`
2. Follow the prompts — name it `MonitoringMiku`, username `MonitoringMikuBot` (or similar)
3. Copy the API token

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` — all required fields:

| Variable | Where to get it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather → `/newbot` |
| `TELEGRAM_OWNER_CHAT_ID` | Message @userinfobot — it replies with your chat ID |
| `TELEGRAM_OWNER_USER_ID` | Same value as `TELEGRAM_OWNER_CHAT_ID` (your user ID) |
| `ZEABUR_API_TOKEN` | Zeabur dashboard → Account → Developer → Generate token |
| `GITHUB_TOKEN` | github.com/settings/tokens?type=beta → fine-grained PAT, `Contents: read` on your repos |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

### 4. Fill in your Zeabur service IDs

Open `bot_registry.py` and replace the four `FILL_*` placeholders with your actual service IDs.

Find them at: **Zeabur dashboard → [service] → Settings → Service ID**

```python
BOTS = {
    "miguquest": BotInfo(
        zeabur_service_id="abc123...",   # ← paste here
        github_repo="miguquest",
        health_url="https://miguquest.zeabur.app/health",  # optional
        ...
    ),
    ...
}
```

The `health_url` field is optional but recommended — if your bot exposes a `/health` endpoint, MonitoringMiku will ping it on every health check cycle in addition to the Zeabur API, catching cases where the process is running but internally deadlocked.

### 5. Run locally

```bash
python main.py
```

On startup you'll see:

```
[INFO] Logging initialised — file: logs/monitoringmiku.log
[INFO] [zeabur] Token valid — authenticated as TheBooleanJulian
[INFO] [health] State DB ready at monitor_state.db
[INFO] [health_server] Listening on 0.0.0.0:8080 — /health · /status
[INFO] [main] MonitoringMiku is live 🎐
```

Open Telegram and send `/status` to your new bot.

---

## Deploying to Zeabur

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "feat: MonitoringMiku initial deploy"
git remote add origin https://github.com/TheBooleanJulian/monitoringmiku.git
git push -u origin main
```

### 2. Import to Zeabur

1. Zeabur dashboard → New Project → Deploy from GitHub
2. Select the `monitoringmiku` repo
3. Zeabur auto-detects Python and uses `zeabur.json`

### 3. Set environment variables

In the Zeabur service settings → Environment Variables, add all variables from `.env.example`.

> **Note:** Zeabur injects `PORT` automatically — your `/health` endpoint will bind to it. Do not set `PORT` manually.

### 4. Expose the health port

Zeabur dashboard → [MonitoringMiku service] → Networking → expose port `8080` (or whatever `PORT` Zeabur assigns). This enables the health endpoint to be externally reachable for uptime monitoring.

## Access model

MonitoringMiku uses a **two-tier auth model**:

| Tier | Filter | Commands | Who can use |
|---|---|---|---|
| Community | `community_filter` | `/status` `/logs` `/commits` `/incidents` `/help` | Anyone in an allowed chat |
| Owner only | `owner_filter` | `/debug` `/restart` `/deploy` | Julian only (by user ID) |

**Community commands** are safe for your curated Telegram channels and group chats — read-only, informational, no API cost.

**Owner commands** are gated on `TELEGRAM_OWNER_USER_ID` regardless of chat type — Julian can run them from anywhere (DM, group, channel); everyone else is silently ignored.

### Adding a group or channel

1. Add MonitoringMiku as an admin in the chat
2. Get the chat ID — forward any message from the chat to `@userinfobot`
3. Add the ID to `TELEGRAM_ALLOWED_CHAT_IDS` in your `.env` (comma-separated, negative for groups/channels):
   ```
   TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890,-1009876543210
   ```
4. Redeploy — the new chat is live immediately

---

## Commands reference

**Community** (anyone in allowed chats) · **Owner** (Julian only, anywhere)

```
/status              — [community] All bots: status + last deploy time
/logs <bot>          — [community] Last 100 log lines (add --n=200 for more)
/commits <bot>       — [community] Last 5 GitHub commits (add --n=10 for more)
/incidents           — [community] Current incident state from DB
/help                — [community] This list

/debug <bot>         — [owner] Claude AI root-cause analysis
/restart <bot>       — [owner] Hot-restart (no new deployment)
/deploy <bot>        — [owner] Full redeploy from latest commit
```

**Bot targets** (all aliases work):

| Key | Aliases | Bot |
|---|---|---|
| `miguquest` | `migu`, `mg` | MiguQuest task manager |
| `mkmon` | `miku`, `mikumonday` | Miku Monday |
| `nac` | `busker`, `fattkew` | NAC Busker schedule |
| `apod` | `nasa` | NASA APOD card bot |

---

## Production readiness checklist

- [x] **Logging** — rotating file handler (`logs/`) + stdout, noisy libs silenced
- [x] **Timeouts** — all `httpx` calls have explicit timeouts (8–20s by API importance)
- [x] **Auth guards** — two-tier: `community_filter` (allowed chat IDs) for public commands; `owner_filter` (user ID) for dev/ops; `@owner_only` decorator as belt-and-suspenders
- [x] **Error boundaries** — `@error_boundary` on every handler + global PTB `add_error_handler`
- [x] **No exposed secrets** — `.gitignore` covers `.env`, `*.db`, `logs/`; `.env.example` has no real values
- [x] **Rate limiting** — token-bucket per (user, command); `/debug` 1/15s, `/restart` 2/30s, `/deploy` 1/60s
- [x] **Error handling** — all service calls wrapped in try/except; friendly Telegram error cards
- [x] **Graceful shutdown** — `SIGINT`/`SIGTERM` handlers; polling, scheduler, and HTTP server all torn down cleanly
- [x] **Database** — SQLite incident persistence; survives restarts without duplicate alerts
- [x] **Polling** — `run_polling()` (no webhook, no public IP needed)
- [x] **Health endpoints** — `GET /health` and `GET /status` on `:8080` for Zeabur uptime checks
- [x] **Group/channel support** — commands work anywhere Julian is present and the bot is an admin
- [x] **Project structure** — handlers / services / middleware / monitor packages, no circular imports

---

## Adding a new bot to the fleet

1. Add a `BotInfo` entry to `bot_registry.py`
2. Add any desired aliases to `_ALIASES`
3. No other changes needed — all handlers resolve bots dynamically via `resolve_bot()`

---

## Health endpoint for monitored bots

To unlock the HTTP health ping feature, add a `/health` route to each bot:

```python
# Minimal aiohttp health endpoint — add to any bot
from aiohttp import web

async def health(request):
    return web.json_response({"status": "ok"})

app = web.Application()
app.router.add_get("/health", health)
```

Then set `health_url` in `bot_registry.py`:

```python
health_url="https://your-bot.zeabur.app/health"
```

MonitoringMiku will ping it on every health check cycle, catching internal deadlocks even when Zeabur reports the process as `RUNNING`.

---

## License

Personal project — TheBooleanJulian © 2025
