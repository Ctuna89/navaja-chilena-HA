"""Pruebas dentro de Home Assistant (requieren pytest-homeassistant-custom-component)."""

from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.navaja_chilena import api  # noqa: E402
from custom_components.navaja_chilena.const import (  # noqa: E402
    AIR_URL, CINEMARK_URL, CRYPTO_URL, EPHEMERIDES_URL, FUEL_BRANDS_URL, FUEL_URL, HOLIDAYS_URLS, IPSA_URL, DOMAIN, INDICATORS_URL, METRO_URL, PHARMACY_URL, QUAKES_CSN_URL,
    QUAKES_URL, STOP_URL,
)

STOP = {"id": "PC615", "status_description": "Servicio en horario normal", "services": [
    {"id": "210", "status_description": "Buses disponibles",
     "buses": [{"id": "X", "min_arrival_time": 5, "max_arrival_time": 8}]}]}
INDICATORS = {"version": "1", "uf": {"codigo": "uf", "nombre": "UF", "unidad_medida": "Pesos",
              "fecha": "2026-11-07T03:00:00.000Z", "valor": 39000.5},
              "dolar": {"codigo": "dolar", "nombre": "Dólar", "unidad_medida": "Pesos",
              "fecha": "2026-11-07T03:00:00.000Z", "valor": 950.2}}
METRO = {"api_status": "OK", "issues": True, "lines": [
    {"id": "l2", "name": "Línea 2", "stations": [{"name": "B", "status": {"code": "1"}}]}]}
CSN = [{"Fecha": "2026-11-07 23:54:11", "Profundidad": "74", "Magnitud": "2.9",
        "RefGeografica": "26 km al E de Sierra Gorda"}]
BUDA = {"ticker": {"last_price": ["74385376.0", "CLP"], "price_variation_24h": "-0.001",
                   "price_variation_7d": "-0.038", "volume": ["0.5", "BTC"]}}
QUAKES = {"features": [{"properties": {"mag": 4.5, "place": "10 km N of Ovalle, Chile",
          "time": 1_762_500_000_000}, "geometry": {"coordinates": [-71.2, -30.5, 30.0]}}]}
HOLIDAYS = [{"nombre": "Navidad", "fecha": "2099-12-25", "irrenunciable": "1", "tipo": "Civil"}]
AIR = {"current": {"pm10": 30, "pm2_5": 12, "us_aqi": 55, "uv_index": 7}}
PHARM = [{"comuna_nombre": "ÑUÑOA", "local_nombre": "Cruz", "local_direccion": "X 1"}]

DATA = {"indicators": ["uf", "dolar"], "metro": True, "stops": "PC615", "quakes": True,
        "holidays": True, "air": True, "crypto": True, "bolsa": True, "saint": True, "pharmacy_comuna": "Ñuñoa"}


def mock_all(mock, metro_status=200):
    mock.get(INDICATORS_URL, json=INDICATORS)
    mock.get(METRO_URL, json=METRO, status=metro_status)
    mock.get(STOP_URL.format(code="PC615"), json=STOP)
    mock.get(QUAKES_URL, json=QUAKES)
    mock.get(IPSA_URL, json={"codigo": "ipsa", "serie": [{"fecha": "2026-11-09", "valor": 10100}, {"fecha": "2026-11-06", "valor": 10000}]})
    mock.get(QUAKES_CSN_URL, json=CSN)
    for m in ('btc-clp', 'eth-clp'):
        mock.get(CRYPTO_URL.format(market=m), json=BUDA)
    mock.get(PHARMACY_URL, json=PHARM)
    mock.get(AIR_URL.format(lat=32.87336, lon=-117.22743), json=AIR)
    from custom_components.navaja_chilena.const import HOLIDAYS_URLS
    for url in HOLIDAYS_URLS:
        for year in range(2024, 2030):
            mock.get(url.format(year=year), json=HOLIDAYS)


