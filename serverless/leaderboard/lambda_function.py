"""Tabla de líderes serverless de La Torre (práctica 3.5, variante AWS del PDF).

AWS Lambda (Python 3.12) + DynamoDB, expuesta con una Function URL:
  POST /resultado   el servidor del juego manda el resultado de cada run (server.py)
  GET  /top?sala=solo|bots|grupo&orden=tiempo|victorias   top 10

Categorías: el mejor tiempo solo se compara entre runs del mismo modo de sala
(solitario, con bots o grupo), porque no son comparables entre sí.

Tabla DynamoDB (variable TABLA): llave de partición "id" = "<sala>#<jugador>".
Sin la variable TABLA usa un almacén en memoria (pruebas y servidor local).
"""
from __future__ import annotations

import base64
import json
import os
from decimal import Decimal

SALAS = ("solo", "bots", "grupo")
MAX_JUGADOR = 24


class Memoria:
    """Almacén en memoria con la misma interfaz que la tabla (pruebas y uso local)."""

    def __init__(self):
        self.items: dict[str, dict] = {}

    def registrar(self, sala: str, jugador: str, victoria: bool, tiempo: float) -> None:
        it = self.items.setdefault(f"{sala}#{jugador}", {"id": f"{sala}#{jugador}", "sala": sala,
                                                          "jugador": jugador, "runs": 0, "victorias": 0})
        it["runs"] += 1
        if victoria:
            it["victorias"] += 1
            if "mejor_tiempo" not in it or tiempo < it["mejor_tiempo"]:
                it["mejor_tiempo"] = tiempo

    def todos(self, sala: str) -> list[dict]:
        return [dict(it) for it in self.items.values() if it["sala"] == sala]


class Dynamo:
    """Tabla DynamoDB. Contadores atómicos con ADD; el mejor tiempo con una escritura condicional."""

    def __init__(self, nombre: str):
        import boto3                                    # disponible en el runtime de Lambda
        from boto3.dynamodb.conditions import Attr
        self.tabla = boto3.resource("dynamodb").Table(nombre)
        self.Attr = Attr

    def registrar(self, sala: str, jugador: str, victoria: bool, tiempo: float) -> None:
        clave = {"id": f"{sala}#{jugador}"}
        self.tabla.update_item(
            Key=clave,
            UpdateExpression="SET sala = :s, jugador = :j ADD runs :uno, victorias :v",
            ExpressionAttributeValues={":s": sala, ":j": jugador, ":uno": 1, ":v": 1 if victoria else 0})
        if victoria:
            t = Decimal(str(round(tiempo, 2)))
            try:                                        # solo si mejora el tiempo guardado
                self.tabla.update_item(
                    Key=clave, UpdateExpression="SET mejor_tiempo = :t",
                    ConditionExpression="attribute_not_exists(mejor_tiempo) OR mejor_tiempo > :t",
                    ExpressionAttributeValues={":t": t})
            except self.tabla.meta.client.exceptions.ConditionalCheckFailedException:
                pass

    def todos(self, sala: str) -> list[dict]:
        # scan basta para la práctica (lo dice el PDF); en producción: índice secundario o Redis
        resp = self.tabla.scan(FilterExpression=self.Attr("sala").eq(sala))
        items = resp["Items"]
        while "LastEvaluatedKey" in resp:
            resp = self.tabla.scan(FilterExpression=self.Attr("sala").eq(sala), ExclusiveStartKey=resp["LastEvaluatedKey"])
            items += resp["Items"]
        return items


_almacen = None


def almacen():
    global _almacen
    if _almacen is None:
        _almacen = Dynamo(os.environ["TABLA"]) if os.environ.get("TABLA") else Memoria()
    return _almacen


def responder(codigo: int, cuerpo) -> dict:
    return {"statusCode": codigo, "headers": {"Content-Type": "application/json",
                                             "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(cuerpo, ensure_ascii=False, default=lambda d: float(d))}


def registrar_resultado(datos: dict) -> int:
    """Valida el resultado que manda el servidor del juego y lo registra. Devuelve cuántos jugadores."""
    sala = datos.get("sala") or "solo"
    if sala not in SALAS:
        raise ValueError("sala inválida")
    jugadores = datos.get("jugadores")
    if not isinstance(jugadores, list) or not 1 <= len(jugadores) <= 3:
        raise ValueError("jugadores inválidos")
    victoria = datos.get("victoria") is True
    tiempo = float(datos.get("tiempo_s", 0))
    if not 0 <= tiempo < 3600:
        raise ValueError("tiempo inválido")
    for j in jugadores:
        if not isinstance(j, str) or not 0 < len(j) <= MAX_JUGADOR:
            raise ValueError("nombre inválido")
        almacen().registrar(sala, j, victoria, tiempo)
    return len(jugadores)


def top(sala: str, orden: str = "tiempo", n: int = 10) -> list[dict]:
    if sala not in SALAS:
        raise ValueError("sala inválida")
    items = almacen().todos(sala)
    if orden == "victorias":
        items.sort(key=lambda i: (-int(i.get("victorias", 0)), int(i.get("runs", 0))))
    else:
        items = [i for i in items if "mejor_tiempo" in i]
        items.sort(key=lambda i: float(i["mejor_tiempo"]))
    return [{"jugador": i["jugador"], "mejor_tiempo": float(i["mejor_tiempo"]) if "mejor_tiempo" in i else None,
             "victorias": int(i.get("victorias", 0)), "runs": int(i.get("runs", 0))} for i in items[:n]]


def lambda_handler(event, context):
    metodo = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    try:
        if metodo == "POST":
            cuerpo = event.get("body") or "{}"
            if event.get("isBase64Encoded"):
                cuerpo = base64.b64decode(cuerpo)
            n = registrar_resultado(json.loads(cuerpo))
            return responder(201, {"registrados": n})
        params = event.get("queryStringParameters") or {}
        return responder(200, top(params.get("sala", "solo"), params.get("orden", "tiempo")))
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return responder(400, {"error": str(e)})
