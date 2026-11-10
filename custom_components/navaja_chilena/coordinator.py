"""Coordinadores de actualización."""

from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo
from typing import Any, Awaitable, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api
from .const import (
    FOOTBALL_INTERVAL,
    FOOTBALL_LIVE_INTERVAL,
    FOOTBALL_SOON_INTERVAL,
    NATIONAL_COMPETITIONS,
    NATIONAL_INTERVAL,
    NATIONAL_TEAM_ID,
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
