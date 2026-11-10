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
api_const = sys.modules["nc.const"]


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


# --------------------------------------------------------------- Combustibles

from datetime import datetime  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=ZoneInfo("America/Santiago"))
SANTIAGO = (-33.4489, -70.6693)


def fuel_stations():
    brands = api.parse_brands(load("combustibles_marcas.json"))
    return api.parse_stations(load("combustibles_estaciones.json"), brands), brands


def test_fuel_brands_and_stations_real_sample():
    stations, brands = fuel_stations()
    assert {"Copec", "Shell", "Aramco"} <= {b[0] for b in brands.values()}        # nombres legibles
    assert len(stations) >= 40 and all(s.brand and not s.brand.startswith("Marca ") for s in stations)
    assert all(-56 <= s.lat <= -17 for s in stations)


def test_fuel_invalid_data_is_discarded():
    raw = load("combustibles_estaciones.json")["data"]
    stations, _ = fuel_stations()
    ids = {s.id for s in stations}
    absurd = next(e for e in raw if e["id"] == 721)                    # precio de $3
    assert all(p.price >= api.PRICE_MIN for s in stations for p in s.prices.values())
    assert 721 not in ids or "93" not in next(s for s in stations if s.id == 721).prices
    assert 2233 not in ids                                              # en mantenimiento
    comma = next(e for e in raw if e["id"] == 400)                      # latitud con coma decimal
    assert "," in str(comma["latitud"]) and 400 in ids                  # se interpreta bien
    assert absurd["id"] == 721


def test_fuel_prefers_self_service_then_assisted():
    raw = {"data": [
        {"id": 1, "marca": 5, "direccion": "A 1", "latitud": "-33.4", "longitud": "-70.6", "region": "RM", "comuna": "X",
         "gasolinera_bandera": 1, "en_mantenimiento_bandera": 0, "combustibles": [
            {"nombre_corto": "93", "suministra": 1, "precio": "1600.000", "precio_fecha": "2026-11-09 10:00:00"},
            {"nombre_corto": "A93", "suministra": 1, "precio": "1590.000", "precio_fecha": "2026-11-09 10:00:00"},
            {"nombre_corto": "A97", "suministra": 1, "precio": "1700.000", "precio_fecha": "2026-11-09 10:00:00"}]}]}
    s = api.parse_stations(raw)[0]
    assert (s.prices["93"].price, s.prices["93"].attention) == (1600.0, "autoservicio")   # no mezcla niveles
    assert (s.prices["97"].price, s.prices["97"].attention) == (1700.0, "asistido")       # solo hay asistido
    assert "95" not in s.prices and s.brand == "Marca 5"


def test_fuel_cheapest_nearby_filters_radius_and_age():
    stations, _ = fuel_stations()
    near = api.cheapest_nearby(stations, "93", *SANTIAGO, radius_km=5, now=NOW)
    assert near and near == sorted(near, key=lambda c: (c.price.price, c.distance_km))
    assert all(c.distance_km <= 5 for c in near)
    assert all((NOW - c.price.updated).days <= api.PRICE_MAX_AGE_DAYS for c in near)
    wide = api.cheapest_nearby(stations, "93", *SANTIAGO, radius_km=20, now=NOW)
    assert len(wide) >= len(near)
    stale = api.cheapest_nearby(stations, "93", *SANTIAGO, radius_km=20, now=NOW, max_age_days=0)
    assert len(stale) < len(wide)                                      # el filtro de antigüedad funciona
    old = next(s for s in stations if s.id == 1146)                    # precio de hace meses
    assert all(c.station.id != 1146 for c in wide)
    assert old.prices["93"].updated < NOW.replace(month=8)
    assert api.cheapest_nearby(stations, "93", -53.1, -70.9, 5, NOW) == []      # Punta Arenas: nada cerca


def test_fuel_brand_names():
    assert api._brand_name("COPEC") == "Copec" and api._brand_name("JLC") == "JLC" and api._brand_name("HN") == "HN"
    assert api._brand_name("Gasco Autogas") == "Gasco Autogas" and api._brand_name(" SHELL ") == "Shell"


def test_fuel_invalid_responses():
    for bad in (None, [], {}, {"data": "x"}, {"data": []}, {"data": [{"gasolinera_bandera": 0}]}):
        with pytest.raises(api.NavajaApiError):
            api.parse_stations(bad)
    assert api.parse_brands(None) == {} and api.parse_brands({"data": [{"id": "x"}]}) == {}


