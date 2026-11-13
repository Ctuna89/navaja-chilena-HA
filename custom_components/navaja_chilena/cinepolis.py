"""Cartelera de Cinépolis (Chile): consultas GraphQL y lectura de películas y funciones.

Cinépolis autorizó por escrito usar los mismos servicios que su sitio web, con la clave de aplicación del sitio (const.py). Los textos
de las consultas son los del propio sitio, y los tests usan respuestas reales de esos servicios (La Reina, 13 de noviembre de 2026).

Servicios: POST api-g.cinepolis.com/v2/billboards/graphql (movies y billboard) y /shared-services/search/entities/graphql (Search).
Reglas que Cinépolis pidió y aquí se cumplen:
- se respeta la zona horaria del cine: un «datetime» sin desfase NO es UTC (las funciones vienen en hora local del cine);
- se conserva la fecha completa de cada función (funciones pasada la medianoche);
- ante una falla se conserva el último resultado, con su hora, y nunca se presenta como «sin funciones»;
- una consulta cada 30 a 60 minutos, con caché.

No es una API pública versionada: la extracción vive aquí, separada de las entidades, para ajustarla si el sitio cambia.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .api import HEADERS, NavajaApiError, _plain
from .const import CINEPOLIS_API_KEY, REQUEST_TIMEOUT  # noqa: F401 - la clave se usará al conectar el módulo

CINEPOLIS_BILLBOARD_URL = "https://api-g.cinepolis.com/v2/billboards/graphql"
CINEPOLIS_SEARCH_URL = "https://api-g.cinepolis.com/shared-services/search/entities/graphql"
CINEPOLIS_COUNTRY = "CL"
CINEPOLIS_MAX_BYTES = 4_000_000
CINEPOLIS_ATTRIBUTION = "Cartelera de Cinépolis (cinepolis.cl)"

# Textos de las consultas, tal como los usa el sitio de Cinépolis
CINEPOLIS_SEARCH_QUERY = """
  query Search($countryId: String!, $search: String!) {
    searchEntities(countryId: $countryId, search: $search) {
      edges {
        node {
          cinemas {
            id
            lat
            lng
            name
            type
            cityId
            vistaId
            timeZone
            cityName
            cityRegion
            businessType
            experiences {
              name
            }
            countryId
          }
          movies {
            id
            name
            countryId
            media {
              platform
              resources {
                type
                code
                resource
                sizes {
                  large
                  small
                  medium
                }
              }
            }
          }
        }
      }
    }
  }
"""
CINEPOLIS_MOVIES_QUERY = """
  query Movies(
    $countryId: String!
    $category: String
    $cinemas: String
    $after: String
    $limit: Int
  ) {
    movies(
      countryId: $countryId
      category: $category
      cinemas: $cinemas
      after: $after
      limit: $limit
    ) {
      pageInfo {
        startCursor
        endCursor
        hasNextPage
        hasPreviousPage
      }
      totalCount
      edges {
        cursor
        node {
          id
          type
          countryId
          name
          originalName
          distributor
          rating
          ratingDescription
          position
          genre
          synopsis
          length
          releaseDate
          languages
          formats
          tags {
            name
            resource
          }
          media {
            resource
            type
            code
            sizes {
              large
              medium
              small
            }
          }
          cities
          cinemas
          categories
          experiences {
            icon
            name
          }
          availableForSale
          alerts {
            title
            message
          }
        }
      }
    }
  }
"""
CINEPOLIS_BILLBOARD_QUERY = """
  query Billboard(
    $countryId: String!
    $movieId: String!
    $cinemas: String!
    $timezone: String
  ) {
    billboard(
      countryId: $countryId
      movieId: $movieId
      cinemas: $cinemas
      timezone: $timezone
    ) {
      dates
      schedules {
        cinemaId
        cityId
        movieId
        dates {
          date
          languages {
            language
            displayLanguage
            showtimes {
              format {
                icon
                name
              }
              sessionId
              datetime
              screen
              experience {
                icon
                name
              }
              movieVistaId
              cinemaVistaId
              alerts {
                section
                title
                message
              }
              availability
              isAllocatedSeating
            }
          }
        }
      }
    }
  }
