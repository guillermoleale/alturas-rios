# CLAUDE.md: alturas-rios

Contexto para seguir trabajando en este repo con Claude Code. Leelo entero antes de cambiar algo.

## Qué es

Dashboard público, estático, con la altura diaria de 81 escalas de Prefectura Naval en la Cuenca del Plata (Paraná, Paraguay, Uruguay, Iguazú, Delta y Río de la Plata). Muestra estados frente a los niveles de alerta, evacuación y aguas bajas, la evolución de cada escala, los pronósticos de altura del INA, el rango habitual por mes, la lluvia en la cuenca, el viento en el Río de la Plata y un mapa.

- Sitio: https://guillermoleale.github.io/alturas-rios/
- Repo: github.com/guillermoleale/alturas-rios (público). Dueño: Guillermo Leale.
- Proyecto personal y no oficial. Se difunde en LinkedIn. El aviso de "no oficial, datos preliminares" en el encabezado debe quedar siempre visible.
- Nació como un artifact de tipo Dashboard en claude.ai y se portó a sitio estático para que se pueda ver sin cuenta. De ahí viene el objeto `dash` (ver más abajo).

## Estructura

```
site/                 lo que se publica en GitHub Pages
  index.html          toda la página: estilos, HTML y scripts (unas 1250 líneas)
  assets/dash.js      reemplazo mínimo del objeto `dash` del artifact original
  assets/og.png       imagen de vista previa para LinkedIn (estática, del 13/10/2026)
  data/               JSON y CSV que generan los scripts; el workflow los commitea
scripts/
  actualizar.py       alturas diarias de cada escala (INA) → alturas.json, alturas.csv, meta.json
  extras.py           pronósticos, climatología, lluvia, viento y capas de NASA (partes independientes)
.github/workflows/actualizar.yml
README.md             explicación pública del proyecto y de las fuentes
```

Python sin dependencias externas (solo biblioteca estándar). No hay build: el HTML usa d3 7.9.0 y Leaflet 1.9.4 desde cdnjs, y fuentes Inter y Source Serif 4 de Google Fonts.

## Datos (site/data)

| Archivo | Lo genera | Contenido |
|---|---|---|
| estaciones.json | a mano (estático) | 81 escalas: sitecode, nombre, tramo, rio, provincia, orden (aguas arriba → abajo), alerta, evacuacion, aguas_bajas, lat, lon |
| alturas.json | actualizar.py | `[{sitecode, fecha "YYYY-MM-DD", altura}]`, una por escala y día desde 2026-07-01 |
| alturas.csv | actualizar.py | lo mismo con nombre, tramo y niveles, para descarga |
| meta.json | actualizar.py | actualizado, hasta, lecturas, correcciones, descartes, fallas_ultima_corrida |
| pronosticos.json | extras.py | `{generado, escalas: {sitecode: {emitido, modelo, calibracion, puntos: [{t, v, lo?, hi?}]}}}` |
| climatologia.json | extras.py | `{generado, escalas: {sitecode: {desde, hasta, meses: {"1".."12": [p10, p50, p90, n]}}}}` |
| meteo.json | extras.py | lluvia diaria (7 días atrás y 7 adelante) en 9 puntos; viento horario 4 días; períodos de "sudestada" |
| capas.json | extras.py | capas NASA GIBS para Leaflet: id, nombre, url con {z}/{y}/{x}, maxNativeZoom, opacidad |

- `tramo` agrupa en: Alto Paraná e Iguazú, Paraná medio e inferior, Delta y Río de la Plata, Paraguay, Uruguay.
- estaciones.json no se actualiza solo. Los niveles vienen del INA (`estaciones&redId=10`). Si cambian, hay que regenerarlo a mano conservando `tramo`, `rio` (nombre amigable) y `orden`.
- Se excluyeron a propósito las series de embalses y virtuales de la red 10: Yacyretá afluente/efluente (87, 88), Aporte/Erogado Salto Grande (89, 90), Confluencia (93), Brazo Largo (97), Virtuani (98) y Federación Embalse (5430).

