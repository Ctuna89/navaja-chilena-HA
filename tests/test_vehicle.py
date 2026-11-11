"""Restricción vehicular y revisión técnica contra las tablas oficiales."""

import importlib.util
from datetime import date, time
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "nc_vehicle", Path(__file__).parents[1] / "custom_components/navaja_chilena/vehicle.py"
)
v = importlib.util.module_from_spec(_spec)
import sys

sys.modules["nc_vehicle"] = v
_spec.loader.exec_module(v)

MON, TUE, WED, THU, FRI = (date(2026, 5, d) for d in (4, 5, 6, 7, 8))   # semana del 4 de mayo de 2026


def digits(vtype, day):
    return v.status_on(vtype, 0, day).digits


def test_official_tables_2026():
    """Resolución Exenta N° 1698/2026, letras b), e) y f)."""
    sv = {MON: {8, 9}, TUE: {0, 1}, WED: {2, 3}, THU: {4, 5}, FRI: {6, 7}}
    ss = {MON: {6, 7, 8, 9}, TUE: {0, 1, 2, 3}, WED: {4, 5, 6, 7}, THU: {8, 9, 0, 1}, FRI: {2, 3, 4, 5}}
    for day in sv:
        assert digits("sello_verde", day) == sv[day] == digits("moto", day)
        assert digits("sin_sello_fuera_anillo", day) == ss[day]
        assert digits("sin_sello_dentro_anillo", day) == set(range(10))


def test_every_digit_restricted_expected_times_per_week():
    for vtype, times in (("sello_verde", 1), ("moto", 1), ("sin_sello_fuera_anillo", 2), ("sin_sello_dentro_anillo", 5)):
        for digit in range(10):
            n = sum(v.status_on(vtype, digit, d).restricted for d in (MON, TUE, WED, THU, FRI))
            assert n == times, (vtype, digit)


def test_restricted_and_free_reasons():
    assert v.status_on("sello_verde", 8, MON) == v.Status(True, v.RESTRICTED, frozenset({8, 9}))
    assert v.status_on("sello_verde", 7, MON).restricted is False
    assert v.status_on("sello_verde", 7, MON).reason == v.FREE_DIGIT


def test_season_boundaries_2026():
    assert v.status_on("sello_verde", 8, date(2026, 4, 30)).reason == v.OFF_SEASON
    assert v.status_on("sello_verde", 8, date(2026, 8, 31)).restricted is True      # lunes, último día
    assert v.status_on("sello_verde", 8, date(2026, 9, 1)).reason == v.OFF_SEASON
    assert v.status_on("sin_sello_dentro_anillo", 3, date(2026, 11, 10)).restricted is False


def test_weekends_holidays_and_exempt():
    assert v.status_on("sello_verde", 8, date(2026, 5, 9)).reason == v.WEEKEND
    may1 = date(2026, 5, 1)   # viernes, Día del Trabajo
    assert v.status_on("sello_verde", 6, may1, {may1}).reason == v.HOLIDAY
    assert v.status_on("sello_verde", 6, may1).restricted is True                    # sin datos de festivos
    for d in (MON, TUE, WED, THU, FRI):
        s = v.status_on("sello_verde_posterior", 8, d)
        assert (s.restricted, s.reason) == (False, v.EXEMPT)


def test_year_without_resolution_is_not_invented():
    assert v.status_on("sello_verde", 8, date(2027, 2, 15)).restricted is False      # verano: no hay temporada
    s = v.status_on("sello_verde", 8, date(2027, 6, 7))
    assert s.restricted is None and s.reason == v.NO_RESOLUTION                      # no se adivina


