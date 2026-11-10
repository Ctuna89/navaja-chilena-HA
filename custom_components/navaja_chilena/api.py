"""Clientes para las APIs públicas usadas por la integración."""

from __future__ import annotations

import re
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    CRYPTO_URL,
    INDICATORS_FALLBACK_URL,
    INDICATORS_URL,
    IPSA_URL,
    METRO_URL,
    REQUEST_TIMEOUT,
    STOP_URL,
)

HEADERS = {"User-Agent": "NavajaChilena/2.1 (Home Assistant)"}

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
            url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
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


async def fetch_indicators(
    session: aiohttp.ClientSession, wanted: list[str] | None = None
) -> dict[str, Indicator]:
    """mindicador.cl; si cae o le faltan indicadores pedidos, completa con findic.cl."""
    result: dict[str, Indicator] = {}
    primary_error: NavajaApiError | None = None
    try:
        result = parse_indicators(await _get_json(session, INDICATORS_URL))
    except NavajaApiError as err:
        primary_error = err
    if primary_error or (wanted and any(code not in result for code in wanted)):
        try:
            extra = parse_indicators(await _get_json(session, INDICATORS_FALLBACK_URL))
            for code, ind in extra.items():
                result.setdefault(code, ind)
        except NavajaApiError:
            if primary_error:
                raise primary_error
    return result


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


KNOWN_LINES = {
    "l1": "Línea 1", "l2": "Línea 2", "l3": "Línea 3", "l4": "Línea 4",
    "l4a": "Línea 4A", "l5": "Línea 5", "l6": "Línea 6",
}


def parse_metro(data: Any) -> dict[str, MetroLine]:
    """Interpreta la respuesta de https://api.xor.cl/red/metro-network.

    La API solo lista en `lines` las líneas con incidentes; con `issues: false`
    llega `lines: []`. Por eso una línea ausente es operativa **únicamente** si
    la respuesta es válida (`api_status` OK y `issues` informado). Cualquier otra
    cosa lanza error y los sensores quedan no disponibles (jamás se supone
    "operativa" sin evidencia). Una línea listada con estado ilegible se
    considera con problemas (es preferible una falsa alarma a un falso normal).
    """
    if not isinstance(data, dict):
        raise NavajaApiError("Respuesta de Metro inesperada")
    if str(data.get("api_status", "")).upper() != "OK":
        raise NavajaApiError(f"La API del Metro informa estado {data.get('api_status')!r}")
    lines_raw = data.get("lines")
    if not isinstance(lines_raw, list):
        raise NavajaApiError("Respuesta de Metro sin lista de líneas")
    if not lines_raw and not isinstance(data.get("issues"), bool):
        raise NavajaApiError("Respuesta de Metro sin indicador de incidentes")

    result: dict[str, MetroLine] = {
        lid: MetroLine(id=lid, name=name, operational=True, message="Operativa")
        for lid, name in KNOWN_LINES.items()
    }
    for item in lines_raw:
        if not isinstance(item, dict) or "id" not in item:
            continue
        line_id = str(item["id"]).lower()
        stations = item.get("stations") or item.get("estaciones") or []
        problems: list[str] = []
        station_states: dict[str, bool] = {}
        for st in stations:
            if not isinstance(st, dict):
                continue
            ok, _ = _status_ok(st.get("status", st.get("estado")))
            st_name = str(st.get("name") or st.get("nombre") or st.get("id"))
            ok = bool(ok)  # estado ilegible = con problemas
            station_states[st_name] = ok
            if not ok:
                problems.append(st_name)
        line_ok, message = _status_ok(item.get("status", item.get("estado")))
        operational = (not problems) if station_states else bool(line_ok)
        if not operational and not message:
            message = f"{len(problems)} estación(es) con problemas" if problems else "Con problemas"
        if operational and not message:
            message = "Operativa"
        result[line_id] = MetroLine(
            id=line_id,
            name=str(item.get("name") or item.get("nombre") or KNOWN_LINES.get(line_id) or line_id.upper()),
            operational=operational,
            message=message,
            stations_with_issues=problems,
            stations=station_states,
        )
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

from .const import (  # noqa: E402
    AIR_URL,
    HOLIDAYS_URLS,
    PHARMACY_URL,
    QUAKES_CSN_URL,
    QUAKES_URL,
)


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


def parse_quakes_csn(data: Any) -> list[Quake]:
    """Centro Sismológico Nacional vía api.gael.cloud (sin coordenadas).

    La `Fecha` se entrega tal cual la publica el CSN (no se convierte).
    """
    if not isinstance(data, list):
        raise NavajaApiError("Respuesta de sismos (CSN) inesperada")
    out: list[Quake] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        mag = _num(item.get("Magnitud"))
        if mag is None:
            continue
        out.append(
            Quake(
                magnitude=mag,
                latitude=None,
                longitude=None,
                depth_km=_num(item.get("Profundidad")),
                reference=item.get("RefGeografica"),
                date=item.get("Fecha"),
            )
        )
    if not out:
        raise NavajaApiError("La respuesta del CSN no contiene sismos")
    out.sort(key=lambda q: q.date or "", reverse=True)
    return out


