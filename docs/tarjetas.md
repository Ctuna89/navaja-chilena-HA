# Tarjetas de ejemplo 🇨🇱

[← Volver al README](../README.md)

Listas para copiar y pegar: usan solo tarjetas que ya trae Home Assistant, sin instalar nada extra. Las imágenes son
capturas reales de Home Assistant (los valores cambian con el tiempo). En tu panel pulsa
*⋮ → Editar panel → Añadir tarjeta → Manual* y pega el YAML. Reemplaza el cine, la comuna y los paraderos de los ejemplos
por los tuyos (los ids los ves en *Ajustes → Dispositivos y servicios → Navaja Chilena*).

> Consejo: en GitHub, el botón de esquema (arriba a la derecha de este archivo) te lleva directo a cada módulo.

## 💰 Indicadores económicos

![Tarjetas con UF, dólar, euro y UTM](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/indicadores-resumen.png)

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

![Gráfico del dólar en los últimos 30 días](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/indicadores-grafico.png)

```yaml
type: statistics-graph
title: Dólar (30 días)
entities:
  - sensor.indicadores_economicos_dolar_observado
stat_types:
  - mean
days_to_show: 30
period: day
chart_type: line
```

Con la fecha del valor (atributo `fecha`):

![Lista de valores del día con su fecha](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/indicadores-detalle.png)

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

## 📈 Bolsa de Santiago (IPSA)

![Tarjeta del IPSA](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/ipsa-tarjeta.png)

```yaml
type: tile
entity: sensor.bolsa_de_santiago_ipsa
name: IPSA
```

Detalle del cierre:

![Detalle del último cierre del IPSA](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/ipsa-detalle.png)

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

## 🪙 Criptomonedas

![Bitcoin y Ethereum con su variación de 24 horas](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/criptomonedas.png)

```yaml
type: entities
title: Criptomonedas
entities:
  - entity: sensor.criptomonedas_buda_bitcoin
    name: Bitcoin
  - type: attribute
    entity: sensor.criptomonedas_buda_bitcoin
    attribute: variacion_24h_pct
    name: Variación 24 h
    suffix: "%"
  - entity: sensor.criptomonedas_buda_ethereum
    name: Ethereum
  - type: attribute
    entity: sensor.criptomonedas_buda_ethereum
    attribute: variacion_24h_pct
    name: Variación 24 h
    suffix: "%"
```

## 🚇 Metro de Santiago

Las siete líneas, con el color de cada una:

![Estado de las siete líneas del Metro](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/metro-lineas.png)

*Ejemplo con un incidente simulado en la Línea 2.*

```yaml
type: grid
title: Metro de Santiago
columns: 3
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

![Resumen del estado de la red del Metro](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/metro-estado.png)

*Ejemplo con un incidente simulado en la Línea 2.*

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

## 🚌 Paraderos

![Minutos para el próximo bus por recorrido](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/paradero-detalle.png)

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

![Vista rápida de un paradero](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/paradero-vistazo.png)

```yaml
type: glance
title: Próximo bus
entities:
  - entity: sensor.paraderos_red_movilidad_paradero_pc615
    name: PC615
```

## 🚍 Paraderos de la Red Regional
Próximas llegadas a un paradero fuera de Santiago (cambia la ciudad y el código por los tuyos).

![Próximas llegadas a un paradero de la Red Regional en Temuco, con estimación y distancia](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/paraderos-regional.png)

```yaml
type: markdown
title: 🚍 Paradero 53 · Temuco
content: |
  {% set llegadas = state_attr('sensor.paraderos_red_regional_temuco_paradero_53', 'proximas') or [] %}
  {% if llegadas | length == 0 %}
  Sin buses próximos.
  {% else %}
  {% for b in llegadas[:5] %}
  - **{{ b.servicio }}** ({{ b.sentido }}) · {{ b.estimacion }} · {{ b.distancia }}{{ ' · en vivo' if b.tiempo_real }}
  {% endfor %}
  {% endif %}
  {% for a in state_attr('sensor.paraderos_red_regional_temuco_paradero_53', 'alertas') or [] %}
  ⚠️ {{ a }}
  {% endfor %}
