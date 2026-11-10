# Registro de cambios

Las versiones se publican en bloque: los cambios nuevos se anotan en **Sin publicar** y se agrupan en una versión cuando se decide.
El número de versión vive en `custom_components/navaja_chilena/manifest.json`; al cambiarlo y fusionar a `main`, un workflow publica la release.

## Sin publicar

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
