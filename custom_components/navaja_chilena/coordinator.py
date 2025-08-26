# Author: duvob90
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Iterable

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    UPDATE_INTERVAL_SECONDS,
    CONF_STOP_IDS,
    USD_URL, UF_URL, METRO_URL, BUS_URL_TMPL, SISMOS_URL,
)

_LOGGER = logging.getLogger(__name__)


def _try_float(v) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".")
        return float(s)
    except Exception:
        return None


def _first(items: Iterable[Any]) -> Any | None:
    for it in items:
        if it is not None:
            return it
    return None


def _fmt_eta(obj: dict) -> str | None:
    """Construye una ETA legible desde múltiples formatos (XOR y variantes)."""
    # 1) Campo ya listo
    txt = _first([obj.get("arrival_estimation"), obj.get("eta_text"), obj.get("eta")])
    if isinstance(txt, str) and txt.strip():
        return txt.strip()

    # 2) Rangos numéricos (a/b, min/max, etc.)
    for a_key, b_key in (("a", "b"), ("min", "max"), ("min_arrival", "max_arrival"), ("min_arrive", "max_arrive")):
        a = _try_float(obj.get(a_key))
        b = _try_float(obj.get(b_key))
        if a is not None and b is not None:
            return f"Entre {int(a):02d} Y {int(b):02d} min."

    # 3) Strings tipo "06-08", "6 a 8", "6–8"
    raw = _first([obj.get("arrives_in"), obj.get("time"), obj.get("window"), obj.get("range")])
    if isinstance(raw, str):
        s = raw.lower().replace("min.", "").replace("min", "").strip()
        for sep in ("-", "–", "—", " a ", " y "):
            if sep in s:
                p = [x.strip() for x in s.split(sep)]
                if len(p) >= 2 and p[0].isdigit() and p[1].isdigit():
                    return f"Entre {int(p[0]):02d} Y {int(p[1]):02d} min."

    # 4) Timestamp → minutos
    ts = _first([obj.get("datetime"), obj.get("timestamp"), obj.get("hora"), obj.get("time_at")])
    if isinstance(ts, str) and ts:
        try:
            target = dt_util.parse_datetime(ts)
            if target:
                mins = max(0, int((target - dt_util.utcnow()).total_seconds() / 60))
                return f"{mins} min"
        except Exception:
            pass

    # 5) Número suelto
    m = _try_float(_first([obj.get("minutes"), obj.get("minutos")]))
    if m is not None:
        return f"{int(m)} min"

    return None


class NavajaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Navaja Chilena Coordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)

        stops_str = self.entry.options.get(CONF_STOP_IDS, self.entry.data.get(CONF_STOP_IDS, ""))
        stop_ids = [s.strip().upper() for s in stops_str.split(",") if s.strip()]

        async def fetch_json(url: str) -> Any:
            try:
                async with session.get(url, timeout=20) as resp:
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except Exception as e:
                _LOGGER.warning("Fetch failed for %s: %s", url, e)
                return None

        usd_task = asyncio.create_task(fetch_json(USD_URL))
        uf_task = asyncio.create_task(fetch_json(UF_URL))
        metro_task = asyncio.create_task(fetch_json(METRO_URL))
        sismos_task = asyncio.create_task(fetch_json(SISMOS_URL))
        bus_tasks = {sid: asyncio.create_task(fetch_json(BUS_URL_TMPL.format(stop_id=sid))) for sid in stop_ids}

        usd_json, uf_json, metro_json, sismos_json = await asyncio.gather(
            usd_task, uf_task, metro_task, sismos_task
        )

        # ---- USD ----
        usd_val = None
        if isinstance(usd_json, dict):
            serie = usd_json.get("serie")
            if isinstance(serie, list) and serie:
                usd_val = serie[0].get("valor")
            if usd_val is None and isinstance(usd_json.get("dolar"), dict):
                usd_val = usd_json["dolar"].get("valor")

        # ---- UF ----
        uf_val = None
        if isinstance(uf_json, dict):
            serie = uf_json.get("serie")
            if isinstance(serie, list) and serie:
                uf_val = serie[0].get("valor")
            if uf_val is None and isinstance(uf_json.get("uf"), dict):
                uf_val = uf_json["uf"].get("valor")

        # ---- Metro ---- (default Operativa)
        metro_lines: dict[str, str] = {f"L{i}": "Operativa" for i in (1, 2, 3, 4, 5, 6)}
        metro_lines["L4A"] = "Operativa"

        def _lid(name: Any) -> str | None:
            if not name:
                return None
            lid = str(name).upper().replace(" ", "")
            if lid.startswith("LINEA"):
                lid = "L" + lid.split("LINEA", 1)[1]
            return lid

        if isinstance(metro_json, dict):
            lines = metro_json.get("lineas") or metro_json.get("lines") or metro_json.get("data")
            if isinstance(lines, list):
                for ln in lines:
                    if not isinstance(ln, dict):
                        continue
                    lid = _lid(ln.get("nombre") or ln.get("name") or ln.get("linea") or ln.get("id"))
                    status = ln.get("estado") or ln.get("status") or ln.get("detalle") or ln.get("state")
                    if lid:
                        metro_lines[lid] = status or "Operativa"
            else:
                for k, v in metro_json.items():
                    if str(k).upper().startswith("L"):
                        metro_lines[str(k).upper()] = str(v or "Operativa")
        elif isinstance(metro_json, list):
            for ln in metro_json:
                if isinstance(ln, dict):
                    lid = _lid(ln.get("nombre") or ln.get("name") or ln.get("linea") or ln.get("id"))
                    status = ln.get("estado") or ln.get("status") or ln.get("detalle") or ln.get("state")
                    if lid:
                        metro_lines[lid] = status or "Operativa"

        # Incidencias por línea
        metro_details: dict[str, dict[str, Any]] = {}
        if isinstance(metro_json, dict):
            lines = metro_json.get("lineas") or metro_json.get("lines") or metro_json.get("data")
            if isinstance(lines, list):
                for ln in lines:
                    if not isinstance(ln, dict):
                        continue
                    lid = _lid(ln.get("nombre") or ln.get("name") or ln.get("linea") or ln.get("id"))
                    if not lid:
                        continue
                    affected: list[str] = []
                    details: list[str] = []
                    for key in ("incidencias", "incidents", "issues"):
                        val = ln.get(key)
                        if isinstance(val, list):
                            for it in val:
                                if isinstance(it, dict):
                                    st = it.get("estacion") or it.get("station") or it.get("name") or it.get("id")
                                    if st:
                                        affected.append(str(st))
                                    txt = it.get("detalle") or it.get("detail") or it.get("status") or it.get("description")
                                    if txt:
                                        details.append(str(txt))
                                else:
                                    details.append(str(it))
                    for key in ("estaciones", "stations"):
                        val = ln.get(key)
                        if isinstance(val, list):
                            for st in val:
                                if isinstance(st, dict):
                                    st_name = st.get("nombre") or st.get("name") or st.get("id")
                                    st_state = st.get("estado") or st.get("status")
                                    if st_name and st_state and str(st_state).lower() not in ("normal", "operativa", "ok"):
                                        affected.append(str(st_name))
                    if affected or details:
                        metro_details[lid] = {
                            "affected_stations": sorted(set(affected)),
                            "details": details,
                        }

        # ---- Sismos ----
        sismo_state = "N/A"
        sismo_attr: dict[str, Any] = {}
        if isinstance(sismos_json, list) and sismos_json:
            last = sismos_json[0]
            mag = _first([last.get("Magnitud"), last.get("magnitud"), last.get("Mag")])
            num_mag = _try_float(mag)
            ref = _first([last.get("RefGeografica"), last.get("Referencia"), last.get("ref")])
            fecha = _first([last.get("Fecha"), last.get("fecha"), last.get("time")])
            prof = _first([last.get("Profundidad"), last.get("profundidad")])
            lat = _try_float(_first([last.get("Latitud"), last.get("lat"), last.get("Latitude")]))
            lon = _try_float(_first([last.get("Longitud"), last.get("lon"), last.get("Longitude")]))
            sismo_state = f"M {num_mag:.1f}" if num_mag is not None else str(mag or "N/A")
            sismo_attr = {
                "referencia": ref,
                "fecha": fecha,
                "profundidad_km": prof,
                "latitude": lat,
                "longitude": lon,
            }

        # ---- Buses ----
        bus_data: dict[str, Any] = {}
        for sid, t in bus_tasks.items():
            js = await t
            out = {"name": None, "arrivals": []}
            if isinstance(js, dict):
                out["name"] = _first([js.get("name"), js.get("stop"), js.get("title")]) or sid
                buses = js.get("buses") or js.get("services") or js.get("arrivals") or js.get("next_buses") or []
                if isinstance(buses, list):
                    for b in buses[:8]:
                        route = _first([b.get("route"), b.get("servicio"), b.get("service"), b.get("route_id"), b.get("id")]) or ""
                        head = _first([b.get("headsign"), b.get("destination"), b.get("destino")]) or ""
                        eta_txt = _fmt_eta(b)
                        out["arrivals"].append({"route": route, "eta": eta_txt, "dest": head})
            bus_data[sid] = out

        return {
            "usd": usd_val,
            "uf": uf_val,
            "metro_lines": metro_lines,
            "metro_details": metro_details,
            "sismo": {"state": sismo_state, "attr": sismo_attr},
            "buses": bus_data,
        }