"""
CINEPOLIS_CATEGORY = "now-playing"


@dataclass(frozen=True)
class CinepolisCinema:
    id: str           # p. ej. "cinepolis-la-reina-santiago-oriente"
    name: str
    timezone: str     # p. ej. "America/Santiago"
    lat: float | None = None
    lng: float | None = None
    city: str | None = None
    region: str | None = None
    experiences: tuple[str, ...] = ()


@dataclass(frozen=True)
class CinepolisShowtime:
    session_id: str
    start: datetime          # con zona horaria del cine y fecha completa
    format: str | None       # p. ej. "2D"
    experience: str | None   # experiencia de sala, cuando corresponda
    screen: str | None
    language: str | None     # p. ej. "SUB" / "DOB" tal como lo entrega el servicio
    language_name: str | None
    availability: Any = None


def cinepolis_headers(api_key: str) -> dict[str, str]:
    """Encabezados que usa el sitio. La clave solo viaja en `x-apikey`; nunca se escribe en mensajes ni en el registro."""
    return HEADERS | {"Content-Type": "application/json", "country-id": CINEPOLIS_COUNTRY, "language": "ES", "x-apikey": api_key}


async def post_graphql(
    session: aiohttp.ClientSession, url: str, query: str, variables: dict[str, Any], api_key: str, operation: str | None = None
) -> dict[str, Any]:
    """Una consulta GraphQL. Devuelve `data`; un error HTTP, de red o de GraphQL es un NavajaApiError (nunca «sin resultados»)."""
    if not api_key:
        raise NavajaApiError("Falta la clave de aplicación de Cinépolis")
    try:
        async with session.post(
            url,
            json=({"operationName": operation} if operation else {}) | {"variables": variables, "query": query},
            headers=cinepolis_headers(api_key),
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            if resp.status in (401, 403):
                raise NavajaApiError(f"Cinépolis rechazó la solicitud (HTTP {resp.status}): revisa la clave de aplicación", resp.status)
            resp.raise_for_status()
            body = await resp.content.read(CINEPOLIS_MAX_BYTES + 1)
    except aiohttp.ClientResponseError as err:
        raise NavajaApiError(f"Cinépolis respondió HTTP {err.status}", err.status) from err
    except aiohttp.ClientError as err:
        raise NavajaApiError(f"No fue posible conectar con Cinépolis: {type(err).__name__}") from err
    except TimeoutError as err:
        raise NavajaApiError("Cinépolis no respondió a tiempo") from err
    if len(body) > CINEPOLIS_MAX_BYTES:
        raise NavajaApiError("La respuesta de Cinépolis excede el tamaño admitido")
    try:
        payload = json.loads(body)
    except ValueError as err:
        raise NavajaApiError("Cinépolis no devolvió JSON") from err
    if not isinstance(payload, dict):
        raise NavajaApiError("Respuesta inesperada de Cinépolis")
    errors = payload.get("errors")
    if errors:
        first = errors[0].get("message") if isinstance(errors, list) and errors and isinstance(errors[0], dict) else None
        raise NavajaApiError(f"Cinépolis devolvió un error de consulta: {_plain(str(first or 'sin detalle'))[:200]}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise NavajaApiError("La respuesta de Cinépolis no trae datos")
    return data


def _float(value: Any) -> float | None:
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def parse_cinema(entity: Any) -> CinepolisCinema | None:
    """Un cine de `searchEntities`: {id, name, timeZone, lat, lng, cityName, cityRegion, experiences[{name}]}."""
    if not isinstance(entity, dict):
        return None
    cid, name, tz = str(entity.get("id") or "").strip(), _plain(str(entity.get("name") or "")), str(entity.get("timeZone") or "").strip()
    if not cid or not name:
        return None
    try:
        ZoneInfo(tz)
    except Exception:  # noqa: BLE001 - sin zona horaria válida no se interpretan las horas
        return None
    lat, lng = _float(entity.get("lat")), _float(entity.get("lng"))
    if lat is None or lng is None or not (-57 <= lat <= -17 and -77 <= lng <= -65):
        lat = lng = None
    experiences = tuple(x for x in (_name(e) for e in (entity.get("experiences") or []) if isinstance(e, (dict, str))) if x)
    return CinepolisCinema(cid, name, tz, lat, lng, _name(entity.get("cityName")), _name(entity.get("cityRegion")), experiences)


def parse_search_cinemas(data: Any) -> list[CinepolisCinema]:
    """Cines de data.searchEntities.edges[].node.cinemas[] (sin repetir). Sin resultados es una lista vacía; otro formato, un error."""
    block = data.get("searchEntities") if isinstance(data, dict) else None
    edges = block.get("edges") if isinstance(block, dict) else None
    if not isinstance(edges, list):
        raise NavajaApiError("Formato inesperado en la búsqueda de Cinépolis")
    found: dict[str, CinepolisCinema] = {}
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        for raw in (node.get("cinemas") if isinstance(node, dict) else None) or []:
            cinema = parse_cinema(raw)
            if cinema is not None:
                found.setdefault(cinema.id, cinema)
    return list(found.values())


def _when(value: Any, tz: ZoneInfo) -> datetime | None:
    """Fecha y hora de una función en la zona del cine. Sin desfase explícito se asume la hora local del cine, no UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.replace(tzinfo=tz) if moment.tzinfo is None else moment.astimezone(tz)


