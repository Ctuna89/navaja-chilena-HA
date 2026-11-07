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


def test_metro():
    data = {"lines": [
        {"id": "l1", "name": "Línea 1", "status": {"code": "1", "message": "Operativa"},
         "stations": [{"id": "a", "name": "A", "status": {"code": "1"}}]},
        {"id": "l2", "name": "Línea 2", "status": {"code": "2", "message": "Demoras"},
         "stations": [{"id": "b", "name": "B", "status": {"code": "2"}}]},
    ]}
    out = api.parse_metro(data)
    assert out["l1"].operational and not out["l2"].operational
    assert out["l2"].stations_with_issues == ["B"] and out["l2"].message == "Demoras"
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
