# Author: duvob90
from __future__ import annotations

from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import NavajaCoordinator
# Si tienes panel.py para la UI de paraderos
try:
    from .panel import register_views
    _HAS_PANEL = True
except Exception:
    _HAS_PANEL = False

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup via YAML (no-op)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    coordinator = NavajaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "entry": entry,
    }

    # Registrar UI/endpoint si existe
    if _HAS_PANEL:
        register_views(hass)

    # ✅ API correcta en HA 2024+/2025
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Recargar al cambiar opciones (recrea sensores de paraderos)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry on options update."""
    await hass.config_entries.async_reload(entry.entry_id)
