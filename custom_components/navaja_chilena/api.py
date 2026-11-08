"""Clientes para las APIs públicas usadas por la integración."""

from __future__ import annotations

import re
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import INDICATORS_URL, METRO_URL, REQUEST_TIMEOUT, STOP_URL

STOP_CODE_RE = re.compile(r"^[A-Z]{1,3}\d{1,5}$")


class NavajaApiError(Exception):
    """Error al consultar o interpretar una API."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def normalize_stop_code(raw: str) -> str:
    """Devuelve el código de paradero en mayúsculas, sin espacios."""
    return raw.strip().upper()


def parse_stop_codes(raw: str) -> list[str]:
    """Separa una lista de paraderos escrita por el usuario.

    Acepta comas, punto y coma o espacios. Elimina duplicados conservando el
    orden. Lanza ValueError si algún código no es válido.
    """
    codes: list[str] = []
    for part in re.split(r"[,;\s]+", raw):
        if not part:
            continue
        code = normalize_stop_code(part)
        if not STOP_CODE_RE.match(code):
            raise ValueError(code)
        if code not in codes:
            codes.append(code)
    return codes


async def _get_json(session: aiohttp.ClientSession, url: str) -> Any:
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)
    except aiohttp.ClientResponseError as err:
        raise NavajaApiError(f"Error consultando {url}: {err}", err.status) from err
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise NavajaApiError(f"Error consultando {url}: {err}") from err


# ---------------------------------------------------------------- Indicadores


@dataclass(frozen=True)
class Indicator:
    """Valor de un indicador económico."""

    code: str
    name: str
    unit: str | None
    value: float
    date: str | None


def parse_indicators(data: Any) -> dict[str, Indicator]:
    """Interpreta la respuesta de https://mindicador.cl/api."""
    if not isinstance(data, dict):
        raise NavajaApiError("Respuesta de indicadores inesperada")
    result: dict[str, Indicator] = {}
    for code, item in data.items():
        if not isinstance(item, dict) or "valor" not in item:
            continue  # version, autor, fecha, etc.
        try:
            value = float(item["valor"])
        except (TypeError, ValueError):
            continue
        result[code] = Indicator(
            code=code,
            name=str(item.get("nombre", code)),
            unit=item.get("unidad_medida"),
            value=value,
            date=item.get("fecha"),
        )
    if not result:
        raise NavajaApiError("La respuesta no contiene indicadores")
    return result


async def fetch_indicators(session: aiohttp.ClientSession) -> dict[str, Indicator]:
    return parse_indicators(await _get_json(session, INDICATORS_URL))


# ---------------------------------------------------------------------- Metro


@dataclass(frozen=True)
class MetroLine:
    """Estado operacional de una línea del Metro de Santiago."""

    id: str
    name: str
    operational: bool | None  # None = desconocido
    message: str
    stations_with_issues: list[str] = field(default_factory=list)
    stations: dict[str, bool] = field(default_factory=dict)  # nombre -> operativa


_OK_CODES = {"0", "true", "ok", "operativa", "operativo", "operational", "normal", "open"}
_BAD_CODES = {
    "1", "2", "3", "false", "cerrada", "cerrado", "closed", "no habilitada",
    "con problemas", "problemas", "accesos cerrados",
}


def _status_ok(status: Any) -> tuple[bool | None, str]:
    """Normaliza un estado a (operativa, mensaje).

    En api.xor.cl los códigos de estación son: 0 operativa, 1 cerrada
    temporalmente, 2 no habilitada, 3 accesos cerrados. Si el estado no es
    reconocible devuelve None (desconocido): nunca se asume "operativa".
    """
    if status is None:
        return None, ""
    code: Any = status
    message = ""
    if isinstance(status, dict):
        code = next(
            (status[k] for k in ("code", "id", "estado", "status") if k in status), None
        )
        message = str(status.get("message") or status.get("description") or "")
    if isinstance(code, bool):
        return code, message
    code_s = str(code).strip().lower() if code is not None else ""
    if code_s in _OK_CODES:
        return True, message or "Operativa"
    if code_s in _BAD_CODES:
        return False, message or "Con problemas"
    return None, message