def parse_quakes_usgs(data: Any) -> list[Quake]:
    """GeoJSON de USGS (FDSN), solo sismos de Chile; con coordenadas."""
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise NavajaApiError("Respuesta de sismos (USGS) inesperada")
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
            when = datetime.fromtimestamp(props["time"] / 1000, ZoneInfo("UTC")).replace(
                microsecond=0
            ).isoformat()
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
        raise NavajaApiError("La respuesta de USGS no contiene sismos de Chile")
    quakes.sort(key=lambda q: q.date or "", reverse=True)
    return quakes


async def fetch_quakes(session: aiohttp.ClientSession) -> dict[str, list[Quake] | None]:
    """Consulta CSN y USGS por separado; falla solo si ambas fallan."""
    result: dict[str, list[Quake] | None] = {"csn": None, "usgs": None}
    errors: list[str] = []
    for key, url, parser in (
        ("csn", QUAKES_CSN_URL, parse_quakes_csn),
        ("usgs", QUAKES_URL, parse_quakes_usgs),
    ):
        try:
            result[key] = parser(await _get_json(session, url))
        except NavajaApiError as err:
            errors.append(str(err))
    if not any(result.values()):
        raise NavajaApiError("; ".join(errors))
    return result


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


# ----------------------------------------------------------------- Criptomonedas


@dataclass(frozen=True)
class CryptoPrice:
    market: str
    price: float
    change_24h_pct: float | None
    change_7d_pct: float | None
    volume_24h: float | None


def parse_crypto(market: str, data: Any) -> CryptoPrice:
    """Ticker de Buda.com; las variaciones vienen como fracción (-0.001 = -0,1 %)."""
    t = data.get("ticker") if isinstance(data, dict) else None
    if not isinstance(t, dict):
        raise NavajaApiError(f"Respuesta inesperada para {market}")

    def first(v: Any) -> float | None:
        return _num(v[0] if isinstance(v, list) and v else v)

    price = first(t.get("last_price"))
    if price is None:
        raise NavajaApiError(f"Sin precio para {market}")
    pct = lambda v: None if _num(v) is None else round(_num(v) * 100, 2)  # noqa: E731
    return CryptoPrice(
        market=market,
        price=price,
        change_24h_pct=pct(t.get("price_variation_24h")),
        change_7d_pct=pct(t.get("price_variation_7d")),
        volume_24h=first(t.get("volume")),
    )


async def fetch_crypto(session: aiohttp.ClientSession, markets: list[str]) -> dict[str, CryptoPrice]:
    out: dict[str, CryptoPrice] = {}
    errors: list[str] = []
    for m in markets:
        try:
            out[m] = parse_crypto(m, await _get_json(session, CRYPTO_URL.format(market=m)))
        except NavajaApiError as err:
            errors.append(str(err))
    if not out:
        raise NavajaApiError("; ".join(errors))
    return out


# ------------------------------------------------------------------ Bolsa (IPSA)


@dataclass(frozen=True)
class StockIndex:
    """Último cierre de un índice bursátil y variación respecto del cierre anterior."""

    code: str
    name: str
    unit: str
    value: float
    date: str
    previous_value: float | None
    previous_date: str | None

    @property
    def change(self) -> float | None:
        if self.previous_value is None:
            return None
        return round(self.value - self.previous_value, 2)

    @property
    def change_pct(self) -> float | None:
        if not self.previous_value:
            return None
        return round((self.value - self.previous_value) / self.previous_value * 100, 2)


def parse_stock_index(data: Any) -> StockIndex:
    """Interpreta la serie de findic.cl/api/ipsa (cierres diarios, más reciente primero)."""
    serie = data.get("serie") if isinstance(data, dict) else None
    if not isinstance(serie, list):
        raise NavajaApiError("Respuesta del IPSA inesperada")
    points: list[tuple[str, float]] = []
    for item in serie:
        if isinstance(item, dict) and _num(item.get("valor")) is not None and item.get("fecha"):
            points.append((str(item["fecha"])[:10], _num(item["valor"])))
    if not points:
        raise NavajaApiError("El IPSA no trae cierres")
    points.sort(reverse=True)  # fecha ISO: orden cronológico inverso
    prev = points[1] if len(points) > 1 else None
    return StockIndex(
        code=str(data.get("codigo", "ipsa")),
        name=str(data.get("nombre", "IPSA")),
        unit=str(data.get("unidad_medida", "Puntos")),
        value=points[0][1],
        date=points[0][0],
        previous_value=prev[1] if prev else None,
        previous_date=prev[0] if prev else None,
    )


async def fetch_ipsa(session: aiohttp.ClientSession) -> StockIndex:
    return parse_stock_index(await _get_json(session, IPSA_URL))
