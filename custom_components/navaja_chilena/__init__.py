"""Navaja Chilena: indicadores económicos, Metro y paraderos de Chile."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import api
from .api import FUEL_LABELS, nearest_theater, parse_stop_codes
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
    CONF_EPHEMERIDES,
    CINEMA_NEAREST,
    CINEMA_NONE,
    CINEMARK_THEATERS,
    CONF_CINEMA,
    DEFAULT_INDICATORS,
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
    CONF_VEHICLE_DIGIT,
    CONF_VEHICLES_MORE,
    CONF_VEHICLE_TYPE,
    VEHICLE_NONE,
)
from .efe_train import CONF_TRAIN_RETURN, CONF_TRAIN_TRIPS, parse_trips
from .efe_train_entity import train_coordinator
from .vehicle import VEHICLE_TYPES, VehicleSpec, build_vehicles, parse_extra_vehicles
from .coordinator import (
    football_coordinator,
    national_coordinator,
    arena_coordinator,
    benefits_coordinator,
    culture_coordinator,
    vamoh_coordinator,
    news_coordinator,
    regional_coordinator,
    fuel_discounts_coordinator,
    fuel_coordinator,
    NavajaCoordinator,
    air_coordinator,
    bolsa_coordinator,
    cinema_coordinator,
    ephemerides_coordinator,
    crypto_coordinator,
    holidays_coordinator,
    pharmacy_coordinator,
    quakes_coordinator,
    indicators_coordinator,
    metro_coordinator,
    stops_coordinator,
)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


@dataclass
class RuntimeData:
    indicators: NavajaCoordinator | None = None
    metro: NavajaCoordinator | None = None
    stops: NavajaCoordinator | None = None
    train: NavajaCoordinator | None = None
    train_trips: list[tuple[int, int]] = field(default_factory=list)
    quakes: NavajaCoordinator | None = None
    holidays: NavajaCoordinator | None = None
    air: NavajaCoordinator | None = None
    pharmacy: NavajaCoordinator | None = None
    crypto: NavajaCoordinator | None = None
    bolsa: NavajaCoordinator | None = None
    saint: bool = False
    cinema: NavajaCoordinator | None = None
    cinema_slug: str = ""
    ephemerides: NavajaCoordinator | None = None
    pharmacy_comuna: str = ""
    fuel: NavajaCoordinator | None = None
    benefits: NavajaCoordinator | None = None
    fuel_discounts: NavajaCoordinator | None = None
    regional: NavajaCoordinator | None = None
    news: NavajaCoordinator | None = None
    culture: NavajaCoordinator | None = None
    arena: NavajaCoordinator | None = None
    vamoh: NavajaCoordinator | None = None
    events_commune: str = ""
    events_free_only: bool = False
    news_topics: list[str] = field(default_factory=list)
    regional_zone: str = ""
    benefit_cards: list[str] = field(default_factory=list)
    benefit_categories: list[str] = field(default_factory=list)
    football: NavajaCoordinator | None = None
    football_team: str = ""
    football_league: bool = False
    national: NavajaCoordinator | None = None
    fuel_types: list[str] = field(default_factory=list)
    fuel_radius: float = FUEL_DEFAULT_RADIUS
    fuel_max_age: int = FUEL_DEFAULT_MAX_AGE
    holidays_visible: bool = False   # crear los sensores de feriados (el dato se usa también por Metro y vehículo)
    vehicles: list[VehicleSpec] = field(default_factory=list)
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
        opts.setdefault(CONF_SAINT, True)
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
        data.indicators = indicators_coordinator(hass, data.indicator_codes)
    if opts.get(CONF_METRO):
        data.metro = metro_coordinator(hass)
    stops = _stops(opts.get(CONF_STOPS))
    if stops:
        data.stops = stops_coordinator(hass, stops)
    try:
        data.train_trips = parse_trips(
            str(opts.get(CONF_TRAIN_TRIPS) or ""), bool(opts.get(CONF_TRAIN_RETURN))
        )
    except ValueError:
        data.train_trips = []
    if data.train_trips:
        data.train = train_coordinator(hass, data.train_trips)

    if opts.get(CONF_QUAKES):
        data.quakes = quakes_coordinator(hass)
    digit = str(opts.get(CONF_VEHICLE_DIGIT, VEHICLE_NONE))
    vtype = opts.get(CONF_VEHICLE_TYPE)
    vtype = vtype if vtype in VEHICLE_TYPES else "sello_verde"
    try:
        data.vehicles = build_vehicles(
            int(digit) if digit in tuple("0123456789") else None,
            vtype,
            parse_extra_vehicles(str(opts.get(CONF_VEHICLES_MORE) or ""), vtype),
        )
    except ValueError:   # configuración inválida: se usa solo el vehículo principal
        data.vehicles = build_vehicles(int(digit) if digit in tuple("0123456789") else None, vtype, [])
    data.holidays_visible = bool(opts.get(CONF_HOLIDAYS))
    team = str(opts.get(CONF_FOOTBALL_TEAM, FOOTBALL_NONE))
    data.football_team = team if team in FOOTBALL_TEAMS else ""
    data.football_league = bool(opts.get(CONF_FOOTBALL_LEAGUE))
    if data.football_team or data.football_league:
        data.football = football_coordinator(hass, data.football_team or None, data.football_league)
    if opts.get(CONF_FOOTBALL_NATIONAL):
        data.national = national_coordinator(hass)
    fuel_types = [f for f in (opts.get(CONF_FUEL_TYPES) or []) if f in FUEL_LABELS]
    if fuel_types:
        data.fuel_types = fuel_types
        try:
            data.fuel_radius = float(opts.get(CONF_FUEL_RADIUS, FUEL_DEFAULT_RADIUS))
        except (TypeError, ValueError):
            data.fuel_radius = FUEL_DEFAULT_RADIUS
        try:
            data.fuel_max_age = int(opts.get(CONF_FUEL_MAX_AGE, FUEL_DEFAULT_MAX_AGE))
        except (TypeError, ValueError):
            data.fuel_max_age = FUEL_DEFAULT_MAX_AGE
        data.fuel = fuel_coordinator(hass)
    commune = str(opts.get(CONF_EVENTS_COMMUNE) or "").strip()
    if commune:
        data.events_commune = commune
        data.events_free_only = bool(opts.get(CONF_EVENTS_FREE_ONLY))
        data.culture = culture_coordinator(hass, commune)
    vamoh_url = str(opts.get(CONF_VAMOH_URL) or "").strip()
    if vamoh_url and api.vamoh_url_ok(vamoh_url):
        data.vamoh = vamoh_coordinator(hass, vamoh_url)
    if opts.get(CONF_CLARO_ARENA):
        data.arena = arena_coordinator(hass)
    topics = [t for t in (opts.get(CONF_NEWS_TOPICS) or []) if t in NEWS_TOPICS]
    if topics:
        try:
            count = int(opts.get(CONF_NEWS_COUNT, NEWS_DEFAULT_COUNT))
        except (TypeError, ValueError):
            count = NEWS_DEFAULT_COUNT
        data.news_topics = topics
        data.news = news_coordinator(hass, topics, count)
    zone = str(opts.get(CONF_REGIONAL_ZONE, REGIONAL_NONE))
    try:
        regional_codes = api.parse_regional_codes(str(opts.get(CONF_REGIONAL_STOPS) or ""))
    except ValueError:
        regional_codes = []
    if zone in REGIONAL_ZONES and regional_codes:
        data.regional_zone = zone
        data.regional = regional_coordinator(hass, zone, regional_codes)
    benefit_cards = [c for c in (opts.get(CONF_BENEFIT_CARDS) or []) if c in BENEFIT_CARDS]
    benefit_cats = [c for c in (opts.get(CONF_BENEFIT_CATEGORIES) or []) if c in BENEFIT_CATEGORIES]
    if benefit_cards:
        data.benefit_cards = benefit_cards
        data.fuel_discounts = fuel_discounts_coordinator(hass)
    if benefit_cards and benefit_cats:
        data.benefit_categories = benefit_cats
        data.benefits = benefits_coordinator(hass, benefit_cards, benefit_cats)
    # Los festivos también los necesitan el horario del Metro y la restricción vehicular.
    if data.holidays_visible or opts.get(CONF_METRO) or bool(data.vehicles):
        data.holidays = holidays_coordinator(hass)
    if opts.get(CONF_AIR):
        data.air = air_coordinator(hass)
    if opts.get(CONF_CRYPTO):
        data.crypto = crypto_coordinator(hass)
    if opts.get(CONF_BOLSA):
        data.bolsa = bolsa_coordinator(hass)
    data.saint = bool(opts.get(CONF_SAINT))
    if opts.get(CONF_EPHEMERIDES):
        data.ephemerides = ephemerides_coordinator(hass)
    cinema = opts.get(CONF_CINEMA, CINEMA_NONE)
    if cinema == CINEMA_NEAREST:
        cinema = nearest_theater(hass.config.latitude, hass.config.longitude)
    if cinema in CINEMARK_THEATERS:
        data.cinema_slug = cinema
        data.cinema = cinema_coordinator(hass, cinema)
    comuna = (opts.get(CONF_PHARMACY_COMUNA) or "").strip()
    if comuna:
        data.pharmacy_comuna = comuna
        data.pharmacy = pharmacy_coordinator(hass, comuna)

    coordinators = [
        c
        for c in (data.indicators, data.metro, data.stops, data.train, data.quakes,
                  data.holidays, data.air, data.pharmacy, data.crypto, data.bolsa, data.cinema, data.ephemerides, data.fuel, data.benefits, data.fuel_discounts, data.regional, data.news, data.culture, data.arena, data.vamoh, data.football, data.national)
        if c is not None
    ]
    results = [await _refresh(c) for c in coordinators]
    offline_modules = data.saint or bool(data.vehicles)   # no dependen de internet
    if coordinators and not any(results) and not offline_modules:
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
