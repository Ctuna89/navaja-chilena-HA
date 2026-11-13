"""Coordinadores de actualización."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import timedelta
from zoneinfo import ZoneInfo
from typing import Any, Awaitable, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.helpers.storage import Store

from . import api
from .const import (
    BENEFITS_INTERVAL,
    EVENTS_INTERVAL,
    VAMOH_INTERVAL,
    VAMOH_PAGE_PAUSE,
    VAMOH_STALE_MAX,
    VAMOH_WEB_INTERVAL,
    VAMOH_WEB_MAX_PAGES,
    NEWS_COOP_MIN_AGE,
    NEWS_INTERVAL,
    REGIONAL_INTERVAL,
    REGIONAL_NAMES_REFETCH,
    FUEL_DISCOUNTS_INTERVAL,
    BENEFITS_REFRESH_DAYS,
    BENEFITS_STORE_VERSION,
    FOOTBALL_INTERVAL,
    FOOTBALL_LIVE_INTERVAL,
    FOOTBALL_SOON_INTERVAL,
    NATIONAL_COMPETITIONS,
    NATIONAL_INTERVAL,
    NATIONAL_TEAM_ID,
    EV_INTERVAL,
    FUEL_INTERVAL,
    CINEMA_INTERVAL,
    BOLSA_INTERVAL,
    CRYPTO_INTERVAL,
    EPHEMERIDES_INTERVAL,
    CRYPTO_MARKETS,
    DOMAIN,
    INDICATORS_INTERVAL,
    METRO_INTERVAL,
    STOPS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

MAX_BACKOFF = timedelta(minutes=30)


class NavajaCoordinator(DataUpdateCoordinator[Any]):
    """Coordinador genérico: ejecuta `fetch(session)` periódicamente."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        interval: timedelta,
        fetch: Callable[[Any], Awaitable[Any]],
        interval_fn: Callable[[Any], timedelta | None] | None = None,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_{name}", update_interval=interval
        )
        self._fetch = fetch
        self._base_interval = interval
        self._interval_fn = interval_fn   # frecuencia según los datos (p. ej. partido en juego)

    async def _async_update_data(self) -> Any:
        # Con la fuente caída se consulta cada vez menos (hasta 30 min); el
        # coordinador de HA registra el fallo una vez y avisa al recuperarse.
        try:
            data = await self._fetch(async_get_clientsession(self.hass))
        except api.NavajaApiError as err:
            cap = max(self._base_interval, MAX_BACKOFF)
            self.update_interval = min((self.update_interval or cap) * 2, cap)
            raise UpdateFailed(str(err)) from err
        hint = self._interval_fn(data) if self._interval_fn else None
        self.update_interval = hint or self._base_interval
        return data


def indicators_coordinator(hass: HomeAssistant, codes: list[str]) -> NavajaCoordinator:
    async def fetch(session: Any) -> dict[str, api.Indicator]:
        return await api.fetch_indicators(session, codes)

    return NavajaCoordinator(hass, "indicadores", INDICATORS_INTERVAL, fetch)


def crypto_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    async def fetch(session: Any) -> dict[str, api.CryptoPrice]:
        return await api.fetch_crypto(session, list(CRYPTO_MARKETS))

    return NavajaCoordinator(hass, "cripto", CRYPTO_INTERVAL, fetch)


def metro_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    return NavajaCoordinator(hass, "metro", METRO_INTERVAL, api.fetch_metro)


def stops_coordinator(hass: HomeAssistant, codes: list[str]) -> NavajaCoordinator:
    """Consulta todos los paraderos; si uno falla, conserva el resto."""

    async def fetch(session: Any) -> dict[str, api.StopInfo]:
        result: dict[str, api.StopInfo] = {}
        errors: list[str] = []
        for code in codes:
            try:
                result[code] = await api.fetch_stop(session, code)
            except api.NavajaApiError as err:
                errors.append(f"{code}: {err}")
        if not result:
            raise api.NavajaApiError("; ".join(errors) or "sin datos")
        if errors:
            _LOGGER.warning("Paraderos con error: %s", "; ".join(errors))
        return result

    return NavajaCoordinator(hass, "paraderos", STOPS_INTERVAL, fetch)


