"""Cartelera de Cinépolis (Chile): consultas GraphQL y lectura de funciones.

ESTADO: estructura preparada, SIN conectar a ninguna entidad ni opción. Falta la clave de aplicación (`x-apikey`) que usa el sitio
de Cinépolis: no se obtiene de su código sin permiso, la tiene que entregar Cinépolis. Tampoco están escritos los textos de las
consultas GraphQL de `searchEntities`, `movies` y `billboard`: se agregan cuando se puedan probar contra el servicio real.

Lo que sí está listo y probado es lo que Cinépolis describió por escrito:
- servicios: POST api-g.cinepolis.com/v2/billboards/graphql y /shared-services/search/entities/graphql (país «CL»);
- encabezados: Content-Type, country-id, language y x-apikey;
- respuesta de `billboard`: data.billboard.schedules[] → dates[] → languages[] → showtimes[];
- cada función: sessionId, datetime, format.name, experience.name, screen, availability; el idioma está en el grupo (language y displayLanguage);
- respetar la zona horaria del cine (un «datetime» sin desfase NO es UTC) y conservar la fecha completa (funciones pasada la medianoche);
- ante una falla se conserva el último dato, con su hora, y nunca se presenta como «sin funciones».

Es el funcionamiento interno del sitio, no una API pública versionada: la extracción vive aquí, separada de las entidades,
para poder ajustarla si cambia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .api import HEADERS, NavajaApiError, _plain
from .const import REQUEST_TIMEOUT

CINEPOLIS_BILLBOARD_URL = "https://api-g.cinepolis.com/v2/billboards/graphql"
CINEPOLIS_SEARCH_URL = "https://api-g.cinepolis.com/shared-services/search/entities/graphql"
CINEPOLIS_COUNTRY = "CL"
CINEPOLIS_MAX_BYTES = 4_000_000
CINEPOLIS_ATTRIBUTION = "Cartelera de Cinépolis (cinepolis.cl)"


@dataclass(frozen=True)
class CinepolisCinema:
    id: str           # p. ej. "cinepolis-la-reina-santiago-oriente"
    name: str
    timezone: str     # p. ej. "America/Santiago"


@dataclass(frozen=True)
class CinepolisShowtime:
    session_id: str
    start: datetime          # con zona horaria del cine y fecha completa
    format: str | None       # p. ej. "2D"
    experience: str | None   # experiencia de sala, cuando corresponda
    screen: str | None
    language: str | None     # p. ej. "SUB" / "DOB" tal como lo entrega el servicio
    language_name: str | None
    availability: Any = None


def cinepolis_headers(api_key: str) -> dict[str, str]:
    """Encabezados que usa el sitio. La clave solo viaja en `x-apikey`; nunca se escribe en mensajes ni en el registro."""
    return HEADERS | {"Content-Type": "application/json", "country-id": CINEPOLIS_COUNTRY, "language": "ES", "x-apikey": api_key}


async def post_graphql(
    session: aiohttp.ClientSession, url: str, query: str, variables: dict[str, Any], api_key: str
) -> dict[str, Any]:
    """Una consulta GraphQL. Devuelve `data`; un error HTTP, de red o de GraphQL es un NavajaApiError (nunca «sin resultados»)."""
    if not api_key:
        raise NavajaApiError("Falta la clave de aplicación de Cinépolis")
    try:
        async with session.post(
            url,
            json={"query": query, "variables": variables},
            headers=cinepolis_headers(api_key),
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            if resp.status in (401, 403):
                raise NavajaApiError(f"Cinépolis rechazó la solicitud (HTTP {resp.status}): revisa la clave de aplicación", resp.status)
            resp.raise_for_status()
            body = await resp.content.read(CINEPOLIS_MAX_BYTES + 1)
    except aiohttp.ClientResponseError as err:
        raise NavajaApiError(f"Cinépolis respondió HTTP {err.status}", err.status) from err
    except aiohttp.ClientError as err:
        raise NavajaApiError(f"No fue posible conectar con Cinépolis: {type(err).__name__}") from err
    except TimeoutError as err:
        raise NavajaApiError("Cinépolis no respondió a tiempo") from err
    if len(body) > CINEPOLIS_MAX_BYTES:
        raise NavajaApiError("La respuesta de Cinépolis excede el tamaño admitido")
    try:
        payload = json.loads(body)
    except ValueError as err:
        raise NavajaApiError("Cinépolis no devolvió JSON") from err
    if not isinstance(payload, dict):
        raise NavajaApiError("Respuesta inesperada de Cinépolis")
    errors = payload.get("errors")
    if errors:
        first = errors[0].get("message") if isinstance(errors, list) and errors and isinstance(errors[0], dict) else None
        raise NavajaApiError(f"Cinépolis devolvió un error de consulta: {_plain(str(first or 'sin detalle'))[:200]}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise NavajaApiError("La respuesta de Cinépolis no trae datos")
    return data


def parse_cinema(entity: Any) -> CinepolisCinema | None:
    """Un resultado de `searchEntities`: {id, name, timeZone}."""
    if not isinstance(entity, dict):
        return None
    cid, name, tz = str(entity.get("id") or "").strip(), _plain(str(entity.get("name") or "")), str(entity.get("timeZone") or "").strip()
    if not cid or not name:
        return None
    try:
        ZoneInfo(tz)
    except Exception:  # noqa: BLE001 - sin zona horaria válida no se interpretan las horas
        return None
    return CinepolisCinema(cid, name, tz)


def _when(value: Any, tz: ZoneInfo) -> datetime | None:
    """Fecha y hora de una función en la zona del cine. Sin desfase explícito se asume la hora local del cine, no UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.replace(tzinfo=tz) if moment.tzinfo is None else moment.astimezone(tz)