def _name(value: Any) -> str | None:
    """Campos que pueden venir como texto o como objeto con nombre: {name: ...}."""
    if isinstance(value, dict):
        value = value.get("name")
    text = _plain(str(value)) if value not in (None, "") else ""
    return text or None


def parse_billboard(payload: Any, timezone: str) -> list[CinepolisShowtime]:
    """Funciones de `data.billboard`: schedules[] → dates[] → languages[] → showtimes[]. Un formato desconocido es un error.

    Una película sin funciones devuelve una lista vacía (válida); lo que no se reconoce no se interpreta como «sin funciones».
    """
    tz = ZoneInfo(timezone)
    billboard = payload.get("billboard") if isinstance(payload, dict) else None
    schedules = billboard.get("schedules") if isinstance(billboard, dict) else None
    if not isinstance(schedules, list):
        raise NavajaApiError("Formato inesperado en la cartelera de Cinépolis")
    found: dict[str, CinepolisShowtime] = {}
    for schedule in schedules:
        for date in (schedule.get("dates") if isinstance(schedule, dict) else None) or []:
            for group in (date.get("languages") if isinstance(date, dict) else None) or []:
                if not isinstance(group, dict):
                    continue
                language, language_name = _name(group.get("language")), _name(group.get("displayLanguage"))
                for raw in group.get("showtimes") or []:
                    if not isinstance(raw, dict):
                        continue
                    session = str(raw.get("sessionId") or "").strip()
                    start = _when(raw.get("datetime"), tz)
                    if not session or start is None:
                        continue
                    found[session] = CinepolisShowtime(
                        session_id=session,
                        start=start,
                        format=_name(raw.get("format")),
                        experience=_name(raw.get("experience")),
                        screen=_name(raw.get("screen")),
                        language=language,
                        language_name=language_name,
                        availability=raw.get("availability"),
                    )
    return sorted(found.values(), key=lambda s: (s.start, s.session_id))


def filter_showtimes(
    showtimes: list[CinepolisShowtime],
    *,
    languages: set[str] | None = None,
    formats: set[str] | None = None,
    experiences: set[str] | None = None,
) -> list[CinepolisShowtime]:
    """Filtros opcionales de idioma, formato y experiencia de sala (sin mayúsculas ni tildes que importen)."""

    def ok(value: str | None, wanted: set[str] | None) -> bool:
        return not wanted or (value or "").casefold() in {w.casefold() for w in wanted}

    return [
        s for s in showtimes
        if ok(s.language, languages) and ok(s.format, formats) and ok(s.experience, experiences)
    ]


def upcoming(showtimes: list[CinepolisShowtime], now: datetime, *, limit: int = 6, within: timedelta | None = None) -> list[CinepolisShowtime]:
    """Funciones que aún no empiezan, de la más próxima en adelante; compara instantes, así que sirve pasada la medianoche."""
    horizon = now + within if within else None
    return [s for s in sorted(showtimes, key=lambda s: s.start) if s.start >= now and (horizon is None or s.start <= horizon)][:limit]


