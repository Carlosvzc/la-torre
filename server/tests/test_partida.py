"""Pruebas de una run completa: sala, pisos, mejoras, victoria y derrota."""
import pytest

from juego import combate as C
from juego import partida as P
from juego.combate import distancia
from juego.partida import Partida

DT = 0.05


def jugador_experto(p: Partida, jugador_id: str) -> None:
    """Bot sencillo de prueba: se acerca, ataca y esquiva justo antes de cada impacto."""
    c, jefe = p.jugadores[jugador_id], p.jefe
    if p.estado == "mejora":
        p.recibir(jugador_id, {"accion": "elegir_mejora", "id": p.ofertas[jugador_id][0]})
        return
    if p.estado != "combate" or not c.vivo:
        return
    duracion_golpe = C.PREPARACION_ATAQUE + C.RECUPERACION_ATAQUE
    impacto_cerca = jefe.estado == "preparando" and jefe.temporizador <= duracion_golpe + 0.1
    if jefe.estado == "preparando" and jefe.temporizador <= 0.15:
        zx, zy = jefe.zonas[0]
        p.recibir(jugador_id, {"accion": "esquivar", "dx": c.x - zx, "dy": c.y - zy})
    elif distancia(c.x, c.y, jefe.x, jefe.y) > 2.2:
        p.recibir(jugador_id, {"accion": "mover", "dx": jefe.x - c.x, "dy": jefe.y - c.y})
    else:
        p.recibir(jugador_id, {"accion": "mover", "dx": 0, "dy": 0})
        # no se compromete a un golpe si el impacto del jefe llega antes de terminarlo,
        # y guarda resistencia para poder esquivar después
        if not impacto_cerca and c.stamina >= C.COSTO_ATAQUE + C.COSTO_ESQUIVA:
            p.recibir(jugador_id, {"accion": "atacar", "dx": jefe.x - c.x, "dy": jefe.y - c.y})


def jugar(p: Partida, segundos: float, bot=None) -> None:
    for _ in range(int(segundos / DT)):
        if p.terminada:
            return
        if bot:
            for j in list(p.jugadores):
                bot(p, j)
        p.paso(DT)


def test_la_run_empieza_cuando_todos_estan_listos():
    p = Partida(semilla=1)
    assert p.agregar_jugador("ana") and p.agregar_jugador("beto")
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    assert p.estado == "esperando"
    p.recibir("beto", {"accion": "listo"})
    p.paso(DT)
    assert p.estado == "combate" and p.piso == 0


def test_la_run_empieza_sola_tras_la_espera():
    p = Partida(semilla=1)
    p.agregar_jugador("ana")
    jugar(p, P.ESPERA_INICIO + 0.1)
    assert p.estado == "combate"


def test_maximo_cuatro_jugadores_y_nadie_entra_ya_iniciada():
    p = Partida(semilla=1)
    assert all(p.agregar_jugador(f"j{i}") for i in range(4))
    assert not p.agregar_jugador("quinto")
    for i in range(4):
        p.recibir(f"j{i}", {"accion": "listo"})
    p.paso(DT)
    assert not p.agregar_jugador("tarde")


def test_quedarse_quieto_termina_en_derrota():
    p = Partida(semilla=3)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    jugar(p, 120, bot=lambda p, j: p.recibir(
        j, {"accion": "mover", "dx": p.jefe.x - p.jugadores[j].x,
            "dy": p.jefe.y - p.jugadores[j].y}) if p.jefe else None)
    assert p.estado == "derrota"
    assert p.resultado()["victoria"] is False


def test_un_buen_jugador_conquista_la_torre_y_recibe_mejoras():
    p = Partida(semilla=7)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    pisos_vistos = set()
    for _ in range(int(P.DURACION_MAXIMA / DT)):
        if p.terminada:
            break
        jugador_experto(p, "ana")
        p.paso(DT)
        pisos_vistos.add(p.piso)
    assert p.estado == "victoria", p.motivo_fin
    assert pisos_vistos == {0, 1, 2, 3}
    c = p.jugadores["ana"]
    assert c.esquivas_exitosas > 0
    r = p.resultado()
    assert r["victoria"] and r["pisos_superados"] == 4 and r["tiempo_s"] > 0


def test_mejora_por_defecto_si_no_elige_a_tiempo():
    p = Partida(semilla=5)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    p.jefe.recibir_dano(1e9)                  # vencemos al primer jefe a la fuerza
    p.paso(DT)
    assert p.estado == "mejora" and len(p.ofertas["ana"]) == 3
    snap = p.snapshot()
    assert len(snap["ofertas"]["ana"]) == 3
    jugar(p, P.ESPERA_MEJORA + 0.1)
    assert p.estado == "combate" and p.piso == 1


def test_elegir_una_mejora_no_ofrecida_se_ignora():
    p = Partida(semilla=5)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    p.jefe.recibir_dano(1e9)
    p.paso(DT)
    no_ofrecida = next(m for m in P.mejoras.CATALOGO if m not in p.ofertas["ana"])
    p.recibir("ana", {"accion": "elegir_mejora", "id": no_ofrecida})
    assert "ana" not in p.elegidas


def test_en_cooperativo_los_caidos_reviven_al_vencer_al_jefe():
    p = Partida(semilla=9)
    p.agregar_jugador("ana")
    p.agregar_jugador("beto")
    for j in ("ana", "beto"):
        p.recibir(j, {"accion": "listo"})
    p.paso(DT)
    p.jugadores["beto"].recibir_dano(1e9)
    p.jefe.recibir_dano(1e9)
    p.paso(DT)
    assert p.jugadores["beto"].vivo
    assert p.jugadores["beto"].vida == pytest.approx(100 * P.VIDA_AL_REVIVIR)


def test_si_todos_se_van_la_partida_se_abandona():
    p = Partida(semilla=1)
    p.agregar_jugador("ana")
    p.quitar_jugador("ana")
    assert p.estado == "abandonada" and p.terminada


def test_jefe_del_dia_es_un_solo_piso():
    p = Partida(modo="jefe_dia", semilla=1)
    assert len(p.pisos) == 1 and p.pisos[0].id == "coloso"
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    p.jefe.recibir_dano(1e9)
    p.paso(DT)
    assert p.estado == "victoria"


def test_el_snapshot_vacia_los_eventos():
    p = Partida(semilla=1)
    p.agregar_jugador("ana")
    assert p.snapshot()["eventos"]
    assert p.snapshot()["eventos"] == []


def test_el_caballero_no_puede_meterse_dentro_del_jefe():
    p = Partida(semilla=1)
    p.agregar_jugador("ana")
    p.recibir("ana", {"accion": "listo"})
    p.paso(DT)
    c, jefe = p.jugadores["ana"], p.jefe
    p.recibir("ana", {"accion": "mover", "dx": jefe.x - c.x, "dy": jefe.y - c.y})
    minimo = jefe.definicion.radio + C.RADIO_CABALLERO
    for _ in range(100):                         # 5 s caminando contra el jefe
        p.paso(DT)
        if p.terminada:
            break
        assert distancia(c.x, c.y, jefe.x, jefe.y) >= minimo - 1e-6


def test_modo_invalido():
    with pytest.raises(ValueError):
        Partida(modo="arena")