def test_haversine():
    assert api.haversine_km(*SANTIAGO, *SANTIAGO) == 0
    assert 0.92 < api.haversine_km(-33.4489, -70.6693, -33.4489, -70.6593) < 0.94    # 0,01° de longitud = 111,3 km·cos(33,4°)·0,01


# ----------------------------------------------------------------------- Fútbol

from datetime import date  # noqa: E402

AUDAX, COLO, CHILE = "4138", "2688", "207"


def test_football_team_results_real():
    ms = sorted(api.parse_matches(load("futbol_equipo_resultados.json")), key=lambda m: m.start, reverse=True)
    assert len(ms) == 27 and all(m.finished for m in ms)
    last = ms[0]                                          # 8-nov: Audax 0 - 1 Coquimbo Unido
    assert (last.home.name, last.away.name, last.score_text) == ("Audax Italiano", "Coquimbo Unido", "0-1")
    assert last.result_for(AUDAX) == "perdió" and last.result_for("8186") == "ganó"
    assert last.opponent(AUDAX).name == "Coquimbo Unido" and last.is_home(AUDAX)
    assert last.status == "Tiempo Completo" and last.start.utcoffset().total_seconds() == 0
    assert last.competition and last.venue
    assert last.involves(AUDAX) and not last.involves(COLO)


def test_football_team_fixtures_real():
    ms = api.parse_matches(load("futbol_equipo_proximos.json"))
    assert [m.start.strftime("%m-%d") for m in ms] == ["11-20", "11-29", "12-06"]
    nxt = ms[0]
    assert (nxt.home.name, nxt.away.name) == ("Cobresal", "Audax Italiano") and not nxt.is_home(AUDAX)
    assert nxt.state == "pre" and nxt.status == "Agendado" and nxt.score_text is None   # sin marcador antes de jugar
    assert nxt.result_for(AUDAX) is None and nxt.venue == "Estadio El Cobre" and nxt.away.logo


def test_football_league_calendar_and_matchdays():
    cal = api.parse_calendar(load("futbol_scoreboard_ultima.json"))
    assert len(cal) > 100 and cal == sorted(cal)
    today = date(2026, 11, 10)
    assert api.matchday_dates(cal, today, upcoming=True) == [date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)]
    last = api.matchday_dates(cal, today, upcoming=False)
    assert last and last[-1] == date(2026, 11, 8) and all(d < today for d in last)
    assert api.matchday_dates(cal, date(2027, 6, 1), upcoming=True) == []           # sin más fechas
    assert api.matchday_dates([], today, upcoming=False) == []
    # el día de partido cuenta como «próxima» jornada
    assert api.matchday_dates(cal, date(2026, 11, 20), upcoming=True)[0] == date(2026, 11, 20)


def test_football_round_matches_real():
    day = {d: api.parse_matches(load(f"futbol_scoreboard_{d}.json")) for d in ("20261120", "20261121", "20261122")}
    nxt = sorted(sum(day.values(), []), key=lambda m: m.start)
    assert len(nxt) == 8 and len({t for m in nxt for t in (m.home.id, m.away.id)}) == 16     # juegan los 16 equipos
    last = api.parse_matches(load("futbol_scoreboard_ultima.json"))
    assert len(last) == 6 and all(m.finished and m.score_text for m in last)
    assert {m.competition for m in last}


def test_football_standings_real():
    t = api.parse_standings(load("futbol_tabla.json"))
    assert len(t) == 16 and [r.rank for r in t] == list(range(1, 17))
    first = t[0]
    assert first.team.name == "Colo Colo" and first.points == 61 and first.played == 27
    assert first.wins * 3 + first.draws == first.points or first.points >= first.wins * 3        # coherencia básica
    assert first.goal_diff == first.goals_for - first.goals_against == 29                         # +29 según ESPN
    assert all(r.played == r.wins + r.draws + r.losses for r in t)


def test_football_team_list_matches_espn():
    from_espn = {t["team"]["id"] for t in load("futbol_equipos.json")["sports"][0]["leagues"][0]["teams"]}
    const = sys.modules["nc.const"]
    assert set(const.FOOTBALL_TEAMS) == from_espn                  # si cambia la liga, esta prueba avisa