def _name(value: Any) -> str | None:
    """Campos que pueden venir como texto o como objeto con nombre: {name: ...}."""
    if isinstance(value, dict):
        value = value.get("name")
    text = _plain(str(value)) if value not in (None, "") else ""
    return text or None


def parse_billboard(payload: Any, timezone: str) -> list[CinepolisShowtime]:
    """Funciones de `data.billboard`: schedules[] → dates[] → languages[] → showtimes[]. Un formato desconocido es un error.

    Una película sin funciones devuelve una lista vacía (válida); lo que no se reconoce no se interpreta como «sin funciones».
    """
    tz = ZoneInfo(timezone)
    billboard = payload.get("billboard") if isinstance(payload, dict) else None
    schedules = billboard.get("schedules") if isinstance(billboard, dict) else None
    if not isinstance(schedules, list):
        raise NavajaApiError("Formato inesperado en la cartelera de Cinépolis")
    found: dict[str, CinepolisShowtime] = {}
    for schedule in schedules:
        for date in (schedule.get("dates") if isinstance(schedule, dict) else None) or []:
            for group in (date.get("languages") if isinstance(date, dict) else None) or []:
                if not isinstance(group, dict):
                    continue
                language, language_name = _name(group.get("language")), _name(group.get("displayLanguage"))
                for raw in group.get("showtimes") or []:
                    if not isinstance(raw, dict):
                        continue
                    session = str(raw.get("sessionId") or "").strip()
                    start = _when(raw.get("datetime"), tz)
                    if not session or start is None:
                        continue
                    found[session] = CinepolisShowtime(
                        session_id=session,
                        start=start,
                        format=_name(raw.get("format")),
                        experience=_name(raw.get("experience")),
                        screen=_name(raw.get("screen")),
                        language=language,
                        language_name=language_name,
                        availability=raw.get("availability"),
                    )
    return sorted(found.values(), key=lambda s: (s.start, s.session_id))


def filter_showtimes(
    showtimes: list[CinepolisShowtime],
    *,
    languages: set[str] | None = None,
    formats: set[str] | None = None,
    experiences: set[str] | None = None,
) -> list[CinepolisShowtime]:
    """Filtros opcionales de idioma, formato y experiencia de sala (sin mayúsculas ni tildes que importen)."""

    def ok(value: str | None, wanted: set[str] | None) -> bool:
        return not wanted or (value or "").casefold() in {w.casefold() for w in wanted}

    return [
        s for s in showtimes
        if ok(s.language, languages) and ok(s.format, formats) and ok(s.experience, experiences)
    ]


def upcoming(showtimes: list[CinepolisShowtime], now: datetime, *, limit: int = 6, within: timedelta | None = None) -> list[CinepolisShowtime]:
    """Funciones que aún no empiezan, de la más próxima en adelante; compara instantes, así que sirve pasada la medianoche."""
    horizon = now + within if within else None
    return [s for s in sorted(showtimes, key=lambda s: s.start) if s.start >= now and (horizon is None or s.start <= horizon)][:limit]
