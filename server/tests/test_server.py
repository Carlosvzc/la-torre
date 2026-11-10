"""Pruebas de red de server.py: levanta el servidor real y se conecta por WebSocket.

También las usa el pipeline de la práctica 3.2 (pytest).
"""
import asyncio
import json
from contextlib import asynccontextmanager

import websockets

import server
from juego.partida import MAX_JUGADORES


@asynccontextmanager
async def servidor_en_marcha(**kwargs):
    """Arranca el servidor en un puerto libre con su bucle de ticks en segundo plano."""
    srv = server.Servidor(semilla=1, **kwargs)
    async with websockets.serve(srv.atender, "127.0.0.1", 0) as ws_server:
        puerto = ws_server.sockets[0].getsockname()[1]
        tarea = asyncio.create_task(srv.bucle())
        try:
            yield srv, f"ws://127.0.0.1:{puerto}"
        finally:
            tarea.cancel()


async def entrar(url, jugador_id, rol="jugador"):
    ws = await websockets.connect(url)
    await ws.send(json.dumps({"hola": {"id": jugador_id, "rol": rol}}))
    bienvenida = json.loads(await ws.recv())
    return ws, bienvenida


async def esperar_snapshot(ws, condicion, intentos=200):
    for _ in range(intentos):
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        if "estado" in d and condicion(d):
            return d
    raise AssertionError("no llegó el snapshot esperado")


def correr(coro):
    asyncio.run(coro)


# --- Pruebas -----------------------------------------------------------------
def test_tick_de_20_por_segundo():
    assert server.TICK_S == 0.05


def test_un_jugador_entra_empieza_la_run_y_recibe_snapshots():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            ws, hola = await entrar(url, "ana")
            assert hola["bienvenida"]["id"] == "ana"
            await ws.send(json.dumps({"accion": "listo"}))
            snap = await esperar_snapshot(ws, lambda d: d["estado"] == "combate")
            assert "ana" in snap["jugadores"]
            assert snap["jefe"]["id"] == "guardian"
            await ws.close()
    correr(caso())


def test_las_acciones_las_decide_el_servidor():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            ws, _ = await entrar(url, "ana")
            await ws.send(json.dumps({"accion": "listo"}))
            await esperar_snapshot(ws, lambda d: d["estado"] == "combate")
            # el cliente no puede fijar su vida ni su posición: solo pide acciones
            await ws.send(json.dumps({"accion": "mover", "dx": 1, "dy": 0, "vida": 9999}))
            await ws.send(json.dumps({"accion": "atacar"}))
            snap = await esperar_snapshot(ws, lambda d: d["jugadores"]["ana"]["st"] < 100)
            ana = snap["jugadores"]["ana"]
            assert ana["vida"] <= ana["vida_max"]           # el 9999 que mandó el cliente no cuenta
            await ws.close()
    correr(caso())


def test_ping_pong_para_medir_latencia():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            ws, _ = await entrar(url, "ana")
            await ws.send(json.dumps({"ping": 123.5}))
            for _ in range(50):
                d = json.loads(await ws.recv())
                if "pong" in d:
                    assert d["pong"] == 123.5
                    break
            else:
                raise AssertionError("sin pong")
            await ws.close()
    correr(caso())


def test_espectador_ve_la_partida_sin_ocupar_lugar_ni_actuar():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            jugador, _ = await entrar(url, "ana")
            esp, hola = await entrar(url, "", rol="espectador")
            assert hola["bienvenida"]["rol"] == "espectador"
            await esp.send(json.dumps({"accion": "listo"}))      # se ignora
            snap = await esperar_snapshot(esp, lambda d: "ana" in d["jugadores"])
            assert snap["estado"] == "esperando"
            assert len(srv.jugadores) == 1 and len(srv.espectadores) == 1
            await jugador.close()
            await esp.close()
    correr(caso())


def test_quinto_jugador_rechazado_por_partida_llena():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            conexiones = [(await entrar(url, f"j{i}"))[0] for i in range(MAX_JUGADORES)]
            ws = await websockets.connect(url)
            await ws.send(json.dumps({"hola": {"id": "quinto"}}))
            try:
                await ws.recv()
                raise AssertionError("debió cerrarse")
            except websockets.ConnectionClosed as e:
                assert e.rcvd.code == 4000
            for c in conexiones:
                await c.close()
    correr(caso())


def test_sin_presentacion_se_cierra_la_conexion():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            ws = await websockets.connect(url)
            await ws.send("esto no es json")
            try:
                await ws.recv()
                raise AssertionError("debió cerrarse")
            except websockets.ConnectionClosed as e:
                assert e.rcvd.code == 4002
    correr(caso())


def test_mensajes_basura_no_tumban_el_servidor():
    async def caso():
        async with servidor_en_marcha() as (srv, url):
            ws, _ = await entrar(url, "ana")
            for basura in ("{", "[]", "42", json.dumps({"accion": "volar"})):
                await ws.send(basura)
            await ws.send(json.dumps({"ping": 1}))
            for _ in range(50):
                if "pong" in json.loads(await ws.recv()):
                    break
            else:
                raise AssertionError("el servidor dejó de responder")
            await ws.close()
    correr(caso())


def test_en_local_al_terminar_la_run_empieza_otra(monkeypatch):
    monkeypatch.setattr(server, "ESPERA_CIERRE_S", 0)
    reportes = []
    monkeypatch.setattr(server, "reportar_resultado", reportes.append)

    async def caso():
        srv = server.Servidor(semilla=1)
        srv.partida.agregar_jugador("ana")
        srv.partida.recibir("ana", {"accion": "listo"})
        srv.tick()
        srv.partida.jugadores["ana"].recibir_dano(1e9)  # forzamos la derrota
        anterior = srv.partida
        srv.tick()
        assert anterior.terminada
        await srv.terminar_run()
        assert srv.partida is not anterior and srv.partida.estado == "esperando"
    correr(caso())
    assert len(reportes) == 1


def test_sin_agones_las_llamadas_al_sdk_no_fallan(monkeypatch):
    monkeypatch.setattr(server, "SDK", "http://127.0.0.1:9")   # puerto cerrado
    assert server.agones("/ready") is False


def test_metricas_con_prefijo_del_juego():
    nombres = {m.name for m in server.JUGADORES.collect()} | {m.name for m in server.TICK.collect()}
    assert "torre_players_connected" in nombres and "torre_tick_seconds" in nombres


def test_se_mide_el_retraso_del_tick():
    def muestras():
        return next(s.value for m in server.RETRASO.collect() for s in m.samples
                    if s.name == "torre_tick_lag_seconds_count")
    antes = muestras()

    async def caso():
        srv = server.Servidor(semilla=1)
        tarea = asyncio.create_task(srv.bucle())
        await asyncio.sleep(0.3)
        tarea.cancel()
    asyncio.run(caso())
    assert muestras() - antes >= 4
