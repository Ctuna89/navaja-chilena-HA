"""Pruebas de los parsers (sin red ni Home Assistant)."""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

# Cargar api.py/const.py como paquete sin importar homeassistant.
pkg = types.ModuleType("nc")
pkg.__path__ = [str(Path(__file__).parents[1] / "custom_components/navaja_chilena")]
sys.modules["nc"] = pkg
for name in ("const", "api", "santoral"):
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


FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


def test_metro_real_response_no_incidents():
    """Respuesta real: lines vacío + issues false => todas las líneas conocidas operativas."""
    out = api.parse_metro(load("metro_ok.json"))
    assert set(out) == set(api.KNOWN_LINES)
    assert all(l.operational is True for l in out.values())


def test_metro_incident_and_station_codes():
    # En api.xor.cl: 0 operativa, 1 cerrada temporalmente, 2 no habilitada, 3 accesos cerrados
    data = {"api_status": "OK", "issues": True, "lines": [
        {"id": "l2", "name": "Línea 2", "stations": [
            {"name": "C", "status": {"code": "0"}},
            {"name": "D", "status": {"code": "1", "message": "Cerrada"}}]}]}
    out = api.parse_metro(data)
    assert out["l2"].operational is False and out["l2"].stations_with_issues == ["D"]
    assert out["l1"].operational is True            # no listada = sin incidentes


def test_metro_listed_line_with_unreadable_status_is_a_problem():
    data = {"api_status": "OK", "issues": True, "lines": [{"id": "l3", "status": {"code": "?"}}]}
    assert api.parse_metro(data)["l3"].operational is False   # falsa alarma > falso normal


def test_metro_invalid_responses_raise_never_default_to_operational():
    for bad in (
        {"api_status": "ERROR", "issues": False, "lines": []},
        {"api_status": "OK", "lines": []},            # sin 'issues': no hay evidencia
        {"issues": False, "lines": []},               # sin api_status
        {"api_status": "OK", "issues": False},        # sin lista
        [], None, "x",
    ):
        with pytest.raises(api.NavajaApiError):
            api.parse_metro(bad)


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


def test_quakes_real_csn():
    q = api.parse_quakes_csn(load("sismos_csn.json"))
    assert q[0].date == "2026-11-07 23:54:11" and q[0].magnitude == 2.9
    assert q[0].reference == "26 km al E de Sierra Gorda" and q[0].latitude is None


def test_quakes_real_usgs_only_chile():
    raw = load("sismos_usgs.json")
    q = api.parse_quakes_usgs(raw)
    assert all("chile" in x.reference.lower() for x in q)
    assert len(q) < len(raw["features"])              # se descartan los de Argentina
    assert q[0].latitude is not None and q[0].date.endswith("+00:00")


def test_quakes_invalid():
    with pytest.raises(api.NavajaApiError):
        api.parse_quakes_csn([])
    with pytest.raises(api.NavajaApiError):
        api.parse_quakes_usgs({"features": []})


def test_real_samples_other_sources():
    assert api.parse_indicators(load("mindicador.json"))["uf"].value > 10000
    fin = api.parse_indicators(load("findic.json"))
    assert {"uf", "dolar", "ipsa", "yen"} <= set(fin)        # findic trae más indicadores
    hs = api.parse_holidays(load("feriados_boostr.json"))
    assert hs[0].name == "Año Nuevo" and hs[0].inalienable
    air = api.parse_air(load("aire.json"))
    assert air.pm2_5 == 37.7 and air.aqi == 69 and air.uv_index == 0.0
    btc = api.parse_crypto("btc-clp", load("buda_btc.json"))
    assert btc.price > 1_000_000 and btc.change_24h_pct == -0.1


def test_real_stop_ignores_services_without_buses():
    s = api.parse_stop("PC615", load("stop_pc615.json"))
    assert s.name == "AVENIDA LAS CONDES / ESQ. LA CABAÑA"
    assert s.next_minutes is not None
    assert any(not x.buses for x in s.services) and any(x.buses for x in s.services)


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


def test_ipsa_real_and_variation():
    ix = api.parse_stock_index(load("ipsa.json"))
    assert ix.code == "ipsa" and ix.value > 1000 and ix.date > ix.previous_date
    assert ix.change == round(ix.value - ix.previous_value, 2)
    assert ix.change_pct == round(ix.change / ix.previous_value * 100, 2)


def test_ipsa_math_and_edge_cases():
    data = {"codigo": "ipsa", "serie": [{"fecha": "2026-11-06", "valor": 10000},
                                         {"fecha": "2026-11-09", "valor": 10100}]}   # desordenada
    ix = api.parse_stock_index(data)
    assert (ix.value, ix.previous_value, ix.change, ix.change_pct) == (10100, 10000, 100, 1.0)
    one = api.parse_stock_index({"serie": [{"fecha": "2026-11-09", "valor": 5}]})
    assert one.change is None and one.change_pct is None
    for bad in ({}, {"serie": []}, {"serie": "x"}, None):
        with pytest.raises(api.NavajaApiError):
            api.parse_stock_index(bad)


def test_santoral_complete():
    from datetime import date, timedelta
    santoral = sys.modules["nc.santoral"]
    d = date(2024, 1, 1)                                  # año bisiesto: 366 días
    while d.year == 2024:
        assert santoral.saint_of(d).strip(), d
        d += timedelta(days=1)
    assert santoral.saint_of(date(2026, 7, 16)) == "Nuestra Señora del Carmen"
    assert santoral.saint_of(date(2026, 11, 1)) == "Todos los Santos"
    assert santoral.saint_of(date(2026, 12, 25)).startswith("Natividad")