## Fuentes y sus mañas

### INA, API pública (https://alerta.ina.gob.ar/pub/datos/)

- **Los parámetros van con `&` pegado al endpoint, no con `?`**: `https://alerta.ina.gob.ar/pub/datos/datos&timeStart=...&siteCode=34&varId=2&format=json`. Con `?` ignora los filtros (por ejemplo `estaciones?redId=10` devuelve todas las redes).
- `datos`: un solo `siteCode` por llamada (con lista da "Argumento siteCode erróneo"). Respuesta `{requestHeader, responseHeader, data: [{obs_id, timestart "YYYY-MM-DDTHH:MM:SS", timeend, valor, timeupdate}]}`. Sin datos devuelve un JSON con "No se encontraron resultados".
- `datosDia` con varias escalas da error de base de datos ("syntax error at or near AND"). No usarlo.
- Variables útiles: varId 2 altura hidrométrica (procId 1 medición, 4 simulado), 33 media mensual, 39 media diaria. Red 10 = "escalas Prefectura Nacional" (tabla alturas_prefe). Rosario tiene altura diaria desde 1884 y media mensual desde 1970.
- Pronósticos: `seriesProno&varId=2&all=false&format=json` lista el último pronóstico por serie y calibración (`sitecode, seriesid, calid, cal_name, cal_model, forecastdate, corid`). `datosProno&siteCode=S&varId=2&calId=C&corId=R&timeStart=..&timeEnd=..` trae los valores (`data: [{prono_id, timestart, timeend, valor}]`).
  - tabprono_central (calId 289): Corrientes, Barranqueras, Goya, Reconquista, La Paz, Paraná, Santa Fe, Rosario. Semanal (el último visto es del 9/10/2026), 3 valores por fecha que se toman como mínimo, central y máximo.
  - tabprono_paraguay (312): Pilcomayo, Formosa. Diario, con rango.
  - Delta: 288_ajuste_salidas (489) para San Nicolás, Ramallo y Campana; regre_sfer (432) para San Fernando. Horarios, unos 4 días.
  - Preferencia de calibración en `PREFERENCIA_CAL` de extras.py. Se descartan pronósticos emitidos hace más de 10 días.
- Licencia: argentina.gob.ar licencia sus contenidos CC BY 4.0 salvo indicación en contrario. La API no tiene términos propios. El INA aclara que los datos en tiempo real no están consistidos ni validados. Citar siempre la fuente.
- Los datos crudos traen errores de carga. Casos vistos: Empedrado (21) con lecturas de las 9 h en 0 o en 12 m entre el 22/9 y el 2/10/2026, y Libertador (12) con 78,91 m el 22/8/2026. Ver reglas abajo.

### Prefectura Naval

La página de alturas (contenidosweb.prefecturanaval.gob.ar/alturas/) bloquea el acceso automatizado por robots.txt. **No scrapearla.** Los mismos datos llegan por el INA (red 10). Se usa solo como link para el público.

### Open-Meteo (https://open-meteo.com)

- Sin clave para uso no comercial, menos de 10.000 llamadas por día. Datos CC BY 4.0: mantener la atribución en la página.
- Con varias coordenadas en una llamada devuelve una lista de objetos.
- La herramienta WebFetch de Claude no puede leer api.open-meteo.com (robots), pero desde scripts o desde GitHub Actions funciona sin problema.
- Flood API (GloFAS, caudales a meses vista) disponible en https://flood-api.open-meteo.com/v1/flood. Todavía no se usa.

### NASA GIBS

