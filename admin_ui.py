"""
/admin web page — pick which Zeabur projects to scan for bot auto-discovery
and which discovered services to exclude (databases, monitoring-miku itself,
etc), instead of hand-editing ZEABUR_PROJECT_IDS / ZEABUR_EXCLUDED_SERVICE_IDS
as CSV env vars.

Mounted onto the existing aiohttp health server (health_server.py) so it needs
no separate process or port. Guarded by config.ADMIN_TOKEN — every route here
requires it, either as ?token=... (page load) or header X-Admin-Token (API calls).
"""

import hmac
import json
import logging

from aiohttp import web

import admin_config
import bot_registry
import config
from services import zeabur

log = logging.getLogger(__name__)


def _token_ok(token: str | None) -> bool:
    return bool(config.ADMIN_TOKEN) and bool(token) and hmac.compare_digest(token, config.ADMIN_TOKEN)


def _require_token(request: web.Request) -> str | None:
    """Returns an error response if the token is missing/wrong/disabled, else None."""
    if not config.ADMIN_TOKEN:
        return web.json_response({"error": "ADMIN_TOKEN not configured on the server"}, status=503)
    token = request.headers.get("X-Admin-Token") or request.query.get("token")
    if not _token_ok(token):
        return web.json_response({"error": "unauthorized"}, status=401)
    return None


async def _page(request: web.Request) -> web.Response:
    if not config.ADMIN_TOKEN:
        return web.Response(text="ADMIN_TOKEN not configured on the server.", status=503)
    token = request.query.get("token")
    if not _token_ok(token):
        return web.Response(text=_LOGIN_HTML, content_type="text/html", status=401)
    return web.Response(text=_HTML.replace("__TOKEN__", json.dumps(token)), content_type="text/html")


async def _api_projects(request: web.Request) -> web.Response:
    if (err := _require_token(request)) is not None:
        return err
    try:
        projects = await zeabur.list_projects()
    except Exception as exc:
        log.warning(f"[admin] Failed to list Zeabur projects: {exc}")
        return web.json_response({"error": str(exc)}, status=502)
    return web.json_response({"projects": projects})


async def _api_services(request: web.Request) -> web.Response:
    if (err := _require_token(request)) is not None:
        return err
    raw_ids = request.query.get("project_ids", "")
    project_ids = [p.strip() for p in raw_ids.split(",") if p.strip()]
    if not project_ids:
        return web.json_response({"services": []})
    try:
        services = await zeabur.list_all_services(project_ids)
    except Exception as exc:
        log.warning(f"[admin] Failed to list Zeabur services: {exc}")
        return web.json_response({"error": str(exc)}, status=502)
    return web.json_response({"services": services})


async def _api_get_config(request: web.Request) -> web.Response:
    if (err := _require_token(request)) is not None:
        return err
    return web.json_response(admin_config.get_config())


async def _api_set_config(request: web.Request) -> web.Response:
    if (err := _require_token(request)) is not None:
        return err
    try:
        body = await request.json()
        project_ids = [str(p) for p in body["project_ids"]]
        excluded_service_ids = [str(s) for s in body["excluded_service_ids"]]
    except (json.JSONDecodeError, KeyError, TypeError):
        return web.json_response({"error": "expected {project_ids: [...], excluded_service_ids: [...]}"}, status=400)

    admin_config.set_config(project_ids, excluded_service_ids)
    log.info(
        f"[admin] Discovery config updated — {len(project_ids)} project(s), "
        f"{len(excluded_service_ids)} excluded service(s)"
    )

    try:
        bot_count = await bot_registry.refresh_registry()
    except Exception as exc:
        log.warning(f"[admin] Config saved but refresh failed: {exc}")
        return web.json_response({"ok": True, "bot_count": None, "refresh_error": str(exc)})

    return web.json_response({"ok": True, "bot_count": bot_count})


def add_admin_routes(app: web.Application) -> None:
    app.router.add_get("/admin", _page)
    app.router.add_get("/admin/api/projects", _api_projects)
    app.router.add_get("/admin/api/services", _api_services)
    app.router.add_get("/admin/api/config", _api_get_config)
    app.router.add_post("/admin/api/config", _api_set_config)