def test_cinemark_real_page():
    html = (FIX / "cinemark_alto_las_condes.html").read_text(encoding="utf-8")
    c = api.parse_cinemark(html)
    assert c.name == "Cinemark Alto Las Condes" and len(c.screenings) == 90
    first = c.screenings[0]
    # La hora escrita (12:00) es la hora local; el sufijo "Z-05:00" es erróneo y se ignora.
    assert first.start.strftime("%Y-%m-%d %H:%M") == "2026-11-10 12:00"
    assert first.start.utcoffset().total_seconds() in (-3 * 3600, -4 * 3600)
    assert first.title and first.screen and first.video_format and first.duration_min
    assert {s.listing_day.isoformat() for s in c.screenings} == {"2026-11-10", "2026-11-11"}


def test_cinemark_late_night_belongs_to_previous_day():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Santiago")
    assert api.listing_day(datetime(2026, 11, 11, 0, 30, tzinfo=tz)).isoformat() == "2026-11-10"
    assert api.listing_day(datetime(2026, 11, 11, 5, 0, tzinfo=tz)).isoformat() == "2026-11-11"


def test_cinemark_invalid_pages():
    for bad in ("", "<html></html>",
                '<script type="application/ld+json">{"@type":"Movie"}</script>',
                '<script type="application/ld+json">no es json</script>'):
        with pytest.raises(api.NavajaApiError):
            api.parse_cinemark(bad)


def test_duration_parsing():
    d = api._duration_min
    assert d("PT2H15M") == 135 and d("PT90M") == 90 and d("PT2H") == 120
    assert d("") is None and d(None) is None and d("PT") is None


def test_nearest_theater():
    assert api.nearest_theater(-33.4489, -70.6693) == "cinemark-portal-nunoa"   # Santiago centro
    assert api.nearest_theater(-36.82, -73.05) == "cinemark-mallplaza-mirador-bio-bio"
    assert api.nearest_theater(-18.48, -70.31) == "cinemark-mallplaza-arica"


def test_ephemerides_real_day_filters_to_chile():
    eph = api.parse_ephemerides(load("efemerides_01-10.json"))
    names = [e.title for e in eph]
    assert "Gabriela Mistral" in names and "Vicente Huidobro" in names and "Raúl Zurita" in names
    assert not any("Estevarena" in n or "Sosa" in n or "Méndez" in n for n in names)   # falsos positivos
    assert eph[0].kind == "fallecimiento" and eph[0].year == 1957            # sucesos > fallecimientos > nacimientos
    births = [e.year for e in eph if e.kind == "nacimiento"]
    assert births == sorted(births)                                          # antiguos primero
    assert eph[0].url.startswith("https://es.wikipedia.org/wiki/")


def test_ephemerides_edge_cases():
    data = {"events": [{"text": "Batalla de Rancagua entre realistas y patriotas.", "year": 1814, "pages": []},
                       {"text": "Se funda una ciudad.", "year": 1541,
                        "pages": [{"title": "Concepción_(Chile)", "description": "ciudad"}]},
                       {"text": "Evento sin relación", "year": 2000, "pages": []},
                       {"text": "", "year": 1, "pages": []}],
            "births": [], "deaths": []}
    eph = api.parse_ephemerides(data)
    assert [e.year for e in eph] == [1541, 1814]
    assert api.parse_ephemerides({"events": [], "births": [], "deaths": []}) == []   # válido: sin efemérides
    for bad in (None, [], {}, {"x": 1}):
        with pytest.raises(api.NavajaApiError):
            api.parse_ephemerides(bad)


def test_efemerides_cl_real_page():
    days = api.parse_efemerides_cl((FIX / "efemerides_cl_2026-11.html").read_text(encoding="utf-8"))
    assert len(days) == 17 and days == sorted(days, key=lambda d: d.date)
    pisagua = days[0]
    assert (pisagua.date.isoformat(), pisagua.year, pisagua.title) == ("2026-11-02", 1879, "Desembarco y Toma de Pisagua")
    assert pisagua.kind == "hecho histórico" and "Pisagua" in pisagua.description
    assert [d.title for d in days if d.date.day == 5] == [
        "Captura de la Esmeralda en El Callao", "Día Mundial sobre la Sensibilización de los Tsunamis"]
    antartica = next(d for d in days if "Antártica" in d.title)
    assert antartica.year is None and antartica.kind == "día conmemorativo"
    assert next(d for d in days if d.title == "Día del Paramédico").description == ""    # sin descripción


def test_efemerides_cl_invalid_pages():
    row = '<td class="t2">05 Noviembre</td><td class="t3"><details><summary>Algo</summary><p>x</p></details></td>'
    ok = f"<title>Efemérides de Chile - Noviembre 2026</title>{row}"
    assert api.parse_efemerides_cl(ok)[0].title == "Algo"
    for bad in ("", "<html></html>", f"<title>Otra cosa</title>{row}",
                "<title>Efemérides de Chile - Noviembre 2026</title>",              # sin filas
                f"<title>Efemérides de Chile - Marte 2026</title>{row}",           # mes desconocido
                f"<title>Efemérides de Chile - Febrero 2026</title>{row}"):        # filas de otro mes
        with pytest.raises(api.NavajaApiError):
            api.parse_efemerides_cl(bad)
