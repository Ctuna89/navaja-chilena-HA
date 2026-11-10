"""Clientes para las APIs públicas usadas por la integración."""

from __future__ import annotations

import html as html_lib
import json
import math
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field, replace
from typing import Any

import aiohttp

from .const import (
    BENEFITS_MAX_PAGES,
    BENEFITS_PAUSE,
    BENEFITS_SITE,
    BENEFITS_URL,
    CINEMARK_THEATERS,
    CINEMARK_URL,
    CRYPTO_URL,
    EPHEMERIDES_CL_URL,
    EPHEMERIDES_URL,
    ESPN_LOCALE,
    ESPN_SOCCER,
    ESPN_STANDINGS_URL,
    FOOTBALL_LEAGUE_SLUG,
    FUEL_BRANDS_URL,
    FUEL_URL,
    INDICATORS_FALLBACK_URL,
    INDICATORS_URL,
    IPSA_URL,
    METRO_URL,
    REQUEST_TIMEOUT,
    STOP_URL,
)

HEADERS = {
    "User-Agent": "NavajaChilena/2.4 (https://github.com/Ctuna89/navaja-chilena-HA; integración de Home Assistant)"
}

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


async def _get_text(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(
            url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            resp.raise_for_status()
            return await resp.text()
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


# ----------------------------------------------------------------------- Cines


@dataclass(frozen=True)
class Screening:
    """Una función de cine."""

    title: str
    start: datetime  # hora local de Chile (con zona)
    screen: str | None
    video_format: str | None
    duration_min: int | None
    genre: str | None
    poster: str | None
    url: str | None

    @property
    def listing_day(self) -> date:
        """Día de cartelera: las funciones de trasnoche (antes de las 05:00) cuentan para el día anterior."""
        return listing_day(self.start)


def listing_day(moment: datetime) -> date:
    return (moment - timedelta(hours=5)).date()


@dataclass(frozen=True)
class Cinema:
    name: str
    screenings: list[Screening]


_LD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_START_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})")


def _duration_min(iso: Any) -> int | None:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", str(iso or ""))
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def parse_cinemark(html: str) -> Cinema:
    """Interpreta la página de un cine de cinemark.cl (schema.org MovieTheater).

    Cinemark serializa la hora como `2026-11-10T12:40:00.000Z-05:00`: el sufijo es
    erróneo y la hora escrita (12:40) es la hora local de Chile; no se convierte.
    """
    theater: dict | None = None
    for block in _LD_RE.findall(html):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "MovieTheater":
            theater = data
            break
    if theater is None:
        raise NavajaApiError("La página del cine no trae la cartelera")
    tz = ZoneInfo(METRO_TZ)
    screenings: list[Screening] = []
    for ev in theater.get("event") or []:
        if not isinstance(ev, dict):
            continue
        m = _START_RE.match(str(ev.get("startDate", "")))
        movie = ev.get("workPresented") or {}
        if not m or not movie.get("name"):
            continue
        year, month, day, hour, minute = map(int, m.groups())
        loc = str((ev.get("location") or {}).get("name") or "")
        screen = loc.rsplit(" - ", 1)[1] if " - " in loc else None
        screenings.append(
            Screening(
                title=str(movie["name"]).strip(),
                start=datetime(year, month, day, hour, minute, tzinfo=tz),
                screen=screen,
                video_format=ev.get("videoFormat") or None,
                duration_min=_duration_min(movie.get("duration")),
                genre=movie.get("genre") or None,
                poster=movie.get("image") or None,
                url=(ev.get("offers") or {}).get("url") or None,
            )
        )
    screenings.sort(key=lambda s: s.start)
    return Cinema(name=str(theater.get("name") or ""), screenings=screenings)


async def fetch_cinemark(session: aiohttp.ClientSession, slug: str) -> Cinema:
    return parse_cinemark(await _get_text(session, CINEMARK_URL.format(slug=slug)))


