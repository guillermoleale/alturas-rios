# Alturas de los ríos de la Cuenca del Plata

Dashboard con la altura diaria de 81 escalas de Prefectura Naval en los ríos Paraná, Paraguay, Uruguay e Iguazú, el Delta y el Río de la Plata, con sus niveles de alerta, evacuación y aguas bajas.

**Ver el dashboard:** https://guillermoleale.github.io/alturas-rios/

Proyecto personal, no oficial. Los datos son preliminares y no están validados. Para alertas, consultá al [INA](https://www.ina.gob.ar/alerta/index.php) y a [Prefectura Naval](https://contenidosweb.prefecturanaval.gob.ar/alturas/).

## Datos

- Fuente: API pública del [Sistema de Alerta Hidrológico del INA](https://alerta.ina.gob.ar/pub/datos/), red «escalas Prefectura Nacional».
- Una lectura por escala y por día desde el 1 de julio de 2026. Cuando hay varias lecturas en un día se usa la de las 0 h, que es la lectura diaria de Prefectura. San Fernando y Buenos Aires publican lecturas horarias y se usa la última del día.
- Se descartan errores de carga evidentes: un cero cuando el día anterior superaba 0,5 m, o un valor más de tres veces mayor que el del día anterior. No se aplica en el Delta y el Río de la Plata, donde la marea y el viento producen saltos reales. Los descartes quedan registrados en `site/data/meta.json`.
- Descarga: [`site/data/alturas.csv`](site/data/alturas.csv).
- Mapa: [Leaflet](https://leafletjs.com/) con mapas base de © [colaboradores de OpenStreetMap](https://www.openstreetmap.org/copyright).
- Pronósticos de altura: último pronóstico publicado por el INA para cada escala que lo tenga (Paraná de Corrientes a Rosario, Delta, San Fernando y Paraguay), con su rango cuando el modelo lo informa.
- Contexto histórico: percentiles 10, 50 y 90 de la altura media mensual de cada escala desde 1970 (INA). «Para la época» compara la altura de hoy con ese rango. Se recalcula una vez por mes.
- Lluvia y viento: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0). Lluvia diaria de la última semana y pronóstico a 7 días en nueve puntos de la cuenca, y viento horario frente a Buenos Aires. Se marca como posible sudestada el viento del sector este a sur de 30 km/h o más durante al menos 6 horas, un criterio orientativo propio.
- Caudales: caudal diario simulado y pronóstico a 30 días del modelo GloFAS v4, del Servicio de Gestión de Emergencias de Copernicus, vía la [Flood API de Open-Meteo](https://open-meteo.com/en/docs/flood-api) (CC BY 4.0), en ocho puntos de la cuenca. Es un dato secundario: el modelo no usa las lecturas de las escalas y un caudal no equivale a una altura. Se compara con el rango habitual del mismo modelo entre 2001 y 2020.
- Capas del mapa: imagen satelital GOES-East GeoColor y lluvia estimada IMERG de [NASA GIBS](https://earthdata.nasa.gov/gibs).

## Cómo se actualiza

Un workflow de GitHub Actions corre `scripts/actualizar.py` y `scripts/extras.py` todos los días a las 12:50 y a las 19:50 (hora de Argentina). Baja los últimos días de cada escala, actualiza los archivos de `site/data/` y publica el sitio en GitHub Pages. Al publicar, `scripts/og.py` saca con Playwright una captura nueva para la imagen de vista previa. También se puede correr a mano desde la pestaña Actions.

Hecho por Guillermo Leale con Claude.