```

## 🚆 Tren Limache–Puerto
Los próximos trenes de un trayecto, con la hora estimada y los que no llegan a tu destino marcados (cambia el sensor por el tuyo):

![Próximos trenes de Villa Alemana a Limache, con un tren que solo llega hasta Sargento Aldea](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/tren-proximos.png)

```yaml
type: markdown
title: Villa Alemana → Limache
content: |
  {% set e = 'sensor.tren_limache_puerto_villa_alemana_limache' %}
  {% for t in (state_attr(e, 'servicios') or [])[:4] %}
  - **{{ t.tiempo }}**{% if t.hora_estimada %} · ≈ {{ as_timestamp(t.hora_estimada) | timestamp_custom('%H:%M') }}{% endif %} · {{ t.tipo }}{% if t.llega_a_destino == false %} · ⚠️ solo hasta {{ t.estacion_final }}{% endif %}
  {% else %}
  {{ 'Sin datos de EFE por ahora.' if states(e) in ['unavailable', 'unknown'] else 'Sin servicios informados.' }}
  {% endfor %}
```

Ida y vuelta de un vistazo:

![Próximo tren a Puerto y a Limache](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/tren-ida-vuelta.png)

```yaml
type: grid
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.tren_limache_puerto_villa_alemana_puerto
    name: → Puerto
    icon: mdi:train
    color: blue
    state_content: [state, hasta]
  - type: tile
    entity: sensor.tren_limache_puerto_villa_alemana_limache
    name: → Limache
    icon: mdi:train
    color: green
    state_content: [state, hasta]
```

## 🌋 Sismos

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

![Último sismo del Centro Sismológico Nacional](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/sismo-csn.png)

```yaml
type: markdown
title: Último sismo (CSN)
content: |
  **Magnitud {{ states('sensor.sismos_chile_ultimo_sismo_csn') }}** a {{ state_attr('sensor.sismos_chile_ultimo_sismo_csn', 'profundidad_km') | int(0) }} km de profundidad  
  {{ state_attr('sensor.sismos_chile_ultimo_sismo_csn', 'referencia') }}  
  🕒 {{ state_attr('sensor.sismos_chile_ultimo_sismo_csn', 'fecha') }}
```

## 📅 Feriados

![Próximo feriado y días que faltan](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/feriados-tarjetas.png)

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

![Nombre del próximo feriado](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/feriados-texto.png)

```yaml
type: markdown
content: |
  🎉 **{{ state_attr('sensor.feriados_chile_proximo_feriado', 'nombre') }}**
  el {{ states('sensor.feriados_chile_proximo_feriado') }}
  (en {{ states('sensor.feriados_chile_dias_para_el_proximo_feriado') }} días)
  {% if state_attr('sensor.feriados_chile_proximo_feriado', 'irrenunciable') %}· irrenunciable{% endif %}
```

## 🌫️ Calidad del aire y UV

![Medidores de calidad del aire e índice UV](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/aire-uv.png)

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

## 💊 Farmacias de turno

![Lista de farmacias de turno](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/farmacias.png)

*Datos de ejemplo.*

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

## 🎬 Cine

Cartelera de hoy con el póster de cada película (el ejemplo muestra las 6 primeras; quita `[:6]` para verlas todas):

![Cartelera de cine con el póster y los horarios de cada película](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/cine-cartelera.png)

```yaml
type: markdown
title: Cartelera de hoy
content: |
  <table>
  {% for m in state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'peliculas')[:6] %}
  <tr>
  <td>{% if m.poster %}<img src="{{ m.poster }}" width="70">{% endif %}</td>
  <td><b>{{ m.titulo }}</b> · {{ m.duracion_min }} min<br>{{ m.funciones | map(attribute='hora') | join(' · ') }}</td>
  </tr>
  {% endfor %}
  </table>
```

Próxima función con su póster:

![Póster y hora de la próxima función](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/cine-proxima.png)

```yaml
type: markdown
title: Próxima función
content: |
  {% set n = state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'proxima_funcion') %}
  {% if n %}
  <table>
  <tr>
  <td>{% if n.poster %}<img src="{{ n.poster }}" width="110">{% endif %}</td>
  <td><b>{{ n.titulo }}</b><br>a las {{ n.hora }}</td>
  </tr>
  </table>
  {% else %}
  Hoy no quedan más funciones.
  {% endif %}
