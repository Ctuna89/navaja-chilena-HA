"""Sensores de Navaja Chilena."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NavajaConfigEntry, api
from .santoral import saint_of
from .const import CINEMARK_THEATERS, EPHEMERIDES_CL_URL, CRYPTO_MARKETS, DOMAIN, INDICATORS, UNIT_MAP


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
    add_when_ready(rt.bolsa, lambda data: [StockSensor(rt.bolsa, entry, "ipsa")])
    add_when_ready(
        rt.crypto,
        lambda data: [CryptoSensor(rt.crypto, entry, m) for m in data],
    )
    add_when_ready(
        rt.stops, lambda data: [StopSensor(rt.stops, entry, code) for code in data]
    )

    # Estos no necesitan datos para existir: aparecen "no disponibles" hasta tenerlos.
    fixed: list[SensorEntity] = []
    if rt.quakes:
        fixed += [QuakeSensor(rt.quakes, entry, "csn"), QuakeSensor(rt.quakes, entry, "usgs")]
    if rt.holidays:
        fixed += [
            NextHolidaySensor(rt.holidays, entry, "proximo"),
            DaysToHolidaySensor(rt.holidays, entry, "dias"),
        ]
    if rt.air:
        fixed += [AirSensor(rt.air, entry, spec) for spec in AIR_SENSORS]
    if rt.pharmacy:
        fixed.append(PharmacySensor(rt.pharmacy, entry, rt.pharmacy_comuna))
    if rt.saint:
        fixed.append(SaintSensor(entry))
    if rt.ephemerides:
        fixed += [
            EphemerisSensor(rt.ephemerides, entry, "hoy"),
            NextSignificantDaySensor(rt.ephemerides, entry, "proximo"),
        ]
    if rt.cinema:
        fixed.append(CinemaSensor(rt.cinema, entry, rt.cinema_slug))
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
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["operativa", "con_problemas", "cerrada"]
    _attr_translation_key = "metro_line"

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
            "nombre": stop.name,
            "estado": stop.status,
            "recorridos": {
                s.id: {"minutos": s.next_minutes, "estado": s.status, "buses": s.buses}
                for s in stop.services
                if s.buses
            },
            "recorridos_sin_buses": [s.id for s in stop.services if not s.buses],
        }


class QuakeSensor(_Base):
    """Último sismo. CSN: completo y en español, sin coordenadas. USGS: con mapa."""

    _kind = "sismo"
    _attr_icon = "mdi:waveform"
    _attr_native_unit_of_measurement = "M"

    def __init__(self, coordinator, entry, source: str) -> None:
        super().__init__(coordinator, entry, source)
        self._attr_name = (
            "Último sismo (CSN)" if source == "csn" else "Último sismo con coordenadas (USGS)"
        )
        self._attr_device_info = _device("sismos", "Sismos Chile")

    def _quake(self):
        quakes = (self.coordinator.data or {}).get(self._key)
        return quakes[0] if quakes else None

    def _has_data(self) -> bool:
        return self._quake() is not None

    @property
    def native_value(self) -> float | None:
        return self._quake().magnitude

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        q = self._quake()
        attrs = {"profundidad_km": q.depth_km, "referencia": q.reference, "fecha": q.date}
        if q.latitude is not None and q.longitude is not None:
            attrs |= {"latitude": q.latitude, "longitude": q.longitude}
        return attrs


class CryptoSensor(_Base):
    _kind = "cripto"
    _attr_icon = "mdi:bitcoin"
    _attr_native_unit_of_measurement = "CLP"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, market: str) -> None:
        super().__init__(coordinator, entry, market)
        self._attr_name = CRYPTO_MARKETS.get(market, market)
        self._attr_device_info = _device("cripto", "Criptomonedas (Buda)")

    @property
    def native_value(self) -> float | None:
        item = (self.coordinator.data or {}).get(self._key)
        return item.price if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = (self.coordinator.data or {}).get(self._key)
        if not item:
            return {}
        return {
            "variacion_24h_pct": item.change_24h_pct,
            "variacion_7d_pct": item.change_7d_pct,
            "volumen_24h": item.volume_24h,
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


class StockSensor(_Base):
    """Último cierre del IPSA con su variación diaria."""

    _kind = "bolsa"
    _attr_icon = "mdi:chart-line"
    _attr_name = "IPSA"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "pts"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_device_info = _device("bolsa", "Bolsa de Santiago")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    @property
    def native_value(self) -> float:
        return self.coordinator.data.value

    @property
    def icon(self) -> str:
        change = self.coordinator.data.change if self.coordinator.data else None
        if change is None or change == 0:
            return "mdi:chart-line"
        return "mdi:trending-up" if change > 0 else "mdi:trending-down"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        return {
            "variacion_puntos": d.change,
            "variacion_pct": d.change_pct,
            "fecha_cierre": d.date,
            "cierre_anterior": d.previous_value,
            "fecha_cierre_anterior": d.previous_date,
        }


class SaintSensor(SensorEntity):
    """Santo del día (santoral católico tradicional). No usa internet."""

    _attr_has_entity_name = True
    _attr_name = "Santo del día"
    _attr_icon = "mdi:cross-celtic"
    _attr_should_poll = False

    def __init__(self, entry: NavajaConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_santo"
        self._attr_device_info = _device("santoral", "Santoral")

    @property
    def native_value(self) -> str:
        return saint_of(dt_util.now().date())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date()
        return {"fecha": today.isoformat(), "mañana": saint_of(today + timedelta(days=1))}

    async def async_added_to_hass(self) -> None:
        # Se actualiza justo después de medianoche (hora de Home Assistant).
        self.async_on_remove(
            async_track_time_change(
                self.hass, lambda _now: self.async_write_ha_state(), hour=0, minute=0, second=5
            )
        )


def _hm(minutes: int | None) -> str:
    return "" if not minutes else f"{minutes // 60}h{minutes % 60:02d}"


class CinemaSensor(_Base):
    """Cartelera de hoy del cine elegido (Cinemark)."""

    _kind = "cine"
    _attr_icon = "mdi:movie-open"
    _attr_native_unit_of_measurement = "películas"

    def __init__(self, coordinator, entry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        name = CINEMARK_THEATERS[slug][0]
        self._attr_name = "Cartelera de hoy"
        self._attr_device_info = _device(f"cine_{slug}", name)
        self._theater_name = name

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    def _today(self) -> list:
        today = api.listing_day(dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)))
        return [s for s in self.coordinator.data.screenings if s.listing_day == today]

    def _movies(self) -> list[dict[str, Any]]:
        movies: dict[str, dict[str, Any]] = {}
        for s in self._today():
            m = movies.setdefault(
                s.title,
                {
                    "titulo": s.title,
                    "duracion_min": s.duration_min,
                    "genero": s.genre,
                    "poster": s.poster,
                    "url": s.url,
                    "funciones": [],
                },
            )
            m["funciones"].append(
                {"hora": s.start.strftime("%H:%M"), "formato": s.video_format, "sala": s.screen}
            )
        return list(movies.values())

    @property
    def native_value(self) -> int:
        return len(self._movies())

    def _upcoming(self):
        now = dt_util.now().astimezone(ZoneInfo(api.METRO_TZ))
        return next((s for s in self._today() if s.start >= now), None)

    @property
    def entity_picture(self) -> str | None:
        """Póster de la próxima función (o de la primera película del día)."""
        if self.coordinator.data is None:
            return None
        screening = self._upcoming() or next(iter(self._today()), None)
        return screening.poster if screening else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        movies = self._movies()
        now = dt_util.now().astimezone(ZoneInfo(api.METRO_TZ))
        upcoming = next((s for s in self._today() if s.start >= now), None)
        summary = "\n".join(
            f"{m['titulo']} ({_hm(m['duracion_min'])}): "
            + ", ".join(f["hora"] for f in m["funciones"])
            for m in movies
        )
        return {
            "cine": self._theater_name,
            "fecha": api.listing_day(now).isoformat(),
            "peliculas": movies,
            "resumen": summary,
            "proxima_funcion": (
                {
                    "titulo": upcoming.title,
                    "hora": upcoming.start.strftime("%H:%M"),
                    "poster": upcoming.poster,
                }
                if upcoming
                else None
            ),
        }


class EphemerisSensor(_Base):
    """Efemérides chilenas de hoy: efemerides.cl primero, Wikipedia como complemento."""

    _kind = "efemeride"
    _attr_icon = "mdi:calendar-text"
    _attr_name = "Efemérides de hoy"
    MAX_LISTED = 10

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_device_info = _device("efemerides", "Efemérides chilenas")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    def _items(self) -> list[dict[str, Any]]:
        d = self.coordinator.data
        items: list[dict[str, Any]] = []
        for e in d["cl"] or []:
            if e.date == d["day"]:
                items.append(
                    {
                        "anio": e.year,
                        "tipo": e.kind,
                        "texto": f"{e.title}. {e.description}" if e.description else e.title,
                        "titulo": e.title,
                        "fuente": "efemerides.cl",
                        "enlace": EPHEMERIDES_CL_URL,
                    }
                )
        for e in d["wiki"] or []:
            items.append(
                {
                    "anio": e.year,
                    "tipo": e.kind,
                    "texto": e.text,
                    "titulo": e.title,
                    "fuente": "Wikipedia (CC BY-SA 4.0)",
                    "enlace": e.url,
                }
            )
        return items

    @property
    def native_value(self) -> str:
        items = self._items()
        if not items:
            return "Sin efemérides chilenas registradas para hoy"
        first = items[0]
        title = first["titulo"] if first["fuente"] == "efemerides.cl" else first["texto"]
        text = f"{first['anio']}: {title}" if first["anio"] else title
        return text if len(text) <= 255 else text[:252] + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        items = self._items()
        shown = items[: self.MAX_LISTED]
        return {
            "fecha": d["day"].isoformat(),
            "total": len(items),
            "efemerides": shown,
            "resumen": "\n".join(
                f"{i['anio'] or '—'} · {i['titulo'] or i['texto']} ({i['fuente'].split(' ')[0]})"
                for i in shown
            ),
            "fuentes": {
                "efemerides.cl": d["cl"] is not None,
                "wikipedia": d["wiki"] is not None,
            },
        }


class NextSignificantDaySensor(_Base):
    """Próximo día significativo de Chile (efemerides.cl; solo conoce el mes en curso)."""

    _kind = "proximo_dia"
    _attr_icon = "mdi:calendar-arrow-right"
    _attr_name = "Próximo día significativo"

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_device_info = _device("efemerides", "Efemérides chilenas")

    def _next(self):
        d = self.coordinator.data
        return next((e for e in d["cl"] or [] if e.date > d["day"]), None)

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data["cl"] is not None

    @property
    def available(self) -> bool:
        return super().available and self._next() is not None

    @property
    def native_value(self) -> str:
        return self._next().title

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        nxt = self._next()
        same_day = [e.title for e in d["cl"] if e.date == nxt.date]
        return {
            "fecha": nxt.date.isoformat(),
            "dias_restantes": (nxt.date - d["day"]).days,
            "anio_del_hecho": nxt.year,
            "tipo": nxt.kind,
            "descripcion": nxt.description,
            "ese_dia": same_day,
            "fuente": "efemerides.cl",
        }
