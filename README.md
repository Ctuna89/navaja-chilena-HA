# Navaja Chilena 🇨🇱

Integración para Home Assistant (instalable vía HACS) con datos útiles de Chile.

## Qué incluye

| Módulo | Datos | Fuente | Actualización |
|---|---|---|---|
| Indicadores económicos | UF, dólar, euro, UTM, IPC, IVP, Imacec, TPM, cobre, desempleo, bitcoin | [mindicador.cl](https://mindicador.cl) | 1 h |
| Metro de Santiago | Estado por línea (`operativa`, `con_problemas` o `cerrada` fuera de horario) y por estación | [api.xor.cl](https://api.xor.cl) | 2 min |
| Paraderos | Minutos al próximo bus y detalle por recorrido | [api.xor.cl](https://api.xor.cl) (Red Movilidad) | 1 min |
| Sismos | Último sismo en Chile: magnitud, profundidad, referencia y coordenadas (sirve para la tarjeta de mapa) | [USGS](https://earthquake.usgs.gov/fdsnws/event/1/) (M ≥ 2.5; el CSN no ofrece API pública) | 5 min |
| Feriados | Próximo feriado, días que faltan, si es irrenunciable | apis.digital.gob.cl (respaldo: boostr.cl) | 1 h |
| Calidad del aire y UV | PM2.5, PM10, US AQI e índice UV en la ubicación de Home Assistant | [Open-Meteo](https://open-meteo.com) | 30 min |
| Farmacias de turno | Cantidad y detalle de farmacias de turno en tu comuna | MINSAL (Farmanet) | 6 h |

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
  **Si la fuente falla o no se entiende su respuesta, el sensor queda «no disponible»; nunca se asume «operativa».**
- **Paraderos**: `sensor.paraderos_red_movilidad_paradero_<código>`: minutos al próximo bus; atributos `estado` y `recorridos`.
  Al configurar, se comprueba que el código exista.
- **Sismos**: `sensor.sismos_chile_ultimo_sismo`: magnitud; atributos `latitude`, `longitude`, `profundidad_km`, `referencia`, `fecha`.
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
  - entity: sensor.sismos_chile_ultimo_sismo
    label_mode: state
default_zoom: 6
```

## Desarrollo

```bash
pip install pytest-homeassistant-custom-component
pytest
```

Metro y paraderos usan un servicio comunitario no oficial (api.xor.cl); feriados y farmacias, servicios públicos sin
contrato de estabilidad. Los parsers se prueban con respuestas simuladas y la integración se prueba dentro de
Home Assistant, pero el formato real de estas fuentes puede cambiar.

Ideas descartadas por ahora: precios de combustibles (la API de la CNE requiere inicio de sesión)
y calidad del aire SINCA (sin API documentada; Open-Meteo cubre PM2.5/PM10 sin claves).

Licencia: ver [LICENSE](LICENSE).
