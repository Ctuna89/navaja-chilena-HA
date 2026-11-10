"""Restricción vehicular (Región Metropolitana) y calendario de revisión técnica.

Sin red: son reglas publicadas oficialmente que cambian una vez al año.

Fuentes
- Restricción: Resolución Exenta N° 1698/2026 de la Seremi de Transportes y
  Telecomunicaciones RM (29-04-2026), https://mtt.gob.cl/restriccion-vehicular-2026/
- Revisión técnica: ficha «Revisión técnica de vehículos motorizados» de ChileAtiende
  (Subsecretaría de Transportes), https://www.chileatiende.gob.cl/fichas/23978

Cada año el MTT publica una nueva resolución (en abril): hay que agregarla a RULES.
En preemergencia o emergencia ambiental se restringen dígitos adicionales que el MTT
informa por sus canales; eso no está incluido aquí.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta

# Horario general de la medida (lunes a viernes, salvo festivos)
WINDOW_START = time(7, 30)
WINDOW_END = time(21, 0)

ALL_DIGITS = frozenset(range(10))
_WEEK = range(5)  # lunes (0) a viernes (4)

# Tipos de vehículo -> descripción (se usan en la configuración)
VEHICLE_TYPES: dict[str, str] = {
    "sello_verde": "Auto con sello verde inscrito antes del 1 de septiembre de 2011",
    "sello_verde_posterior": "Auto con sello verde inscrito desde septiembre de 2011 (sin restricción)",
    "sin_sello_fuera_anillo": "Auto sin sello verde, fuera del anillo Américo Vespucio",
    "sin_sello_dentro_anillo": "Auto sin sello verde, dentro del anillo Américo Vespucio",
    "moto": "Moto inscrita antes del 1 de septiembre de 2010",
}

_TWO_DIGITS = {
    0: frozenset({8, 9}),
    1: frozenset({0, 1}),
    2: frozenset({2, 3}),
    3: frozenset({4, 5}),
    4: frozenset({6, 7}),
}
_FOUR_DIGITS = {
    0: frozenset({6, 7, 8, 9}),
    1: frozenset({0, 1, 2, 3}),
    2: frozenset({4, 5, 6, 7}),
    3: frozenset({8, 9, 0, 1}),
    4: frozenset({2, 3, 4, 5}),
}


@dataclass(frozen=True)
class YearRules:
    """Reglas de restricción de un año (una resolución)."""

    start: date
    end: date
    resolution: str
    # tipo de vehículo -> {día de la semana: dígitos}; None = exento
    tables: dict[str, dict[int, frozenset[int]] | None]


RULES: dict[int, YearRules] = {
    2026: YearRules(
        start=date(2026, 5, 1),
        end=date(2026, 8, 31),
        resolution="Resolución Exenta N° 1698/2026 SRM-RM (29-04-2026)",
        tables={
            "sello_verde": _TWO_DIGITS,
            "sello_verde_posterior": None,
            "sin_sello_fuera_anillo": _FOUR_DIGITS,
            "sin_sello_dentro_anillo": {d: ALL_DIGITS for d in _WEEK},
            "moto": _TWO_DIGITS,
        },
    ),
}

# Motivos
RESTRICTED = "restringido"
FREE_DIGIT = "digito_libre"
OFF_SEASON = "fuera_de_temporada"
WEEKEND = "fin_de_semana"
HOLIDAY = "festivo"
EXEMPT = "exento"
NO_RESOLUTION = "sin_resolucion"


@dataclass(frozen=True)
class Status:
    """Estado de restricción de un vehículo en una fecha."""

    restricted: bool | None  # None = no se puede determinar
    reason: str
    digits: frozenset[int] | None = None  # dígitos restringidos ese día (si rige)


def status_on(
    vehicle_type: str, digit: int, day: date, holidays: frozenset[date] | set[date] = frozenset()
) -> Status:
    """¿Tiene restricción el vehículo en `day`? Los festivos se pasan en `holidays`."""
    rules = RULES.get(day.year)
    if rules is None:
        # Sin resolución del año: de enero a marzo no hay temporada; después, no se sabe.
        if day.month <= 3:
            return Status(False, OFF_SEASON)
        return Status(None, NO_RESOLUTION)
    if not (rules.start <= day <= rules.end):
        return Status(False, OFF_SEASON)
    table = rules.tables.get(vehicle_type)
    if table is None:
        return Status(False, EXEMPT)
    if day.weekday() not in _WEEK:
        return Status(False, WEEKEND)
    if day in holidays:
        return Status(False, HOLIDAY)
    digits = table[day.weekday()]
    return Status(digit in digits, RESTRICTED if digit in digits else FREE_DIGIT, digits)


def next_restriction(
    vehicle_type: str, digit: int, today: date, holidays: frozenset[date] | set[date] = frozenset()
) -> date | None:
    """Primer día desde `today` (inclusive) con restricción, dentro de la temporada vigente."""
    rules = RULES.get(today.year)
    if rules is None:
        return None
    day = max(today, rules.start)
    while day <= rules.end:
        if status_on(vehicle_type, digit, day, holidays).restricted:
            return day
        day += timedelta(days=1)
    return None


def window_active(now_time: time) -> bool:
    return WINDOW_START <= now_time < WINDOW_END


def season(year: int) -> tuple[date, date] | None:
    rules = RULES.get(year)
    return (rules.start, rules.end) if rules else None


# ------------------------------------------------------------- Revisión técnica

# Último dígito de la patente -> mes de preferencia (ChileAtiende; marzo y diciembre sin dígito)
REVISION_MONTH: dict[int, int] = {9: 1, 0: 2, 1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11}

MONTH_NAMES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
)


def revision_month(digit: int) -> int:
    return REVISION_MONTH[digit]


def months_until_revision(digit: int, today: date) -> int:
    """Meses que faltan para el mes de preferencia (0 = es este mes)."""
    return (REVISION_MONTH[digit] - today.month) % 12
