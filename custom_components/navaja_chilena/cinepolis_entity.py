"""Cartelera de Cinépolis: sensor con las películas y funciones de hoy del cine elegido."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import api, cinepolis
from .const import DOMAIN


class CinepolisSensor(CoordinatorEntity, SensorEntity):
    """Películas de hoy en el cine de Cinépolis elegido, con sus funciones."""

    _attr_has_entity_name = True
    _attr_name = "Cartelera de hoy"
    _attr_icon = "mdi:movie-open"
    _attr_native_unit_of_measurement = "películas"
    _attr_attribution = cinepolis.CINEPOLIS_ATTRIBUTION

    def __init__(self, coordinator, entry, cinema_text: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_cinepolis_cartelera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "cinepolis")},
            name=f"Cinépolis {cinema_text}",
            manufacturer="Navaja Chilena",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    def _now(self):
        data = self.coordinator.data
        return dt_util.now().astimezone(ZoneInfo(data.cinema.timezone))

    def _today(self) -> list[tuple[cinepolis.CinepolisMovie, list[cinepolis.CinepolisShowtime]]]:
        """Películas con funciones en el día de cartelera de hoy (las de trasnoche cuentan para el día anterior)."""
        today = api.listing_day(self._now())
        result = []
        for movie, showtimes in self.coordinator.data.movies:
            todays = [s for s in showtimes if api.listing_day(s.start) == today]
            if todays:
                result.append((movie, todays))
        return result

    @property
    def native_value(self) -> int:
        return len(self._today())

    def _next(self):
        """La próxima función desde ahora, de hoy o de los días siguientes (el servicio solo entrega las que aún no empiezan)."""
        now = self._now()
        coming = [(s, m) for m, shows in self.coordinator.data.movies for s in shows if s.start >= now]
        return min(coming, key=lambda item: item[0].start) if coming else None

    @property
    def entity_picture(self) -> str | None:
        nxt = self._next() if self.coordinator.data is not None else None
        return cinepolis.poster_url(nxt[1]) if nxt else None

    @staticmethod
    def _show(s: cinepolis.CinepolisShowtime) -> dict[str, Any]:
        return {
            "hora": s.start.strftime("%H:%M"),
            "fecha": s.start.strftime("%Y-%m-%d"),
            "formato": s.format,
            "idioma": s.language_name or s.language,
            "experiencia": s.experience,
            "sala": s.screen,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        movies = [
            {
                "titulo": m.name,
                "duracion_min": m.duration_min,
                "genero": ", ".join(m.genres) or None,
                "clasificacion": m.rating,
                "afiche": cinepolis.poster_url(m),
                "funciones": [self._show(s) for s in shows],
            }
            for m, shows in self._today()
        ]
        nxt = self._next()
        summary = "\n".join(
            f"{m['titulo']}" + (f" ({m['duracion_min']} min)" if m["duracion_min"] else "") + ": " + ", ".join(f["hora"] for f in m["funciones"])
            for m in movies
        )
        attrs: dict[str, Any] = {
            "cine": data.cinema.name,
            "fecha": api.listing_day(self._now()).isoformat(),
            "peliculas": movies,
            "resumen": summary,
            "proxima_funcion": (
                {
                    "titulo": nxt[1].name,
                    "hora": nxt[0].start.strftime("%H:%M"),
                    "fecha": nxt[0].start.strftime("%Y-%m-%d"),
                    "afiche": cinepolis.poster_url(nxt[1]),
                }
                if nxt
                else None
            ),
            "cartelera_completa": data.complete,
            "actualizado": data.updated.astimezone(ZoneInfo(data.cinema.timezone)).strftime("%Y-%m-%d %H:%M"),
            "desactualizado": data.error is not None,
        }
        if data.cinema.lat is not None:
            attrs |= {"latitude": data.cinema.lat, "longitude": data.cinema.lng}
        if data.error:
            attrs["ultimo_error"] = data.error
        return attrs
