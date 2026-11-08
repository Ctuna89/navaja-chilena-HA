"""Flujo de configuración y opciones."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import api
from .api import parse_stop_codes
from .const import (
    CONF_AIR,
    CONF_CRYPTO,
    CONF_HOLIDAYS,
    CONF_INDICATORS,
    CONF_METRO,
    CONF_PHARMACY_COMUNA,
    CONF_QUAKES,
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
            vol.Required(
                CONF_QUAKES, default=defaults.get(CONF_QUAKES, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_HOLIDAYS, default=defaults.get(CONF_HOLIDAYS, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_AIR, default=defaults.get(CONF_AIR, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_CRYPTO, default=defaults.get(CONF_CRYPTO, False)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_PHARMACY_COMUNA, default=defaults.get(CONF_PHARMACY_COMUNA, "")
            ): selector.TextSelector(),
        }
    )


def _validate(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    try:
        stops = parse_stop_codes(user_input.get(CONF_STOPS, ""))
    except ValueError:
        return user_input, {CONF_STOPS: "invalid_stop"}
    has_any = (
        user_input[CONF_INDICATORS]
        or stops
        or any(user_input.get(k) for k in (CONF_METRO, CONF_QUAKES, CONF_HOLIDAYS, CONF_AIR, CONF_CRYPTO))
        or user_input.get(CONF_PHARMACY_COMUNA, "").strip()
    )
    if not has_any:
        errors["base"] = "nothing_selected"
    return {
        **user_input,
        CONF_STOPS: ", ".join(stops),
        CONF_PHARMACY_COMUNA: user_input.get(CONF_PHARMACY_COMUNA, "").strip(),
    }, errors


async def _check_stops(hass, stops: list[str]) -> dict[str, str]:
    """Rechaza paraderos que la API declara inexistentes (HTTP 400/404).

    Si la API no responde por otra causa no se bloquea la configuración.
    """
    session = async_get_clientsession(hass)
    for code in stops:
        try:
            await api.fetch_stop(session, code)
        except api.NavajaApiError as err:
            if err.status in (400, 404):
                return {CONF_STOPS: "stop_not_found"}
    return {}


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
                errors = await _check_stops(self.hass, parse_stop_codes(cleaned[CONF_STOPS]))
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
                errors = await _check_stops(self.hass, parse_stop_codes(cleaned[CONF_STOPS]))
            if not errors:
                return self.async_create_entry(data=cleaned)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_schema(user_input or current), errors=errors
        )