# ------------------------------------------------------------ Módulos extra
from homeassistant.util import dt as dt_util  # noqa: E402

from .const import (  # noqa: E402
    AIR_INTERVAL,
    HOLIDAYS_INTERVAL,
    HOLIDAYS_REFETCH,
    PHARMACY_INTERVAL,
    QUAKES_INTERVAL,
)


def quakes_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    return NavajaCoordinator(hass, "sismos", QUAKES_INTERVAL, api.fetch_quakes)


def air_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    async def fetch(session: Any) -> api.AirQuality:
        return await api.fetch_air(session, hass.config.latitude, hass.config.longitude)

    return NavajaCoordinator(hass, "aire", AIR_INTERVAL, fetch)


def pharmacy_coordinator(hass: HomeAssistant, comuna: str) -> NavajaCoordinator:
    async def fetch(session: Any) -> list[api.Pharmacy]:
        return await api.fetch_pharmacies(session, comuna)

    return NavajaCoordinator(hass, "farmacias", PHARMACY_INTERVAL, fetch)


def holidays_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    """Descarga feriados del año actual y siguiente (cacheados 12 h).

    El coordinador corre cada hora solo para recalcular "próximo feriado".
    """
    cache: dict[str, Any] = {"at": None, "year": None, "data": []}

    async def fetch(session: Any) -> dict[str, Any]:
        now = dt_util.now()
        stale = (
            cache["at"] is None
            or cache["year"] != now.year
            or now - cache["at"] > HOLIDAYS_REFETCH
        )
        if stale:
            data = await api.fetch_holidays(session, now.year)
            try:
                data += await api.fetch_holidays(session, now.year + 1)
            except api.NavajaApiError:
                pass  # el año siguiente suele publicarse tarde
            cache.update(at=now, year=now.year, data=data)
        today = now.date()
        nxt = api.next_holiday(cache["data"], today)
        return {
            "next": nxt,
            "today": today,
            "is_holiday_today": bool(nxt and nxt.date == today),
            "all": frozenset(h.date for h in cache["data"]),
        }

    return NavajaCoordinator(hass, "feriados", HOLIDAYS_INTERVAL, fetch)


def bolsa_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    return NavajaCoordinator(hass, "bolsa", BOLSA_INTERVAL, api.fetch_ipsa)


def cinema_coordinator(hass: HomeAssistant, slug: str) -> NavajaCoordinator:
    async def fetch(session: Any) -> api.Cinema:
        return await api.fetch_cinemark(session, slug)

    return NavajaCoordinator(hass, "cine", CINEMA_INTERVAL, fetch)


def ephemerides_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    """efemerides.cl (días significativos de Chile) + Wikipedia (complemento).

    Cada fuente se consulta una sola vez al día; si una falla, la otra sigue
    sirviendo y la fallida se reintenta en el próximo ciclo (cada hora).
    """
    cache: dict[str, Any] = {"day": None, "cl": None, "wiki": None}

    async def fetch(session: Any) -> dict[str, Any]:
        today = dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)).date()
        if cache["day"] != today:  # día nuevo: lo cacheado ya no sirve
            cache.update(day=today, cl=None, wiki=None)
        errors: list[str] = []
        for key in ("cl", "wiki"):
            if cache[key] is not None:
                continue
            try:
                if key == "cl":
                    cache[key] = await api.fetch_efemerides_cl(session)
                else:
                    cache[key] = await api.fetch_ephemerides(session, today)
            except api.NavajaApiError as err:
                errors.append(f"{key}: {err}")
        if cache["cl"] is None and cache["wiki"] is None:
            raise api.NavajaApiError("; ".join(errors))
        if errors:
            _LOGGER.debug("Efemérides: fuente con error (%s)", "; ".join(errors))
        return {"day": today, "cl": cache["cl"], "wiki": cache["wiki"]}

    return NavajaCoordinator(hass, "efemerides", EPHEMERIDES_INTERVAL, fetch)


