"""Pruebas dentro de Home Assistant (requieren pytest-homeassistant-custom-component)."""

from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.navaja_chilena import api  # noqa: E402
from custom_components.navaja_chilena.const import (  # noqa: E402
    AIR_URL, CINEMARK_URL, CRYPTO_URL, EPHEMERIDES_URL, IPSA_URL, DOMAIN, INDICATORS_URL, METRO_URL, PHARMACY_URL, QUAKES_CSN_URL,
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


async def test_ephemerides_sensor_and_single_request_per_day(hass, aioclient_mock, freezer):
    import json as _json
    freezer.move_to("2026-01-10 10:00:00-03:00")
    mock_all(aioclient_mock)
    payload = _json.loads((Path(__file__).parent / "fixtures" / "efemerides_01-10.json").read_text())
    url = EPHEMERIDES_URL.format(month=1, day=10)
    aioclient_mock.get(url, json=payload)
    entry = MockConfigEntry(domain=DOMAIN, data={"indicators": [], "metro": False, "ephemerides": True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    s = next(x for x in hass.states.async_all("sensor") if x.name.endswith("Efemérides de hoy"))
    assert s.state.startswith("1957: Gabriela Mistral") and len(s.state) <= 255
    assert s.attributes["total"] == 8 and s.attributes["fecha"] == "2026-01-10"
    assert s.attributes["efemerides"][0]["articulo"] == "Gabriela Mistral"
    assert "CC BY-SA" in s.attributes["fuente"]
    coordinator = entry.runtime_data.ephemerides
    before = aioclient_mock.call_count
    await coordinator.async_refresh()                     # mismo día: no vuelve a consultar Wikipedia
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == before


async def test_ephemerides_none_today_is_not_unavailable(hass, aioclient_mock, freezer):
    freezer.move_to("2026-03-03 10:00:00-03:00")
    mock_all(aioclient_mock)
    aioclient_mock.get(EPHEMERIDES_URL.format(month=3, day=3), json={"events": [], "births": [], "deaths": []})
    entry = MockConfigEntry(domain=DOMAIN, data={"indicators": [], "metro": False, "ephemerides": True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    s = next(x for x in hass.states.async_all("sensor") if x.name.endswith("Efemérides de hoy"))
    assert s.state == "Sin efemérides chilenas registradas para hoy" and s.attributes["total"] == 0