def nearest_theater(lat: float, lon: float) -> str:
    """Slug del cine Cinemark más cercano a unas coordenadas (distancia en línea recta)."""

    def dist(slug: str) -> float:
        _, _, tlat, tlon = CINEMARK_THEATERS[slug]
        p1, p2 = math.radians(lat), math.radians(tlat)
        a = (
            math.sin((p2 - p1) / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(math.radians(tlon - lon) / 2) ** 2
        )
        return 6371 * 2 * math.asin(math.sqrt(a))

    return min(CINEMARK_THEATERS, key=dist)


# ------------------------------------------------------------------ Efemérides

# Se filtra por texto y descripción corta de la página (no por el extracto, que
# arrastra falsos positivos como futbolistas uruguayos con "Chile" en la biografía).
_CHILE_RE = re.compile(
    r"\bchilen[oa]s?\b|\bChile\b|Santiago de Chile|Valpara[ií]so|La Moneda|Pinochet|"
    r"Salvador Allende|Arturo Prat|Bernardo O'Higgins|Punta Arenas|Rapa Nui|Isla de Pascua|"
    r"Guerra del Pac[ií]fico|Combate Naval de Iquique|Batalla de (?:Chacabuco|Maip[úu]|Rancagua)",
    re.I,
)
_KIND_ORDER = {"events": 0, "deaths": 1, "births": 2}
_KIND_LABEL = {"events": "suceso", "deaths": "fallecimiento", "births": "nacimiento"}


@dataclass(frozen=True)
class Ephemeris:
    year: int | None
    kind: str  # suceso | fallecimiento | nacimiento
    text: str
    title: str | None
    url: str | None


def _is_chilean(item: dict) -> bool:
    pages = [p for p in item.get("pages") or [] if isinstance(p, dict)]
    haystack = [str(item.get("text") or "")]
    for p in pages:
        haystack.append(str(p.get("description") or ""))
        title = str(p.get("title") or "")
        if title.endswith("_(Chile)") or title.endswith(" (Chile)"):
            return True
    return bool(_CHILE_RE.search(" ".join(haystack)))


def parse_ephemerides(data: Any) -> list[Ephemeris]:
    """Efemérides chilenas del feed «Un día como hoy» de Wikipedia.

    Orden: sucesos, fallecimientos y nacimientos; dentro de cada grupo, los más antiguos
    primero (suelen ser los más relevantes históricamente).
    """
    if not isinstance(data, dict) or not any(k in data for k in _KIND_ORDER):
        raise NavajaApiError("Respuesta de efemérides inesperada")
    found: list[tuple[int, int, Ephemeris]] = []
    for key, order in _KIND_ORDER.items():
        for item in data.get(key) or []:
            if not isinstance(item, dict) or not item.get("text") or not _is_chilean(item):
                continue
            page = next((p for p in item.get("pages") or [] if isinstance(p, dict)), {})
            year = item.get("year")
            found.append(
                (
                    order,
                    year if isinstance(year, int) else 9999,
                    Ephemeris(
                        year=year if isinstance(year, int) else None,
                        kind=_KIND_LABEL[key],
                        text=str(item["text"]).strip(),
                        title=(str(page.get("title") or "").replace("_", " ") or None),
                        url=((page.get("content_urls") or {}).get("desktop") or {}).get("page"),
                    ),
                )
            )
    found.sort(key=lambda t: (t[0], t[1]))
    return [e for _, _, e in found]


async def fetch_ephemerides(session: aiohttp.ClientSession, day: date) -> list[Ephemeris]:
    url = EPHEMERIDES_URL.format(month=day.month, day=day.day)
    return parse_ephemerides(await _get_json(session, url))


# ------------------------------------------------- Días significativos (efemerides.cl)

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
_ROW_RE = re.compile(
    r'<td class="t2">\s*(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóúñ]+)\s*</td>\s*<td class="t3">\s*<details>\s*'
    r"<summary>(.*?)</summary>\s*<p>(.*?)</p>",
    re.S,
)
_PAGE_MONTH_RE = re.compile(r"<title>[^<]*?-\s*([A-Za-zÁÉÍÓÚáéíóúñ]+)\s+(\d{4})\s*</title>")
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SignificantDay:
    """Un día significativo de Chile según efemerides.cl."""

    date: date
    title: str
    year: int | None  # año del hecho histórico, si el título lo trae "(1879)"
    description: str

    @property
    def kind(self) -> str:
        return "hecho histórico" if self.year else "día conmemorativo"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(_TAG_RE.sub("", text))).strip()


