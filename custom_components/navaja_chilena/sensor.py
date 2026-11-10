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
from . import vehicle
from .vehicle_entity import REASON_TEXT, VehicleMixin
from .api import FUEL_LABELS
from .const import FOOTBALL_TEAMS, NATIONAL_TEAM_ID
from .const import NEWS_TOPICS, REGIONAL_ZONES, BENEFIT_CATEGORIES, BENEFITS_SITE, CINEMARK_THEATERS, EPHEMERIDES_CL_URL, CRYPTO_MARKETS, DOMAIN, INDICATORS, UNIT_MAP


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
    if rt.holidays and rt.holidays_visible:
        fixed += [
            NextHolidaySensor(rt.holidays, entry, "proximo"),
            DaysToHolidaySensor(rt.holidays, entry, "dias"),
        ]
    if rt.air:
        fixed += [AirSensor(rt.air, entry, spec) for spec in AIR_SENSORS]
    if rt.pharmacy:
        fixed.append(PharmacySensor(rt.pharmacy, entry, rt.pharmacy_comuna))
    if rt.football:
        if rt.football_team:
            name = FOOTBALL_TEAMS[rt.football_team]
            dev = f"Fútbol: {name}"
            fixed += [
                NextMatchSensor(rt.football, entry, rt.football_team, dev, "team_fixtures", "team_results"),
                LastResultSensor(rt.football, entry, rt.football_team, dev, "team_results"),
                PositionSensor(rt.football, entry, rt.football_team, dev),
            ]
        if rt.football_league:
            fixed += [
                LeagueTableSensor(rt.football, entry),
                LeagueNextRoundSensor(rt.football, entry),
                LeagueLastRoundSensor(rt.football, entry),
            ]
    if rt.national:
        fixed += [
            NextMatchSensor(rt.national, entry, NATIONAL_TEAM_ID, "Fútbol: La Roja", "fixtures", "results"),
            LastResultSensor(rt.national, entry, NATIONAL_TEAM_ID, "Fútbol: La Roja", "results"),
        ]
    add_when_ready(
        rt.regional,
        lambda data: [RegionalStopSensor(rt.regional, entry, code, rt.regional_zone) for code in data],
    )
    if rt.news:
        fixed += [NewsSensor(rt.news, entry, topic) for topic in rt.news_topics]
    if rt.fuel_discounts:
        fixed.append(FuelDiscountSensor(rt.fuel_discounts, entry, rt.benefit_cards))
    if rt.benefits:
        fixed += [BenefitsSensor(rt.benefits, entry, cat) for cat in rt.benefit_categories]
    if rt.fuel:
        fixed += [FuelSensor(rt.fuel, entry, fuel, rt.fuel_radius, rt.fuel_max_age) for fuel in rt.fuel_types]
    if rt.saint:
        fixed.append(SaintSensor(entry))
    if rt.vehicle_digit is not None:
        fixed += [
            VehicleDigitsSensor(entry, rt, "digitos"),
            NextRestrictionSensor(entry, rt, "proxima"),
            RevisionMonthSensor(entry, rt, "revision"),
        ]
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


class RegionalStopSensor(_Base):
    """Próxima llegada a un paradero de la Red Regional (ciudades fuera de Santiago)."""

    _kind = "paradero_regional"
    _attr_icon = "mdi:bus-stop"
    _attr_native_unit_of_measurement = "min"
    MAX_LISTED = 8

    def __init__(self, coordinator, entry, code: str, zone: str) -> None:
        super().__init__(coordinator, entry, f"{zone}_{code}")
        self._code = code
        self._zone = zone
        self._attr_name = f"Paradero {code}"
        self._attr_device_info = _device(f"regional_{zone}", f"Paraderos Red Regional: {REGIONAL_ZONES[zone][1]}")

    def _has_data(self) -> bool:
        return self._code in (self.coordinator.data or {})

    def _stop(self):
        return self.coordinator.data[self._code]

    @property
    def native_value(self) -> int | None:
        stop = self._stop()
        if not stop.arrivals:
            return None
        return max(0, round((stop.arrivals[0].eta - dt_util.utcnow()).total_seconds() / 60))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stop = self._stop()
        now = dt_util.utcnow()
        return {
            "nombre": stop.name,
            "ciudad": REGIONAL_ZONES[self._zone][1],
            "proximas": [
                {
                    "servicio": a.route,
                    "sentido": a.direction,
                    "llegada": a.eta.isoformat(),
                    "minutos": max(0, round((a.eta - now).total_seconds() / 60)),
                    "estimacion": a.label,
                    "tiempo_real": a.realtime,
                    "distancia": a.distance,
                }
                for a in stop.arrivals[: self.MAX_LISTED]
            ],
            "alertas": list(stop.alerts),
            "fuente": "Red Regional / TransApp (servicio no oficial)",
        }


