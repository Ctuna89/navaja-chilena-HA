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
VEHICLE_NONE = "none"
