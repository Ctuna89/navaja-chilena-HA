"""«Cerca de ti»: avisos según la ubicación de un teléfono, calculados solo dentro de Home Assistant.

El usuario elige una persona o dispositivo (el de la app Companion). La integración lee su ubicación del
estado de esa entidad y calcula distancias localmente: no envía la posición a ningún servicio. Las consultas
a Cinemark o a Bencina en Línea no llevan la ubicación del usuario.

Entidades (dispositivo «Cerca de ti»):
- «Cerca de un Cinemark»: encendida a menos del radio de un cine; trae la próxima función.
- «Cerca de una estación con descuento»: encendida a menos del radio de una estación de una marca con
  descuento hoy para tus tarjetas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.util import dt as dt_util

from . import api
from .const import CINEMA_INTERVAL, CINEMARK_THEATERS, DOMAIN, NEAR_EXIT_FACTOR, NEAR_MAX_ACCURACY

_LOGGER = logging.getLogger(__name__)
TZ = ZoneInfo(api.METRO_TZ)
RETRY_AFTER = timedelta(minutes=10)   # tras un fallo de Cinemark no se insiste de inmediato


class _NearBase(BinarySensorEntity):
    """Base: sigue al teléfono elegido y recalcula cuando cambia su ubicación."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: Any, runtime: Any, key: str) -> None:
        self._rt = runtime
        self._near = False
        self._attr_unique_id = f"{entry.entry_id}_cerca_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "cerca_de_ti")},
            name="Cerca de ti",
            manufacturer="Navaja Chilena",
            entry_type=DeviceEntryType.SERVICE,
        )

    # --- ubicación
    def _location(self) -> tuple[float, float] | None:
        state = self.hass.states.get(self._rt.near_tracker)
        if state is None:
            return None
        attrs = state.attributes
        try:
            lat, lon = float(attrs["latitude"]), float(attrs["longitude"])
        except (KeyError, TypeError, ValueError):
            return None
        accuracy = attrs.get("gps_accuracy")
        if isinstance(accuracy, (int, float)) and accuracy > max(NEAR_MAX_ACCURACY, self._rt.near_radius):
            return None   # una ubicación imprecisa daría avisos falsos
        return lat, lon

    def _within(self, meters: float) -> bool:
        """Con histéresis: se enciende dentro del radio y se apaga recién al alejarse un 30 % más."""
        radius = self._rt.near_radius
        return meters <= radius or (self._near and meters <= radius * NEAR_EXIT_FACTOR)

    def _now(self) -> datetime:
        return dt_util.now().astimezone(TZ)

    # --- ciclo de vida
    def _extra_sources(self) -> list[Any]:
        return []

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_track_state_change_event(self.hass, [self._rt.near_tracker], self._changed))
        for coordinator in self._extra_sources():
            self.async_on_remove(coordinator.async_add_listener(self._changed))
        self.async_on_remove(async_track_time_change(self.hass, self._changed, hour=0, minute=0, second=5))
        self._evaluate()

    @callback
    def _changed(self, *_: Any) -> None:
        self._evaluate()
        self.async_write_ha_state()

    def _evaluate(self) -> None:  # pragma: no cover - lo define cada entidad
        raise NotImplementedError

    @property
    def is_on(self) -> bool:
        return self._near


