"""Pruebas de las 4 clases: cada una debe jugarse distinto y todas deben poder ganar."""
import asyncio
import json
import os
import random
import sys

import pytest
import websockets

import server
from juego import combate as C
from juego.combate import CLASES, nuevo_jugador
from juego.jefes import JEFES, Jefe
from juego.partida import Partida

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "loadtest"))
from estrategia import decidir  # noqa: E402

DT = 0.05


def en_combate(clase, semilla=1) -> Partida:
    p = Partida(semilla=semilla)
    assert p.agregar_jugador("ana", clase)
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    return p


def colocar(p: Partida, distancia_al_jefe: float):
    c, j = p.jugadores["ana"], p.jefe
    c.x, c.y = j.x, j.y - distancia_al_jefe
    c.dir_x, c.dir_y = 0.0, 1.0
    j.estado, j.temporizador = "recuperando", 99      # el jefe no estorba en estas pruebas
    return c, j


def avanzar(p: Partida, segundos: float):
    for _ in range(round(segundos / DT)):
        p.paso(DT)


# --- Catálogo -------------------------------------------------------------------
def test_hay_cuatro_clases_con_estilos_distintos():
    assert set(CLASES) == {"caballero", "barbaro", "cazadora", "hechicero"}
    assert len({c.ataque for c in CLASES.values()}) == 3          # tajo, flecha, bola
    assert len({c.habilidad for c in CLASES.values()}) == 4
    assert {c.esquiva for c in CLASES.values()} == {"voltereta", "destello"}


def test_nuevo_jugador_usa_los_valores_de_su_clase():
    b = nuevo_jugador("x", "barbaro")
    assert b.vida_max == 135 and b.dano == 32 and b.defensa == C.PIEL_CURTIDA
    h = nuevo_jugador("x", "hechicero")
    assert h.tipo_ataque == "bola" and h.tipo_esquiva == "destello"


def test_clase_invalida_no_entra():
    assert not Partida(semilla=1).agregar_jugador("ana", "paladin")


def test_cambiar_de_clase_solo_en_la_sala():
    p = Partida(semilla=1)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "clase", "clase": "cazadora"})
    assert p.jugadores["ana"].clase == "cazadora"
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    p.recibir("ana", {"accion": "clase", "clase": "barbaro"})       # ya en combate: se ignora
    assert p.jugadores["ana"].clase == "cazadora"


# --- Ataques ----------------------------------------------------------------------
def test_cazadora_alcanza_de_lejos_y_el_caballero_no():
    for clase, debe_pegar in (("cazadora", True), ("caballero", False)):
        p = en_combate(clase)
        c, j = colocar(p, 8.0)
        vida = j.vida
        p.recibir("ana", {"accion": "atacar", "dx": 0, "dy": 1})
        avanzar(p, 0.6)
        assert (j.vida < vida) == debe_pegar, clase


def test_cazadora_hace_mas_dano_de_lejos():
    c = nuevo_jugador("x", "cazadora")
    assert c.dano_efectivo(8) == pytest.approx(c.dano * C.LEJOS_DANO)
    assert c.dano_efectivo(3) == pytest.approx(c.dano)


def test_bola_de_fuego_tarda_y_falla_si_el_jefe_se_mueve():
    p = en_combate("hechicero")
    c, j = colocar(p, 6.0)
    vida = j.vida
    p.recibir("ana", {"accion": "atacar", "dx": 0, "dy": 1})
    avanzar(p, CLASES["hechicero"].preparacion + DT)
    assert p.proyectiles and j.vida == vida                         # en vuelo: aún no pega
    assert "proyectiles" in p.snapshot()
    j.x += 4                                                        # el jefe se aparta
    avanzar(p, C.BOLA_VUELO + DT)
    assert not p.proyectiles and j.vida == vida                     # estalló donde ya no estaba


def test_bola_de_fuego_pega_si_el_jefe_se_queda():
    p = en_combate("hechicero")
    c, j = colocar(p, 6.0)
    vida = j.vida
    p.recibir("ana", {"accion": "atacar", "dx": 0, "dy": 1})
    avanzar(p, CLASES["hechicero"].preparacion + C.BOLA_VUELO + 2 * DT)
    assert j.vida == pytest.approx(vida - CLASES["hechicero"].dano)


def test_barbaro_tiene_furia_con_poca_vida():
    b = nuevo_jugador("x", "barbaro")
    normal = b.dano_efectivo(2)
    b.vida = b.vida_max * 0.3
    assert b.dano_efectivo(2) == pytest.approx(normal * C.FURIA_DANO)


# --- Esquivas -----------------------------------------------------------------------
def test_destello_teletransporta_al_instante():
    c = nuevo_jugador("x", "hechicero")
    c.x, c.y = 10, 10
    c.pedir({"accion": "esquivar", "dx": 1, "dy": 0})
    c.paso(DT)
    assert c.x == pytest.approx(10 + C.CLASES["hechicero"].distancia_esquiva)
    assert c.invulnerable


