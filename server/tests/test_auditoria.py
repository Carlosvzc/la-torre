"""Pruebas de regresión de la auditoría del 9 de noviembre (un caso por hallazgo).

Cada prueba reproducía un fallo antes de la corrección.
"""
import asyncio
import json

import pytest
import websockets

import server
from juego.combate import Caballero, numero_seguro
from juego.partida import DURACION_MAXIMA, Partida

DT = 0.05


def partida_en_combate(semilla=1) -> Partida:
    p = Partida(semilla=semilla)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    assert p.estado == "combate"
    return p


def json_estricto(datos) -> None:
    """Falla si el JSON lleva NaN o Infinity (JSON.parse de JavaScript los rechaza)."""
    def rechazar(constante):
        raise ValueError(f"constante no válida en JSON: {constante}")
    json.loads(json.dumps(datos), parse_constant=rechazar)


# --- Hallazgos 1 y 2: números inválidos del cliente -------------------------------
@pytest.mark.parametrize("valor", ["nan", "inf", "-inf", float("nan"), "abc", None, [], {}])
def test_numeros_invalidos_no_rompen_el_estado(valor):
    p = partida_en_combate()
    for accion in ("mover", "esquivar", "atacar"):
        p.recibir("ana", {"accion": accion, "dx": valor, "dy": valor})   # sin excepción
        for _ in range(10):
            p.paso(DT)
    json_estricto(p.snapshot())


def test_numero_seguro():
    assert numero_seguro("2.5") == 2.5
    assert numero_seguro("nan") == 0.0 and numero_seguro("inf", 1.0) == 1.0
    assert numero_seguro(None) == 0.0 and numero_seguro("abc") == 0.0


def test_mensaje_que_no_es_objeto_se_ignora():
    p = partida_en_combate()
    p.recibir("ana", ["atacar"])                  # no debe lanzar
    p.recibir("ana", {"accion": "elegir_mejora", "id": ["lista"]})


# --- Hallazgo 3: el servidor se marca Allocated solo --------------------------------
def test_primer_jugador_marca_allocated_una_sola_vez(monkeypatch):
    llamadas = []
    monkeypatch.setattr(server, "agones", lambda ruta: llamadas.append(ruta) or True)

    async def caso():
        srv = server.Servidor(semilla=1)
        srv.con_agones = True
        async with websockets.serve(srv.atender, "127.0.0.1", 0) as w:
            url = f"ws://127.0.0.1:{w.sockets[0].getsockname()[1]}"
            clientes = []
            for nombre in ("ana", "beto"):
                ws = await websockets.connect(url)
                await ws.send(json.dumps({"hola": {"id": nombre}}))
                await ws.recv()
                clientes.append(ws)
            for ws in clientes:
                await ws.close()
    asyncio.run(caso())
    assert llamadas.count("/allocate") == 1


# --- Hallazgos 4 y 8: el reloj de la run no corre con la sala vacía ----------------
def test_sala_vacia_no_caduca():
    p = Partida(semilla=1)
    for _ in range(int(DURACION_MAXIMA / DT) + 10):
        p.paso(DT)
    assert p.estado == "esperando" and p.tiempo_total == 0
    assert p.agregar_jugador("ana")


def test_la_duracion_de_la_run_empieza_con_el_primer_jugador():
    p = Partida(semilla=1)
    for _ in range(100):                          # 5 s en Ready sin nadie
        p.paso(DT)
    p.agregar_jugador("ana")
    for _ in range(20):                           # 1 s con la jugadora en la sala
        p.paso(DT)
    assert p.tiempo_total == pytest.approx(1.0)


# --- Hallazgo 9 (prueba de Locust): un SDK de Agones lento no puede congelar los ticks ---
def test_latido_lento_de_agones_no_congela_el_tick(monkeypatch):
    import time as _time
    monkeypatch.setattr(server, "agones", lambda ruta: _time.sleep(0.8) or True)
    monkeypatch.setattr(server, "LATIDO_TICKS", 2)          # latido muy seguido para la prueba

    async def caso():
        srv = server.Servidor(semilla=1)
        srv.con_agones = True
        tarea = asyncio.create_task(srv.bucle())
        await asyncio.sleep(1.0)
        tarea.cancel()
        return srv.n_tick
    ticks = asyncio.run(caso())
    assert ticks >= 15, f"solo {ticks} ticks en 1 s: el latido está bloqueando el bucle"


def test_sin_agones_no_se_manda_latido(monkeypatch):
    llamadas = []
    monkeypatch.setattr(server, "agones", lambda ruta: llamadas.append(ruta) or False)
    monkeypatch.setattr(server, "LATIDO_TICKS", 2)

    async def caso():
        srv = server.Servidor(semilla=1)                   # con_agones = False (local)
        tarea = asyncio.create_task(srv.bucle())
        await asyncio.sleep(0.3)
        tarea.cancel()
    asyncio.run(caso())
    assert "/health" not in llamadas


# --- Hallazgo 5: presentación mal formada → cierre limpio 4002 -----------------------
@pytest.mark.parametrize("hola", ['{"hola": "texto"}', '{"hola": 5}', '{"otro": 1}', "[]"])
def test_presentacion_mal_formada_cierra_con_4002(hola):
    async def caso():
        srv = server.Servidor(semilla=1)
        async with websockets.serve(srv.atender, "127.0.0.1", 0) as w:
            url = f"ws://127.0.0.1:{w.sockets[0].getsockname()[1]}"
            async with websockets.connect(url) as ws:
                await ws.send(hola)
                with pytest.raises(websockets.ConnectionClosed) as e:
                    await ws.recv()
                assert e.value.rcvd.code == 4002
    asyncio.run(caso())


# --- Hallazgo 6: nada de golpes pendientes al cambiar de piso -------------------------
def test_ataque_a_medias_no_pasa_al_siguiente_piso():
    p = partida_en_combate()
    c = p.jugadores["ana"]
    c.x, c.y = p.jefe.x, p.jefe.y - 2
    p.recibir("ana", {"accion": "atacar", "dx": 0, "dy": 1})
    p.paso(DT)
    assert c.estado == "atacando"
    p.jefe.recibir_dano(1e9)
    p.paso(DT)
    p.recibir("ana", {"accion": "elegir_mejora", "id": p.ofertas["ana"][0]})
    p.paso(DT)
    assert p.piso == 1 and c.estado == "libre" and not c.golpe_pendiente


# --- Hallazgo 7: el golpe solo alcanza al frente -----------------------------------
def _dano_al_jefe(dir_ataque) -> float:
    p = partida_en_combate()
    c = p.jugadores["ana"]
    c.x, c.y = p.jefe.x, p.jefe.y - 2             # el jefe está al norte (+y)
    vida = p.jefe.vida
    p.recibir("ana", {"accion": "atacar", "dx": dir_ataque[0], "dy": dir_ataque[1]})
    for _ in range(8):
        p.paso(DT)
    return vida - p.jefe.vida


def test_golpe_de_espaldas_no_hace_dano():
    assert _dano_al_jefe((0, -1)) == 0


def test_golpe_de_frente_si_hace_dano():
    assert _dano_al_jefe((0, 1)) > 0


def test_atacar_apunta_hacia_la_direccion_pedida():
    c = Caballero("ana", dir_x=0, dir_y=-1)
    c.pedir({"accion": "atacar", "dx": 1, "dy": 0})
    c.paso(DT)
    assert (c.dir_x, c.dir_y) == (1.0, 0.0)
