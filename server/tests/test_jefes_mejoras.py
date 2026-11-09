"""Pruebas de los jefes (fases, avisos, escalado) y de las mejoras."""
import random

import pytest

from juego import jefes, mejoras
from juego.combate import Caballero
from juego.jefes import JEFES, Jefe

DT = 0.05


def test_hay_cuatro_jefes_con_dos_o_tres_ataques_en_su_primera_fase():
    assert len(JEFES) == 4
    for j in JEFES:
        assert 2 <= len(j.fases[0].ataques) <= 3


def test_la_dificultad_crece_por_piso_y_por_jugadores():
    vidas = [Jefe.crear(JEFES[0], piso, 1).vida_max for piso in range(4)]
    assert vidas == sorted(vidas) and vidas[0] < vidas[-1]
    assert Jefe.crear(JEFES[0], 0, 3).vida_max > Jefe.crear(JEFES[0], 0, 1).vida_max


def test_cambia_de_fase_al_bajar_la_vida():
    rey = Jefe.crear(JEFES[3], 0, 1)
    assert rey.fase == 0
    rey.recibir_dano(rey.vida_max * 0.5)
    assert rey.fase == 1
    rey.recibir_dano(rey.vida_max * 0.3)
    assert rey.fase == 2
    assert rey.resumen()["fase"] == 3


def test_el_jefe_avisa_y_golpea_a_quien_no_esquiva():
    rng = random.Random(1)
    guardian = Jefe.crear(JEFES[0], 0, 1)
    c = Caballero("ana", x=guardian.x, y=guardian.y - 2)   # pegado al jefe
    eventos = []
    for _ in range(200):
        eventos += guardian.paso(DT, [c], rng)
        if eventos:
            break
    assert eventos and eventos[0]["jugador"] == "ana"
    assert c.vida < 100


def test_el_aviso_aparece_en_el_snapshot_mientras_se_prepara():
    rng = random.Random(2)
    guardian = Jefe.crear(JEFES[0], 0, 1)
    c = Caballero("ana", x=guardian.x, y=guardian.y - 2)
    for _ in range(100):
        guardian.paso(DT, [c], rng)
        if guardian.estado == "preparando":
            break
    aviso = guardian.resumen()["aviso"]
    assert aviso["zonas"] and aviso["en"] > 0


def test_esquivar_a_tiempo_evita_el_dano():
    rng = random.Random(3)
    guardian = Jefe.crear(JEFES[0], 0, 1)
    c = Caballero("ana", x=guardian.x, y=guardian.y - 2)
    for _ in range(300):
        if guardian.estado == "preparando" and guardian.temporizador <= 2 * DT:
            c.pedir({"accion": "esquivar", "dx": 0, "dy": -1})
        c.paso(DT)
        guardian.paso(DT, [c], rng)
    assert c.vida == 100 and c.esquivas_exitosas > 0


def test_jefe_muerto_no_actua():
    j = Jefe.crear(JEFES[1], 0, 1)
    j.recibir_dano(10_000)
    assert not j.vivo
    assert j.paso(DT, [Caballero("ana")], random.Random()) == []


def test_sorteo_de_tres_mejoras_distintas_y_reproducible():
    a = mejoras.sortear(random.Random(42))
    b = mejoras.sortear(random.Random(42))
    assert a == b and len(set(a)) == 3


@pytest.mark.parametrize("mejora_id", sorted(mejoras.CATALOGO))
def test_cada_mejora_cambia_algo(mejora_id):
    c = Caballero("ana", vida=40)
    antes = dict(vars(c))
    mejoras.aplicar(c, mejora_id)
    assert vars(c) != antes


def test_la_defensa_no_pasa_del_tope():
    c = Caballero("ana")
    for _ in range(10):
        mejoras.aplicar(c, "coraza")
    assert c.defensa == pytest.approx(0.6)


def test_jefe_del_dia_es_fijo():
    assert jefes.JEFE_DEL_DIA.id == "coloso"
