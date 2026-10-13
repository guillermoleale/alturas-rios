#!/usr/bin/env python3
"""Actualiza las alturas diarias de las escalas con la API pública del INA.

Lee site/data/estaciones.json y site/data/alturas.json, baja las lecturas de los
últimos días de cada escala y vuelve a escribir alturas.json, alturas.csv y meta.json.

Uso:
    python scripts/actualizar.py                 # baja datos nuevos del INA
    python scripts/actualizar.py --solo-archivos # solo regenera CSV y meta con lo que hay
"""
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "site", "data")
API = "https://alerta.ina.gob.ar/pub/datos/datos"
INICIO = "2026-07-01"
DIAS_ATRAS = 3          # se vuelven a bajar los últimos días por si hubo correcciones
HORARIAS = {52, 85}     # San Fernando y Buenos Aires publican lecturas horarias
TZ_AR = dt.timezone(dt.timedelta(hours=-3))
SIN_FILTRO = "Delta y Río de la Plata"  # la marea y el viento producen saltos reales


def leer(nombre):
    with open(os.path.join(DATOS, nombre), encoding="utf-8") as f:
        return json.load(f)


def escribir_json(nombre, obj, compacto=True):
    ruta = os.path.join(DATOS, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")


def bajar(sitecode, desde, hasta):
    """Devuelve la lista de registros {timestart, valor, ...} de una escala."""
    url = f"{API}&timeStart={desde}&timeEnd={hasta}&siteCode={sitecode}&varId=2&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "alturas-rios (github.com/guillermoleale/alturas-rios)"})
    ultimo_error = None
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                cuerpo = json.load(r)
            if isinstance(cuerpo, dict) and isinstance(cuerpo.get("data"), list):
                return cuerpo["data"]
            texto = json.dumps(cuerpo, ensure_ascii=False)
            if "No se encontraron" in texto:
                return []
            raise RuntimeError(texto[:200])
        except urllib.error.HTTPError as e:
            ultimo_error = f"HTTP {e.code}"
            if e.code != 429 and e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo_error = str(e)
        time.sleep(5 * (intento + 1))
    raise RuntimeError(ultimo_error or "sin respuesta")


def una_por_dia(registros, sitecode):
    """Una lectura por día: la de las 00:00 (la diaria de Prefectura) o, si no hay, la última."""
    por_dia = {}
    for r in registros:
        ts, valor = r.get("timestart"), r.get("valor")
        if not ts or valor is None:
            continue
        por_dia.setdefault(ts[:10], []).append((ts[11:16], float(valor)))
    salida = {}
    for fecha, lecturas in por_dia.items():
        lecturas.sort()
        ceros = [v for h, v in lecturas if h == "00:00"]
        salida[fecha] = ceros[-1] if ceros and sitecode not in HORARIAS else lecturas[-1][1]
    return salida


def es_error_de_carga(valor, anterior):
    if anterior is None:
        return False
    return (valor <= 0 and anterior > 0.5) or (anterior > 1 and valor > 3 * anterior)


def actualizar(estaciones, series):
    hoy = dt.datetime.now(TZ_AR).date()
    hasta = (hoy + dt.timedelta(days=1)).isoformat()
    fallas, descartes, cambios = [], [], 0
    for e in estaciones:
        sc = e["sitecode"]
        serie = series.setdefault(sc, {})
        desde = (dt.date.fromisoformat(max(serie)) - dt.timedelta(days=DIAS_ATRAS)).isoformat() if serie else INICIO
        try:
            registros = bajar(sc, desde, hasta)
        except Exception as ex:  # noqa: BLE001
            fallas.append(f"{e['nombre']}: {ex}")
            continue
        for fecha, valor in sorted(una_por_dia(registros, sc).items()):
            if fecha < INICIO:
                continue
            anterior = serie.get((dt.date.fromisoformat(fecha) - dt.timedelta(days=1)).isoformat())
            if e["tramo"] != SIN_FILTRO and es_error_de_carga(valor, anterior):
                descartes.append({"escala": e["nombre"], "fecha": fecha, "valor": valor})
                continue
            if serie.get(fecha) != valor:
                cambios += 1
            serie[fecha] = valor
        time.sleep(0.3)
    return fallas, descartes, cambios


def guardar(estaciones, series, meta):
    filas = [{"sitecode": sc, "fecha": f, "altura": v}
             for sc in sorted(series) for f, v in sorted(series[sc].items())]
    escribir_json("alturas.json", filas)
    nombres = {e["sitecode"]: e for e in estaciones}
    with open(os.path.join(DATOS, "alturas.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sitecode", "escala", "tramo", "rio", "provincia", "fecha", "altura_m",
                    "nivel_alerta_m", "nivel_evacuacion_m", "nivel_aguas_bajas_m"])
        for r in filas:
            e = nombres.get(r["sitecode"], {})
            w.writerow([r["sitecode"], e.get("nombre"), e.get("tramo"), e.get("rio"), e.get("provincia"),
                        r["fecha"], r["altura"], e.get("alerta"), e.get("evacuacion"), e.get("aguas_bajas")])
    meta["hasta"] = max((r["fecha"] for r in filas), default=None)
    meta["lecturas"] = len(filas)
    escribir_json("meta.json", meta, compacto=False)
    return filas


def main():
    estaciones = leer("estaciones.json")
    series = {}
    for r in leer("alturas.json"):
        series.setdefault(r["sitecode"], {})[r["fecha"]] = r["altura"]
    try:
        meta = leer("meta.json")
    except FileNotFoundError:
        meta = {}

    if "--solo-archivos" in sys.argv:
        guardar(estaciones, series, meta)
        print("Archivos regenerados sin bajar datos.")
        return

    fallas, descartes, cambios = actualizar(estaciones, series)
    if len(fallas) > len(estaciones) / 2:
        print(f"Fallaron {len(fallas)} de {len(estaciones)} escalas; no se actualiza.")
        print("\n".join(fallas[:10]))
        sys.exit(1)

    meta["actualizado"] = dt.datetime.now(TZ_AR).isoformat(timespec="minutes")
    meta["fallas_ultima_corrida"] = fallas
    meta["descartes"] = (meta.get("descartes", []) + descartes)[-100:]
    filas = guardar(estaciones, series, meta)
    print(f"Listo: {cambios} lecturas nuevas o corregidas, {len(filas)} en total, datos hasta {meta['hasta']}.")
    if descartes:
        print("Descartadas por error de carga: " + ", ".join(f"{d['escala']} {d['fecha']} ({d['valor']})" for d in descartes))
    if fallas:
        print("Escalas que no respondieron: " + "; ".join(fallas))


if __name__ == "__main__":
    main()