def parse_efemerides_cl(page: str) -> list[SignificantDay]:
    """Interpreta la página de efemerides.cl (solo trae el mes en curso, ya ordenado)."""
    header = _PAGE_MONTH_RE.search(page)
    if not header or header.group(1).lower() not in _MONTHS:
        raise NavajaApiError("efemerides.cl: no se reconoció el mes de la página")
    page_month, page_year = _MONTHS[header.group(1).lower()], int(header.group(2))
    days: list[SignificantDay] = []
    for dd, month_name, title, desc in _ROW_RE.findall(page):
        if _MONTHS.get(month_name.lower()) != page_month:
            continue
        try:
            when = date(page_year, page_month, int(dd))
        except ValueError:
            continue
        title = _clean(title)
        year_match = re.search(r"\((\d{4})\)\s*$", title)
        if not title:
            continue
        days.append(
            SignificantDay(
                date=when,
                title=re.sub(r"\s*\(\d{4}\)\s*$", "", title) if year_match else title,
                year=int(year_match.group(1)) if year_match else None,
                description=_clean(desc),
            )
        )
    if not days:
        raise NavajaApiError("efemerides.cl: la página no trae días significativos")
    return sorted(days, key=lambda d: d.date)


async def fetch_efemerides_cl(session: aiohttp.ClientSession) -> list[SignificantDay]:
    return parse_efemerides_cl(await _get_text(session, EPHEMERIDES_CL_URL))


# ------------------------------------------------------------------ Combustibles

FUEL_LABELS = {
    "93": "Gasolina 93",
    "95": "Gasolina 95",
    "97": "Gasolina 97",
    "DI": "Diésel",
}
# código de autoservicio y código de atención asistida (prefijo «A»)
_FUEL_CODES = {k: (k, "A" + k) for k in FUEL_LABELS}
PRICE_MIN, PRICE_MAX = 300.0, 5000.0   # $/L: fuera de este rango es un error de ingreso
PRICE_MAX_AGE_DAYS = 14                # por defecto, precios más antiguos no se consideran


@dataclass(frozen=True)
class FuelPrice:
    price: float
    updated: datetime | None
    attention: str  # "autoservicio" | "asistido"


@dataclass(frozen=True)
class Station:
    id: int
    brand: str
    address: str
    commune: str
    region: str
    lat: float
    lon: float
    logo: str | None
    prices: dict[str, FuelPrice]


@dataclass(frozen=True)
class FuelCandidate:
    station: Station
    price: FuelPrice
    distance_km: float


def _coord(value: Any) -> float | None:
    try:
        return float(str(value).strip().replace(",", "."))   # algunas vienen con coma decimal
    except ValueError:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _brand_name(raw: str) -> str:
    """COPEC -> Copec; las siglas cortas (JLC, HN) se dejan en mayúsculas."""
    name = raw.strip()
    return name.title() if name.isupper() and len(name) > 3 else name


def parse_brands(data: Any) -> dict[int, tuple[str, str | None]]:
    """id de marca -> (nombre, logo)."""
    out: dict[int, tuple[str, str | None]] = {}
    items = data.get("data") if isinstance(data, dict) else None
    for b in items or []:
        if isinstance(b, dict) and isinstance(b.get("id"), int) and b.get("nombre"):
            out[b["id"]] = (_brand_name(str(b["nombre"])), b.get("imagen") or b.get("logo") or None)
    return out


def _parse_updated(raw: Any) -> datetime | None:
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(METRO_TZ))
    except ValueError:
        return None


