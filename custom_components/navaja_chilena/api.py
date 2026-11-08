"""Clientes para las APIs públicas usadas por la integración."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import INDICATORS_URL, METRO_URL, REQUEST_TIMEOUT, STOP_URL

STOP_CODE_RE = re.compile(r"^[A-Z]{1,3}\d{1,5}$")


class NavajaApiError(Exception):
    """Error al consultar o interpretar una API."""


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
    operational: bool
    message: str
    stations_with_issues: list[str] = field(default_factory=list)


def _status_ok(status: Any) -> tuple[bool, str]:
    """Normaliza el estado de una línea/estación a (operativa, mensaje)."""
    code: Any = status
    message = ""
    if isinstance(status, dict):
        code = status.get("code", status.get("id", status.get("estado")))
        message = str(status.get("message") or status.get("description") or "")
    elif isinstance(status, bool):
        return status, "Operativa" if status else "Con problemas"
    code_s = str(code).strip().lower() if code is not None else ""
    ok = code_s in {"1", "true", "ok", "operativa", "operational", "open"}
    return ok, message or ("Operativa" if ok else "Con problemas")


def parse_metro(data: Any) -> dict[str, MetroLine]:
    """Interpreta la respuesta de https://api.xor.cl/red/metro-network."""
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
        status = item.get("status", item.get("estado"))
        stations = item.get("stations") or item.get("estaciones") or []
        problems: list[str] = []
        for st in stations:
            if not isinstance(st, dict):
                continue
            st_ok, _ = _status_ok(st.get("status", st.get("estado")))
            if not st_ok and st.get("status", st.get("estado")) is not None:
                problems.append(str(st.get("name") or st.get("nombre") or st.get("id")))
        ok, message = _status_ok(status)
        result[line_id] = MetroLine(
            id=line_id,
            name=str(item.get("name") or item.get("nombre") or line_id.upper()),
            operational=ok,
            message=message,
            stations_with_issues=problems,
        )
    if not result:
        raise NavajaApiError("La respuesta no contiene líneas de Metro")
    return result


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
    """Interpreta la lista de sismos (más reciente primero)."""
    if isinstance(data, dict):
        data = data.get("data") or data.get("sismos") or []
    if not isinstance(data, list):
        raise NavajaApiError("Respuesta de sismos inesperada")
    quakes: list[Quake] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        mag = _num(_pick(item, "Magnitud", "magnitude", "mag"))
        if mag is None:
            continue
        quakes.append(
            Quake(
                magnitude=mag,
                latitude=_num(_pick(item, "Latitud", "latitude", "lat")),
                longitude=_num(_pick(item, "Longitud", "longitude", "lon", "lng")),
                depth_km=_num(_pick(item, "Profundidad", "depth")),
                reference=_pick(item, "RefGeografica", "referencia", "reference"),
                date=_pick(item, "Fecha", "fecha", "date"),
            )
        )
    if not quakes:
        raise NavajaApiError("La respuesta no contiene sismos")
    # Si hay fecha ISO-like ordenable, deja el más reciente primero.
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
