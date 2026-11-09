"""Pruebas de las reglas de combate del caballero."""
import pytest

from juego import combate
from juego.combate import Caballero

DT = 0.05


def avanzar(c: Caballero, segundos: float) -> int:
    """Avanza el caballero y cuenta cuántos golpes conectaron."""
    golpes = 0
    for _ in range(round(segundos / DT)):
        golpes += c.paso(DT)
    return golpes


def test_atacar_gasta_stamina_y_conecta_una_sola_vez():
    c = Caballero("ana")
    c.pedir({"accion": "atacar"})
    golpes = avanzar(c, 0.6)
    assert golpes == 1
    # gastó 20; como mucho regeneró un par de ticks al final
    assert 100 - combate.COSTO_ATAQUE <= c.stamina <= 100 - combate.COSTO_ATAQUE + 3
    assert c.estado == "libre"


def test_el_golpe_conecta_tras_la_preparacion():
    c = Caballero("ana")
    c.pedir({"accion": "atacar"})
    assert avanzar(c, combate.PREPARACION_ATAQUE - DT) == 0   # todavía no
    assert avanzar(c, DT * 2) == 1                            # ahora sí


def test_sin_stamina_no_se_puede_atacar():
    c = Caballero("ana", stamina=10)
    c.pedir({"accion": "atacar"})
    assert avanzar(c, 0.6) == 0
    assert c.estado == "libre"


def test_la_esquiva_da_invulnerabilidad_y_luego_no():
    c = Caballero("ana")
    c.pedir({"accion": "esquivar", "dx": 1, "dy": 0})
    c.paso(DT)
    assert c.invulnerable
    assert c.recibir_dano(50) == 0
    assert c.vida == 100
    assert c.esquivas_exitosas == 1
    avanzar(c, combate.INVULNERABLE_ESQUIVA)                  # se acaban los i-frames
    assert not c.invulnerable
    assert c.recibir_dano(50) == 50


def test_la_esquiva_desplaza_al_caballero():
    c = Caballero("ana", x=10, y=10)
    c.pedir({"accion": "esquivar", "dx": 1, "dy": 0})
    avanzar(c, combate.DURACION_ESQUIVA)
    assert c.x == pytest.approx(10 + combate.DISTANCIA_ESQUIVA, abs=0.01)


def test_la_stamina_se_regenera_despues_de_la_espera():
    c = Caballero("ana", stamina=0)
    c.sin_gastar = 0
    avanzar(c, combate.ESPERA_REGEN - DT)
    assert c.stamina == 0
    avanzar(c, 1.0)
    assert c.stamina > 20


def test_la_defensa_reduce_el_dano_con_tope():
    c = Caballero("ana", defensa=0.25)
    assert c.recibir_dano(40) == pytest.approx(30)
    c2 = Caballero("beto", defensa=0.95)                    # se limita al 60 %
    assert c2.recibir_dano(100) == pytest.approx(40)


def test_morir_detiene_al_caballero():
    c = Caballero("ana", vida=10)
    c.recibir_dano(50)
    assert not c.vivo
    c.pedir({"accion": "atacar"})
    assert avanzar(c, 1) == 0
    c.revivir(0.3)
    assert c.vivo and c.vida == pytest.approx(30)


def test_no_sale_de_la_arena():
    c = Caballero("ana", x=1, y=1)
    c.fijar_movimiento(-1, -1)
    avanzar(c, 2)
    assert c.x == combate.RADIO_CABALLERO and c.y == combate.RADIO_CABALLERO
