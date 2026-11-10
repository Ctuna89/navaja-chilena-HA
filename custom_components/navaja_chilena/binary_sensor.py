"""Sensores binarios del vehículo: restricción hoy y revisión técnica este mes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NavajaConfigEntry, vehicle
from .sensor import _digits_text
from .vehicle_entity import REASON_TEXT, VehicleMixin


async def async_setup_entry(
    hass: HomeAssistant, entry: NavajaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
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
