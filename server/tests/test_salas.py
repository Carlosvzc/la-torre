"""Pruebas de los modos de sala: solitario y multijugador (hasta 3)."""
import asyncio
import json

import pytest
import websockets

import server
from juego import partida as P
from juego.partida import Partida

DT = 0.05


def test_solitario_empieza_de_inmediato_y_nadie_mas_entra():
    p = Partida(semilla=1)
    assert p.agregar_jugador("ana", "cazadora", "solo")
    p.paso(DT)
    assert p.estado == "combate"                       # sin sala de espera
    assert p.puede_entrar("grupo") == "esta partida es en solitario"
    assert not p.agregar_jugador("beto", "caballero", "grupo")


def test_solitario_no_entra_en_un_grupo_que_espera():
    p = Partida(semilla=1)
    p.agregar_jugador("ana", "caballero", "grupo")
    assert p.puede_entrar("solo") == "hay un grupo esperando: entra en multijugador"
    assert p.agregar_jugador("beto", "barbaro", "grupo")


def test_grupo_espera_a_que_todos_esten_listos():
    p = Partida(semilla=1)
    for i, clase in enumerate(("caballero", "cazadora", "hechicero")):
        assert p.agregar_jugador(f"j{i}", clase, "grupo")
    p.recibir("j0", {"accion": "listo"})
    p.recibir("j1", {"accion": "listo"})
    for _ in range(40):                                # 2 s: falta uno, sigue esperando
        p.paso(DT)
    snap = p.snapshot()
    assert p.estado == "esperando" and snap["sala"] == "grupo" and snap["max"] == 3
    assert snap["listos"] == ["j0", "j1"]
    p.recibir("j2", {"accion": "listo"})
    p.paso(DT)
    assert p.estado == "combate" and len(p.jugadores) == 3


def test_grupo_arranca_solo_tras_la_espera_maxima():
    p = Partida(semilla=1)
    p.agregar_jugador("ana", "caballero", "grupo")
    for _ in range(int(P.ESPERA_INICIO / DT) + 2):
        p.paso(DT)
    assert p.estado == "combate"


def test_si_el_que_no_estaba_listo_se_va_empieza_la_run():
    p = Partida(semilla=1)
    p.agregar_jugador("ana", "caballero", "grupo")
    p.agregar_jugador("beto", "barbaro", "grupo")
    p.recibir("ana", {"accion": "listo"})
    p.quitar_jugador("beto")
    p.paso(DT)
    assert p.estado == "combate"


def test_con_bots_entran_dos_companeros_de_otras_clases_y_empieza_ya():
    p = Partida(semilla=4)
    assert p.agregar_jugador("ana", "cazadora", "bots")
    assert len(p.jugadores) == 3 and p.bots == set(P.NOMBRES_BOTS)
    clases = {c.clase for c in p.jugadores.values()}
    assert len(clases) == 3                            # nadie repite clase
    p.paso(DT)
    assert p.estado == "combate"
    assert p.puede_entrar("grupo") == "esta partida es de un jugador con bots"
    assert sorted(p.snapshot()["bots"]) == sorted(P.NOMBRES_BOTS)


def test_los_bots_juegan_solos_y_ayudan():
    p = Partida(semilla=4)
    p.agregar_jugador("ana", "caballero", "bots")
    for _ in range(200):                               # 10 s: la humana no hace nada
        p.paso(DT)
    bots = [p.jugadores[b] for b in P.NOMBRES_BOTS]
    assert sum(b.dano_causado for b in bots) > 0       # los compañeros atacaron
    assert any(b.esquivas_exitosas for b in bots) or p.jefe.vida < p.jefe.vida_max


def test_si_el_humano_se_va_la_run_con_bots_termina():
    p = Partida(semilla=4)
    p.agregar_jugador("ana", "caballero", "bots")
    p.paso(DT)
    p.quitar_jugador("ana")
    assert p.estado == "abandonada" and not p.jugadores


def test_el_resultado_separa_humanos_y_bots():
    p = Partida(semilla=4)
    p.agregar_jugador("ana", "caballero", "bots")
    r = p.resultado()
    assert r["jugadores"] == ["ana"] and r["bots"] == 2 and r["sala"] == "bots"


def test_con_bots_se_puede_conquistar_la_torre():
    """Un jugador perfecto con dos compañeros IA gana la run completa."""
    import random

    from juego.estrategia import decidir
    p = Partida(semilla=2)
    p.agregar_jugador("ana", "caballero", "bots")
    rng = random.Random(2)
    while not p.terminada:
        accion = decidir(p.snapshot(), "ana", 1.0, rng)
        if accion:
            p.recibir("ana", accion)
        p.paso(DT)
    assert p.estado == "victoria", p.motivo_fin


def test_modo_de_sala_invalido():
    assert Partida(semilla=1).puede_entrar("batalla") == "modo de sala desconocido"


def _entrar(url, nombre, sala):
    async def caso():
        ws = await websockets.connect(url)
        await ws.send(json.dumps({"hola": {"id": nombre, "clase": "caballero", "sala": sala}}))
        try:
            return ws, json.loads(await ws.recv())
        except websockets.ConnectionClosed as e:
            return None, {"cerrado": e.rcvd.code, "motivo": e.rcvd.reason}
    return caso()


def test_protocolo_de_salas():
    async def caso():
        srv = server.Servidor(semilla=1)
        async with websockets.serve(srv.atender, "127.0.0.1", 0) as w:
            url = f"ws://127.0.0.1:{w.sockets[0].getsockname()[1]}"
            ana, hola_ana = await _entrar(url, "ana", "solo")
            _, rechazo = await _entrar(url, "beto", "grupo")
            await ana.close()
            return hola_ana, rechazo
    hola_ana, rechazo = asyncio.run(caso())
    assert hola_ana["bienvenida"]["sala"] == "solo" and hola_ana["bienvenida"]["max"] == 3
    assert "direccion_lan" in hola_ana["bienvenida"]
    assert rechazo == {"cerrado": 4006, "motivo": "esta partida es en solitario"}