def test_football_national_real_spanish():
    ms = api.parse_matches(load("futbol_roja_amistosos.json"))
    assert len(ms) == 7 and all(CHILE in (m.home.id, m.away.id) for m in ms)
    mex = max(ms, key=lambda m: m.start)
    assert mex.opponent(CHILE).name == "México" and mex.result_for(CHILE) == "ganó"          # nombres en español
    assert mex.competition == "Amistosos internacionales"


def test_football_live_and_odd_events():
    ev = {"id": "1", "date": "2026-11-20T21:00Z", "league": {"name": "Liga"}, "status": {"displayClock": "67'", "type": {
        "state": "in", "description": "Segundo tiempo"}}, "competitions": [{"competitors": [
        {"homeAway": "home", "score": "2", "team": {"id": "1", "displayName": "A"}},
        {"homeAway": "away", "score": {"displayValue": "1"}, "team": {"id": "2", "displayName": "B", "logos": [{"href": "x.png"}]}}]}]}
    m = api.parse_match(ev)
    assert m.live and not m.finished and m.clock == "67'" and m.score_text == "2-1" and m.away.logo == "x.png"
    assert m.result_for("1") is None                                       # no hay resultado hasta que termina
    for bad in (None, {}, {"date": "x"}, {"date": "2026-01-01T00:00Z", "competitions": [{}]}, "x"):
        assert api.parse_match(bad) is None
    for bad in (None, [], {}, {"events": "x"}):
        with pytest.raises(api.NavajaApiError):
            api.parse_matches(bad)
    assert api.parse_matches({"events": []}) == []                          # sin partidos es válido
    for bad in (None, {}, {"children": []}, {"children": [{"standings": {"entries": []}}]}):
        with pytest.raises(api.NavajaApiError):
            api.parse_standings(bad)
    with pytest.raises(api.NavajaApiError):
        api.parse_calendar({})


# -------------------------------------------------- Beneficios de tarjetas

def test_parse_days():
    d = api.parse_days
    assert d("Todos los miércoles") == {2}
    assert d("Lunes a viernes") == {0, 1, 2, 3, 4}
    assert d("Presencial - Miércoles - Antofagasta") == {2}
    assert d("Venta online, todos los día excepto los martes.") == {0, 2, 3, 4, 5, 6}
    assert d("Fines de semana") == {5, 6}
    assert d("Sábados y domingos") == {5, 6}
    assert d("Todos los días") == set(range(7))
    assert d("De jueves a domingo") == {3, 4, 5, 6}
    assert d("En productos de la tienda.") is None
    assert d("") is None


def test_parse_benefits_real_page():
    page = (Path(__file__).parent / "fixtures/beneficios_comida_bci.html").read_text()
    items = api.parse_benefits(page)
    assert len(items) == 12
    assert api.benefits_page_count(page) == 7
    assert len({b.id for b in items}) == 12
    first = items[0]
    assert first.card == "BCI" and first.title and first.merchant
    assert first.url.startswith("https://www.nbeneficios.cl/beneficios/ver/")
    assert any(b.days is not None for b in items) and any(b.days is None for b in items)
    restored = [api.benefit_from_dict(api.benefit_to_dict(b)) for b in items]
    assert restored == items


def test_benefits_due():
    from datetime import date, datetime
    due = api.benefits_due
    assert due(None, date(2026, 11, 10))
    assert not due(datetime(2026, 11, 10, 9), date(2026, 11, 16))        # 6 días
    assert due(datetime(2026, 11, 10, 9), date(2026, 11, 17))            # 7 días
    assert due(datetime(2026, 10, 30, 9), date(2026, 11, 1))             # día 1, aún no descargado hoy
    assert not due(datetime(2026, 11, 1, 8), date(2026, 11, 1))          # día 1 ya descargado
    assert due(datetime(2026, 11, 1, 8), date(2026, 11, 8))


def test_months_limit_benefit():
    assert api.parse_months("Presencial - Sábado - Lo Barnechea los sábados de enero.") == {1}
    assert api.parse_months("Online - Todos los miércoles de noviembre.") == {11}
    assert api.parse_months("Todos los días") is None
    page = (Path(__file__).parent / "fixtures/beneficios_comida_bci.html").read_text()
    baza = next(b for b in api.parse_benefits(page) if b.merchant == "Baza")
    assert baza.applies_on(5, 1) is True and baza.applies_on(5, 11) is False


