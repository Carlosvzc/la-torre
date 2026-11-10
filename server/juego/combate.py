"""Reglas de combate de los jugadores: clases, vida, resistencia, ataque, esquiva y habilidad.

Todo avanza en pasos de tiempo fijos (`dt`, normalmente 0.05 s = 20 ticks/s).
El servidor es autoritativo: el cliente solo pide acciones y aquí se decide si
se pueden hacer, cuánto cuestan y cuánto daño causan.

Hay 4 clases (`CLASES`) con un estilo de juego distinto. `Caballero(id)` crea un caballero
(la clase equilibrada); `nuevo_jugador(id, clase)` crea cualquiera de las cuatro.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- Arena -----------------------------------------------------------------
ARENA_LADO = 20.0          # la arena es un cuadrado de 20 x 20 unidades
RADIO_CABALLERO = 0.5

# --- Valores del caballero (la clase de referencia) ----------------------------
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

COS_CONO_ATAQUE = math.cos(math.radians(75))   # el tajo alcanza en un cono de ±75° al frente

# --- Habilidades (tecla K): efectos y duraciones -------------------------------
MURO_DURACION, MURO_REDUCCION = 2.0, 0.75      # Muro de escudo: 75 % menos daño durante 2 s
GRITO_ANIMACION, GRITO_DURACION = 0.6, 6.0     # Grito de guerra
GRITO_DANO, GRITO_REGEN = 1.4, 2.0
FURIA_UMBRAL, FURIA_DANO = 0.4, 1.5            # Bárbaro con menos de 40 % de vida: +50 % de daño
PIEL_CURTIDA = 0.15                            # Bárbaro: 15 % de defensa de base
ARMADURA = 0.10                                # Caballero: 10 % de defensa de base
TIRO_CARGA, TIRO_RECUPERACION, TIRO_DANO = 1.0, 0.2, 40.0   # Disparo perforante
LEJOS_DISTANCIA, LEJOS_DANO = 5.0, 1.2         # Cazadora: +20 % de daño a más de 5 unidades
NOVA_ANIMACION, NOVA_RADIO, NOVA_DANO, NOVA_LENTITUD = 0.45, 3.5, 15.0, 4.0
BOLA_VUELO, BOLA_RADIO = 0.35, 1.2             # Bola de fuego: tarda 0.35 s y estalla en 1.2 de radio


@dataclass(frozen=True)
class Clase:
    id: str
    nombre: str
    descripcion: str
    vida: float
    stamina: float
    dano: float
    velocidad: float
    ataque: str               # "tajo" (cuerpo a cuerpo) | "flecha" (a distancia) | "bola" (zona con retraso)
    costo_ataque: float
    preparacion: float
    recuperacion: float
    alcance: float
    cono_grados: float        # medio ángulo del cono en el que alcanza el ataque
    esquiva: str              # "voltereta" (se desplaza rodando) | "destello" (teletransporte)
    costo_esquiva: float
    duracion_esquiva: float
    invulnerable_esquiva: float
    distancia_esquiva: float
    habilidad: str            # "muro" | "grito" | "tiro" | "nova"
    nombre_habilidad: str
    costo_habilidad: float
    recarga_habilidad: float

    def publico(self) -> dict:
        """Lo que necesita el cliente para dibujar y animar la clase (tiempos incluidos)."""
        return {k: v for k, v in self.__dict__.items()}


CLASES: dict[str, Clase] = {c.id: c for c in (
    Clase("caballero", "Caballero", "Equilibrado y resistente: armadura completa, tajo rápido, voltereta y muro de escudo.",
          vida=110, stamina=100, dano=17, velocidad=5.0,
          ataque="tajo", costo_ataque=COSTO_ATAQUE, preparacion=PREPARACION_ATAQUE,
          recuperacion=RECUPERACION_ATAQUE, alcance=ALCANCE_ATAQUE, cono_grados=75,
          esquiva="voltereta", costo_esquiva=COSTO_ESQUIVA, duracion_esquiva=DURACION_ESQUIVA,
          invulnerable_esquiva=INVULNERABLE_ESQUIVA, distancia_esquiva=DISTANCIA_ESQUIVA,
          habilidad="muro", nombre_habilidad="Muro de escudo", costo_habilidad=20, recarga_habilidad=10),
    Clase("barbaro", "Bárbaro", "Lento y brutal: hachazo enorme, piel curtida, furia con poca vida y grito de guerra.",
          vida=135, stamina=110, dano=32, velocidad=4.5,
          ataque="tajo", costo_ataque=30, preparacion=0.42, recuperacion=0.30, alcance=2.4, cono_grados=100,
          esquiva="voltereta", costo_esquiva=30, duracion_esquiva=0.45, invulnerable_esquiva=0.28,
          distancia_esquiva=3.0,
          habilidad="grito", nombre_habilidad="Grito de guerra", costo_habilidad=0, recarga_habilidad=16),
    Clase("cazadora", "Cazadora", "A distancia y frágil: flechas rápidas, voltereta larga y disparo perforante.",
          vida=80, stamina=100, dano=10, velocidad=5.6,
          ataque="flecha", costo_ataque=12, preparacion=0.22, recuperacion=0.14, alcance=10.0, cono_grados=30,
          esquiva="voltereta", costo_esquiva=18, duracion_esquiva=0.38, invulnerable_esquiva=0.28,
          distancia_esquiva=4.5,
          habilidad="tiro", nombre_habilidad="Disparo perforante", costo_habilidad=30, recarga_habilidad=9),
    Clase("hechicero", "Hechicero", "Magia de zona: la bola de fuego tarda en llegar, destello y nova de escarcha.",
          vida=75, stamina=120, dano=24, velocidad=4.8,
          ataque="bola", costo_ataque=25, preparacion=0.35, recuperacion=0.20, alcance=9.0, cono_grados=180,
          esquiva="destello", costo_esquiva=30, duracion_esquiva=0.25, invulnerable_esquiva=0.20,
          distancia_esquiva=4.0,
          habilidad="nova", nombre_habilidad="Nova de escarcha", costo_habilidad=35, recarga_habilidad=14),
)}


def limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def numero_seguro(valor, defecto: float = 0.0) -> float:
    """Convierte lo que mande el cliente a un número finito.

    El cliente no es de fiar: "abc", None, "nan" o "inf" se vuelven `defecto`.
    Un NaN en el estado rompería el JSON de todos los jugadores.
    """
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return defecto
    return numero if math.isfinite(numero) else defecto


def normalizar(dx: float, dy: float) -> tuple[float, float]:
    """Devuelve el vector unitario (o (0, 0) si no hay dirección válida)."""
    if not (math.isfinite(dx) and math.isfinite(dy)):
        return 0.0, 0.0
    largo = math.hypot(dx, dy)
    if largo < 1e-9:
        return 0.0, 0.0
    return dx / largo, dy / largo


def distancia(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


@dataclass
class Caballero:
    """Estado completo de un jugador (de cualquier clase). Las mejoras modifican estos atributos."""

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

    # Clase (por defecto, el caballero con los valores de siempre)
    clase: str = "caballero"
    tipo_ataque: str = "tajo"
    costo_ataque: float = COSTO_ATAQUE
    preparacion: float = PREPARACION_ATAQUE
    recuperacion: float = RECUPERACION_ATAQUE
    alcance: float = ALCANCE_ATAQUE
    cos_cono: float = COS_CONO_ATAQUE
    tipo_esquiva: str = "voltereta"
    costo_esquiva: float = COSTO_ESQUIVA
    duracion_esquiva: float = DURACION_ESQUIVA
    invulnerable_esquiva: float = INVULNERABLE_ESQUIVA
    distancia_esquiva: float = DISTANCIA_ESQUIVA
    habilidad: str = "muro"
    costo_habilidad: float = 20.0
    recarga_habilidad: float = 10.0

    # Estado de la acción en curso: "libre", "atacando", "esquivando", "habilidad" o "muerto"
    estado: str = "libre"
    temporizador: float = 0.0       # tiempo restante de la acción en curso
    golpe_pendiente: bool = False   # el ataque todavía no conecta
    recuperacion_actual: float = RECUPERACION_ATAQUE
    cargado: bool = False           # el ataque en curso es el disparo perforante
    nova_pendiente: bool = False    # la partida debe resolver una nova este tick
    recarga: float = 0.0            # segundos hasta poder usar la habilidad otra vez
    efectos: dict = field(default_factory=dict)   # efecto → segundos restantes
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
        transcurrido = self.duracion_esquiva - self.temporizador
        return self.estado == "esquivando" and transcurrido < self.invulnerable_esquiva

    def gastar(self, costo: float) -> bool:
        """Gasta stamina si alcanza. Devuelve False si no hay suficiente."""
        if self.stamina < costo:
            return False
        self.stamina -= costo
        self.sin_gastar = 0.0
        return True

    def dano_efectivo(self, dist: float) -> float:
        """Daño de un ataque con todas las bonificaciones de clase y efectos activos."""
        base = TIRO_DANO if self.cargado else self.dano
        mult = 1.0
        if self.clase == "barbaro" and self.vida < self.vida_max * FURIA_UMBRAL:
            mult *= FURIA_DANO
        if "grito" in self.efectos:
            mult *= GRITO_DANO
        if self.clase == "cazadora" and dist > LEJOS_DISTANCIA:
            mult *= LEJOS_DANO
        return base * mult

    # --- Acciones que pide el cliente ----------------------------------
    def fijar_movimiento(self, dx: float, dy: float) -> None:
        self.intencion_x, self.intencion_y = normalizar(dx, dy)

    def pedir(self, accion: dict) -> None:
        """Guarda una acción (atacar/esquivar/habilidad) para ejecutarla en cuanto se pueda.

        Solo se guarda una: la última que llegue reemplaza a la anterior.
        """
        if self.vivo:
            self.accion_en_cola = accion

    def _apuntar(self, accion: dict) -> None:
        dx, dy = normalizar(accion.get("dx", 0.0), accion.get("dy", 0.0))
        if (dx, dy) != (0.0, 0.0):              # el jugador apunta (fijar objetivo)
            self.dir_x, self.dir_y = dx, dy

    def _intentar_accion(self) -> None:
        accion, self.accion_en_cola = self.accion_en_cola, None
        if accion is None:
            return
        tipo = accion.get("accion")
        if tipo == "atacar" and self.gastar(self.costo_ataque):
            self._apuntar(accion)
            self.estado, self.cargado = "atacando", False
            self.recuperacion_actual = self.recuperacion
            self.temporizador = self.preparacion + self.recuperacion
            self.golpe_pendiente = True
        elif tipo == "esquivar" and self.gastar(self.costo_esquiva * self.costo_esquiva_mult):
            dx, dy = normalizar(accion.get("dx", 0.0), accion.get("dy", 0.0))
            if (dx, dy) == (0.0, 0.0):          # sin dirección: hacia atrás
                dx, dy = -self.dir_x, -self.dir_y
            self.dir_x, self.dir_y = dx, dy
            self.estado = "esquivando"
            self.temporizador = self.duracion_esquiva
            if self.tipo_esquiva == "destello":  # teletransporte: aparece de golpe más allá
                self._mover(dx * self.distancia_esquiva, dy * self.distancia_esquiva)
        elif tipo == "habilidad" and self.recarga <= 0 and self.gastar(self.costo_habilidad):
            self._usar_habilidad(accion)

    def _usar_habilidad(self, accion: dict) -> None:
        self.recarga = self.recarga_habilidad
        if self.habilidad == "muro":            # se puede mover mientras dura
            self.efectos["muro"] = MURO_DURACION
        elif self.habilidad == "grito":
            self.efectos["grito"] = GRITO_DURACION
            self.estado, self.temporizador = "habilidad", GRITO_ANIMACION
        elif self.habilidad == "tiro":          # un ataque con carga larga y mucho daño
            self._apuntar(accion)
            self.estado, self.cargado = "atacando", True
            self.recuperacion_actual = TIRO_RECUPERACION
            self.temporizador = TIRO_CARGA + TIRO_RECUPERACION
            self.golpe_pendiente = True
        elif self.habilidad == "nova":
            self.nova_pendiente = True
            self.estado, self.temporizador = "habilidad", NOVA_ANIMACION

    # --- Simulación -----------------------------------------------------
    def paso(self, dt: float) -> bool:
        """Avanza al jugador `dt` segundos.

        Devuelve True en el tick exacto en que su ataque se suelta, para que la
        partida compruebe a quién alcanza (o lance la bola de fuego).
        """
        if not self.vivo:
            return False

        self.recarga = max(0.0, self.recarga - dt)
        for efecto in list(self.efectos):
            self.efectos[efecto] -= dt
            if self.efectos[efecto] <= 0:
                del self.efectos[efecto]

        conecta = False
        if self.estado == "libre":
            self._intentar_accion()

        if self.estado == "libre":
            if self.intencion_x or self.intencion_y:
                self.dir_x, self.dir_y = self.intencion_x, self.intencion_y
                self._mover(self.intencion_x * self.velocidad * dt,
                            self.intencion_y * self.velocidad * dt)
        elif self.estado == "esquivando":
            if self.tipo_esquiva == "voltereta":
                rapidez = self.distancia_esquiva / self.duracion_esquiva
                self._mover(self.dir_x * rapidez * dt, self.dir_y * rapidez * dt)
            self.temporizador -= dt
        elif self.estado == "atacando":
            self.temporizador -= dt
            if self.golpe_pendiente and self.temporizador <= self.recuperacion_actual + 1e-9:
                self.golpe_pendiente = False
                conecta = True
        elif self.estado == "habilidad":
            self.temporizador -= dt

        if self.estado in ("atacando", "esquivando", "habilidad") and self.temporizador <= 1e-9:
            self.estado, self.temporizador = "libre", 0.0
            self.cargado = False

        # Regeneración de stamina: solo si está libre (el grito la duplica)
        self.sin_gastar += dt
        if self.estado == "libre" and self.sin_gastar >= ESPERA_REGEN:
            regen = REGEN_STAMINA * self.regen_mult * (GRITO_REGEN if "grito" in self.efectos else 1.0)
            self.stamina = min(self.stamina_max, self.stamina + regen * dt)
        return conecta

    def _mover(self, dx: float, dy: float) -> None:
        self.x = limitar(self.x + dx, RADIO_CABALLERO, ARENA_LADO - RADIO_CABALLERO)
        self.y = limitar(self.y + dy, RADIO_CABALLERO, ARENA_LADO - RADIO_CABALLERO)

    def recibir_dano(self, cantidad: float) -> float:
        """Aplica daño respetando la esquiva, el muro de escudo y la defensa. Devuelve el daño real."""
        if not self.vivo:
            return 0.0
        if self.invulnerable:
            self.esquivas_exitosas += 1
            return 0.0
        real = cantidad * (1.0 - limitar(self.defensa, 0.0, DEFENSA_MAXIMA))
        if "muro" in self.efectos:
            real *= 1.0 - MURO_REDUCCION
        self.vida = max(0.0, self.vida - real)
        self.dano_recibido += real
        if self.vida <= 0:
            self.estado, self.temporizador = "muerto", 0.0
            self.accion_en_cola = None
            self.efectos.clear()
        return real

    def curar(self, cantidad: float) -> None:
        if self.vivo:
            self.vida = min(self.vida_max, self.vida + cantidad)

    def de_frente_a(self, x: float, y: float) -> bool:
        """True si el punto (x, y) está dentro del cono de ataque del jugador."""
        hx, hy = normalizar(x - self.x, y - self.y)
        if (hx, hy) == (0.0, 0.0):
            return True                          # encima del objetivo: siempre alcanza
        return hx * self.dir_x + hy * self.dir_y >= self.cos_cono

    def reiniciar_accion(self) -> None:
        """Corta cualquier acción en curso (se usa al cambiar de piso)."""
        if self.vivo:
            self.estado, self.temporizador = "libre", 0.0
        self.golpe_pendiente = self.cargado = self.nova_pendiente = False
        self.accion_en_cola = None
        self.efectos.clear()
        self.fijar_movimiento(0, 0)

    def revivir(self, fraccion: float) -> None:
        """Vuelve a la vida con una fracción de su vida máxima (cooperativo)."""
        self.estado, self.temporizador = "libre", 0.0
        self.vida = max(1.0, self.vida_max * fraccion)
        self.stamina = self.stamina_max

    def resumen(self) -> dict:
        """Lo que se manda al cliente en cada snapshot (redondeado para ahorrar bytes)."""
        datos = {
            "x": round(self.x, 2), "y": round(self.y, 2),
            "dx": round(self.dir_x, 2), "dy": round(self.dir_y, 2),
            "vida": round(self.vida, 1), "vida_max": round(self.vida_max, 1),
            "st": round(self.stamina, 1), "st_max": round(self.stamina_max, 1),
            "estado": self.estado, "clase": self.clase,
            "recarga": round(self.recarga, 1),
        }
        if self.efectos:
            datos["efectos"] = {k: round(v, 1) for k, v in self.efectos.items()}
        if self.cargado:
            datos["cargado"] = True
        return datos


def nuevo_jugador(jugador_id: str, clase: str = "caballero") -> Caballero:
    """Crea un jugador con los atributos de su clase."""
    c = CLASES[clase]
    return Caballero(
        jugador_id, vida_max=c.vida, vida=c.vida, stamina_max=c.stamina, stamina=c.stamina,
        dano=c.dano, velocidad=c.velocidad, clase=c.id, tipo_ataque=c.ataque,
        defensa={"barbaro": PIEL_CURTIDA, "caballero": ARMADURA}.get(c.id, 0.0),
        costo_ataque=c.costo_ataque, preparacion=c.preparacion, recuperacion=c.recuperacion,
        alcance=c.alcance, cos_cono=math.cos(math.radians(c.cono_grados)),
        tipo_esquiva=c.esquiva, costo_esquiva=c.costo_esquiva, duracion_esquiva=c.duracion_esquiva,
        invulnerable_esquiva=c.invulnerable_esquiva, distancia_esquiva=c.distancia_esquiva,
        habilidad=c.habilidad, costo_habilidad=c.costo_habilidad, recarga_habilidad=c.recarga_habilidad,
    )
