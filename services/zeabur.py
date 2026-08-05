"""
Zeabur GraphQL API client.

Zeabur API docs: https://zeabur.com/docs/developer/api
GraphQL playground: https://gateway.zeabur.com/graphql

NOTE: Zeabur's public GraphQL schema evolves. If a query fails, open the
playground with your API token and introspect the schema to confirm field names.
Your service IDs are in Zeabur dashboard → service → Settings → Service ID.
"""

import asyncio
import logging
import httpx
from config import ZEABUR_API_TOKEN, ZEABUR_GRAPHQL_URL

_HEADERS = {
    "Authorization": f"Bearer {ZEABUR_API_TOKEN}",
    "Content-Type": "application/json",
}

# Zeabur deployment status values
RUNNING = "RUNNING"
STOPPED = "STOPPED"
SLEEPING = "SLEEPING"
DEPLOYING = "DEPLOYING"
FAILED = "FAILED"
REMOVED = "REMOVED"


async def validate_token() -> None:
    """
    Lightweight startup check — verifies the Zeabur token is accepted.
    Raises RuntimeError if the token is invalid or the API is unreachable.
    Run this once at startup via main.py before the bot goes live.
    """
    query = "query { user { username } }"
    try:
        data = await _gql(query, {})
        username = data.get("user", {}).get("username", "(unknown)")
        logging.getLogger(__name__).info(f"[zeabur] Token valid — authenticated as {username}")
    except Exception as exc:
        raise RuntimeError(f"Zeabur token validation failed: {exc}") from exc


async def _gql(query: str, variables: dict) -> dict:
    """Execute a GraphQL operation and return data dict. Raises on errors."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            ZEABUR_GRAPHQL_URL,
            headers=_HEADERS,
            json={"query": query, "variables": variables},
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            messages = "; ".join(e.get("message", str(e)) for e in payload["errors"])
            raise RuntimeError(f"Zeabur API: {messages}")
        return payload["data"]


async def get_service_status(service_id: str) -> dict:
    """
    Returns service dict with structure:
      { id, name, latestDeployment: { id, status, createdAt } }
    
    'status' will be one of: RUNNING STOPPED SLEEPING DEPLOYING FAILED REMOVED
    """
    query = """
    query GetService($serviceID: String!) {
      service(id: $serviceID) {
        id
        name
        latestDeployment {
          id
          status
          createdAt
        }
      }
    }
    """
    data = await _gql(query, {"serviceID": service_id})
    return data["service"]


async def get_service_logs(service_id: str, deployment_id: str, lines: int = 100) -> list[dict]:
    """
    Returns list of log entries: [{ timestamp, message }, ...]
    
    NOTE: If Zeabur exposes logs via a REST endpoint rather than GraphQL,
    replace this with a GET to:
      https://api.zeabur.com/api/v1/services/{serviceID}/deployments/{deploymentID}/logs
    and set header Authorization: Bearer {ZEABUR_API_TOKEN}
    """
    query = """
    query GetDeploymentLogs($serviceID: String!, $deploymentID: String!, $lines: Int) {
      deploymentLogs(
        serviceID: $serviceID
        deploymentID: $deploymentID
        lines: $lines
      ) {
        timestamp
        message
      }
    }
    """
    data = await _gql(query, {
        "serviceID": service_id,
        "deploymentID": deployment_id,
        "lines": lines,
    })
    return data.get("deploymentLogs", [])


async def restart_service(service_id: str) -> bool:
    """Hot-restart the service process without a new deployment."""
    mutation = """
    mutation RestartService($serviceID: String!) {
      restartService(serviceID: $serviceID)
    }
    """
    await _gql(mutation, {"serviceID": service_id})
    return True


async def redeploy_service(service_id: str) -> bool:
    """Trigger a full redeploy from the latest Git commit."""
    mutation = """
    mutation RedeployService($serviceID: String!) {
      redeployService(serviceID: $serviceID)
    }
    """
    await _gql(mutation, {"serviceID": service_id})
    return True


async def list_projects() -> list[dict]:
    """
    Returns every project visible to this API token as [{ id, name }, ...].
    Used by the /admin page to let the owner pick which projects to scan for
    bot auto-discovery, instead of hand-copying project IDs into an env var.
    """
    query = """
    query GetProjects {
      projects {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    data = await _gql(query, {})
    edges = (data.get("projects") or {}).get("edges") or []
    return [edge["node"] for edge in edges if edge.get("node")]


async def list_project_services(project_id: str) -> list[dict]:
    """
    Returns every service in a Zeabur project as [{ id, name }, ...].
    Used by bot_registry's auto-discovery — one call per tracked project.
    """
    query = """
    query GetProjectServices($projectID: String!) {
      project(id: $projectID) {
        services {
          edges {
            node {
              id
              name
            }
          }
        }
      }
    }
    """
    data = await _gql(query, {"projectID": project_id})
    project = data.get("project") or {}
    edges = (project.get("services") or {}).get("edges") or []
    return [edge["node"] for edge in edges if edge.get("node")]


async def list_all_services(project_ids: list[str]) -> list[dict]:
    """
    Fans out list_project_services across every configured project ID and
    flattens the results, tagging each service with its project_id.
    A single project failing to fetch (bad ID, permissions) logs a warning
    and is skipped rather than failing the whole discovery run.
    """
    async def _one(pid: str) -> list[dict]:
        try:
            services = await list_project_services(pid)
        except Exception as exc:
            logging.getLogger(__name__).warning(f"[zeabur] Failed to list services for project {pid}: {exc}")
            return []
        for s in services:
            s["project_id"] = pid
        return services

    results = await asyncio.gather(*(_one(pid) for pid in project_ids))
    return [service for batch in results for service in batch]


def format_log_lines(log_entries: list[dict]) -> list[str]:
    """Converts raw log entries to plain text lines."""
    lines = []
    for entry in log_entries:
        ts = entry.get("timestamp", "")
        msg = entry.get("message", "").rstrip()
        if ts:
            # Trim ISO timestamp to HH:MM:SS
            try:
                time_part = ts[11:19]
            except Exception:
                time_part = ts
            lines.append(f"[{time_part}] {msg}")
        else:
            lines.append(msg)
    return lines
