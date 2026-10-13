# Alturas de los ríos de la Cuenca del Plata

Dashboard con la altura diaria de 81 escalas de Prefectura Naval en los ríos Paraná, Paraguay, Uruguay e Iguazú, el Delta y el Río de la Plata, con sus niveles de alerta, evacuación y aguas bajas.

**Ver el dashboard:** https://guillermoleale.github.io/alturas-rios/

Proyecto personal, no oficial. Los datos son preliminares y no están validados. Para alertas, consultá al [INA](https://www.ina.gob.ar/alerta/index.php) y a [Prefectura Naval](https://contenidosweb.prefecturanaval.gob.ar/alturas/).

## Datos

- Fuente: API pública del [Sistema de Alerta Hidrológico del INA](https://alerta.ina.gob.ar/pub/datos/), red «escalas Prefectura Nacional».
- Una lectura por escala y por día desde el 1 de julio de 2026. Cuando hay varias lecturas en un día se usa la de las 0 h, que es la lectura diaria de Prefectura. San Fernando y Buenos Aires publican lecturas horarias y se usa la última del día.
- Se descartan errores de carga evidentes: un cero cuando el día anterior superaba 0,5 m, o un valor más de tres veces mayor que el del día anterior. No se aplica en el Delta y el Río de la Plata, donde la marea y el viento producen saltos reales. Los descartes quedan registrados en `site/data/meta.json`.
- Descarga: [`site/data/alturas.csv`](site/data/alturas.csv).
- Mapa: [Leaflet](https://leafletjs.com/) con mapas base de © [OpenStreetMap](https://www.openstreetmap.org/copyright) y © [CARTO](https://carto.com/attributions).

## Cómo se actualiza

Un workflow de GitHub Actions corre `scripts/actualizar.py` todos los días a las 12:50 y a las 19:50 (hora de Argentina). Baja los últimos días de cada escala, actualiza los archivos de `site/data/` y publica el sitio en GitHub Pages. También se puede correr a mano desde la pestaña Actions.

Hecho por Guillermo Leale con Claude.
