"""Una run de la torre: de la sala de espera a la victoria o la derrota.

Estados:
    esperando → combate → mejora → combate → ... → victoria | derrota | abandonada

No sabe nada de la red: `server.py` le pasa los mensajes de los jugadores y le
pide un snapshot en cada tick. Así se puede probar entera con pytest.
"""
from __future__ import annotations

import random

from . import mejoras
from .combate import (ARENA_LADO, BOLA_RADIO, BOLA_VUELO, CLASES, NOVA_DANO, NOVA_LENTITUD,
                      NOVA_RADIO, RADIO_CABALLERO, Caballero, distancia, limitar, nuevo_jugador,
                      numero_seguro)
from .estrategia import decidir
from .jefes import JEFE_DEL_DIA, JEFES, DefJefe, Jefe

MAX_JUGADORES = 3             # cooperativo de hasta 3 personas
ESPERA_INICIO = 60.0          # multijugador: si no todos dicen "listo", la run empieza sola
# solitario (empieza ya, nadie más entra) · con bots (tú + 2 compañeros IA, empieza ya) ·
# multijugador (sala de espera hasta 3 personas)
SALAS = ("solo", "bots", "grupo")
NOMBRES_BOTS = ("Alba (IA)", "Ébano (IA)")
HABILIDAD_BOTS = 0.9          # buenos, pero fallan a veces (como un compañero humano)
TICKS_DECISION_BOTS = 2       # deciden 10 veces por segundo


