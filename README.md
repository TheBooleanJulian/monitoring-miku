<div align="center">

# MonitoringMiku

**Fleet operations bot that monitors, debugs, and operates your Zeabur-hosted Telegram bots from a single chat interface.**

![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/-Telegram-26A5E4?logo=telegram&logoColor=white)
![SQLite](https://img.shields.io/badge/-SQLite-003B57?logo=sqlite&logoColor=white)
![Claude](https://img.shields.io/badge/-Claude%20API-D4A017)
![Zeabur](https://img.shields.io/badge/-Zeabur-6C5CE7)
![License](https://img.shields.io/badge/license-MIT-00D4C8.svg)

</div>

---

## What it does

MonitoringMiku is the ops layer for the TheBooleanJulian bot fleet. It watches four Zeabur-hosted services — **MiguQuest**, **Miku Monday**, **NAC Busker**, and **NASA APOD** — and surfaces their health, logs, and commit history directly in Telegram. When something breaks, it alerts you proactively and can invoke Claude AI to diagnose the failure from logs and recent commits. You can restart or redeploy any service without leaving the chat.

## Features

- `/status` — live Zeabur deployment health for all four bots at a glance
- `/logs <bot>` — tail recent log lines; auto-sends as `.txt` if over Telegram's message limit
- `/debug <bot>` — Claude AI root-cause analysis combining recent logs and commits
- `/commits <bot>` — latest GitHub commits for any monitored repo
- `/restart <bot>` / `/deploy <bot>` — hot-restart or full redeploy via Zeabur API
- `/incidents` — SQLite-persisted incident state that survives restarts
- Proactive alerts — DMs on downtime, re-alerts every 30 min if still down, notifies on recovery
- `/health` + `/status` HTTP endpoints for Zeabur uptime monitoring (aiohttp)
- Owner-only auth guard, per-command rate limiting, and per-handler error boundaries

## Tech Stack

| Layer | Choice |
|---|---|
| Bot | python-telegram-bot 21.9 (polling) |
| AI | Claude API (Anthropic) |
| Scheduling | APScheduler |
| Health server | aiohttp |
| External APIs | Zeabur GraphQL, GitHub REST |
| State | SQLite (incident persistence) |
| Hosting | Zeabur (GitHub CI/CD, feature → dev → main) |

## Quick Start

```bash
git clone https://github.com/TheBooleanJulian/monitoring-miku.git
cd monitoring-miku
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — see Configuration below
python main.py
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_OWNER_CHAT_ID` | ✅ | Your Telegram chat ID (from @userinfobot) |
| `TELEGRAM_OWNER_USER_ID` | ✅ | Your Telegram user ID (same as chat ID for DMs) |
| `ZEABUR_API_TOKEN` | ✅ | Zeabur dashboard → Account → Developer |
| `GITHUB_TOKEN` | ✅ | Fine-grained PAT with `Contents: read` on your repos |
| `ANTHROPIC_API_KEY` | ✅ | console.anthropic.com |

After setting env vars, open `bot_registry.py` and fill in the Zeabur service IDs for each monitored bot.

## Project Structure

```
monitoring-miku/
├── main.py                  # Entry point — async lifecycle, signal handling, middleware wiring
├── config.py                # Env vars + startup validation
├── logging_setup.py         # Rotating file handler + stdout stream
├── health_server.py         # aiohttp /health + /status endpoints
├── bot_registry.py          # Monitored bots list + alias resolution
├── middleware/
│   ├── auth.py              # Owner/community filters
│   ├── rate_limit.py        # Token-bucket rate limiting per command
│   └── error_boundary.py    # Per-handler + global error handling
├── handlers/
│   ├── help.py              # /start, /help
│   ├── status.py            # /status
│   ├── logs.py              # /logs <bot>
│   ├── debug.py             # /debug <bot>
│   ├── ops.py               # /restart, /deploy
│   ├── commits.py           # /commits <bot>
│   └── incidents.py         # /incidents
├── services/
│   ├── zeabur.py            # Zeabur GraphQL API client
│   ├── github.py            # GitHub REST API client
│   └── claude_debug.py      # Anthropic AI log analysis
├── monitor/
│   └── health_monitor.py    # APScheduler cron + SQLite incident state
├── requirements.txt
├── .env.example
└── zeabur.json
```

## Deployment

Deployed on Zeabur via GitHub CI/CD. Push to `main` triggers deploy. `zeabur.json` defines the service configuration. The bot runs in polling mode — no public IP or webhook required.

## Status / Roadmap

- [x] Health monitoring with proactive Telegram alerts
- [x] Claude AI log diagnosis (`/debug`)
- [x] Zeabur restart and redeploy via API
- [x] SQLite incident persistence across restarts
- [x] Owner-only auth + rate limiting + error boundaries
- [x] aiohttp health endpoints for Zeabur uptime checks
- [ ] Multi-owner / team access support
- [ ] Per-bot alert thresholds and snooze

## Changelog

- **Jul 2026** — Initial release: full fleet ops bot with health monitoring, Claude AI debugging, Zeabur restart/deploy, GitHub commit tailing, SQLite incident persistence, aiohttp health server, and production middleware (auth, rate limiting, error boundaries)

## License

MIT

---

<div align="center">
<sub>Built by <a href="https://github.com/TheBooleanJulian">@TheBooleanJulian</a></sub>
</div>