class _States(dict):
    """Busca por el final del nombre (HA antepone el nombre del dispositivo)."""

    def __getitem__(self, key):
        for name, value in self.items():
            if name.endswith(key):
                return value
        raise KeyError(key)


def states(hass):
    return _States({s.name: s.state for s in hass.states.async_all("sensor")})


async def setup(hass, aioclient_mock, **kw):
    mock_all(aioclient_mock, **kw)
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_metro_states(hass, aioclient_mock, monkeypatch):
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: True)
    await setup(hass, aioclient_mock)
    st = states(hass)
    assert st["Línea 1"] == "operativa"          # no listada = sin incidentes
    line1 = next(x for x in hass.states.async_all("sensor") if x.name.endswith("Línea 1"))
    assert line1.attributes["device_class"] == "enum"
    assert line1.attributes["options"] == ["operativa", "con_problemas", "cerrada"]   # estados traducibles
    assert st["Línea 2"] == "con_problemas"
    assert st["UF"] == "39000.5"
    assert st["Paradero PC615"] == "5"
    assert st["Último sismo (CSN)"] == "2.9"
    assert st["Último sismo con coordenadas (USGS)"] == "4.5"
    assert st["Bitcoin"] == "74385376.0"
    assert st["IPSA"] == "10100.0"
    from homeassistant.util import dt as dt_util
    from custom_components.navaja_chilena.santoral import saint_of
    assert st["Santo del día"] == saint_of(dt_util.now().date())
    ipsa = next(s for s in hass.states.async_all("sensor") if s.name.endswith("IPSA"))
    assert ipsa.attributes["variacion_pct"] == 1.0 and ipsa.attributes["variacion_puntos"] == 100
    assert st["Próximo feriado"] == "2099-12-25"
    assert st["PM2.5"] == "12.0"
    assert st["Ñuñoa"] == "1"


async def test_metro_closed_outside_hours(hass, aioclient_mock, monkeypatch):
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: False)
    await setup(hass, aioclient_mock)
    st = states(hass)
    assert st["Línea 1"] == "cerrada" and st["Línea 2"] == "cerrada"


async def test_metro_down_does_not_break_the_rest(hass, aioclient_mock, monkeypatch):
    """Si la fuente del Metro falla, jamás se ve 'operativa' y lo demás sigue funcionando."""
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: True)
    entry = await setup(hass, aioclient_mock, metro_status=404)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    st = states(hass)
    assert st["UF"] == "39000.5" and st["Paradero PC615"] == "5"
    assert not any("Línea" in k for k in st)          # no se inventan líneas ni estados


async def test_metro_recovers_and_lines_appear(hass, aioclient_mock, monkeypatch):
    from datetime import timedelta
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: True)
    await setup(hass, aioclient_mock, metro_status=404)
    aioclient_mock.clear_requests()
    mock_all(aioclient_mock)                          # el Metro vuelve
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert states(hass)["Línea 1"] == "operativa"


async def test_all_sources_down_retries_setup(hass, aioclient_mock):
    aioclient_mock.get(INDICATORS_URL, status=500)
    entry = MockConfigEntry(domain=DOMAIN, data={"indicators": ["uf"], "metro": False})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_config_and_options_flow(hass, aioclient_mock):
    aioclient_mock.get(STOP_URL.format(code="PC615"), json=STOP)
    aioclient_mock.get(STOP_URL.format(code="PA433"), status=400)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert r["type"] is FlowResultType.FORM
    bad = await hass.config_entries.flow.async_configure(r["flow_id"], {**DATA, "stops": "PA433"})
    assert bad["errors"] == {"stops": "stop_not_found"}
    bad = await hass.config_entries.flow.async_configure(r["flow_id"], {**DATA, "stops": "xx"})
    assert bad["errors"] == {"stops": "invalid_stop"}
    ok = await hass.config_entries.flow.async_configure(r["flow_id"], {**DATA, "stops": "pc615"})
    assert ok["type"] is FlowResultType.CREATE_ENTRY and ok["data"]["stops"] == "PC615"