class NewsSensor(_Base):
    """Titulares de un tema (La Tercera y Cooperativa): el valor es el más reciente."""

    _kind = "noticias"
    _attr_icon = "mdi:newspaper-variant-outline"

    def __init__(self, coordinator, entry, topic: str) -> None:
        super().__init__(coordinator, entry, topic)
        self._attr_name = f"Titulares: {NEWS_TOPICS[topic]}"
        self._attr_device_info = _device("noticias", "Noticias")

    def _has_data(self) -> bool:
        return self._key in (self.coordinator.data or {})

    def _items(self) -> list[api.NewsItem]:
        return self.coordinator.data[self._key]

    @property
    def native_value(self) -> str | None:
        items = self._items()
        if not items:
            return None
        title = items[0].title
        return title if len(title) <= 255 else title[:254].rstrip() + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tz = ZoneInfo(api.METRO_TZ)
        return {
            "medio": self._items()[0].source if self._items() else None,
            "enlace": self._items()[0].url if self._items() else None,
            "titulares": [
                {
                    "titulo": n.title,
                    "medio": n.source,
                    "enlace": n.url,
                    "hora": n.published.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                    "resumen": n.summary,
                }
                for n in self._items()
            ],
            "fuente": "La Tercera y Cooperativa.cl (feeds RSS públicos)",
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
        @callback
        def _refresh(_now: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(self.hass, _refresh, hour=0, minute=0, second=5)
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


def _digits_text(digits: frozenset[int] | None) -> str:
    if not digits:
        return "Ninguno"
    if digits == vehicle.ALL_DIGITS:
        return "Todos"
    return "-".join(str(d) for d in sorted(digits))


class VehicleDigitsSensor(VehicleMixin, SensorEntity):
    """Dígitos de patente con restricción hoy (según el tipo de vehículo configurado)."""

    _attr_icon = "mdi:car-clock"
    _attr_name = "Dígitos con restricción hoy"

    def __init__(self, entry, runtime, key: str) -> None:
        self._setup_vehicle(entry, runtime, key)

    @property
    def available(self) -> bool:
        return self.status().restricted is not None

    @property
    def native_value(self) -> str:
        return _digits_text(self.status().digits)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.status()
        return {
            "motivo": REASON_TEXT[st.reason],
            "tu_digito": self.digit,
            "horario": f"{vehicle.WINDOW_START:%H:%M}–{vehicle.WINDOW_END:%H:%M}",
            "tipo_de_vehiculo": vehicle.VEHICLE_TYPES[self.vehicle_type],
        }


class NextRestrictionSensor(VehicleMixin, SensorEntity):
    """Próxima fecha con restricción para tu dígito (dentro de la temporada vigente)."""

    _attr_icon = "mdi:calendar-alert"
    _attr_name = "Próxima restricción"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, entry, runtime, key: str) -> None:
        self._setup_vehicle(entry, runtime, key)

    def _next(self):
        return vehicle.next_restriction(self.vehicle_type, self.digit, self.today(), self.holidays())

    @property
    def native_value(self):
        return self._next()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nxt = self._next()
        season = vehicle.season(self.today().year)
        attrs: dict[str, Any] = {
            "temporada": f"{season[0]:%d-%m-%Y} al {season[1]:%d-%m-%Y}" if season else None,
            "festivos_considerados": self.holidays_known(),
        }
        if nxt is not None:
            attrs["dias_restantes"] = (nxt - self.today()).days
            attrs["es_hoy"] = nxt == self.today()
        else:
            attrs["motivo"] = (
                "Tu tipo de vehículo no tiene restricción"
                if self.vehicle_type == "sello_verde_posterior"
                else "No quedan días de restricción en la temporada vigente"
            )
        return attrs


class RevisionMonthSensor(VehicleMixin, SensorEntity):
    """Mes de preferencia para la revisión técnica según el último dígito de la patente."""

    _attr_icon = "mdi:car-wrench"
    _attr_name = "Mes de revisión técnica"

    def __init__(self, entry, runtime, key: str) -> None:
        self._setup_vehicle(entry, runtime, key)

    @property
    def native_value(self) -> str:
        return vehicle.MONTH_NAMES[vehicle.revision_month(self.digit) - 1].capitalize()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        months = vehicle.months_until_revision(self.digit, self.today())
        return {
            "tu_digito": self.digit,
            "meses_restantes": months,
            "este_mes": months == 0,
            "nota": "Mes de preferencia en las plantas, no una fecha límite: tu plazo depende del certificado anterior.",
            "fuente": "ChileAtiende (Subsecretaría de Transportes)",
        }


class FuelDiscountSensor(_Base):
    """Descuentos en bencina de hoy con tus tarjetas (calendario mensual)."""

    _kind = "descuento_bencina"
    _attr_icon = "mdi:gas-station-outline"
    _attr_native_unit_of_measurement = "descuentos"

    def __init__(self, coordinator, entry, cards: list[str]) -> None:
        super().__init__(coordinator, entry, "hoy")
        self._cards = cards
        self._attr_name = "Descuentos en bencina hoy"
        self._attr_device_info = _device("combustibles", "Combustibles")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    def _today(self):
        return dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)).date()

    def _current(self) -> bool:
        return api.fuel_discounts_current(self.coordinator.data, self._today())

    @staticmethod
    def _brief(d: api.FuelDiscount) -> dict[str, Any]:
        return {
            "estaciones": list(d.stations),
            "tarjeta": d.card_name,
            "descuento": d.amount,
            "detalle": d.detail,
            "confirmado": d.confirmed,
            "fuente": d.source,
        }

    @property
    def native_value(self) -> int | None:
        if not self._current():
            return None   # calendario de otro mes: no se muestra como vigente
        return len(api.fuel_discounts_for(self.coordinator.data, self._cards, self._today())[0])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cal = self.coordinator.data
        attrs: dict[str, Any] = {
            "calendario": cal.month,
            "actualizado": cal.updated,
            "fuente": "Calendario mensual de Navaja Chilena (cada descuento indica su fuente)",
        }
        if not self._current():
            attrs["motivo"] = f"El calendario de descuentos es de {cal.month}; está pendiente su actualización mensual"
            return attrs
        today, nxt, upcoming = api.fuel_discounts_for(cal, self._cards, self._today())
        savings = [d.saving_clp_l for d in today if d.saving_clp_l]
        attrs.update(
            {
                "hoy": [self._brief(d) for d in today],
                "mejor_ahorro_clp_litro": max(savings) if savings else None,
                "proximo_dia": api.DAY_NAMES[nxt - 1] if nxt else None,
                "proximo": [self._brief(d) for d in upcoming],
                "aviso": "Revisa condiciones, topes y activaciones en el sitio del emisor o de la estación.",
            }
        )
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _refresh(_now: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(async_track_time_change(self.hass, _refresh, hour=0, minute=0, second=5))


class BenefitsSensor(_Base):
    """Descuentos de hoy, de tus tarjetas, en una categoría (N Beneficios)."""

    _kind = "descuentos"
    _attr_icon = "mdi:credit-card-check-outline"
    _attr_native_unit_of_measurement = "descuentos"
    MAX_LISTED = 15

    def __init__(self, coordinator, entry, category: str) -> None:
        super().__init__(coordinator, entry, category)
        self._category = category
        self._attr_name = f"Descuentos de hoy: {BENEFIT_CATEGORIES[category]}"
        self._attr_device_info = _device("descuentos", "Descuentos de tarjetas")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    def _today_date(self):
        return dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)).date()

    def _split(self) -> tuple[list[api.Benefit], list[api.Benefit], list[api.Benefit]]:
        mine = [b for b in self.coordinator.data if b.category == self._category]
        d = self._today_date()
        today = [b for b in mine if b.applies_on(d.weekday(), d.month, d) is True]
        unknown = [b for b in mine if b.applies_on(d.weekday(), d.month, d) is None]
        return mine, today, unknown

    @property
    def native_value(self) -> int:
        return len(self._split()[1])

    @staticmethod
    def _brief(b: api.Benefit) -> dict[str, Any]:
        return {
            "comercio": b.merchant,
            "tarjeta": b.card,
            "descuento": b.title,
            "detalle": b.detail,
            "url": b.url,
            "imagen": b.image,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mine, today, unknown = self._split()
        return {
            "hoy": [self._brief(b) for b in today[: self.MAX_LISTED]],
            "sin_dia_indicado": [self._brief(b) for b in unknown[: self.MAX_LISTED]],
            "total_en_categoria": len(mine),
            "aviso": "Revisa las condiciones de cada beneficio en el sitio del emisor.",
            "fuente": f"N Beneficios ({BENEFITS_SITE})",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _refresh(_now: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(async_track_time_change(self.hass, _refresh, hour=0, minute=0, second=5))


class FuelSensor(_Base):
    """Precio más bajo de un combustible en las estaciones cercanas a tu casa."""

    _kind = "combustible"
    _attr_icon = "mdi:gas-station"
    _attr_native_unit_of_measurement = "CLP/L"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    TOP = 5

    def __init__(self, coordinator, entry, fuel: str, radius: float, max_age: int) -> None:
        super().__init__(coordinator, entry, fuel)
        self._fuel = fuel
        self._radius = radius
        self._max_age = max_age
        self._attr_name = f"{FUEL_LABELS[fuel]} más barat{'o' if fuel == 'DI' else 'a'}"
        self._attr_device_info = _device("combustibles", "Combustibles")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    def _candidates(self) -> list[api.FuelCandidate]:
        cfg = self.coordinator.hass.config
        return api.cheapest_nearby(
            self.coordinator.data, self._fuel, cfg.latitude, cfg.longitude, self._radius, dt_util.now(), self._max_age
        )

    @property
    def native_value(self) -> float | None:
        found = self._candidates()
        return found[0].price.price if found else None

    @property
    def entity_picture(self) -> str | None:
        found = self._candidates() if self.coordinator.data is not None else []
        return found[0].station.logo if found else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        found = self._candidates()
        attrs: dict[str, Any] = {
            "radio_km": self._radius,
            "max_antiguedad_dias": self._max_age,
            "estaciones_en_radio": len(found),
            "fuente": "Bencina en Línea (Comisión Nacional de Energía)",
        }
        if not found:
            attrs["motivo"] = f"No hay estaciones con un precio de los últimos {self._max_age} días a {self._radius:g} km de tu casa"
            return attrs
        best = found[0]
        attrs.update(
            {
                "marca": best.station.brand,
                "direccion": best.station.address,
                "comuna": best.station.commune,
                "distancia_km": round(best.distance_km, 1),
                "atencion": best.price.attention,
                "antiguedad_dias": (dt_util.now() - best.price.updated).days if best.price.updated else None,
                "actualizado": best.price.updated.strftime("%Y-%m-%d %H:%M") if best.price.updated else None,
                "latitude": best.station.lat,
                "longitude": best.station.lon,
                "promedio_en_radio": round(sum(c.price.price for c in found) / len(found)),
                "mas_baratas": [
                    {
                        "precio": c.price.price,
                        "marca": c.station.brand,
                        "direccion": c.station.address,
                        "comuna": c.station.commune,
                        "distancia_km": round(c.distance_km, 1),
                        "atencion": c.price.attention,
                        "actualizado": c.price.updated.strftime("%Y-%m-%d") if c.price.updated else None,
                    }
                    for c in found[: self.TOP]
                ],
            }
        )
        return attrs


# ----------------------------------------------------------------------- Fútbol

_WEEKDAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def _when(moment: datetime) -> str:
    local = moment.astimezone(ZoneInfo(api.METRO_TZ))
    return f"{_WEEKDAYS[local.weekday()]} {local:%d-%m} {local:%H:%M}"


def _round_item(m: api.Match) -> dict[str, Any]:
    return {
        "local": m.home.name,
        "visita": m.away.name,
        "hora_local": _when(m.start),
        "estadio": m.venue,
        "estado": m.status,
        "marcador": m.score_text,
        "en_vivo": m.live,
    }


class _FootballBase(_Base):
    def __init__(self, coordinator, entry, key: str, device_key: str, device_name: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_device_info = _device(device_key, device_name)

    def _has_data(self) -> bool:
        return self.coordinator.data is not None

    def _list(self, key: str) -> list[api.Match]:
        return list((self.coordinator.data or {}).get(key) or [])


class NextMatchSensor(_FootballBase):
    """Próximo partido (o el que está en juego) de un equipo o de la selección."""

    _kind = "partido_proximo"
    _attr_icon = "mdi:soccer"
    _attr_name = "Próximo partido"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry, team_id: str, device: str, fixtures_key: str, results_key: str) -> None:
        super().__init__(coordinator, entry, f"{team_id}_{fixtures_key}", f"futbol_{team_id}", device)
        self._team_id = team_id
        self._fixtures_key = fixtures_key
        self._results_key = results_key

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.get(self._fixtures_key) is not None

    def _upcoming(self) -> list[api.Match]:
        pool = self._list(self._fixtures_key) + [m for m in self._list(self._results_key) if m.live]
        return sorted({m.id: m for m in pool if not m.finished}.values(), key=lambda m: m.start)

    @property
    def native_value(self):
        up = self._upcoming()
        return up[0].start if up else None

    @property
    def entity_picture(self) -> str | None:
        up = self._upcoming() if self.coordinator.data is not None else []
        return up[0].opponent(self._team_id).logo if up else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        up = self._upcoming()
        if not up:
            return {"motivo": "No hay partidos programados"}
        m = up[0]
        today = dt_util.now().astimezone(ZoneInfo(api.METRO_TZ)).date()
        return {
            "rival": m.opponent(self._team_id).name,
            "condicion": "local" if m.is_home(self._team_id) else "visita",
            "competencia": m.competition,
            "hora_local": _when(m.start),
            "dias_restantes": (m.start.astimezone(ZoneInfo(api.METRO_TZ)).date() - today).days,
            "estadio": m.venue,
            "ciudad": m.city,
            "en_vivo": m.live,
            "marcador": m.score_text if m.live else None,
            "minuto": m.clock,
            "siguientes": [
                {
                    "rival": n.opponent(self._team_id).name,
                    "condicion": "local" if n.is_home(self._team_id) else "visita",
                    "hora_local": _when(n.start),
                    "competencia": n.competition,
                }
                for n in up[1:4]
            ],
        }


class LastResultSensor(_FootballBase):
    """Último resultado de un equipo o de la selección, con su forma reciente."""

    _kind = "partido_ultimo"
    _attr_icon = "mdi:scoreboard"
    _attr_name = "Último resultado"
    _LETTER = {"ganó": "G", "empató": "E", "perdió": "P"}

    def __init__(self, coordinator, entry, team_id: str, device: str, results_key: str) -> None:
        super().__init__(coordinator, entry, f"{team_id}_{results_key}", f"futbol_{team_id}", device)
        self._team_id = team_id
        self._results_key = results_key

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.get(self._results_key) is not None

    def _finished(self) -> list[api.Match]:
        return sorted((m for m in self._list(self._results_key) if m.finished), key=lambda m: m.start, reverse=True)

    def _mine(self, m: api.Match) -> tuple[int, int]:
        h, a = m.home_score or 0, m.away_score or 0
        return (h, a) if m.is_home(self._team_id) else (a, h)

    @property
    def native_value(self) -> str | None:
        done = self._finished()
        if not done:
            return None
        m = done[0]
        mine, theirs = self._mine(m)
        return f"{m.result_for(self._team_id).capitalize()} {mine}-{theirs} vs {m.opponent(self._team_id).name}"

    @property
    def entity_picture(self) -> str | None:
        done = self._finished() if self.coordinator.data is not None else []
        if not done:
            return None
        m = done[0]
        return (m.home if m.is_home(self._team_id) else m.away).logo

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        done = self._finished()
        if not done:
            return {"motivo": "Aún no hay resultados"}
        m = done[0]
        mine, theirs = self._mine(m)
        recent = done[:5]
        return {
            "resultado": m.result_for(self._team_id),
            "marcador": f"{mine}-{theirs}",
            "local": m.home.name,
            "visita": m.away.name,
            "marcador_local_visita": m.score_text,
            "rival": m.opponent(self._team_id).name,
            "competencia": m.competition,
            "fecha": _when(m.start),
            "estadio": m.venue,
            "forma": "".join(self._LETTER[x.result_for(self._team_id)] for x in recent),
            "ultimos": [
                {
                    "rival": x.opponent(self._team_id).name,
                    "resultado": x.result_for(self._team_id),
                    "marcador": "%d-%d" % self._mine(x),
                    "fecha": _when(x.start),
                    "competencia": x.competition,
                }
                for x in recent
            ],
        }


class PositionSensor(_FootballBase):
    """Posición del equipo en la tabla de la Primera División."""

    _kind = "tabla_posicion"
    _attr_icon = "mdi:podium"
    _attr_name = "Posición en la tabla"

    def __init__(self, coordinator, entry, team_id: str, device: str) -> None:
        super().__init__(coordinator, entry, team_id, f"futbol_{team_id}", device)
        self._team_id = team_id

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.get("standings") is not None

    def _row(self) -> api.TableRow | None:
        rows = (self.coordinator.data or {}).get("standings") or []
        return next((r for r in rows if r.team.id == self._team_id), None)

    @property
    def native_value(self) -> int | None:
        row = self._row()
        return row.rank if row else None

    @property
    def entity_picture(self) -> str | None:
        row = self._row()
        return row.team.logo if row else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self._row()
        if row is None:
            return {"motivo": "El equipo no figura en la tabla"}
        rows = self.coordinator.data["standings"]
        leader = rows[0]
        return {
            "puntos": row.points,
            "jugados": row.played,
            "ganados": row.wins,
            "empatados": row.draws,
            "perdidos": row.losses,
            "goles_a_favor": row.goals_for,
            "goles_en_contra": row.goals_against,
            "diferencia_de_goles": row.goal_diff,
            "lider": leader.team.name,
            "puntos_del_lider": leader.points,
            "puntos_bajo_el_lider": leader.points - row.points,
            "equipos": len(rows),
        }


class LeagueTableSensor(_FootballBase):
    """Tabla de posiciones completa de la Primera División."""

    _kind = "liga_tabla"
    _attr_icon = "mdi:format-list-numbered"
    _attr_name = "Tabla de posiciones"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "tabla", "futbol_liga", "Fútbol: Primera División")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.get("standings") is not None

    def _rows(self) -> list[api.TableRow]:
        return list((self.coordinator.data or {}).get("standings") or [])

    @property
    def native_value(self) -> str | None:
        rows = self._rows()
        return rows[0].team.name if rows else None

    @property
    def entity_picture(self) -> str | None:
        rows = self._rows()
        return rows[0].team.logo if rows else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "tabla": [
                {
                    "posicion": r.rank,
                    "equipo": r.team.name,
                    "pj": r.played,
                    "pg": r.wins,
                    "pe": r.draws,
                    "pp": r.losses,
                    "gf": r.goals_for,
                    "gc": r.goals_against,
                    "dg": r.goal_diff,
                    "pts": r.points,
                }
                for r in self._rows()
            ]
        }


class LeagueNextRoundSensor(_FootballBase):
    """Partidos de la próxima fecha; el estado es el horario del primero que falta jugar."""

    _kind = "liga_proxima"
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Próxima fecha"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "proxima", "futbol_liga", "Fútbol: Primera División")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.get("league_next") is not None

    @property
    def native_value(self):
        pending = [m for m in self._list("league_next") if not m.finished]
        return pending[0].start if pending else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        matches = self._list("league_next")
        return {"partidos": [_round_item(m) for m in matches], "cantidad": len(matches)}


class LeagueLastRoundSensor(_FootballBase):
    """Resultados de la última fecha; el estado es la cantidad de partidos."""

    _kind = "liga_ultima"
    _attr_icon = "mdi:scoreboard-outline"
    _attr_name = "Última fecha"
    _attr_native_unit_of_measurement = "partidos"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "ultima", "futbol_liga", "Fútbol: Primera División")

    def _has_data(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.get("league_last") is not None

    @property
    def native_value(self) -> int:
        return len(self._list("league_last"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"resultados": [_round_item(m) for m in self._list("league_last")]}
