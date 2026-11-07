"""Sensores de Navaja Chilena."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
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

    if rt.quakes:
        entities.append(QuakeSensor(rt.quakes, entry, "ultimo"))
    if rt.holidays:
        entities += [
            NextHolidaySensor(rt.holidays, entry, "proximo"),
            DaysToHolidaySensor(rt.holidays, entry, "dias"),
        ]
    if rt.air:
        entities += [AirSensor(rt.air, entry, spec) for spec in AIR_SENSORS]
    if rt.pharmacy:
        entities.append(PharmacySensor(rt.pharmacy, entry, rt.pharmacy_comuna))

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
        return super().available and self._has_data()

    def _has_data(self) -> bool:
        return self._key in (self.coordinator.data or {})


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


class QuakeSensor(_Base):
    """Último sismo; con latitude/longitude para la tarjeta de mapa."""

    _kind = "sismo"
    _attr_icon = "mdi:waveform"
    _attr_name = "Último sismo"
    _attr_native_unit_of_measurement = "M"

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_device_info = _device("sismos", "Sismos Chile")

    def _has_data(self) -> bool:
        return bool(self.coordinator.data)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data[0].magnitude

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        q = self.coordinator.data[0]
        return {
            "latitude": q.latitude,
            "longitude": q.longitude,
            "profundidad_km": q.depth_km,
            "referencia": q.reference,
            "fecha": q.date,
        }


class _HolidayBase(_Base):
    _kind = "feriado"

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_device_info = _device("feriados", "Feriados Chile")

    def _has_data(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data["next"])


class NextHolidaySensor(_HolidayBase):
    _attr_icon = "mdi:calendar-star"
    _attr_name = "Próximo feriado"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self):
        return self.coordinator.data["next"].date

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        h = self.coordinator.data["next"]
        return {
            "nombre": h.name,
            "tipo": h.kind,
            "irrenunciable": h.inalienable,
            "es_hoy": self.coordinator.data["is_holiday_today"],
        }


class DaysToHolidaySensor(_HolidayBase):
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Días para el próximo feriado"
    _attr_native_unit_of_measurement = "d"

    @property
    def native_value(self) -> int:
        d = self.coordinator.data
        return (d["next"].date - d["today"]).days


AIR_SENSORS = (
    # (clave, nombre, atributo, device_class, unidad, icono)
    ("pm2_5", "PM2.5", "pm2_5", SensorDeviceClass.PM25, "µg/m³", None),
    ("pm10", "PM10", "pm10", SensorDeviceClass.PM10, "µg/m³", None),
    ("aqi", "Índice de calidad del aire (US AQI)", "aqi", SensorDeviceClass.AQI, None, None),
    ("uv", "Índice UV", "uv_index", None, "UV index", "mdi:weather-sunny-alert"),
)


class AirSensor(_Base):
    _kind = "aire"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, spec) -> None:
        key, name, self._field, dclass, unit, icon = spec
        super().__init__(coordinator, entry, key)
        self._attr_name = name
        self._attr_device_class = dclass
        self._attr_native_unit_of_measurement = unit
        if icon:
            self._attr_icon = icon
        self._attr_device_info = _device("aire", "Calidad del aire y UV")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    @property
    def native_value(self) -> float | None:
        return getattr(self.coordinator.data, self._field)


class PharmacySensor(_Base):
    _kind = "farmacias"
    _attr_icon = "mdi:pharmacy"
    _attr_native_unit_of_measurement = "farmacias"
    MAX_LISTED = 20

    def __init__(self, coordinator, entry, comuna: str) -> None:
        super().__init__(coordinator, entry, comuna.lower())
        self._attr_name = f"Farmacias de turno {comuna}"
        self._attr_device_info = _device("farmacias", "Farmacias de turno")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "farmacias": [
                {
                    "nombre": p.name,
                    "direccion": p.address,
                    "telefono": p.phone,
                    "apertura": p.opens,
                    "cierre": p.closes,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                }
                for p in self.coordinator.data[: self.MAX_LISTED]
            ]
        }
