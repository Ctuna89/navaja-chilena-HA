"""Coordinadores de actualización."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api
from .const import DOMAIN, INDICATORS_INTERVAL, METRO_INTERVAL, STOPS_INTERVAL

_LOGGER = logging.getLogger(__name__)


class NavajaCoordinator(DataUpdateCoordinator[Any]):
    """Coordinador genérico: ejecuta `fetch(session)` periódicamente."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        interval: timedelta,
        fetch: Callable[[Any], Awaitable[Any]],
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_{name}", update_interval=interval
        )
        self._fetch = fetch

    async def _async_update_data(self) -> Any:
        try:
            return await self._fetch(async_get_clientsession(self.hass))
        except api.NavajaApiError as err:
            raise UpdateFailed(str(err)) from err


def indicators_coordinator(hass: HomeAssistant) -> NavajaCoordinator:
    return NavajaCoordinator(hass, "indicadores", INDICATORS_INTERVAL, api.fetch_indicators)


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