```

El sensor también entrega el póster de la próxima función como imagen de la entidad, así que las tarjetas que muestran la
imagen de una entidad (como `tile`) lo usan directamente:

![Tarjeta con el póster de la próxima película como imagen](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/cine-picture.png)

```yaml
type: tile
entity: sensor.cinemark_alto_las_condes_cartelera_de_hoy
name: Cartelera de hoy
show_entity_picture: true
vertical: true
```

Versión corta (texto ya armado por la integración) y próxima función:

![Cartelera de cine en versión corta con la próxima función](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/cine-resumen.png)

```yaml
type: markdown
title: Cartelera
content: |
  {{ state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'resumen') }}

  {% set n = state_attr('sensor.cinemark_alto_las_condes_cartelera_de_hoy', 'proxima_funcion') %}
  {% if n %}⏭️ Próxima función: **{{ n.titulo }}** a las {{ n.hora }}{% endif %}
```

## 🇨🇱 Efemérides

Las de hoy, con su fuente:

![Efemérides chilenas de hoy](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/efemerides-hoy.png)

```yaml
type: markdown
title: Un día como hoy
content: |
  {% for e in state_attr('sensor.efemerides_chilenas_efemerides_de_hoy', 'efemerides') %}
  {% if e.anio %}**{{ e.anio }}** · {% endif %}{{ e.texto }} _({{ e.fuente }})_

  {% else %}
  Sin efemérides chilenas registradas para hoy.
  {% endfor %}
```

Próximo día significativo:

![Próximo día significativo](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/efemerides-proximo.png)

```yaml
type: entities
title: Próximo día significativo
entities:
  - entity: sensor.efemerides_chilenas_proximo_dia_significativo
    name: Día
  - type: attribute
    entity: sensor.efemerides_chilenas_proximo_dia_significativo
    attribute: fecha
    name: Fecha
  - type: attribute
    entity: sensor.efemerides_chilenas_proximo_dia_significativo
    attribute: dias_restantes
    name: Faltan
    suffix: día(s)
```

## ✝️ Santoral

![Santo del día](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/santoral.png)

```yaml
type: markdown
title: Santoral
content: |
  🙏 **Hoy:** {{ states('sensor.santoral_santo_del_dia') }}  
  Mañana: {{ state_attr('sensor.santoral_santo_del_dia', 'mañana') }}
```

## ⚽ Fútbol

Tu equipo: próximo partido, último resultado y posición en la tabla (cambia `colo_colo` por tu equipo):

![Próximo partido, último resultado y posición de Colo Colo](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/futbol-resumen.png)

```yaml
type: grid
title: Colo Colo
columns: 1
square: false
cards:
  - type: tile
    entity: sensor.futbol_colo_colo_proximo_partido
    name: Próximo partido
    show_entity_picture: true
    state_content:
      - state
      - rival
  - type: tile
    entity: sensor.futbol_colo_colo_ultimo_resultado
    name: Último resultado
    show_entity_picture: true
  - type: tile
    entity: sensor.futbol_colo_colo_posicion_en_la_tabla
    name: Posición en la tabla
    show_entity_picture: true
```

Más detalle del próximo partido y de la campaña:

![Detalle del próximo partido, la forma reciente y los puntos](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/futbol-detalle.png)

```yaml
type: entities
title: Colo Colo
entities:
  - entity: sensor.futbol_colo_colo_proximo_partido
    name: Próximo partido
  - type: attribute
    entity: sensor.futbol_colo_colo_proximo_partido
    attribute: hora_local
    name: Cuándo
  - type: attribute
    entity: sensor.futbol_colo_colo_proximo_partido
    attribute: estadio
    name: Dónde
  - type: attribute
    entity: sensor.futbol_colo_colo_ultimo_resultado
    attribute: forma
    name: Últimos 5 (G ganó, E empató, P perdió)
  - type: attribute
    entity: sensor.futbol_colo_colo_posicion_en_la_tabla
    attribute: puntos
    name: Puntos
    suffix: pts
  - type: attribute
    entity: sensor.futbol_colo_colo_posicion_en_la_tabla
    attribute: puntos_bajo_el_lider
    name: Puntos bajo el líder
```

Los partidos de la próxima fecha de la Primera División:

![Partidos de la próxima fecha con horario y estadio](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/futbol-proxima-fecha.png)

```yaml
type: markdown
title: Próxima fecha
content: |
  {% for p in state_attr('sensor.futbol_primera_division_proxima_fecha', 'partidos') %}
  **{{ p.local }}** vs **{{ p.visita }}**  
  {{ p.hora_local }} · {{ p.estadio }}

  {% else %}
  No hay partidos programados.
  {% endfor %}
