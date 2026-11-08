"""Navaja Chilena: indicadores económicos, Metro y paraderos de Chile."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import parse_stop_codes
from .const import (
    DEFAULT_INDICATORS,
    CONF_AIR,
    CONF_HOLIDAYS,
    CONF_INDICATORS,
    CONF_METRO,
    CONF_PHARMACY_COMUNA,
    CONF_QUAKES,
    CONF_STOPS,
)
from .coordinator import (
    NavajaCoordinator,
    air_coordinator,
    holidays_coordinator,
    pharmacy_coordinator,
    quakes_coordinator,
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
    quakes: NavajaCoordinator | None = None
    holidays: NavajaCoordinator | None = None
    air: NavajaCoordinator | None = None
    pharmacy: NavajaCoordinator | None = None
    pharmacy_comuna: str = ""
    indicator_codes: list[str] = field(default_factory=list)


type NavajaConfigEntry = ConfigEntry[RuntimeData]


def _options(entry: ConfigEntry) -> dict:
    """Datos + opciones, con valores por defecto para entradas de versiones antiguas."""
    opts = {**entry.data, **entry.options}
    if CONF_INDICATORS not in opts:  # entrada creada por la versión 1.x
        opts.setdefault(CONF_INDICATORS, DEFAULT_INDICATORS)
        opts.setdefault(CONF_METRO, True)
        opts.setdefault(CONF_QUAKES, True)
        opts.setdefault(CONF_HOLIDAYS, True)
    return opts


def _stops(raw) -> list[str]:
    if isinstance(raw, (list, tuple)):
        raw = ",".join(str(r) for r in raw)
    try:
        return parse_stop_codes(str(raw or ""))
    except ValueError:
        return []


async def _refresh(coordinator: NavajaCoordinator | None) -> bool:
    """Primer refresco que no propaga errores: cada módulo falla por separado."""
    if coordinator is None:
        return False
    await coordinator.async_refresh()
    return coordinator.last_update_success


async def async_setup_entry(hass: HomeAssistant, entry: NavajaConfigEntry) -> bool:
    opts = _options(entry)
    data = RuntimeData(indicator_codes=list(opts.get(CONF_INDICATORS, [])))

    if data.indicator_codes:
        data.indicators = indicators_coordinator(hass)
    if opts.get(CONF_METRO):
        data.metro = metro_coordinator(hass)
    stops = _stops(opts.get(CONF_STOPS))
    if stops:
        data.stops = stops_coordinator(hass, stops)

    if opts.get(CONF_QUAKES):
        data.quakes = quakes_coordinator(hass)
    if opts.get(CONF_HOLIDAYS):
        data.holidays = holidays_coordinator(hass)
    if opts.get(CONF_AIR):
        data.air = air_coordinator(hass)
    comuna = (opts.get(CONF_PHARMACY_COMUNA) or "").strip()
    if comuna:
        data.pharmacy_comuna = comuna
        data.pharmacy = pharmacy_coordinator(hass, comuna)

    coordinators = [
        c
        for c in (data.indicators, data.metro, data.stops, data.quakes,
                  data.holidays, data.air, data.pharmacy)
        if c is not None
    ]
    results = [await _refresh(c) for c in coordinators]
    if coordinators and not any(results):
        # Ninguna fuente responde: reintentar la carga más tarde.
        raise ConfigEntryNotReady("Ninguna fuente de datos respondió")

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: NavajaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NavajaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
