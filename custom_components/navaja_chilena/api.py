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
