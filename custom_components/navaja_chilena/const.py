"""Constantes de Navaja Chilena."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "navaja_chilena"

# Opciones de configuración
CONF_INDICATORS = "indicators"
CONF_METRO = "metro"
CONF_STOPS = "stops"

# APIs públicas (sin clave)
INDICATORS_URL = "https://mindicador.cl/api"
INDICATORS_FALLBACK_URL = "https://findic.cl/api/"  # mismo formato; trae más indicadores
METRO_URL = "https://api.xor.cl/red/metro-network"
STOP_URL = "https://api.xor.cl/red/bus-stop/{code}"

REQUEST_TIMEOUT = 15

# Frecuencias de actualización
INDICATORS_INTERVAL = timedelta(hours=1)
METRO_INTERVAL = timedelta(minutes=2)
STOPS_INTERVAL = timedelta(minutes=1)

# Indicadores disponibles: código en mindicador.cl -> nombre en español
INDICATORS: dict[str, str] = {
    "uf": "UF",
    "dolar": "Dólar observado",
    "euro": "Euro",
    "utm": "UTM",
    "ipc": "IPC",
    "ivp": "IVP",
    "imacec": "Imacec",
    "tpm": "Tasa de política monetaria",
    "libra_cobre": "Libra de cobre",
    "tasa_desempleo": "Tasa de desempleo",
    "bitcoin": "Bitcoin (USD)",
    "yen": "Yen",
    "dolar_intercambio": "Dólar acuerdo",
    "ethereum": "Ethereum (USD)",
}
DEFAULT_INDICATORS = ["uf", "dolar", "euro", "utm"]

# Unidad de medida de mindicador.cl -> unidad en Home Assistant
UNIT_MAP: dict[str, str] = {
    "Pesos": "CLP",
    "Dólar": "USD",
    "Porcentaje": "%",
}

# ---- Módulos adicionales
CONF_QUAKES = "quakes"
CONF_HOLIDAYS = "holidays"
CONF_AIR = "air"
CONF_PHARMACY_COMUNA = "pharmacy_comuna"

# USGS (FDSN): caja que cubre Chile continental; se filtra por "Chile" en el lugar.
QUAKES_CSN_URL = "https://api.gael.cloud/general/public/sismos"  # CSN; sin coordenadas
QUAKES_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&orderby=time"
    "&limit=100&minmagnitude=2.5&minlatitude=-56&maxlatitude=-17"
    "&minlongitude=-76&maxlongitude=-66"
)
HOLIDAYS_URLS = ("https://api.boostr.cl/holidays/{year}.json",)
AIR_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    "?latitude={lat}&longitude={lon}&current=pm10,pm2_5,us_aqi,uv_index"
)
PHARMACY_URL = "https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php"

QUAKES_INTERVAL = timedelta(minutes=5)
HOLIDAYS_INTERVAL = timedelta(hours=1)
HOLIDAYS_REFETCH = timedelta(hours=12)
AIR_INTERVAL = timedelta(minutes=30)
PHARMACY_INTERVAL = timedelta(hours=6)

# Criptomonedas en pesos (Buda.com)
CONF_CRYPTO = "crypto"
CRYPTO_URL = "https://www.buda.com/api/v2/markets/{market}/ticker"
CRYPTO_MARKETS = {"btc-clp": "Bitcoin", "eth-clp": "Ethereum"}
CRYPTO_INTERVAL = timedelta(minutes=5)

# Bolsa de Santiago (IPSA) y santoral
CONF_BOLSA = "bolsa"
CONF_SAINT = "saint"
IPSA_URL = "https://findic.cl/api/ipsa"
BOLSA_INTERVAL = timedelta(minutes=30)

# Cines Cinemark (slug -> nombre, dirección, latitud, longitud); de https://www.cinemark.cl/cines
CINEMARK_THEATERS: dict[str, tuple[str, str, float, float]] = {
    "cinemark-alto-las-condes": ("Cinemark Alto Las Condes", "Avenida Kennedy 9001, Local 3092, Las Condes", -33.3912, -70.5475),
    "cinemark-arauco-coronel": ("Cinemark Arauco Coronel", "Av. Carlos Prats 0901, Local 1180, Coronel", -37.0135, -73.1643),
    "cinemark-espacio-urbano": ("Cinemark Espacio Urbano Viña del Mar", "Av. Benidorm 961, Pob. Vergara, Viña del Mar", -33.0067, -71.5477),
    "cinemark-gran-avenida": ("Cinemark Gran Avenida", "Gran Avenida José Miguel Carrera 6150, Local 1216", -33.5117, -70.6593),
    "cinemark-mall-marina": ("Cinemark Mall Marina", "Av. Libertad 1348, Local 301, Viña del Mar", -33.0089, -71.5494),
    "cinemark-mallplaza-arica": ("Cinemark Mallplaza Arica", "Av. Diego Portales 640, Local 300, Arica", -18.4693, -70.3113),
    "cinemark-mallplaza-iquique": ("Cinemark Mallplaza Iquique", "Av. Héroes de la Concepción 2555, Local 1, Iquique", -20.2337, -70.1476),
    "cinemark-mallplaza-la-serena": ("Cinemark Mallplaza La Serena", "Huanhualí 105 107, La Serena", -29.9149, -71.2606),
    "cinemark-mallplaza-mirador-bio-bio": ("Cinemark Mallplaza Mirador Bío Bío", "Los Carrera Poniente 301, Local CN200, Concepción", -36.8303, -73.0654),
    "cinemark-mallplaza-norte": ("Cinemark Mallplaza Norte", "Av. Américo Vespucio 1737, Local C6, Huechuraba", -33.3644, -70.6803),
    "cinemark-mallplaza-oeste": ("Cinemark Mallplaza Oeste", "Av. Américo Vespucio 1501, Local CN 100, 200 y 300, Cerrillos", -33.5155, -70.7215),
    "cinemark-mallplaza-tobalaba": ("Cinemark Mallplaza Tobalaba", "Av. Camilo Henríquez 3690, Puente Alto", -33.569, -70.5606),
    "cinemark-mallplaza-trebol": ("Cinemark Mallplaza Trébol", "Av. Alessandri 3177, Local B 107, Talcahuano", -36.7922, -73.0704),
    "cinemark-mallplaza-vespucio": ("Cinemark Mallplaza Vespucio", "Av. Vicuña Mackenna 7110, Local 158, La Florida", -33.517, -70.6),
    "cinemark-mid-mall-maipu": ("Cinemark Mid Mall Maipú", "Camino a Melipilla 15.900, Maipú", -33.5387, -70.7732),
    "cinemark-open-la-calera": ("Cinemark Open La Calera", "José Joaquín Pérez 12010, La Calera", -32.7917, -71.1952),
    "cinemark-open-ovalle": ("Cinemark Open Ovalle", "Av. Benavente 1075, Ovalle", -30.5993, -71.1863),
    "cinemark-open-rancagua": ("Cinemark Open Rancagua", "Teniente Coronel José Bernardo Cuevas 405, Rancagua", -34.1684, -70.7456),
    "cinemark-la-dehesa": ("Cinemark Portal La Dehesa", "Avenida La Dehesa 1445, Local 2000", -33.3569, -70.5157),
    "cinemark-portal-osorno": ("Cinemark Portal Osorno", "Plaza Yungay 609, 4to piso, Osorno", -40.5745, -73.1336),
    "cinemark-portal-nunoa": ("Cinemark Portal Ñuñoa", "Av. José Pedro Alessandri 1166, Local 4033, Ñuñoa", -33.4655, -70.6),
    "cinemark-rancagua": ("Cinemark Rancagua Machalí", "Av. San Joaquín 10, Camino Machalí, Rancagua", -34.1759, -70.7064),
}

CONF_CINEMA = "cinema"
CINEMA_NONE = "none"
CINEMA_NEAREST = "nearest"
CINEMARK_URL = "https://www.cinemark.cl/cartelera/{slug}"
CINEMA_INTERVAL = timedelta(hours=3)

# Efemérides chilenas (Wikipedia en español, "Un día como hoy")
CONF_EPHEMERIDES = "ephemerides"
EPHEMERIDES_URL = "https://es.wikipedia.org/api/rest_v1/feed/onthisday/all/{month:02d}/{day:02d}"
EPHEMERIDES_INTERVAL = timedelta(hours=1)  # solo recalcula; la descarga es una vez al día

EPHEMERIDES_CL_URL = "https://www.efemerides.cl/"  # días significativos del mes en curso

# Vehículo: restricción vehicular y revisión técnica (reglas en vehicle.py)
CONF_VEHICLE_DIGIT = "vehicle_digit"
CONF_VEHICLE_TYPE = "vehicle_type"
CONF_VEHICLES_MORE = "vehicles_more"
VEHICLE_NONE = "none"

# Combustibles (Bencina en Línea, Comisión Nacional de Energía)
CONF_FUEL_TYPES = "fuel_types"
CONF_FUEL_RADIUS = "fuel_radius"
FUEL_URL = "https://api.bencinaenlinea.cl/api/busqueda_estacion_filtro"
FUEL_BRANDS_URL = "https://api.bencinaenlinea.cl/api/marca"
FUEL_INTERVAL = timedelta(hours=3)
FUEL_BRANDS_REFETCH = timedelta(hours=24)
FUEL_DEFAULT_TYPES = ["93", "DI"]
FUEL_RADII = (2, 5, 10, 20)
FUEL_DEFAULT_RADIUS = 5
CONF_FUEL_MAX_AGE = "fuel_max_age"
FUEL_MAX_AGES = (7, 14, 30)
FUEL_DEFAULT_MAX_AGE = 14   # días: los precios más viejos suelen estar desactualizados

# Fútbol (ESPN, API pública no documentada)
CONF_FOOTBALL_TEAM = "football_team"
CONF_FOOTBALL_LEAGUE = "football_league"
CONF_FOOTBALL_NATIONAL = "football_national"
FOOTBALL_NONE = "none"
ESPN_SOCCER = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/chi.1/standings"
ESPN_LOCALE = "lang=es&region=cl"
FOOTBALL_LEAGUE_SLUG = "chi.1"
FOOTBALL_INTERVAL = timedelta(hours=3)
NATIONAL_INTERVAL = timedelta(hours=6)
FOOTBALL_LIVE_INTERVAL = timedelta(minutes=5)
FOOTBALL_SOON_INTERVAL = timedelta(minutes=15)
NATIONAL_TEAM_ID = "207"          # Selección de Chile en ESPN
NATIONAL_COMPETITIONS = ("fifa.friendly", "fifa.worldq.conmebol", "conmebol.america", "fifa.world")

# Primera División 2026 (id en ESPN -> nombre). Se actualiza cuando cambian los equipos de la liga.
FOOTBALL_TEAMS: dict[str, str] = {
    "4138": "Audax Italiano",
    "4133": "Cobresal",
    "2688": "Colo Colo",
    "8186": "Coquimbo Unido",
    "8110": "Deportes Concepción",
    "19195": "Deportes Limache",
    "4129": "Everton",
    "4134": "Huachipato",
    "4137": "La Serena",
    "6072": "O'Higgins",
    "4422": "Palestino",
    "885": "Universidad Católica",
    "4139": "Universidad de Chile",
    "5362": "Universidad de Concepción",
    "10144": "Unión La Calera",
    "7427": "Ñublense",
}

# Beneficios de tarjetas (N Beneficios, un servicio de Infoacción)
CONF_BENEFIT_CARDS = "benefit_cards"
CONF_BENEFIT_CATEGORIES = "benefit_categories"
BENEFITS_URL = "https://www.nbeneficios.cl/categorias/ver/{category}"
BENEFITS_SITE = "https://www.nbeneficios.cl/"
BENEFITS_INTERVAL = timedelta(hours=6)      # revisa si toca actualizar; la descarga es semanal y el día 1
BENEFITS_REFRESH_DAYS = 7
BENEFITS_MAX_PAGES = 10                     # por tarjeta y categoría
BENEFITS_PAUSE = 1.0                        # segundos entre consultas al sitio
BENEFITS_STORE_VERSION = 1
BENEFIT_CARDS: dict[str, str] = {
    "bancochile": "Banco de Chile",
    "bancoestado": "BancoEstado",
    "bci": "BCI",
    "bice": "BICE",
    "cencosud": "Cencosud",
    "cmr": "CMR Falabella",
    "copec": "Copec",
    "itau": "Itaú",
    "lider": "Lider",
    "mach": "MACH",
    "mercadopago": "Mercado Pago",
    "ripley": "Ripley",
    "santander": "Santander",
    "scotiabank": "Scotiabank",
    "security": "Security",
    "tenpo": "Tenpo",
}
BENEFIT_CATEGORIES: dict[str, str] = {
    "combustibles": "Combustibles",
    "comida": "Comida",
    "tiendas": "Tiendas y supermercados",
    "salud-belleza": "Salud y belleza",
    "entretencion": "Entretención",
    "viajes": "Viajes",
    "transporte": "Transporte",
    "vestuario-calzado": "Vestuario y calzado",
    "hogar": "Hogar",
    "tecnologia": "Tecnología",
    "educacion": "Educación",
    "fitness": "Fitness",
    "librerias": "Librerías",
    "mascotas": "Mascotas",
    "ninos": "Niños",
    "servicios": "Servicios",
    "tiempo-libre": "Tiempo libre",
    "apps": "Apps",
    "otros": "Otros",
}

# Calendario mensual de descuentos en bencina (archivo del repositorio, renovado cada mes)
FUEL_DISCOUNTS_URL = "https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/data/bencina.json"
FUEL_DISCOUNTS_INTERVAL = timedelta(hours=6)

# Red Regional (paraderos de ciudades fuera de Santiago; servicio no oficial de TransApp/DTPR)
CONF_REGIONAL_ZONE = "regional_zone"
CONF_REGIONAL_STOPS = "regional_stops"
REGIONAL_NONE = "none"
REGIONAL_URL = "https://phone.dtpr.transapp.cl/v7/phone"
REGIONAL_HEADERS = {"Os-type": "Android", "App-Version": "2.5.1", "Accept": "application/json"}
REGIONAL_INTERVAL = timedelta(minutes=1)
REGIONAL_NAMES_REFETCH = timedelta(days=7)
# Ciudades (clave -> (identificador del servicio, nombre)). Se actualiza si el servicio agrega o cambia ciudades.
REGIONAL_ZONES: dict[str, tuple[str, str]] = {
    "arica": ("23d78cd5-58c2-4606-904a-9d9bee4d9025", "Arica"),
    "iquique": ("b10b7a98-0a6e-427b-b380-a1984e809466", "Iquique"),
    "tocopilla-cl": ("95d5c8c0-0cb3-489f-b731-80116890df36", "Tocopilla"),
    "calama-cl": ("58afbdfd-9686-4733-b6f5-104b8917e3e4", "Calama"),
    "antofagasta": ("f2851f3c-246a-472a-96ab-f557503d15ba", "Antofagasta"),
    "copiapo": ("cc2cad83-5786-4525-b9e4-4d0d12a23de0", "Copiapó"),
    "serena": ("1d97f294-5fbc-4ed3-af32-4417214a6d60", "Coquimbo - La Serena"),
    "ovalle": ("69817f54-ca05-4e26-97cd-018afeb66f6e", "Ovalle"),
    "valparaiso-cl": ("e944e47c-a4f6-4be2-a8b4-3ed1968062cb", "Gran Valparaíso"),
    "rm-sur": ("1951b2f1-4a61-4cf3-81a1-94c4ecbfc5b8", "Región Metropolitana"),
    "rancagua": ("8a359f14-f61b-4c5f-b4b4-6917cfd08ff6", "Rancagua - Machalí"),
    "talca": ("50cde66c-2b67-4702-afa8-1f190249d9b8", "Talca"),
    "chillan": ("92288036-1ec2-48fc-8b2e-018fc04933b8", "Chillán"),
    "concepcion": ("f083f24e-7fee-4fdc-9520-dbbdae877f07", "Gran Concepción"),
    "villarrica": ("afe43285-f320-4657-9883-a41bf6ca224a", "Villarrica"),
    "temuco": ("c28e2682-b083-41ba-8827-5caac8b86181", "Temuco"),
    "valdivia-cl": ("fe2620a2-5301-40dd-b3a8-5870bd646b04", "Valdivia"),
    "osorno": ("94e8933a-db06-44b5-8b7e-399b73b7daf7", "Osorno"),
    "ptomontt": ("c4e2b90c-881e-46c5-adb4-a0840d8b002d", "Puerto Montt"),
    "castro": ("6a723180-2ec3-4c2d-b087-f7790ceb31c7", "Castro"),
    "quellon-cl": ("c0cfe3c9-cac1-4e91-8bd9-525ce0418fd6", "Quellón"),
    "puerto natales": ("476385bd-aebc-4d6f-a49b-5131c3019a46", "Puerto Natales"),
    "punta arenas": ("2fa4a6bc-d598-47ac-a3dc-f7c3b9c8100c", "Punta Arenas"),
}

# Titulares de noticias por tema (feeds RSS públicos de La Tercera y Cooperativa.cl)
CONF_NEWS_TOPICS = "news_topics"
CONF_NEWS_COUNT = "news_count"
NEWS_INTERVAL = timedelta(minutes=30)
NEWS_COOP_MIN_AGE = timedelta(minutes=60)   # Cooperativa declara una vigencia de 60 minutos en sus feeds
NEWS_COUNTS = (5, 10, 15)
NEWS_DEFAULT_COUNT = 5
NEWS_PAUSE = 0.5                             # segundos entre consultas al mismo medio
NEWS_LATERCERA_URL = "https://www.latercera.com/arc/outboundfeeds/rss/category/{slug}/?outputType=xml"
NEWS_COOPERATIVA_URL = "https://www.cooperativa.cl/noticias/site/tax/port/all/rss_{n}___1.xml"
NEWS_COOPERATIVA_FEEDS = tuple(range(1, 9))
NEWS_TOPICS: dict[str, str] = {
    "nacional": "Nacional",
    "politica": "Política",
    "mundo": "Mundo",
    "economia": "Economía",
    "deportes": "Deportes",
    "tecnologia": "Tecnología",
    "sociedad": "Sociedad",
    "cultura": "Cultura y tendencias",
    "servicios": "Servicios",
}
# Tema -> sección del feed de La Tercera (La Tercera publica un feed por sección)
NEWS_LATERCERA_SECTIONS: dict[str, str] = {
    "nacional": "nacional",
    "politica": "politica",
    "mundo": "mundo",
    "deportes": "el-deportivo",
    "tecnologia": "tecnologia",
    "cultura": "tendencias",
    "servicios": "servicios",
}
# Categoría que Cooperativa pone a cada noticia (sin tildes, en minúsculas) -> tema
NEWS_COOPERATIVA_CATEGORIES: dict[str, str] = {
    "pais": "nacional",
    "mundo": "mundo",
    "economia": "economia",
    "deportes": "deportes",
    "tecnologia": "tecnologia",
    "sociedad": "sociedad",
    "cultura": "cultura",
    "magazine": "cultura",
}

# Panoramas: agenda cultural (Chile Cultura, Ministerio de las Culturas) y Claro Arena
CONF_EVENTS_COMMUNE = "events_commune"
CONF_EVENTS_FREE_ONLY = "events_free_only"
CONF_CLARO_ARENA = "claro_arena"
CULTURE_EVENTS_URL = "https://chilecultura.gob.cl/api/v1.0/events/"
CULTURE_COMMUNES_URL = "https://chilecultura.gob.cl/api/v1.0/communes/"
CULTURE_LOOKBACK_DAYS = 45     # eventos de varios días que empezaron antes de hoy y siguen en curso
CULTURE_PAGE_SIZE = 100
CULTURE_MAX_PAGES = 5
CLARO_ARENA_URL = "https://claroarena.cl/cartelera/"
EVENTS_INTERVAL = timedelta(hours=6)
EVENTS_PAUSE = 1.0                # segundos entre páginas de la misma fuente

# Panoramas por Vamoh: calendario público (.ics) por comuna, o el enlace personal de la cuenta de Vamoh
CONF_VAMOH_URL = "vamoh_url"
VAMOH_SITE = "https://vamoh.cl/"
VAMOH_HOST_SUFFIX = "vamoh.cl"          # solo se leen enlaces https de vamoh.cl y sus subdominios
VAMOH_INTERVAL = timedelta(hours=6)     # Vamoh pide consultar «cada unas horas»
VAMOH_MAX_BYTES = 2_000_000
VAMOH_ATTRIBUTION = "Panoramas por Vamoh (vamoh.cl)"

# «Cerca de ti» (opcional): avisos según la ubicación de un teléfono, calculados solo dentro de Home Assistant
CONF_NEAR_TRACKER = "near_tracker"
CONF_NEAR_RADIUS = "near_radius"
NEAR_RADII = (150, 300, 500, 1000)       # metros
NEAR_DEFAULT_RADIUS = 300
NEAR_EXIT_FACTOR = 1.3                   # histéresis: se apaga al alejarse un 30 % más que el radio de aviso
NEAR_MAX_ACCURACY = 250                  # m: una ubicación menos precisa que esto se ignora

# Cargadores de vehículos eléctricos (mapa público del Ministerio de Energía, cargadorespublicos.cl; datos de la SEC)
CONF_EV_CONNECTORS = "ev_connectors"
CONF_EV_RADIUS = "ev_radius"
CONF_EV_MIN_POWER = "ev_min_power"
CONF_EV_BATTERY = "ev_battery"
CONF_EV_LOW_BATTERY = "ev_low_battery"
EV_URL = "https://cargadorespublicos.cl/api/data"
EV_INTERVAL = timedelta(minutes=15)
EV_MAX_BYTES = 16 * 1024 * 1024
EV_STATUS_MAX_AGE = timedelta(days=2)   # el estado «disponible» de un punto sin novedades hace más de 2 días no se da por vigente
EV_CONNECTORS: dict[str, str] = {
    "Tipo 2": "Tipo 2 (AC)",
    "CCS 2": "CCS 2 (carga rápida DC)",
    "CHAdeMO": "CHAdeMO (carga rápida DC)",
    "GB/T DC": "GB/T (carga rápida DC)",
    "Tipo 1": "Tipo 1 (AC)",
    "CCS 1": "CCS 1 (carga rápida DC)",
    "GB/T AC": "GB/T (AC)",
}
EV_RADII = (2, 5, 10, 20, 50)
EV_DEFAULT_RADIUS = 5
EV_MIN_POWERS = (0, 7, 22, 50, 100)
EV_LOW_BATTERIES = (20, 30, 40, 50)
EV_DEFAULT_LOW_BATTERY = 30
EV_ATTRIBUTION = "Cargadores: mapa de cargadores públicos del Ministerio de Energía (SEC)"
