"""Pruebas de los parsers (sin red ni Home Assistant)."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

# Cargar api.py/const.py como paquete sin importar homeassistant.
pkg = types.ModuleType("nc")
pkg.__path__ = [str(Path(__file__).parents[1] / "custom_components/navaja_chilena")]
sys.modules["nc"] = pkg
for name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"nc.{name}", f"{pkg.__path__[0]}/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"nc.{name}"] = mod
    spec.loader.exec_module(mod)
api = sys.modules["nc.api"]


def test_stop_codes():
    assert api.parse_stop_codes("pc615, PA433;pc615  pj12") == ["PC615", "PA433", "PJ12"]
    assert api.parse_stop_codes("") == []
    with pytest.raises(ValueError):
        api.parse_stop_codes("123abc")


def test_indicators():
    data = {
        "version": "1.7.0", "autor": "x", "fecha": "2026-11-07T12:00:00.000Z",
        "uf": {"codigo": "uf", "nombre": "Unidad de fomento (UF)", "unidad_medida": "Pesos",
               "fecha": "2026-11-07T03:00:00.000Z", "valor": 39000.5},
        "ipc": {"codigo": "ipc", "nombre": "IPC", "unidad_medida": "Porcentaje", "fecha": None, "valor": 0.3},
        "roto": {"valor": "n/a"},
    }
    out = api.parse_indicators(data)
    assert set(out) == {"uf", "ipc"} and out["uf"].value == 39000.5
    with pytest.raises(api.NavajaApiError):
        api.parse_indicators({"version": "1"})


def test_metro_station_codes():
    # En api.xor.cl: 0 operativa, 1 cerrada temporalmente, 2 no habilitada, 3 accesos cerrados
    data = {"lines": [
        {"id": "l1", "name": "Línea 1", "stations": [
            {"name": "A", "status": {"code": "0"}}, {"name": "B", "status": 0}]},
        {"id": "l2", "name": "Línea 2", "stations": [
            {"name": "C", "status": {"code": "0"}}, {"name": "D", "status": {"code": "1", "message": "Cerrada"}}]},
    ]}
    out = api.parse_metro(data)
    assert out["l1"].operational is True
    assert out["l2"].operational is False and out["l2"].stations_with_issues == ["D"]


def test_metro_unknown_is_never_operational():
    data = {"lines": [
        {"id": "l1", "name": "L1", "status": {"code": "?"}},
        {"id": "l2", "name": "L2", "status": {"code": "0"}},
    ]}
    out = api.parse_metro(data)
    assert out["l1"].operational is None and out["l2"].operational is True
    with pytest.raises(api.NavajaApiError):  # nada interpretable -> error, no "operativa"
        api.parse_metro({"lines": [{"id": "l1", "name": "L1", "status": {"code": "?"}}]})
    with pytest.raises(api.NavajaApiError):
        api.parse_metro({"lines": []})


def test_stop():
    data = {"id": "PC615", "status_description": "Servicio en horario normal", "services": [
        {"id": "210", "status_description": "Buses disponibles",
         "buses": [{"id": "X", "min_arrival_time": 5, "max_arrival_time": 8},
                   {"id": "Y", "min_arrival_time": 12, "max_arrival_time": 15}]},
        {"id": "301", "status_description": "Sin buses", "buses": []},
    ]}
    s = api.parse_stop("PC615", data)
    assert s.next_minutes == 5 and s.services[1].next_minutes is None
    with pytest.raises(api.NavajaApiError):
        api.parse_stop("ZZ1", {"error": "x"})


def test_quakes_usgs():
    feat = lambda mag, place, t, lon=-70.5, lat=-33.1, d=10.0: {
        "properties": {"mag": mag, "place": place, "time": t},
        "geometry": {"coordinates": [lon, lat, d]}}
    data = {"features": [
        feat(3.1, "20 km N of Ovalle, Chile", 1_762_500_000_000),
        feat(4.7, "10 km S of Salta, Argentina", 1_762_600_000_000),   # se descarta
        feat(5.2, "50 km W of Illapel, Chile", 1_762_550_000_000, -71.9, -31.6, 35.0),
    ]}
    q = api.parse_quakes(data)
    assert [x.magnitude for x in q] == [5.2, 3.1]
    assert q[0].latitude == -31.6 and q[0].longitude == -71.9 and q[0].depth_km == 35.0
    assert q[0].date.startswith("2025-11-0")
    with pytest.raises(api.NavajaApiError):
        api.parse_quakes({"features": []})
    with pytest.raises(api.NavajaApiError):
        api.parse_quakes([])


def test_holidays_both_formats():
    from datetime import date
    gov = [{"nombre": "Navidad", "fecha": "2026-12-25", "irrenunciable": "1", "tipo": "Civil"},
           {"nombre": "Año Nuevo", "fecha": "2026-01-01", "irrenunciable": "1"}]
    bo = {"status": "success", "data": [{"title": "Navidad", "date": "2026-12-25", "inalienable": True}]}
    for payload in (gov, bo):
        hs = api.parse_holidays(payload)
        nxt = api.next_holiday(hs, date(2026, 11, 7))
        assert nxt.name == "Navidad" and nxt.inalienable
    assert api.next_holiday(api.parse_holidays(gov), date(2027, 1, 1)) is None


def test_air():
    a = api.parse_air({"current": {"pm10": 30.5, "pm2_5": 12, "us_aqi": 55, "uv_index": 7.2}})
    assert (a.pm2_5, a.pm10, a.aqi, a.uv_index) == (12, 30.5, 55, 7.2)
    with pytest.raises(api.NavajaApiError):
        api.parse_air({})


def test_pharmacies_accent_insensitive():
    data = [
        {"comuna_nombre": "ÑUÑOA", "local_nombre": "Cruz", "local_direccion": "X 1",
         "local_lat": "-33.45", "local_lng": "-70.6"},
        {"comuna_nombre": "Providencia", "local_nombre": "Otra"},
    ]
    assert [p.name for p in api.parse_pharmacies(data, "Ñuñoa")] == ["Cruz"]
    assert api.parse_pharmacies(data, "Las Condes") == []


def test_metro_schedule():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Santiago")
    at = lambda d, h, m=0: datetime(2026, 11, d, h, m, tzinfo=tz)  # 9 nov 2026 = lunes
    assert api.metro_is_open(at(9, 12))
    assert not api.metro_is_open(at(9, 5, 59))
    assert api.metro_is_open(at(9, 6, 0))
    assert not api.metro_is_open(at(9, 23, 0))
    assert api.metro_is_open(at(7, 6, 45))             # sábado abre 6:30
    assert not api.metro_is_open(at(7, 6, 15))
    assert not api.metro_is_open(at(8, 7, 0))          # domingo abre 7:30
    assert api.metro_is_open(at(8, 7, 30))
    assert not api.metro_is_open(at(9, 7, 0), holiday=True)  # festivo = horario domingo
    assert api.metro_is_open(at(9, 7, 30), holiday=True)
