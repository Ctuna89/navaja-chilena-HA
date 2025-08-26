# Author: duvob90
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup via YAML (no-op)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Navaja Chilena from a config entry."""
    # ⬇️ Importamos aquí para no bloquear el import de config_flow
    from .coordinator import NavajaCoordinator

    coordinator = NavajaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "entry": entry}

    # UI/endpoint opcional (también import perezoso)
    try:
        from .panel import register_views
        register_views(hass)
    except Exception as e:
        _LOGGER.debug("Panel opcional no cargado: %s", e)

    # Cargar plataformas
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Recargar si cambian opciones
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
