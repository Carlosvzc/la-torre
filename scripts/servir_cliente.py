"""Sirve los clientes del juego (cliente/) en localhost:8080 sin que el navegador use copias viejas.

`python -m http.server` no manda cabeceras de caché, así que el navegador puede seguir mostrando
una versión anterior del juego después de actualizarlo. Este servidor añade
`Cache-Control: no-cache`: el navegador pregunta cada vez si cambió (si no, responde 304 al
instante) y nunca muestra una versión vieja.

Uso:  python scripts/servir_cliente.py [puerto] [interfaz]
      interfaz 127.0.0.1 (solo esta PC, por defecto) o 0.0.0.0 (también la red local, para
      que tus amigos abran http://IP-de-tu-PC:8080/retro/ en el multijugador)
"""
import functools
import http.server
import os
import sys

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cliente")


class SinCacheVieja(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, formato, *args):        # registro breve en la salida estándar
        sys.stdout.write("%s %s\n" % (self.log_date_time_string(), formato % args))


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    interfaz = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    manejador = functools.partial(SinCacheVieja, directory=RAIZ)
    with http.server.ThreadingHTTPServer((interfaz, puerto), manejador) as servidor:
        print(f"Sirviendo {RAIZ} en {interfaz}:{puerto} (sin caché vieja)", flush=True)
        servidor.serve_forever()


if __name__ == "__main__":
    main()
