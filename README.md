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
- **Criptomonedas**: `sensor.criptomonedas_buda_bitcoin` y `..._ethereum`: precio en CLP; atributos `variacion_24h_pct`, `variacion_7d_pct`, `volumen_24h`.
- **Feriados**: `sensor.feriados_chile_proximo_feriado` (fecha) y `sensor.feriados_chile_dias_para_el_proximo_feriado`.
- **Aire y UV**: `sensor.calidad_del_aire_y_uv_pm2_5`, `..._pm10`, `..._indice_de_calidad_del_aire_us_aqi`, `..._indice_uv`.
- **Farmacias**: `sensor.farmacias_de_turno_<comuna>`: cantidad; atributo `farmacias` (hasta 20, con dirección, teléfono y coordenadas).

Cada módulo funciona por separado: si una fuente cae, solo sus sensores quedan «no disponibles» y se reintenta con
espera creciente (hasta 30 min), con un único aviso en el registro.

## Actualizar desde la versión 1.x

La versión anterior usaba otros nombres de entidad y otra configuración. Tras actualizar en HACS (*⋮ → Volver a descargar*)
y reiniciar, lo más limpio es **eliminar la integración en Dispositivos y servicios y volver a añadirla**.
Las tarjetas que usaban `sensor.navaja_*` o `sensor.metro_l1` deberán apuntar a los ids nuevos.

### Ejemplo: último sismo en un mapa

```yaml
type: map
entities:
  - entity: sensor.sismos_chile_ultimo_sismo_con_coordenadas_usgs
    label_mode: state
default_zoom: 6
```

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

Las respuestas reales están guardadas en `tests/fixtures` y las pruebas las usan. Son servicios comunitarios o sin contrato de estabilidad: su formato puede cambiar.

Fuente de ideas: [listado de APIs públicas de Chile](https://github.com/juanbrujo/listado-apis-publicas-en-chile).

Licencia: ver [LICENSE](LICENSE).
