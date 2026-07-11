from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class BotInfo:
    name: str
    key: str                  # canonical key used in commands
    zeabur_service_id: str    # from Zeabur dashboard > service > settings
    github_repo: str          # repo name under TheBooleanJulian
    description: str
    emoji: str
    health_url: str = ""      # Optional HTTP /health endpoint — if set, monitor pings it too


# ── Fill in your Zeabur service IDs from the dashboard ──────────────────────
BOTS: Dict[str, BotInfo] = {
    "miguquest": BotInfo(
        name="MiguQuest",
        key="miguquest",
        zeabur_service_id="FILL_MIGUQUEST_SERVICE_ID",
        github_repo="miguquest",
        description="Gamified task manager with Miku theme, XP system, Google Calendar integration",
        emoji="🎮",
    ),
    "mkmon": BotInfo(
        name="Miku Monday",
        key="mkmon",
        zeabur_service_id="FILL_MIKU_MONDAY_SERVICE_ID",
        github_repo="miku-monday-bot",
        description="Weekly automated Miku posts",
        emoji="🎵",
    ),
    "nac": BotInfo(
        name="NAC Busker",
        key="nac",
        zeabur_service_id="FILL_NAC_SERVICE_ID",
        github_repo="nac-busker-bot",
        description="NAC eServices schedule scraper for FattKew's busking slots",
        emoji="🎸",
    ),
    "apod": BotInfo(
        name="NASA APOD",
        key="apod",
        zeabur_service_id="FILL_APOD_SERVICE_ID",
        github_repo="nasa-apod-bot",
        description="Daily NASA Astronomy Picture of the Day with Pillow graphic cards",
        emoji="🚀",
    ),
}

# Aliases so commands are forgiving (e.g. /logs miku, /logs mkmon both work)
_ALIASES: Dict[str, str] = {
    "miguquest": "miguquest",
    "migu": "miguquest",
    "mg": "miguquest",
    "mkmon": "mkmon",
    "miku": "mkmon",
    "mikumonday": "mkmon",
    "miku-monday": "mkmon",
    "nac": "nac",
    "busker": "nac",
    "fattkew": "nac",
    "apod": "apod",
    "nasa": "apod",
}


def resolve_bot(raw: str) -> Optional[BotInfo]:
    """Case-insensitive, alias-aware lookup. Returns None if not found."""
    key = raw.lower().replace("-", "").replace("_", "").replace(" ", "")
    canonical = _ALIASES.get(key)
    return BOTS.get(canonical) if canonical else None


def all_bots() -> list[BotInfo]:
    return list(BOTS.values())


def bot_list_text() -> str:
    """Returns a formatted string listing all bots for help messages."""
    return "\n".join(
        f"  {b.emoji} `{b.key}` — {b.name}" for b in BOTS.values()
    )