def test_validity_end_discards_expired():
    from datetime import date
    assert api.parse_until("Promoción válida hasta el 31 de diciembre de 2026.") == date(2026, 12, 31)
    assert api.parse_until("Promoción válida del 01 al 30 de noviembre de 2026.") == date(2026, 11, 30)
    assert api.parse_until("Venta online") is None
    b = api.Benefit("1", "X", "comida", "M", "t", "d", "u", None, frozenset({1}), None, date(2026, 11, 30))
    assert b.applies_on(1, 11, date(2026, 11, 24)) is True
    assert b.applies_on(1, 12, date(2026, 12, 1)) is False
    assert api.benefit_from_dict(api.benefit_to_dict(b)) == b


# ------------------------------------------- Descuentos en bencina (calendario)

def _calendar():
    return api.parse_fuel_discounts(json.loads((Path(__file__).parents[1] / "data/bencina.json").read_text()))


def test_fuel_discount_calendar_file_is_valid():
    cal = _calendar()
    assert len(cal.items) >= 5
    assert all(d.source.startswith("https://") for d in cal.items)
    assert {d.card for d in cal.items} <= set(api_const.BENEFIT_CARDS)


def test_fuel_discounts_for_today_and_next():
    from datetime import date
    cal = _calendar()
    tue = date(2026, 11, 10)                                   # martes
    today, nxt, upcoming = api.fuel_discounts_for(cal, ["bancoestado", "bci"], tue)
    assert [d.card for d in today] == ["bancoestado"] and nxt == 4 and [d.card for d in upcoming] == ["bci"]
    sat = date(2026, 11, 14)                                   # sábado: sin descuentos, el próximo es el martes
    today, nxt, upcoming = api.fuel_discounts_for(cal, ["itau", "bancoestado"], sat)
    assert today == [] and nxt == 2 and len(upcoming) == 2
    assert api.fuel_discounts_for(cal, ["santander"], tue) == ([], None, [])


def test_fuel_discounts_current_month_and_bad_rows():
    from datetime import date
    cal = _calendar()
    assert api.fuel_discounts_current(cal, date(2026, 11, 30)) and not api.fuel_discounts_current(cal, date(2026, 12, 1))
    bad = api.parse_fuel_discounts({"vigencia": "2026-11", "descuentos": [{"dias": [9], "tarjeta": "x", "monto": "y"}, {"tarjeta": "x"}, {"dias": [1], "tarjeta": "bci", "monto": "7%"}]})
    assert len(bad.items) == 1 and bad.items[0].card == "bci"
    with pytest.raises(api.NavajaApiError):
        api.parse_fuel_discounts({"descuentos": []})


