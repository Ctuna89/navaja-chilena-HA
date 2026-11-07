"""Navaja Chilena: indicadores económicos, Metro y paraderos de Chile."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import parse_stop_codes
from .const import CONF_INDICATORS, CONF_METRO, CONF_STOPS
from .coordinator import (
    NavajaCoordinator,
    indicators_coordinator,
    metro_coordinator,
    stops_coordinator,
)

PLATFORMS = [Platform.SENSOR]


@dataclass
class RuntimeData:
    indicators: NavajaCoordinator | None = None
    metro: NavajaCoordinator | None = None
    stops: NavajaCoordinator | None = None
    indicator_codes: list[str] = field(default_factory=list)


type NavajaConfigEntry = ConfigEntry[RuntimeData]


def _options(entry: ConfigEntry) -> dict:
    return {**entry.data, **entry.options}


async def async_setup_entry(hass: HomeAssistant, entry: NavajaConfigEntry) -> bool:
    opts = _options(entry)
    data = RuntimeData(indicator_codes=list(opts.get(CONF_INDICATORS, [])))

    if data.indicator_codes:
        data.indicators = indicators_coordinator(hass)
        await data.indicators.async_config_entry_first_refresh()
    if opts.get(CONF_METRO):
        data.metro = metro_coordinator(hass)
        await data.metro.async_config_entry_first_refresh()
    stops = parse_stop_codes(opts.get(CONF_STOPS, ""))
    if stops:
        data.stops = stops_coordinator(hass, stops)
        await data.stops.async_config_entry_first_refresh()

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: NavajaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NavajaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
