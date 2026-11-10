# Pruebas de carga (práctica 3.4)

`locustfile.py` simula **jugadores** que juegan runs completas (20 acciones/s y un ping por segundo)
y **espectadores** que reciben el estado por WebSocket (10 snapshots/s).

```powershell
& $HOME\.venvs\la-torre\Scripts\python.exe -m pip install -r loadtest\requirements.txt
```

## En local (un solo servidor, máximo 4 jugadores por run)

> Usa `127.0.0.1`, no `localhost`: en Windows `localhost` intenta primero IPv6 y cada conexión
> tarda ~2 s extra (lo medimos: 2000 ms contra 6–12 ms).

```powershell
cd $HOME\OneDrive\Documents\la-torre\loadtest
$env:SERVIDOR_WS = "ws://127.0.0.1:7654"; $env:JUGADORES_POR_RUN = "2"; $env:HABILIDAD = "0.5"
& $HOME\.venvs\la-torre\Scripts\locust.exe -f locustfile.py Jugador Espectador -u 4 -r 4 -t 75s --headless --csv resultados/local
```

Sin `--headless` abre la interfaz web de Locust en http://localhost:8089.

## Contra Agones (kind o la nube)

```powershell
$env:ALLOCATOR_IP = "<IP del allocator>"; Remove-Item Env:SERVIDOR_WS -ErrorAction SilentlyContinue
locust -f locustfile.py Jugador -u 1000 -r 2 -t 20m --headless --processes -1 --csv resultados/rampa
```

`--processes` no funciona en Windows: en la nube Locust corre en una VM Linux (como indica el PDF).

**Espectadores con Agones:** encuentran las runs a través de los jugadores *del mismo proceso*.
Lánzalos en el mismo comando (`Jugador Espectador`, con `--class-picker` o pesos) o pásales
`ESPECTAR=ws://ip:puerto,...`. Si no tienen runs que mirar, aparece el error `sin_runs`
(antes la prueba "pasaba" con 0 peticiones).

**Vigila la CPU de la VM de Locust:** si se satura, el RTT y los huecos de los espectadores
suben por culpa del generador, no del servidor. Compáralo con `torre_tick_lag_seconds` del servidor.

## Códigos de rechazo del servidor
| Código | Motivo |
|---|---|
| 4000 | Partida llena (4 jugadores) |
| 4001 | La run ya empezó |
| 4002 | Primer mensaje inválido (se esperaba `{"hola": {...}}`) |
| 4003 | La run está terminando (Locust espera 3 s antes de reintentar) |
| 4004 | Ese id ya está en la partida |

## Variables
| Variable | Defecto | Qué hace |
|---|---|---|
| `SERVIDOR_WS` | — | Modo local: siempre este servidor |
| `ALLOCATOR_IP` | — | Modo Agones: pide un GameServer por grupo |
| `FLOTA` | `torre-fleet` | Fleet de Agones a la que se piden servidores |
| `JUGADORES_POR_RUN` | 2 | Tamaño del grupo (1–4) |
| `HABILIDAD` | 0.85 | 0–1: qué tan bien esquiva y elige cuándo atacar |

## Qué mide cada fila de Locust
| Tipo / nombre | Significado |
|---|---|
| `ALLOC asignacion` | Tiempo de pedir un GameServer al allocator |
| `WS conexion` | Abrir el WebSocket y recibir la bienvenida |
| `WS rtt` | Latencia ida y vuelta (ping → pong) |
| `RUN run_victoria` / `run_derrota` | Una run terminada; el "tiempo" es la duración del combate |
| `WS snapshot_espectador` | Hueco entre snapshots (≈100 ms); > 300 ms cuenta como `SnapshotTardio` (el "rebuffering"); los bytes sirven para el egress |

Las runs se cuentan **una vez por run** (la reporta el primer jugador del grupo por id).

## Resultados medidos
| Fecha | Prueba | Resultado |
|---|---|---|
| 9 nov | Local, 2 jugadores + 2 espectadores, 75 s | Conexión 6–12 ms; RTT mediana 1 ms, p99 11 ms; snapshots de espectador mediana 100 ms, 2 de 1 358 tardíos (~456 ms); 1 run terminada |
| 9 nov | Igual, tras la auditoría | Conexión 5–10 ms; RTT mediana 1 ms, p99 2 ms; espectadores mediana 100 ms, 2 de 1 462 tardíos (~480 ms) **del lado de Locust**: en el servidor ningún tick empezó > 50 ms tarde (1 543 ticks, retraso medio 8 ms en Windows); 1 run contada una vez |
