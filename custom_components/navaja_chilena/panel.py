# Author: duvob90
from __future__ import annotations
import aiohttp
from yarl import URL
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_BUS_TMPL = "https://api.xor.cl/red/bus-stop/{stop_id}"

HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Navaja Chilena — Paraderos</title>
<style>
body { font-family: sans-serif; margin: 1.25rem; }
input, button { font-size: 1rem; padding: 0.5rem; }
#res { margin-top: 1rem; white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-top: 1rem; }
h1 { margin-top: 0; font-size: 1.25rem; }
small { color: #555; }
</style>
</head>
<body>
  <h1>Navaja Chilena — Bus Stop Browser</h1>
  <p>Ingresa un <b>código de paradero</b> (p. ej. <code>PA433</code>). Este buscador valida y muestra próximos buses.</p>
  <form id="f">
    <input id="stop" placeholder="PA433" />
    <button type="submit">Buscar</button>
  </form>
  <div id="res"></div>
<script>
const $ = s => document.querySelector(s);
$("#f").addEventListener("submit", async (e) => {
  e.preventDefault();
  const stop = $("#stop").value.trim();
  if (!stop) return;
  $("#res").textContent = "Consultando...";
  try {
    const r = await fetch(`/api/navaja_chilena/lookup?stop_id=${encodeURIComponent(stop)}`);
    const j = await r.json();
    if (j.error) {
      $("#res").innerHTML = `<div class="card"><b>Error:</b> ${j.error}</div>`;
      return;
    }
    const name = j.name || stop;
    const arr = j.arrivals || [];
    let html = `<div class="card"><div><b>${name}</b> <small>(${stop})</small></div>`;
    if (!arr.length) {
      html += `<div>No hay próximas llegadas.</div>`;
    } else {
      html += `<ul>` + arr.map(a => `<li><b>${a.route || ""}</b> → ${a.dest || ""} <small>(${a.eta || ""})</small></li>`).join("") + `</ul>`;
    }
    html += `</div>`;
    $("#res").innerHTML = html;
  } catch (err) {
    $("#res").innerHTML = `<div class="card"><b>Error de red:</b> ${err}</div>`;
  }
});
</script>
</body>
</html>"""

class NavajaStopsPage(HomeAssistantView):
    url = "/navaja_chilena/stops"
    name = "navaja_chilena:stops"
    requires_auth = True

    async def get(self, request):
        return aiohttp.web.Response(text=HTML, content_type="text/html")

class NavajaLookupAPI(HomeAssistantView):
    url = "/api/navaja_chilena/lookup"
    name = "navaja_chilena:lookup"
    requires_auth = True

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]
        session = async_get_clientsession(hass)
        stop_id = request.query.get("stop_id", "").strip()
        if not stop_id:
            return aiohttp.web.json_response({"error": "stop_id requerido"}, status=400)
        try:
            async with session.get(API_BUS_TMPL.format(stop_id=stop_id), timeout=20) as resp:
                if resp.status != 200:
                    return aiohttp.web.json_response({"error": f"HTTP {resp.status}"}, status=resp.status)
                data = await resp.json(content_type=None)
        except Exception as e:
            return aiohttp.web.json_response({"error": f"{e}"}, status=500)

        out = {"name": data.get("name") or data.get("stop") or data.get("title") or stop_id, "arrivals": []}
        buses = data.get("buses") or data.get("services") or data.get("arrivals") or []
        if isinstance(buses, list):
            for b in buses[:10]:
                route = b.get("route") or b.get("servicio") or b.get("service") or b.get("id") or ""
                when = b.get("time") or b.get("arrives_in") or b.get("minutes") or b.get("timestamp") or b.get("datetime")
                head = b.get("headsign") or b.get("destination") or b.get("destino") or ""
                if isinstance(when, (int, float)):
                    when = f"{int(when)} min"
                out["arrivals"].append({"route": route, "eta": when, "dest": head})
        return aiohttp.web.json_response(out)

def register_views(hass: HomeAssistant) -> None:
    hass.http.register_view(NavajaStopsPage())
    hass.http.register_view(NavajaLookupAPI())
