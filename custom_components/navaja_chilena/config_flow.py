"""Flujo de configuración y opciones."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import parse_stop_codes
from .const import (
    CONF_INDICATORS,
    CONF_METRO,
    CONF_STOPS,
    DEFAULT_INDICATORS,
    DOMAIN,
    INDICATORS,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_INDICATORS,
                default=defaults.get(CONF_INDICATORS, DEFAULT_INDICATORS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in INDICATORS.items()
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_METRO, default=defaults.get(CONF_METRO, True)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_STOPS, default=defaults.get(CONF_STOPS, "")
            ): selector.TextSelector(),
        }
    )


def _validate(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    try:
        stops = parse_stop_codes(user_input.get(CONF_STOPS, ""))
    except ValueError:
        return user_input, {CONF_STOPS: "invalid_stop"}
    if not (user_input[CONF_INDICATORS] or user_input[CONF_METRO] or stops):
        errors["base"] = "nothing_selected"
    return {**user_input, CONF_STOPS: ", ".join(stops)}, errors


class NavajaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="Navaja Chilena", data=cleaned)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return NavajaOptionsFlow()


class NavajaOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=cleaned)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_schema(user_input or current), errors=errors
        )