# ---------------------------------------------------------------- Películas y cartelera completa

@dataclass(frozen=True)
class CinepolisMovie:
    id: str
    name: str
    original_name: str | None
    rating: str | None             # clasificación: «14», «18», «TE»…
    rating_description: str | None
    genres: tuple[str, ...]
    synopsis: str | None
    duration_min: int | None
    release_date: str | None
    languages: tuple[str, ...]
    formats: tuple[str, ...]
    poster_path: str | None        # ruta del afiche según Cinépolis (relativa); ver poster_url
    available_for_sale: bool | None


@dataclass(frozen=True)
class CinepolisPage:
    movies: list[CinepolisMovie]
    has_next: bool
    end_cursor: str | None


@dataclass(frozen=True)
class CinepolisCartelera:
    cinema: CinepolisCinema
    movies: list[tuple[CinepolisMovie, list[CinepolisShowtime]]]
    updated: datetime
    complete: bool               # False si el cine tiene más películas que las consultadas (tope de páginas o de películas)
    error: str | None = None     # si la última actualización falló y se muestra el resultado anterior


def _duration(text: Any) -> int | None:
    m = re.search(r"\d+", str(text or ""))
    return int(m.group(0)) if m else None


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(_plain(str(v)) for v in value if isinstance(v, str) and v.strip()) if isinstance(value, list) else ()


def _poster_path(media: Any) -> str | None:
    """Ruta del afiche (código «poster»); la imagen vertical grande si existe."""
    for item in media if isinstance(media, list) else []:
        if isinstance(item, dict) and item.get("code") == "poster" and isinstance(item.get("sizes"), dict):
            path = str(item["sizes"].get("large") or item["sizes"].get("medium") or "").strip()
            return path or None
    return None


def parse_movie(node: Any) -> CinepolisMovie | None:
    if not isinstance(node, dict):
        return None
    mid, name = str(node.get("id") or "").strip(), _plain(str(node.get("name") or ""))
    if not mid or not name:
        return None
    for_sale = node.get("availableForSale")
    return CinepolisMovie(
        id=mid,
        name=name,
        original_name=_name(node.get("originalName")),
        rating=_name(node.get("rating")),
        rating_description=_name(node.get("ratingDescription")),
        genres=_strings(node.get("genre")),
        synopsis=_name(node.get("synopsis")),
        duration_min=_duration(node.get("length")),
        release_date=_name(node.get("releaseDate")),
        languages=_strings(node.get("languages")),
        formats=_strings(node.get("formats")),
        poster_path=_poster_path(node.get("media")),
        available_for_sale=for_sale if isinstance(for_sale, bool) else None,
    )


def parse_movies_page(data: Any) -> CinepolisPage:
    """Una página de data.movies: edges[].node y pageInfo. Se avanza con hasNextPage/endCursor; `totalCount` no es confiable."""
    block = data.get("movies") if isinstance(data, dict) else None
    edges = block.get("edges") if isinstance(block, dict) else None
    if not isinstance(edges, list):
        raise NavajaApiError("Formato inesperado en la lista de películas de Cinépolis")
    info = block.get("pageInfo") if isinstance(block.get("pageInfo"), dict) else {}
    movies = [m for m in (parse_movie(e.get("node")) for e in edges if isinstance(e, dict)) if m is not None]
    cursor = info.get("endCursor")
    return CinepolisPage(movies, info.get("hasNextPage") is True, str(cursor) if cursor not in (None, "") else None)


def poster_url(movie: CinepolisMovie) -> str | None:
    """URL del afiche. Cinépolis entrega rutas relativas y no hay una base de imágenes confirmada: sin ella no se inventa una URL."""
    path = movie.poster_path
    if path and path.startswith("https://"):
        return path
    return None


async def search_cinemas(session: aiohttp.ClientSession, text: str, api_key: str = CINEPOLIS_API_KEY) -> list[CinepolisCinema]:
    data = await post_graphql(
        session, CINEPOLIS_SEARCH_URL, CINEPOLIS_SEARCH_QUERY, {"countryId": CINEPOLIS_COUNTRY, "search": text.strip()}, api_key, "Search"
    )
    return parse_search_cinemas(data)


