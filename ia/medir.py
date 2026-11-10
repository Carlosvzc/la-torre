"""Evalúa el bot y mide su inferencia (práctica 3.1, paso 4 y entregable).

Uso:
    python ia/medir.py ia/modelos/bot_cpu_100k.zip [--episodios 50]

Mide:
  - Tasa de victorias contra el Guardián frente a dos referencias: azar y el bot de reglas.
  - Latencia media de una decisión en CPU (1 núcleo) con PyTorch (SB3) y con numpy.
  - Decisiones por segundo por núcleo y vCPU necesarias para 2 000 bots a 10 Hz (+30 %).
Exporta la política a .npz (lo que usaría el servidor, sin PyTorch) y comprueba que decide igual.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time

import numpy as np
import torch
from stable_baselines3 import PPO

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "loadtest"))
from entorno_duelo import ID, DueloJefe, accion_a_mensaje, observar  # noqa: E402
from estrategia import decidir  # noqa: E402

BOTS, HZ, MARGEN = 2000, 10, 0.30


# --- Política exportada a numpy (sin PyTorch: lo que correría dentro del servidor) -------
def exportar(modelo: PPO, ruta: str) -> dict:
    red = modelo.policy.mlp_extractor.policy_net
    capas = [m for m in red if isinstance(m, torch.nn.Linear)] + [modelo.policy.action_net]
    pesos = {}
    for i, capa in enumerate(capas):
        pesos[f"W{i}"] = capa.weight.detach().cpu().numpy().astype(np.float32)
        pesos[f"b{i}"] = capa.bias.detach().cpu().numpy().astype(np.float32)
    np.savez(ruta, **pesos)
    return pesos


def decidir_numpy(pesos: dict, obs: np.ndarray) -> int:
    x = obs
    n = len(pesos) // 2
    for i in range(n - 1):
        x = np.tanh(pesos[f"W{i}"] @ x + pesos[f"b{i}"])
    return int(np.argmax(pesos[f"W{n - 1}"] @ x + pesos[f"b{n - 1}"]))


# --- Evaluación -------------------------------------------------------------------------
def evaluar(politica, episodios: int, semilla: int = 1000) -> dict:
    """`politica(env, obs)` hace un paso. Devuelve victorias y métricas medias."""
    env = DueloJefe()
    victorias, tiempos, vida_jefe = 0, [], []
    for ep in range(episodios):
        obs, _ = env.reset(seed=semilla + ep)
        while True:
            obs, _, term, trunc, info = politica(env, obs)
            if term or trunc:
                break
        victorias += info["victoria"]
        vida_jefe.append(info["vida_jefe"])
        if info["victoria"]:
            tiempos.append(info["tiempo"])
    return {"victorias": victorias, "episodios": episodios,
            "tasa": round(victorias / episodios, 3),
            "tiempo_medio_victoria_s": round(float(np.mean(tiempos)), 1) if tiempos else None,
            "vida_jefe_restante_media": round(float(np.mean(vida_jefe)), 3)}


def politica_modelo(modelo):
    def paso(env, obs):
        accion, _ = modelo.predict(obs, deterministic=True)
        return env.step(accion)
    return paso


def politica_azar(env, obs):
    return env.step(env.action_space.sample())


def politica_reglas(habilidad):
    rng = random.Random(7)

    def paso(env, obs):
        # el bot de reglas habla el protocolo del juego directamente (mismo que en Locust)
        mensaje = decidir(env.snap, ID, habilidad, rng)
        if mensaje and mensaje.get("accion") != "listo":
            env.partida.recibir(ID, mensaje)
        return env.step(0) if mensaje is None else _paso_sin_accion(env)
    return paso


def _paso_sin_accion(env):
    # la acción ya se mandó: avanzamos el entorno con "quieto" sin pisarla
    guardado = env.partida.recibir
    env.partida.recibir = lambda *a, **k: None
    try:
        return env.step(0)
    finally:
        env.partida.recibir = guardado


# --- Latencia ------------------------------------------------------------------------
def latencia(funcion, obs_muestra: list, repeticiones: int = 10_000) -> float:
    for o in obs_muestra[:200]:                  # calentamiento
        funcion(o)
    t = time.perf_counter()
    for i in range(repeticiones):
        funcion(obs_muestra[i % len(obs_muestra)])
    return (time.perf_counter() - t) / repeticiones * 1000      # ms por decisión


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("modelo")
    ap.add_argument("--episodios", type=int, default=50)
    args = ap.parse_args()
    torch.set_num_threads(1)                    # "por núcleo": un solo hilo
    modelo = PPO.load(args.modelo, device="cpu")
    nombre = os.path.splitext(os.path.basename(args.modelo))[0]

    print(f"Evaluando {nombre} en {args.episodios} combates contra el Guardián de Hierro…")
    resultados = {
        "modelo": nombre,
        "bot_entrenado": evaluar(politica_modelo(modelo), args.episodios),
        "azar": evaluar(politica_azar, args.episodios),
        "reglas_habilidad_1.0": evaluar(politica_reglas(1.0), args.episodios),
        "reglas_habilidad_0.85": evaluar(politica_reglas(0.85), args.episodios),
    }

    # Observaciones reales para medir la latencia
    env, obs_muestra = DueloJefe(), []
    obs, _ = env.reset(seed=5)
    for _ in range(2000):
        obs_muestra.append(obs)
        obs, _, term, trunc, _ = env.step(env.action_space.sample())
        if term or trunc:
            obs, _ = env.reset()

    pesos = exportar(modelo, os.path.join(AQUI, "modelos", nombre + ".npz"))
    iguales = sum(decidir_numpy(pesos, o) == int(modelo.predict(o, deterministic=True)[0]) for o in obs_muestra[:1000])
    lat_sb3 = latencia(lambda o: modelo.predict(o, deterministic=True), obs_muestra)
    lat_np = latencia(lambda o: decidir_numpy(pesos, o), obs_muestra)

    def capacidad(lat_ms):
        por_nucleo = 1000 / lat_ms
        necesarias = BOTS * HZ / por_nucleo
        return {"latencia_ms": round(lat_ms, 4), "decisiones_s_por_nucleo": round(por_nucleo),
                "vcpu_sin_margen": round(necesarias, 2),
                "vcpu_con_margen_30": math.ceil(necesarias * (1 + MARGEN) * 100) / 100,
                "vcpu_redondeadas": math.ceil(necesarias * (1 + MARGEN))}

    resultados["inferencia"] = {
        "cpu": "1 hilo", "bots": BOTS, "hz": HZ, "decisiones_s_requeridas": BOTS * HZ,
        "pytorch_sb3": capacidad(lat_sb3), "numpy_exportado": capacidad(lat_np),
        "numpy_coincide_con_sb3": f"{iguales}/1000",
    }
    with open(os.path.join(AQUI, "resultados", f"medicion_{nombre}.json"), "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
