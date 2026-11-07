"""Sensores de Navaja Chilena."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NavajaConfigEntry
from .const import DOMAIN, INDICATORS, UNIT_MAP


def _device(key: str, name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, key)},
        name=name,
        manufacturer="Navaja Chilena",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: NavajaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
    entities: list[SensorEntity] = []

    if rt.indicators:
        entities += [
            IndicatorSensor(rt.indicators, entry, code)
            for code in rt.indicator_codes
            if code in rt.indicators.data
        ]
    if rt.metro:
        entities += [
            MetroLineSensor(rt.metro, entry, line_id) for line_id in rt.metro.data
        ]
    if rt.stops:
        entities += [StopSensor(rt.stops, entry, code) for code in rt.stops.data]

    async_add_entities(entities)


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: NavajaConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{self._kind}_{key}"

    _kind = ""

    @property
    def available(self) -> bool:
        return super().available and self._key in (self.coordinator.data or {})


class IndicatorSensor(_Base):
    _kind = "indicador"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, entry, code: str) -> None:
        super().__init__(coordinator, entry, code)
        self._attr_name = INDICATORS.get(code, code)
        self._attr_device_info = _device("indicadores", "Indicadores económicos")

    @property
    def native_value(self) -> float | None:
        item = self.coordinator.data.get(self._key)
        return item.value if item else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        item = self.coordinator.data.get(self._key)
        return UNIT_MAP.get(item.unit, item.unit) if item and item.unit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self.coordinator.data.get(self._key)
        return {"fecha": item.date, "nombre_oficial": item.name} if item else {}


class MetroLineSensor(_Base):
    _kind = "metro"
    _attr_icon = "mdi:subway-variant"

    def __init__(self, coordinator, entry, line_id: str) -> None:
        super().__init__(coordinator, entry, line_id)
        self._attr_name = coordinator.data[line_id].name
        self._attr_device_info = _device("metro", "Metro de Santiago")

    @property
    def native_value(self) -> str | None:
        line = self.coordinator.data.get(self._key)
        if not line:
            return None
        return "operativa" if line.operational else "con_problemas"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        line = self.coordinator.data.get(self._key)
        if not line:
            return {}
        return {
            "mensaje": line.message,
            "estaciones_con_problemas": line.stations_with_issues,
        }


class StopSensor(_Base):
    _kind = "paradero"
    _attr_icon = "mdi:bus-stop"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, entry, code: str) -> None:
        super().__init__(coordinator, entry, code)
        self._attr_name = f"Paradero {code}"
        self._attr_device_info = _device("paraderos", "Paraderos Red Movilidad")

    @property
    def native_value(self) -> int | None:
        stop = self.coordinator.data.get(self._key)
        return stop.next_minutes if stop else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stop = self.coordinator.data.get(self._key)
        if not stop:
            return {}
        return {
            "estado": stop.status,
            "recorridos": {
                s.id: {"minutos": s.next_minutes, "estado": s.status, "buses": s.buses}
                for s in stop.services
            },
        }