def pick_cinema(cinemas: list[CinepolisCinema], text: str) -> CinepolisCinema | None:
    """El cine que el usuario escribió: coincidencia exacta de nombre (sin mayúsculas ni tildes) o el único resultado."""
    import unicodedata

    def norm(value: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(c)).strip()

    wanted = norm(text)
    exact = [c for c in cinemas if norm(c.name) == wanted or norm(c.id) == wanted]
    if len(exact) == 1:
        return exact[0]
    return cinemas[0] if len(cinemas) == 1 and not exact else None


async def fetch_movies(
    session: aiohttp.ClientSession, cinema_id: str, api_key: str = CINEPOLIS_API_KEY, *, limit: int = 20, max_pages: int = 5, pause: float = 0.0
) -> tuple[list[CinepolisMovie], bool]:
    """Películas en cartelera del cine. Devuelve (películas, completo): False si se cortó por el máximo de páginas."""
    import asyncio

    movies: dict[str, CinepolisMovie] = {}
    after: str | None = None
    seen_cursors: set[str] = set()
    for number in range(max_pages):
        if number and pause:
            await asyncio.sleep(pause)
        variables: dict[str, Any] = {"countryId": CINEPOLIS_COUNTRY, "cinemas": cinema_id, "category": CINEPOLIS_CATEGORY, "limit": limit}
        if after is not None:
            variables["after"] = after
        page = parse_movies_page(await post_graphql(session, CINEPOLIS_BILLBOARD_URL, CINEPOLIS_MOVIES_QUERY, variables, api_key, "Movies"))
        before = len(movies)
        for movie in page.movies:
            movies.setdefault(movie.id, movie)
        if not page.has_next:
            return list(movies.values()), True
        if not page.movies or len(movies) == before or page.end_cursor is None or page.end_cursor in seen_cursors:
            return list(movies.values()), True          # página vacía o cursor repetido: no se insiste
        seen_cursors.add(page.end_cursor)
        after = page.end_cursor                           # el cursor se pasa tal cual (es opaco)
    return list(movies.values()), False


async def fetch_showtimes(
    session: aiohttp.ClientSession, cinema: CinepolisCinema, movie_id: str, api_key: str = CINEPOLIS_API_KEY
) -> list[CinepolisShowtime]:
    data = await post_graphql(
        session,
        CINEPOLIS_BILLBOARD_URL,
        CINEPOLIS_BILLBOARD_QUERY,
        {"countryId": CINEPOLIS_COUNTRY, "movieId": movie_id, "cinemas": cinema.id, "timezone": cinema.timezone},
        api_key,
        "Billboard",
    )
    return parse_billboard(data, cinema.timezone)


async def fetch_cartelera(
    session: aiohttp.ClientSession,
    cinema: CinepolisCinema,
    now: datetime,
    api_key: str = CINEPOLIS_API_KEY,
    *,
    max_movies: int = 25,
    pause: float = 0.0,
) -> CinepolisCartelera:
    """Películas del cine con sus funciones. `billboard` es por película: una consulta cada una, con tope y pausa entre ellas.

    Una película cuyas funciones no se pudieron leer se omite (no se muestra como «sin funciones»); si fallan todas, es un error.
    """
    import asyncio

    movies, complete = await fetch_movies(session, cinema.id, api_key, pause=pause)
    listed = movies[:max_movies]
    result: list[tuple[CinepolisMovie, list[CinepolisShowtime]]] = []
    failures: list[NavajaApiError] = []
    for index, movie in enumerate(listed):
        if index and pause:
            await asyncio.sleep(pause)
        try:
            showtimes = await fetch_showtimes(session, cinema, movie.id, api_key)
        except NavajaApiError as err:
            failures.append(err)
            if err.status in (401, 403):
                raise                                      # clave rechazada o bloqueo: no tiene sentido seguir
            continue
        if showtimes:
            result.append((movie, showtimes))
    if listed and not result and failures:
        raise failures[0]
    return CinepolisCartelera(cinema, result, now, complete and len(movies) <= max_movies)
