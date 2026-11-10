"""Pruebas de carga de La Torre (práctica 3.4): jugadores y espectadores simulados.

Cada usuario de Locust es un cliente de verdad por WebSocket:
  - Jugador: pide un servidor, entra con su grupo, juega una run completa con la
    estrategia de `estrategia.py` (20 acciones por segundo, como un humano con mando)
    y mide la latencia ida y vuelta (RTT) con un ping por segundo. Al terminar la run,
    pide otro servidor y vuelve a empezar.
  - Espectador: se conecta a una run en curso y mide cada cuánto llegan los snapshots
    (deberían llegar cada 100 ms) y cuántos bytes recibe (base para el egress).

Modos:
  Local (un servidor):      $env:SERVIDOR_WS = "ws://localhost:7654"
  Agones (allocator):       $env:ALLOCATOR_IP = "<IP>"   (certificados client.crt, client.key, ca.crt)

Ejemplos:
  locust -f locustfile.py Jugador -u 4 -r 1 -t 2m --headless --csv resultados/local
  locust -f locustfile.py Jugador -u 1000 -r 2 -t 20m --headless --processes -1 --csv rampa
  locust -f locustfile.py Espectador -u 500 -r 50 -t 5m --headless --processes -1 --csv espectadores

Variables opcionales: JUGADORES_POR_RUN (2), HABILIDAD (0.85, de 0 a 1), FLOTA (torre-fleet),
ESPECTAR (lista de ws://ip:puerto separada por comas, para espectadores lanzados aparte).

Importante con Agones: los espectadores encuentran las runs a través de los jugadores del mismo
proceso. Lánzalos en el mismo comando (`Jugador Espectador`) o pásales ESPECTAR. Si no tienen
ninguna run que mirar, se registra el error `sin_runs` (antes fallaba en silencio).
"""
from __future__ import annotations

import json
import os
import random
import struct
import time
import uuid

import requests
from gevent.lock import Semaphore
from locust import User, constant, events, task
from websocket import ABNF, WebSocketException, WebSocketTimeoutException, create_connection

from estrategia import decidir

SERVIDOR_WS = os.getenv("SERVIDOR_WS", "")
ALLOCATOR_IP = os.getenv("ALLOCATOR_IP", "")
FLOTA = os.getenv("FLOTA", "torre-fleet")
GRUPO = max(1, min(4, int(os.getenv("JUGADORES_POR_RUN", "2"))))
HABILIDAD = float(os.getenv("HABILIDAD", "0.85"))
ESPECTAR = [u.strip() for u in os.getenv("ESPECTAR", "").split(",") if u.strip()]
CERTS = {"cert": ("client.crt", "client.key"), "verify": "ca.crt"}
SNAPSHOT_TARDIO_S = 0.3       # un espectador "se congela" si pasan más de 300 ms sin snapshot
PONG_PERDIDO_S = 5.0          # si el pong no llega en 5 s, se da por perdido y se vuelve a medir


class SnapshotTardio(Exception):
    """El equivalente al rebuffering: el estado llegó tarde al espectador."""


class Rechazado(Exception):
    """El servidor cerró la conexión con un código (4000 llena, 4001 empezada, 4003 terminando...)."""


class SinRunsQueMirar(Exception):
    """El espectador no tiene ninguna run en curso a la que conectarse."""


def recibir_mensaje(ws) -> dict:
    """Lee el siguiente mensaje de texto; si el servidor cierra, lanza `Rechazado` con su código."""
    while True:
        opcode, datos = ws.recv_data(control_frame=True)
        if opcode == ABNF.OPCODE_CLOSE:
            codigo = struct.unpack("!H", datos[:2])[0] if len(datos) >= 2 else 1005
            raise Rechazado(f"{codigo}: {datos[2:].decode('utf-8', 'replace')}")
        if opcode in (ABNF.OPCODE_TEXT, ABNF.OPCODE_BINARY):
            return json.loads(datos)
        # ping/pong de control del protocolo: se ignoran


def medir(tipo: str, nombre: str, inicio: float, error: Exception | None = None, bytes_: int = 0) -> None:
    """Registra una medición en Locust (aparece en las tablas y en los CSV)."""
    events.request.fire(request_type=tipo, name=nombre,
                        response_time=(time.perf_counter() - inicio) * 1000,
                        response_length=bytes_, exception=error, context={})


class Emparejador:
    """Mini-matchmaker compartido: llena cada servidor con GRUPO jugadores antes de pedir otro.

    Hace el papel del emparejador real (como en el PDF): en local siempre da el mismo
    servidor; con Agones pide un GameServer al allocator.
    """
    candado = Semaphore()
    sala = {"addr": None, "cupo": 0}
    activas: list[str] = []            # runs en curso, para los espectadores

    @classmethod
    def pedir(cls) -> str:
        with cls.candado:                # un solo pedido a la vez
            if cls.sala["cupo"] == 0:
                cls.sala = {"addr": cls._nuevo_servidor(), "cupo": GRUPO}
                cls.activas.append(cls.sala["addr"])
                del cls.activas[:-50]
            cls.sala["cupo"] -= 1
            return cls.sala["addr"]

    @staticmethod
    def _nuevo_servidor() -> str:
        if SERVIDOR_WS:
            return SERVIDOR_WS
        if not ALLOCATOR_IP:
            raise RuntimeError("define SERVIDOR_WS (local) o ALLOCATOR_IP (Agones)")
        t0 = time.perf_counter()
        pedido = {"namespace": "default",
                  "gameServerSelectors": [{"matchLabels": {"agones.dev/fleet": FLOTA}}]}
        try:
            r = requests.post(f"https://{ALLOCATOR_IP}/gameserverallocation", json=pedido, timeout=10, **CERTS)
            r.raise_for_status()
            gs = r.json()
            medir("ALLOC", "asignacion", t0)
            return f"ws://{gs['address']}:{gs['ports'][0]['port']}"
        except Exception as e:
            medir("ALLOC", "asignacion", t0, e)
            raise


