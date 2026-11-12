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
from .efe_train import CONF_TRAIN_RETURN, CONF_TRAIN_TRIPS, format_trips, parse_trips
from .vehicle import VEHICLE_TYPES, build_vehicles, parse_extra_vehicles
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
    CONF_CLARO_ARENA,
    CONF_VAMOH_URL,
    CONF_EVENTS_COMMUNE,
    CONF_EVENTS_FREE_ONLY,
    CONF_NEWS_COUNT,
    CONF_NEWS_TOPICS,
    NEWS_COUNTS,
    NEWS_DEFAULT_COUNT,
    NEWS_TOPICS,
    CONF_REGIONAL_STOPS,
    CONF_REGIONAL_ZONE,
    REGIONAL_NONE,
    REGIONAL_ZONES,
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
    CONF_VEHICLES_MORE,
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
            vol.Optional(
                CONF_TRAIN_TRIPS, default=defaults.get(CONF_TRAIN_TRIPS, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_TRAIN_RETURN, default=defaults.get(CONF_TRAIN_RETURN, False)
            ): selector.BooleanSelector(),
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
            vol.Optional(
                CONF_VEHICLES_MORE, default=defaults.get(CONF_VEHICLES_MORE, "")
            ): selector.TextSelector(),
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
            vol.Optional(
                CONF_EVENTS_COMMUNE, default=defaults.get(CONF_EVENTS_COMMUNE, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_EVENTS_FREE_ONLY, default=defaults.get(CONF_EVENTS_FREE_ONLY, False)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_VAMOH_URL, default=defaults.get(CONF_VAMOH_URL, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_CLARO_ARENA, default=defaults.get(CONF_CLARO_ARENA, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NEWS_TOPICS, default=defaults.get(CONF_NEWS_TOPICS, [])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in NEWS_TOPICS.items()],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_NEWS_COUNT, default=str(defaults.get(CONF_NEWS_COUNT, NEWS_DEFAULT_COUNT))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=str(n), label=f"{n} titulares") for n in NEWS_COUNTS],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_REGIONAL_ZONE, default=defaults.get(CONF_REGIONAL_ZONE, REGIONAL_NONE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=REGIONAL_NONE, label="No usar / None"),
                        *[
                            selector.SelectOptionDict(value=k, label=name)
                            for k, (_id, name) in sorted(REGIONAL_ZONES.items(), key=lambda kv: kv[1][1])
                        ],
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_REGIONAL_STOPS, default=defaults.get(CONF_REGIONAL_STOPS, "")
            ): selector.TextSelector(),
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
    try:
        vtype_default = str(user_input.get(CONF_VEHICLE_TYPE) or "sello_verde")
        more_vehicles = parse_extra_vehicles(user_input.get(CONF_VEHICLES_MORE, ""), vtype_default)
        primary = str(user_input.get(CONF_VEHICLE_DIGIT, VEHICLE_NONE))
        build_vehicles(int(primary) if primary.isdigit() else None, vtype_default, more_vehicles)
    except ValueError:
        return user_input, {CONF_VEHICLES_MORE: "invalid_vehicle"}
    try:
        trips = parse_trips(user_input.get(CONF_TRAIN_TRIPS, ""))
        parse_trips(user_input.get(CONF_TRAIN_TRIPS, ""), bool(user_input.get(CONF_TRAIN_RETURN)))  # el tope cuenta el sentido inverso
    except ValueError:
        return user_input, {CONF_TRAIN_TRIPS: "invalid_trip"}
    vamoh = str(user_input.get(CONF_VAMOH_URL) or "").strip()
    if vamoh and not api.vamoh_url_ok(vamoh):
        return user_input, {CONF_VAMOH_URL: "invalid_vamoh_url"}
    zone = str(user_input.get(CONF_REGIONAL_ZONE, REGIONAL_NONE))
    try:
        regional = api.parse_regional_codes(user_input.get(CONF_REGIONAL_STOPS, ""))
    except ValueError:
        return user_input, {CONF_REGIONAL_STOPS: "invalid_regional_stop"}
    if zone != REGIONAL_NONE and not regional:
        return user_input, {CONF_REGIONAL_STOPS: "regional_needs_stops"}
    if zone == REGIONAL_NONE and regional:
        return user_input, {CONF_REGIONAL_ZONE: "regional_needs_zone"}
    has_any = (
        user_input[CONF_INDICATORS]
        or stops
        or trips
        or any(user_input.get(k) for k in (CONF_METRO, CONF_QUAKES, CONF_HOLIDAYS, CONF_AIR, CONF_CRYPTO, CONF_BOLSA, CONF_SAINT, CONF_EPHEMERIDES))
        or user_input.get(CONF_PHARMACY_COMUNA, "").strip()
        or bool(user_input.get(CONF_FUEL_TYPES))
        or bool(user_input.get(CONF_BENEFIT_CARDS))
        or bool(user_input.get(CONF_NEWS_TOPICS))
        or bool(str(user_input.get(CONF_EVENTS_COMMUNE) or "").strip())
        or bool(user_input.get(CONF_CLARO_ARENA))
        or bool(str(user_input.get(CONF_VAMOH_URL) or "").strip())
        or (zone != REGIONAL_NONE and bool(regional))
        or str(user_input.get(CONF_FOOTBALL_TEAM, FOOTBALL_NONE)) != FOOTBALL_NONE
        or bool(user_input.get(CONF_FOOTBALL_LEAGUE))
        or bool(user_input.get(CONF_FOOTBALL_NATIONAL))
        or user_input.get(CONF_CINEMA, CINEMA_NONE) != CINEMA_NONE
        or str(user_input.get(CONF_VEHICLE_DIGIT, VEHICLE_NONE)) != VEHICLE_NONE
        or bool(more_vehicles)
    )
    if not has_any:
        errors["base"] = "nothing_selected"
    return {
        **user_input,
        CONF_STOPS: ", ".join(stops),
        CONF_TRAIN_TRIPS: format_trips(trips),
        CONF_VEHICLES_MORE: ", ".join(f"{d}:{t}" for d, t in more_vehicles),
        CONF_PHARMACY_COMUNA: user_input.get(CONF_PHARMACY_COMUNA, "").strip(),
        CONF_REGIONAL_STOPS: ", ".join(regional),
        CONF_VAMOH_URL: vamoh,
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


async def _resolve_commune(hass, commune: str) -> tuple[str, dict[str, str]]:
    """Nombre oficial de la comuna según Chile Cultura (corrige tildes y mayúsculas).

    Si no se puede consultar la lista, se deja lo escrito y no se bloquea la configuración.
    """
    commune = " ".join(commune.split())
    if not commune:
        return "", {}
    try:
        communes = await api.fetch_culture_communes(async_get_clientsession(hass))
    except api.NavajaApiError:
        return commune, {}
    official = api.resolve_commune(commune, communes)
    if official is None:
        return commune, {CONF_EVENTS_COMMUNE: "events_commune_not_found"}
    return official, {}


async def _check_vamoh(hass, url: str) -> dict[str, str]:
    """Que el enlace entregue un calendario .ics. Si Vamoh no responde en este momento, no se bloquea."""
    if not url:
        return {}
    try:
        await api.fetch_vamoh_calendar(async_get_clientsession(hass), url)
    except api.NavajaApiError as err:
        if err.status is None and "no es un calendario" in str(err):
            return {CONF_VAMOH_URL: "vamoh_not_calendar"}
        if err.status in (401, 403, 404):
            return {CONF_VAMOH_URL: "vamoh_not_calendar"}
    return {}


async def _check_regional(hass, zone: str, codes: list[str]) -> dict[str, str]:
    """Rechaza paraderos que no existen en la ciudad. Si no se puede comprobar, no se bloquea."""
    if zone == REGIONAL_NONE or not codes:
        return {}
    try:
        names = await api.fetch_regional_stop_names(async_get_clientsession(hass), zone)
    except api.NavajaApiError:
        return {}
    if names and any(c not in names for c in codes):
        return {CONF_REGIONAL_STOPS: "regional_stop_not_found"}
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
                errors = await _check_regional(
                    self.hass, str(cleaned.get(CONF_REGIONAL_ZONE, REGIONAL_NONE)),
                    api.parse_regional_codes(cleaned.get(CONF_REGIONAL_STOPS, "")))
            if not errors:
                commune, errors = await _resolve_commune(self.hass, str(cleaned.get(CONF_EVENTS_COMMUNE) or ""))
                cleaned = {**cleaned, CONF_EVENTS_COMMUNE: commune}
            if not errors:
                errors = await _check_vamoh(self.hass, str(cleaned.get(CONF_VAMOH_URL) or ""))
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
                errors = await _check_regional(
                    self.hass, str(cleaned.get(CONF_REGIONAL_ZONE, REGIONAL_NONE)),
                    api.parse_regional_codes(cleaned.get(CONF_REGIONAL_STOPS, "")))
            if not errors:
                commune, errors = await _resolve_commune(self.hass, str(cleaned.get(CONF_EVENTS_COMMUNE) or ""))
                cleaned = {**cleaned, CONF_EVENTS_COMMUNE: commune}
            if not errors:
                errors = await _check_vamoh(self.hass, str(cleaned.get(CONF_VAMOH_URL) or ""))
            if not errors:
                return self.async_create_entry(data=cleaned)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_schema(user_input or current), errors=errors
        )
