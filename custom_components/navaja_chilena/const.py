# Author: duvob90
from __future__ import annotations

DOMAIN = "navaja_chilena"
TITLE = "Navaja Chilena"

CONF_STOP_IDS = "stop_ids"  # comma-separated list
DEFAULT_STOPS = "PA433"
UPDATE_INTERVAL_SECONDS = 60

# API endpoints
USD_URL = "https://mindicador.cl/api/dolar"
UF_URL = "https://mindicador.cl/api/uf"
METRO_URL = "https://www.metro.cl/api/estado-red"
BUS_URL_TMPL = "https://api.xor.cl/red/bus-stop/{stop_id}"
SISMOS_URL = "https://api.gael.cl/general/public/sismos"

# Known Metro lines (used if API does not list lines initially)
METRO_KNOWN_LINES = ["L1", "L2", "L3", "L4", "L4A", "L5", "L6"]
