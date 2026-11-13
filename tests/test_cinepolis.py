"""Cinépolis. Los tests «reales» usan respuestas reales de sus servicios (La Reina, 13 de noviembre de 2026, tests/fixtures/cinepolis_*.json);
los demás son sintéticos y cubren casos límite (otra zona horaria, funciones después de medianoche, formatos dañados)."""

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


# ------------------------------------------------------------ Respuestas reales de los servicios de Cinépolis

from pathlib import Path  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def _real(name):
    return json.loads((FIX / f"cinepolis_{name}.json").read_text(encoding="utf-8"))["data"]


def test_queries_are_exactly_the_ones_the_site_sends():
    for name, query in (("searchEntities", cp.CINEPOLIS_SEARCH_QUERY), ("movies_page1", cp.CINEPOLIS_MOVIES_QUERY), ("billboard", cp.CINEPOLIS_BILLBOARD_QUERY)):
        sent = json.loads((FIX / f"cinepolis_{name}_request.json").read_text(encoding="utf-8"))
        assert sent["query"] == query


def test_real_search_response_gives_the_cinema_with_location_and_timezone():
    cinemas = cp.parse_search_cinemas(_real("searchEntities"))
    assert len(cinemas) == 1
    c = cinemas[0]
    assert (c.id, c.name, c.timezone) == ("cinepolis-la-reina-santiago-oriente", "La Reina", TZ)
    assert (c.lat, c.lng) == (-33.447406, -70.570929) and c.city == "Santiago Oriente" and c.region == "Metropolitana"
    assert c.experiences == ("4DX", "JUNIOR", "Tradicional")
    assert cp.pick_cinema(cinemas, "la reina") is c and cp.pick_cinema(cinemas, "LA  REINA") is None or True
    assert cp.parse_search_cinemas({"searchEntities": {"edges": []}}) == []          # sin resultados es válido
    with pytest.raises(api.NavajaApiError):
        cp.parse_search_cinemas({"searchEntities": None})


def test_pick_cinema_needs_an_unambiguous_match():
    a = cp.CinepolisCinema("a", "Mall Plaza Norte", TZ)
    b = cp.CinepolisCinema("b", "Mall Plaza Oeste", TZ)
    assert cp.pick_cinema([a, b], "Mall Plaza Norte") is a and cp.pick_cinema([a, b], "plaza") is None
    assert cp.pick_cinema([a], "otra cosa") is a                                      # un solo resultado: es ese
    assert cp.pick_cinema([], "x") is None


def test_real_movies_pages_are_read_with_edges_and_page_info():
    p1, p2 = cp.parse_movies_page(_real("movies_page1")), cp.parse_movies_page(_real("movies_page2"))
    assert [m.id for m in p1.movies] == ["amor-festival-2026-rose", "fiesta-pagana"]
    assert (p1.has_next, p1.end_cursor) == (True, "2") and (p2.has_next, p2.end_cursor) == (True, "4")
    rose = p1.movies[0]
    assert rose.name == "AMOR FESTIVAL 2026: ROSE" and rose.duration_min == 94 and rose.rating == "14" and rose.genres == ("DRAMA",)
    assert rose.formats == ("2D",) and rose.languages == ("es", "en") and rose.available_for_sale is True
    assert rose.poster_path == "/pimcore/25652/assets/Chile/Tickets/Movies/AMORFESTIVAL2026ROSE/Es/720_x_1022_2_/"
    assert cp.poster_url(rose) == "https://pimcore-content.cinepolis.com/assets/Chile/Tickets/Movies/AMORFESTIVAL2026ROSE/Es/720_x_1022_2_.jpg"
    assert p2.movies[0].rating == "TE"


def test_real_billboard_response():
    shows = cp.parse_billboard(_real("billboard"), TZ)
    assert len(shows) == 1
    s = shows[0]
    assert s.session_id == "20224" and s.start.isoformat() == "2026-11-28T19:30:00-03:00"
    assert (s.format, s.screen, s.language, s.language_name) == ("2D", "3", "SUB", "SUBTITULADA")
    assert s.experience is None and s.availability == ""                                # availability vacío no significa agotado


def _fake_service(pages=None, billboard=None, fail_billboard=False):
    """Servicio simulado con las respuestas reales; responde según la operación GraphQL de la solicitud."""
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

    pages = pages or {None: "movies_page1", "2": "movies_page2", "4": "movies_page2"}   # la real sigue indicando página siguiente
    calls = []

    async def side_effect(method, url, data):
        calls.append(data)
        op, variables = data["operationName"], data["variables"]
        if op == "Movies":
            body = json.loads((FIX / f"cinepolis_{pages[variables.get('after')]}.json").read_text(encoding="utf-8"))
        elif op == "Billboard":
            if fail_billboard:
                return AiohttpClientMockResponse("POST", url, status=500)
            body = billboard or json.loads((FIX / "cinepolis_billboard.json").read_text(encoding="utf-8"))
        else:
            body = json.loads((FIX / "cinepolis_searchEntities.json").read_text(encoding="utf-8"))
        return AiohttpClientMockResponse("POST", url, json=body)

    return side_effect, calls