- extras.py lee https://gibs.earthdata.nasa.gov/wmts/epsg3857/nrt/1.0.0/WMTSCapabilities.xml y arma la URL de cada capa: saca `{Time}` (sin fecha devuelve la imagen más reciente) y reemplaza TileMatrixSet, z, y, x.
- Capas usadas: `GOES-East_ABI_GeoColor_v0_NRT` (GoogleMapsCompatible_Level7, png) e `IMERG_Precipitation_Rate_30min_v7_NRT` (Level6, png). IMERG solo pinta donde llueve y llega con algunas horas de demora.
- Que las imágenes se vean bien en el sitio no se verificó a ojo. Revisarlo en el navegador.

### Mapa base

OpenStreetMap estándar (tile.openstreetmap.org) con atribución. **CARTO ya no sirve sin clave de API** (devuelve mosaicos con la marca "API KEY REQUIRED"). Para que no le gane a los puntos, la capa base lleva `className: 'base-osm'` y un filtro CSS (menos saturación; invertida en modo oscuro). El filtro va solo en esa capa, no en todo el panel de mosaicos, para no invertir las capas de NASA.

## Reglas de datos (actualizar.py)

- Una lectura por día: la de las 00:00 (la diaria de Prefectura). Si no hay, la última del día. San Fernando (52) y Buenos Aires (85) son horarias y toman la última.
- Se vuelven a bajar los últimos 3 días de cada escala en cada corrida (DIAS_ATRAS), por si el INA corrige.
- Error de carga: valor ≤ 0 si el día anterior era > 0,5 m, o más de 3 veces el día anterior (si era > 1 m). Se descarta y se anota en meta.json. No se aplica al tramo Delta y Río de la Plata, donde la marea y el viento producen saltos reales.
- Si fallan más de la mitad de las escalas, el script sale con error y no se publica nada nuevo.
- Escalas sin lecturas en el período: Puerto Maní, Bouvier, Alicia, Puerto Gualeguaychú. Federación tiene lecturas viejas (hasta el 11/9) en otra referencia (unos 35 m, contra un alerta de 3,9): figura como "Sin dato reciente".

## Página (site/index.html)

- Secciones, en orden y con estos `id`: encabezado (`inicio`), indicadores, atencion (escalas para mirar), mapa, perfil (distancia al alerta por tramo), evolucion, lluvia, viento, tabla, fuente.
- Scripts: el primero define dos cálculos con `dash.calc`: `estado_actual` (última lectura, variación a 24 h y 7 días, margen al alerta y estado) y `resumen` (cantidad de escalas por estado). El segundo, dentro de un IIFE, dibuja todo; está dividido por comentarios `// ---------- sección ----------`. El último lee meta.json para el texto "Actualizado el…".
- `assets/dash.js` imita la API del artifact: `dash.data(id)` → `{status, data}` (status loading, ok o error), `dash.onData(fn)` redibuja cuando cambian los datos, los filtros o el ancho, `dash.calc`, `dash.params/setParams/resetParams` (filtros `estacion`, `dias`, `tramo`, que se reflejan en la URL), `dash.setLink` (hash de la sección) y `dash.colors`. Para sumar una fuente nueva hay que agregarla a `SOURCES` en dash.js.
- Los atributos `data-source`, `data-field` y `data-where` del HTML son restos del artifact. No hacen nada, pero no molestan.
- Estados: Evacuación (altura ≥ evacuación), Alerta (≥ alerta), Aguas bajas (< aguas bajas), Normal, Sin niveles, Sin dato reciente (última lectura con más de 2 días de atraso respecto de la más reciente), Sin datos.
- "Para la época": compara la altura del día con los percentiles 10 y 90 de la media mensual de ese mes. Es una aproximación (dato diario contra medias mensuales); la página lo explica al pie.
- Sudestada: viento del sector este a sur (90° a 180°) de 30 km/h o más durante al menos 6 horas. Criterio propio y orientativo, constante `SUDESTADA` en extras.py.
- Diseño: variables CSS en `:root` (nombres `--color-*` y `--cds-*` heredados del artifact) con versión oscura en `prefers-color-scheme: dark`. Texto en Inter, cifras grandes en Source Serif 4. Colores de estado: evacuación `--cds-chart-status-critical`, alerta `--color-warn`, normal gris, aguas bajas `--series-1`. Números con `Intl.NumberFormat('es-AR')` (coma decimal) y signo menos `−`.
- Tablas y gráficos se redibujan enteros en cada `onData`. Los tooltips son un `div.rh-tip` dentro de cada contenedor.
- Bugs ya resueltos que no hay que reintroducir:
  - El `IntersectionObserver` que actualiza el hash de la URL arranca recién después del evento `load`. Si cambia el hash antes, Chrome salta a esa sección al terminar de cargar.
  - El scroll inicial solo respeta el hash con el que se abrió la página (`hashInicial`).
  - Los estilos que pisan a Leaflet llevan el prefijo `.rh .rh-map`, porque el CSS de Leaflet se carga después y empata en especificidad.

