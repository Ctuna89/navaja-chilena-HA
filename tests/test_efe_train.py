"""Pruebas del tren Limache–Puerto (EFE Valparaíso), sin red ni Home Assistant."""

import importlib.util
import json
import ssl
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

# Cargar const.py/api.py/efe_train.py como paquete sin importar homeassistant (igual que test_api.py).
if "nc" not in sys.modules:
    pkg = types.ModuleType("nc")
    pkg.__path__ = [str(Path(__file__).parents[1] / "custom_components/navaja_chilena")]
    sys.modules["nc"] = pkg
for name in ("const", "api", "efe_train"):
    if f"nc.{name}" in sys.modules:
        continue
    spec = importlib.util.spec_from_file_location(
        f"nc.{name}", f"{sys.modules['nc'].__path__[0]}/{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"nc.{name}"] = mod
    spec.loader.exec_module(mod)
api = sys.modules["nc.api"]
efe_train = sys.modules["nc.efe_train"]

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_build_url():
    parts = urlsplit(efe_train.build_url(18, 1))
    assert f"{parts.scheme}://{parts.netloc}/" == "https://ms4.metrovalparaiso.cl/"
    assert json.loads(parse_qs(parts.query)["arg"][0]) == {"idOrigen": 18, "idDestino": 1}


@pytest.mark.parametrize(
    ("text", "expected"),
    [("6 minutos", 6), ("1 minuto", 1), ("cercano", None), ("", None), (None, None), ("6 min", None)],
)
def test_parse_minutes(text, expected):
    assert efe_train.parse_minutes(text) == expected


@pytest.mark.parametrize(
    ("raw", "with_return", "expected"),
    [
        ("Villa Alemana > Puerto", False, [(18, 1)]),
        ("villa alemana>puerto; Viña del Mar → LIMACHE", False, [(18, 1), (8, 21)]),
        ("18 > 1, Villa Alemana > Puerto", False, [(18, 1)]),
        ("Villa Alemana > Puerto", True, [(18, 1), (1, 18)]),
        ("Villa Alemana > Puerto, Puerto > Villa Alemana", True, [(18, 1), (1, 18)]),
        ("", False, []),
        (" , ", False, []),
    ],
)
def test_parse_trips(raw, with_return, expected):
    assert efe_train.parse_trips(raw, with_return) == expected


@pytest.mark.parametrize(
    "raw", ["Villa Alemana", "Villa Alemana > Marte", "Puerto > Puerto", "Puerto > Francia > Barón", "0 > 22"]
)
def test_parse_trips_invalid(raw):
    with pytest.raises(ValueError):
        efe_train.parse_trips(raw)


def test_format_trips_round_trip():
    trips = [(18, 1), (8, 21)]
    assert efe_train.format_trips(trips) == "Villa Alemana > Puerto, Viña del Mar > Limache"
    assert efe_train.parse_trips(efe_train.format_trips(trips)) == trips


def test_parse_with_services_keeps_fields():
    data = load("efe_train_with_services.json")
    result = efe_train.parse_response(data, "u", 18, 1)
    assert result.state == efe_train.STATE_SERVICES
    assert len(result.services) == len(data["object"]["servicios"])
    for raw, parsed in zip(data["object"]["servicios"], result.services):
        assert {k: parsed[k] for k in raw} == raw  # campos originales intactos
    assert result.services[0]["minutos"] == 10
    assert result.warning == "Servicio no disponible por el momento"
    assert result.operability["via1"] == "YES"


def test_parse_empty_list_is_not_an_error():
    result = efe_train.parse_response(load("efe_train_no_services.json"), "u", 18, 1)
    assert result.services == []
    assert result.state == efe_train.STATE_NO_SERVICES


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {"status": "ERROR"},
        {"status": "OK", "message": {}},
        {"status": "OK", "message": {}, "object": {}},
        {"status": "OK", "object": {"servicios": []}},
        {"status": "OK", "message": {}, "object": {"servicios": ["x"]}},
    ],
)
def test_parse_invalid_raises(data):
    with pytest.raises(api.NavajaApiError):
        efe_train.parse_response(data, "u", 18, 1)


def test_ssl_context_keeps_verification():
    ctx = efe_train.create_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert efe_train.INTERMEDIATE_CERT.is_file()


@pytest.mark.parametrize(
    ("hasta", "expected"),
    [("Hasta Puerto", 1), ("Hasta Sargento Aldea", 19), ("hasta  viña del mar", 8), ("Hasta Peñablanca", 20),
     ("Puerto", 1), ("Hasta Marte", None), (None, None)],
)
def test_terminal_station(hasta, expected):
    assert efe_train.terminal_station(hasta) == expected


@pytest.mark.parametrize(
    ("terminal", "origin", "destination", "expected"),
    [
        (19, 18, 21, False),  # Villa Alemana → Limache, tren hasta Sargento Aldea
        (21, 18, 21, True),
        (19, 3, 17, True),    # Francia → La Concepción: Sargento Aldea pasa por La Concepción
        (1, 17, 3, True),     # La Concepción → Francia, hasta Puerto
        (8, 17, 3, False),    # un tren que terminara en Viña del Mar no llega a Francia
        (None, 18, 1, None),
    ],
)
def test_reaches_destination(terminal, origin, destination, expected):
    assert efe_train.reaches_destination(terminal, origin, destination) is expected


def test_parse_adds_derived_fields_without_touching_originals():
    data = {
        "status": "OK",
        "message": {},
        "object": {"servicios": [
            {"hasta": "Hasta Sargento Aldea", "tipo": "simple", "tiempo": "8 minutos", "idServicio": "1"},
            {"hasta": "Hasta Limache", "tipo": "doble", "tiempo": "cercano", "idServicio": "2"},
        ]},
    }
    at = datetime(2026, 11, 9, 10, 33, 20, tzinfo=timezone.utc)
    first, second = efe_train.parse_response(data, "u", 18, 21, at).services
    assert first["hasta"] == "Hasta Sargento Aldea" and first["tiempo"] == "8 minutos"
    assert first["estacion_final"] == "Sargento Aldea"
    assert first["llega_a_destino"] is False
    assert first["hora_estimada"] == "2026-11-09T10:41+00:00"
    assert second["llega_a_destino"] is True
    assert second["minutos"] is None and second["hora_estimada"] is None  # «cercano»: sin inventar hora


@pytest.mark.parametrize(
    ("value", "expected"),
    [(18, 18), ("18", 18), ("Villa Alemana", 18), ("viña del mar", 8), ("PEÑABLANCA", 20), (0, None), (22, None),
     ("Marte", None), (True, None), (None, None)],
)
def test_resolve_station(value, expected):
    assert efe_train.resolve_station(value) == expected


def test_parse_trips_caps_the_number_of_queries():
    many = ", ".join(f"{o} > Limache" for o in range(1, 9))   # 8 distintos: permitido
    assert len(efe_train.parse_trips(many)) == 8
    with pytest.raises(ValueError):
        efe_train.parse_trips(many, with_return=True)          # con el sentido inverso serían 16
    with pytest.raises(ValueError):
        efe_train.parse_trips(many + ", Puerto > Quilpué")
