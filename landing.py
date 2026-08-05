"""
Public landing page — GET /

Shows MonitoringMiku's own uptime plus live status for every monitored bot
(pulled client-side from the existing public /status JSON endpoint, no auth),
with a button linking through to /admin.
"""

from aiohttp import web

_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MonitoringMiku</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
  header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1.5rem; }
  h1 { font-size: 1.4rem; margin: 0; }
  .muted { opacity: 0.65; font-size: 0.85rem; }
  .card { border: 1px solid #8884; border-radius: 8px; padding: 0.9rem 1rem; margin: 0.6rem 0; }
  .row { display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0; border-bottom: 1px solid #8882; }
  .row:last-child { border-bottom: none; }
  .row .name { flex: 1; }
  .dot { width: 0.6rem; height: 0.6rem; border-radius: 50%; flex-shrink: 0; }
  .dot.up { background: #2ecc71; }
  .dot.down { background: #e74c3c; }
  .dot.unknown { background: #95a5a6; }
  .badge { font-size: 0.78rem; padding: 0.1rem 0.5rem; border-radius: 999px; background: #8882; }
  a.button { display: inline-block; padding: 0.55rem 1.1rem; border-radius: 6px; background: #5b5bd6; color: white; text-decoration: none; font-size: 0.9rem; }
  a.button:hover { opacity: 0.9; }
  #empty { opacity: 0.65; }
</style>
</head>
<body>
<header>
  <h1>🎐 MonitoringMiku</h1>
  <a class="button" href="/admin">Admin →</a>
</header>

<div class="card">
  <div class="row"><span class="name">Service uptime</span><span id="uptime" class="badge">…</span></div>
</div>

<h2 style="font-size: 1rem;">Fleet</h2>
<div id="bots" class="card">Loading…</div>

<p class="muted">Data from <code>/status</code> · auto-refreshes every 30s</p>

<script>
function fmtDuration(sec) {
  if (sec < 60) return sec + "s";
  if (sec < 3600) return Math.floor(sec / 60) + "m " + (sec % 60) + "s";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h + "h " + m + "m";
}

async function refresh() {
  try {
    const res = await fetch("/status");
    const data = await res.json();

    document.getElementById("uptime").textContent = fmtDuration(data.uptime_seconds);

    const el = document.getElementById("bots");
    if (!data.bots.length) {
      el.innerHTML = '<div id="empty">No bots discovered yet.</div>';
      return;
    }
    el.innerHTML = "";
    for (const bot of data.bots) {
      const up = bot.status === "RUNNING";
      const dotClass = up ? "up" : (bot.status === "UNKNOWN" ? "unknown" : "down");
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML =
        '<span class="dot ' + dotClass + '"></span>' +
        '<span class="name">' + bot.name + '</span>' +
        '<span class="badge">' + bot.status + '</span>';
      el.appendChild(row);
    }
  } catch (e) {
    document.getElementById("bots").textContent = "Error loading status: " + e.message;
  }
}

refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>
"""


async def landing_page(request: web.Request) -> web.Response:
    return web.Response(text=_HTML, content_type="text/html")
