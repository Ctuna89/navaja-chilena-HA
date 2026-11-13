"""Estructura de Cinépolis. Las respuestas de estos tests son SINTÉTICAS: siguen la forma que Cinépolis describió por escrito
(data.billboard.schedules[] → dates[] → languages[] → showtimes[]) y se reemplazan por respuestas reales cuando haya clave."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.navaja_chilena import api, cinepolis as cp

TZ = "America/Santiago"


def _payload(*groups):
    return {"billboard": {"schedules": [{"dates": [{"date": "2026-11-28", "languages": list(groups)}]}]}}


def _group(showtimes, language="SUB", display="Subtitulada"):
    return {"language": language, "displayLanguage": display, "showtimes": showtimes}


def _show(session="s1", when="2026-11-28T19:30:00", fmt="2D", exp=None, screen="Sala 3", availability=None):
    d = {"sessionId": session, "datetime": when, "format": {"name": fmt}, "screen": screen}
    if exp:
        d["experience"] = {"name": exp}
    if availability is not None:
        d["availability"] = availability
    return d


def test_parse_cinema_from_search_entity():
    ok = cp.parse_cinema({"id": "cinepolis-la-reina-santiago-oriente", "name": "La Reina", "timeZone": TZ})
    assert ok == cp.CinepolisCinema("cinepolis-la-reina-santiago-oriente", "La Reina", TZ)
    for bad in (None, {}, {"id": "x", "name": "Y", "timeZone": "Marte/Olimpo"}, {"id": "", "name": "Y", "timeZone": TZ}, "texto"):
        assert cp.parse_cinema(bad) is None


def test_showtime_without_offset_is_local_time_of_the_cinema_not_utc():
    shows = cp.parse_billboard(_payload(_group([_show(when="2026-11-28T19:30:00")])), TZ)
    assert shows[0].start.isoformat() == "2026-11-28T19:30:00-03:00" and shows[0].start.utcoffset() == timedelta(hours=-3)


def test_showtime_with_offset_or_z_is_converted_to_the_cinema_zone():
    shows = cp.parse_billboard(_payload(_group([_show("a", "2026-11-28T22:30:00Z"), _show("b", "2026-11-28T19:30:00-03:00")])), TZ)
    assert [s.start.isoformat() for s in shows] == ["2026-11-28T19:30:00-03:00", "2026-11-28T19:30:00-03:00"]


def test_after_midnight_showtime_keeps_its_full_date():
    shows = cp.parse_billboard(_payload(_group([_show("a", "2026-11-28T23:45:00"), _show("b", "2026-11-29T00:15:00")])), TZ)
    assert [s.start.date().isoformat() for s in shows] == ["2026-11-28", "2026-11-29"]
    now = datetime(2026, 11, 28, 23, 50, tzinfo=timezone(timedelta(hours=-3)))
    assert [s.session_id for s in cp.upcoming(shows, now)] == ["b"]            # la de las 00:15 sigue siendo «la próxima»


def test_language_comes_from_the_group_and_fields_are_read():
    payload = _payload(
        _group([_show("a", exp="Sala Prime", availability={"seats": 20})], "SUB", "Subtitulada"),
        _group([_show("b", "2026-11-28T17:00:00", fmt="3D")], "DOB", "Doblada"),
    )
    by = {s.session_id: s for s in cp.parse_billboard(payload, TZ)}
    assert (by["a"].language, by["a"].language_name, by["a"].format, by["a"].experience, by["a"].screen) == ("SUB", "Subtitulada", "2D", "Sala Prime", "Sala 3")
    assert by["a"].availability == {"seats": 20} and by["b"].language_name == "Doblada" and by["b"].experience is None


def test_showtimes_are_sorted_deduplicated_and_bad_rows_skipped():
    rows = [_show("b", "2026-11-28T21:00:00"), _show("a", "2026-11-28T19:00:00"), _show("a", "2026-11-28T19:00:00"),
            {"sessionId": "", "datetime": "2026-11-28T10:00:00"}, {"sessionId": "x", "datetime": "no es fecha"}, "basura", None]
    shows = cp.parse_billboard(_payload(_group(rows)), TZ)
    assert [s.session_id for s in shows] == ["a", "b"]


def test_movie_without_showtimes_is_valid_but_unknown_format_is_an_error():
    assert cp.parse_billboard({"billboard": {"schedules": []}}, TZ) == []
    assert cp.parse_billboard(_payload(_group([])), TZ) == []
    for bad in (None, {}, {"billboard": None}, {"billboard": {"schedules": "x"}}, [], "texto"):
        with pytest.raises(api.NavajaApiError):
            cp.parse_billboard(bad, TZ)                                          # un cambio de formato no es «sin funciones»


def test_filters_by_language_format_and_experience():
    shows = cp.parse_billboard(_payload(
        _group([_show("a", exp="Prime"), _show("b", "2026-11-28T20:00:00", fmt="3D")], "SUB"),
        _group([_show("c", "2026-11-28T21:00:00")], "DOB"),
    ), TZ)
    ids = lambda xs: [s.session_id for s in xs]  # noqa: E731
    assert ids(cp.filter_showtimes(shows, languages={"sub"})) == ["a", "b"]
    assert ids(cp.filter_showtimes(shows, formats={"3d"})) == ["b"]
    assert ids(cp.filter_showtimes(shows, experiences={"PRIME"})) == ["a"]
    assert ids(cp.filter_showtimes(shows)) == ["a", "b", "c"]


def test_upcoming_limit_and_window():
    shows = cp.parse_billboard(_payload(_group([_show(str(i), f"2026-11-28T{10 + i}:00:00") for i in range(8)])), TZ)
    now = datetime(2026, 11, 28, 12, 30, tzinfo=timezone(timedelta(hours=-3)))
    assert [s.session_id for s in cp.upcoming(shows, now, limit=3)] == ["3", "4", "5"]
    assert [s.session_id for s in cp.upcoming(shows, now, within=timedelta(hours=2))] == ["3", "4"]


def test_headers_carry_the_key_only_in_x_apikey():
    h = cp.cinepolis_headers("CLAVE-DE-PRUEBA")
    assert h["x-apikey"] == "CLAVE-DE-PRUEBA" and h["country-id"] == "CL" and h["language"] == "ES"
    assert h["Content-Type"] == "application/json" and "NavajaChilena" in h["User-Agent"]
    assert "CLAVE-DE-PRUEBA" not in {v for k, v in h.items() if k != "x-apikey"}


async def test_post_graphql_returns_data_and_sends_the_headers(hass, aioclient_mock):
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, json={"data": {"billboard": {"schedules": []}}})
    data = await cp.post_graphql(async_get_clientsession(hass), cp.CINEPOLIS_BILLBOARD_URL, "query { x }", {"countryId": "CL"}, "CLAVE")
    assert data == {"billboard": {"schedules": []}}
    method, url, body, headers = aioclient_mock.mock_calls[0]
    assert body == {"query": "query { x }", "variables": {"countryId": "CL"}} and headers["x-apikey"] == "CLAVE"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": 500},
        {"status": 403},
        {"text": "<html>no json</html>"},
        {"json": ["lista"]},
        {"json": {"data": None}},
        {"json": {"errors": [{"message": "No autorizado"}], "data": None}},
    ],
)
async def test_post_graphql_failures_are_errors_never_empty_data(hass, aioclient_mock, kwargs):
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, **kwargs)
    with pytest.raises(api.NavajaApiError) as err:
        await cp.post_graphql(async_get_clientsession(hass), cp.CINEPOLIS_BILLBOARD_URL, "query { x }", {}, "CLAVE-SECRETA")
    assert "conectar" not in str(err.value)                                       # falló por la respuesta, no por la red
    assert "CLAVE-SECRETA" not in str(err.value)                                  # la clave nunca aparece en los mensajes


async def test_post_graphql_without_a_key_does_not_call_the_service(hass, aioclient_mock):
    with pytest.raises(api.NavajaApiError):
        await cp.post_graphql(async_get_clientsession(hass), cp.CINEPOLIS_BILLBOARD_URL, "query { x }", {}, "")
    assert aioclient_mock.call_count == 0