```

Resultados de la última fecha:

![Resultados de la última fecha](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/futbol-ultima-fecha.png)

```yaml
type: markdown
title: Última fecha
content: |
  {% for r in state_attr('sensor.futbol_primera_division_ultima_fecha', 'resultados') %}
  {{ r.local }} **{{ r.marcador }}** {{ r.visita }}  
  {% endfor %}
```

Tabla de posiciones (los 8 primeros):

![Tabla de posiciones de la Primera División](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/futbol-tabla.png)

```yaml
type: markdown
title: Primera División
content: |
  | # | Equipo | PJ | DG | Pts |
  |:-:|:--|:-:|:-:|:-:|
  {% for f in state_attr('sensor.futbol_primera_division_tabla_de_posiciones', 'tabla')[:8] -%}
  | {{ f.posicion }} | {{ f.equipo }} | {{ f.pj }} | {{ f.dg }} | **{{ f.pts }}** |
  {% endfor %}
```

La Roja:

![Último resultado y próximo partido de La Roja](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/futbol-roja.png)

```yaml
type: markdown
title: La Roja 🇨🇱
content: |
  {% set n = 'sensor.futbol_la_roja_proximo_partido' %}
  **Último:** {{ states('sensor.futbol_la_roja_ultimo_resultado') }}  
  {% if states(n) not in ['unknown', 'unavailable'] %}
  **Próximo:** vs {{ state_attr(n, 'rival') }} — {{ state_attr(n, 'hora_local') }} ({{ state_attr(n, 'competencia') }})
  {% else %}
  **Próximo:** sin partido programado
  {% endif %}
```

## ⛽ Combustibles

La bencina y el diésel más baratos cerca de tu casa, con la marca de la estación:

![Precio de la bencina 93 y el diésel más baratos cerca, con la marca](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/combustibles-resumen.png)

```yaml
type: grid
title: Combustible más barato cerca
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.combustibles_gasolina_93_mas_barata
    name: Bencina 93
    show_entity_picture: true
    state_content:
      - state
      - marca
  - type: tile
    entity: sensor.combustibles_diesel_mas_barato
    name: Diésel
    show_entity_picture: true
    state_content:
      - state
      - marca
```

Las 5 estaciones más baratas de bencina 93:

![Las cinco estaciones más baratas de bencina 93 con dirección y distancia](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/combustibles-ranking.png)

```yaml
type: markdown
title: Bencina 93 más barata
content: |
  {% for e in state_attr('sensor.combustibles_gasolina_93_mas_barata', 'mas_baratas') %}
  **${{ '{:,.0f}'.format(e.precio) | replace(',', '.') }}** · {{ e.marca }} — {{ e.direccion }}, {{ e.comuna }} ({{ e.distancia_km }} km)  
  {% else %}
  No hay estaciones con precio vigente cerca.
  {% endfor %}
```

Precio, promedio de la zona y cuántas estaciones hay:

![Precio, promedio de la zona, estaciones y antigüedad del precio](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/combustibles-detalle.png)

```yaml
type: entities
title: Bencina 93 cerca de ti
entities:
  - entity: sensor.combustibles_gasolina_93_mas_barata
    name: Más barata
  - type: attribute
    entity: sensor.combustibles_gasolina_93_mas_barata
    attribute: promedio_en_radio
    name: Promedio de la zona
    suffix: CLP/L
  - type: attribute
    entity: sensor.combustibles_gasolina_93_mas_barata
    attribute: estaciones_en_radio
    name: Estaciones en el radio
  - type: attribute
    entity: sensor.combustibles_gasolina_93_mas_barata
    attribute: antiguedad_dias
    name: Precio informado hace
    suffix: días
```

## 💳 Descuentos de tus tarjetas
Lista de los descuentos de hoy en una categoría (cambia `comida` por `combustibles`, `salud_y_belleza`, etc.).

![Descuentos de hoy en comida para tus tarjetas, con comercio, tarjeta y enlace](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/descuentos-hoy.png)

```yaml
type: markdown
title: 💳 Descuentos de hoy en comida
content: |
  {% set items = state_attr('sensor.descuentos_de_tarjetas_descuentos_de_hoy_comida', 'hoy') or [] %}
  {% if items | length == 0 %}
  Hoy no hay descuentos de tus tarjetas en esta categoría.
  {% else %}
  {% for b in items[:8] %}
  - **{{ b.comercio }}** · {{ b.descuento }} — {{ b.tarjeta }} ([ver]({{ b.url }}))
  {% endfor %}
  {% endif %}
