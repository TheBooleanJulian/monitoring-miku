"""GitHub REST API client (v3)."""

import httpx
from config import GITHUB_TOKEN, GITHUB_OWNER

_API = "https://api.github.com"
_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


async def get_recent_commits(repo: str, count: int = 5) -> list[dict]:
    """
    Returns the last `count` commits as simplified dicts:
      { sha, message, author, date, url }
    """
    url = f"{_API}/repos/{GITHUB_OWNER}/{repo}/commits"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=_HEADERS, params={"per_page": count})
        resp.raise_for_status()
        raw = resp.json()

    return [
        {
            "sha": c["sha"][:7],
            "message": c["commit"]["message"].split("\n")[0][:80],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"][:10],
            "url": c["html_url"],
        }
        for c in raw
    ]


async def get_latest_diff(repo: str, max_chars: int = 3000) -> str:
    """
    Returns the unified diff of the latest commit, truncated to max_chars.
    Used as extra context for Claude's debug analysis.
    """
    url = f"{_API}/repos/{GITHUB_OWNER}/{repo}/commits"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=_HEADERS, params={"per_page": 1})
        resp.raise_for_status()
        commits = resp.json()
        if not commits:
            return "(no commits found)"

        sha = commits[0]["sha"]
        diff_headers = {**_HEADERS, "Accept": "application/vnd.github.v3.diff"}
        diff_resp = await client.get(
            f"{_API}/repos/{GITHUB_OWNER}/{repo}/commits/{sha}",
            headers=diff_headers,
        )
        diff_resp.raise_for_status()

    diff = diff_resp.text
    if len(diff) > max_chars:
        diff = diff[:max_chars] + "\n\n... (diff truncated)"
    return diff


async def trigger_workflow(repo: str, workflow_filename: str, ref: str = "main") -> bool:
    """
    Triggers a GitHub Actions workflow_dispatch event.
    workflow_filename: e.g. "deploy.yml"
    Requires the workflow to have `on: workflow_dispatch` enabled.
    """
    url = f"{_API}/repos/{GITHUB_OWNER}/{repo}/actions/workflows/{workflow_filename}/dispatches"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            headers=_HEADERS,
            json={"ref": ref},
        )
        resp.raise_for_status()
    return True


def format_commits(commits: list[dict]) -> str:
    """Formats commit list for Telegram (Markdown)."""
    lines = []
    for c in commits:
        lines.append(f"`{c['sha']}` {c['date']} — {c['message']}")
    return "\n".join(lines)
