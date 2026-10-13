#!/usr/bin/env python3
"""Regenera site/assets/og.png, la imagen de vista previa para LinkedIn y otras redes, con una captura
de la parte de arriba de la página con los datos del día.

Necesita Playwright, que no es de la biblioteca estándar; por eso va aparte de los scripts de datos:
    pip install playwright && python -m playwright install chromium

Uso: python scripts/og.py
Sirve site/ en un puerto local, abre la página a 1200 x 630 y guarda la captura. Si algo falla,
deja la imagen anterior como estaba.
"""
import functools
import http.server
import os
import sys
import threading

from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(RAIZ, "site")
SALIDA = os.path.join(SITE, "assets", "og.png")


class Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Silencioso, directory=SITE))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    temporal = SALIDA + ".tmp.png"
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = navegador.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1,
                                        color_scheme="light", locale="es-AR",
                                        timezone_id="America/Argentina/Buenos_Aires")
            errores = []
            pagina.on("pageerror", lambda e: errores.append(str(e)))
            pagina.goto(f"http://127.0.0.1:{servidor.server_port}/", wait_until="networkidle")
            # Espera a que estén el resumen, las tarjetas y la fecha de actualización.
            pagina.wait_for_function(
                "() => !document.querySelector('#resumen-texto.dash-skeleton, #indicadores .dash-skeleton')"
                " && document.getElementById('actualizado').textContent.length > 0", timeout=30000)
            pagina.evaluate("document.fonts.ready.then(() => true)")
            resumen = pagina.inner_text("#resumen-texto")
            if errores or resumen.startswith("No se pudieron"):
                raise RuntimeError(f"la página no cargó bien: {errores or resumen}")
            pagina.screenshot(path=temporal)
            navegador.close()
        os.replace(temporal, SALIDA)
        print(f"og.png: {resumen}")
    finally:
        servidor.shutdown()
        if os.path.exists(temporal):
            os.remove(temporal)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo regenerar og.png: {e}")
        sys.exit(1)
