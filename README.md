# Navaja Chilena 🇨🇱

Integración para Home Assistant (instalable vía HACS) con datos útiles de Chile.

## Qué incluye

| Módulo | Datos | Fuente | Actualización |
|---|---|---|---|
| Indicadores económicos | UF, dólar, euro, UTM, IPC, IVP, Imacec, TPM, cobre, desempleo, bitcoin, yen, dólar acuerdo | [mindicador.cl](https://mindicador.cl), con respaldo en [findic.cl](https://findic.cl) | 1 h |
| Metro de Santiago | Estado por línea (`operativa`, `con_problemas` o `cerrada` fuera de horario) y por estación | api.xor.cl | 2 min |
| Paraderos | Minutos al próximo bus y detalle por recorrido | api.xor.cl (Red Movilidad) | 1 min |
| Sismos | Último sismo del CSN (en español) y último sismo con coordenadas (USGS, para el mapa) | api.gael.cloud (CSN) y [USGS](https://earthquake.usgs.gov/fdsnws/event/1/) | 5 min |
| Feriados | Próximo feriado, días que faltan, si es irrenunciable | [boostr.cl](https://api.boostr.cl) | 1 h |
| Calidad del aire y UV | PM2.5, PM10, US AQI e índice UV en la ubicación de Home Assistant | [Open-Meteo](https://open-meteo.com) | 30 min |
| Farmacias de turno | Cantidad y detalle de farmacias de turno en tu comuna | MINSAL (Farmanet) | 6 h |
| Bolsa de Santiago | Último cierre del IPSA, variación en puntos y en %, y cierre anterior | [findic.cl](https://findic.cl) | 30 min |
| Santoral | Santo del día (y el de mañana), sin internet | incluido en la integración | a medianoche |
| Cine | Cartelera de hoy de tu cine Cinemark favorito o **el más cercano a tu casa**: películas, horarios, formato, sala y duración | cinemark.cl (lectura de su página) | 3 h |
| Efemérides | Días significativos y efemérides de Chile de hoy, y el próximo día significativo | [efemerides.cl](https://www.efemerides.cl) + [Wikipedia en español](https://es.wikipedia.org) (complemento) | 1 consulta al día por fuente |
| Criptomonedas | Bitcoin y Ethereum en pesos, con variación 24 h y 7 d | [Buda.com](https://www.buda.com) | 5 min |

No requiere claves de API.

## Instalación

1. HACS → ⋮ → *Repositorios personalizados* → pega `https://github.com/Ctuna89/navaja-chilena-HA` y elige categoría **Integración**.
2. Instala *Navaja Chilena* y reinicia Home Assistant.
3. *Ajustes → Dispositivos y servicios → Añadir integración → Navaja Chilena*.

## Configuración

En el asistente eliges los indicadores, si quieres el Metro y los códigos de paradero
separados por coma (ej. `PC615, PA433`). Todo se puede cambiar después en *Configurar*.

## Entidades

Los ids llevan el nombre del dispositivo como prefijo (por ejemplo `sensor.indicadores_economicos_uf`).

- **Indicadores**: `sensor.indicadores_economicos_<indicador>`: valor numérico; atributo `fecha`.
- **Metro**: `sensor.metro_de_santiago_linea_1`, `..._linea_2`, etc.: `operativa` / `con_problemas` / `cerrada`;
  atributos `mensaje`, `estaciones` (estado de cada una), `estaciones_con_problemas`, `horario_apertura`, `horario_cierre`.
  El horario se calcula en la integración (hora de Santiago): lun-vie 06:00–23:00, sáb 06:30–23:00,
  domingo y festivos 07:30–23:00 (para los festivos activa también el módulo de feriados).
  La API del Metro solo lista las líneas con incidentes (sin incidentes responde `lines: []`), así que una línea no listada es operativa únicamente si la respuesta es válida. **Si la fuente falla o no se entiende, el sensor queda «no disponible»; nunca se asume «operativa».**
- **Paraderos**: `sensor.paraderos_red_movilidad_paradero_<código>`: minutos al próximo bus; atributos `estado` y `recorridos`.
  Al configurar, se comprueba que el código exista. Solo se listan los recorridos con buses en camino (`recorridos_sin_buses` trae el resto).
- **Sismos**: `sensor.sismos_chile_ultimo_sismo_csn` (magnitud, `referencia`, `profundidad_km`, `fecha` tal como la publica el CSN; sin coordenadas) y `sensor.sismos_chile_ultimo_sismo_con_coordenadas_usgs` (además `latitude`/`longitude`, para la tarjeta de mapa).
- **IPSA**: `sensor.bolsa_de_santiago_ipsa`: último cierre en puntos; atributos `variacion_puntos`, `variacion_pct`, `fecha_cierre`, `cierre_anterior`, `fecha_cierre_anterior`. Es un dato de cierre diario (la bolsa no opera fines de semana ni feriados).
- **Santoral**: `sensor.santoral_santo_del_dia`; atributos `fecha` y `mañana`. Usa el santoral católico tradicional (archivo `santoral.py`); otros calendarios pueden asignar un santo distinto a algunos días y se puede editar.
- **Cine**: `sensor.<nombre del cine>_cartelera_de_hoy`: cantidad de películas hoy; atributos `peliculas` (título, duración, género, póster y `funciones` con hora, formato y sala), `resumen` (texto listo para una tarjeta Markdown), `proxima_funcion` y `fecha`. Las funciones de trasnoche (antes de las 05:00) cuentan para el día anterior.
- **Efemérides**: `sensor.efemerides_chilenas_efemerides_de_hoy`: la efeméride principal de hoy. Primero van los días significativos de efemerides.cl (hechos históricos y días conmemorativos, con descripción) y después, como complemento, lo chileno de Wikipedia (sucesos, fallecimientos y nacimientos). Atributos `efemerides` (hasta 10, cada una con `fuente` y `enlace`), `total`, `resumen` y `fuentes` (cuáles respondieron). Si hoy no hay nada, el estado es «Sin efemérides chilenas registradas para hoy». Si una fuente cae, la otra sigue funcionando.
- **Próximo día significativo**: `sensor.efemerides_chilenas_proximo_dia_significativo`: título, `fecha`, `dias_restantes`, `descripcion` y otros que caen ese mismo día. efemerides.cl solo publica el mes en curso, así que el último día del mes (o tras el último día significativo) el sensor queda «no disponible» hasta el cambio de mes.
- **Criptomonedas**: `sensor.criptomonedas_buda_bitcoin` y `..._ethereum`: precio en CLP; atributos `variacion_24h_pct`, `variacion_7d_pct`, `volumen_24h`.
- **Feriados**: `sensor.feriados_chile_proximo_feriado` (fecha) y `sensor.feriados_chile_dias_para_el_proximo_feriado`.
- **Aire y UV**: `sensor.calidad_del_aire_y_uv_pm2_5`, `..._pm10`, `..._indice_de_calidad_del_aire_us_aqi`, `..._indice_uv`.
- **Farmacias**: `sensor.farmacias_de_turno_<comuna>`: cantidad; atributo `farmacias` (hasta 20, con dirección, teléfono y coordenadas).

Cada módulo funciona por separado: si una fuente cae, solo sus sensores quedan «no disponibles» y se reintenta con
espera creciente (hasta 30 min), con un único aviso en el registro.

## Tarjetas de ejemplo

Todas usan tarjetas nativas de Home Assistant (no requieren HACS frontend). Para usarlas: *Panel → ⋮ → Editar →
Añadir tarjeta → Manual*, y pega el YAML. Los ids son los que crea la integración; **ajusta el de tu cine, tu comuna y tus
paraderos** (los ves en *Ajustes → Dispositivos y servicios → Navaja Chilena*).

### 💰 Indicadores económicos

```yaml
type: grid
title: Indicadores
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.indicadores_economicos_uf
    name: UF
    icon: mdi:home-city
  - type: tile
    entity: sensor.indicadores_economicos_dolar_observado
    name: Dólar
    icon: mdi:currency-usd
  - type: tile
    entity: sensor.indicadores_economicos_euro
    name: Euro
    icon: mdi:currency-eur
  - type: tile
    entity: sensor.indicadores_economicos_utm
    name: UTM
    icon: mdi:cash
```

Evolución del dólar en el último mes:

```yaml
type: statistics-graph
title: Dólar (30 días)
entities:
  - sensor.indicadores_economicos_dolar_observado
stat_types:
  - mean
days_to_show: 30
chart_type: line
```

Con la fecha del valor (atributo `fecha`):

```yaml
type: entities
title: Valores del día
entities:
  - entity: sensor.indicadores_economicos_uf
    name: UF
  - type: attribute
    entity: sensor.indicadores_economicos_uf
    attribute: fecha
    name: Fecha del valor
  - entity: sensor.indicadores_economicos_ipc
    name: IPC mensual
```

### 📈 Bolsa de Santiago (IPSA)

```yaml
type: tile
entity: sensor.bolsa_de_santiago_ipsa
name: IPSA
state_content:
  - state
  - variacion_pct
```

Detalle del cierre:

```yaml
type: entities
title: IPSA
entities:
  - entity: sensor.bolsa_de_santiago_ipsa
    name: Último cierre
  - type: attribute
    entity: sensor.bolsa_de_santiago_ipsa
    attribute: variacion_puntos
    name: Variación (puntos)
    suffix: pts
  - type: attribute
    entity: sensor.bolsa_de_santiago_ipsa
    attribute: variacion_pct
    name: Variación
    suffix: "%"
  - type: attribute
    entity: sensor.bolsa_de_santiago_ipsa
    attribute: fecha_cierre
    name: Fecha del cierre
```

### 🪙 Criptomonedas

```yaml
type: grid
title: Criptomonedas
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.criptomonedas_buda_bitcoin
    name: Bitcoin
    state_content:
      - state
      - variacion_24h_pct
  - type: tile
    entity: sensor.criptomonedas_buda_ethereum
    name: Ethereum
    state_content:
      - state
      - variacion_24h_pct
```

### 🚇 Metro de Santiago

Las siete líneas, con el color de cada una:

```yaml
type: grid
title: Metro de Santiago
columns: 4
square: false
cards:
  - type: tile
    entity: sensor.metro_de_santiago_linea_1
    name: L1
    color: red
  - type: tile
    entity: sensor.metro_de_santiago_linea_2
    name: L2
    color: yellow
  - type: tile
    entity: sensor.metro_de_santiago_linea_3
    name: L3
    color: brown
  - type: tile
    entity: sensor.metro_de_santiago_linea_4
    name: L4
    color: blue
  - type: tile
    entity: sensor.metro_de_santiago_linea_4a
    name: L4A
    color: light-blue
  - type: tile
    entity: sensor.metro_de_santiago_linea_5
    name: L5
    color: green
  - type: tile
    entity: sensor.metro_de_santiago_linea_6
    name: L6
    color: purple
```

Resumen con las estaciones afectadas (o el aviso de que el Metro está cerrado):

```yaml
type: markdown
title: Estado de la red
content: |
  {% set lineas = states.sensor | selectattr('entity_id', 'match', 'sensor.metro_de_santiago_linea') | list %}
  {% set cerradas = lineas | selectattr('state', 'eq', 'cerrada') | list %}
  {% set mal = lineas | selectattr('state', 'eq', 'con_problemas') | list %}
  {% if lineas and cerradas | count == lineas | count %}
  🌙 **Metro cerrado.** Abre a las {{ lineas[0].attributes.horario_apertura }}.
  {% elif mal %}
  {% for l in mal %}
  ### ⚠️ {{ l.name }}
  {{ l.attributes.mensaje }}
  {% for e in l.attributes.estaciones_con_problemas %}- {{ e }}
  {% endfor %}
  {% endfor %}
  {% elif lineas %}
  ✅ Sin incidentes en la red.
  {% else %}
  Sin datos del Metro.
  {% endif %}
```

### 🚌 Paraderos

```yaml
type: markdown
title: Paradero PC615
content: |
  {% set r = state_attr('sensor.paraderos_red_movilidad_paradero_pc615', 'recorridos') %}
  {{ state_attr('sensor.paraderos_red_movilidad_paradero_pc615', 'nombre') or '' }}

  {% if r %}
  {% for recorrido, info in r.items() %}
  - **{{ recorrido }}**: {{ info.minutos }} min
  {% endfor %}
  {% else %}
  No hay buses en camino.
  {% endif %}
```

Varios paraderos de un vistazo:

```yaml
type: glance
title: Próximo bus
entities:
  - entity: sensor.paraderos_red_movilidad_paradero_pc615
    name: PC615
```

### 🌋 Sismos

Mapa del último sismo (USGS trae las coordenadas):

```yaml
type: map
title: Último sismo
entities:
  - entity: sensor.sismos_chile_ultimo_sismo_con_coordenadas_usgs
    label_mode: state
default_zoom: 6
```

Último sismo del Centro Sismológico Nacional, en palabras:

```yaml
type: markdown
title: Último sismo (CSN)
content: |
  **Magnitud {{ states('sensor.sismos_chile_ultimo_sismo_csn') }}** a {{ state_attr('sensor.sismos_chile_ultimo_sismo_csn', 'profundidad_km') | int(0) }} km de profundidad  
  {{ state_attr('sensor.sismos_chile_ultimo_sismo_csn', 'referencia') }}  
  🕒 {{ state_attr('sensor.sismos_chile_ultimo_sismo_csn', 'fecha') }}
```

### 📅 Feriados

```yaml
type: grid
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.feriados_chile_proximo_feriado
    name: Próximo feriado
    icon: mdi:calendar-star
  - type: tile
    entity: sensor.feriados_chile_dias_para_el_proximo_feriado
    name: Faltan
    icon: mdi:calendar-clock
```

Con el nombre del feriado:

```yaml
type: markdown
content: |
  🎉 **{{ state_attr('sensor.feriados_chile_proximo_feriado', 'nombre') }}**
  el {{ states('sensor.feriados_chile_proximo_feriado') }}
  (en {{ states('sensor.feriados_chile_dias_para_el_proximo_feriado') }} días)
  {% if state_attr('sensor.feriados_chile_proximo_feriado', 'irrenunciable') %}· irrenunciable{% endif %}
```

### 🌫️ Calidad del aire y UV

```yaml
type: grid
title: Aire y radiación UV
columns: 2
square: false
cards:
  - type: gauge
    entity: sensor.calidad_del_aire_y_uv_indice_de_calidad_del_aire_us_aqi
    name: Calidad del aire (AQI)
    min: 0
    max: 300
    severity:
      green: 0
      yellow: 51
      red: 101
  - type: gauge
    entity: sensor.calidad_del_aire_y_uv_indice_uv
    name: Índice UV
    min: 0
    max: 12
    severity:
      green: 0
      yellow: 3
      red: 8
  - type: tile
    entity: sensor.calidad_del_aire_y_uv_pm2_5
    name: PM2.5
  - type: tile
    entity: sensor.calidad_del_aire_y_uv_pm10
    name: PM10
```

### 💊 Farmacias de turno

```yaml
type: markdown
title: Farmacias de turno
content: |
  {% set f = state_attr('sensor.farmacias_de_turno_nunoa', 'farmacias') %}
  {% if f %}
  {% for x in f %}
  **{{ x.nombre }}**  
  {{ x.direccion }}{% if x.apertura and x.cierre %} · {{ x.apertura }}–{{ x.cierre }}{% endif %}  
  {% if x.telefono %}📞 {{ x.telefono }}{% endif %}

  {% endfor %}
  {% else %}
  Sin farmacias de turno registradas hoy.
  {% endif %}
```

### 🎬 Cine

Cartelera de hoy con los horarios de cada película:

```yaml
type: markdown
title: Cartelera de hoy
content: |
  {% set p = state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'peliculas') %}
  {% for m in p %}
  **{{ m.titulo }}** · {{ m.duracion_min }} min  
  {{ m.funciones | map(attribute='hora') | join(' · ') }}

  {% endfor %}
```

Versión corta (texto ya armado por la integración) y próxima función:

```yaml
type: markdown
title: Cartelera
content: |
  {{ state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'resumen') }}

  {% set n = state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'proxima_funcion') %}
  {% if n %}⏭️ Próxima función: **{{ n.titulo }}** a las {{ n.hora }}{% endif %}
```

### 🇨🇱 Efemérides

Las de hoy, con su fuente:

```yaml
type: markdown
title: Un día como hoy
content: |
  {% for e in state_attr('sensor.efemerides_chilenas_efemerides_de_hoy', 'efemerides') %}
  **{{ e.anio if e.anio else '—' }}** · {{ e.texto }} _({{ e.fuente }})_

  {% else %}
  Sin efemérides chilenas registradas para hoy.
  {% endfor %}
```

Próximo día significativo:

```yaml
type: tile
entity: sensor.efemerides_chilenas_proximo_dia_significativo
name: Próximo día significativo
icon: mdi:calendar-arrow-right
state_content:
  - state
  - dias_restantes
```

### ✝️ Santoral

```yaml
type: markdown
title: Santoral
content: |
  🙏 **Hoy:** {{ states('sensor.santoral_santo_del_dia') }}  
  Mañana: {{ state_attr('sensor.santoral_santo_del_dia', 'mañana') }}
```

### ☀️ Resumen del día (todo junto)

```yaml
type: markdown
title: Buen día 🇨🇱
content: |
  **{{ states('sensor.santoral_santo_del_dia') }}**

  💵 UF ${{ '{:,.0f}'.format(states('sensor.indicadores_economicos_uf') | float(0)) | replace(',', '.') }} ·
  Dólar ${{ '{:,.0f}'.format(states('sensor.indicadores_economicos_dolar_observado') | float(0)) | replace(',', '.') }}

  📈 IPSA {{ '{:,.0f}'.format(states('sensor.bolsa_de_santiago_ipsa') | float(0)) | replace(',', '.') }}
  ({{ state_attr('sensor.bolsa_de_santiago_ipsa', 'variacion_pct') }} %)

  🇨🇱 {{ states('sensor.efemerides_chilenas_efemerides_de_hoy') }}
```

## Actualizar desde la versión 1.x

La versión anterior usaba otros nombres de entidad y otra configuración. Tras actualizar en HACS (*⋮ → Volver a descargar*)
y reiniciar, lo más limpio es **eliminar la integración en Dispositivos y servicios y volver a añadirla**.
Las tarjetas que usaban `sensor.navaja_*` o `sensor.metro_l1` deberán apuntar a los ids nuevos.

## Desarrollo

```bash
pip install pytest-homeassistant-custom-component
pytest
```

### Estado de las fuentes

Probadas contra los servicios reales el 2026-11-08 (el código de la integración se ejecutó contra cada API):

| Fuente | Resultado |
|---|---|
| mindicador.cl, findic.cl (indicadores e IPSA), api.xor.cl (Metro y paraderos), api.gael.cloud, USGS, boostr, Open-Meteo, Buda | ✅ funcionan |
| MINSAL (farmacias de turno) | ⚠️ bloquea servidores de datacenter (Cloudflare 403); no pudo confirmarse, puede funcionar desde una red residencial |
| SINCA (calidad del aire oficial) | ⚠️ 403 desde datacenter; Open-Meteo cubre PM2.5/PM10 |
| apis.digital.gob.cl (feriados), feriados-cl.netlify.app, api-sismologia-chile.herokuapp.com, api.gael.cl | ❌ caídas o inexistentes (no se usan) |
| api.cne.cl (combustibles) | ❌ exige cuenta |
| efemerides.cl | ✅ HTML simple, mes en curso (17 entradas en noviembre); su `robots.txt` permite la lectura |
| es.wikipedia.org (efemérides) | ✅ funciona, pero es una lista mundial: se filtra lo chileno, así que algunos días no habrá resultados |
| cinemark.cl | ✅ 22 cines (sin API oficial: se lee el bloque estructurado de cada página; puede cambiar sin aviso) |
| Cineplanet, Cine Hoyts/Cinépolis | ❌ no incluidos: Cineplanet solo carga con JavaScript y exige un token; Hoyts/Cinépolis están detrás de Cloudflare |

Las respuestas reales están guardadas en `tests/fixtures` y las pruebas las usan. Son servicios comunitarios o sin contrato de estabilidad: su formato puede cambiar.

Fuente de ideas: [listado de APIs públicas de Chile](https://github.com/juanbrujo/listado-apis-publicas-en-chile).

Los días significativos provienen de [efemerides.cl](https://www.efemerides.cl) (cada entrada enlaza al sitio; se lee una vez al día, identificando la integración en el `User-Agent`). Los textos de Wikipedia en español están bajo licencia
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.es); el sensor incluye el atributo `fuente`
y el enlace a cada artículo. La integración consulta Wikipedia una vez al día e identifica su origen en el
`User-Agent`, como piden sus normas de uso.

Licencia: ver [LICENSE](LICENSE).
