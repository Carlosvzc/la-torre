"""Reglas de combate del caballero: vida, resistencia (stamina), ataque y esquiva.

Todo avanza en pasos de tiempo fijos (`dt`, normalmente 0.05 s = 20 ticks/s).
El servidor es autoritativo: el cliente solo pide acciones y aquí se decide si
se pueden hacer, cuánto cuestan y cuánto daño causan.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- Arena -----------------------------------------------------------------
ARENA_LADO = 20.0          # la arena es un cuadrado de 20 x 20 unidades
RADIO_CABALLERO = 0.5

# --- Costos y tiempos de las acciones (en segundos y puntos) -------------------
COSTO_ATAQUE = 20.0
PREPARACION_ATAQUE = 0.30  # tiempo desde que se pulsa hasta que el golpe conecta
RECUPERACION_ATAQUE = 0.25 # tiempo tras el golpe en que no se puede actuar
ALCANCE_ATAQUE = 2.0

COSTO_ESQUIVA = 25.0
DURACION_ESQUIVA = 0.40
INVULNERABLE_ESQUIVA = 0.30  # i-frames: los primeros 0.3 s de la esquiva
DISTANCIA_ESQUIVA = 3.5

REGEN_STAMINA = 30.0       # puntos por segundo
ESPERA_REGEN = 0.5         # segundos sin gastar stamina antes de regenerar
DEFENSA_MAXIMA = 0.6       # nunca se reduce más del 60 % del daño


def limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def normalizar(dx: float, dy: float) -> tuple[float, float]:
    """Devuelve el vector unitario (o (0, 0) si no hay dirección)."""
    largo = math.hypot(dx, dy)
    if largo < 1e-9:
        return 0.0, 0.0
    return dx / largo, dy / largo


def distancia(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


@dataclass
class Caballero:
    """Estado completo de un jugador. Las mejoras modifican estos atributos."""

    id: str
    x: float = ARENA_LADO / 2
    y: float = 3.0
    vida_max: float = 100.0
    vida: float = 100.0
    stamina_max: float = 100.0
    stamina: float = 100.0
    dano: float = 15.0
    defensa: float = 0.0            # fracción de daño que se ignora (0.0 a 0.6)
    velocidad: float = 5.0          # unidades por segundo
    regen_mult: float = 1.0         # multiplicador de la regeneración de stamina
    costo_esquiva_mult: float = 1.0
    robo_vida: float = 0.0          # fracción del daño causado que cura

    # Estado de la acción en curso: "libre", "atacando", "esquivando" o "muerto"
    estado: str = "libre"
    temporizador: float = 0.0       # tiempo restante de la acción en curso
    golpe_pendiente: bool = False   # el ataque todavía no conecta
    dir_x: float = 0.0              # hacia dónde mira / se esquiva
    dir_y: float = 1.0
    sin_gastar: float = 0.0         # segundos desde el último gasto de stamina
    intencion_x: float = 0.0        # dirección que el jugador mantiene pulsada
    intencion_y: float = 0.0
    accion_en_cola: dict | None = field(default=None, repr=False)

    # Estadísticas de la run
    dano_causado: float = 0.0
    dano_recibido: float = 0.0
    esquivas_exitosas: int = 0

    # ------------------------------------------------------------------
    @property
    def vivo(self) -> bool:
        return self.estado != "muerto"

    @property
    def invulnerable(self) -> bool:
        transcurrido = DURACION_ESQUIVA - self.temporizador
        return self.estado == "esquivando" and transcurrido < INVULNERABLE_ESQUIVA

    def gastar(self, costo: float) -> bool:
        """Gasta stamina si alcanza. Devuelve False si no hay suficiente."""
        if self.stamina < costo:
            return False
        self.stamina -= costo
        self.sin_gastar = 0.0
        return True

    # --- Acciones que pide el cliente ----------------------------------
    def fijar_movimiento(self, dx: float, dy: float) -> None:
        self.intencion_x, self.intencion_y = normalizar(dx, dy)

    def pedir(self, accion: dict) -> None:
        """Guarda una acción (atacar/esquivar) para ejecutarla en cuanto se pueda.

        Solo se guarda una: la última que llegue reemplaza a la anterior.
        """
        if self.vivo:
            self.accion_en_cola = accion

    def _intentar_accion(self) -> None:
        accion, self.accion_en_cola = self.accion_en_cola, None
        if accion is None:
            return
        tipo = accion.get("accion")
        if tipo == "atacar" and self.gastar(COSTO_ATAQUE):
            self.estado = "atacando"
            self.temporizador = PREPARACION_ATAQUE + RECUPERACION_ATAQUE
            self.golpe_pendiente = True
        elif tipo == "esquivar" and self.gastar(COSTO_ESQUIVA * self.costo_esquiva_mult):
            dx, dy = normalizar(accion.get("dx", 0.0), accion.get("dy", 0.0))
            if (dx, dy) == (0.0, 0.0):          # sin dirección: hacia atrás
                dx, dy = -self.dir_x, -self.dir_y
            self.dir_x, self.dir_y = dx, dy
            self.estado = "esquivando"
            self.temporizador = DURACION_ESQUIVA

    # --- Simulación -----------------------------------------------------
    def paso(self, dt: float) -> bool:
        """Avanza el caballero `dt` segundos.

        Devuelve True en el tick exacto en que su ataque conecta, para que la
        partida compruebe si alcanzó al jefe.
        """
        if not self.vivo:
            return False

        conecta = False
        if self.estado == "libre":
            self._intentar_accion()

        if self.estado == "libre":
            if self.intencion_x or self.intencion_y:
                self.dir_x, self.dir_y = self.intencion_x, self.intencion_y
                self._mover(self.intencion_x * self.velocidad * dt,
                            self.intencion_y * self.velocidad * dt)
        elif self.estado == "esquivando":
            rapidez = DISTANCIA_ESQUIVA / DURACION_ESQUIVA
            self._mover(self.dir_x * rapidez * dt, self.dir_y * rapidez * dt)
            self.temporizador -= dt
        elif self.estado == "atacando":
            self.temporizador -= dt
            if self.golpe_pendiente and self.temporizador <= RECUPERACION_ATAQUE + 1e-9:
                self.golpe_pendiente = False
                conecta = True

        if self.estado in ("atacando", "esquivando") and self.temporizador <= 1e-9:
            self.estado, self.temporizador = "libre", 0.0

        # Regeneración de stamina: solo si no está atacando ni esquivando
        self.sin_gastar += dt
        if self.estado == "libre" and self.sin_gastar >= ESPERA_REGEN:
            self.stamina = min(self.stamina_max,
                               self.stamina + REGEN_STAMINA * self.regen_mult * dt)
        return conecta

    def _mover(self, dx: float, dy: float) -> None:
        self.x = limitar(self.x + dx, RADIO_CABALLERO, ARENA_LADO - RADIO_CABALLERO)
        self.y = limitar(self.y + dy, RADIO_CABALLERO, ARENA_LADO - RADIO_CABALLERO)

    def recibir_dano(self, cantidad: float) -> float:
        """Aplica daño respetando la esquiva y la defensa. Devuelve el daño real."""
        if not self.vivo:
            return 0.0
        if self.invulnerable:
            self.esquivas_exitosas += 1
            return 0.0
        real = cantidad * (1.0 - limitar(self.defensa, 0.0, DEFENSA_MAXIMA))
        self.vida = max(0.0, self.vida - real)
        self.dano_recibido += real
        if self.vida <= 0:
            self.estado, self.temporizador = "muerto", 0.0
            self.accion_en_cola = None
        return real

    def curar(self, cantidad: float) -> None:
        if self.vivo:
            self.vida = min(self.vida_max, self.vida + cantidad)

    def revivir(self, fraccion: float) -> None:
        """Vuelve a la vida con una fracción de su vida máxima (cooperativo)."""
        self.estado, self.temporizador = "libre", 0.0
        self.vida = max(1.0, self.vida_max * fraccion)
        self.stamina = self.stamina_max

    def resumen(self) -> dict:
        """Lo que se manda al cliente en cada snapshot (redondeado para ahorrar bytes)."""
        return {
            "x": round(self.x, 2), "y": round(self.y, 2),
            "dx": round(self.dir_x, 2), "dy": round(self.dir_y, 2),
            "vida": round(self.vida, 1), "vida_max": round(self.vida_max, 1),
            "st": round(self.stamina, 1), "st_max": round(self.stamina_max, 1),
            "estado": self.estado,
        }
