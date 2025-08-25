# Author: duvob90
from __future__ import annotations
import voluptuous as vol
from typing import Any, List

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_STOP_IDS, DEFAULT_STOPS

def _parse_stops(raw: str) -> List[str]:
    return [s.strip().upper() for s in (raw or "").split(",") if s.strip()]

def _join_stops(stops: list[str]) -> str:
    # Normalize unique, keep order
    seen = set()
    out = []
    for s in stops:
        u = s.upper()
        if u not in seen:
            seen.add(u)
            out.append(u)
    return ",".join(out)

class NavajaChilenaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            stop_ids = user_input.get(CONF_STOP_IDS, "").strip()
            if not stop_ids:
                errors["base"] = "no_stops"
            else:
                return self.async_create_entry(title="Navaja Chilena", data={CONF_STOP_IDS: stop_ids})

        schema = vol.Schema({vol.Required(CONF_STOP_IDS, default=DEFAULT_STOPS): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Menu-like form: choose action
        current = self.config_entry.options.get(CONF_STOP_IDS,
                                               self.config_entry.data.get(CONF_STOP_IDS, DEFAULT_STOPS))
        self._current_stops = _parse_stops(current)
        actions = {"add": "Agregar paradero", "remove": "Eliminar paradero", "bulk": "Edición masiva (lista)"}
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add()
            if action == "remove":
                return await self.async_step_remove()
            if action == "bulk":
                return await self.async_step_bulk()
        schema = vol.Schema({vol.Required("action"): vol.In(actions)})
        return self.async_show_form(step_id="init", data_schema=schema, description_placeholders={})

    async def async_step_add(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            stop = user_input.get("stop_id", "").strip().upper()
            if stop:
                new = _join_stops(self._current_stops + [stop])
                return self.async_create_entry(title="", data={CONF_STOP_IDS: new})
        schema = vol.Schema({vol.Required("stop_id", description="Código de paradero (e.g. PA433)"): str})
        return self.async_show_form(step_id="add", data_schema=schema)

    async def async_step_remove(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        choices = {s: s for s in self._current_stops} or {"(sin paraderos)": "(sin paraderos)"}
        if user_input is not None:
            sel = user_input.get("stop_id")
            if sel in choices and self._current_stops:
                new_list = [s for s in self._current_stops if s != sel]
                new = _join_stops(new_list)
                return self.async_create_entry(title="", data={CONF_STOP_IDS: new})
        schema = vol.Schema({vol.Required("stop_id"): vol.In(choices)})
        return self.async_show_form(step_id="remove", data_schema=schema)

    async def async_step_bulk(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        default_val = _join_stops(self._current_stops)
        if user_input is not None:
            bulk = user_input.get("stop_ids", "")
            new = _join_stops(_parse_stops(bulk))
            return self.async_create_entry(title="", data={CONF_STOP_IDS: new})
        schema = vol.Schema({vol.Required("stop_ids", default=default_val): str})
        return self.async_show_form(step_id="bulk", data_schema=schema)