```

Aviso en el celular cuando hay descuentos (automatización):

```yaml
alias: Descuentos de hoy en combustibles
triggers:
  - trigger: state
    entity_id: sensor.descuentos_de_tarjetas_descuentos_de_hoy_combustibles
conditions:
  - condition: numeric_state
    entity_id: sensor.descuentos_de_tarjetas_descuentos_de_hoy_combustibles
    above: 0
actions:
  - action: notify.notify          # cambia por tu servicio, p. ej. notify.mobile_app_mi_celular
    data:
      title: 💳 Descuentos de hoy
      message: |
        {% for b in state_attr(trigger.entity_id, 'hoy')[:5] %}
        {{ b.comercio }}: {{ b.descuento }} ({{ b.tarjeta }})
        {% endfor %}
```

## 📰 Noticias por tema
Titulares de un tema con enlace a la nota (cambia `nacional` por `politica`, `mundo`, `economia`, `deportes`…).

![Titulares nacionales de La Tercera y Cooperativa con enlace a cada nota](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/noticias-nacional.png)

```yaml
type: markdown
title: 📰 Titulares · Nacional
content: |
  {% for n in state_attr('sensor.noticias_titulares_nacional', 'titulares') or [] %}
  - [{{ n.titulo }}]({{ n.enlace }}) · {{ n.medio }}, {{ n.hora[-5:] }}
  {% endfor %}
```

## 🎭 Panoramas

Los eventos culturales de hoy en tu comuna, con el recinto, si son gratis y el enlace (cambia `santiago` por tu comuna en los ids):

![Eventos culturales de hoy en Santiago con recinto, si son gratis y enlace](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/panoramas-hoy.png)

```yaml
type: markdown
title: 🎭 Panoramas de hoy · Santiago
content: |
  {% set hoy = state_attr('sensor.panoramas_culturales_santiago_hoy', 'eventos') or [] %}
  {% for e in hoy[:6] %}
  - **{{ e.nombre }}** · {{ e.recinto }} · {{ 'gratis' if e.gratis else 'pago' }} · [ver]({{ e.enlace }})
  {% else %}
  Hoy no hay eventos publicados en tu comuna.
  {% endfor %}
  {% if hoy | length > 6 %}…y {{ hoy | length - 6 }} más.{% endif %}
```

Lo que viene en el Claro Arena, con enlace para comprar entradas:

![Próximos eventos del Claro Arena con fecha, hora y enlace a las entradas](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/panoramas-claro-arena.png)

```yaml
type: markdown
title: 🏟️ Claro Arena
content: |
  {% set e = state_attr('sensor.claro_arena_proximo_evento', 'eventos') or [] %}
  {% for x in e[:4] %}
  - **{{ x.fecha[8:10] }}/{{ x.fecha[5:7] }} {{ x.hora }}** · {{ x.titulo }}{% if x.entradas %} · [entradas]({{ x.entradas }}){% endif %}
  {% else %}
  Sin eventos con fecha por ahora.
  {% endfor %}
```

### Panoramas por Vamoh

Los planes destacados de Vamoh, con enlace a la ficha de cada uno en Vamoh. Requiere el enlace del calendario de Vamoh en las opciones de Navaja Chilena.

```yaml
type: markdown
title: ✨ Panoramas por Vamoh
content: |
  {% set p = state_attr('sensor.panoramas_por_vamoh_proximo_panorama', 'proximos') or [] %}
  {% for e in p[:5] %}
  - **{{ e.fecha[8:10] }}/{{ e.fecha[5:7] }}{% if e.hora %} {{ e.hora }}{% endif %}** · {{ e.titulo }}{% if e.lugar %} · {{ e.lugar }}{% endif %}{% if e.ficha %} · [ver en Vamoh]({{ e.ficha }}){% endif %}
  {% else %}
  Vamoh no tiene panoramas destacados por ahora.
  {% endfor %}

  <sub>Panoramas por <a href="https://vamoh.cl">Vamoh</a></sub>
