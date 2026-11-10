"""Tren Limache–Puerto: próximos trenes de EFE Valparaíso.

Usa la misma fuente pública de «Próximos trenes» que la app de EFE, sin cuenta ni
claves. La API no está documentada para terceros y responde un par origen/destino
por consulta. Sin dependencias de Home Assistant para poder probarlo por separado.
"""

from __future__ import annotations

import json
import re
import ssl
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .api import HEADERS, NavajaApiError

# Opciones del asistente y frecuencia de consulta
CONF_TRAIN_TRIPS = "train_trips"
CONF_TRAIN_RETURN = "train_return"
TRAIN_URL = "https://ms4.metrovalparaiso.cl/"
TRAIN_INTERVAL = timedelta(minutes=1)
REQUEST_TIMEOUT = 15
MAX_RESPONSE_BYTES = 1_048_576
MAX_TRIPS = 8  # cada trayecto es una consulta por minuto a EFE: se limita para no cargarla de más

# EFE entrega solo el certificado de hoja. Se añade el intermedio público de
# GlobalSign para construir la cadena hasta las raíces de confianza. La
# verificación de cadena, vigencia y nombre sigue activa.
INTERMEDIATE_CERT = Path(__file__).parent / "certs" / "globalsign-r46-alphassl-2025.pem"

# IDs de estación de la API (1–21), en el orden de la línea, de Puerto a Limache.
STATIONS: dict[int, str] = {
    1: "Puerto",
    2: "Bellavista",
    3: "Francia",
    4: "Barón",
    5: "Portales",
    6: "Recreo",
    7: "Miramar",
    8: "Viña del Mar",
    9: "Hospital",
    10: "Chorrillos",
    11: "El Salto",
    12: "Valencia",
    13: "Quilpué",
    14: "El Sol",
    15: "El Belloto",
    16: "Las Américas",
    17: "La Concepción",
    18: "Villa Alemana",
    19: "Sargento Aldea",
    20: "Peñablanca",
    21: "Limache",
}

STATE_SERVICES = "servicios_informados"
STATE_NO_SERVICES = "sin_servicios_informados"

NOTICE = (
    "Respuesta de la API que usa la app EFE. Una lista vacía no garantiza "
    "que no haya trenes. No está confirmado que los tiempos sean en tiempo real."
)

_MINUTES_RE = re.compile(r"^\s*(\d{1,3})\s+minutos?\s*$", re.IGNORECASE)
_TRIP_SEP_RE = re.compile(r"\s*(?:>|→|->)\s*")


def create_ssl_context() -> ssl.SSLContext:
    """Contexto TLS con verificación completa. Bloqueante: usar en un executor."""
    try:
        import certifi  # incluido en Home Assistant

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    context.load_verify_locations(cafile=str(INTERMEDIATE_CERT))
    return context


def build_url(origin: int, destination: int) -> str:
    arg = json.dumps({"idOrigen": origin, "idDestino": destination}, separators=(",", ":"))
    return f"{TRAIN_URL}?{urlencode({'arg': arg})}"


def parse_minutes(tiempo: Any) -> int | None:
    """«6 minutos» → 6. Cualquier otro texto («cercano») → None, sin inventar."""
    if not isinstance(tiempo, str):
        return None
    match = _MINUTES_RE.match(tiempo)
    return int(match.group(1)) if match else None


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


_STATION_BY_NAME = {_normalize(name): sid for sid, name in STATIONS.items()}


