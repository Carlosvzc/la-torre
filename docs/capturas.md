# Capturas de pantalla por práctica

Guárdalas en `docs/capturas/` con el nombre indicado. Que en cada captura se vea la **fecha/hora**
(la barra de tareas de Windows sirve) y el comando completo.

## Práctica 3.3 — Contenerizar y orquestar

### En local (ya se pueden tomar)
| # | Archivo | Qué debe verse | Cómo obtenerla |
|---|---|---|---|
| 1 | `3.3-01-docker-run.png` | `docker run` del servidor y la línea `La Torre (modo torre) en :7654, métricas en :9100` | Ver abajo |
| 2 | `3.3-02-metrics.png` | Salida de `/metrics` filtrada a `torre_` con jugadores conectados > 0 | Ver abajo, **mientras juega el bot** |

```powershell
cd $HOME\OneDrive\Documents\la-torre\server
docker build -t torre-server:1.0 .
docker run --rm -p 7654:7654 -p 9100:9100 torre-server:1.0      # captura 1 (deja esta terminal abierta)
```

En una segunda terminal, lanza un bot y, a los ~10 s, pide las métricas:

```powershell
cd $HOME\OneDrive\Documents\la-torre\loadtest
& $HOME\.venvs\la-torre\Scripts\python.exe jugar_bot.py ws://localhost:7654 --jugadores 2
```

```powershell
(curl.exe -s localhost:9100/metrics) | Select-String "^torre_"      # captura 2
```

### En Kubernetes (kind en local; se repiten en GKE cuando haya nube)
| # | Archivo | Qué debe verse |
|---|---|---|
| 3 | `3.3-03-gameservers-antes.png` | `kubectl get gameservers` con 3 en `Ready` |
| 4 | `3.3-04-gameservers-despues.png` | Tras la `GameServerAllocation`, uno en `Allocated` |
| 5 | `3.3-05-borrar-allocated.png` | Borrado del pod `Allocated` y lo que hace la flota |

(Las prácticas 3.2, 3.4, 3.5 y 3.6 se agregan aquí cuando lleguemos a ellas.)
