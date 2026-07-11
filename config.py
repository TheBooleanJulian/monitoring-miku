import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_CHAT_ID: int = int(os.getenv("TELEGRAM_OWNER_CHAT_ID", "0"))
# User ID for dev/ops command auth guard — same number as TELEGRAM_OWNER_CHAT_ID
TELEGRAM_OWNER_USER_ID: int = int(os.getenv("TELEGRAM_OWNER_USER_ID", os.getenv("TELEGRAM_OWNER_CHAT_ID", "0")))

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
HEALTH_SERVER_PORT: int = int(os.getenv("PORT", os.getenv("HEALTH_SERVER_PORT", "8080")))

# ── Zeabur ───────────────────────────────────────────────────────────────────
# Personal API token from https://zeabur.com/account/developer
ZEABUR_API_TOKEN: str = os.getenv("ZEABUR_API_TOKEN", "")
ZEABUR_GRAPHQL_URL: str = "https://gateway.zeabur.com/graphql"

# ── GitHub ───────────────────────────────────────────────────────────────────
# Fine-grained personal token with read access to your repos
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "TheBooleanJulian")

# ── Anthropic ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

# ── Monitoring ───────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL_SECONDS: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "300"))  # 5 min
ALERT_REPEAT_MINUTES: int = int(os.getenv("ALERT_REPEAT_MINUTES", "30"))  # re-alert if still down after 30 min
LOG_LINES_DEFAULT: int = int(os.getenv("LOG_LINES_DEFAULT", "100"))
LOG_LINES_MAX: int = 300


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
