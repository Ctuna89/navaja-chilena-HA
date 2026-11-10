# Calendario de descuentos en bencina

`bencina.json` lo lee la integración (módulo **Descuentos de tus tarjetas**, sensor «Descuentos en bencina hoy»). Se renueva **una vez al mes** con un pull request.
Si `vigencia` no es el mes en curso, el sensor queda sin valor y lo explica: nunca se muestran descuentos de un mes anterior como vigentes.

## Formato

```json
{ "vigencia": "AAAA-MM", "actualizado": "AAAA-MM-DD", "descuentos": [ { ... } ] }
```

Cada descuento:

| Campo | Obligatorio | Descripción |
|---|---|---|
| `dias` | sí | Días de la semana en que aplica: 1 = lunes … 7 = domingo |
| `estaciones` | no | `["Copec"]`, `["Shell"]`, `["Aramco"]`, etc. |
| `tarjeta` | sí | Clave de la tarjeta: `bancochile`, `bancoestado`, `bci`, `bice`, `cencosud`, `cmr`, `copec`, `itau`, `lider`, `mach`, `mercadopago`, `ripley`, `santander`, `scotiabank`, `security`, `tenpo` |
| `tarjeta_nombre` | no | Nombre para mostrar (ej. «Itaú Legend», «Rutpay BancoEstado») |
| `monto` | sí | Texto: `$100/L`, `7% de cashback`, `desde $50/L` |
| `ahorro_clp_litro` | no | Número, si el descuento es fijo por litro |
| `porcentaje` | no | Número, si es un porcentaje |
| `detalle` | no | Condiciones que cambian la decisión: crédito/débito, canal (app, QR, código), tope de litros o de monto, usos al mes, activaciones previas |
| `confirmado` | sí | `true` solo si lo confirma una fuente oficial **del mes**; si solo hay prensa de meses anteriores, `false` |
| `fuente` | sí | URL de donde sale el dato |

## Cómo actualizarlo cada mes

1. **Investigar** los descuentos del mes y año en curso. Consultas útiles: `descuentos bencina <mes> <año>`, `Copec promociones <mes> <año>`,
   `Shell descuentos <mes> <año> App Shell`, `Aramco descuentos <mes> <año>`, `<banco> descuento combustible <mes> <año>`.
2. **Fuentes oficiales primero** (lee las páginas con `curl -sS -L`; las páginas de Copec y la prensa se cargan sin JavaScript): [Copec – Promociones](https://ww2.copec.cl/personas/promociones), la página de Shell/Enex y de Aramco, y las páginas de beneficios de cada banco o tarjeta
   (Rutpay de BancoEstado, Banco de Chile, BCI, Itaú, Tenpo, Santander, Scotiabank, etc.).
3. **Contrastar** con al menos dos guías de prensa del mismo mes (La Tercera, BioBioChile, Chócale, Autofact, Meganoticias, Encancha).
4. **Verificar que cada dato sea del mes actual**: muchos resultados son de meses o años anteriores. Si un convenio solo aparece en meses anteriores,
   se deja fuera o se incluye con `"confirmado": false` y se explica en `detalle`.
5. **Incluir solo lo que se pudo respaldar**, con su `fuente`. Un descuento sin respaldo no se agrega.
6. Actualizar `vigencia` y `actualizado`.
7. **Validar**: `python data/validar.py --mes-actual` debe terminar con `OK` (formato, tarjetas conocidas, fuentes https, montos plausibles, mes en curso).
8. **Publicar** sin cambiar la versión de la integración (el archivo se lee desde `main`): un pull request que solo cambie `data/bencina.json`. Si la rama se llama `datos/bencina-AAAA-MM`, el workflow *Datos de bencina* lo valida y lo fusiona solo; la tarea mensual lo abre desde su rama de trabajo y lo fusiona con las herramientas de GitHub.

Colaboradores: un pull request desde una rama `datos/bencina-*` que solo cambie este archivo se valida y fusiona automáticamente; cualquier otro cambio sigue el flujo normal.
