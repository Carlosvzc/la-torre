"""Entorno Gymnasium: un caballero (el agente) contra un jefe de La Torre (práctica 3.1).

Usa la lógica real del servidor (`server/juego`), así que lo que aprende el bot sirve en el
juego de verdad. Sustituye al CartPole del PDF.

- Decisión a 10 Hz: cada acción dura 2 ticks del servidor (0.1 s), como "2 000 bots a 10 Hz".
- Observación: 14 números normalizados (lo mismo que un jugador ve en el snapshot).
- Acciones (7): quieto, acercarse, alejarse, rodear a la izquierda, rodear a la derecha,
  atacar al jefe, esquivar alejándose del golpe.
- Recompensa: daño causado (+) y recibido (−), +10 al vencer, −10 al caer, −0.01 por paso.
"""
from __future__ import annotations

import math
import os
import sys

import gymnasium as gym
import numpy as np
from gymnasium import spaces

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from juego.combate import ARENA_LADO  # noqa: E402
from juego.jefes import JEFES  # noqa: E402
from juego.partida import Partida  # noqa: E402

DT = 0.05                   # un tick del servidor
TICKS_POR_DECISION = 2      # 10 decisiones por segundo
DURACION_MAX_S = 120.0      # un combate de entrenamiento no dura más de 2 min
ID = "bot"

ACCIONES = ("quieto", "acercarse", "alejarse", "rodear_izq", "rodear_der", "atacar", "esquivar")
ESTADOS_CABALLERO = ("libre", "atacando", "esquivando")
ESTADOS_JEFE = ("persiguiendo", "preparando", "recuperando")


def observar(snap: dict, mi_id: str = ID) -> np.ndarray:
    """Convierte un snapshot del servidor en el vector que ve la red (14 valores en ~[-1, 1]).

    Se usa igual en el entrenamiento y en el servidor/cliente, a partir del JSON del snapshot.
    """
    yo, jefe = snap["jugadores"][mi_id], snap["jefe"]
    dx, dy = jefe["x"] - yo["x"], jefe["y"] - yo["y"]
    dist = math.hypot(dx, dy)
    aviso = jefe.get("aviso")
    en, margen = 0.0, 1.0
    if aviso:
        en = min(aviso["en"], 1.5) / 1.5
        # distancia al borde de la zona más cercana (negativa = estoy dentro)
        borde = min(math.hypot(zx - yo["x"], zy - yo["y"]) - aviso["radio"] for zx, zy in aviso["zonas"])
        margen = max(-1.0, min(1.0, borde / 5))
    return np.array([
        dx / ARENA_LADO, dy / ARENA_LADO, dist / ARENA_LADO,
        yo["vida"] / yo["vida_max"], yo["st"] / yo["st_max"],
        *(1.0 if yo["estado"] == e else 0.0 for e in ESTADOS_CABALLERO),
        *(1.0 if jefe["estado"] == e else 0.0 for e in ESTADOS_JEFE),
        en, margen, jefe["vida"] / jefe["vida_max"],
    ], dtype=np.float32)


def accion_a_mensaje(accion: int, snap: dict, mi_id: str = ID) -> dict | None:
    """Traduce la acción de la red al mensaje que manda un cliente (mismo protocolo del juego)."""
    yo, jefe = snap["jugadores"][mi_id], snap["jefe"]
    fx, fy = jefe["x"] - yo["x"], jefe["y"] - yo["y"]
    nombre = ACCIONES[int(accion)]
    if nombre == "quieto":
        return {"accion": "mover", "dx": 0, "dy": 0}
    if nombre == "acercarse":
        return {"accion": "mover", "dx": fx, "dy": fy}
    if nombre == "alejarse":
        return {"accion": "mover", "dx": -fx, "dy": -fy}
    if nombre == "rodear_izq":
        return {"accion": "mover", "dx": -fy, "dy": fx}
    if nombre == "rodear_der":
        return {"accion": "mover", "dx": fy, "dy": -fx}
    if nombre == "atacar":
        return {"accion": "atacar", "dx": fx, "dy": fy}
    aviso = jefe.get("aviso")                       # esquivar: lejos del golpe (o hacia atrás)
    if aviso:
        zx, zy = min(aviso["zonas"], key=lambda z: math.hypot(z[0] - yo["x"], z[1] - yo["y"]))
        return {"accion": "esquivar", "dx": yo["x"] - zx, "dy": yo["y"] - zy}
    return {"accion": "esquivar", "dx": -fx, "dy": -fy}


class DueloJefe(gym.Env):
    """Un combate de un piso: el bot contra un jefe (por defecto el Guardián de Hierro)."""

    metadata = {"render_modes": []}

    def __init__(self, jefe: int = 0):
        super().__init__()
        self.indice_jefe = jefe
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(14,), dtype=np.float32)
        self.action_space = spaces.Discrete(len(ACCIONES))
        self.partida: Partida | None = None

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        semilla = int(self.np_random.integers(0, 2**31 - 1))
        self.partida = Partida(modo="torre", semilla=semilla)
        self.partida.pisos = (JEFES[self.indice_jefe],)    # un solo piso para entrenar
        self.partida.agregar_jugador(ID)
        self.partida.recibir(ID, {"accion": "listo"})
        self.partida.paso(DT)
        self.snap = self.partida.snapshot()
        return observar(self.snap), {}

    def step(self, accion):
        p = self.partida
        jefe, yo = p.jefe, p.jugadores[ID]
        vida_jefe, mi_vida = jefe.vida, yo.vida
        mensaje = accion_a_mensaje(int(accion), self.snap)
        if mensaje:
            p.recibir(ID, mensaje)
        for _ in range(TICKS_POR_DECISION):
            p.paso(DT)
            if p.terminada:
                break
        self.snap = p.snapshot()

        recompensa = (vida_jefe - jefe.vida) / 10 - (mi_vida - yo.vida) / 10 - 0.01
        terminado, truncado = False, False
        if p.estado == "victoria":
            recompensa += 10
            terminado = True
        elif p.estado == "derrota" or not yo.vivo:
            recompensa -= 10
            terminado = True
        elif p.tiempo_combate >= DURACION_MAX_S:
            truncado = True
        info = {"victoria": p.estado == "victoria", "tiempo": p.tiempo_combate,
                "vida_jefe": jefe.vida / jefe.vida_max}
        obs = observar(self.snap) if ID in self.snap["jugadores"] and self.snap["jefe"] else np.zeros(14, np.float32)
        return obs, float(recompensa), terminado, truncado, info