## Actualización y publicación

- Workflow `.github/workflows/actualizar.yml`: cron `50 15 * * *` y `50 22 * * *` (UTC, o sea 12:50 y 19:50 en Argentina), `workflow_dispatch` y cada push a main.
- Job `actualizar`: corre actualizar.py, después extras.py con `continue-on-error`, y commitea `site/data/` como github-actions[bot]. Los pushes del bot no disparan otro workflow, así que no hay bucle.
- Job `publicar`: hace checkout de main ya actualizado y publica `site/` con actions/deploy-pages. En el repo, Pages está configurado con Source: GitHub Actions.
- La climatología se recalcula sola cada 30 días; para forzarla, `python scripts/extras.py --forzar-climatologia`.
- Antes de pushear, siempre `git pull`: el bot commitea datos varias veces por día.

## Cómo trabajar localmente

```bash
python scripts/actualizar.py                 # baja lecturas nuevas (necesita red)
python scripts/actualizar.py --solo-archivos # regenera CSV y meta sin red
python scripts/extras.py                     # pronósticos, lluvia, viento y capas
python -m http.server 8000 -d site           # y abrir http://localhost:8000
```

Para revisar la página con Playwright: servir `site/` y abrirla en claro, en oscuro y a 390 px de ancho. Revisar la consola (no debe haber errores) y que `document.documentElement.scrollWidth` no supere el ancho de la ventana. Los mosaicos de OSM y NASA solo cargan con red.

## Pendientes e ideas

- Avisos por Telegram o mail cuando una escala cruza el alerta, desde el mismo workflow (secrets del repo). Fue el punto 5 de la lista de ideas y quedó sin hacer.
- Caudales pronosticados de GloFAS vía la Flood API de Open-Meteo, como dato secundario y bien rotulado (punto 6).
- La imagen og.png es una captura fija del 13/10/2026. Se podría regenerar en el workflow con Playwright.
- Verificar a ojo las capas de NASA en el mapa y la vista en celular de las secciones de lluvia y viento.
- La sección "Escalas para mirar" se hace larga en celular (18 tarjetas con los datos del 13/10).
- Duplicado en claude.ai: sigue existiendo el artifact Dashboard original ("Alturas de los ríos") y una tarea programada de claude.ai, "Actualizar dashboard de alturas de ríos" (todos los días a las 12:50), que lo actualiza. Si el sitio público reemplaza al artifact, hay que borrar esa tarea; preguntarle a Guillermo antes.

## Estilo de escritura

- Todo el texto de la página, los commits y la documentación va en español rioplatense con voseo ("tocá", "consultá").
- No usar la raya ni el guion largo (U+2014) en ningún texto, ni la coma antes de la "y" final en enumeraciones en inglés. Evitar las palabras "crucial", "clave" y "emocionado".
- Explicaciones concretas y breves, sin párrafos de resumen al final.
- Mensajes de commit en español, en imperativo y descriptivos ("Sumar pronósticos del INA…").
- No poner datos personales del dueño más allá de la firma "Hecho por Guillermo Leale con Claude" del pie.