def parse_metro(data: Any) -> dict[str, MetroLine]:
    """Interpreta la respuesta de https://api.xor.cl/red/metro-network.

    El estado de la línea se deduce de sus estaciones cuando existen; si no,
    del estado propio de la línea. Si no se puede determinar, queda en None
    (el sensor aparece como no disponible en lugar de inventar "operativa").
    """
    lines_raw = data.get("lines", data) if isinstance(data, dict) else data
    if isinstance(lines_raw, dict):
        lines_raw = list(lines_raw.values())
    if not isinstance(lines_raw, list):
        raise NavajaApiError("Respuesta de Metro inesperada")

    result: dict[str, MetroLine] = {}
    for item in lines_raw:
        if not isinstance(item, dict) or "id" not in item:
            continue
        line_id = str(item["id"]).lower()
        stations = item.get("stations") or item.get("estaciones") or []
        problems: list[str] = []
        station_states: dict[str, bool] = {}
        known = 0
        for st in stations:
            if not isinstance(st, dict):
                continue
            ok, _ = _status_ok(st.get("status", st.get("estado")))
            st_name = str(st.get("name") or st.get("nombre") or st.get("id"))
            if ok is None:
                continue
            known += 1
            station_states[st_name] = ok
            if not ok:
                problems.append(st_name)
        line_ok, message = _status_ok(item.get("status", item.get("estado")))
        if known:
            operational: bool | None = not problems
            if problems and not message:
                message = f"{len(problems)} estación(es) con problemas"
        else:
            operational = line_ok
        if operational and not message:
            message = "Operativa"
        result[line_id] = MetroLine(
            id=line_id,
            name=str(item.get("name") or item.get("nombre") or line_id.upper()),
            operational=operational,
            message=message,
            stations_with_issues=problems,
            stations=station_states,
        )
    if not result or all(l.operational is None for l in result.values()):
        raise NavajaApiError("No se pudo interpretar el estado del Metro")
    return result


# Horario de funcionamiento del Metro de Santiago (hora de Chile continental).
METRO_TZ = "America/Santiago"
METRO_HOURS = {
    "weekday": (time(6, 0), time(23, 0)),
    "saturday": (time(6, 30), time(23, 0)),
    "sunday": (time(7, 30), time(23, 0)),  # domingo y festivos
}


def metro_hours(now: datetime, holiday: bool = False) -> tuple[time, time]:
    """Hora de apertura y cierre que rige en el día de `now`."""
    if holiday or now.weekday() == 6:
        return METRO_HOURS["sunday"]
    return METRO_HOURS["saturday" if now.weekday() == 5 else "weekday"]


def metro_is_open(now: datetime | None = None, holiday: bool = False) -> bool:
    """True si el Metro está en horario de servicio ahora (hora de Santiago)."""
    now = now.astimezone(ZoneInfo(METRO_TZ)) if now else datetime.now(ZoneInfo(METRO_TZ))
    opens, closes = metro_hours(now, holiday)
    return opens <= now.time() < closes


async def fetch_metro(session: aiohttp.ClientSession) -> dict[str, MetroLine]:
    return parse_metro(await _get_json(session, METRO_URL))


# ------------------------------------------------------------------ Paraderos


@dataclass(frozen=True)
class StopService:
    """Próximas llegadas de un recorrido a un paradero."""

    id: str
    status: str
    buses: list[dict[str, Any]]

    @property
    def next_minutes(self) -> int | None:
        times = [
            b["min_arrival_time"]
            for b in self.buses
            if isinstance(b.get("min_arrival_time"), int)
        ]
        return min(times) if times else None


@dataclass(frozen=True)
class StopInfo:
    """Estado de un paradero de Red Movilidad."""

    code: str
    name: str | None
    status: str
    services: list[StopService]

    @property
    def next_minutes(self) -> int | None:
        times = [s.next_minutes for s in self.services if s.next_minutes is not None]
        return min(times) if times else None


def parse_stop(code: str, data: Any) -> StopInfo:
    """Interpreta la respuesta de https://api.xor.cl/red/bus-stop/{code}."""
    if not isinstance(data, dict):
        raise NavajaApiError(f"Respuesta inesperada para el paradero {code}")
    if "services" not in data and "id" not in data:
        raise NavajaApiError(f"El paradero {code} no existe o no tiene datos")
    services: list[StopService] = []
    for svc in data.get("services") or []:
        if not isinstance(svc, dict):
            continue
        buses = [b for b in (svc.get("buses") or []) if isinstance(b, dict)]
        services.append(
            StopService(
                id=str(svc.get("id", "?")),
                status=str(svc.get("status_description") or ""),
                buses=buses,
            )
        )
    return StopInfo(
        code=code,
        name=data.get("name"),
        status=str(data.get("status_description") or ""),
        services=services,
    )


async def fetch_stop(session: aiohttp.ClientSession, code: str) -> StopInfo:
    return parse_stop(code, await _get_json(session, STOP_URL.format(code=code)))


# --------------------------------------------------------------------- Sismos

from datetime import date  # noqa: E402
import unicodedata  # noqa: E402

from .const import AIR_URL, HOLIDAYS_URLS, PHARMACY_URL, QUAKES_URL  # noqa: E402


def _num(value: Any) -> float | None:
    """Extrae el primer número de un valor como '4.2 Ml' o '-33,4'."""
    if value is None:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    return float(m.group().replace(",", ".")) if m else None


def _pick(item: dict, *keys: str) -> Any:
    lower = {k.lower(): v for k, v in item.items()}
    for key in keys:
        if key.lower() in lower:
            return lower[key.lower()]
    return None


@dataclass(frozen=True)
class Quake:
    """Un sismo reportado por el Centro Sismológico Nacional."""

    magnitude: float
    latitude: float | None
    longitude: float | None
    depth_km: float | None
    reference: str | None
    date: str | None


