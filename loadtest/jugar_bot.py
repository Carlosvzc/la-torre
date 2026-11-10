"""Juega una run completa contra un servidor por WebSocket, como lo haría un cliente.

Uso:
    python loadtest/jugar_bot.py ws://localhost:7654 --jugadores 2 --habilidad 0.9

Sirve para probar el contenedor en local (práctica 3.3) antes de Locust.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import time

import websockets

from estrategia import decidir


async def jugador(url: str, jugador_id: str, habilidad: float, semilla: int, clase: str) -> dict:
    rng = random.Random(semilla)
    pisos, ultimo = set(), None
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"hola": {"id": jugador_id, "rol": "jugador", "clase": clase}}))
        print(f"[{jugador_id}] {json.loads(await ws.recv())}")
        try:
            async for msg in ws:
                snap = json.loads(msg)
                if "estado" not in snap:
                    continue
                ultimo = snap
                if snap["estado"] == "combate" and snap["piso"] not in pisos:
                    pisos.add(snap["piso"])
                    print(f"[{jugador_id}] piso {snap['piso']}: {snap['jefe']['nombre']}")
                for e in snap["eventos"]:
                    if e["tipo"] == "fin":
                        print(f"[{jugador_id}] FIN: {e['resultado']} ({e['motivo']}) "
                              f"t={snap['t']} s")
                accion = decidir(snap, jugador_id, habilidad, rng)
                if accion:
                    await ws.send(json.dumps(accion))
        except websockets.ConnectionClosed:
            pass
    return ultimo or {}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", default="ws://localhost:7654")
    ap.add_argument("--jugadores", type=int, default=1)
    ap.add_argument("--habilidad", type=float, default=1.0)
    ap.add_argument("--clase", default="caballero", help="caballero, barbaro, cazadora, hechicero o mezcla")
    args = ap.parse_args()
    clases = ["caballero", "barbaro", "cazadora", "hechicero"]
    inicio = time.time()
    await asyncio.gather(*(jugador(args.url, f"bot{i}", args.habilidad, i,
                                   clases[i % 4] if args.clase == "mezcla" else args.clase)
                           for i in range(args.jugadores)))
    print(f"run completa en {time.time() - inicio:.0f} s reales")


if __name__ == "__main__":
    asyncio.run(main())