def test_next_restriction():
    # dígito 8 con sello verde: lunes; el 1 de mayo (viernes) es festivo
    assert v.next_restriction("sello_verde", 8, date(2026, 3, 1)) == date(2026, 5, 4)
    assert v.next_restriction("sello_verde", 8, MON) == MON                           # incluye hoy
    assert v.next_restriction("sello_verde", 8, date(2026, 5, 5)) == date(2026, 5, 11)
    # dígito 4: jueves; si el 14 es festivo se salta al 21
    assert v.next_restriction("sello_verde", 4, date(2026, 5, 8)) == date(2026, 5, 14)
    assert v.next_restriction("sello_verde", 4, date(2026, 5, 8), {date(2026, 5, 14)}) == date(2026, 5, 21)
    assert v.next_restriction("sello_verde", 8, date(2026, 9, 5)) is None             # terminó la temporada
    assert v.next_restriction("sello_verde_posterior", 8, date(2026, 5, 4)) is None   # exento
    assert v.next_restriction("sello_verde", 8, date(2027, 5, 3)) is None             # sin resolución 2027


def test_window():
    assert v.window_active(time(7, 30)) and v.window_active(time(20, 59))
    assert not v.window_active(time(7, 29)) and not v.window_active(time(21, 0))


def test_revision_calendar_chileatiende():
    """Ficha oficial: 9 enero, 0 febrero, 1 abril, 2 mayo, … 8 noviembre; marzo y diciembre sin dígito."""
    assert v.REVISION_MONTH == {9: 1, 0: 2, 1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11}
    assert sorted(v.REVISION_MONTH) == list(range(10))
    assert 3 not in v.REVISION_MONTH.values() and 12 not in v.REVISION_MONTH.values()
    assert v.MONTH_NAMES[v.revision_month(8) - 1] == "noviembre"


def test_months_until_revision():
    today = date(2026, 11, 10)
    assert v.months_until_revision(8, today) == 0       # noviembre: este mes
    assert v.months_until_revision(9, today) == 2       # enero
    assert v.months_until_revision(0, today) == 3       # febrero
    assert v.months_until_revision(7, today) == 11      # octubre (ya pasó este año)
    for d in range(10):
        assert 0 <= v.months_until_revision(d, today) <= 11


# ------------------------------------------------------------ Varios vehículos

def test_parse_extra_vehicles():
    assert v.parse_extra_vehicles("3, 5:moto;7:sin_sello 3") == [(3, "sello_verde"), (5, "moto"), (7, "sin_sello_fuera_anillo")]
    assert v.parse_extra_vehicles("4:sin_sello_dentro_anillo", "moto") == [(4, "sin_sello_dentro_anillo")]
    assert v.parse_extra_vehicles("2", "sin_sello_fuera_anillo") == [(2, "sin_sello_fuera_anillo")]
    assert v.parse_extra_vehicles("") == []
    for bad in ("12", "a", "3:camion", "3:", ":moto", "3-5"):
        try:
            v.parse_extra_vehicles(bad)
        except ValueError:
            continue
        raise AssertionError(f"debía rechazar {bad!r}")


def test_build_vehicles_keeps_primary_and_names_the_rest():
    specs = v.build_vehicles(8, "sello_verde", [(3, "sello_verde"), (5, "moto"), (8, "sello_verde")])
    assert [(s.digit, s.primary, s.name) for s in specs] == [(8, True, "Mi vehículo"), (3, False, "Vehículo patente 3"), (5, False, "Vehículo patente 5")]
    assert specs[0].suffix == "" and specs[1].suffix == "_3_sello_verde"      # el principal conserva los ids existentes
    # Mismo dígito con otro tipo: el nombre los distingue
    same = v.build_vehicles(8, "sello_verde", [(8, "moto")])
    assert [s.name for s in same] == ["Mi vehículo", "Vehículo patente 8 (moto)"]
    # Sin vehículo principal
    assert [s.name for s in v.build_vehicles(None, "sello_verde", [(2, "moto")])] == ["Vehículo patente 2"]
    assert v.build_vehicles(None, "sello_verde", []) == []


def test_build_vehicles_has_a_limit():
    extra = [(d, "sello_verde") for d in range(1, 6)]
    assert len(v.build_vehicles(0, "sello_verde", extra[:4])) == 5
    try:
        v.build_vehicles(0, "sello_verde", extra)
    except ValueError:
        pass
    else:
        raise AssertionError("debía rechazar más de 5 vehículos")
