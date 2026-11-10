"""Tren Limache–Puerto (EFE Valparaíso): coordinador y sensores.

Todo el módulo vive aquí y en `efe_train.py`; el resto de la integración solo lo
llama si el usuario configuró trayectos.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import api, efe_train
from .const import DOMAIN
from .coordinator import NavajaCoordinator

_LOGGER = logging.getLogger(__name__)

NO_SERVICES = "Sin servicios informados"


def train_coordinator(hass: HomeAssistant, trips: list[tuple[int, int]]) -> NavajaCoordinator:
    """Consulta cada trayecto; si uno falla, conserva el resto.

    La clave de cada trayecto es «origen-destino» con los IDs de estación de EFE.
    """
    ssl_context = None

    async def fetch(session: Any) -> dict[str, efe_train.Departures]:
        nonlocal ssl_context
        if ssl_context is None:  # cargar certificados bloquea: se hace una vez, fuera del loop
            ssl_context = await hass.async_add_executor_job(efe_train.create_ssl_context)
        result: dict[str, efe_train.Departures] = {}
        errors: list[str] = []
        for origin, destination in trips:
            try:
                result[f"{origin}-{destination}"] = await efe_train.fetch_departures(
                    session, ssl_context, origin, destination, dt_util.now()
                )
            except api.NavajaApiError as err:
                errors.append(
                    f"{efe_train.STATIONS[origin]} > {efe_train.STATIONS[destination]}: {err}"
                )
        if not result:
            raise api.NavajaApiError("; ".join(errors) or "sin datos")
        if errors:
            _LOGGER.warning("Trayectos de tren con error: %s", "; ".join(errors))
        return result

    return NavajaCoordinator(hass, "tren", efe_train.TRAIN_INTERVAL, fetch)


def train_sensors(coordinator, entry, trips: list[tuple[int, int]]) -> list[SensorEntity]:
    return [TrainSensor(coordinator, entry, o, d) for o, d in trips]


class TrainSensor(CoordinatorEntity, SensorEntity):
    """Próximo tren de un trayecto: el texto de EFE («6 minutos», «cercano»), sin reinterpretar.

    «Sin servicios informados» es una respuesta válida con la lista vacía; si EFE
    no responde, el sensor queda no disponible.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:train"
    # La lista completa cambia en cada consulta; no se guarda en el historial.
    _unrecorded_attributes = frozenset({"servicios", "operabilidad", "aviso", "consultado_en"})

    def __init__(self, coordinator, entry, origin: int, destination: int) -> None:
        super().__init__(coordinator)
        self._key = f"{origin}-{destination}"
        self._origin = origin
        self._destination = destination
        # Mismo formato de id único y de dispositivo que el resto de Navaja Chilena.
        self._attr_unique_id = f"{entry.entry_id}_tren_{self._key}"
        self._attr_name = f"{efe_train.STATIONS[origin]} → {efe_train.STATIONS[destination]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "tren")},
            name="Tren Limache–Puerto",
            manufacturer="Navaja Chilena",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return super().available and self._key in (self.coordinator.data or {})

    @property
    def native_value(self) -> str:
        data = self.coordinator.data[self._key]
        return str(data.services[0].get("tiempo")) if data.services else NO_SERVICES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data[self._key]
        first = data.services[0] if data.services else {}
        return {
            "origen": efe_train.STATIONS[self._origin],
            "destino": efe_train.STATIONS[self._destination],
            "consultado_en": data.fetched_at.isoformat() if data.fetched_at else None,
            "hasta": first.get("hasta"),
            "llega_a_destino": first.get("llega_a_destino"),
            "minutos": first.get("minutos"),
            "hora_estimada": first.get("hora_estimada"),
            "tipo": first.get("tipo"),
            "servicios_informados": len(data.services),
            "servicios": data.services,
            "estado_consulta": data.state,
            "aviso_efe": data.warning,
            "operabilidad": data.operability,
            "tiempo_real_confirmado": False,
            "aviso": efe_train.NOTICE,
        }
