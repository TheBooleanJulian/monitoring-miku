import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _int_env(var: str, default: str) -> int:
    """int(os.getenv(...)) but exits with a clear message instead of a raw
    traceback when the env var is set to a non-numeric value (e.g. a
    misconfigured Zeabur variable left as its own key name)."""
    raw = os.getenv(var, default)
    try:
        return int(raw)
    except ValueError:
        print(f"[config] {var} must be an integer, got {raw!r} — check your env vars", file=sys.stderr)
        sys.exit(1)


# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_CHAT_ID: int = _int_env("TELEGRAM_OWNER_CHAT_ID", "0")
# User ID for dev/ops command auth guard — same number as TELEGRAM_OWNER_CHAT_ID
TELEGRAM_OWNER_USER_ID: int = _int_env("TELEGRAM_OWNER_USER_ID", str(TELEGRAM_OWNER_CHAT_ID))

# Comma-separated list of chat IDs where community commands (/status, /logs etc.)
# are publicly accessible. Add your group/channel IDs here.
# Example: TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890,-1009876543210
# Owner's private chat is always included automatically.
_raw_allowed = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
TELEGRAM_ALLOWED_CHAT_IDS: set[int] = {
    int(cid.strip())
    for cid in _raw_allowed.split(",")
    if cid.strip().lstrip("-").isdigit()
} | ({TELEGRAM_OWNER_CHAT_ID} if TELEGRAM_OWNER_CHAT_ID else set())

# ── Health server ─────────────────────────────────────────────────────────────
# Zeabur injects PORT; fall back to HEALTH_SERVER_PORT, then 8080
HEALTH_SERVER_PORT: int = _int_env("PORT", os.getenv("HEALTH_SERVER_PORT", "8080"))

# ── Zeabur ───────────────────────────────────────────────────────────────────
# Personal API token from https://zeabur.com/account/developer
ZEABUR_API_TOKEN: str = os.getenv("ZEABUR_API_TOKEN", "")
ZEABUR_GRAPHQL_URL: str = "https://gateway.zeabur.com/graphql"

# Comma-separated Zeabur project IDs to scan for bot auto-discovery.
# Every service found in these projects is treated as a monitored bot
# UNLESS its service ID is listed in ZEABUR_EXCLUDED_SERVICE_IDS below.
_raw_project_ids = os.getenv("ZEABUR_PROJECT_IDS", "")
ZEABUR_PROJECT_IDS: list[str] = [p.strip() for p in _raw_project_ids.split(",") if p.strip()]

# Comma-separated Zeabur service IDs to exclude from auto-discovery
# (databases, monitoring-miku itself, repo-tracker, or any other non-bot service
# sharing a tracked project). This list should stay short — new bots need no entry.
_raw_excluded_ids = os.getenv("ZEABUR_EXCLUDED_SERVICE_IDS", "")
ZEABUR_EXCLUDED_SERVICE_IDS: set[str] = {s.strip() for s in _raw_excluded_ids.split(",") if s.strip()}

# ── GitHub ───────────────────────────────────────────────────────────────────
# Fine-grained personal token with read access to your repos
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "TheBooleanJulian")

# ── Anthropic ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

# ── Monitoring ───────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL_SECONDS: int = _int_env("HEALTH_CHECK_INTERVAL", "300")  # 5 min
ALERT_REPEAT_MINUTES: int = _int_env("ALERT_REPEAT_MINUTES", "30")  # re-alert if still down after 30 min
LOG_LINES_DEFAULT: int = _int_env("LOG_LINES_DEFAULT", "100")
LOG_LINES_MAX: int = 300

# How often to re-run bot auto-discovery against Zeabur + GitHub. Default: 30 min
REGISTRY_REFRESH_INTERVAL_SECONDS: int = _int_env("REGISTRY_REFRESH_INTERVAL", "1800")


def validate() -> list[str]:
    """Returns a list of missing required env vars."""
    missing = []
    for var, val in [
        ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
        ("TELEGRAM_OWNER_CHAT_ID", str(TELEGRAM_OWNER_CHAT_ID)),
        ("TELEGRAM_OWNER_USER_ID", str(TELEGRAM_OWNER_USER_ID)),
        ("ZEABUR_API_TOKEN", ZEABUR_API_TOKEN),
        ("GITHUB_TOKEN", GITHUB_TOKEN),
        ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
    ]:
        if not val or val == "0":
            missing.append(var)
    return missing
