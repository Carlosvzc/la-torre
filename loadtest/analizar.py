"""Genera las 3 gráficas de la práctica 3.4 a partir de mediciones reales.

  1. CCU vs latencia p95 (del historial de Locust: <prefijo>_stats_history.csv, fila "rtt")
  2. Línea de tiempo del autoescalado: GameServers Ready/Allocated y nodos (registrar_escalado.py)
  3. Errores y "rebuffering" de espectadores durante el pico (historial de Locust)

Uso:  python analizar.py resultados/rampa resultados/escalado-rampa.csv resultados/pico
Las imágenes quedan en resultados/*.png y un resumen numérico en resultados/resumen.txt.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

META_P95_MS = 80


def historial(prefijo: str) -> pd.DataFrame:
    h = pd.read_csv(f"{prefijo}_stats_history.csv")
    h["segundo"] = h["Timestamp"] - h["Timestamp"].min()
    return h


def grafica_ccu_p95(prefijo: str, resumen: list) -> None:
    h = historial(prefijo)
    rtt = h[h["Name"] == "rtt"].copy()
    rtt["p95"] = pd.to_numeric(rtt["95%"], errors="coerce")
    rtt = rtt.dropna(subset=["p95"])
    plt.figure(figsize=(7, 4))
    plt.plot(rtt["User Count"], rtt["p95"], marker=".", linewidth=1)
    plt.axhline(META_P95_MS, linestyle="--", color="red", label=f"meta p95 = {META_P95_MS} ms")
    plt.xlabel("Jugadores simulados (CCU)"); plt.ylabel("Latencia p95 (ms)")
    plt.title("CCU vs latencia p95"); plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig("resultados/ccu_vs_p95.png", dpi=150); plt.close()
    pasa = rtt[rtt["p95"] > META_P95_MS]
    capacidad = int(pasa["User Count"].min()) if not pasa.empty else int(rtt["User Count"].max())
    resumen.append(f"Máximo CCU medido: {int(rtt['User Count'].max())}; p95 máximo: {rtt['p95'].max():.0f} ms")
    resumen.append(f"Capacidad (primer CCU con p95 > {META_P95_MS} ms, o el máximo si nunca se pasó): {capacidad}")


def grafica_escalado(csv: str, resumen: list) -> None:
    e = pd.read_csv(csv)
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(e["segundo"], e["ready"], label="Ready")
    ax1.plot(e["segundo"], e["allocated"], label="Allocated")
    ax1.plot(e["segundo"], e["gameservers"], label="Total GameServers", linestyle=":")
    ax1.set_xlabel("Segundos"); ax1.set_ylabel("GameServers")
    ax2 = ax1.twinx()
    ax2.step(e["segundo"], e["nodos"], where="post", color="black", label="Nodos")
    ax2.set_ylabel("Nodos")
    lineas = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    ax1.legend(lineas, [l.get_label() for l in lineas], loc="upper left")
    plt.title("Autoescalado: servidores y nodos en el tiempo"); plt.tight_layout()
    plt.savefig("resultados/escalado.png", dpi=150); plt.close()
    # Tiempo de reacción de nodos: primer pod pendiente → primer nodo nuevo listo
    base = e["nodos"].iloc[0]
    pend = e[e["pods_pendientes"] > 0]
    nuevo = e[e["nodos"] > base]
    if not pend.empty and not nuevo.empty:
        resumen.append(f"Reacción de nodos: pods pendientes en t={pend['segundo'].iloc[0]} s → nodo nuevo en "
                       f"t={nuevo['segundo'].iloc[0]} s ({nuevo['segundo'].iloc[0] - pend['segundo'].iloc[0]} s)")
    resumen.append(f"GameServers: de {e['gameservers'].iloc[0]} a {e['gameservers'].max()}; nodos: de {base} a {e['nodos'].max()}")


def grafica_errores(prefijo: str, resumen: list) -> None:
    h = historial(prefijo)
    total = h[h["Name"] == "Aggregated"]
    plt.figure(figsize=(7, 4))
    plt.plot(total["segundo"], total["Failures/s"], label="Errores/s (todas las peticiones)")
    esp = h[h["Name"] == "snapshot_espectador"]
    if not esp.empty:
        plt.plot(esp["segundo"], esp["Failures/s"], label="Snapshots tardíos/s (rebuffering)")
    plt.xlabel("Segundos"); plt.ylabel("Por segundo"); plt.title("Errores durante la prueba")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig("resultados/errores.png", dpi=150); plt.close()
    stats = pd.read_csv(f"{prefijo}_stats.csv")
    agg = stats[stats["Name"] == "Aggregated"].iloc[0]
    resumen.append(f"Peticiones: {int(agg['Request Count'])}, fallos: {int(agg['Failure Count'])} "
                   f"({100 * agg['Failure Count'] / max(1, agg['Request Count']):.2f} %)")


def main():
    rampa, escalado, pico = (sys.argv[1:4] + [None, None, None])[:3]
    os.makedirs("resultados", exist_ok=True)
    resumen = []
    if rampa:
        grafica_ccu_p95(rampa, resumen)
    if escalado:
        grafica_escalado(escalado, resumen)
    if pico:
        grafica_errores(pico, resumen)
    with open("resultados/resumen.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(resumen) + "\n")
    print("\n".join(resumen))


if __name__ == "__main__":
    main()
