# Registro de cambios

Las versiones se publican en bloque: los cambios nuevos se anotan en **Sin publicar** y se agrupan en una versión cuando se decide.
El número de versión vive en `custom_components/navaja_chilena/manifest.json`; al cambiarlo y fusionar a `main`, un workflow publica la release.

## Sin publicar

- **Cinépolis**: la cartelera de hoy de tu cine de Cinépolis (escribes su nombre, p. ej. «La Reina») con afiche, películas, funciones, formato, idioma y sala, en la hora del cine. Cada 45 minutos, con el último resultado conservado si el servicio falla y sin confundir una falla con «sin funciones». Funciona con los servicios del propio sitio de Cinépolis, con su autorización.
## 3.2.0

Una versión con tres módulos nuevos: cargadores eléctricos, «Cerca de ti» y Panoramas por Vamoh.

- **Cargadores eléctricos**: el cargador público libre más cercano a tu casa, cuántos puntos libres hay, el más barato por kWh y, si agregas el sensor de batería de tu auto, «Conviene cargar» cuando la batería está baja y hay un cargador libre compatible. Eliges los conectores de tu auto, el radio y la potencia mínima. Datos del mapa de cargadores públicos del Ministerio de Energía (registro SEC), consultados cada 15 minutos; un punto sin novedades hace más de 2 días no se cuenta como libre. Con «Cerca de ti» también avisa al pasar cerca de un cargador libre. Incluye tarjetas y automatizaciones de ejemplo.
- **Cerca de ti** (opcional): eliges tu teléfono y una distancia, y dos sensores se encienden cuando pasas cerca de un Cinemark (con la próxima función) o de una estación de servicio con descuento hoy para tus tarjetas. La ubicación no sale de tu Home Assistant. Incluye tarjetas y automatizaciones de ejemplo, también «con zona» para restaurantes.
- **Panoramas por Vamoh**: eliges tu región y una categoría y lee los panoramas de las páginas públicas de listado de Vamoh, con afiche, precio y la ficha de cada evento en Vamoh. Una consulta por hora, ordenados por fecha, con aviso de resultados parciales, sin llamar «gratis» a lo que no informa precio y conservando el último resultado bueno si Vamoh falla. Como alternativa se puede leer su calendario (.ics) o tu enlace personal, que nunca se muestra ni se registra. Atribución visible.

## 3.1.0

- **Panoramas**: los eventos culturales de hoy y el próximo en tu comuna (Chile Cultura, con opción de solo gratis) y el próximo evento del estadio Claro Arena. Cada fuente se activa por separado.
- **Varios vehículos**: además del vehículo principal puedes registrar hasta 4 más (`3, 5:moto`), cada uno con su restricción, próxima restricción y mes de revisión técnica en su propio dispositivo. El vehículo principal conserva sus entidades de siempre.
- **Documentación**: las tarjetas de ejemplo pasaron a su propia página (`docs/tarjetas.md`) y el README quedó más corto; la tabla de la portada incluye la Red Regional y el resumen de la mañana.

## 3.0.0

Una versión que reúne todo lo nuevo desde la 2.11: noticias, el resumen de la mañana y el tren de Valparaíso.

- **Resumen de la mañana**: ejemplo de automatización que envía a tu celular el santo, UF y dólar, tu restricción vehicular, los descuentos en bencina de hoy, el próximo feriado y tres titulares; solo incluye lo que tienes activado. La tarjeta «Resumen del día» suma los tres titulares principales.
- **Noticias por tema**: titulares de La Tercera y Cooperativa separados por tema (nacional, política, mundo, economía, deportes, tecnología, sociedad, cultura y servicios), con enlace a cada nota. Se actualiza cada 30 minutos.
- **Tren Limache–Puerto** (aporte de claudiojara): próximos trenes de EFE Valparaíso entre tus estaciones (`Villa Alemana > Puerto`, con la opción del sentido inverso). Un sensor por trayecto con el texto de EFE, la hora estimada, la lista de trenes y si cada uno llega a tu destino (hacia Limache también hay trenes cortos «Hasta Sargento Aldea»). Usa la API de «Próximos trenes» de la app de EFE, no documentada para terceros.

## 2.11.0

- **Paraderos de la Red Regional**: llegadas en vivo y alertas del servicio en las ciudades fuera de Santiago (Temuco, Talca, Concepción, Valparaíso, La Serena…). Servicio de TransApp/DTPR, no oficial. Gracias a edwinroket/red-regional-api y frabarz/hass-red-regional por la referencia de la API.
- **Descuentos en bencina**: con tus tarjetas marcadas, el sensor «Descuentos en bencina hoy» muestra qué estaciones tienen descuento hoy y el próximo día con descuento, a partir de un calendario mensual del repositorio (`data/bencina.json`) con la fuente de cada fila. Si el calendario no es del mes en curso, no se muestra como vigente.

## 2.10.0

- **Fútbol**: próximos partidos, resultados y posición de tu equipo de la Primera División; tabla y fechas de la liga; y La Roja (ESPN). Se consulta cada 3 horas y cada 5 minutos con un partido en juego.

- **Descuentos de tus tarjetas**: eliges tus tarjetas y las categorías que te interesan (combustibles, comida, salud, etc.) y ves los descuentos que aplican hoy (N Beneficios). Se descarga cada 7 días y el día 1 de cada mes, y se guarda para no consultar de más.

## 2.9.0

- **Combustibles**: precio más bajo de bencina (93, 95, 97) y diésel cerca de tu casa, con marca, dirección y distancia (Bencina en Línea, CNE). Solo precios recientes (por defecto 14 días).

## 2.8.0

- **Mi vehículo**: restricción vehicular (Región Metropolitana, Resolución Exenta N° 1698/2026) y mes de revisión técnica según el último dígito de la patente.
- Los festivos se obtienen solos cuando los necesitan el Metro o el vehículo.
- Corrección: la actualización de medianoche (santoral y vehículo) ahora corre correctamente en Home Assistant.

## 2.7.0

- **Cartelera**: póster de las películas (imagen de la entidad y atributo `poster`).

## 2.6.0

- Metro: los estados se muestran traducidos («Operativa», «Con problemas», «Cerrada»).
- README con capturas reales de cada tarjeta de ejemplo.

## 2.5.0

- **Efemérides**: se suma efemerides.cl (días significativos de Chile) y el sensor «Próximo día significativo».

## 2.4.0

- **Efemérides** chilenas de hoy desde Wikipedia.

## 2.3.0

- **Cartelera de cine** (Cinemark): tu cine favorito o el más cercano a tu casa.

## 2.2.0

- **IPSA** con su variación diaria y **santo del día**.

## 2.1.0

- Fuentes verificadas con datos reales: Metro, sismos (CSN y USGS), feriados, respaldo de indicadores, criptomonedas.

## 2.0.1

- Correcciones de robustez: Metro sin estado inventado, validación de paraderos y módulos independientes entre sí.

## 2.0.0

- Reescritura completa de la integración: indicadores económicos, Metro, paraderos, sismos, feriados, calidad del aire y UV, farmacias de turno.
