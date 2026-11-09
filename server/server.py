"""Servidor de partida de La Torre (un proceso = un GameServer de Agones = una run).

Basado en el server.py de la práctica 3.3, pero autoritativo: los clientes solo
mandan acciones y el servidor simula el combate a 20 ticks por segundo.

Protocolo (JSON por WebSocket, puerto 7654):
    cliente → {"hola": {"id": "ana", "rol": "jugador" | "espectador"}}   (primer mensaje)
    servidor → {"bienvenida": {"id": "ana", "rol": "jugador", "modo": "torre"}}
    cliente → {"accion": "listo" | "mover" | "atacar" | "esquivar" | "elegir_mejora", ...}
    cliente → {"ping": <número>}            servidor → {"pong": <el mismo número>}
    servidor → snapshot del estado en cada tick (jugadores) o cada 2 ticks (espectadores)

Ciclo de vida en Agones (SDK REST en el contenedor auxiliar):
    /ready al arrancar → la run se asigna (Allocated) → /health cada 2 s → /shutdown al terminar.
Fuera de Agones las llamadas fallan en silencio y, al terminar una run, se empieza otra
para poder probar en local con Docker y Locust.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.request

import websockets
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from juego.partida import MAX_JUGADORES, Partida

MODO = os.getenv("MODO", "torre")
PUERTO = int(os.getenv("PUERTO", "7654"))
PUERTO_METRICAS = int(os.getenv("PUERTO_METRICAS", "9100"))
LEADERBOARD_URL = os.getenv("LEADERBOARD_URL", "")      # práctica 3.5 (vacío = no se reporta)
SDK = f"http://localhost:{os.getenv('AGONES_SDK_HTTP_PORT', '9358')}"

TICK_S = 0.05                 # 20 ticks por segundo
TICKS_ESPECTADOR = 2          # los espectadores reciben 10 snapshots por segundo
LATIDO_TICKS = 40             # /health cada 2 s
ESPERA_CIERRE_S = 3.0         # tiempo para que los clientes vean el resultado final
MAX_MENSAJE = 4096            # bytes; un cliente no puede mandar mensajes enormes

log = logging.getLogger("torre")

# --- Métricas Prometheus (prefijo torre_) ---------------------------------------
JUGADORES = Gauge("torre_players_connected", "Jugadores conectados")
ESPECTADORES = Gauge("torre_spectators_connected", "Espectadores conectados")
TICK = Histogram("torre_tick_seconds", "Duración del tick (simulación + envío)",
                 buckets=(.0005, .001, .0025, .005, .01, .025, .05, .1))
BYTES = Counter("torre_bytes_sent_total", "Bytes enviados a los clientes", ["rol"])
MENSAJES = Counter("torre_messages_received_total", "Mensajes recibidos de los clientes")
RUNS = Counter("torre_runs_total", "Runs terminadas", ["modo", "resultado"])
PISO = Gauge("torre_current_floor", "Piso actual de la run (0 = sala de espera)")
DURACION_RUN = Histogram("torre_run_seconds", "Duración de las runs terminadas",
                         buckets=(30, 60, 120, 240, 360, 480, 600, 900))


def agones(ruta: str) -> bool:
    """Llama al SDK REST de Agones. Devuelve False si no hay Agones (modo local)."""
    try:
        req = urllib.request.Request(SDK + ruta, data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
        return True
    except Exception:
        return False


def reportar_resultado(resultado: dict) -> None:
    """Manda el resultado de la run a la tabla de líderes serverless (si hay URL)."""
    if not LEADERBOARD_URL:
        return
    try:
        req = urllib.request.Request(LEADERBOARD_URL.rstrip("/") + "/resultado",
                                     data=json.dumps(resultado).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:                      # la run no debe fallar por esto
        log.warning("no se pudo reportar el resultado: %s", e)


class Servidor:
    """Une la red (WebSocket) con la lógica (`Partida`)."""

    def __init__(self, modo: str = MODO, semilla: int | None = None):
        self.modo = modo
        self.semilla = semilla
        self.partida = Partida(modo=modo, semilla=semilla)
        self.jugadores: dict[str, websockets.WebSocketServerProtocol] = {}
        self.espectadores: set = set()
        self.con_agones = False
        self.cerrando = False
        self.n_tick = 0
        self.eventos_espectador: list[dict] = []
        self.inicio_run = time.monotonic()

    # --- Conexiones ------------------------------------------------------------
    async def atender(self, ws) -> None:
        """Primer mensaje = presentación; después, acciones o pings."""
        try:
            hola = json.loads(await asyncio.wait_for(ws.recv(), timeout=5)).get("hola", {})
        except Exception:
            await ws.close(code=4002, reason="se esperaba {\"hola\": ...}")
            return
        rol = hola.get("rol", "jugador")
        jugador_id = str(hola.get("id", ""))[:24]

        if rol == "espectador":
            await self._atender_espectador(ws)
            return
        if not jugador_id:
            await ws.close(code=4002, reason="falta el id del jugador")
            return
        if self.cerrando or len(self.jugadores) >= MAX_JUGADORES:
            await ws.close(code=4000, reason="partida llena")
            return
        if not self.partida.agregar_jugador(jugador_id):
            await ws.close(code=4001, reason="la run ya empezó o el id está repetido")
            return

        self.jugadores[jugador_id] = ws
        JUGADORES.set(len(self.jugadores))
        await self._enviar(ws, {"bienvenida": {"id": jugador_id, "rol": "jugador",
                                               "modo": self.modo}}, "jugador")
        try:
            async for msg in ws:
                await self._procesar(ws, jugador_id, msg)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.jugadores.pop(jugador_id, None)
            JUGADORES.set(len(self.jugadores))
            self.partida.quitar_jugador(jugador_id)

    async def _atender_espectador(self, ws) -> None:
        self.espectadores.add(ws)
        ESPECTADORES.set(len(self.espectadores))
        await self._enviar(ws, {"bienvenida": {"rol": "espectador", "modo": self.modo}},
                           "espectador")
        try:
            async for msg in ws:                 # los espectadores solo pueden medir ping
                await self._procesar(ws, None, msg)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.espectadores.discard(ws)
            ESPECTADORES.set(len(self.espectadores))

    async def _procesar(self, ws, jugador_id: str | None, msg) -> None:
        MENSAJES.inc()
        try:
            d = json.loads(msg)
        except (ValueError, TypeError):
            return
        if not isinstance(d, dict):
            return
        if "ping" in d:                          # latencia: se responde al instante
            await self._enviar(ws, {"pong": d["ping"]},
                               "jugador" if jugador_id else "espectador")
        elif jugador_id is not None:
            self.partida.recibir(jugador_id, d)

    async def _enviar(self, ws, datos: dict, rol: str) -> None:
        texto = json.dumps(datos, separators=(",", ":"))
        BYTES.labels(rol).inc(len(texto))
        try:
            await ws.send(texto)
        except websockets.ConnectionClosed:
            pass

    # --- Bucle principal ---------------------------------------------------------
    def tick(self) -> None:
        """Un tick: simula, arma el snapshot y lo difunde."""
        self.partida.paso(TICK_S)
        snap = self.partida.snapshot()
        PISO.set(0 if snap["estado"] == "esperando" else snap["piso"])
        if self.jugadores:
            texto = json.dumps(snap, separators=(",", ":"))
            websockets.broadcast(self.jugadores.values(), texto)
            BYTES.labels("jugador").inc(len(texto) * len(self.jugadores))

        # Los espectadores van a 10 Hz, pero no se pierden eventos de los ticks saltados
        self.eventos_espectador += snap["eventos"]
        if self.espectadores and self.n_tick % TICKS_ESPECTADOR == 0:
            snap["eventos"], self.eventos_espectador = self.eventos_espectador, []
            texto = json.dumps(snap, separators=(",", ":"))
            websockets.broadcast(self.espectadores, texto)
            BYTES.labels("espectador").inc(len(texto) * len(self.espectadores))
        elif not self.espectadores:
            self.eventos_espectador = []
        self.n_tick += 1

    async def terminar_run(self) -> None:
        """Registra la run, avisa a la tabla de líderes y libera el servidor."""
        p = self.partida
        RUNS.labels(self.modo, p.estado).inc()
        DURACION_RUN.observe(time.monotonic() - self.inicio_run)
        if p.estado != "abandonada" and p.jugadores:
            await asyncio.to_thread(reportar_resultado, p.resultado())
        log.info("run terminada: %s (%s)", p.estado, p.motivo_fin)
        await asyncio.sleep(ESPERA_CIERRE_S)     # que todos vean la pantalla final

        if self.con_agones:                      # en Agones: el pod se apaga y se recicla
            self.cerrando = True
            await asyncio.to_thread(agones, "/shutdown")
            for ws in list(self.jugadores.values()) + list(self.espectadores):
                await ws.close(code=1000, reason="fin de la run")
        else:                                    # en local: se abre una run nueva
            for ws in list(self.jugadores.values()):
                await ws.close(code=1000, reason="fin de la run")
            self.partida = Partida(modo=self.modo, semilla=self.semilla)
            self.inicio_run = time.monotonic()

    async def bucle(self) -> None:
        siguiente = time.perf_counter()
        while not self.cerrando:
            t = time.perf_counter()
            self.tick()
            TICK.observe(time.perf_counter() - t)
            if self.n_tick % LATIDO_TICKS == 0:
                await asyncio.to_thread(agones, "/health")
            if self.partida.terminada:
                await self.terminar_run()
            # Tick de periodo fijo: se descuenta lo que tardó este tick
            siguiente += TICK_S
            await asyncio.sleep(max(0.0, siguiente - time.perf_counter()))
            if time.perf_counter() - siguiente > 1.0:   # muy atrasado: no intentar recuperar
                siguiente = time.perf_counter()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start_http_server(PUERTO_METRICAS)           # /metrics para Prometheus
    servidor = Servidor()
    async with websockets.serve(servidor.atender, "0.0.0.0", PUERTO, max_size=MAX_MENSAJE):
        servidor.con_agones = await asyncio.to_thread(agones, "/ready")
        log.info("La Torre (modo %s) en :%d, métricas en :%d, Agones: %s",
                 MODO, PUERTO, PUERTO_METRICAS, "sí" if servidor.con_agones else "no (local)")
        await servidor.bucle()


if __name__ == "__main__":
    asyncio.run(main())