def parse_quakes(data: Any) -> list[Quake]:
    """Interpreta el GeoJSON de USGS (FDSN) y deja solo sismos de Chile."""
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise NavajaApiError("Respuesta de sismos inesperada")
    quakes: list[Quake] = []
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        place = str(props.get("place") or "")
        mag = _num(props.get("mag"))
        if mag is None or "chile" not in place.lower() or len(coords) < 2:
            continue
        when = None
        if isinstance(props.get("time"), (int, float)):
            when = (
                datetime.fromtimestamp(props["time"] / 1000, ZoneInfo(METRO_TZ))
                .replace(microsecond=0)
                .isoformat()
            )
        quakes.append(
            Quake(
                magnitude=mag,
                latitude=_num(coords[1]),
                longitude=_num(coords[0]),
                depth_km=_num(coords[2]) if len(coords) > 2 else None,
                reference=place,
                date=when,
            )
        )
    if not quakes:
        raise NavajaApiError("La respuesta no contiene sismos de Chile")
    quakes.sort(key=lambda q: q.date or "", reverse=True)
    return quakes


async def fetch_quakes(session: aiohttp.ClientSession) -> list[Quake]:
    return parse_quakes(await _get_json(session, QUAKES_URL))


# -------------------------------------------------------------------- Feriados


@dataclass(frozen=True)
class Holiday:
    date: date
    name: str
    kind: str | None
    inalienable: bool


def parse_holidays(data: Any) -> list[Holiday]:
    """Acepta el formato del gobierno (lista) y el de boostr ({'data': [...]})."""
    if isinstance(data, dict):
        data = data.get("data")
    if not isinstance(data, list):
        raise NavajaApiError("Respuesta de feriados inesperada")
    out: list[Holiday] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw = _pick(item, "fecha", "date")
        try:
            d = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        inal = _pick(item, "irrenunciable", "inalienable")
        out.append(
            Holiday(
                date=d,
                name=str(_pick(item, "nombre", "title", "name") or "Feriado"),
                kind=_pick(item, "tipo", "type"),
                inalienable=str(inal).lower() in {"1", "true"},
            )
        )
    if not out:
        raise NavajaApiError("La respuesta no contiene feriados")
    return sorted(out, key=lambda h: h.date)


async def fetch_holidays(session: aiohttp.ClientSession, year: int) -> list[Holiday]:
    last: Exception | None = None
    for url in HOLIDAYS_URLS:
        try:
            return parse_holidays(await _get_json(session, url.format(year=year)))
        except NavajaApiError as err:
            last = err
    raise NavajaApiError(f"No se pudieron obtener feriados {year}: {last}")


def next_holiday(holidays: list[Holiday], today: date) -> Holiday | None:
    return next((h for h in holidays if h.date >= today), None)


# ------------------------------------------------------- Calidad del aire y UV


@dataclass(frozen=True)
class AirQuality:
    pm2_5: float | None
    pm10: float | None
    aqi: float | None
    uv_index: float | None


def parse_air(data: Any) -> AirQuality:
    """Interpreta la respuesta de Open-Meteo Air Quality."""
    cur = data.get("current") if isinstance(data, dict) else None
    if not isinstance(cur, dict):
        raise NavajaApiError("Respuesta de calidad del aire inesperada")
    return AirQuality(
        pm2_5=_num(cur.get("pm2_5")),
        pm10=_num(cur.get("pm10")),
        aqi=_num(cur.get("us_aqi")),
        uv_index=_num(cur.get("uv_index")),
    )


async def fetch_air(session: aiohttp.ClientSession, lat: float, lon: float) -> AirQuality:
    return parse_air(await _get_json(session, AIR_URL.format(lat=lat, lon=lon)))


# ------------------------------------------------------------------ Farmacias


def _fold(text: Any) -> str:
    """Minúsculas y sin tildes, para comparar nombres de comuna."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


@dataclass(frozen=True)
class Pharmacy:
    name: str
    address: str
    phone: str | None
    opens: str | None
    closes: str | None
    latitude: float | None
    longitude: float | None


def parse_pharmacies(data: Any, comuna: str) -> list[Pharmacy]:
    """Filtra por comuna los locales de turno del MINSAL."""
    if not isinstance(data, list):
        raise NavajaApiError("Respuesta de farmacias inesperada")
    wanted = _fold(comuna)
    out: list[Pharmacy] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if _fold(item.get("comuna_nombre")) != wanted:
            continue
        out.append(
            Pharmacy(
                name=str(item.get("local_nombre") or "").strip(),
                address=str(item.get("local_direccion") or "").strip(),
                phone=item.get("local_telefono"),
                opens=item.get("funcionamiento_hora_apertura"),
                closes=item.get("funcionamiento_hora_cierre"),
                latitude=_num(item.get("local_lat")),
                longitude=_num(item.get("local_lng")),
            )
        )
    return out


async def fetch_pharmacies(session: aiohttp.ClientSession, comuna: str) -> list[Pharmacy]:
    return parse_pharmacies(await _get_json(session, PHARMACY_URL), comuna)
