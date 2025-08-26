# Author: duvob90
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

# Evitamos dependencias innecesarias para que el import sea 100% fiable
DOMAIN = "navaja_chilena"
CONF_STOP_IDS = "stop_ids"
DEFAULT_STOPS = "PA433"

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_STOP_IDS, default=DEFAULT_STOPS): str
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración de Navaja Chilena."""
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            # Guardamos directamente lo ingresado por el usuario
            return self.async_create_entry(title="Navaja Chilena", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Opciones: agregar/eliminar/editar paraderos desde la UI."""
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            # Persistimos las opciones tal cual
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_STOP_IDS,
            self.config_entry.data.get(CONF_STOP_IDS, DEFAULT_STOPS),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_STOP_IDS, default=current): str
            }),
        )
