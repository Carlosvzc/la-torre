"""Una run de la torre: de la sala de espera a la victoria o la derrota.

Estados:
    esperando → combate → mejora → combate → ... → victoria | derrota | abandonada

No sabe nada de la red: `server.py` le pasa los mensajes de los jugadores y le
pide un snapshot en cada tick. Así se puede probar entera con pytest.
"""
from __future__ import annotations

import random

from . import mejoras
from .combate import ALCANCE_ATAQUE, ARENA_LADO, Caballero, distancia
from .jefes import JEFE_DEL_DIA, JEFES, DefJefe, Jefe

MAX_JUGADORES = 4             # cooperativo de 1 a 4
ESPERA_INICIO = 15.0          # si no todos dicen "listo", la run empieza sola
ESPERA_MEJORA = 20.0          # tiempo para elegir mejora; luego se elige la primera
DURACION_MAXIMA = 15 * 60.0   # una run no puede ocupar un servidor para siempre
VIDA_AL_REVIVIR = 0.3         # en cooperativo, los caídos vuelven al vencer al jefe

TERMINALES = ("victoria", "derrota", "abandonada")


class Partida:
    def __init__(self, modo: str = "torre", semilla: int | None = None,
                 max_jugadores: int = MAX_JUGADORES):
        if modo not in ("torre", "jefe_dia"):
            raise ValueError(f"modo desconocido: {modo}")
        self.modo = modo
        self.rng = random.Random(semilla)
        self.max_jugadores = max_jugadores
        self.pisos: tuple[DefJefe, ...] = JEFES if modo == "torre" else (JEFE_DEL_DIA,)
        self.jugadores: dict[str, Caballero] = {}
        self.listos: set[str] = set()
        self.estado = "esperando"
        self.piso = 0
        self.jefe: Jefe | None = None
        self.ofertas: dict[str, list[str]] = {}
        self.elegidas: dict[str, str] = {}
        self.tiempo_total = 0.0
        self.tiempo_combate = 0.0     # lo que cuenta para la tabla de líderes
        self.temporizador = 0.0
        self.eventos: list[dict] = []
        self.motivo_fin = ""

    # --- Jugadores ---------------------------------------------------------
    @property
    def terminada(self) -> bool:
        return self.estado in TERMINALES

    def agregar_jugador(self, jugador_id: str) -> bool:
        """Solo se entra en la sala de espera y mientras haya lugar."""
        if (self.estado != "esperando" or jugador_id in self.jugadores
                or len(self.jugadores) >= self.max_jugadores):
            return False
        if not self.jugadores:
            self.temporizador = ESPERA_INICIO
        self.jugadores[jugador_id] = Caballero(jugador_id)
        self._evento("entra", jugador=jugador_id)
        return True

    def quitar_jugador(self, jugador_id: str) -> None:
        if self.jugadores.pop(jugador_id, None) is None:
            return
        self.listos.discard(jugador_id)
        self.ofertas.pop(jugador_id, None)
        self.elegidas.pop(jugador_id, None)
        self._evento("sale", jugador=jugador_id)
        if not self.jugadores and not self.terminada:
            self._terminar("abandonada", "todos los jugadores se fueron")

    def recibir(self, jugador_id: str, msg: dict) -> None:
        """Procesa una acción del cliente. Lo inválido se ignora en silencio."""
        c = self.jugadores.get(jugador_id)
        if c is None or self.terminada:
            return
        accion = msg.get("accion")
        if accion == "listo" and self.estado == "esperando":
            self.listos.add(jugador_id)
        elif accion == "mover":
            c.fijar_movimiento(float(msg.get("dx", 0)), float(msg.get("dy", 0)))
        elif accion in ("atacar", "esquivar") and self.estado == "combate":
            c.pedir({"accion": accion, "dx": float(msg.get("dx", 0)),
                     "dy": float(msg.get("dy", 0))})
        elif accion == "elegir_mejora" and self.estado == "mejora":
            if msg.get("id") in self.ofertas.get(jugador_id, []) and jugador_id not in self.elegidas:
                self.elegidas[jugador_id] = msg["id"]

    # --- Simulación --------------------------------------------------------
    def paso(self, dt: float) -> None:
        if self.terminada:
            return
        self.tiempo_total += dt
        if self.tiempo_total >= DURACION_MAXIMA:
            self._terminar("derrota", "tiempo agotado")
            return
        if self.estado == "esperando":
            self.temporizador -= dt
            todos_listos = self.jugadores and self.listos >= set(self.jugadores)
            if todos_listos or (self.jugadores and self.temporizador <= 0):
                self._iniciar_piso()
        elif self.estado == "combate":
            self._paso_combate(dt)
        elif self.estado == "mejora":
            self.temporizador -= dt
            if set(self.elegidas) >= set(self.ofertas) or self.temporizador <= 0:
                self._aplicar_mejoras()
                self.piso += 1
                self._iniciar_piso()

    def _paso_combate(self, dt: float) -> None:
        self.tiempo_combate += dt
        jefe = self.jefe
        alcance = ALCANCE_ATAQUE + jefe.definicion.radio
        for c in self.jugadores.values():
            if c.paso(dt) and distancia(c.x, c.y, jefe.x, jefe.y) <= alcance:
                real = jefe.recibir_dano(c.dano)
                c.dano_causado += real
                c.curar(real * c.robo_vida)
                self._evento("golpe", jugador=c.id, dano=round(real, 1))
        self.eventos += jefe.paso(dt, list(self.jugadores.values()), self.rng)

        if not jefe.vivo:
            self._evento("jefe_vencido", jefe=jefe.definicion.id, piso=self.piso + 1)
            if self.piso + 1 >= len(self.pisos):
                self._terminar("victoria", "la torre fue conquistada")
            else:
                self._ofrecer_mejoras()
        elif not any(c.vivo for c in self.jugadores.values()):
            self._terminar("derrota", f"caídos ante {jefe.definicion.nombre}")

    def _iniciar_piso(self) -> None:
        n = len(self.jugadores)
        self.jefe = Jefe.crear(self.pisos[self.piso], self.piso, n)
        separacion = ARENA_LADO / (n + 1)
        for i, c in enumerate(self.jugadores.values()):     # todos vuelven a la entrada
            c.x, c.y = separacion * (i + 1), 3.0
            c.fijar_movimiento(0, 0)
            c.stamina = c.stamina_max
        self.estado = "combate"
        self._evento("piso", piso=self.piso + 1, jefe=self.jefe.definicion.nombre)

    def _ofrecer_mejoras(self) -> None:
        self.estado, self.temporizador = "mejora", ESPERA_MEJORA
        self.elegidas = {}
        self.ofertas = {}
        for c in self.jugadores.values():
            if not c.vivo:
                c.revivir(VIDA_AL_REVIVIR)
            self.ofertas[c.id] = mejoras.sortear(self.rng)

    def _aplicar_mejoras(self) -> None:
        for jugador_id, ofertas in self.ofertas.items():
            c = self.jugadores.get(jugador_id)
            if c is not None:
                mejoras.aplicar(c, self.elegidas.get(jugador_id, ofertas[0]))
        self.ofertas, self.elegidas = {}, {}

    def _terminar(self, estado: str, motivo: str) -> None:
        self.estado, self.motivo_fin = estado, motivo
        self._evento("fin", resultado=estado, motivo=motivo)

    def _evento(self, tipo: str, **datos) -> None:
        self.eventos.append({"tipo": tipo, **datos})

    # --- Salidas -------------------------------------------------------------
    def snapshot(self) -> dict:
        """Estado que se transmite a jugadores y espectadores. Vacía los eventos."""
        datos = {
            "modo": self.modo, "estado": self.estado,
            "piso": self.piso + 1, "pisos": len(self.pisos),
            "t": round(self.tiempo_combate, 2),
            "jugadores": {i: c.resumen() for i, c in self.jugadores.items()},
            "jefe": self.jefe.resumen() if self.jefe else None,
            "eventos": self.eventos,
        }
        if self.estado == "esperando":
            datos["inicio_en"] = round(max(0.0, self.temporizador), 1)
        if self.estado == "mejora":
            datos["ofertas"] = {i: mejoras.describir(o) for i, o in self.ofertas.items()}
            datos["elegir_en"] = round(max(0.0, self.temporizador), 1)
        self.eventos = []
        return datos

    def resultado(self) -> dict:
        """Resumen para la tabla de líderes (se manda al terminar la run)."""
        victoria = self.estado == "victoria"
        return {
            "modo": self.modo,
            "victoria": victoria,
            "pisos_superados": self.piso + (1 if victoria else 0),
            "tiempo_s": round(self.tiempo_combate, 2),
            "jugadores": sorted(self.jugadores),
            "motivo": self.motivo_fin,
        }