def ev_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    async def fetch(session: Any) -> list[api.EvStation]:
        return await api.fetch_ev_stations(session)

    return NavajaCoordinator(hass, "cargadores_electricos", EV_INTERVAL, fetch)


def fuel_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    brands: dict[int, tuple[str, str | None]] = {}

    async def fetch(session: Any) -> list[api.Station]:
        return await api.fetch_fuel(session, brands)

    return NavajaCoordinator(hass, "combustibles", FUEL_INTERVAL, fetch)


def _football_interval(data: Any) -> timedelta | None:
    """Más seguido cuando hay un partido en juego o por empezar; si no, la frecuencia normal."""
    matches = api.all_matches(data)
    if any(m.live for m in matches):
        return FOOTBALL_LIVE_INTERVAL
    now = dt_util.utcnow()
    if any(m.state == "pre" and timedelta(0) <= m.start - now <= timedelta(hours=3) for m in matches):
        return FOOTBALL_SOON_INTERVAL
    return None


def football_coordinator(hass: HomeAssistant, team_id: str | None, league: bool) -> NavajaCoordinator:
    async def fetch(session: Any) -> dict[str, Any]:
        today = dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)).date()
        return await api.fetch_football(session, team_id, league, today)

    return NavajaCoordinator(hass, "futbol", FOOTBALL_INTERVAL, fetch, _football_interval)


def national_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    async def fetch(session: Any) -> dict[str, Any]:
        return await api.fetch_national(session, NATIONAL_TEAM_ID, NATIONAL_COMPETITIONS)

    return NavajaCoordinator(hass, "seleccion", NATIONAL_INTERVAL, fetch, _football_interval)


def benefits_coordinator(hass: HomeAssistant, cards: list[str], categories: list[str]) -> NavajaCoordinator:
    """Beneficios de tarjetas: descarga cada 7 días y el día 1 de cada mes.

    El coordinador solo revisa si toca; lo descargado se guarda en disco para no
    volver a consultar el sitio al reiniciar Home Assistant.
    """
    store: Store = Store(hass, BENEFITS_STORE_VERSION, f"{DOMAIN}_beneficios")
    signature = {"cards": sorted(cards), "categories": sorted(categories)}
    state: dict[str, Any] = {"items": None, "fetched": None, "loaded": False}

    async def load() -> None:
        state["loaded"] = True
        stored = await store.async_load()
        if not isinstance(stored, dict) or stored.get("signature") != signature:
            return
        try:
            state["items"] = [api.benefit_from_dict(d) for d in stored["items"]]
            state["fetched"] = dt_util.parse_datetime(stored["fetched"])
        except (KeyError, TypeError, ValueError):
            state["items"], state["fetched"] = None, None

    async def fetch(session: Any) -> list[api.Benefit]:
        if not state["loaded"]:
            await load()
        now = dt_util.now()
        today = now.astimezone(ZoneInfo(api.METRO_TZ)).date()
        if state["items"] is not None and not api.benefits_due(state["fetched"], today, BENEFITS_REFRESH_DAYS):
            return state["items"]
        try:
            items, complete = await api.fetch_benefits(session, cards, categories)
        except api.NavajaApiError:
            if state["items"] is not None:   # fuente caída: se sigue con lo último descargado
                _LOGGER.debug("N Beneficios no respondió; se mantienen los datos anteriores")
                return state["items"]
            raise
        state["items"] = items
        if complete:
            state["fetched"] = now
            await store.async_save(
                {
                    "signature": signature,
                    "fetched": now.isoformat(),
                    "items": [api.benefit_to_dict(b) for b in items],
                }
            )
        return items

    return NavajaCoordinator(hass, "beneficios", BENEFITS_INTERVAL, fetch)


def fuel_discounts_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    async def fetch(session: Any) -> api.FuelDiscountCalendar:
        return await api.fetch_fuel_discounts(session)

    return NavajaCoordinator(hass, "descuentos_bencina", FUEL_DISCOUNTS_INTERVAL, fetch)


