"""
Claude-powered bot debugger.

Sends recent logs + commit context to Claude and returns a structured diagnosis:
  Status / Root Cause / Evidence / Fix / Confidence
"""

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM_PROMPT = """\
You are an expert Python/Telegram bot debugger analysing production logs.

Respond in EXACTLY this format (no preamble, no trailing commentary):

**Status:** <one sentence — running fine / degraded / crashed>
**Root Cause:** <1–3 sentences identifying the error and its origin>
**Evidence:** <the specific log line(s) that confirm this — quote them verbatim>
**Fix:** <concrete minimal fix — exact code change, env var to set, or command to run>
**Confidence:** <High / Medium / Low>

If there are no errors in the logs, respond:
**Status:** All clear — no errors detected.
**Root Cause:** N/A
**Evidence:** N/A
**Fix:** N/A
**Confidence:** High

Never speculate beyond what the logs show. Be direct."""


async def debug_bot_logs(
    bot_name: str,
    description: str,
    log_lines: list[str],
    recent_commits: list[dict],
    latest_diff: str = "",
) -> str:
    """
    Runs Claude analysis on the given logs + context.
    Returns Claude's structured diagnosis as a string.
    """
    commits_text = "\n".join(
        f"  [{c['sha']}] {c['date']} — {c['message']} ({c['author']})"
        for c in recent_commits[:5]
    )

    diff_section = ""
    if latest_diff and latest_diff.strip() not in ("", "(no commits found)"):
        diff_section = f"\nLatest commit diff (for code context):\n```\n{latest_diff[:2000]}\n```"

    logs_text = "\n".join(log_lines[-150:])

    user_prompt = f"""\
Bot name: {bot_name}
Description: {description}

Recent commits:
{commits_text}
{diff_section}
Logs (chronological, most recent last):
```
{logs_text}
```

Analyse the logs above and produce your diagnosis."""

    # Use sync client inside async context — fine for single calls
    # For high-concurrency, swap to AsyncAnthropic
    message = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


async def quick_error_check(log_lines: list[str]) -> bool:
    """
    Fast heuristic: returns True if the logs contain likely error signals.
    Used by the health monitor before deciding to alert.
    """
    error_signals = [
        "traceback", "error", "exception", "critical",
        "fatal", "killed", "oom", "segfault",
    ]
    joined = "\n".join(log_lines[-50:]).lower()
    return any(sig in joined for sig in error_signals)