_LOGIN_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MonitoringMiku — Admin</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 420px; margin: 4rem auto; padding: 0 1rem; }
  input { width: 100%; padding: 0.55rem; border-radius: 6px; border: 1px solid #8886; box-sizing: border-box; margin: 0.5rem 0; }
  button { padding: 0.55rem 1.1rem; border-radius: 6px; border: none; background: #5b5bd6; color: white; font-size: 0.95rem; cursor: pointer; }
</style>
</head>
<body>
<h1>🎐 Admin sign-in</h1>
<p>Enter the <code>ADMIN_TOKEN</code> configured on the server.</p>
<form id="f">
  <input type="password" id="token" placeholder="Admin token" autofocus>
  <button type="submit">Continue</button>
</form>
<script>
document.getElementById("f").onsubmit = (e) => {
  e.preventDefault();
  const t = document.getElementById("token").value;
  if (t) window.location.href = "/admin?token=" + encodeURIComponent(t);
};
</script>
</body>
</html>
"""

_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MonitoringMiku — Discovery Config</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.3rem; }
  h2 { font-size: 1rem; margin-top: 2rem; }
  .card { border: 1px solid #8884; border-radius: 8px; padding: 0.75rem; margin: 0.5rem 0; }
  .row { display: flex; align-items: center; gap: 0.6rem; padding: 0.35rem 0; }
  .row label { flex: 1; cursor: pointer; }
  .muted { opacity: 0.65; font-size: 0.85rem; }
  button { padding: 0.5rem 1rem; border-radius: 6px; border: none; background: #5b5bd6; color: white; font-size: 0.95rem; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  #status { margin-top: 1rem; font-size: 0.9rem; }
  code { background: #8882; padding: 0.1rem 0.3rem; border-radius: 4px; }
</style>
</head>
<body>
<h1>🎐 MonitoringMiku — Discovery Config</h1>
<p class="muted">Pick which Zeabur projects to scan for bots, then uncheck any discovered services that aren't bots (databases, this service itself, etc).</p>

<h2>Projects to scan</h2>
<div id="projects" class="card">Loading…</div>

<h2>Discovered services — untick to exclude</h2>
<div id="services" class="card muted">Select a project above first.</div>

<button id="save" disabled>Save &amp; refresh registry</button>
<div id="status"></div>

<script>
const TOKEN = __TOKEN__;

async function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({"X-Admin-Token": TOKEN}, opts.headers || {});
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

let selectedProjects = new Set();
let excludedServices = new Set();

async function init() {
  const [{project_ids, excluded_service_ids}, {projects}] = await Promise.all([
    api("/admin/api/config?token=" + encodeURIComponent(TOKEN)),
    api("/admin/api/projects?token=" + encodeURIComponent(TOKEN)),
  ]);
  selectedProjects = new Set(project_ids);
  excludedServices = new Set(excluded_service_ids);
  renderProjects(projects);
  if (selectedProjects.size) await loadServices();
  document.getElementById("save").disabled = false;
}

function renderProjects(projects) {
  const el = document.getElementById("projects");
  if (!projects.length) { el.textContent = "No projects found for this Zeabur token."; return; }
  el.innerHTML = "";
  for (const p of projects) {
    const row = document.createElement("div");
    row.className = "row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedProjects.has(p.id);
    cb.onchange = () => {
      if (cb.checked) selectedProjects.add(p.id); else selectedProjects.delete(p.id);
      loadServices();
    };
    const label = document.createElement("label");
    label.textContent = p.name + " ";
    const idSpan = document.createElement("span");
    idSpan.className = "muted";
    idSpan.textContent = p.id;
    label.appendChild(idSpan);
    row.appendChild(cb);
    row.appendChild(label);
    el.appendChild(row);
  }
}

async function loadServices() {
  const el = document.getElementById("services");
  if (!selectedProjects.size) {
    el.className = "card muted";
    el.textContent = "Select a project above first.";
    return;
  }
  el.className = "card muted";
  el.textContent = "Loading…";
  const ids = Array.from(selectedProjects).join(",");
  const {services} = await api("/admin/api/services?token=" + encodeURIComponent(TOKEN) + "&project_ids=" + encodeURIComponent(ids));
  el.className = "card";
  el.innerHTML = "";
  if (!services.length) { el.textContent = "No services found in the selected project(s)."; return; }
  for (const s of services) {
    const row = document.createElement("div");
    row.className = "row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !excludedServices.has(s.id);
    cb.onchange = () => {
      if (cb.checked) excludedServices.delete(s.id); else excludedServices.add(s.id);
    };
    const label = document.createElement("label");
    label.textContent = s.name + " ";
    const idSpan = document.createElement("span");
    idSpan.className = "muted";
    idSpan.textContent = s.id;
    label.appendChild(idSpan);
    row.appendChild(cb);
    row.appendChild(label);
    el.appendChild(row);
  }
}

document.getElementById("save").onclick = async () => {
  const btn = document.getElementById("save");
  const statusEl = document.getElementById("status");
  btn.disabled = true;
  statusEl.textContent = "Saving…";
  try {
    const data = await api("/admin/api/config?token=" + encodeURIComponent(TOKEN), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        project_ids: Array.from(selectedProjects),
        excluded_service_ids: Array.from(excludedServices),
      }),
    });
    statusEl.textContent = data.bot_count != null
      ? ("Saved — registry refreshed, " + data.bot_count + " bot(s) discovered.")
      : ("Saved, but registry refresh failed: " + data.refresh_error);
  } catch (e) {
    statusEl.textContent = "Error: " + e.message;
  }
  btn.disabled = false;
};

init().catch(e => { document.getElementById("status").textContent = "Error: " + e.message; });
</script>
</body>
</html>
"""