def regional_coordinator(hass: HomeAssistant, zone: str, codes: list[str]) -> NavajaCoordinator:
    """Paraderos de la Red Regional: llegadas en vivo y alertas. Cada paradero falla por separado."""
    import uuid

    phone_id = str(uuid.uuid4())   # identificador anónimo que el servicio exige; se genera por instalación
    names: dict[str, str] = {}
    state: dict[str, Any] = {"names_at": None}

    async def fetch(session: Any) -> dict[str, api.RegionalStop]:
        now = dt_util.utcnow()
        stale = state["names_at"] is None or now - state["names_at"] > REGIONAL_NAMES_REFETCH
        if stale:
            try:
                names.update(await api.fetch_regional_stop_names(session, zone))
                state["names_at"] = now
            except api.NavajaApiError as err:   # el nombre es opcional: se usa el código
                _LOGGER.debug("Red Regional: sin nombres de paraderos (%s)", err)
        result: dict[str, api.RegionalStop] = {}
        errors: list[str] = []
        for code in codes:
            try:
                result[code] = await api.fetch_regional_stop(session, zone, code, names.get(code, code), phone_id, now)
            except api.NavajaApiError as err:
                errors.append(f"{code}: {err}")
        if not result:
            raise api.NavajaApiError("; ".join(errors) or "sin datos")
        return result

    return NavajaCoordinator(hass, "red_regional", REGIONAL_INTERVAL, fetch)


def news_coordinator(hass: HomeAssistant, topics: list[str], count: int) -> NavajaCoordinator:
    cache: dict[str, Any] = {}   # Cooperativa: no se vuelve a descargar antes de una hora

    async def fetch(session: Any) -> dict[str, list[api.NewsItem]]:
        return await api.fetch_news(session, topics, count, cache, dt_util.utcnow(), NEWS_COOP_MIN_AGE)

    return NavajaCoordinator(hass, "noticias", NEWS_INTERVAL, fetch)


def culture_coordinator(hass: HomeAssistant, commune: str) -> NavajaCoordinator:
    """Agenda cultural de una comuna (Chile Cultura): cada 6 horas."""

    async def fetch(session: Any) -> list[api.CultureEvent]:
        today = dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)).date()
        return await api.fetch_culture_events(session, commune, today)

    return NavajaCoordinator(hass, "cultura", EVENTS_INTERVAL, fetch)


def arena_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    async def fetch(session: Any) -> list[api.ArenaEvent]:
        return await api.fetch_arena_events(session)

    return NavajaCoordinator(hass, "claro_arena", EVENTS_INTERVAL, fetch)


def vamoh_web_coordinator(hass: HomeAssistant, region: str, category: str | None) -> NavajaCoordinator:
    """Panoramas por Vamoh desde sus páginas de listado: una consulta por hora. Si falla, se conserva el último resultado bueno."""
    state: dict[str, Any] = {"listing": None}

    async def fetch(session: Any) -> api.VamohListing:
        now = dt_util.now()
        try:
            listing = await api.fetch_vamoh_listing(session, region, category, VAMOH_WEB_MAX_PAGES, now, VAMOH_PAGE_PAUSE)
        except api.NavajaApiError as err:
            previous = state["listing"]
            if previous is not None and now - previous.updated <= VAMOH_STALE_MAX:
                _LOGGER.debug("Vamoh no respondió; se conserva el resultado del %s: %s", previous.updated, err)
                return replace(previous, error=str(err))
            raise
        state["listing"] = listing
        return listing

    return NavajaCoordinator(hass, "vamoh_web", VAMOH_WEB_INTERVAL, fetch)


def vamoh_coordinator(hass: HomeAssistant, url: str) -> NavajaCoordinator:
    """Calendario de Panoramas por Vamoh: cada 6 horas, con ETag para no descargar lo que no cambió."""
    state: dict[str, Any] = {"etag": None, "modified": None, "events": None}

    async def fetch(session: Any) -> list[api.VamohEvent]:
        events, etag, modified = await api.fetch_vamoh_calendar(session, url, state["etag"], state["modified"])
        if events is None:           # 304: sin cambios
            return state["events"] if state["events"] is not None else []
        state.update(events=events, etag=etag, modified=modified)
        return events

    return NavajaCoordinator(hass, "vamoh", VAMOH_INTERVAL, fetch)
