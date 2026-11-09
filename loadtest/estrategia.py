"""Decisiones de un jugador simulado a partir del snapshot (lo mismo que ve un humano).

Lo usan el bot de consola (`jugar_bot.py`) y los jugadores simulados de Locust (3.4).
No toca la lógica del servidor: solo lee el JSON que llega y responde con una acción.
"""
from __future__ import annotations

import math
import random

COSTO_ATAQUE, COSTO_ESQUIVA = 20, 25
DURACION_GOLPE = 0.55          # preparación + recuperación del ataque del caballero


def decidir(snap: dict, mi_id: str, habilidad: float = 1.0,
            rng: random.Random | None = None) -> dict | None:
    """Devuelve la acción a mandar en este tick (o None).

    `habilidad` entre 0 y 1: con 1 reacciona perfecto; con menos a veces se equivoca,
    así las runs de Locust terminan en victorias y derrotas variadas.
    """
    rng = rng or random
    yo = snap.get("jugadores", {}).get(mi_id)
    if yo is None:
        return None
    estado = snap.get("estado")
    if estado == "esperando":
        return {"accion": "listo"}
    if estado == "mejora":
        ofertas = snap.get("ofertas", {}).get(mi_id)
        if ofertas:
            return {"accion": "elegir_mejora", "id": rng.choice(ofertas)["id"]}
        return None
    if estado != "combate" or yo["estado"] == "muerto":
        return None

    jefe = snap["jefe"]
    dx, dy = jefe["x"] - yo["x"], jefe["y"] - yo["y"]
    dist = math.hypot(dx, dy)
    aviso = jefe.get("aviso")

    if aviso and aviso["en"] <= 0.15 and rng.random() < habilidad:
        zx, zy = min(aviso["zonas"], key=lambda z: math.hypot(z[0] - yo["x"], z[1] - yo["y"]))
        if math.hypot(zx - yo["x"], zy - yo["y"]) <= aviso["radio"] + 2.0:
            return {"accion": "esquivar", "dx": yo["x"] - zx, "dy": yo["y"] - zy}
    if dist > 2.2:
        return {"accion": "mover", "dx": dx, "dy": dy}
    impacto_cerca = aviso is not None and aviso["en"] <= DURACION_GOLPE + 0.1
    prudente = rng.random() < habilidad
    if yo["estado"] == "libre" and yo["st"] >= COSTO_ATAQUE + COSTO_ESQUIVA \
            and not (impacto_cerca and prudente):
        return {"accion": "atacar", "dx": dx, "dy": dy}    # apunta el golpe al jefe
    return {"accion": "mover", "dx": 0, "dy": 0}
