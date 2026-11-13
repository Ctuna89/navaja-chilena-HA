"""Cargadores de vehículos eléctricos: el más cercano libre, el más barato y «conviene cargar» según la batería.

Datos del mapa de cargadores públicos del Ministerio de Energía (registro de la SEC). Se miden desde la ubicación de la casa
configurada en Home Assistant. La batería del auto la entrega la integración de tu auto en Home Assistant (opcional).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import api
from .const import DOMAIN, EV_ATTRIBUTION

TOP = 5


def _device() -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, "cargadores_electricos")},
        name="Cargadores eléctricos",
        manufacturer="Navaja Chilena",
        entry_type=DeviceEntryType.SERVICE,
    )


def brief(c: api.EvCandidate) -> dict[str, Any]:
    """Resumen de una estación para atributos y tarjetas."""
    return {
        "nombre": c.station.name,
        "direccion": c.station.address,
        "comuna": c.station.commune,
        "distancia_km": round(c.distance_km, 1),
        "puntos_libres": c.free_points,
        "puntos_compatibles": c.compatible_points,
        "potencia_max_kw": round(c.max_kw),
        "conectores": list(c.standards),
        "tarifa_clp_kwh": round(c.price) if c.price is not None else None,
        "actualizado": c.updated.astimezone(dt_util.DEFAULT_TIME_ZONE).strftime("%Y-%m-%d %H:%M") if c.updated else None,
    }


class _EvBase(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: Any, runtime: Any, key: str) -> None:
        super().__init__(runtime.ev)
        self._rt = runtime
        self._attr_unique_id = f"{entry.entry_id}_ev_{key}"
        self._attr_device_info = _device()

    def _candidates(self, *, only_free: bool = True) -> list[api.EvCandidate]:
        cfg = self.coordinator.hass.config
        return api.ev_candidates(
            self.coordinator.data, set(self._rt.ev_connectors), self._rt.ev_min_power,
            cfg.latitude, cfg.longitude, self._rt.ev_radius, dt_util.now(), only_free=only_free,
        )

    def _config_attrs(self) -> dict[str, Any]:
        return {
            "radio_km": self._rt.ev_radius,
            "conectores_buscados": self._rt.ev_connectors,
            "potencia_minima_kw": self._rt.ev_min_power,
            "fuente": EV_ATTRIBUTION,
        }

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None


class EvNearestSensor(_EvBase, SensorEntity):
    """Estación con un punto libre compatible más cercana a tu casa."""

    _attr_name = "Cargador libre más cercano"
    _attr_icon = "mdi:ev-station"

    def __init__(self, entry: Any, runtime: Any) -> None:
        super().__init__(entry, runtime, "cercano")

    @property
    def native_value(self) -> str | None:
        found = self._candidates()
        return found[0].station.name if found else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        found = self._candidates()
        attrs = self._config_attrs() | {"estaciones_con_libres": len(found)}
        if not found:
            compatible = self._candidates(only_free=False)
            attrs["estaciones_compatibles_en_radio"] = len(compatible)
            attrs["motivo"] = f"No hay puntos libres compatibles a {self._rt.ev_radius:g} km de tu casa"
            return attrs
        best = found[0]
        attrs.update(brief(best) | {"latitude": best.station.lat, "longitude": best.station.lon})
        attrs["mas_cercanos"] = [brief(c) for c in found[:TOP]]
        return attrs


class EvFreePointsSensor(_EvBase, SensorEntity):
    """Cuántos puntos de carga compatibles están libres dentro del radio."""

    _attr_name = "Puntos de carga libres cerca"
    _attr_icon = "mdi:ev-plug-type2"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: Any, runtime: Any) -> None:
        super().__init__(entry, runtime, "libres")

    @property
    def native_value(self) -> int:
        return sum(c.free_points for c in self._candidates())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._config_attrs() | {"estaciones_con_libres": len(self._candidates())}


class EvCheapestSensor(_EvBase, SensorEntity):
    """Tarifa por energía más baja entre los puntos libres compatibles (CLP/kWh)."""

    _attr_name = "Cargador libre más barato"
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = "CLP/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, entry: Any, runtime: Any) -> None:
        super().__init__(entry, runtime, "barato")

    def _priced(self) -> list[api.EvCandidate]:
        return sorted((c for c in self._candidates() if c.price is not None), key=lambda c: (c.price, c.distance_km))

    @property
    def native_value(self) -> float | None:
        priced = self._priced()
        return priced[0].price if priced else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        priced = self._priced()
        attrs = self._config_attrs()
        if not priced:
            attrs["motivo"] = "No hay puntos libres compatibles con tarifa por energía informada en el radio"
            return attrs
        best = priced[0]
        attrs.update(brief(best) | {"latitude": best.station.lat, "longitude": best.station.lon})
        attrs["mas_baratos"] = [brief(c) for c in priced[:TOP]]
        return attrs


class EvShouldChargeBinarySensor(_EvBase, BinarySensorEntity):
    """Encendido si la batería de tu auto está baja y hay un punto libre compatible cerca de tu casa."""

    _attr_name = "Conviene cargar"
    _attr_icon = "mdi:battery-charging-low"

    def __init__(self, entry: Any, runtime: Any) -> None:
        super().__init__(entry, runtime, "conviene_cargar")

    def _level(self) -> float | None:
        state = self.hass.states.get(self._rt.ev_battery)
        if state is None:
            return None
        try:
            level = float(state.state)
        except (TypeError, ValueError):
            return None
        return level if 0 <= level <= 100 else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_state_change_event(self.hass, [self._rt.ev_battery], self._battery_changed))

    @callback
    def _battery_changed(self, *_: Any) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return super().available and self._level() is not None   # sin batería válida no se adivina

    @property
    def is_on(self) -> bool:
        level = self._level()
        return bool(level is not None and level <= self._rt.ev_low_battery and self._candidates())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        level = self._level()
        attrs: dict[str, Any] = self._config_attrs() | {
            "bateria": level,
            "umbral_bateria": self._rt.ev_low_battery,
            "bateria_baja": bool(level is not None and level <= self._rt.ev_low_battery),
        }
        found = self._candidates()
        if found:
            attrs["cargador"] = brief(found[0]) | {"latitude": found[0].station.lat, "longitude": found[0].station.lon}
        else:
            attrs["motivo"] = f"No hay puntos libres compatibles a {self._rt.ev_radius:g} km de tu casa"
        return attrs


def sensors(entry: Any, runtime: Any) -> list[Any]:
    return [EvNearestSensor(entry, runtime), EvFreePointsSensor(entry, runtime), EvCheapestSensor(entry, runtime)]


def binary_sensors(entry: Any, runtime: Any) -> list[Any]:
    return [EvShouldChargeBinarySensor(entry, runtime)] if runtime.ev_battery else []