class Jugador(User):
    """Juega runs completas, una tras otra."""
    wait_time = constant(1)            # pausa entre una run y la siguiente

    def on_start(self):
        self.id = "bot-" + uuid.uuid4().hex[:6]
        self.rng = random.Random()

    @task
    def run_completa(self):
        try:
            url = Emparejador.pedir()
        except Exception:
            time.sleep(2)
            return
        t0 = time.perf_counter()
        try:
            ws = create_connection(url, timeout=10)
            ws.send(json.dumps({"hola": {"id": self.id, "rol": "jugador"}}))
            bienvenida = recibir_mensaje(ws)
            if "bienvenida" not in bienvenida:
                raise WebSocketException(f"respuesta inesperada: {bienvenida}")
            medir("WS", "conexion", t0)
        except Exception as e:
            medir("WS", "conexion", t0, e)
            # 4003 = la run está terminando: esperar a que el servidor quede libre
            time.sleep(3 if isinstance(e, Rechazado) and str(e).startswith("4003") else 1)
            return
        try:
            self._jugar(ws)
        finally:
            ws.close()

    def _jugar(self, ws) -> None:
        ws.settimeout(5)
        listo = False
        ping_pendiente: float | None = None
        ultimo_ping = time.perf_counter()
        while True:
            ahora = time.perf_counter()
            if ping_pendiente is not None and ahora - ping_pendiente > PONG_PERDIDO_S:
                medir("WS", "rtt", ping_pendiente, WebSocketTimeoutException("pong perdido"))
                ping_pendiente = None                   # se da por perdido y se sigue midiendo
            if ping_pendiente is None and ahora - ultimo_ping >= 1.0:     # un ping por segundo
                ping_pendiente = ultimo_ping = ahora
                ws.send(json.dumps({"ping": ping_pendiente}))
            try:
                texto = ws.recv()
            except WebSocketTimeoutException as e:
                medir("WS", "snapshot", ahora, e)
                return
            except WebSocketException:
                return                                  # el servidor cerró (fin de la run)
            if not texto:
                return
            d = json.loads(texto)
            if "pong" in d:
                if d["pong"] == ping_pendiente:
                    medir("WS", "rtt", ping_pendiente)
                    ping_pendiente = None
                continue
            if "estado" not in d:
                continue
            for e in d.get("eventos", []):
                # Una run se cuenta una sola vez: la reporta el primer jugador (por id) del grupo.
                # "Tiempo" = duración del combate; "bytes" = piso alcanzado.
                if e.get("tipo") == "fin" and d["jugadores"] and min(d["jugadores"]) == self.id:
                    events.request.fire(request_type="RUN", name=f"run_{e['resultado']}",
                                        response_time=d["t"] * 1000, response_length=d["piso"],
                                        exception=None, context={})
            if d["estado"] == "esperando":
                # espera a que llegue su grupo (o a que la sala esté por arrancar sola)
                if not listo and (len(d["jugadores"]) >= GRUPO or d.get("inicio_en", 99) <= 1):
                    ws.send(json.dumps({"accion": "listo"}))
                    listo = True
                continue
            accion = decidir(d, self.id, HABILIDAD, self.rng)
            if accion:
                ws.send(json.dumps(accion))


class Espectador(User):
    """Mira runs en curso; cambia de run cada minuto."""
    wait_time = constant(1)

    @task
    def mirar(self):
        t0 = time.perf_counter()
        candidatos = ESPECTAR or ([SERVIDOR_WS] if SERVIDOR_WS else Emparejador.activas)
        if not candidatos:
            # Antes esto fallaba en silencio (0 peticiones); ahora se ve en el reporte
            medir("WS", "conexion_espectador", t0, SinRunsQueMirar(
                "sin runs: lanza Jugador en el mismo comando o define ESPECTAR"))
            time.sleep(2)
            return
        url = random.choice(candidatos)
        try:
            ws = create_connection(url, timeout=10)
            ws.send(json.dumps({"hola": {"rol": "espectador"}}))
            recibir_mensaje(ws)
            medir("WS", "conexion_espectador", t0)
        except Exception as e:
            medir("WS", "conexion_espectador", t0, e)
            time.sleep(1)
            return
        ws.settimeout(5)
        fin = time.perf_counter() + 60
        anterior = time.perf_counter()
        try:
            while time.perf_counter() < fin:
                try:
                    texto = ws.recv()
                except WebSocketException:
                    return
                if not texto:
                    return
                ahora = time.perf_counter()
                hueco = ahora - anterior
                anterior = ahora
                # tiempo = hueco entre snapshots; bytes = tamaño recibido (para el egress)
                events.request.fire(request_type="WS", name="snapshot_espectador",
                                    response_time=hueco * 1000, response_length=len(texto),
                                    exception=SnapshotTardio(f"{hueco * 1000:.0f} ms") if hueco > SNAPSHOT_TARDIO_S else None,
                                    context={})
        finally:
            ws.close()
