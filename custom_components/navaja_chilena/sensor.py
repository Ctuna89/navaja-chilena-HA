"""Sensores de Navaja Chilena."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NavajaConfigEntry, api
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

    def add_when_ready(coordinator, make) -> None:
        """Crea las entidades al tener datos; si la fuente está caída, cuando vuelva."""
        if coordinator is None:
            return
        if coordinator.data is not None:
            async_add_entities(make(coordinator.data))
            return

        @callback
        def _listener() -> None:
            if coordinator.data is not None:
                unsub()
                async_add_entities(make(coordinator.data))

        unsub = coordinator.async_add_listener(_listener)
        entry.async_on_unload(unsub)

    add_when_ready(
        rt.indicators,
        lambda data: [
            IndicatorSensor(rt.indicators, entry, code)
            for code in rt.indicator_codes
            if code in data
        ],
    )
    add_when_ready(
        rt.metro,
        lambda data: [
            MetroLineSensor(rt.metro, entry, line_id, rt.holidays) for line_id in data
        ],
    )
    add_when_ready(
        rt.stops, lambda data: [StopSensor(rt.stops, entry, code) for code in data]
    )

    # Estos no necesitan datos para existir: aparecen "no disponibles" hasta tenerlos.
    fixed: list[SensorEntity] = []
    if rt.quakes:
        fixed.append(QuakeSensor(rt.quakes, entry, "ultimo"))
    if rt.holidays:
        fixed += [
            NextHolidaySensor(rt.holidays, entry, "proximo"),
            DaysToHolidaySensor(rt.holidays, entry, "dias"),
        ]
    if rt.air:
        fixed += [AirSensor(rt.air, entry, spec) for spec in AIR_SENSORS]
    if rt.pharmacy:
        fixed.append(PharmacySensor(rt.pharmacy, entry, rt.pharmacy_comuna))
    async_add_entities(fixed)


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
    """Línea de Metro: operativa, con_problemas o cerrada (fuera de horario)."""

    _kind = "metro"
    _attr_icon = "mdi:subway-variant"

    def __init__(self, coordinator, entry, line_id: str, holidays=None) -> None:
        super().__init__(coordinator, entry, line_id)
        self._holidays = holidays
        self._attr_name = coordinator.data[line_id].name
        self._attr_device_info = _device("metro", "Metro de Santiago")

    def _has_data(self) -> bool:
        line = (self.coordinator.data or {}).get(self._key)
        return line is not None and line.operational is not None

    def _is_holiday(self) -> bool:
        data = self._holidays.data if self._holidays else None
        return bool(data and data.get("is_holiday_today"))

    def _is_open(self) -> bool:
        return api.metro_is_open(holiday=self._is_holiday())

    @property
    def native_value(self) -> str | None:
        line = self.coordinator.data.get(self._key)
        if not line:
            return None
        if not self._is_open():
            return "cerrada"
        return "operativa" if line.operational else "con_problemas"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        line = self.coordinator.data.get(self._key)
        if not line:
            return {}
        now = datetime.now(ZoneInfo(api.METRO_TZ))
        opens, closes = api.metro_hours(now, self._is_holiday())
        is_open = self._is_open()
        if is_open:
            stations = {
                n: "operativa" if ok else "con_problemas" for n, ok in line.stations.items()
            }
        else:
            stations = {n: "cerrada" for n in line.stations}
        return {
            "mensaje": line.message if is_open else "Fuera de horario de servicio",
            "estaciones_con_problemas": line.stations_with_issues if is_open else [],
            "estaciones": stations,
            "horario_apertura": opens.strftime("%H:%M"),
            "horario_cierre": closes.strftime("%H:%M"),
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
        self._attr_name = comuna
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
