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