def parse_stations(data: Any, brands: dict[int, tuple[str, str | None]] | None = None) -> list[Station]:
    """Interpreta la respuesta de Bencina en Línea, descartando datos inválidos."""
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise NavajaApiError("Respuesta de combustibles inesperada")
    brands = brands or {}
    stations: list[Station] = []
    for e in items:
        if not isinstance(e, dict) or not e.get("gasolinera_bandera") or e.get("en_mantenimiento_bandera"):
            continue
        lat, lon = _coord(e.get("latitud")), _coord(e.get("longitud"))
        if lat is None or lon is None or not (-56 <= lat <= -17 and -110 <= lon <= -66):
            continue
        prices: dict[str, FuelPrice] = {}
        by_code = {c.get("nombre_corto"): c for c in e.get("combustibles") or [] if isinstance(c, dict)}
        for fuel, (self_service, assisted) in _FUEL_CODES.items():
            for code, attention in ((self_service, "autoservicio"), (assisted, "asistido")):
                c = by_code.get(code)
                price = _num(c.get("precio")) if c else None
                if c is None or not c.get("suministra") or price is None or not (PRICE_MIN <= price <= PRICE_MAX):
                    continue
                prices[fuel] = FuelPrice(price, _parse_updated(c.get("precio_fecha")), attention)
                break  # se prefiere autoservicio; si no hay, asistido
        if not prices:
            continue
        brand_name, brand_logo = brands.get(e.get("marca"), (f"Marca {e.get('marca')}", None))
        stations.append(
            Station(
                id=int(e.get("id", 0)),
                brand=brand_name,
                address=str(e.get("direccion") or "").strip().title(),
                commune=str(e.get("comuna") or "").strip(),
                region=str(e.get("region") or "").strip(),
                lat=lat,
                lon=lon,
                logo=e.get("logo") or brand_logo,
                prices=prices,
            )
        )
    if not stations:
        raise NavajaApiError("La respuesta no contiene estaciones con precios")
    return stations


def cheapest_nearby(
    stations: list[Station],
    fuel: str,
    lat: float,
    lon: float,
    radius_km: float,
    now: datetime,
    max_age_days: int = PRICE_MAX_AGE_DAYS,
) -> list[FuelCandidate]:
    """Estaciones en el radio con precio vigente de `fuel`, de la más barata a la más cara."""
    found: list[FuelCandidate] = []
    for s in stations:
        p = s.prices.get(fuel)
        if p is None or p.updated is None or (now - p.updated).days > max_age_days:
            continue
        dist = haversine_km(lat, lon, s.lat, s.lon)
        if dist <= radius_km:
            found.append(FuelCandidate(s, p, dist))
    return sorted(found, key=lambda c: (c.price.price, c.distance_km))


async def fetch_fuel(session: aiohttp.ClientSession, brands_cache: dict[int, tuple[str, str | None]]) -> list[Station]:
    """Descarga las estaciones; los nombres de marca se piden aparte y su falla no es grave."""
    if not brands_cache:
        try:
            brands_cache.update(parse_brands(await _get_json(session, FUEL_BRANDS_URL)))
        except NavajaApiError:
            pass
    return parse_stations(await _get_json(session, FUEL_URL), brands_cache)


# ----------------------------------------------------------------------- Fútbol


@dataclass(frozen=True)
class FootballTeam:
    id: str
    name: str
    abbr: str
    logo: str | None


@dataclass(frozen=True)
class Match:
    """Un partido (programado, en juego o terminado)."""

    id: str
    start: datetime  # UTC
    competition: str
    home: FootballTeam
    away: FootballTeam
    home_score: int | None
    away_score: int | None
    state: str  # "pre" | "in" | "post"
    status: str  # texto en español: «Agendado», «Tiempo Completo»…
    clock: str | None
    venue: str | None
    city: str | None

    @property
    def live(self) -> bool:
        return self.state == "in"

    @property
    def finished(self) -> bool:
        return self.state == "post"

    @property
    def score_text(self) -> str | None:
        if self.home_score is None or self.away_score is None:
            return None
        return f"{self.home_score}-{self.away_score}"

    def involves(self, team_id: str) -> bool:
        return team_id in (self.home.id, self.away.id)

    def is_home(self, team_id: str) -> bool:
        return self.home.id == team_id

    def opponent(self, team_id: str) -> FootballTeam:
        return self.away if self.is_home(team_id) else self.home

    def result_for(self, team_id: str) -> str | None:
        """«ganó», «empató» o «perdió» desde el punto de vista del equipo (si terminó)."""
        if not self.finished or self.home_score is None or self.away_score is None:
            return None
        mine, theirs = (
            (self.home_score, self.away_score) if self.is_home(team_id) else (self.away_score, self.home_score)
        )
        return "ganó" if mine > theirs else "empató" if mine == theirs else "perdió"


