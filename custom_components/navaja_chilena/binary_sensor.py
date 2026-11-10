"""Sensores binarios del vehículo: restricción hoy y revisión técnica este mes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NavajaConfigEntry, vehicle
from .const import REGIONAL_ZONES
from .sensor import _device, _digits_text
from .vehicle_entity import REASON_TEXT, VehicleMixin


async def async_setup_entry(
    hass: HomeAssistant, entry: NavajaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
    if rt.regional:
        known = rt.regional.data

        def _add(codes) -> None:
            async_add_entities([RegionalAlertBinarySensor(rt.regional, entry, c, rt.regional_zone) for c in codes])

        if known is not None:
            _add(known)
        else:
            @callback
            def _listener() -> None:
                if rt.regional.data is not None:
                    unsub()
                    _add(rt.regional.data)

            unsub = rt.regional.async_add_listener(_listener)
            entry.async_on_unload(unsub)
    if rt.vehicle_digit is not None:
        async_add_entities(
            [RestrictionTodayBinarySensor(entry, rt, "restriccion"), RevisionThisMonthBinarySensor(entry, rt, "revision_mes")]
        )


class RestrictionTodayBinarySensor(VehicleMixin, BinarySensorEntity):
    """Encendido si tu vehículo tiene restricción hoy."""

    _attr_name = "Restricción vehicular hoy"
    _attr_translation_key = "restriction_today"

    def __init__(self, entry, runtime, key: str) -> None:
        self._setup_vehicle(entry, runtime, key)

    @property
    def available(self) -> bool:
        return self.status().restricted is not None

    @property
    def is_on(self) -> bool:
        return bool(self.status().restricted)

    @property
    def icon(self) -> str:
        return "mdi:car-off" if self.is_on else "mdi:car"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.status()
        now = self.now()
        return {
            "motivo": REASON_TEXT[st.reason],
            "digitos_hoy": _digits_text(st.digits),
            "tu_digito": self.digit,
            "rige_ahora": bool(st.restricted) and vehicle.window_active(now.time()),
            "horario": f"{vehicle.WINDOW_START:%H:%M}–{vehicle.WINDOW_END:%H:%M}",
            "tipo_de_vehiculo": vehicle.VEHICLE_TYPES[self.vehicle_type],
            "festivos_considerados": self.holidays_known(),
            "fuente": "Resolución Exenta N° 1698/2026 SRM-RM (MTT)",
            "aviso": "No incluye los dígitos adicionales de preemergencia o emergencia ambiental.",
        }


class RevisionThisMonthBinarySensor(VehicleMixin, BinarySensorEntity):
    """Encendido si este mes es el de preferencia para la revisión técnica de tu patente."""

    _attr_name = "Revisión técnica este mes"
    _attr_translation_key = "revision_this_month"
    _attr_icon = "mdi:car-wrench"

    def __init__(self, entry, runtime, key: str) -> None:
        self._setup_vehicle(entry, runtime, key)

    @property
    def is_on(self) -> bool:
        return vehicle.months_until_revision(self.digit, self.today()) == 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "mes_de_preferencia": vehicle.MONTH_NAMES[vehicle.revision_month(self.digit) - 1].capitalize(),
            "meses_restantes": vehicle.months_until_revision(self.digit, self.today()),
        }


class RegionalAlertBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Encendido si el servicio informa alertas que afectan al paradero."""

    _attr_has_entity_name = True
    _attr_name = "Alertas del servicio"
    _attr_icon = "mdi:bus-alert"

    def __init__(self, coordinator, entry, code: str, zone: str) -> None:
        super().__init__(coordinator)
        self._code = code
        self._attr_unique_id = f"{entry.entry_id}_alerta_regional_{zone}_{code}"
        self._attr_device_info = _device(f"regional_{zone}", f"Paraderos Red Regional: {REGIONAL_ZONES[zone][1]}")

    @property
    def available(self) -> bool:
        return super().available and self._code in (self.coordinator.data or {})

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data[self._code].alerts)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"alertas": list(self.coordinator.data[self._code].alerts), "paradero": self._code}
