"""Base común de las entidades del vehículo (restricción vehicular y revisión técnica)."""

from __future__ import annotations

from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import vehicle
from .const import DOMAIN

TZ = ZoneInfo("America/Santiago")

# Texto legible de cada motivo (clave de vehicle.Status.reason)
REASON_TEXT = {
    vehicle.RESTRICTED: "Tu dígito está restringido hoy",
    vehicle.FREE_DIGIT: "Tu dígito no está restringido hoy",
    vehicle.OFF_SEASON: "Fuera de la temporada de restricción",
    vehicle.WEEKEND: "Fin de semana: no hay restricción",
    vehicle.HOLIDAY: "Festivo: no hay restricción",
    vehicle.EXEMPT: "Tu tipo de vehículo no tiene restricción",
    vehicle.NO_RESOLUTION: "Aún no se carga la resolución de este año",
}


class VehicleMixin:
    """Entidad sin consulta a internet: se recalcula al cambiar el día y la hora de la medida."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def _setup_vehicle(self, entry: Any, runtime: Any, key: str) -> None:
        self._rt = runtime
        self._attr_unique_id = f"{entry.entry_id}_vehiculo_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "vehiculo")},
            name="Mi vehículo",
            manufacturer="Navaja Chilena",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def digit(self) -> int:
        return self._rt.vehicle_digit

    @property
    def vehicle_type(self) -> str:
        return self._rt.vehicle_type

    def now(self):
        return dt_util.now().astimezone(TZ)

    def today(self) -> date:
        return self.now().date()

    def holidays(self) -> frozenset[date]:
        coordinator = self._rt.holidays
        data = coordinator.data if coordinator is not None else None
        return data["all"] if data and "all" in data else frozenset()

    def holidays_known(self) -> bool:
        coordinator = self._rt.holidays
        return bool(coordinator is not None and coordinator.data and "all" in coordinator.data)

    def status(self) -> vehicle.Status:
        return vehicle.status_on(self.vehicle_type, self.digit, self.today(), self.holidays())

    async def async_added_to_hass(self) -> None:
        @callback
        def refresh(*_: Any) -> None:
            self.async_write_ha_state()

        for hour, minute, second in ((0, 0, 5), (vehicle.WINDOW_START.hour, vehicle.WINDOW_START.minute, 1),
                                     (vehicle.WINDOW_END.hour, vehicle.WINDOW_END.minute, 1)):
            self.async_on_remove(
                async_track_time_change(self.hass, refresh, hour=hour, minute=minute, second=second)
            )
        if self._rt.holidays is not None:
            self.async_on_remove(self._rt.holidays.async_add_listener(self.async_write_ha_state))