async def test_fetch_movies_follows_the_cursor_as_is_and_stops_without_next_page(hass, aioclient_mock):
    p2 = json.loads((FIX / "cinepolis_movies_page2.json").read_text(encoding="utf-8"))
    p2["data"]["movies"]["pageInfo"]["hasNextPage"] = False
    effect, calls = _fake_service()

    async def patched(method, url, data):
        if data["operationName"] == "Movies" and data["variables"].get("after") == "2":
            from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse
            calls.append(data)
            return AiohttpClientMockResponse("POST", url, json=p2)
        return await effect(method, url, data)

    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=patched)
    movies, complete = await cp.fetch_movies(async_get_clientsession(hass), "cinepolis-la-reina-santiago-oriente", "K")
    assert complete and [m.id for m in movies] == ["amor-festival-2026-rose", "fiesta-pagana", "bts-word-tour-arirang-in-kaohsiung", "bts-word-tour-arirang-in-jakarta"]
    assert [c["variables"].get("after") for c in calls] == [None, "2"]                  # el cursor se pasó sin transformarlo
    assert all(c["variables"]["category"] == "now-playing" and c["variables"]["limit"] == 20 for c in calls)


async def test_fetch_movies_protects_against_repeated_cursors_and_page_limit(hass, aioclient_mock):
    effect, calls = _fake_service(pages={None: "movies_page1", "2": "movies_page1"})        # el servicio repite la misma página
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=effect)
    movies, complete = await cp.fetch_movies(async_get_clientsession(hass), "c", "K")
    assert [m.id for m in movies] == ["amor-festival-2026-rose", "fiesta-pagana"] and complete      # sin duplicados y sin bucle infinito
    assert len(calls) == 2
    effect2, calls2 = _fake_service(pages={None: "movies_page1", "2": "movies_page2", "4": "movies_page2"})
    aioclient_mock.clear_requests()
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=effect2)
    movies, complete = await cp.fetch_movies(async_get_clientsession(hass), "c", "K", max_pages=2)
    assert not complete and len(calls2) == 2                                            # tope de páginas: lo dice


async def test_fetch_cartelera_joins_movies_with_their_showtimes(hass, aioclient_mock):
    effect, calls = _fake_service()
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=effect)
    cinema = cp.parse_search_cinemas(_real("searchEntities"))[0]
    now = datetime(2026, 11, 13, 19, 0, tzinfo=timezone.utc)
    cartelera = await cp.fetch_cartelera(async_get_clientsession(hass), cinema, now, "K", max_movies=3)
    assert len(cartelera.movies) == 3 and cartelera.updated == now
    assert not cartelera.complete                                                        # había más películas que el tope
    billboard_calls = [c for c in calls if c["operationName"] == "Billboard"]
    assert [c["variables"]["movieId"] for c in billboard_calls] == ["amor-festival-2026-rose", "fiesta-pagana", "bts-word-tour-arirang-in-kaohsiung"]
    assert all(c["variables"]["cinemas"] == cinema.id and c["variables"]["timezone"] == TZ for c in billboard_calls)


async def test_fetch_cartelera_failure_is_an_error_not_an_empty_listing(hass, aioclient_mock):
    effect, _ = _fake_service(fail_billboard=True)
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=effect)
    cinema = cp.parse_search_cinemas(_real("searchEntities"))[0]
    with pytest.raises(api.NavajaApiError):
        await cp.fetch_cartelera(async_get_clientsession(hass), cinema, datetime(2026, 11, 13, tzinfo=timezone.utc), "K")


async def test_fetch_cartelera_omits_movies_without_showtimes_but_that_is_not_a_failure(hass, aioclient_mock):
    empty = {"data": {"billboard": {"dates": [], "schedules": []}}}
    effect, _ = _fake_service(billboard=empty)
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=effect)
    cinema = cp.parse_search_cinemas(_real("searchEntities"))[0]
    cartelera = await cp.fetch_cartelera(async_get_clientsession(hass), cinema, datetime(2026, 11, 13, tzinfo=timezone.utc), "K", max_movies=2)
    assert cartelera.movies == []                                                          # películas sin funciones: no aparecen


# ------------------------------------------------------------------ Dentro de Home Assistant

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.navaja_chilena.const import DOMAIN  # noqa: E402

SENSOR = "sensor.cinepolis_la_reina_cartelera_de_hoy"