class NearCinemaBinarySensor(_NearBase):
    """Encendida cuando estás cerca de un Cinemark; la próxima función va en sus atributos."""

    _attr_name = "Cerca de un Cinemark"
    _attr_icon = "mdi:movie-open-marker"

    def __init__(self, entry: Any, runtime: Any) -> None:
        super().__init__(entry, runtime, "cinemark")
        self._slug: str | None = None
        self._distance: float | None = None
        self._cache: dict[str, tuple[datetime, api.Cinema | None]] = {}
        self._loading: set[str] = set()

    @property
    def available(self) -> bool:
        return self._location() is not None

    def _cinema_for(self, slug: str) -> tuple[api.Cinema | None, bool]:
        """(cartelera, hay_dato): la del cine configurado si es el mismo; si no, la guardada en memoria."""
        rt = self._rt
        if rt.cinema is not None and rt.cinema_slug == slug and rt.cinema.data is not None:
            return rt.cinema.data, True
        cached = self._cache.get(slug)
        if cached is None:
            return None, False
        fetched, cinema = cached
        ttl = CINEMA_INTERVAL if cinema is not None else RETRY_AFTER
        if dt_util.utcnow() - fetched > ttl:
            return cinema, False   # vencida: sirve mientras llega la nueva
        return cinema, True

    def _evaluate(self) -> None:
        loc = self._location()
        if loc is None:
            self._near, self._slug, self._distance = False, None, None
            return
        self._slug, self._distance = api.theaters_by_distance(*loc)[0]
        self._near = self._within(self._distance)
        if self._near:
            _, fresh = self._cinema_for(self._slug)
            if not fresh and self._slug not in self._loading:
                self._loading.add(self._slug)
                self.hass.async_create_task(self._async_load(self._slug))

    async def _async_load(self, slug: str) -> None:
        try:
            cinema: api.Cinema | None = await api.fetch_cinemark(async_get_clientsession(self.hass), slug)
        except api.NavajaApiError as err:
            _LOGGER.debug("Cartelera de %s no disponible: %s", slug, err)
            cinema = None
        finally:
            self._loading.discard(slug)
        self._cache[slug] = (dt_util.utcnow(), cinema)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._slug is None:
            return {}
        name, address, lat, lon = CINEMARK_THEATERS[self._slug]
        attrs: dict[str, Any] = {
            "cine_mas_cercano": name,
            "direccion": address,
            "distancia_m": round(self._distance or 0),
            "radio_m": self._rt.near_radius,
            "latitude": lat,
            "longitude": lon,
        }
        if not self._near:
            return attrs
        cinema, _fresh = self._cinema_for(self._slug)
        if cinema is None:
            attrs["cartelera_disponible"] = False   # no se inventa: aún no llega o Cinemark no respondió
            return attrs
        upcoming = api.cinema_upcoming(cinema, self._now())
        brief = [{"titulo": s.title, "hora": s.start.strftime("%H:%M"), "formato": s.video_format, "poster": s.poster} for s in upcoming]
        attrs.update(
            {
                "cartelera_disponible": True,
                "proxima_funcion": brief[0] if brief else None,
                "proximas_funciones": brief,
                "resumen": "\n".join(f"{b['hora']} {b['titulo']}" + (f" ({b['formato']})" if b["formato"] else "") for b in brief),
            }
        )
        return attrs


class NearDiscountStationBinarySensor(_NearBase):
    """Encendida cuando estás cerca de una estación de una marca con descuento hoy para tus tarjetas."""

    _attr_name = "Cerca de una estación con descuento"
    _attr_icon = "mdi:gas-station"

    def __init__(self, entry: Any, runtime: Any) -> None:
        super().__init__(entry, runtime, "estacion_descuento")
        self._found: tuple[api.Station, float] | None = None
        self._today_discounts: dict[str, list[api.FuelDiscount]] = {}

    def _extra_sources(self) -> list[Any]:
        return [c for c in (self._rt.fuel, self._rt.fuel_discounts) if c is not None]

    def _calendar(self) -> api.FuelDiscountCalendar | None:
        data = self._rt.fuel_discounts.data if self._rt.fuel_discounts is not None else None
        if data is None or not api.fuel_discounts_current(data, self._now().date()):
            return None   # calendario de otro mes: no se muestra como vigente
        return data

    @property
    def available(self) -> bool:
        return self._location() is not None and self._rt.fuel is not None and self._rt.fuel.data is not None and self._calendar() is not None

    def _evaluate(self) -> None:
        loc, calendar = self._location(), self._calendar()
        stations = self._rt.fuel.data if self._rt.fuel is not None else None
        if loc is None or calendar is None or stations is None:
            self._near, self._found, self._today_discounts = False, None, {}
            return
        today, _nxt, _up = api.fuel_discounts_for(calendar, self._rt.benefit_cards, self._now().date())
        self._today_discounts = api.discount_brands(today)
        self._found = api.nearest_discount_station(stations, set(self._today_discounts), *loc)
        self._near = bool(self._found) and self._within(self._found[1])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {"radio_m": self._rt.near_radius, "marcas_con_descuento_hoy": sorted(b.title() for b in self._today_discounts)}
        if self._found is None:
            return attrs
        station, meters = self._found
        attrs.update(
            {
                "estacion_mas_cercana": station.brand,
                "direccion": station.address,
                "comuna": station.commune,
                "distancia_m": round(meters),
                "latitude": station.lat,
                "longitude": station.lon,
            }
        )
        if self._near:
            attrs["descuentos"] = [
                {"tarjeta": d.card_name, "descuento": d.amount, "detalle": d.detail, "confirmado": d.confirmed, "fuente": d.source}
                for d in self._today_discounts.get(station.brand.casefold(), [])
            ]
            attrs["aviso"] = "Revisa condiciones, topes y activaciones antes de cargar."
        return attrs
