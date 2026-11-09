"""Los jefes de la torre: su catálogo, sus fases y su IA basada en reglas.

Cada ataque tiene un aviso ("preparación"): el jefe marca dónde va a golpear y,
cuando se acaba el tiempo, golpea esa zona. Quien esté dentro sin esquivar recibe
el daño. El aviso viaja en el snapshot para que el cliente (o el bot) pueda reaccionar.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .combate import ARENA_LADO, RADIO_CABALLERO, Caballero, distancia, limitar, normalizar

PAUSA_ENTRE_ATAQUES = 0.6      # segundos que el jefe persigue antes de volver a atacar


@dataclass(frozen=True)
class Ataque:
    nombre: str
    tipo: str            # "barrido" | "golpe" | "embestida" | "lluvia"
    preparacion: float   # segundos de aviso antes del impacto
    recuperacion: float  # segundos vulnerable después del impacto
    radio: float         # radio de la zona de impacto
    dano: float
    distancia_max: float # el jefe solo lo usa si su objetivo está a esta distancia o menos


@dataclass(frozen=True)
class Fase:
    umbral: float                  # empieza cuando la vida baja de esta fracción
    ataques: tuple[Ataque, ...]
    mult_velocidad: float = 1.0
    mult_preparacion: float = 1.0  # < 1 significa avisos más cortos (más difícil)


@dataclass(frozen=True)
class DefJefe:
    id: str
    nombre: str
    vida: float
    velocidad: float
    radio: float
    fases: tuple[Fase, ...]


# --- Catálogo de ataques -----------------------------------------------------
BARRIDO = Ataque("barrido", "barrido", 0.9, 0.7, 3.0, 18, 3.0)
GOLPE = Ataque("golpe pesado", "golpe", 0.8, 0.8, 1.5, 22, 4.0)
EMBESTIDA = Ataque("embestida", "embestida", 1.0, 0.9, 1.8, 25, 12.0)
LLUVIA = Ataque("lluvia de ceniza", "lluvia", 1.1, 0.6, 1.6, 20, 14.0)
ZARPAZO = Ataque("zarpazo", "golpe", 0.5, 0.5, 1.4, 18, 3.0)
SALTO = Ataque("salto feroz", "embestida", 0.7, 0.7, 1.6, 24, 12.0)

# --- Los 4 jefes de la torre (nombres y diseño originales) ---------------------
JEFES: tuple[DefJefe, ...] = (
    DefJefe("guardian", "Guardián de Hierro", 300, 2.5, 1.2, (
        Fase(1.0, (BARRIDO, GOLPE)),
        Fase(0.5, (BARRIDO, GOLPE, EMBESTIDA), 1.2, 0.85),
    )),
    DefJefe("bruja", "Bruja de Ceniza", 280, 3.0, 1.0, (
        Fase(1.0, (LLUVIA, BARRIDO)),
        Fase(0.6, (LLUVIA, BARRIDO, GOLPE), 1.3, 0.8),
    )),
    DefJefe("sabueso", "Sabueso Abismal", 320, 4.2, 1.0, (
        Fase(1.0, (SALTO, ZARPAZO)),
        Fase(0.5, (SALTO, ZARPAZO, BARRIDO), 1.25, 0.8),
    )),
    DefJefe("rey", "Rey sin Corona", 420, 3.2, 1.3, (
        Fase(1.0, (GOLPE, BARRIDO)),
        Fase(0.66, (GOLPE, BARRIDO, LLUVIA), 1.1, 0.9),
        Fase(0.33, (GOLPE, BARRIDO, LLUVIA, EMBESTIDA), 1.3, 0.75),
    )),
)

# Jefe del día: igual para todos; se usa en el modo jefe_dia y en la prueba de pico
JEFE_DEL_DIA = DefJefe("coloso", "Coloso del Eclipse", 600, 3.0, 1.5, (
    Fase(1.0, (BARRIDO, GOLPE, LLUVIA)),
    Fase(0.5, (BARRIDO, GOLPE, LLUVIA, EMBESTIDA, ZARPAZO), 1.3, 0.75),
))


def escalado(piso: int, jugadores: int) -> tuple[float, float, float]:
    """Multiplicadores (vida, daño, velocidad) según el piso (0–3) y los jugadores (1–4)."""
    vida = (1 + 0.4 * piso) * (1 + 0.7 * (max(1, jugadores) - 1))
    dano = 1 + 0.15 * piso
    velocidad = 1 + 0.08 * piso
    return vida, dano, velocidad


@dataclass
class Jefe:
    """Un jefe en combate: estado y decisiones tick a tick."""

    definicion: DefJefe
    vida_max: float
    mult_dano: float
    mult_velocidad: float
    x: float = ARENA_LADO / 2
    y: float = ARENA_LADO - 4.0
    vida: float = 0.0
    estado: str = "persiguiendo"   # "persiguiendo" | "preparando" | "recuperando" | "muerto"
    temporizador: float = PAUSA_ENTRE_ATAQUES
    ataque: Ataque | None = None
    zonas: list[tuple[float, float]] = field(default_factory=list)  # dónde caerá el golpe
    fase: int = 0

    @classmethod
    def crear(cls, definicion: DefJefe, piso: int, jugadores: int) -> "Jefe":
        m_vida, m_dano, m_vel = escalado(piso, jugadores)
        vida = definicion.vida * m_vida
        return cls(definicion, vida, m_dano, m_vel, vida=vida)

    @property
    def vivo(self) -> bool:
        return self.estado != "muerto"

    @property
    def fase_actual(self) -> Fase:
        return self.definicion.fases[self.fase]

    def _actualizar_fase(self) -> None:
        fraccion = self.vida / self.vida_max
        for i, fase in enumerate(self.definicion.fases):
            if fraccion <= fase.umbral + 1e-9:
                self.fase = max(self.fase, i)

    def recibir_dano(self, cantidad: float) -> float:
        if not self.vivo:
            return 0.0
        real = min(self.vida, cantidad)
        self.vida -= real
        if self.vida <= 0:
            self.estado, self.ataque, self.zonas = "muerto", None, []
        else:
            self._actualizar_fase()
        return real

    # --- IA por reglas ----------------------------------------------------
    def _objetivo(self, caballeros: list[Caballero]) -> Caballero | None:
        vivos = [c for c in caballeros if c.vivo]
        if not vivos:
            return None
        return min(vivos, key=lambda c: distancia(self.x, self.y, c.x, c.y))

    def paso(self, dt: float, caballeros: list[Caballero], rng: random.Random) -> list[dict]:
        """Avanza el jefe `dt` segundos. Devuelve los eventos de impacto de este tick."""
        if not self.vivo:
            return []
        objetivo = self._objetivo(caballeros)
        if objetivo is None:
            return []
        fase = self.fase_actual
        self.temporizador -= dt

        if self.estado == "persiguiendo":
            d = distancia(self.x, self.y, objetivo.x, objetivo.y)
            posibles = [a for a in fase.ataques if d <= a.distancia_max]
            if self.temporizador <= 0 and posibles:
                self._iniciar_ataque(rng.choice(posibles), objetivo, caballeros, fase)
            elif d > self.definicion.radio + 1.5:
                dx, dy = normalizar(objetivo.x - self.x, objetivo.y - self.y)
                v = self.definicion.velocidad * self.mult_velocidad * fase.mult_velocidad
                self._mover(dx * v * dt, dy * v * dt)
            return []

        if self.estado == "preparando" and self.temporizador <= 0:
            eventos = self._impactar(caballeros)
            self.estado, self.temporizador = "recuperando", self.ataque.recuperacion
            return eventos

        if self.estado == "recuperando" and self.temporizador <= 0:
            self.estado, self.ataque, self.zonas = "persiguiendo", None, []
            self.temporizador = PAUSA_ENTRE_ATAQUES * fase.mult_preparacion
        return []

    def _iniciar_ataque(self, ataque: Ataque, objetivo: Caballero,
                        caballeros: list[Caballero], fase: Fase) -> None:
        self.ataque, self.estado = ataque, "preparando"
        self.temporizador = ataque.preparacion * fase.mult_preparacion
        if ataque.tipo == "barrido":
            self.zonas = [(self.x, self.y)]
        elif ataque.tipo == "lluvia":                    # una zona sobre cada jugador vivo
            self.zonas = [(c.x, c.y) for c in caballeros if c.vivo]
        else:                                            # golpe y embestida: donde está el objetivo
            self.zonas = [(objetivo.x, objetivo.y)]

    def _impactar(self, caballeros: list[Caballero]) -> list[dict]:
        ataque = self.ataque
        if ataque.tipo == "embestida":                   # el jefe se lanza a la zona marcada
            self.x, self.y = self.zonas[0]
            self._mover(0, 0)
        eventos = []
        for c in caballeros:
            if not c.vivo:
                continue
            if any(distancia(zx, zy, c.x, c.y) <= ataque.radio + RADIO_CABALLERO
                   for zx, zy in self.zonas):
                real = c.recibir_dano(ataque.dano * self.mult_dano)
                eventos.append({"tipo": "impacto", "ataque": ataque.nombre,
                                "jugador": c.id, "dano": round(real, 1)})
        return eventos

    def _mover(self, dx: float, dy: float) -> None:
        r = self.definicion.radio
        self.x = limitar(self.x + dx, r, ARENA_LADO - r)
        self.y = limitar(self.y + dy, r, ARENA_LADO - r)

    def resumen(self) -> dict:
        datos = {
            "id": self.definicion.id, "nombre": self.definicion.nombre,
            "x": round(self.x, 2), "y": round(self.y, 2),
            "vida": round(self.vida, 1), "vida_max": round(self.vida_max, 1),
            "estado": self.estado, "fase": self.fase + 1,
        }
        if self.estado == "preparando":                 # el aviso que permite esquivar
            datos["aviso"] = {
                "ataque": self.ataque.nombre, "radio": self.ataque.radio,
                "zonas": [[round(x, 2), round(y, 2)] for x, y in self.zonas],
                "en": round(max(0.0, self.temporizador), 2),
            }
        return datos