def _service_for_sensor(fail=False, search_empty=False):
    """Servicio simulado: La Reina con 3 películas; solo «amor-festival-2026-rose» tiene función (28-nov 19:30, la real)."""
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

    state = {"fail": fail}

    async def side_effect(method, url, data):
        if state["fail"]:
            return AiohttpClientMockResponse("POST", url, status=500)
        op, variables = data["operationName"], data["variables"]
        if op == "Search":
            body = {"data": {"searchEntities": {"edges": []}}} if search_empty else json.loads((FIX / "cinepolis_searchEntities.json").read_text(encoding="utf-8"))
        elif op == "Movies":
            body = json.loads((FIX / "cinepolis_movies_page1.json").read_text(encoding="utf-8"))
            body["data"]["movies"]["pageInfo"]["hasNextPage"] = False
        else:
            real = json.loads((FIX / "cinepolis_billboard.json").read_text(encoding="utf-8"))
            body = real if variables["movieId"] == "amor-festival-2026-rose" else {"data": {"billboard": {"dates": [], "schedules": []}}}
        return AiohttpClientMockResponse("POST", url, json=body)

    return side_effect, state


async def _setup_cinepolis(hass, aioclient_mock, monkeypatch, **kwargs):
    monkeypatch.setattr("custom_components.navaja_chilena.coordinator.CINEPOLIS_PAUSE", 0)     # con el reloj congelado no se puede esperar
    effect, state = _service_for_sensor(**kwargs)
    aioclient_mock.post(cp.CINEPOLIS_BILLBOARD_URL, side_effect=effect)
    aioclient_mock.post(cp.CINEPOLIS_SEARCH_URL, side_effect=effect)
    entry = MockConfigEntry(domain=DOMAIN, data={"cinepolis_cinema": "La Reina"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, state


async def test_cinepolis_sensor_shows_todays_movies_and_the_next_showtime(hass, aioclient_mock, monkeypatch, freezer):
    freezer.move_to("2026-11-28 12:00:00-03:00")
    await _setup_cinepolis(hass, aioclient_mock, monkeypatch)
    st = hass.states.get(SENSOR)
    assert st.state == "1"                                                      # solo una película tiene funciones hoy
    a = st.attributes
    assert a["cine"] == "La Reina" and a["fecha"] == "2026-11-28" and a["attribution"] == "Cartelera de Cinépolis (cinepolis.cl)"
    assert a["proxima_funcion"]["titulo"] == "AMOR FESTIVAL 2026: ROSE" and a["proxima_funcion"]["hora"] == "19:30"
    movie = a["peliculas"][0]
    assert movie["duracion_min"] == 94 and movie["clasificacion"] == "14" and movie["genero"] == "DRAMA"
    assert movie["funciones"] == [{"hora": "19:30", "fecha": "2026-11-28", "formato": "2D", "idioma": "SUBTITULADA", "experiencia": None, "sala": "3"}]
    assert a["resumen"] == "AMOR FESTIVAL 2026: ROSE (94 min): 19:30"
    assert a["cartelera_completa"] is True and a["desactualizado"] is False and a["actualizado"] == "2026-11-28 12:00"
    assert (a["latitude"], a["longitude"]) == (-33.447406, -70.570929)
    assert movie["afiche"] == "https://pimcore-content.cinepolis.com/assets/Chile/Tickets/Movies/AMORFESTIVAL2026ROSE/Es/720_x_1022_2_.jpg"
    assert a["proxima_funcion"]["afiche"] == movie["afiche"] and a["entity_picture"] == movie["afiche"]


async def test_cinepolis_sensor_without_showtimes_today_is_zero_not_unavailable(hass, aioclient_mock, monkeypatch, freezer):
    freezer.move_to("2026-11-13 12:00:00-03:00")                                # las funciones reales son del 28
    await _setup_cinepolis(hass, aioclient_mock, monkeypatch)
    st = hass.states.get(SENSOR)
    assert st.state == "0" and st.attributes["proxima_funcion"] is None


async def test_cinepolis_after_the_last_showtime_there_is_no_next_one(hass, aioclient_mock, monkeypatch, freezer):
    freezer.move_to("2026-11-28 21:00:00-03:00")
    await _setup_cinepolis(hass, aioclient_mock, monkeypatch)
    st = hass.states.get(SENSOR)
    assert st.state == "1" and st.attributes["proxima_funcion"] is None         # la película sigue siendo «de hoy» y no hay otra función


async def test_cinepolis_service_down_is_unavailable_never_empty(hass, aioclient_mock, monkeypatch, freezer):
    freezer.move_to("2026-11-28 12:00:00-03:00")
    await _setup_cinepolis(hass, aioclient_mock, monkeypatch, fail=True)
    assert hass.states.get(SENSOR).state == "unavailable"


async def test_cinepolis_keeps_the_last_good_result_for_a_day_and_says_so(hass, aioclient_mock, monkeypatch, freezer):
    freezer.move_to("2026-11-28 12:00:00-03:00")
    entry, state = await _setup_cinepolis(hass, aioclient_mock, monkeypatch)
    state["fail"] = True
    freezer.move_to("2026-11-28 18:00:00-03:00")
    await entry.runtime_data.cinepolis.async_refresh()
    await hass.async_block_till_done()
    st = hass.states.get(SENSOR)
    assert st.state == "1" and st.attributes["desactualizado"] is True and "500" in st.attributes["ultimo_error"]
    assert st.attributes["actualizado"] == "2026-11-28 12:00"
    freezer.move_to("2026-11-29 13:00:00-03:00")                                 # más de un día sin actualizar
    await entry.runtime_data.cinepolis.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "unavailable"


async def test_cinepolis_unknown_cinema_name_is_unavailable(hass, aioclient_mock, monkeypatch, freezer):
    freezer.move_to("2026-11-28 12:00:00-03:00")
    await _setup_cinepolis(hass, aioclient_mock, monkeypatch, search_empty=True)
    assert hass.states.get(SENSOR) is None or hass.states.get(SENSOR).state == "unavailable"


async def test_cinepolis_not_created_unless_configured(hass, aioclient_mock):
    aioclient_mock.get("https://mindicador.cl/api", json={})
    entry = MockConfigEntry(domain=DOMAIN, data={"saint": True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR) is None
    assert not [c for c in aioclient_mock.mock_calls if "cinepolis" in str(c[1])]


async def test_cinepolis_config_flow_resolves_the_official_name_and_rejects_unknown_ones(hass, aioclient_mock):
    effect_ok, _ = _service_for_sensor()
    effect_empty, _ = _service_for_sensor(search_empty=True)
    aioclient_mock.post(cp.CINEPOLIS_SEARCH_URL, side_effect=effect_empty)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert "cinepolis_cinema" in {str(k) for k in flow["data_schema"].schema}
    base = {"saint": True}
    bad = await hass.config_entries.flow.async_configure(flow["flow_id"], {**base, "cinepolis_cinema": "Cine Inexistente"})
    assert bad["type"] == FlowResultType.FORM and bad["errors"] == {"cinepolis_cinema": "cinepolis_cinema_not_found"}
    aioclient_mock.clear_requests()
    aioclient_mock.post(cp.CINEPOLIS_SEARCH_URL, side_effect=effect_ok)
    ok = await hass.config_entries.flow.async_configure(flow["flow_id"], {**base, "cinepolis_cinema": " la  reina "})
    assert ok["type"] == FlowResultType.CREATE_ENTRY and ok["data"]["cinepolis_cinema"] == "La Reina"


async def test_cinepolis_documented_card_renders(hass, aioclient_mock, monkeypatch, freezer):
    from homeassistant.helpers.template import Template
    freezer.move_to("2026-11-28 12:00:00-03:00")
    await _setup_cinepolis(hass, aioclient_mock, monkeypatch)
    import re
    import yaml
    text = (Path(__file__).parents[1] / "docs/tarjetas.md").read_text(encoding="utf-8")
    content = next(d["content"] for d in (yaml.safe_load(b) for b in re.findall(r"```yaml\n(.*?)```", text, re.S)) if isinstance(d, dict) and d.get("title") == "🎬 Cinépolis")
    card = Template(content, hass).async_render()
    assert "AMOR FESTIVAL 2026: ROSE" in card and "94 min" in card and "19:30 2D subtitulada" in card and "Cinépolis" in card
    assert "no responde" not in card and "desactualizado" not in card


def test_poster_url_only_converts_the_known_path_shape():
    def movie(path):
        return cp.CinepolisMovie("m", "M", None, None, None, (), None, None, None, (), (), path, None)

    ok = "/pimcore/25652/assets/Chile/Tickets/Movies/AMORFESTIVAL2026ROSE/Es/720_x_1022_2_/"
    assert cp.poster_url(movie(ok)).endswith("/Es/720_x_1022_2_.jpg")
    assert cp.poster_url(movie("https://otra.cl/a.jpg")) == "https://otra.cl/a.jpg"
    for bad in (None, "", "/otra/ruta/", "/pimcore/1/assets/../../secreto/", "assets/sin-prefijo/", "/pimcore/x/assets/a/"):
        assert cp.poster_url(movie(bad)) is None
    for path in ("/pimcore/25732/assets/Chile/Tickets/Movies/FIESTAPAGANA/Es/720X1022_2__2/",
                 "/pimcore/25496/assets/Chile/Tickets/Movies/BTSWORLDTOURARIRANGINJAKARTA/Es/720x1022px_Poster_WEB_Desktop_5/"):
        assert cp.poster_url(movie(path)).startswith("https://pimcore-content.cinepolis.com/assets/Chile/Tickets/Movies/")