@dataclass(frozen=True)
class TableRow:
    rank: int
    team: FootballTeam
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    points: int

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against


def _score(raw: Any) -> int | None:
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("displayValue"))
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _team(raw: Any) -> FootballTeam | None:
    if not isinstance(raw, dict) or raw.get("id") is None:
        return None
    logos = raw.get("logos") or []
    logo = raw.get("logo") or (logos[0].get("href") if logos and isinstance(logos[0], dict) else None)
    name = str(raw.get("displayName") or raw.get("name") or raw.get("location") or "").strip()
    return FootballTeam(str(raw["id"]), name, str(raw.get("abbreviation") or name[:3].upper()), logo)


def parse_match(event: Any, competition: str | None = None) -> Match | None:
    """Interpreta un evento de ESPN; devuelve None si no se puede (datos incompletos)."""
    if not isinstance(event, dict):
        return None
    comp = (event.get("competitions") or [{}])[0]
    if not isinstance(comp, dict):
        return None
    home = away = None
    scores: dict[str, int | None] = {}
    for c in comp.get("competitors") or []:
        if not isinstance(c, dict):
            continue
        team = _team(c.get("team"))
        if c.get("homeAway") == "home":
            home, scores["home"] = team, _score(c.get("score"))
        elif c.get("homeAway") == "away":
            away, scores["away"] = team, _score(c.get("score"))
    try:
        start = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    if home is None or away is None:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=ZoneInfo("UTC"))
    status = event.get("status") or comp.get("status") or {}
    stype = status.get("type") or {}
    venue = comp.get("venue") or event.get("venue") or {}
    state = str(stype.get("state") or "pre")
    return Match(
        id=str(event.get("id", "")),
        start=start,
        competition=str((event.get("league") or {}).get("name") or competition or ""),
        home=home,
        away=away,
        home_score=scores.get("home") if state != "pre" else None,
        away_score=scores.get("away") if state != "pre" else None,
        state=state if state in ("pre", "in", "post") else "pre",
        status=str(stype.get("description") or stype.get("detail") or ""),
        clock=str(status.get("displayClock")) if state == "in" and status.get("displayClock") else None,
        venue=venue.get("fullName") or None,
        city=(venue.get("address") or {}).get("city") or None,
    )


def parse_matches(data: Any, competition: str | None = None) -> list[Match]:
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        raise NavajaApiError("Respuesta de partidos inesperada")
    return sorted(
        (m for m in (parse_match(e, competition) for e in events) if m is not None), key=lambda m: m.start
    )


def parse_calendar(data: Any) -> list[date]:
    """Fechas con partidos de la temporada (de la respuesta del scoreboard)."""
    try:
        raw = data["leagues"][0]["calendar"]
    except (KeyError, IndexError, TypeError):
        raise NavajaApiError("El calendario de la liga no viene en la respuesta") from None
    days: list[date] = []
    for item in raw:
        try:
            days.append(date.fromisoformat(str(item)[:10]))
        except ValueError:
            continue
    return sorted(set(days))


def matchday_dates(calendar: list[date], today: date, upcoming: bool, span_days: int = 3) -> list[date]:
    """Fechas de la próxima (o última) jornada: días consecutivos cercanos entre sí."""
    if upcoming:
        pool = [d for d in calendar if d >= today]
        if not pool:
            return []
        first = pool[0]
        return [d for d in pool if (d - first).days <= span_days]
    pool = [d for d in calendar if d < today]
    if not pool:
        return []
    last = pool[-1]
    return [d for d in pool if (last - d).days <= span_days]


def parse_standings(data: Any) -> list[TableRow]:
    try:
        entries = data["children"][0]["standings"]["entries"]
    except (KeyError, IndexError, TypeError):
        raise NavajaApiError("Respuesta de la tabla inesperada") from None
    rows: list[TableRow] = []
    for e in entries:
        team = _team(e.get("team")) if isinstance(e, dict) else None
        if team is None:
            continue
        stats = {s.get("name"): s for s in e.get("stats") or [] if isinstance(s, dict)}

        def num(name: str) -> int:
            s = stats.get(name) or {}
            return _score(s.get("value", s.get("displayValue"))) or 0

        rows.append(
            TableRow(
                rank=num("rank"),
                team=team,
                played=num("gamesPlayed"),
                wins=num("wins"),
                draws=num("ties"),
                losses=num("losses"),
                goals_for=num("pointsFor"),
                goals_against=num("pointsAgainst"),
                points=num("points"),
            )
        )
    if not rows:
        raise NavajaApiError("La tabla no trae equipos")
    return sorted(rows, key=lambda r: (r.rank or 99, -r.points))