def test_voltereta_de_la_cazadora_llega_mas_lejos():
    lejos = {}
    for clase in ("caballero", "cazadora"):
        c = nuevo_jugador("x", clase)
        c.x, c.y = 5, 10
        c.pedir({"accion": "esquivar", "dx": 1, "dy": 0})
        for _ in range(20):
            c.paso(DT)
        lejos[clase] = c.x
    assert lejos["cazadora"] > lejos["caballero"]


# --- Habilidades --------------------------------------------------------------------
def test_muro_de_escudo_reduce_el_dano():
    c = nuevo_jugador("x", "caballero")
    sin_muro = nuevo_jugador("y", "caballero").recibir_dano(40)
    c.pedir({"accion": "habilidad"})
    c.paso(DT)
    assert "muro" in c.efectos
    assert c.recibir_dano(40) == pytest.approx(sin_muro * (1 - C.MURO_REDUCCION))


def test_grito_de_guerra_sube_el_dano_y_tiene_recarga():
    b = nuevo_jugador("x", "barbaro")
    normal = b.dano_efectivo(2)
    b.pedir({"accion": "habilidad"})
    b.paso(DT)
    assert b.dano_efectivo(2) == pytest.approx(normal * C.GRITO_DANO)
    assert b.recarga > 0
    for _ in range(round((C.GRITO_ANIMACION + 0.1) / DT)):
        b.paso(DT)
    b.pedir({"accion": "habilidad"})                               # en recarga: no se repite
    b.paso(DT)
    assert b.efectos["grito"] < C.GRITO_DURACION - 0.5


def test_disparo_perforante_carga_y_hace_mucho_dano():
    p = en_combate("cazadora")
    c, j = colocar(p, 6.0)
    vida = j.vida
    p.recibir("ana", {"accion": "habilidad", "dx": 0, "dy": 1})
    avanzar(p, 0.6)
    assert j.vida == vida                                           # todavía cargando
    avanzar(p, C.TIRO_CARGA)
    assert vida - j.vida == pytest.approx(C.TIRO_DANO * C.LEJOS_DANO)


def test_nova_de_escarcha_dana_y_frena_al_jefe():
    p = en_combate("hechicero")
    c, j = colocar(p, 2.5)
    vida = j.vida
    p.recibir("ana", {"accion": "habilidad"})
    p.paso(DT)
    assert j.vida == pytest.approx(vida - C.NOVA_DANO)
    assert j.lento > 0 and j.resumen()["lento"] > 0


def test_jefe_ralentizado_se_mueve_mas_lento():
    rng = random.Random(1)
    distancias = {}
    for lento in (False, True):
        j = Jefe.crear(JEFES[0], 0, 1)
        if lento:
            j.ralentizar(10)
        objetivo = nuevo_jugador("x")
        objetivo.x, objetivo.y = 10, 2
        y0 = j.y
        for _ in range(10):
            j.paso(DT, [objetivo], rng)
        distancias[lento] = y0 - j.y
    assert distancias[True] == pytest.approx(distancias[False] * 0.5, rel=0.05)


# --- Protocolo ----------------------------------------------------------------------
def test_protocolo_clase_en_hola_y_catalogo_en_bienvenida():
    async def caso():
        srv = server.Servidor(semilla=1)
        async with websockets.serve(srv.atender, "127.0.0.1", 0) as w:
            url = f"ws://127.0.0.1:{w.sockets[0].getsockname()[1]}"
            ws = await websockets.connect(url)
            await ws.send(json.dumps({"hola": {"id": "ana", "clase": "cazadora"}}))
            bienvenida = json.loads(await ws.recv())["bienvenida"]
            mala = await websockets.connect(url)
            await mala.send(json.dumps({"hola": {"id": "beto", "clase": "paladin"}}))
            with pytest.raises(websockets.ConnectionClosed) as e:
                await mala.recv()
            await ws.close()
            return bienvenida, e.value.rcvd.code, srv.partida.jugadores["ana"].clase
    bienvenida, codigo, clase = asyncio.run(caso())
    assert bienvenida["clase"] == "cazadora" and set(bienvenida["clases"]) == set(CLASES)
    assert bienvenida["clases"]["barbaro"]["preparacion"] == CLASES["barbaro"].preparacion
    assert codigo == 4005 and clase == "cazadora"


# --- Balance: todas las clases pueden conquistar la torre ------------------------
@pytest.mark.parametrize("clase", sorted(CLASES))
def test_cada_clase_puede_conquistar_la_torre(clase):
    p = Partida(semilla=3)
    p.agregar_jugador("bot", clase)
    rng = random.Random(3)
    while not p.terminada:
        accion = decidir(p.snapshot(), "bot", 1.0, rng)
        if accion:
            p.recibir("bot", accion)
        p.paso(DT)
    assert p.estado == "victoria", f"{clase}: {p.motivo_fin}"
