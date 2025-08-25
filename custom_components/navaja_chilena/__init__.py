# Author: duvob90
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import Platform
from .const import DOMAIN
from .coordinator import NavajaCoordinator
from .panel import register_views
from typing import Any

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NavajaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "entry": entry,
    }

    register_views(hass)
    register_views(hass)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update: reload entry to recreate sensors."""
    await hass.config_entries.async_reload(entry.entry_id)