def _espn_url(path: str, **params: str) -> str:
    extra = "".join(f"&{k}={v}" for k, v in params.items())
    return f"{ESPN_SOCCER}/{path}?{ESPN_LOCALE}{extra}"


async def _try(errors: list[str], coro: Any) -> Any:
    try:
        return await coro
    except NavajaApiError as err:
        errors.append(str(err))
        return None


async def fetch_football(
    session: aiohttp.ClientSession, team_id: str | None, league: bool, today: date
) -> dict[str, Any]:
    """Tabla, partidos del equipo y jornadas de la liga. Cada parte falla por separado."""
    out: dict[str, Any] = {
        "standings": None, "team_results": None, "team_fixtures": None,
        "league_last": None, "league_next": None,
    }
    errors: list[str] = []
    if team_id or league:
        out["standings"] = await _try(errors, _fetch_standings(session))
    if team_id:
        out["team_results"] = await _try(errors, _fetch_team(session, team_id, False))
        out["team_fixtures"] = await _try(errors, _fetch_team(session, team_id, True))
    if league:
        cal = await _try(errors, _fetch_calendar(session))
        if cal is not None:
            for key, upcoming in (("league_next", True), ("league_last", False)):
                days = matchday_dates(cal, today, upcoming)
                matches: list[Match] = []
                ok = True
                for d in days:
                    part = await _try(errors, _fetch_day(session, d))
                    if part is None:
                        ok = False
                    else:
                        matches += part
                if ok:
                    out[key] = sorted(matches, key=lambda m: m.start)
    if all(v is None for v in out.values()):
        raise NavajaApiError("; ".join(errors) or "sin datos de fútbol")
    return out


async def _fetch_standings(session: aiohttp.ClientSession) -> list[TableRow]:
    return parse_standings(await _get_json(session, f"{ESPN_STANDINGS_URL}?{ESPN_LOCALE}"))


async def _fetch_team(session: aiohttp.ClientSession, team_id: str, fixtures: bool) -> list[Match]:
    extra = {"fixture": "true"} if fixtures else {}
    matches = parse_matches(
        await _get_json(session, _espn_url(f"{FOOTBALL_LEAGUE_SLUG}/teams/{team_id}/schedule", **extra))
    )
    return matches if fixtures else sorted(matches, key=lambda m: m.start, reverse=True)


async def _fetch_calendar(session: aiohttp.ClientSession) -> list[date]:
    return parse_calendar(await _get_json(session, _espn_url(f"{FOOTBALL_LEAGUE_SLUG}/scoreboard")))


async def _fetch_day(session: aiohttp.ClientSession, day: date) -> list[Match]:
    return parse_matches(
        await _get_json(session, _espn_url(f"{FOOTBALL_LEAGUE_SLUG}/scoreboard", dates=f"{day:%Y%m%d}"))
    )


async def fetch_national(session: aiohttp.ClientSession, team_id: str, competitions: tuple[str, ...]) -> dict[str, Any]:
    """Partidos de la selección en todas sus competencias (amistosos, eliminatorias, Copa)."""
    results: list[Match] = []
    fixtures: list[Match] = []
    errors: list[str] = []
    answered = 0
    for slug in competitions:
        for fixture in (False, True):
            extra = {"fixture": "true"} if fixture else {}
            data = await _try(errors, _get_json(session, _espn_url(f"{slug}/teams/{team_id}/schedule", **extra)))
            if data is None:
                continue
            try:
                found = parse_matches(data)
            except NavajaApiError as err:
                errors.append(str(err))
                continue
            answered += 1
            (fixtures if fixture else results).extend(found)
    if not answered:
        raise NavajaApiError("; ".join(errors) or "sin datos de la selección")
    seen: set[str] = set()

    def unique(items: list[Match]) -> list[Match]:
        out = []
        for m in items:
            if m.id not in seen:
                seen.add(m.id)
                out.append(m)
        return out

    return {
        "results": sorted(unique(results), key=lambda m: m.start, reverse=True),
        "fixtures": sorted(unique(fixtures), key=lambda m: m.start),
    }


