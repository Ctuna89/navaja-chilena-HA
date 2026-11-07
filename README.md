# Navaja Chilena 🇨🇱

Integración para Home Assistant (instalable vía HACS) con datos útiles de Chile.

## Qué incluye

| Módulo | Datos | Fuente | Actualización |
|---|---|---|---|
| Indicadores económicos | UF, dólar, euro, UTM, IPC, IVP, Imacec, TPM, cobre, desempleo, bitcoin | [mindicador.cl](https://mindicador.cl) | 1 h |
| Metro de Santiago | Estado operacional por línea y estaciones con problemas | [api.xor.cl](https://api.xor.cl) | 2 min |
| Paraderos | Minutos al próximo bus y detalle por recorrido | [api.xor.cl](https://api.xor.cl) (Red Movilidad) | 1 min |
| Sismos | Último sismo: magnitud, profundidad, referencia y coordenadas (sirve para la tarjeta de mapa) | Centro Sismológico Nacional vía api.gael.cl | 5 min |
| Feriados | Próximo feriado, días que faltan, si es irrenunciable | apis.digital.gob.cl (respaldo: boostr.cl) | 1 h |
| Calidad del aire y UV | PM2.5, PM10, US AQI e índice UV en la ubicación de Home Assistant | [Open-Meteo](https://open-meteo.com) | 30 min |
| Farmacias de turno | Cantidad y detalle de farmacias de turno en tu comuna | MINSAL (Farmanet) | 6 h |

No requiere claves de API.

## Instalación

1. HACS → ⋮ → *Repositorios personalizados* → añade este repositorio como **Integración**.
2. Instala *Navaja Chilena* y reinicia Home Assistant.
3. *Ajustes → Dispositivos y servicios → Añadir integración → Navaja Chilena*.

## Configuración

En el asistente eliges los indicadores, si quieres el Metro y los códigos de paradero
separados por coma (ej. `PC615, PA433`). Todo se puede cambiar después en *Configurar*.

## Entidades

- `sensor.<indicador>`: valor numérico; atributo `fecha`.
- `sensor.<línea de metro>`: `operativa` / `con_problemas`; atributos `mensaje` y `estaciones_con_problemas`.
- `sensor.paradero_<código>`: minutos al próximo bus; atributos `estado` y `recorridos`.
- `sensor.ultimo_sismo`: magnitud; atributos `latitude`, `longitude`, `profundidad_km`, `referencia`, `fecha`.
- `sensor.proximo_feriado` (fecha) y `sensor.dias_para_el_proximo_feriado`.
- `sensor.pm2_5`, `sensor.pm10`, `sensor.indice_de_calidad_del_aire_us_aqi`, `sensor.indice_uv`.
- `sensor.farmacias_de_turno_<comuna>`: cantidad; atributo `farmacias` (hasta 20, con dirección, teléfono y coordenadas).

### Ejemplo: último sismo en un mapa

```yaml
type: map
entities:
  - entity: sensor.ultimo_sismo
    label_mode: state
default_zoom: 6
```

## Desarrollo

```bash
pip install pytest aiohttp
pytest tests
```

Metro, paraderos y sismos usan servicios comunitarios no oficiales, y feriados/farmacias usan
servicios públicos sin contrato de estabilidad; su formato podría cambiar. Los parsers en `api.py`
son tolerantes y están probados con respuestas simuladas, pero **no se han contrastado contra los
servicios reales**. Si un sensor aparece como no disponible, revisa el registro de Home Assistant.

Ideas descartadas por ahora: precios de combustibles (la API de la CNE requiere inicio de sesión)
y calidad del aire SINCA (sin API documentada; Open-Meteo cubre PM2.5/PM10 sin claves).

Licencia: ver [LICENSE](LICENSE).
