"""Tren Limache–Puerto dentro de Home Assistant (requiere pytest-homeassistant-custom-component)."""

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.navaja_chilena.const import DOMAIN  # noqa: E402
from custom_components.navaja_chilena.efe_train import build_url  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
IDA = build_url(18, 1)      # Villa Alemana → Puerto
VUELTA = build_url(1, 18)   # Puerto → Villa Alemana
SENSOR_IDA = "sensor.tren_limache_puerto_villa_alemana_puerto"
SENSOR_VUELTA = "sensor.tren_limache_puerto_puerto_villa_alemana"
DATA = {"indicators": [], "train_trips": "Villa Alemana > Puerto", "train_return": False}


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


async def setup(hass, data=DATA):
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_train_sensor_with_services(hass, aioclient_mock):
    aioclient_mock.get(IDA, json=fixture("efe_train_with_services.json"))
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(SENSOR_IDA)
    assert state.state == "10 minutos"
    attrs = state.attributes
    assert attrs["origen"] == "Villa Alemana" and attrs["destino"] == "Puerto"
    assert attrs["hasta"] == "Hasta Puerto" and attrs["llega_a_destino"] is True
    assert attrs["minutos"] == 10 and attrs["hora_estimada"]
    assert attrs["servicios_informados"] == 3 and len(attrs["servicios"]) == 3
    assert attrs["estado_consulta"] == "servicios_informados"
    assert attrs["aviso_efe"] == "Servicio no disponible por el momento"
    assert attrs["tiempo_real_confirmado"] is False


async def test_empty_list_is_not_unavailable(hass, aioclient_mock):
    aioclient_mock.get(IDA, json=fixture("efe_train_no_services.json"))
    await setup(hass)
    state = hass.states.get(SENSOR_IDA)
    assert state.state == "Sin servicios informados"
    assert state.attributes["estado_consulta"] == "sin_servicios_informados"
    assert state.attributes["servicios_informados"] == 0


async def test_return_direction_creates_both_sensors(hass, aioclient_mock):
    aioclient_mock.get(IDA, json=fixture("efe_train_with_services.json"))
    aioclient_mock.get(VUELTA, json=fixture("efe_train_no_services.json"))
    await setup(hass, {**DATA, "train_return": True})
    assert hass.states.get(SENSOR_IDA).state == "10 minutos"
    assert hass.states.get(SENSOR_VUELTA).state == "Sin servicios informados"


async def test_one_trip_down_keeps_the_other(hass, aioclient_mock):
    aioclient_mock.get(IDA, json=fixture("efe_train_with_services.json"))
    aioclient_mock.get(VUELTA, status=502)
    await setup(hass, {**DATA, "train_return": True})
    assert hass.states.get(SENSOR_IDA).state == "10 minutos"
    assert hass.states.get(SENSOR_VUELTA).state == "unavailable"


async def test_source_down_retries_setup(hass, aioclient_mock):
    aioclient_mock.get(IDA, status=502)
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_format_change_makes_unavailable_not_empty(hass, aioclient_mock):
    aioclient_mock.get(IDA, json=fixture("efe_train_with_services.json"))
    entry = await setup(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.get(IDA, json={"status": "OK"})  # formato cambiado
    await entry.runtime_data.train.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR_IDA).state == "unavailable"


async def test_config_flow_validates_and_normalizes_trips(hass, aioclient_mock):
    aioclient_mock.get(IDA, json=fixture("efe_train_with_services.json"))
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    base = {"indicators": [], "metro": False, "quakes": False, "holidays": False, "air": False,
            "bolsa": False, "saint": False, "ephemerides": False, "crypto": False, "train_return": False}
    bad = await hass.config_entries.flow.async_configure(
        r["flow_id"], {**base, "train_trips": "Villa Alemana > Marte"}
    )
    assert bad["errors"] == {"train_trips": "invalid_trip"}
    ok = await hass.config_entries.flow.async_configure(
        r["flow_id"], {**base, "train_trips": "villa alemana>puerto"}
    )
    assert ok["type"] is FlowResultType.CREATE_ENTRY
    assert ok["data"]["train_trips"] == "Villa Alemana > Puerto"