def all_matches(data: Any) -> list[Match]:
    """Todos los partidos de una respuesta de fetch_* (para decidir la frecuencia de consulta)."""
    found: list[Match] = []
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                found += [m for m in value if isinstance(m, Match)]
    return found


# ------------------------------------------------- Beneficios de tarjetas

DAY_NAMES = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
_ALL_DAYS = frozenset(range(7))
_DAY_RE = r"(lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)"


@dataclass(frozen=True)
class Benefit:
    id: str
    card: str
    category: str
    merchant: str
    title: str
    detail: str
    url: str
    image: str | None
    days: frozenset[int] | None   # None: el texto no indica días
    months: frozenset[int] | None = None   # None: el texto no limita a meses
    until: date | None = None              # fin de vigencia, si el texto lo indica

    def applies_on(self, weekday: int, month: int | None = None, today: date | None = None) -> bool | None:
        """True/False si el texto indica los días; None si no los indica."""
        if today is not None and self.until is not None and today > self.until:
            return False
        if month is not None and self.months is not None and month not in self.months:
            return False
        return None if self.days is None else weekday in self.days


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _day_index(name: str) -> int:
    if name not in DAY_NAMES:
        name = name[:-1]   # sábados, domingos
    return DAY_NAMES.index(name)


def _days_in(text: str) -> set[int]:
    days: set[int] = set()
    for m in re.finditer(rf"{_DAY_RE}\s*(?:a|al|hasta(?: el)?)\s*{_DAY_RE}", text):
        a, b = _day_index(m.group(1)), _day_index(m.group(2))
        days.update(range(a, b + 1) if a <= b else [*range(a, 7), *range(0, b + 1)])
    for m in re.finditer(_DAY_RE, text):
        days.add(_day_index(m.group(1)))
    if re.search(r"fin(?:es)? de semana", text):
        days.update({5, 6})
    return days


def parse_days(text: str) -> frozenset[int] | None:
    """Días de la semana en que aplica un beneficio, según su texto (lunes=0).

    Devuelve None cuando el texto no menciona días (no se asume nada).
    """
    t = _fold(text)
    exclusion = re.search(r"\b(?:excepto|salvo|menos|exceptuando)\b(.*)", t)
    base, excluded = (t[: exclusion.start()], _days_in(exclusion.group(1))) if exclusion else (t, set())
    days = _days_in(base)
    if not days and re.search(r"todos? los dias|toda la semana|cualquier dia|diari[oa]", base):
        days = set(_ALL_DAYS)
    if not days and excluded:
        days = set(_ALL_DAYS)
    days -= excluded
    return frozenset(days) if days else None


MONTH_NAMES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def parse_months(text: str) -> frozenset[int] | None:
    """Meses que limitan el beneficio ("los sábados de enero"); None si no los hay."""
    t = _fold(text)
    found = {
        MONTH_NAMES.index(m.group(1)) + 1
        for m in re.finditer(rf"\b(?:de|en|del)\s+({'|'.join(MONTH_NAMES)})\b", t)
    }
    return frozenset(found) if found else None


def parse_until(text: str) -> date | None:
    """Fin de vigencia: «válida hasta el 31 de diciembre de 2026» o «del 01 al 30 de noviembre de 2026»."""
    t = _fold(text)
    months = "|".join(MONTH_NAMES)
    m = re.search(rf"(?:hasta(?: el)?|al)\s+(\d{{1,2}})\s+de\s+({months})\s+de\s+(\d{{4}})", t)
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTH_NAMES.index(m.group(2)) + 1, int(m.group(1)))
    except ValueError:
        return None


_CARD_SPLIT = re.compile(r'<div class="img-card-corner">')