def resolve_station(value: Any) -> int | None:
    """Estación por ID (1–21) o por nombre, sin importar tildes ni mayúsculas."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value in STATIONS else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text) if int(text) in STATIONS else None
        return _STATION_BY_NAME.get(_normalize(text))
    return None


def terminal_station(hasta: Any) -> int | None:
    """«Hasta Sargento Aldea» → 19. Texto desconocido → None."""
    if not isinstance(hasta, str):
        return None
    text = _normalize(hasta)
    if text.startswith("hasta "):
        text = text[len("hasta ") :]
    return _STATION_BY_NAME.get(text)


def reaches_destination(terminal: int | None, origin: int, destination: int) -> bool | None:
    """Si un tren que termina en `terminal` pasa por `destination` (None si no se reconoce)."""
    if terminal is None:
        return None
    if destination > origin:
        return terminal >= destination
    return terminal <= destination


def parse_trips(raw: str, with_return: bool = False) -> list[tuple[int, int]]:
    """«Villa Alemana > Puerto, Viña del Mar > Limache» → [(18, 1), (8, 21)].

    Separa los trayectos por coma o punto y coma, y origen y destino con «>».
    Con `with_return` agrega también el sentido inverso de cada uno. Elimina
    duplicados conservando el orden. Lanza ValueError con el trayecto inválido.
    """
    trips: list[tuple[int, int]] = []
    for part in re.split(r"[,;]", raw or ""):
        if not part.strip():
            continue
        names = _TRIP_SEP_RE.split(part.strip())
        if len(names) != 2:
            raise ValueError(part.strip())
        origin, destination = (resolve_station(n) for n in names)
        if origin is None or destination is None or origin == destination:
            raise ValueError(part.strip())
        for trip in ((origin, destination), (destination, origin)) if with_return else ((origin, destination),):
            if trip not in trips:
                trips.append(trip)
    if len(trips) > MAX_TRIPS:
        raise ValueError(f"máximo {MAX_TRIPS} trayectos")
    return trips


def format_trips(trips: list[tuple[int, int]]) -> str:
    return ", ".join(f"{STATIONS[o]} > {STATIONS[d]}" for o, d in trips)


@dataclass(frozen=True)
class Departures:
    """Respuesta validada de EFE para un par origen/destino."""

    origin: int
    destination: int
    services: list[dict[str, Any]]
    message: dict[str, Any]
    url: str
    fetched_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def state(self) -> str:
        return STATE_SERVICES if self.services else STATE_NO_SERVICES

    @property
    def warning(self) -> str | None:
        state = self.message.get("serviceState")
        if isinstance(state, dict):
            value = state.get("warningMessage")
            return value if isinstance(value, str) else None
        return None

    @property
    def operability(self) -> dict[str, Any] | None:
        value = self.message.get("operability")
        return value if isinstance(value, dict) else None


def parse_response(
    data: Any,
    url: str,
    origin: int,
    destination: int,
    fetched_at: datetime | None = None,
) -> Departures:
    """Valida la respuesta. Un cambio de formato es un error, no una lista vacía."""
    if not isinstance(data, dict) or data.get("status") != "OK":
        raise NavajaApiError("EFE devolvió un estado de error")
    obj = data.get("object")
    if not isinstance(obj, dict) or not isinstance(obj.get("servicios"), list):
        raise NavajaApiError("El formato de respuesta de EFE cambió")
    message = data.get("message")
    if not isinstance(message, dict):
        raise NavajaApiError("La respuesta de EFE no incluye su estado de servicio")
    services = []
    for item in obj["servicios"]:
        if not isinstance(item, dict):
            raise NavajaApiError("El formato de los servicios de EFE cambió")
        # Se conservan los campos tal como llegan. Lo que se agrega se deriva solo
        # de ellos: «minutos» si el texto es explícitamente «N minutos»; la hora
        # estimada es la hora de la consulta más esos minutos.
        minutes = parse_minutes(item.get("tiempo"))
        terminal = terminal_station(item.get("hasta"))
        services.append(
            {
                **item,
                "minutos": minutes,
                "hora_estimada": (
                    (fetched_at + timedelta(minutes=minutes)).isoformat(timespec="minutes")
                    if fetched_at is not None and minutes is not None
                    else None
                ),
                "estacion_final": STATIONS.get(terminal) if terminal else None,
                "llega_a_destino": reaches_destination(terminal, origin, destination),
            }
        )
    extra = {"estado": obj.get("estado")} if "estado" in obj else {}
    return Departures(origin, destination, services, message, url, fetched_at, extra)


async def fetch_departures(
    session: aiohttp.ClientSession,
    ssl_context: ssl.SSLContext,
    origin: int,
    destination: int,
    now: datetime | None = None,
) -> Departures:
    url = build_url(origin, destination)
    try:
        async with session.get(
            url,
            headers={**HEADERS, "Accept": "application/json"},
            ssl=ssl_context,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            body = await resp.content.read(MAX_RESPONSE_BYTES + 1)
    except aiohttp.ClientResponseError as err:
        raise NavajaApiError(f"EFE respondió HTTP {err.status}", err.status) from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise NavajaApiError(f"No fue posible conectar con EFE: {type(err).__name__}") from err
    if len(body) > MAX_RESPONSE_BYTES:
        raise NavajaApiError("La respuesta de EFE excede el tamaño admitido")
    try:
        data = json.loads(body)
    except ValueError as err:
        raise NavajaApiError("EFE no devolvió JSON válido") from err
    return parse_response(data, url, origin, destination, now)
