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
    "bitcoin": "Bitcoin",
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
QUAKES_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&orderby=time"
    "&limit=100&minmagnitude=2.5&minlatitude=-56&maxlatitude=-17"
    "&minlongitude=-76&maxlongitude=-66"
)
HOLIDAYS_URLS = (
    "https://apis.digital.gob.cl/fl/feriados/{year}",
    "https://api.boostr.cl/holidays/{year}.json",
)
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
