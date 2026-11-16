"""Registra cada 5 s el estado de la flota y del clúster durante una prueba de carga (práctica 3.4).

Escribe resultados/escalado-<nombre>.csv con: segundo, Ready, Allocated, Scheduled/Creating,
total de GameServers, nodos listos y pods pendientes. Con esto se mide el tiempo de reacción
del autoescalado (de cuándo sube la carga a cuándo llegan servidores y nodos nuevos).

Uso (con kubectl apuntando al clúster):  python registrar_escalado.py rampa
Ctrl+C para terminar.
"""
import csv
import json
import os
import subprocess
import sys
import time


def kubectl(*args) -> dict:
    salida = subprocess.run(["kubectl", *args, "-o", "json"], capture_output=True, text=True, timeout=20)
    return json.loads(salida.stdout or "{}")


def main():
    nombre = sys.argv[1] if len(sys.argv) > 1 else "prueba"
    os.makedirs("resultados", exist_ok=True)
    ruta = os.path.join("resultados", f"escalado-{nombre}.csv")
    inicio = time.time()
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segundo", "ready", "allocated", "arrancando", "gameservers", "nodos", "pods_pendientes"])
        print(f"Registrando en {ruta} (Ctrl+C para terminar)")
        try:
            while True:
                gs = kubectl("get", "gameservers").get("items", [])
                estados = [g.get("status", {}).get("state", "") for g in gs]
                nodos = kubectl("get", "nodes").get("items", [])
                listos = sum(any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"]) for n in nodos)
                pendientes = len(kubectl("get", "pods", "--field-selector=status.phase=Pending").get("items", []))
                fila = [round(time.time() - inicio), estados.count("Ready"), estados.count("Allocated"),
                        sum(e in ("Scheduled", "Creating", "Starting", "PortAllocation", "RequestReady") for e in estados),
                        len(gs), listos, pendientes]
                w.writerow(fila)
                f.flush()
                print(dict(zip(["s", "ready", "allocated", "arrancando", "total", "nodos", "pendientes"], fila)))
                time.sleep(5)
        except KeyboardInterrupt:
            print("Listo:", ruta)


if __name__ == "__main__":
    main()
