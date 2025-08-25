# Author: duvob90
from __future__ import annotations
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TITLE, CONF_STOP_IDS, METRO_KNOWN_LINES
from .coordinator import NavajaCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NavajaCoordinator = data["coordinator"]

    entities: list[SensorEntity] = []
    entities.append(UsdSensor(coordinator, entry))
    entities.append(UfSensor(coordinator, entry))
    entities.append(QuakeSensor(coordinator, entry))

    # Metro per-line sensors
    metro_lines = (coordinator.data.get("metro_lines") or {}).keys()
    line_ids = list(metro_lines) if metro_lines else METRO_KNOWN_LINES
    for lid in line_ids:
        entities.append(MetroLineSensor(coordinator, entry, lid))

    # Bus stop sensors
    stops_str = entry.options.get(CONF_STOP_IDS, entry.data.get(CONF_STOP_IDS, ""))
    stop_ids = [s.strip() for s in stops_str.split(",") if s.strip()]
    for sid in stop_ids:
        entities.append(BusStopSensor(coordinator, entry, sid))

    async_add_entities(entities)

class NavajaBase(CoordinatorEntity[NavajaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NavajaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=TITLE,
            manufacturer="duvob90",
            model="Navaja Chilena",
        )

class UsdSensor(NavajaBase):
    @property
    def name(self) -> str:
        return "USD (CLP)"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_usd"

    @property
    def icon(self) -> str:
        return "mdi:currency-usd"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return "CLP"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("usd")

class UfSensor(NavajaBase):
    @property
    def name(self) -> str:
        return "UF (CLP)"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_uf"

    @property
    def icon(self) -> str:
        return "mdi:cash-100"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return "CLP"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("uf")

class MetroLineSensor(NavajaBase):
    def __init__(self, coordinator: NavajaCoordinator, entry: ConfigEntry, line_id: str) -> None:
        super().__init__(coordinator, entry)
        self._line_id = line_id.upper()

    @property
    def name(self) -> str:
        return f"Metro {self._line_id}"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_metro_{self._line_id}"

    @property
    def icon(self) -> str:
        return "mdi:subway-variant"

    @property
    def native_value(self) -> Any:
        lines = self.coordinator.data.get("metro_lines") or {}
        return lines.get(self._line_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        details = (self.coordinator.data.get("metro_details") or {}).get(self._line_id) or {}
        return details if details else None

class QuakeSensor(NavajaBase):
    @property
    def name(self) -> str:
        return "Último Sismo (Chile)"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_quake"

    @property
    def icon(self) -> str:
        return "mdi:earth"

    @property
    def native_value(self) -> Any:
        q = self.coordinator.data.get("sismo") or {}
        return q.get("state")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        q = self.coordinator.data.get("sismo") or {}
        return q.get("attr") or {}

class BusStopSensor(NavajaBase):
    def __init__(self, coordinator: NavajaCoordinator, entry: ConfigEntry, stop_id: str) -> None:
        super().__init__(coordinator, entry)
        self._stop_id = stop_id

    @property
    def name(self) -> str:
        return f"Paradero {self._stop_id}"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_bus_{self._stop_id}"

    @property
    def icon(self) -> str:
        return "mdi:bus-clock"

    @property
    def native_value(self) -> Any:
        buses = (self.coordinator.data.get("buses") or {}).get(self._stop_id) or {}
        arrivals = buses.get("arrivals") or []
        if arrivals:
            first = arrivals[0]
            eta = first.get("eta")
            route = first.get("route") or ""
            dest = first.get("dest") or ""
            if eta and route:
                return f"{route} → {dest} ({eta})"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        buses = (self.coordinator.data.get("buses") or {}).get(self._stop_id) or {}
        name = buses.get("name") or self._stop_id
        arrivals = buses.get("arrivals") or []
        return {"paradero": name, "stop_id": self._stop_id, "arrivals": arrivals}