def _clean(raw: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def parse_benefits(page: str) -> list[Benefit]:
    """Lee los beneficios de una página de listado de N Beneficios."""
    found: list[Benefit] = []
    for block in _CARD_SPLIT.split(page)[1:]:
        link = re.search(r'href="(/beneficios/ver/(\d+)/[^"]*)"', block)
        title = re.search(r'<h6 class="black black-title">(.*?)</h6>', block, re.S)
        if not link or not title:
            continue
        card_name = _clean(block.split("</div>", 1)[0])
        category = re.search(r'btn btn-primary[^"]*">(.*?)</div>', block, re.S)
        merchant = re.search(r'<h6 class="primary-color[^"]*">(.*?)</h6>', block, re.S)
        detail = re.search(r'card-subtitle">(.*?)</p>', block, re.S)
        image = re.search(r'data-original="([^"]+)"', block)
        title_t = _clean(title.group(1))
        detail_t = _clean(detail.group(1)) if detail else ""
        found.append(
            Benefit(
                id=link.group(2),
                card=card_name,
                category=_clean(category.group(1)) if category else "",
                merchant=_clean(merchant.group(1)) if merchant else "",
                title=title_t,
                detail=detail_t,
                url=BENEFITS_SITE.rstrip("/") + link.group(1),
                image=image.group(1) if image else None,
                days=parse_days(f"{detail_t} {title_t}"),
                months=parse_months(f"{detail_t} {title_t}"),
                until=parse_until(detail_t),
            )
        )
    return found


def benefits_page_count(page: str) -> int:
    m = re.search(r"P[aá]gina\s+\d+\s+de\s+(\d+)", page)
    return max(1, int(m.group(1))) if m else 1


async def fetch_benefits(
    session: aiohttp.ClientSession, cards: list[str], categories: list[str], pause: float | None = None
) -> tuple[list[Benefit], bool]:
    """Beneficios de las categorías y tarjetas elegidas (una consulta por combinación y página).

    Devuelve (beneficios, completo): completo es False si alguna consulta falló."""
    import asyncio

    pause = BENEFITS_PAUSE if pause is None else pause
    by_id: dict[str, Benefit] = {}
    errors: list[str] = []
    answered = 0
    first = True
    for category in categories:
        for card in cards:
            page_no, pages = 1, 1
            while page_no <= min(pages, BENEFITS_MAX_PAGES):
                if not first:
                    await asyncio.sleep(pause)
                first = False
                url = f"{BENEFITS_URL.format(category=category)}?tarjeta={card}&page={page_no}"
                try:
                    page = await _get_text(session, url)
                except NavajaApiError as err:
                    errors.append(str(err))
                    break
                answered += 1
                if page_no == 1:
                    pages = benefits_page_count(page)
                for b in parse_benefits(page):
                    # La categoría queda con el identificador pedido (no el rótulo del sitio).
                    by_id.setdefault(f"{category}:{b.id}", replace(b, category=category))
                page_no += 1
    if not answered:
        raise NavajaApiError("; ".join(errors[:1]) or "N Beneficios no respondió")
    return list(by_id.values()), not errors


def benefits_due(fetched: datetime | None, today: date, refresh_days: int = 7) -> bool:
    """Toca descargar: pasaron `refresh_days` desde la última vez, o hoy es día 1 y aún no se hizo hoy."""
    if fetched is None:
        return True
    last = fetched.date()
    if (today - last).days >= refresh_days:
        return True
    return today.day == 1 and last < today


def benefit_to_dict(b: Benefit) -> dict[str, Any]:
    return {
        "id": b.id, "card": b.card, "category": b.category, "merchant": b.merchant, "title": b.title,
        "detail": b.detail, "url": b.url, "image": b.image,
        "days": None if b.days is None else sorted(b.days),
        "months": None if b.months is None else sorted(b.months),
        "until": b.until.isoformat() if b.until else None,
    }


def benefit_from_dict(d: dict[str, Any]) -> Benefit:
    days, months = d.get("days"), d.get("months")
    return Benefit(
        id=str(d["id"]), card=d.get("card", ""), category=d.get("category", ""), merchant=d.get("merchant", ""),
        title=d.get("title", ""), detail=d.get("detail", ""), url=d.get("url", ""), image=d.get("image"),
        days=None if days is None else frozenset(int(x) for x in days),
        months=None if months is None else frozenset(int(x) for x in months),
        until=date.fromisoformat(d["until"]) if d.get("until") else None,
    )
