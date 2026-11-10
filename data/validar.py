"""Valida data/bencina.json antes de publicarlo (sin dependencias de Home Assistant).

Uso: python data/validar.py [--mes-actual]
Con --mes-actual exige que `vigencia` sea el mes en curso (hora de Chile).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("const", ROOT / "custom_components/navaja_chilena/const.py")
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)

MAX_AHORRO_LITRO = 400     # CLP/L: por encima es casi seguro un error
MAX_PORCENTAJE = 30


def validar(data: object, exigir_mes_actual: bool = False) -> list[str]:
    errores: list[str] = []
    if not isinstance(data, dict):
        return ["La raíz debe ser un objeto"]
    vig = str(data.get("vigencia", ""))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", vig):
        errores.append("`vigencia` debe ser AAAA-MM")
    elif exigir_mes_actual and vig != datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m"):
        errores.append(f"`vigencia` ({vig}) no es el mes en curso")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("actualizado", ""))):
        errores.append("`actualizado` debe ser AAAA-MM-DD")
    filas = data.get("descuentos")
    if not isinstance(filas, list) or not filas:
        return errores + ["`descuentos` debe ser una lista con al menos un descuento"]
    for i, f in enumerate(filas, 1):
        p = f"descuento {i}"
        if not isinstance(f, dict):
            errores.append(f"{p}: debe ser un objeto")
            continue
        dias = f.get("dias")
        if not isinstance(dias, list) or not dias or not all(isinstance(d, int) and 1 <= d <= 7 for d in dias):
            errores.append(f"{p}: `dias` debe ser una lista de 1 (lunes) a 7 (domingo)")
        if f.get("tarjeta") not in const.BENEFIT_CARDS:
            errores.append(f"{p}: `tarjeta` desconocida ({f.get('tarjeta')!r})")
        if not str(f.get("monto", "")).strip():
            errores.append(f"{p}: falta `monto`")
        if not isinstance(f.get("confirmado"), bool):
            errores.append(f"{p}: `confirmado` debe ser true o false")
        if not str(f.get("fuente", "")).startswith("https://"):
            errores.append(f"{p}: `fuente` debe ser una URL https")
        a, pc = f.get("ahorro_clp_litro"), f.get("porcentaje")
        if a is not None and not (isinstance(a, (int, float)) and 0 < a <= MAX_AHORRO_LITRO):
            errores.append(f"{p}: `ahorro_clp_litro` fuera de rango (1-{MAX_AHORRO_LITRO})")
        if pc is not None and not (isinstance(pc, (int, float)) and 0 < pc <= MAX_PORCENTAJE):
            errores.append(f"{p}: `porcentaje` fuera de rango (1-{MAX_PORCENTAJE})")
    return errores


def main() -> int:
    data = json.loads((ROOT / "data/bencina.json").read_text(encoding="utf-8"))
    errores = validar(data, "--mes-actual" in sys.argv)
    for e in errores:
        print("ERROR:", e)
    if not errores:
        print(f"OK: {len(data['descuentos'])} descuentos, vigencia {data['vigencia']}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