```

## 📍 Cerca de ti

Requiere activar **«Cerca de ti»** en las opciones (elige tu teléfono y la distancia). Las tarjetas muestran algo solo cuando estás cerca.

Próxima función cuando pasas cerca de un Cinemark:

![Tarjeta que muestra el Cinemark más cercano y sus próximas funciones](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/cerca-cinemark.png)

```yaml
type: markdown
title: 🎬 Cerca de ti
content: |
  {% set e = 'binary_sensor.cerca_de_ti_cerca_de_un_cinemark' %}
  {% if is_state(e, 'on') and state_attr(e, 'proximas_funciones') %}
  **{{ state_attr(e, 'cine_mas_cercano') }}** · a {{ state_attr(e, 'distancia_m') }} m
  {% for f in state_attr(e, 'proximas_funciones')[:4] %}
  - **{{ f.hora }}** · {{ f.titulo }}{% if f.formato %} ({{ f.formato }}){% endif %}
  {% endfor %}
  {% elif is_state(e, 'on') %}
  Estás cerca de **{{ state_attr(e, 'cine_mas_cercano') }}**, pero no hay funciones para mostrar ahora.
  {% else %}
  Cuando pases cerca de un Cinemark, aquí verás la próxima función.
  {% endif %}
```

Estación con descuento hoy para tus tarjetas:

![Tarjeta que muestra la estación cercana y el descuento de hoy](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/cerca-estacion.png)

```yaml
type: markdown
title: ⛽ Cerca de ti
content: |
  {% set e = 'binary_sensor.cerca_de_ti_cerca_de_una_estacion_con_descuento' %}
  {% if is_state(e, 'on') %}
  **{{ state_attr(e, 'estacion_mas_cercana') }}** · {{ state_attr(e, 'direccion') }} · a {{ state_attr(e, 'distancia_m') }} m
  {% for d in state_attr(e, 'descuentos') %}
  - **{{ d.descuento }}** con {{ d.tarjeta }}{% if not d.confirmado %} (por confirmar){% endif %}
  {% endfor %}
  {% else %}
  Hoy hay descuento en: {{ state_attr(e, 'marcas_con_descuento_hoy') | join(', ') or 'ninguna marca' }}. Te avisaré al pasar cerca.
  {% endif %}
```

**Automatización: aviso al pasar cerca de un Cinemark** (como máximo una vez cada 3 horas y solo por la tarde):

```yaml
alias: Aviso al pasar cerca de un Cinemark
triggers:
  - trigger: state
    entity_id: binary_sensor.cerca_de_ti_cerca_de_un_cinemark
    to: "on"
conditions:
  - condition: time
    after: "12:00:00"
    before: "22:30:00"
  - condition: template
    value_template: "{{ state_attr(trigger.entity_id, 'proxima_funcion') is not none }}"
  - condition: template
    value_template: >-
      {{ this.attributes.last_triggered is none
         or (now() - this.attributes.last_triggered).total_seconds() > 10800 }}
actions:
  - action: notify.notify          # cambia por tu servicio, p. ej. notify.mobile_app_mi_celular
    data:
      title: "🎬 {{ state_attr(trigger.entity_id, 'cine_mas_cercano') }}"
      message: >-
        {% set f = state_attr(trigger.entity_id, 'proxima_funcion') %}
        Próxima función a las {{ f.hora }}: {{ f.titulo }}.
```

**Automatización: aviso al pasar cerca de una estación con descuento hoy:**

```yaml
alias: Descuento de bencina cerca
triggers:
  - trigger: state
    entity_id: binary_sensor.cerca_de_ti_cerca_de_una_estacion_con_descuento
    to: "on"
conditions:
  - condition: template
    value_template: >-
      {{ this.attributes.last_triggered is none
         or (now() - this.attributes.last_triggered).total_seconds() > 10800 }}
actions:
  - action: notify.notify
    data:
      title: "⛽ {{ state_attr(trigger.entity_id, 'estacion_mas_cercana') }} a {{ state_attr(trigger.entity_id, 'distancia_m') }} m"
      message: >-
        {% for d in state_attr(trigger.entity_id, 'descuentos') %}{{ d.descuento }} con {{ d.tarjeta }}{{ ' · ' if not loop.last }}{% endfor %}
```

**Automatización «con zona»** para un restaurante o tienda: crea una zona en *Ajustes → Áreas, etiquetas y zonas → Zonas* en ese local (radio de 50 a 100 m) y avisa al entrar si hoy tienes un descuento ahí
(cambia `Abrasas`, la zona, tu persona y la categoría del sensor):

```yaml
alias: Descuento de hoy en mi restaurante favorito
triggers:
  - trigger: zone
    entity_id: person.tu_persona
    zone: zone.restaurante_abrasas
    event: enter
