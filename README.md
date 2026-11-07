# Navaja Chilena 🇨🇱

Integración para Home Assistant (instalable vía HACS) con datos útiles de Chile.

## Qué incluye

| Módulo | Datos | Fuente | Actualización |
|---|---|---|---|
| Indicadores económicos | UF, dólar, euro, UTM, IPC, IVP, Imacec, TPM, cobre, desempleo, bitcoin | [mindicador.cl](https://mindicador.cl) | 1 h |
| Metro de Santiago | Estado operacional por línea y estaciones con problemas | [api.xor.cl](https://api.xor.cl) | 2 min |
| Paraderos | Minutos al próximo bus y detalle por recorrido | [api.xor.cl](https://api.xor.cl) (Red Movilidad) | 1 min |

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

## Desarrollo

```bash
pip install pytest aiohttp
pytest tests
```

Las APIs de Metro y paraderos son servicios comunitarios no oficiales; su formato podría cambiar.
Los parsers en `api.py` son tolerantes, pero esas dos fuentes aún no se han probado contra el servicio real.

Licencia: ver [LICENSE](LICENSE).
