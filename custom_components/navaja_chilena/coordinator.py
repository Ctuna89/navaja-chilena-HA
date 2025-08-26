# Author: duvob90
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    UPDATE_INTERVAL_SECONDS,
    CONF_STOP_IDS,
    USD_URL, UF_URL, METRO_URL, BUS_URL_TMPL, SISMOS_URL,
)

_LOGGER = logging.getLogger(__name__)


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

        # Paraderos desde opciones o datos
        stops_str = self.entry.options.get(CONF_STOP_IDS, self.entry.data.get(CONF_STOP_IDS, ""))
        stop_ids = [s.strip() for s in stops_str.split(",") if s.strip()]

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
            if usd_val is None and "dolar" in usd_json and isinstance(usd_json["dolar"], dict):
                usd_val = usd_json["dolar"].get("valor")

        # ---- UF ----
        uf_val = None
        if isinstance(uf_json, dict):
            serie = uf_json.get("serie")
            if isinstance(serie, list) and serie:
                uf_val = serie[0].get("valor")
            if uf_val is None and "uf" in uf_json and isinstance(uf_json["uf"], dict):
                uf_val = uf_json["uf"].get("valor")

        # ---- Metro por línea ----
        metro_lines: dict[str, str] = {}
        if isinstance(metro_json, dict):
            lines = metro_json.get("lineas") or metro_json.get("lines") or metro_json.get("data")
            if isinstance(lines, list):
                for ln in lines:
                    if not isinstance(ln, dict):
                        continue
                    name = ln.get("nombre") or ln.get("name") or ln.get("linea") or ln.get("id")
                    status = ln.get("estado") or ln.get("status") or ln.get("detalle") or ln.get("state")
                    if name:
                        name_str = str(name).upper().replace(" ", "")
                        metro_lines[name_str] = status or "N/A"
            else:
                for k, v in metro_json.items():
                    if isinstance(v, (str, int)) and str(k).upper().startswith("L"):
                        metro_lines[str(k).upper()] = str(v)
        elif isinstance(metro_json, list):
            for ln in metro_json:
                if isinstance(ln, dict):
                    name = ln.get("nombre") or ln.get("name") or ln.get("linea") or ln.get("id")
                    status = ln.get("estado") or ln.get("status") or ln.get("detalle") or ln.get("state")
                    if name:
                        metro_lines[str(name).upper().replace(" ", "")] = status or "N/A"

        # Incidencias/estaciones afectadas (si la API lo entrega)
        metro_details: dict[str, dict[str, Any]] = {}
        if isinstance(metro_json, dict):
            lines = metro_json.get("lineas") or metro_json.get("lines") or metro_json.get("data")
            if isinstance(lines, list):
                for ln in lines:
                    if not isinstance(ln, dict):
                        continue
                    name = ln.get("nombre") or ln.get("name") or ln.get("linea") or ln.get("id")
                    if not name:
                        continue
                    lid = str(name).upper().replace(" ", "")
                    affected = []
                    details = []
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
        sismo_state = None
        sismo_attr: dict[str, Any] = {}
        if isinstance(sismos_json, list) and sismos_json:
            last = sismos_json[0]
            mag = last.get("Magnitud") or last.get("magnitud")
            ref = last.get("RefGeografica") or last.get("Referencia") or last.get("ref")
            fecha = last.get("Fecha") or last.get("fecha")
            prof = last.get("Profundidad") or last.get("profundidad")
            lat = last.get("Latitud") or last.get("lat") or last.get("Latitude")
            lon = last.get("Longitud") or last.get("lon") or last.get("Longitude")
            try:
                lat = float(str(lat).replace(",", ".")) if lat is not None else None
            except Exception:
                lat = None
            try:
                lon = float(str(lon).replace(",", ".")) if lon is not None else None
            except Exception:
                lon = None

            sismo_state = mag
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
            stops_entry = {"name": None, "arrivals": []}
            if isinstance(js, dict):
                stops_entry["name"] = js.get("name") or js.get("stop") or js.get("title") or sid
                buses = js.get("buses") or js.get("services") or js.get("arrivals") or []
                if isinstance(buses, list):
                    for b in buses[:8]:
                        route = b.get("route") or b.get("servicio") or b.get("service") or b.get("id") or ""
                        when = b.get("time") or b.get("arrives_in") or b.get("minutes") or b.get("timestamp") or b.get("datetime")
                        head = b.get("headsign") or b.get("destination") or b.get("destino") or ""
                        if isinstance(when, (int, float)):
                            when = f"{int(when)} min"
                        stops_entry["arrivals"].append({"route": route, "eta": when, "dest": head})
            bus_data[sid] = stops_entry

        return {
            "usd": usd_val,
            "uf": uf_val,
            "metro_lines": metro_lines,
            "metro_details": metro_details,
            "sismo": {"state": sismo_state, "attr": sismo_attr},
            "buses": bus_data,
        }