conditions:
  - condition: template
    value_template: >-
      {{ (state_attr('sensor.descuentos_de_tarjetas_descuentos_de_hoy_comida', 'hoy') or [])
         | selectattr('comercio', 'search', 'Abrasas') | list | count > 0 }}
actions:
  - action: notify.notify
    data:
      title: "🍽️ Hoy tienes descuento aquí"
      message: >-
        {% set d = (state_attr('sensor.descuentos_de_tarjetas_descuentos_de_hoy_comida', 'hoy')
                    | selectattr('comercio', 'search', 'Abrasas') | list)[0] %}
        {{ d.comercio }}: {{ d.descuento }} con {{ d.tarjeta }}.
```

## 🚗 Mi vehículo

Restricción de hoy, dígitos restringidos, próxima fecha y mes de revisión técnica:

![Tarjetas con la restricción de hoy, los dígitos, la próxima fecha y el mes de revisión técnica](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/vehiculo-tarjetas.png)

*Ejemplo con fecha simulada: lunes 8 de junio de 2026, dentro de la temporada de restricción (hoy no hay restricción).*

```yaml
type: grid
title: Mi vehículo
columns: 2
square: false
cards:
  - type: tile
    entity: binary_sensor.mi_vehiculo_restriccion_vehicular_hoy
    name: Restricción hoy
  - type: tile
    entity: sensor.mi_vehiculo_digitos_con_restriccion_hoy
    name: Dígitos restringidos
  - type: tile
    entity: sensor.mi_vehiculo_proxima_restriccion
    name: Próxima restricción
  - type: tile
    entity: sensor.mi_vehiculo_mes_de_revision_tecnica
    name: Revisión técnica
```

Aviso en palabras:

![Aviso en palabras con la restricción del día y la revisión técnica](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/vehiculo-aviso.png)

*Ejemplo con fecha simulada: lunes 8 de junio de 2026, dentro de la temporada de restricción (hoy no hay restricción).*

```yaml
type: markdown
title: Mi vehículo
content: |
  {% set r = 'binary_sensor.mi_vehiculo_restriccion_vehicular_hoy' %}
  {% if is_state(r, 'on') %}
  🚫 **Hoy tienes restricción** (dígitos {{ state_attr(r, 'digitos_hoy') }}), de {{ state_attr(r, 'horario') }}.
  {% elif is_state(r, 'off') %}
  ✅ **Hoy no tienes restricción.** {{ state_attr(r, 'motivo') }}.
  {% else %}
  Sin datos de restricción para hoy.
  {% endif %}

  🔧 Revisión técnica: **{{ states('sensor.mi_vehiculo_mes_de_revision_tecnica') }}**{% if is_state('binary_sensor.mi_vehiculo_revision_tecnica_este_mes', 'on') %} (¡te toca este mes!){% endif %}
```

### 🚗 Varios vehículos

Si registraste más de un vehículo (el principal y los de *Otros vehículos*), este resumen los junta en una sola tarjeta. Ajusta la lista de nombres y de dispositivos a los tuyos:

![Resumen de tres vehículos con su restricción de hoy, próxima restricción y mes de revisión técnica](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/vehiculos-varios.png)

*Ejemplo con fecha simulada: lunes 8 de junio de 2026, dentro de la temporada de restricción.*

```yaml
type: markdown
title: 🚗 Mis vehículos
content: |
  {% set autos = {'Auto (patente …8)': 'mi_vehiculo', 'Auto (patente …3)': 'vehiculo_patente_3', 'Moto (patente …5)': 'vehiculo_patente_5'} %}
  {% for nombre, id in autos.items() %}
  **{{ nombre }}**  
  {% if is_state('binary_sensor.' ~ id ~ '_restriccion_vehicular_hoy', 'on') %}🚫 Hoy tiene restricción{% else %}✅ Hoy sin restricción{% endif %}{% if has_value('sensor.' ~ id ~ '_proxima_restriccion') %} · próxima: {{ states('sensor.' ~ id ~ '_proxima_restriccion') }}{% endif %}  
  🔧 Revisión técnica: {{ states('sensor.' ~ id ~ '_mes_de_revision_tecnica') }}{% if is_state('binary_sensor.' ~ id ~ '_revision_tecnica_este_mes', 'on') %} · **¡este mes!**{% endif %}
  {% endfor %}