def nombre_reservado(jugador_id: str) -> bool:
    """Los nombres que terminan en "(IA)" son de los bots: un humano no puede usarlos
    (si no, un bot podría reemplazarlo o confundirse con él)."""
    return jugador_id in NOMBRES_BOTS or jugador_id.rstrip().upper().endswith("(IA)")
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
        self.proyectiles: list[dict] = []   # bolas de fuego en vuelo
        self.sala: str | None = None        # la elige el primer jugador: "solo", "bots" o "grupo"
        self.bots: set[str] = set()         # compañeros controlados por el servidor
        self.ticks = 0

    # --- Jugadores ---------------------------------------------------------
    @property
    def terminada(self) -> bool:
        return self.estado in TERMINALES

    def puede_entrar(self, sala: str = "grupo") -> str | None:
        """None si se puede entrar con ese modo de sala; si no, el motivo (para el cliente)."""
        if sala not in SALAS:
            return "modo de sala desconocido"
        if self.sala == "solo":
            return "esta partida es en solitario"
        if self.sala == "bots":
            return "esta partida es de un jugador con bots"
        if self.sala == "grupo" and sala != "grupo":
            return "hay un grupo esperando: entra en multijugador"
        if self.estado != "esperando":
            return "la run ya empezó"
        if len(self.jugadores) >= self.max_jugadores:
            return "partida llena"
        return None

    def agregar_jugador(self, jugador_id: str, clase: str = "caballero", sala: str = "grupo") -> bool:
        """Solo se entra en la sala de espera, mientras haya lugar y con clase y modo válidos.

        El primer jugador decide el modo: en solitario la run empieza ya y nadie más entra;
        en grupo se espera a que todos digan "listo" (hasta 3 jugadores).
        """
        if (jugador_id in self.jugadores or nombre_reservado(jugador_id)
                or clase not in CLASES or self.puede_entrar(sala)):
            return False
        primero = not self.jugadores
        if primero:
            self.sala = sala
            self.temporizador = ESPERA_INICIO if sala == "grupo" else 0.0
        self.jugadores[jugador_id] = nuevo_jugador(jugador_id, clase)
        self._evento("entra", jugador=jugador_id, clase=clase)
        if primero and sala == "bots":
            self._agregar_bots(clase)
        return True

    def _agregar_bots(self, clase_humano: str) -> None:
        """Dos compañeros IA con clases distintas a la del jugador (el grupo queda en 3)."""
        otras = [c for c in CLASES if c != clase_humano]
        for nombre, clase in zip(NOMBRES_BOTS, self.rng.sample(otras, len(NOMBRES_BOTS))):
            self.jugadores[nombre] = nuevo_jugador(nombre, clase)
            self.bots.add(nombre)
            self.listos.add(nombre)
            self._evento("entra", jugador=nombre, clase=clase, bot=True)

    def _decidir_bots(self) -> None:
        """Los compañeros IA ven lo mismo que un jugador (el estado público) y mandan acciones."""
        if not self.bots:
            return
        vista = self._estado_publico()
        for bot in self.bots:
            if bot in self.jugadores:
                accion = decidir(vista, bot, HABILIDAD_BOTS, self.rng)
                if accion:
                    self.recibir(bot, accion)

    def quitar_jugador(self, jugador_id: str) -> None:
        if self.jugadores.pop(jugador_id, None) is None:
            return
        self.listos.discard(jugador_id)
        self.ofertas.pop(jugador_id, None)
        self.elegidas.pop(jugador_id, None)
        self._evento("sale", jugador=jugador_id)
        humanos = [j for j in self.jugadores if j not in self.bots]
        if not humanos and not self.terminada:              # los bots no juegan solos
            for bot in list(self.bots):
                self.jugadores.pop(bot, None)
            self._terminar("abandonada", "todos los jugadores se fueron")

    def recibir(self, jugador_id: str, msg: dict) -> None:
        """Procesa una acción del cliente. Lo inválido se ignora en silencio."""
        c = self.jugadores.get(jugador_id)
        if c is None or self.terminada or not isinstance(msg, dict):
            return
        accion = msg.get("accion")
        dx, dy = numero_seguro(msg.get("dx")), numero_seguro(msg.get("dy"))
        if accion == "listo" and self.estado == "esperando":
            self.listos.add(jugador_id)
        elif accion == "mover":
            c.fijar_movimiento(dx, dy)
        elif accion in ("atacar", "esquivar", "habilidad") and self.estado == "combate":
            c.pedir({"accion": accion, "dx": dx, "dy": dy})
        elif accion == "clase" and self.estado == "esperando":
            clase = msg.get("clase")                # cambiar de clase solo en la sala
            if isinstance(clase, str) and clase in CLASES and clase != c.clase:
                self.jugadores[jugador_id] = nuevo_jugador(jugador_id, clase)
                self._evento("clase", jugador=jugador_id, clase=clase)
        elif accion == "elegir_mejora" and self.estado == "mejora":
            mejora = msg.get("id")
            if (isinstance(mejora, str) and mejora in self.ofertas.get(jugador_id, [])
                    and jugador_id not in self.elegidas):
                self.elegidas[jugador_id] = mejora

    # --- Simulación --------------------------------------------------------
    def paso(self, dt: float) -> None:
        if self.terminada:
            return
        if self.estado == "esperando" and not self.jugadores:
            return        # servidor Ready sin nadie: el reloj de la run aún no corre
        self.tiempo_total += dt
        self.ticks += 1
        if self.ticks % TICKS_DECISION_BOTS == 0:
            self._decidir_bots()
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
        for c in self.jugadores.values():
            if c.paso(dt):
                self._resolver_ataque(c, jefe)
            if c.nova_pendiente:
                c.nova_pendiente = False
                self._resolver_nova(c, jefe)
        self._paso_proyectiles(dt, jefe)
        self.eventos += jefe.paso(dt, list(self.jugadores.values()), self.rng)
        self._separar(jefe)

        if not jefe.vivo:
            self._evento("jefe_vencido", jefe=jefe.definicion.id, piso=self.piso + 1)
            if self.piso + 1 >= len(self.pisos):
                self._terminar("victoria", "la torre fue conquistada")
            else:
                self._ofrecer_mejoras()
        elif not any(c.vivo for c in self.jugadores.values()):
            self._terminar("derrota", f"caídos ante {jefe.definicion.nombre}")

    # --- Ataques de cada clase --------------------------------------------------
    def _danar_jefe(self, c: Caballero, jefe: Jefe, cantidad: float, tipo: str) -> None:
        real = jefe.recibir_dano(cantidad)
        c.dano_causado += real
        c.curar(real * c.robo_vida)
        self._evento("golpe", jugador=c.id, dano=round(real, 1), ataque=tipo)

    def _resolver_ataque(self, c: Caballero, jefe: Jefe) -> None:
        """El ataque se suelta este tick: tajo y flecha pegan al instante; la bola vuela."""
        d = distancia(c.x, c.y, jefe.x, jefe.y)
        al_alcance = d <= c.alcance + jefe.definicion.radio
        if c.tipo_ataque == "bola":
            if al_alcance:                       # apunta a donde está el jefe AHORA
                self.proyectiles.append({"x0": c.x, "y0": c.y, "x": jefe.x, "y": jefe.y,
                                         "en": BOLA_VUELO, "dano": c.dano_efectivo(d), "autor": c.id})
                self._evento("hechizo", jugador=c.id, x=round(jefe.x, 2), y=round(jefe.y, 2))
            else:
                self._evento("fallo", jugador=c.id, ataque="bola")
            return
        acierta = al_alcance and c.de_frente_a(jefe.x, jefe.y)
        if c.tipo_ataque == "flecha":            # el cliente dibuja la flecha volando
            self._evento("disparo", jugador=c.id, acierto=acierta, cargado=c.cargado)
        if acierta:
            self._danar_jefe(c, jefe, c.dano_efectivo(d), "cargado" if c.cargado else c.tipo_ataque)

    def _paso_proyectiles(self, dt: float, jefe: Jefe) -> None:
        """Las bolas de fuego estallan en la zona marcada: si el jefe se movió, fallan."""
        for p in list(self.proyectiles):
            p["en"] -= dt
            if p["en"] > 0:
                continue
            self.proyectiles.remove(p)
            acierta = jefe.vivo and distancia(p["x"], p["y"], jefe.x, jefe.y) <= BOLA_RADIO + jefe.definicion.radio
            self._evento("explosion", jugador=p["autor"], x=round(p["x"], 2), y=round(p["y"], 2), acierto=acierta)
            autor = self.jugadores.get(p["autor"])
            if acierta and autor is not None:
                self._danar_jefe(autor, jefe, p["dano"], "bola")

    def _resolver_nova(self, c: Caballero, jefe: Jefe) -> None:
        self._evento("nova", jugador=c.id, x=round(c.x, 2), y=round(c.y, 2), radio=NOVA_RADIO)
        if distancia(c.x, c.y, jefe.x, jefe.y) <= NOVA_RADIO + jefe.definicion.radio:
            self._danar_jefe(c, jefe, NOVA_DANO * (c.dano_efectivo(0) / c.dano), "nova")
            jefe.ralentizar(NOVA_LENTITUD)

    def _separar(self, jefe: Jefe) -> None:
        """Colisión simple: nadie puede quedar dentro del cuerpo del jefe."""
        minimo = jefe.definicion.radio + RADIO_CABALLERO
        for c in self.jugadores.values():
            if not c.vivo:
                continue
            d = distancia(c.x, c.y, jefe.x, jefe.y)
            if d >= minimo:
                continue
            if d < 1e-6:                          # justo encima: se empuja hacia la entrada
                ux, uy = 0.0, -1.0
            else:
                ux, uy = (c.x - jefe.x) / d, (c.y - jefe.y) / d
            c.x = limitar(jefe.x + ux * minimo, RADIO_CABALLERO, ARENA_LADO - RADIO_CABALLERO)
            c.y = limitar(jefe.y + uy * minimo, RADIO_CABALLERO, ARENA_LADO - RADIO_CABALLERO)

    def _iniciar_piso(self) -> None:
        n = len(self.jugadores)
        self.jefe = Jefe.crear(self.pisos[self.piso], self.piso, n)
        separacion = ARENA_LADO / (n + 1)
        for i, c in enumerate(self.jugadores.values()):     # todos vuelven a la entrada
            c.x, c.y = separacion * (i + 1), 3.0
            c.reiniciar_accion()                  # nada de golpes pendientes del piso anterior
            c.dir_x, c.dir_y = 0.0, 1.0           # todos miran hacia el jefe
            c.stamina = c.stamina_max
        self.proyectiles = []
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
        datos = self._estado_publico()
        self.eventos = []
        return datos

    def _estado_publico(self) -> dict:
        """Lo que ve cualquier jugador (también los bots). No vacía los eventos."""
        datos = {
            "modo": self.modo, "estado": self.estado,
            "piso": self.piso + 1, "pisos": len(self.pisos),
            "t": round(self.tiempo_combate, 2),
            "jugadores": {i: c.resumen() for i, c in self.jugadores.items()},
            "jefe": self.jefe.resumen() if self.jefe else None,
            "eventos": self.eventos,
        }
        if self.proyectiles:                     # bolas de fuego en vuelo (para dibujarlas)
            datos["proyectiles"] = [{"x0": round(p["x0"], 2), "y0": round(p["y0"], 2),
                                     "x": round(p["x"], 2), "y": round(p["y"], 2),
                                     "en": round(p["en"], 2), "autor": p["autor"]} for p in self.proyectiles]
        if self.estado == "esperando":
            datos["inicio_en"] = round(max(0.0, self.temporizador), 1)
            datos["sala"] = self.sala
            datos["max"] = self.max_jugadores
            datos["listos"] = sorted(self.listos & set(self.jugadores))
        if self.estado == "mejora":
            datos["ofertas"] = {i: mejoras.describir(o) for i, o in self.ofertas.items()}
            datos["elegir_en"] = round(max(0.0, self.temporizador), 1)
        if self.bots:
            datos["bots"] = sorted(self.bots)
        return datos

    def resultado(self) -> dict:
        """Resumen para la tabla de líderes (se manda al terminar la run)."""
        victoria = self.estado == "victoria"
        return {
            "modo": self.modo,
            "victoria": victoria,
            "pisos_superados": self.piso + (1 if victoria else 0),
            "tiempo_s": round(self.tiempo_combate, 2),
            "jugadores": sorted(j for j in self.jugadores if j not in self.bots),
            "bots": len(self.bots),             # la tabla de líderes separa las runs con bots
            "sala": self.sala,
            "motivo": self.motivo_fin,
        }
