"""Mejoras que el servidor ofrece al vencer a cada jefe (3 al azar por jugador)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .combate import DEFENSA_MAXIMA, Caballero


@dataclass(frozen=True)
class Mejora:
    id: str
    nombre: str
    descripcion: str
    aplicar: Callable[[Caballero], None]


def _mas_vida(c: Caballero) -> None:
    c.vida_max += 25
    c.vida += 25


def _defensa(c: Caballero) -> None:
    c.defensa = min(DEFENSA_MAXIMA, c.defensa + 0.10)


def _curar(c: Caballero) -> None:
    c.curar(c.vida_max * 0.5)


def _stamina(c: Caballero) -> None:
    c.stamina_max += 20
    c.stamina = c.stamina_max


CATALOGO: dict[str, Mejora] = {m.id: m for m in (
    Mejora("filo", "Filo templado", "+20 % de daño",
           lambda c: setattr(c, "dano", c.dano * 1.20)),
    Mejora("vigor", "Vigor", "+25 de vida máxima", _mas_vida),
    Mejora("aguante", "Aguante", "+20 de resistencia máxima", _stamina),
    Mejora("aliento", "Aliento", "+25 % de regeneración de resistencia",
           lambda c: setattr(c, "regen_mult", c.regen_mult * 1.25)),
    Mejora("coraza", "Coraza", "+10 % de defensa (máximo 60 %)", _defensa),
    Mejora("respiro", "Respiro", "Recupera 50 % de la vida", _curar),
    Mejora("ligereza", "Ligereza", "La esquiva cuesta 20 % menos",
           lambda c: setattr(c, "costo_esquiva_mult", c.costo_esquiva_mult * 0.8)),
    Mejora("sangria", "Sangría", "Cura 5 % del daño que causas",
           lambda c: setattr(c, "robo_vida", c.robo_vida + 0.05)),
    Mejora("zancada", "Zancada", "+10 % de velocidad",
           lambda c: setattr(c, "velocidad", c.velocidad * 1.10)),
)}


def sortear(rng: random.Random, n: int = 3) -> list[str]:
    """Elige `n` mejoras distintas al azar."""
    return rng.sample(sorted(CATALOGO), n)


def aplicar(caballero: Caballero, mejora_id: str) -> Mejora:
    mejora = CATALOGO[mejora_id]
    mejora.aplicar(caballero)
    return mejora


def describir(ids: list[str]) -> list[dict]:
    """Formato que se manda al cliente para mostrar las opciones."""
    return [{"id": i, "nombre": CATALOGO[i].nombre, "descripcion": CATALOGO[i].descripcion}
            for i in ids]