```

## ☀️ Resumen del día (todo junto)

![Resumen del día con indicadores, efeméride y los tres titulares principales](https://raw.githubusercontent.com/Ctuna89/navaja-chilena-HA/main/docs/img/resumen-del-dia.png)

```yaml
type: markdown
title: Buen día 🇨🇱
content: |
  **{{ states('sensor.santoral_santo_del_dia') }}**

  💵 UF ${{ '{:,.0f}'.format(states('sensor.indicadores_economicos_uf') | float(0)) | replace(',', '.') }}  
  💲 Dólar ${{ '{:,.0f}'.format(states('sensor.indicadores_economicos_dolar_observado') | float(0)) | replace(',', '.') }}  
  📈 IPSA {{ '{:,.0f}'.format(states('sensor.bolsa_de_santiago_ipsa') | float(0)) | replace(',', '.') }} ({{ state_attr('sensor.bolsa_de_santiago_ipsa', 'variacion_pct') }} %)  
  🇨🇱 {{ states('sensor.efemerides_chilenas_efemerides_de_hoy') }}

  {% for n in (state_attr('sensor.noticias_titulares_nacional', 'titulares') or [])[:3] %}
  📰 [{{ n.titulo }}]({{ n.enlace }})  
  {% endfor %}
```

## 🌅 Resumen de la mañana en tu celular
Una notificación diaria que junta lo que ya tienes en Navaja Chilena: el santo, UF y dólar, si hoy tienes restricción vehicular, los descuentos en bencina de tus
tarjetas, el próximo feriado y tres titulares. Solo aparece lo que corresponde: si hoy no tienes restricción ni descuentos, esas líneas no salen.

```yaml
alias: Resumen de la mañana
triggers:
  - trigger: time
    at: "07:30:00"
actions:
  - action: notify.notify          # cambia por tu servicio, p. ej. notify.mobile_app_mi_celular
    data:
      title: "🇨🇱 Buen día{{ ' · ' ~ states('sensor.santoral_santo_del_dia') if has_value('sensor.santoral_santo_del_dia') }}"
      message: |
        {% if has_value('sensor.indicadores_economicos_uf') and has_value('sensor.indicadores_economicos_dolar_observado') -%}
        💵 UF ${{ '{:,.0f}'.format(states('sensor.indicadores_economicos_uf') | float(0)) | replace(',', '.') }} · Dólar ${{ '{:,.0f}'.format(states('sensor.indicadores_economicos_dolar_observado') | float(0)) | replace(',', '.') }}
        {% endif -%}
        {% if is_state('binary_sensor.mi_vehiculo_restriccion_vehicular_hoy', 'on') -%}
        🚗 Hoy tienes restricción vehicular ({{ state_attr('binary_sensor.mi_vehiculo_restriccion_vehicular_hoy', 'horario') }})
        {% endif -%}
        {% if states('sensor.combustibles_descuentos_en_bencina_hoy') | int(0) > 0 -%}
        ⛽ Bencina con descuento hoy: {% for d in state_attr('sensor.combustibles_descuentos_en_bencina_hoy', 'hoy') %}{{ d.tarjeta }} en {{ d.estaciones | join('/') }} ({{ d.descuento }}){{ ', ' if not loop.last }}{% endfor %}
        {% endif -%}
        {% if state_attr('sensor.feriados_chile_proximo_feriado', 'es_hoy') -%}
        🎉 Hoy es feriado: {{ state_attr('sensor.feriados_chile_proximo_feriado', 'nombre') }}
        {% elif has_value('sensor.feriados_chile_proximo_feriado') -%}
        📅 Próximo feriado: {{ state_attr('sensor.feriados_chile_proximo_feriado', 'nombre') }} (en {{ states('sensor.feriados_chile_dias_para_el_proximo_feriado') }} días)
        {% endif -%}
        {% for n in (state_attr('sensor.noticias_titulares_nacional', 'titulares') or [])[:3] -%}
        📰 {{ n.titulo }}
        {% endfor -%}
```

Cada línea aparece solo si ese módulo está activado: el resumen se arma con lo que tú elegiste. Los nombres de las entidades son los de tu instalación; si
cambiaste alguno, ajústalo en la plantilla.

[← Volver al README](../README.md)
