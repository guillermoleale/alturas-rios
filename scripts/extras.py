#!/usr/bin/env python3
"""Datos complementarios del dashboard. Cada parte es independiente: si una falla, las otras siguen.

- pronosticos.json  : último pronóstico de altura del INA para cada escala que lo tenga.
- climatologia.json : rango habitual de la altura media mensual por escala y mes (INA, desde 1970).
- meteo.json        : lluvia de la última semana y pronóstico a 7 días en puntos de la cuenca,
                      y viento horario en el Río de la Plata (Open-Meteo, CC BY 4.0).
- capas.json        : capas de satélite y lluvia de NASA GIBS para el mapa.

Uso: python scripts/extras.py [--forzar-climatologia]
"""
import datetime as dt
import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "site", "data")
INA = "https://alerta.ina.gob.ar/pub/datos/"
TZ_AR = dt.timezone(dt.timedelta(hours=-3))
UA = {"User-Agent": "alturas-rios (github.com/guillermoleale/alturas-rios)"}

# Calibraciones del INA por orden de preferencia cuando una escala tiene más de una.
PREFERENCIA_CAL = [289, 312, 489, 442, 432, 433, 441, 440]

PUNTOS_LLUVIA = [
    ("Cuenca del Iguazú", "Alto Paraná", -26.2, -51.1),
    ("Alto Paraná (Foz do Iguaçu)", "Alto Paraná", -25.55, -54.58),
    ("Paraguay (Asunción)", "Paraguay", -25.28, -57.63),
    ("Alto Uruguay (Chapecó)", "Uruguay", -27.1, -52.62),
    ("Uruguay medio (Paso de los Libres)", "Uruguay", -29.71, -57.09),
    ("Corrientes", "Paraná medio", -27.47, -58.83),
    ("Santa Fe", "Paraná medio", -31.63, -60.7),
    ("Rosario", "Paraná inferior", -32.95, -60.64),
    ("Buenos Aires", "Río de la Plata", -34.6, -58.4),
]
PUNTO_VIENTO = ("Río de la Plata frente a Buenos Aires", -34.55, -58.1)
SUDESTADA = {"dir_min": 90, "dir_max": 180, "vel_min": 30, "horas_min": 6}

CAPAS = [
    ("GOES-East_ABI_GeoColor_v0_NRT", "Satélite (GOES-East, NASA)", 0.75),
    ("IMERG_Precipitation_Rate_30min_v7_NRT", "Lluvia reciente estimada (IMERG, NASA)", 0.85),
]


def get_json(url, intentos=4):
    error = None
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            error = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"{url[:120]}: {error}")


def lista(cuerpo):
    if isinstance(cuerpo, dict) and isinstance(cuerpo.get("data"), list):
        return cuerpo["data"]
    if "No se encontraron" in json.dumps(cuerpo, ensure_ascii=False):
        return []
    raise RuntimeError(json.dumps(cuerpo, ensure_ascii=False)[:200])