async def test_options_flow_opens(hass, aioclient_mock, monkeypatch):
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: True)
    entry = await setup(hass, aioclient_mock)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "init"
    r = await hass.config_entries.options.async_configure(r["flow_id"], {**DATA, "air": False})
    assert r["type"] is FlowResultType.CREATE_ENTRY


async def test_legacy_entry_does_not_crash(hass, aioclient_mock, monkeypatch):
    """Una entrada de la versión 1.x (solo paraderos) debe cargar con valores por defecto."""
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: True)
    mock_all(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data={"stops": ["PC615"]})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED


CINEMA_HTML = (Path(__file__).parent / "fixtures" / "cinemark_alto_las_condes.html").read_text(encoding="utf-8")


async def test_cinema_sensor_shows_today(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 15:00:00-03:00")
    mock_all(aioclient_mock)
    aioclient_mock.get(CINEMARK_URL.format(slug="cinemark-alto-las-condes"), text=CINEMA_HTML)
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, "cinema": "cinemark-alto-las-condes"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    s = next(x for x in hass.states.async_all("sensor") if x.name.endswith("Cartelera de hoy"))
    movies = s.attributes["peliculas"]
    assert int(s.state) == len(movies) and len(movies) > 5
    assert s.attributes["cine"] == "Cinemark Alto Las Condes" and s.attributes["fecha"] == "2026-11-10"
    assert all(m["funciones"] for m in movies) and s.attributes["resumen"].count("\n") == len(movies) - 1
    nxt = s.attributes["proxima_funcion"]
    assert nxt and nxt["hora"] >= "15:00"                 # ya pasó la función de las 12:00
    assert nxt["poster"].startswith("https://cdn.cinemark.cl/content/posters/")
    assert s.attributes["entity_picture"] == nxt["poster"]    # la tarjeta nativa muestra el póster
    assert all(m["poster"] for m in movies)


async def test_cinema_nearest_uses_home_location(hass, aioclient_mock):
    hass.config.latitude, hass.config.longitude = -33.4489, -70.6693   # Santiago centro
    mock_all(aioclient_mock)
    aioclient_mock.get(CINEMARK_URL.format(slug="cinemark-portal-nunoa"), text=CINEMA_HTML)
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, "cinema": "nearest"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.cinema_slug == "cinemark-portal-nunoa"


async def test_cinema_down_does_not_break_the_rest(hass, aioclient_mock, monkeypatch):
    monkeypatch.setattr(api, "metro_is_open", lambda *a, **k: True)
    mock_all(aioclient_mock)
    aioclient_mock.get(CINEMARK_URL.format(slug="cinemark-alto-las-condes"), status=503)
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, "cinema": "cinemark-alto-las-condes"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert states(hass)["UF"] == "39000.5"


CL_HTML = (Path(__file__).parent / "fixtures" / "efemerides_cl_2026-11.html").read_text(encoding="utf-8")

def _wiki_payload():
    import json as _json
    return _json.loads((Path(__file__).parent / "fixtures" / "efemerides_01-10.json").read_text())


async def _setup_ephemerides(hass, aioclient_mock, day, cl=True, wiki=True, wiki_status=200):
    from custom_components.navaja_chilena.const import EPHEMERIDES_CL_URL
    mock_all(aioclient_mock)
    if cl:
        aioclient_mock.get(EPHEMERIDES_CL_URL, text=CL_HTML)
    else:
        aioclient_mock.get(EPHEMERIDES_CL_URL, status=503)
    aioclient_mock.get(EPHEMERIDES_URL.format(month=day[0], day=day[1]),
                       json=_wiki_payload() if wiki else {}, status=wiki_status if wiki else 500)
    entry = MockConfigEntry(domain=DOMAIN, data={"indicators": [], "metro": False, "ephemerides": True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _by_name(hass, suffix):
    return next(x for x in hass.states.async_all("sensor") if x.name.endswith(suffix))


async def test_ephemerides_combines_both_sources(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-05 10:00:00-03:00")          # dos entradas en efemerides.cl
    await _setup_ephemerides(hass, aioclient_mock, (11, 5))
    s = _by_name(hass, "Efemérides de hoy")
    assert s.state == "1820: Captura de la Esmeralda en El Callao"        # efemerides.cl manda
    items = s.attributes["efemerides"]
    assert [i["fuente"] for i in items[:2]] == ["efemerides.cl", "efemerides.cl"]
    assert any(i["fuente"].startswith("Wikipedia") for i in items)         # y Wikipedia complementa
    assert s.attributes["fuentes"] == {"efemerides.cl": True, "wikipedia": True}
    nxt = _by_name(hass, "Próximo día significativo")
    assert nxt.state == "Día de la Antártica Chilena" and nxt.attributes["dias_restantes"] == 1
    assert nxt.attributes["fecha"] == "2026-11-06" and nxt.attributes["fuente"] == "efemerides.cl"


async def test_ephemerides_day_without_cl_entry_falls_back_to_wikipedia(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 10:00:00-03:00")          # el 10 no figura en efemerides.cl
    await _setup_ephemerides(hass, aioclient_mock, (11, 10))
    s = _by_name(hass, "Efemérides de hoy")
    assert s.state.startswith("1957: Gabriela Mistral")
    assert all(i["fuente"].startswith("Wikipedia") for i in s.attributes["efemerides"])
    assert _by_name(hass, "Próximo día significativo").state == "Día del Asistente Social"


async def test_ephemerides_one_source_down_other_keeps_working(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-05 10:00:00-03:00")
    await _setup_ephemerides(hass, aioclient_mock, (11, 5), cl=False)       # efemerides.cl caído
    s = _by_name(hass, "Efemérides de hoy")
    assert s.attributes["fuentes"] == {"efemerides.cl": False, "wikipedia": True}
    assert s.state != "unavailable" and s.attributes["total"] > 0
    assert _by_name(hass, "Próximo día significativo").state == "unavailable"   # no se inventa

    aioclient_mock.clear_requests()
    from custom_components.navaja_chilena.const import EPHEMERIDES_CL_URL
    aioclient_mock.get(EPHEMERIDES_CL_URL, text=CL_HTML)                    # vuelve a funcionar
    aioclient_mock.get(EPHEMERIDES_URL.format(month=11, day=5), json=_wiki_payload())
    from datetime import timedelta
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _by_name(hass, "Efemérides de hoy").attributes["fuentes"]["efemerides.cl"] is True
    assert _by_name(hass, "Próximo día significativo").state == "Día de la Antártica Chilena"


async def test_ephemerides_each_source_queried_once_per_day(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-05 10:00:00-03:00")
    entry = await _setup_ephemerides(hass, aioclient_mock, (11, 5))
    before = aioclient_mock.call_count
    await entry.runtime_data.ephemerides.async_refresh()
    await entry.runtime_data.ephemerides.async_refresh()
    assert aioclient_mock.call_count == before


async def test_ephemerides_both_down_is_unavailable_not_empty(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-05 10:00:00-03:00")
    entry = await _setup_ephemerides(hass, aioclient_mock, (11, 5), cl=False, wiki=False)
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


# --------------------------------------------------------------- Vehículo

VEH = {"indicators": [], "metro": False, "vehicle_digit": "8", "vehicle_type": "sello_verde"}


def _veh(hass, name):
    pool = list(hass.states.async_all("sensor")) + list(hass.states.async_all("binary_sensor"))
    return next(x for x in pool if x.name.endswith(name))


async def _setup_vehicle(hass, aioclient_mock, data=None, holidays=None):
    if holidays is not None:
        for year in (2026, 2027):
            aioclient_mock.get(HOLIDAYS_URLS[0].format(year=year),
                               json={"status": "success", "data": [{"date": d, "title": "Feriado de prueba"} for d in holidays]})
    mock_all(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data=data or VEH)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_vehicle_restricted_in_season(hass, aioclient_mock, freezer):
    freezer.move_to("2026-06-08 10:00:00-04:00")          # lunes de la temporada 2026
    await _setup_vehicle(hass, aioclient_mock)
    b = _veh(hass, "Restricción vehicular hoy")
    assert b.state == "on" and b.attributes["digitos_hoy"] == "8-9" and b.attributes["tu_digito"] == 8
    assert b.attributes["rige_ahora"] is True and b.attributes["horario"] == "07:30–21:00"
    assert "preemergencia" in b.attributes["aviso"]
    assert _veh(hass, "Dígitos con restricción hoy").state == "8-9"
    nxt = _veh(hass, "Próxima restricción")
    assert nxt.state == "2026-06-08" and nxt.attributes["es_hoy"] is True
    assert nxt.attributes["temporada"] == "01-05-2026 al 31-08-2026"
    rev = _veh(hass, "Mes de revisión técnica")
    assert rev.state == "Noviembre" and rev.attributes["meses_restantes"] == 5 and rev.attributes["este_mes"] is False
    assert _veh(hass, "Revisión técnica este mes").state == "off"


async def test_vehicle_free_digit_and_next_date(hass, aioclient_mock, freezer):
    freezer.move_to("2026-06-09 10:00:00-04:00")          # martes: dígitos 0-1
    await _setup_vehicle(hass, aioclient_mock)
    b = _veh(hass, "Restricción vehicular hoy")
    assert b.state == "off" and b.attributes["motivo"] == "Tu dígito no está restringido hoy"
    assert _veh(hass, "Dígitos con restricción hoy").state == "0-1"
    assert _veh(hass, "Próxima restricción").state == "2026-06-15"      # lunes siguiente


async def test_vehicle_holiday_is_respected(hass, aioclient_mock, freezer):
    freezer.move_to("2026-06-08 10:00:00-04:00")
    await _setup_vehicle(hass, aioclient_mock, holidays=["2026-06-08"])    # el lunes es festivo
    b = _veh(hass, "Restricción vehicular hoy")
    assert b.state == "off" and b.attributes["motivo"] == "Festivo: no hay restricción"
    assert b.attributes["festivos_considerados"] is True
    assert _veh(hass, "Próxima restricción").state == "2026-06-15"


async def test_vehicle_out_of_season(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 10:00:00-03:00")
    await _setup_vehicle(hass, aioclient_mock)
    b = _veh(hass, "Restricción vehicular hoy")
    assert b.state == "off" and b.attributes["motivo"] == "Fuera de la temporada de restricción"
    assert _veh(hass, "Dígitos con restricción hoy").state == "Ninguno"
    nxt = _veh(hass, "Próxima restricción")
    assert nxt.state == "unknown" and "motivo" in nxt.attributes
    assert _veh(hass, "Revisión técnica este mes").state == "on"          # dígito 8 = noviembre


async def test_vehicle_no_resolution_year_is_unavailable_not_guessed(hass, aioclient_mock, freezer):
    freezer.move_to("2027-06-07 10:00:00-04:00")
    await _setup_vehicle(hass, aioclient_mock)
    assert _veh(hass, "Restricción vehicular hoy").state == "unavailable"
    assert _veh(hass, "Dígitos con restricción hoy").state == "unavailable"
    assert _veh(hass, "Mes de revisión técnica").state == "Noviembre"      # la revisión no depende de la resolución


async def test_vehicle_exempt_type(hass, aioclient_mock, freezer):
    freezer.move_to("2026-06-08 10:00:00-04:00")
    await _setup_vehicle(hass, aioclient_mock, data={**VEH, "vehicle_type": "sello_verde_posterior"})
    b = _veh(hass, "Restricción vehicular hoy")
    assert b.state == "off" and b.attributes["motivo"] == "Tu tipo de vehículo no tiene restricción"


async def test_vehicle_works_offline(hass, aioclient_mock, freezer):
    """Sin internet (ni festivos) el módulo sigue funcionando y la entrada carga."""
    freezer.move_to("2026-06-08 10:00:00-04:00")
    entry = MockConfigEntry(domain=DOMAIN, data=VEH)       # nada está mockeado: toda consulta falla
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    b = _veh(hass, "Restricción vehicular hoy")
    assert b.state == "on" and b.attributes["festivos_considerados"] is False


async def test_vehicle_updates_at_midnight(hass, aioclient_mock, freezer):
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    await hass.config.async_set_time_zone("America/Santiago")
    freezer.move_to("2026-06-08 23:00:00-04:00")
    await _setup_vehicle(hass, aioclient_mock)
    assert _veh(hass, "Restricción vehicular hoy").state == "on"
    freezer.move_to("2026-06-09 00:00:10-04:00")           # martes: dígito 8 ya no
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _veh(hass, "Restricción vehicular hoy").state == "off"


async def test_vehicle_holidays_feed_metro_without_holiday_module(hass, aioclient_mock):
    """El dato de festivos se obtiene solo cuando lo necesita el Metro, sin crear sensores de feriados."""
    mock_all(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data={"indicators": [], "metro": True, "holidays": False})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.holidays is not None and entry.runtime_data.holidays_visible is False
    assert not any("feriado" in s.name.lower() for s in hass.states.async_all("sensor"))


async def test_options_flow_saves_vehicle(hass, aioclient_mock):
    entry = await _setup_vehicle(hass, aioclient_mock)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {**VEH, "vehicle_digit": "3", "vehicle_type": "sin_sello_fuera_anillo"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["vehicle_digit"] == "3" and r["data"]["vehicle_type"] == "sin_sello_fuera_anillo"


async def test_saint_updates_at_midnight(hass, aioclient_mock, freezer):
    """Regresión: la actualización de medianoche debe correr en el bucle de eventos (@callback)."""
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    await hass.config.async_set_time_zone("America/Santiago")
    freezer.move_to("2026-11-10 23:59:00-03:00")
    mock_all(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data={"indicators": [], "metro": False, "saint": True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _veh(hass, "Santo del día").state == "San León Magno"
    freezer.move_to("2026-11-11 00:00:10-03:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _veh(hass, "Santo del día").state == "San Martín de Tours"


# -------------------------------------------------------------- Combustibles

FIX_DIR = Path(__file__).parent / "fixtures"


async def _setup_fuel(hass, aioclient_mock, fuel_status=200, brands_status=200, **extra):
    import json as _json
    hass.config.latitude, hass.config.longitude = -33.4489, -70.6693            # Santiago centro
    mock_all(aioclient_mock)
    aioclient_mock.get(FUEL_URL, json=_json.loads((FIX_DIR / "combustibles_estaciones.json").read_text()), status=fuel_status)
    aioclient_mock.get(FUEL_BRANDS_URL, json=_json.loads((FIX_DIR / "combustibles_marcas.json").read_text()), status=brands_status)
    data = {"indicators": ["uf"], "metro": False, "fuel_types": ["93", "DI"], "fuel_radius": "5", "fuel_max_age": "30", **extra}
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_fuel_cheapest_near_home(hass, aioclient_mock, freezer):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    freezer.move_to("2026-11-10 12:00:00-03:00")
    entry = await _setup_fuel(hass, aioclient_mock)
    s93 = _veh(hass, "Gasolina 93 más barata")
    stations = entry.runtime_data.fuel.data
    expected = api.cheapest_nearby(stations, "93", -33.4489, -70.6693, 5,
                                   datetime(2026, 11, 10, 12, tzinfo=ZoneInfo("America/Santiago")), 30)
    assert expected and float(s93.state) == expected[0].price.price
    a = s93.attributes
    assert a["unit_of_measurement"] == "CLP/L" and a["radio_km"] == 5.0
    assert a["estaciones_en_radio"] == len(expected) and a["marca"] == expected[0].station.brand
    assert a["distancia_km"] <= 5 and 1000 < a["promedio_en_radio"] < 3000
    prices = [x["precio"] for x in a["mas_baratas"]]
    assert prices == sorted(prices) and len(prices) == min(5, len(expected)) and prices[0] == float(s93.state)
    assert a["entity_picture"].startswith("https://") and "latitude" in a
    assert _veh(hass, "Diésel más barato").state not in ("unknown", "unavailable")      # nombre en masculino
    assert not any("Gasolina 95" in x.name for x in hass.states.async_all("sensor"))   # solo los elegidos


async def test_fuel_nothing_in_radius_is_unknown_with_reason(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 12:00:00-03:00")
    await _setup_fuel(hass, aioclient_mock)
    hass.config.latitude, hass.config.longitude = -53.1, -70.9                  # Punta Arenas: sin estaciones en la muestra
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await entry.runtime_data.fuel.async_refresh()
    await hass.async_block_till_done()
    s = _veh(hass, "Gasolina 93 más barata")
    assert s.state == "unknown" and "No hay estaciones" in s.attributes["motivo"]


async def test_fuel_stale_prices_are_ignored(hass, aioclient_mock, freezer):
    freezer.move_to("2027-03-10 12:00:00-03:00")                                 # meses después: todos los precios son viejos
    await _setup_fuel(hass, aioclient_mock)
    assert _veh(hass, "Gasolina 93 más barata").state == "unknown"


async def test_fuel_source_down_does_not_break_the_rest(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 12:00:00-03:00")
    entry = await _setup_fuel(hass, aioclient_mock, fuel_status=503)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert states(hass)["UF"] == "39000.5"
    assert _veh(hass, "Gasolina 93 más barata").state == "unavailable"          # nunca un precio inventado


async def test_fuel_brands_endpoint_failure_is_not_fatal(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 12:00:00-03:00")
    await _setup_fuel(hass, aioclient_mock, brands_status=500)
    s = _veh(hass, "Gasolina 93 más barata")
    assert float(s.state) > 0 and s.attributes["marca"].startswith("Marca ")     # sin nombre, pero con precio


async def test_fuel_options_flow(hass, aioclient_mock, freezer):
    freezer.move_to("2026-11-10 12:00:00-03:00")
    entry = await _setup_fuel(hass, aioclient_mock)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"indicators": ["uf"], "metro": False, "fuel_types": ["95", "97"], "fuel_radius": "10", "fuel_max_age": "7"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["fuel_types"] == ["95", "97"] and r["data"]["fuel_radius"] == "10" and r["data"]["fuel_max_age"] == "7"


async def test_fuel_max_age_option_changes_result(hass, aioclient_mock, freezer):
    """Con un tope más estricto se consideran menos estaciones (y el precio puede subir)."""
    freezer.move_to("2026-11-10 12:00:00-03:00")
    entry = await _setup_fuel(hass, aioclient_mock, fuel_max_age="30")
    wide = _veh(hass, "Gasolina 93 más barata")
    n30 = wide.attributes["estaciones_en_radio"]
    assert wide.attributes["max_antiguedad_dias"] == 30 and wide.attributes["antiguedad_dias"] <= 30
    hass.config_entries.async_update_entry(entry, data={**entry.data, "fuel_max_age": "7"})
    await hass.async_block_till_done()
    strict = _veh(hass, "Gasolina 93 más barata")
    assert strict.attributes["max_antiguedad_dias"] == 7
    assert strict.attributes.get("estaciones_en_radio", 0) <= n30
    if strict.state != "unknown":
        assert strict.attributes["antiguedad_dias"] <= 7 and float(strict.state) >= float(wide.state)
