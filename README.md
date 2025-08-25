

# Navaja Chilena — Home Assistant Custom Integration

**Autor:** @duvob90
**Versión:** 2025.1.5 (2025-08-25)

Integración multi-servicio para Chile:

- **Indicadores:** Dólar observado (CLP) y UF (CLP).
- **Transporte público:** Próximos buses por paradero de Red Movilidad (Santiago).
- **Metro:** Estado de la red del Metro de Santiago **por línea** (L1, L2, L3, L4, L4A, L5, L6).
- **Sismos:** Último sismo registrado en Chile, con soporte para mostrar **mapa**.

> Actualiza **cada 1 minuto** mediante `DataUpdateCoordinator`.

---

## Instalación (HACS)

1. En HACS → **Integrations** → menú ⋮ → **Custom repositories**.
2. Agrega este repo como tipo **Integration**.
3. Instala **Navaja Chilena** y reinicia Home Assistant.
4. Ve a **Settings → Devices & Services → Add Integration** y busca **Navaja Chilena**.
5. Ingresa uno o más **paraderos** (por ejemplo: `PA433,PA340`).

**Estructura del repo** (relevante para HACS):  
```
custom_components/navaja_chilena/
  ├── __init__.py
  ├── manifest.json
  ├── config_flow.py
  ├── const.py
  ├── coordinator.py
  └── sensor.py
hacs.json
README.md
LICENSE
```

---

## APIs usadas

- **USD a CLP:** `https://mindicador.cl/api/dolar`
- **UF a CLP:** `https://mindicador.cl/api/uf`
- **Estado Metro:** `https://www.metro.cl/api/estado-red`
- **Próximos buses:** `https://api.xor.cl/red/bus-stop/{stop_id}`  (UI para configurar paraderos)
- **Sismos (Chile):** `https://api.gael.cl/general/public/sismos`  
  **Provider:** Centro Sismológico Nacional, Universidad de Chile — **Formato:** JSON

---

## Entidades

- `sensor.navaja_dolar_clp` — valor del dólar observado (CLP).
- `sensor.navaja_uf` — valor UF (CLP).
- `sensor.metro_l1`, `sensor.metro_l2`, ..., `sensor.metro_l6` — estado por línea.
- `sensor.navaja_sismo` — magnitud del último sismo y atributos: `latitude`, `longitude`, `profundidad_km`, `referencia`, `fecha`.
- `sensor.redmovilidad_paradero_<ID>` — un sensor por paradero, con próximos buses en atributos.

> **Nota:** `sensor.navaja_sismo` incluye `latitude`/`longitude` para mostrarse en la tarjeta **map**.

---

## Ejemplos de tarjetas Lovelace (bonitas y nativas)

### 1) Indicadores (Tile Grid)
```yaml
type: grid
title: Indicadores financieros
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.navaja_dolar_clp
    name: Dólar (CLP)
  - type: tile
    entity: sensor.navaja_uf
    name: UF
```

### 2) Metro por línea (Tiles)
```yaml
type: grid
title: Estado Metro por Línea
columns: 3
square: false
cards:
  - type: tile
    entity: sensor.metro_l1
    name: L1
  - type: tile
    entity: sensor.metro_l2
    name: L2
  - type: tile
    entity: sensor.metro_l3
    name: L3
  - type: tile
    entity: sensor.metro_l4
    name: L4
  - type: tile
    entity: sensor.metro_l4a
    name: L4A
  - type: tile
    entity: sensor.metro_l5
    name: L5
  - type: tile
    entity: sensor.metro_l6
    name: L6
```

### 3) Último sismo (Map + etiqueta magnitud)
```yaml
type: map
title: Último Sismo
entities:
  - entity: sensor.navaja_sismo
    name: Magnitud
    label_mode: state
default_zoom: 7
```

### 4) Próximos buses (Glance + Entities)
```yaml
type: vertical-stack
cards:
  - type: glance
    title: Paraderos monitoreados
    entities:
      - entity: sensor.redmovilidad_paradero_PA433
        name: PA433
      - entity: sensor.redmovilidad_paradero_PA340
        name: PA340
  - type: entities
    title: Detalle próximos buses (PA433)
    entities:
      - entity: sensor.redmovilidad_paradero_PA433
        name: Próximas llegadas
        secondary_info: last-changed
```

---

## Configuración — paraderos

- La UI pedirá una lista de **paraderos** (códigos Red Movilidad, p. ej. `PA433`).  
- Puedes editarlos luego desde **Options** de la integración.

---

## Buenas prácticas aplicadas

- `DataUpdateCoordinator` con `async_get_clientsession` y *timeouts*.
- Diario *polling* unificado y diseño tolerante a fallos (si una API falla, el resto sigue).
- Logger por módulo (`logging.getLogger(__name__)`).
- Entidades *per-line* para Metro (nombres estables, `unique_id` por línea).
- *Config Flow* para UI (sin YAML).
- Estructura HACS: `custom_components/<domain>` + `hacs.json` + `manifest.json` con `version` y `codeowners` (@duvob90).

---

## Licencia
MIT — ver `LICENSE`.


### UI para paraderos (dentro de Home Assistant)
La integración expone una página simple para **validar/ver** códigos de paradero y sus próximas llegadas:

- Navega a: `https://TU_HA_LOCAL/navaja_chilena/stops` (reemplaza `TU_HA_LOCAL` por tu URL/host).
- Ingresa un código (p. ej. `PA433`) y verás el **nombre del paradero** y los **próximos buses**.

> Requiere estar autenticado en Home Assistant (misma sesión del navegador).


### Incidencias por línea (atributos)
Cada sensor de línea (`sensor.metro_l1`, etc.) agrega atributos con detalles si hay incidencias:

- `affected_stations`: lista de estaciones afectadas.
- `details`: descripciones/textos de la incidencia, si la API los entrega.

Ejemplo (card *entities* mostrando atributos vía "More info"):
```yaml
type: entities
title: Metro L1
entities:
  - entity: sensor.metro_l1
    name: Estado Línea 1
```


### Gestionar sensores de paraderos desde la UI
Ve a **Settings → Devices & Services → Navaja Chilena → Configure** y verás un menú con acciones:
- **Agregar paradero**: ingresa un código (p. ej. `PA433`). Se crea/recarga el sensor `sensor.redmovilidad_paradero_PA433`.
- **Eliminar paradero**: selecciona uno existente para eliminar su sensor.
- **Edición masiva**: pega/edita una lista separada por comas (`PA433,PA340,...`).

> Al guardar, la integración se recarga automáticamente para **crear/eliminar sensores** según corresponda.