def leer(nombre, defecto=None):
    try:
        with open(os.path.join(DATOS, nombre), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return defecto


def escribir(nombre, obj):
    with open(os.path.join(DATOS, nombre), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def ahora():
    return dt.datetime.now(TZ_AR)


# ---------------------------------------------------------------- pronósticos
def pronosticos(estaciones):
    nuestras = {e["sitecode"] for e in estaciones}
    series = lista(get_json(INA + "seriesProno&varId=2&all=false&format=json"))
    limite = (ahora() - dt.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M")
    elegidas = {}
    for s in series:
        sc = s.get("sitecode")
        if sc not in nuestras or not s.get("forecastdate") or s["forecastdate"][:16] < limite:
            continue
        rango = PREFERENCIA_CAL.index(s["calid"]) if s.get("calid") in PREFERENCIA_CAL else len(PREFERENCIA_CAL)
        actual = elegidas.get(sc)
        if actual is None or rango < actual[0] or (rango == actual[0] and s["forecastdate"] > actual[1]["forecastdate"]):
            elegidas[sc] = (rango, s)

    salida = {}
    for sc, (_, s) in sorted(elegidas.items()):
        inicio = s["forecastdate"][:10]
        fin = (dt.date.fromisoformat(inicio) + dt.timedelta(days=60)).isoformat()
        url = (f"{INA}datosProno&siteCode={sc}&varId=2&calId={s['calid']}&corId={s['corid']}"
               f"&timeStart={inicio}&timeEnd={fin}&format=json")
        try:
            cuerpo = get_json(url)
            valores = lista(cuerpo)
        except Exception as e:  # noqa: BLE001
            print(f"  pronóstico {s.get('estacion_nombre')}: {e}")
            continue
        por_t = {}
        for v in valores:
            if v.get("valor") is not None and v.get("timestart"):
                por_t.setdefault(v["timestart"][:16], []).append(float(v["valor"]))
        if not por_t:
            continue
        puntos = []
        for t in sorted(por_t):
            vs = sorted(por_t[t])
            p = {"t": t, "v": round(statistics.median(vs), 3)}
            if len(vs) > 1 and vs[-1] - vs[0] > 1e-9:
                p["lo"], p["hi"] = round(vs[0], 3), round(vs[-1], 3)
            puntos.append(p)
        cab = cuerpo.get("responseHeader", {}) if isinstance(cuerpo, dict) else {}
        salida[str(sc)] = {
            "emitido": (cab.get("forecastdate") or s["forecastdate"])[:16],
            "modelo": s.get("cal_model") or cab.get("model_name"),
            "calibracion": s.get("cal_name") or cab.get("cal_name"),
            "puntos": puntos,
        }
        time.sleep(0.3)
    escribir("pronosticos.json", {"generado": ahora().isoformat(timespec="minutes"), "escalas": salida})
    print(f"Pronósticos: {len(salida)} escalas.")


# ---------------------------------------------------------------- climatología
def percentil(vs, p):
    vs = sorted(vs)
    k = (len(vs) - 1) * p
    i = int(k)
    return vs[i] if i + 1 >= len(vs) else vs[i] + (vs[i + 1] - vs[i]) * (k - i)


def climatologia(estaciones, forzar=False):
    previa = leer("climatologia.json")
    if previa and not forzar:
        hecha = dt.datetime.fromisoformat(previa["generado"])
        if ahora() - hecha < dt.timedelta(days=30):
            print("Climatología: vigente, no se recalcula.")
            return
    anio_actual = ahora().year
    salida = {}
    for e in estaciones:
        sc = e["sitecode"]
        url = (f"{INA}datos&siteCode={sc}&varId=33&procId=1&timeStart=1970-01-01"
               f"&timeEnd={ahora().date().isoformat()}&format=json")
        try:
            valores = lista(get_json(url))
        except Exception as ex:  # noqa: BLE001
            print(f"  climatología {e['nombre']}: {ex}")
            continue
        por_mes, anios = {}, set()
        for v in valores:
            ts, val = v.get("timestart"), v.get("valor")
            if not ts or val is None or int(ts[:4]) >= anio_actual:
                continue
            por_mes.setdefault(int(ts[5:7]), []).append(float(val))
            anios.add(int(ts[:4]))
        meses = {}
        for m, vs in por_mes.items():
            if len(vs) >= 8:
                meses[str(m)] = [round(percentil(vs, 0.1), 2), round(percentil(vs, 0.5), 2), round(percentil(vs, 0.9), 2), len(vs)]
        if meses:
            salida[str(sc)] = {"desde": min(anios), "hasta": max(anios), "meses": meses}
        time.sleep(0.3)
    escribir("climatologia.json", {"generado": ahora().isoformat(timespec="minutes"),
                                   "descripcion": "Percentiles 10, 50 y 90 de la altura media mensual por mes calendario (INA, varId 33), y cantidad de años.",
                                   "escalas": salida})
    print(f"Climatología: {len(salida)} escalas.")


# ---------------------------------------------------------------- meteorología
def open_meteo(params):
    return get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params, safe=",/"))


def meteo():
    resp = open_meteo({
        "latitude": ",".join(str(p[2]) for p in PUNTOS_LLUVIA),
        "longitude": ",".join(str(p[3]) for p in PUNTOS_LLUVIA),
        "daily": "precipitation_sum", "past_days": 7, "forecast_days": 7,
        "timezone": "America/Argentina/Buenos_Aires",
    })
    if isinstance(resp, dict):
        resp = [resp]
    hoy = ahora().date().isoformat()
    lluvia = []
    for (nombre, zona, lat, lon), r in zip(PUNTOS_LLUVIA, resp):
        dias = [{"fecha": f, "mm": (round(v, 1) if v is not None else None)}
                for f, v in zip(r["daily"]["time"], r["daily"]["precipitation_sum"])]
        pasado = sum(d["mm"] or 0 for d in dias if d["fecha"] < hoy)
        futuro = sum(d["mm"] or 0 for d in dias if d["fecha"] >= hoy)
        lluvia.append({"nombre": nombre, "zona": zona, "lat": lat, "lon": lon, "dias": dias,
                       "ultimos7": round(pasado, 1), "proximos7": round(futuro, 1)})

    nombre, lat, lon = PUNTO_VIENTO
    r = open_meteo({"latitude": lat, "longitude": lon,
                    "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
                    "forecast_days": 4, "timezone": "America/Argentina/Buenos_Aires"})
    h = r["hourly"]
    horas = [{"t": t, "vel": v, "dir": d, "raf": g}
             for t, v, d, g in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"], h["wind_gusts_10m"])
             if t[:13] >= ahora().strftime("%Y-%m-%dT%H")]
    periodos, inicio = [], None
    for i, x in enumerate(horas + [None]):
        ok = x is not None and x["vel"] is not None and x["dir"] is not None and \
            SUDESTADA["dir_min"] <= x["dir"] <= SUDESTADA["dir_max"] and x["vel"] >= SUDESTADA["vel_min"]
        if ok and inicio is None:
            inicio = i
        if not ok and inicio is not None:
            if i - inicio >= SUDESTADA["horas_min"]:
                tramo = horas[inicio:i]
                periodos.append({"desde": tramo[0]["t"], "hasta": tramo[-1]["t"],
                                 "vel_max": max(x["vel"] for x in tramo), "raf_max": max((x["raf"] or 0) for x in tramo)})
            inicio = None
    escribir("meteo.json", {
        "generado": ahora().isoformat(timespec="minutes"), "hoy": hoy,
        "fuente": "Open-Meteo.com (CC BY 4.0)",
        "lluvia": lluvia,
        "viento": {"lugar": nombre, "lat": lat, "lon": lon, "horas": horas,
                   "criterio": SUDESTADA, "sudestada": periodos},
    })
    print(f"Meteorología: {len(lluvia)} puntos de lluvia, {len(horas)} horas de viento, {len(periodos)} períodos de viento del sudeste.")


# ---------------------------------------------------------------- capas NASA
def capas():
    url = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/nrt/1.0.0/WMTSCapabilities.xml"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
        arbol = ET.parse(r)
    ns = {"w": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
    buscadas = {c[0]: c for c in CAPAS}
    salida = []
    for capa in arbol.getroot().iter("{http://www.opengis.net/wmts/1.0}Layer"):
        ident = capa.findtext("ows:Identifier", namespaces=ns)
        if ident not in buscadas:
            continue
        tms = capa.findtext("w:TileMatrixSetLink/w:TileMatrixSet", namespaces=ns)
        recurso = capa.find("w:ResourceURL", ns)
        if not tms or recurso is None:
            continue
        plantilla = (recurso.get("template")
                     .replace("/{Time}", "")
                     .replace("{TileMatrixSet}", tms)
                     .replace("{TileMatrix}", "{z}").replace("{TileRow}", "{y}").replace("{TileCol}", "{x}"))
        nivel = int(tms.rsplit("Level", 1)[-1]) if "Level" in tms else 6
        _, nombre, opacidad = buscadas[ident]
        salida.append({"id": ident, "nombre": nombre, "url": plantilla, "maxNativeZoom": nivel, "opacidad": opacidad})
    orden = [c[0] for c in CAPAS]
    salida.sort(key=lambda c: orden.index(c["id"]))
    if salida:
        escribir("capas.json", {"generado": ahora().isoformat(timespec="minutes"), "capas": salida})
    print(f"Capas NASA: {[c['id'] for c in salida]}")


def main():
    estaciones = leer("estaciones.json", [])
    tareas = [
        ("pronósticos", lambda: pronosticos(estaciones)),
        ("climatología", lambda: climatologia(estaciones, "--forzar-climatologia" in sys.argv)),
        ("meteorología", meteo),
        ("capas", capas),
    ]
    fallas = []
    for nombre, f in tareas:
        try:
            f()
        except Exception as e:  # noqa: BLE001
            fallas.append(nombre)
            print(f"Falló {nombre}: {e}")
    if fallas:
        print("Partes con errores: " + ", ".join(fallas))


if __name__ == "__main__":
    main()
