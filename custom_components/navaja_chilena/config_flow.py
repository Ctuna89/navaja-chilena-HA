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
from .vehicle import VEHICLE_TYPES
from .api import FUEL_LABELS
from .const import (
    CONF_FOOTBALL_LEAGUE,
    CONF_FOOTBALL_NATIONAL,
    CONF_FOOTBALL_TEAM,
    FOOTBALL_NONE,
    FOOTBALL_TEAMS,
    BENEFIT_CARDS,
    BENEFIT_CATEGORIES,
    CONF_BENEFIT_CARDS,
    CONF_BENEFIT_CATEGORIES,
    CONF_FUEL_MAX_AGE,
    CONF_FUEL_RADIUS,
    CONF_FUEL_TYPES,
    FUEL_DEFAULT_MAX_AGE,
    FUEL_DEFAULT_RADIUS,
    FUEL_MAX_AGES,
    FUEL_RADII,
    CONF_VEHICLE_DIGIT,
    CONF_VEHICLE_TYPE,
    VEHICLE_NONE,
    CONF_EPHEMERIDES,
    CINEMA_NEAREST,
    CINEMA_NONE,
    CINEMARK_THEATERS,
    CONF_CINEMA,
    CONF_AIR,
    CONF_BOLSA,
    CONF_CRYPTO,
    CONF_HOLIDAYS,
    CONF_INDICATORS,
    CONF_METRO,
    CONF_PHARMACY_COMUNA,
    CONF_QUAKES,
    CONF_SAINT,
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
                CONF_BOLSA, default=defaults.get(CONF_BOLSA, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SAINT, default=defaults.get(CONF_SAINT, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EPHEMERIDES, default=defaults.get(CONF_EPHEMERIDES, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_CRYPTO, default=defaults.get(CONF_CRYPTO, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_CINEMA, default=defaults.get(CONF_CINEMA, CINEMA_NONE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=CINEMA_NONE, label="No usar / None"),
                        selector.SelectOptionDict(
                            value=CINEMA_NEAREST, label="El más cercano a mi casa / Nearest to home"
                        ),
                        *[
                            selector.SelectOptionDict(value=slug, label=name)
                            for slug, (name, *_rest) in CINEMARK_THEATERS.items()
                        ],
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_VEHICLE_DIGIT, default=str(defaults.get(CONF_VEHICLE_DIGIT, VEHICLE_NONE))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=VEHICLE_NONE, label="No usar / None"),
                        *[selector.SelectOptionDict(value=str(d), label=str(d)) for d in range(10)],
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_VEHICLE_TYPE, default=defaults.get(CONF_VEHICLE_TYPE, "sello_verde")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=label)
                        for k, label in VEHICLE_TYPES.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_FUEL_TYPES, default=defaults.get(CONF_FUEL_TYPES, [])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in FUEL_LABELS.items()],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_FUEL_RADIUS, default=str(defaults.get(CONF_FUEL_RADIUS, FUEL_DEFAULT_RADIUS))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=str(r), label=f"{r} km") for r in FUEL_RADII],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_FUEL_MAX_AGE, default=str(defaults.get(CONF_FUEL_MAX_AGE, FUEL_DEFAULT_MAX_AGE))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=str(d), label=f"{d} días") for d in FUEL_MAX_AGES],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_BENEFIT_CARDS, default=defaults.get(CONF_BENEFIT_CARDS, [])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in BENEFIT_CARDS.items()],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_BENEFIT_CATEGORIES, default=defaults.get(CONF_BENEFIT_CATEGORIES, [])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in BENEFIT_CATEGORIES.items()],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_FOOTBALL_TEAM, default=str(defaults.get(CONF_FOOTBALL_TEAM, FOOTBALL_NONE))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=FOOTBALL_NONE, label="No usar / None"),
                        *[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in sorted(FOOTBALL_TEAMS.items(), key=lambda kv: kv[1])
                        ],
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_FOOTBALL_LEAGUE, default=defaults.get(CONF_FOOTBALL_LEAGUE, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_FOOTBALL_NATIONAL, default=defaults.get(CONF_FOOTBALL_NATIONAL, False)
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
        or any(user_input.get(k) for k in (CONF_METRO, CONF_QUAKES, CONF_HOLIDAYS, CONF_AIR, CONF_CRYPTO, CONF_BOLSA, CONF_SAINT, CONF_EPHEMERIDES))
        or user_input.get(CONF_PHARMACY_COMUNA, "").strip()
        or bool(user_input.get(CONF_FUEL_TYPES))
        or bool(user_input.get(CONF_BENEFIT_CARDS))
        or str(user_input.get(CONF_FOOTBALL_TEAM, FOOTBALL_NONE)) != FOOTBALL_NONE
        or bool(user_input.get(CONF_FOOTBALL_LEAGUE))
        or bool(user_input.get(CONF_FOOTBALL_NATIONAL))
        or user_input.get(CONF_CINEMA, CINEMA_NONE) != CINEMA_NONE
        or str(user_input.get(CONF_VEHICLE_DIGIT, VEHICLE_NONE)) != VEHICLE_NONE
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