def test_bencina_validator_rejects_implausible_data():
    spec = importlib.util.spec_from_file_location("validar", Path(__file__).parents[1] / "data/validar.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    good = json.loads((Path(__file__).parents[1] / "data/bencina.json").read_text())
    assert v.validar(good) == []
    bad = json.loads(json.dumps(good))
    bad["descuentos"][0].update({"ahorro_clp_litro": 5000, "tarjeta": "inventada", "fuente": "http://x"})
    bad["descuentos"][1]["dias"] = [8]
    assert len(v.validar(bad)) >= 4
    assert v.validar({"vigencia": "2026-11", "actualizado": "2026-11-01", "descuentos": []})


# ------------------------------------------------------------ Red Regional

def _regional_now():
    from datetime import datetime, timezone
    return datetime.fromtimestamp(1794340000, tz=timezone.utc)


def test_regional_codes():
    assert api.parse_regional_codes("p60094, 1253;merval-01  1253") == ["P60094", "1253", "MERVAL-01"]
    assert api.parse_regional_codes("") == []
    with pytest.raises(ValueError):
        api.parse_regional_codes("ab cd/ef")


def test_regional_stop_arrivals_sorted_and_past_dropped():
    raw = json.loads((Path(__file__).parent / "fixtures/regional_parada_53.json").read_text())
    stop = api.parse_regional_stop(raw, "53", "Parada de prueba", _regional_now())
    assert stop.name == "Parada de prueba" and stop.arrivals
    etas = [a.eta for a in stop.arrivals]
    assert etas == sorted(etas)
    assert all(e >= _regional_now().replace(second=0) - __import__("datetime").timedelta(minutes=2) for e in etas)
    assert {a.direction for a in stop.arrivals} <= {"ida", "regreso"}
    # con la hora muy adelantada, todo "ya pasó"
    from datetime import timedelta
    assert api.parse_regional_stop(raw, "53", "x", _regional_now() + timedelta(days=1)).arrivals == ()


def test_regional_alerts_are_plain_text():
    raw = json.loads((Path(__file__).parent / "fixtures/regional_parada_P60094_alertas.json").read_text())
    stop = api.parse_regional_stop(raw, "P60094", "x", _regional_now())
    assert stop.alerts and all("<" not in a and "Alerta GPS" in a for a in stop.alerts)


def test_regional_bad_response_is_an_error():
    with pytest.raises(api.NavajaApiError):
        api.parse_regional_stop({"foo": 1}, "1", "x", _regional_now())


def test_regional_stop_names_from_gtfs():
    import io, zipfile
    csv_text = (Path(__file__).parent / "fixtures/regional_stop.csv").read_text()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("stop.csv", csv_text)
    names = api.parse_regional_stop_names(buf.getvalue())
    assert names["75"] == "1 Norte esq. 1 Oriente" and len(names) >= 10
    with pytest.raises(api.NavajaApiError):
        api.parse_regional_stop_names(b"no es un zip")


# ----------------------------------------------------------------- Noticias

NEWS_DIR = Path(__file__).parent / "fixtures"


def test_news_latercera_feed():
    feed = api.parse_news_feed((NEWS_DIR / "noticias_latercera_nacional.xml").read_text(), "La Tercera")
    assert len(feed) == 4
    cat, item = feed[0]
    assert cat == "nacional" and item.source == "La Tercera"
    assert item.title and item.url.startswith("https://www.latercera.com/") and item.published.tzinfo is not None
    assert item.summary and "<" not in item.summary


def test_news_cooperativa_feed_uses_short_summary_and_category():
    feed = api.parse_news_feed((NEWS_DIR / "noticias_cooperativa_3.xml").read_text(), "Cooperativa")
    assert feed and all(i.url.startswith("https://www.cooperativa.cl/") for _c, i in feed)
    assert {c for c, _i in feed} <= {"pais", "economia"}
    assert all("whatsapp" not in i.summary.lower() and "<" not in i.summary for _c, i in feed)
    assert all(len(i.summary) <= 220 for _c, i in feed)


def test_news_feed_rejects_xml_entities_and_garbage():
    with pytest.raises(api.NavajaApiError):
        api.parse_news_feed('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss><channel></channel></rss>', "x")
    with pytest.raises(api.NavajaApiError):
        api.parse_news_feed("no es xml", "x")
    assert api.parse_news_feed("<rss><channel><item><title>Sin enlace</title></item></channel></rss>", "x") == []


def test_news_merge_sorts_dedupes_and_limits():
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    mk = lambda t, m, u, src="La Tercera": api.NewsItem(t, src, u, base + timedelta(minutes=m), "")
    data = {"nacional": [mk("a", 1, "https://x/a"), mk("b", 5, "https://x/b"), mk("a otra vez", 2, "https://x/a", "Cooperativa"), mk("c", 3, "https://x/c")]}
    out = api.merge_news(data, ["nacional", "mundo"], 2)
    assert [n.title for n in out["nacional"]] == ["b", "c"] and "mundo" not in out


# ----------------------------------------------------------------- Documentación

def test_docs_yaml_images_and_links_are_valid():
    import re
    import yaml
    root = Path(__file__).parents[1]
    raw_prefix = "https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/"
    for name in ("README.md", "docs/tarjetas.md"):
        text = (root / name).read_text(encoding="utf-8")
        for block in re.findall(r"```yaml\n(.*?)```", text, re.S):
            yaml.safe_load(block)                      # cada ejemplo es YAML válido
        for url in re.findall(r"\]\((https://raw\.githubusercontent\.com/Ctuna89/navaja-chilena-HA/main/[^)]+)\)", text):
            assert (root / url[len(raw_prefix):]).is_file(), f"{name}: falta la imagen {url}"
        for target in re.findall(r"\]\(((?:\.\./|docs/|data/)[^)#]+)", text):
            base = root / "docs" if name.startswith("docs/") else root
            assert (base / target).resolve().exists(), f"{name}: enlace roto {target}"
    assert "docs/tarjetas.md" in (root / "README.md").read_text(encoding="utf-8")
