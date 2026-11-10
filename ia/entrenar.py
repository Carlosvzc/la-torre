"""Entrena el bot con PPO y mide cuánto tarda (práctica 3.1, paso 3 y 5 del PDF).

Uso:
    python ia/entrenar.py --device cpu  --pasos 100000
    python ia/entrenar.py --device cuda --pasos 100000      # en Colab con GPU T4

Guarda el modelo en ia/modelos/ y una línea de resultados en ia/resultados/entrenamiento.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno_duelo import DueloJefe  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda", "auto"])
    ap.add_argument("--pasos", type=int, default=100_000)
    ap.add_argument("--entornos", type=int, default=1, help="entornos en paralelo (el PDF usa 1)")
    ap.add_argument("--semilla", type=int, default=0)
    ap.add_argument("--nombre", default=None)
    args = ap.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        sys.exit("No hay GPU CUDA disponible (en Colab: Entorno de ejecución → Cambiar tipo → T4 GPU)")
    nombre = args.nombre or f"bot_{args.device}_{args.pasos // 1000}k"
    env = make_vec_env(DueloJefe, n_envs=args.entornos, seed=args.semilla)
    modelo = PPO("MlpPolicy", env, verbose=0, device=args.device, seed=args.semilla)

    inicio = time.time()
    modelo.learn(total_timesteps=args.pasos)
    segundos = time.time() - inicio

    os.makedirs(os.path.join(AQUI, "modelos"), exist_ok=True)
    ruta = os.path.join(AQUI, "modelos", nombre)
    modelo.save(ruta)
    resultado = {
        "nombre": nombre, "device": str(modelo.device), "pasos": args.pasos, "entornos": args.entornos,
        "segundos": round(segundos, 1), "pasos_por_s": round(args.pasos / segundos),
        "cpu": platform.processor() or platform.machine(), "hilos_torch": torch.get_num_threads(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "torch": torch.__version__, "fecha": time.strftime("%Y-%m-%d %H:%M"),
    }
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    with open(os.path.join(AQUI, "resultados", "entrenamiento.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")
    print(f"Entrenamiento ({resultado['device']}): {segundos:.1f} s · {resultado['pasos_por_s']} pasos/s → {ruta}.zip")


if __name__ == "__main__":
    main()
