"""Pruebas de la tabla de líderes (con el almacén en memoria; la lógica es la misma que en DynamoDB)."""
import json

import pytest

import lambda_function as L


@pytest.fixture(autouse=True)
def almacen_limpio(monkeypatch):
    monkeypatch.delenv("TABLA", raising=False)
    monkeypatch.setattr(L, "_almacen", L.Memoria())


def post(datos):
    return L.lambda_handler({"requestContext": {"http": {"method": "POST"}}, "body": json.dumps(datos)}, None)


def get(**params):
    r = L.lambda_handler({"requestContext": {"http": {"method": "GET"}}, "queryStringParameters": params}, None)
    return r["statusCode"], json.loads(r["body"])


def test_registra_y_ordena_por_mejor_tiempo():
    post({"sala": "solo", "jugadores": ["ana"], "victoria": True, "tiempo_s": 300.5})
    post({"sala": "solo", "jugadores": ["beto"], "victoria": True, "tiempo_s": 250})
    post({"sala": "solo", "jugadores": ["ana"], "victoria": True, "tiempo_s": 200})     # ana mejora
    codigo, top = get(sala="solo")
    assert codigo == 200 and [t["jugador"] for t in top] == ["ana", "beto"]
    assert top[0]["mejor_tiempo"] == 200 and top[0]["victorias"] == 2


def test_las_derrotas_cuentan_runs_pero_no_tiempo():
    post({"sala": "solo", "jugadores": ["ana"], "victoria": False, "tiempo_s": 100})
    assert get(sala="solo")[1] == []                                     # sin victorias no hay tiempo
    assert get(sala="solo", orden="victorias")[1][0]["runs"] == 1


def test_los_modos_de_sala_no_se_mezclan():
    post({"sala": "bots", "jugadores": ["ana"], "victoria": True, "tiempo_s": 150})
    post({"sala": "grupo", "jugadores": ["ana", "beto", "carla"], "victoria": True, "tiempo_s": 180})
    assert get(sala="solo")[1] == []
    assert len(get(sala="grupo")[1]) == 3 and get(sala="bots")[1][0]["mejor_tiempo"] == 150


@pytest.mark.parametrize("malo", [
    {"sala": "pvp", "jugadores": ["a"], "victoria": True, "tiempo_s": 1},
    {"sala": "solo", "jugadores": [], "victoria": True, "tiempo_s": 1},
    {"sala": "solo", "jugadores": ["x" * 40], "victoria": True, "tiempo_s": 1},
    {"sala": "solo", "jugadores": ["a"], "victoria": True, "tiempo_s": -5},
])
def test_datos_invalidos_dan_400(malo):
    assert post(malo)["statusCode"] == 400


def test_cuerpo_que_no_es_json_da_400():
    r = L.lambda_handler({"requestContext": {"http": {"method": "POST"}}, "body": "{roto"}, None)
    assert r["statusCode"] == 400


def test_acepta_el_resultado_tal_como_lo_manda_el_servidor():
    # forma exacta de Partida.resultado() en server/juego/partida.py
    resultado = {"modo": "torre", "victoria": True, "pisos_superados": 4, "tiempo_s": 321.4,
                 "jugadores": ["ana"], "bots": 2, "sala": "bots", "motivo": "la torre fue conquistada"}
    assert post(resultado)["statusCode"] == 201
    assert get(sala="bots")[1][0]["jugador"] == "ana"
