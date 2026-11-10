"""Decisiones de un jugador simulado a partir del snapshot (lo mismo que ve un humano).

Lo usan el bot de consola (`jugar_bot.py`), los jugadores simulados de Locust (3.4) y las
pruebas de balance. No toca la lógica del servidor: solo lee el JSON que llega y responde
con una acción. Sabe jugar las 4 clases: cuerpo a cuerpo (caballero, bárbaro) se pega al
jefe; a distancia (cazadora, hechicero) mantiene la distancia y huye si el jefe se acerca.
"""
from __future__ import annotations

import math
import random

# Por clase: distancia a la que le gusta pelear, duración de su ataque (para no comprometerse
# antes de un impacto), costos de ataque y esquiva, y alcance máximo.
ESTILO = {
    "caballero": {"distancia": 2.2, "golpe": 0.55, "ataque": 20, "esquiva": 25, "alcance": 2.0},
    "barbaro":   {"distancia": 2.5, "golpe": 0.72, "ataque": 30, "esquiva": 30, "alcance": 2.4},
    "cazadora":  {"distancia": 6.5, "golpe": 0.36, "ataque": 12, "esquiva": 18, "alcance": 10.0},
    "hechicero": {"distancia": 6.0, "golpe": 0.55, "ataque": 25, "esquiva": 30, "alcance": 9.0},
}
CLASES = tuple(ESTILO)


def _habilidad_conviene(clase: str, yo: dict, jefe: dict, dist: float, aviso: dict | None,
                        en_zona: bool) -> bool:
    if yo.get("recarga", 0) > 0 or yo["estado"] != "libre":
        return False
    if clase == "caballero":       # muro de escudo solo si va a recibir un golpe y NO le alcanza para esquivar
        return bool(aviso) and en_zona and aviso["en"] <= 0.6 and 20 <= yo["st"] < ESTILO[clase]["esquiva"]
    if clase == "barbaro":         # grito de guerra al llegar al jefe
        return dist <= 4.0
    if clase == "cazadora":        # disparo perforante (1.2 s) solo mientras el jefe se recupera
        return jefe["estado"] == "recuperando" and dist <= 9.0 and yo["st"] >= 30 + ESTILO[clase]["esquiva"]
    if clase == "hechicero":       # nova cuando el jefe se le echa encima
        return dist <= 3.2 and yo["st"] >= 35
    return False


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

    clase = yo.get("clase", "caballero")
    estilo = ESTILO.get(clase, ESTILO["caballero"])
    jefe = snap["jefe"]
    dx, dy = jefe["x"] - yo["x"], jefe["y"] - yo["y"]
    dist = math.hypot(dx, dy)
    aviso = jefe.get("aviso")
    en_zona = bool(aviso) and any(math.hypot(zx - yo["x"], zy - yo["y"]) <= aviso["radio"] + 2.0
                                  for zx, zy in aviso["zonas"])

    # 1. Esquivar justo antes del impacto
    if aviso and aviso["en"] <= 0.15 and en_zona and rng.random() < habilidad:
        zx, zy = min(aviso["zonas"], key=lambda z: math.hypot(z[0] - yo["x"], z[1] - yo["y"]))
        return {"accion": "esquivar", "dx": yo["x"] - zx, "dy": yo["y"] - zy}
    # 2. Habilidad de la clase
    if _habilidad_conviene(clase, yo, jefe, dist, aviso, en_zona) and rng.random() < habilidad:
        return {"accion": "habilidad", "dx": dx, "dy": dy}
    # 3. Posicionarse: los de cuerpo a cuerpo se acercan; los de distancia guardan espacio
    alcance_real = estilo["alcance"] + jefe.get("radio", 1.0)      # se mide hasta el borde del jefe
    if dist > min(estilo["distancia"], alcance_real - 0.5) + 0.3:
        return {"accion": "mover", "dx": dx, "dy": dy}
    if estilo["distancia"] > 3 and dist < estilo["distancia"] - 2.0:
        # huye del jefe; si va a chocar con un muro, rodea (de lado)
        hx, hy = -dx, -dy
        if not (1.5 < yo["x"] + hx / max(dist, 1e-6) * 2 < 18.5 and 1.5 < yo["y"] + hy / max(dist, 1e-6) * 2 < 18.5):
            hx, hy = -dy, dx
        return {"accion": "mover", "dx": hx, "dy": hy}
    # 4. Atacar si no hay un impacto a punto de caer
    impacto_cerca = aviso is not None and aviso["en"] <= estilo["golpe"] + 0.1 and en_zona
    prudente = rng.random() < habilidad
    # los golpes lentos se reservan para la ventana de castigo (el jefe se recupera)
    if estilo["golpe"] > 0.6 and jefe["estado"] == "preparando" and prudente:
        return {"accion": "mover", "dx": 0, "dy": 0}
    if yo["estado"] == "libre" and yo["st"] >= estilo["ataque"] + estilo["esquiva"] \
            and not (impacto_cerca and prudente):
        return {"accion": "atacar", "dx": dx, "dy": dy}    # apunta el golpe al jefe
    return {"accion": "mover", "dx": 0, "dy": 0}
