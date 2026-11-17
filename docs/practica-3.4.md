# Práctica 3.4 — Pruebas de carga y autoescalado en EKS (AWS us-east-2)

Fecha: 16/11/2026. Clúster `la-torre-default` (EKS 1.35), nodos **c7i-flex.large** (2 vCPU, 4 GiB),
Cluster Autoscaler entre 2 y **8** nodos, Agones 1.62 con `torre-fleet` (FleetAutoscaler Buffer 20 %,
mín. 3) y cada GameServer pidiendo 250m de CPU. Todo lo de abajo es **medido**; las proyecciones
están marcadas como tales.

## Montaje

- **Monitoreo:** kube-prometheus-stack 93.3.0 (`k8s/monitoreo/valores-prometheus.yaml`), PodMonitor del
  juego (`k8s/podmonitor.yaml`, cada 5 s) y ServiceMonitor del controlador de Agones. Tablero
  `grafana/tablero-torre.json` (10 paneles) cargado por el sidecar de Grafana. Sin balanceadores ni discos.
- **Generador de carga dentro del clúster** (misma región que los servidores, `k8s/locust.yaml`): pod de
  Locust 2.47 con 1.5 vCPU reservadas y una cuenta de servicio que solo puede crear
  `GameServerAllocation`. Cada grupo de 3 jugadores simulados pide un servidor a la API de Kubernetes
  (lo mismo que `kubectl create -f k8s/asignacion.yaml`) y se conecta por la IP interna del nodo.
  Se eligió así porque la SCP de la cuenta impide el OIDC y el allocator quedó sin balanceador.
- **Registro de escalado:** `loadtest/registrar_escalado.py` (cada ≈ 11 s, `resultados/escalado-rampa.csv`).

## Pruebas

| Prueba | Clases | Usuarios | Duración | Hora (UTC) |
|---|---|---|---|---|
| Rampa | Jugador (grupos de 3) | 0 → 120, 0.15/s | 18 min | 20:18:29–20:36:35 |
| Pico | Jugador + Espectador (50/50) | 60, 10/s | 3 min | 20:41:27–20:44:30 |

Un primer intento de pico (20:36:55, 120 usuarios, 2 procesos) no se usa: los espectadores quedaron en
otro proceso que los jugadores y no encontraron runs (4 710 errores `sin_runs`).

## Resultados

### Rampa (`loadtest/resultados/rampa_*.csv`, `rampa_resumen.txt`)

| Métrica | Valor |
|---|---|
| RTT (ping cada segundo) | 73 537 medidos, **0 fallos**; p50 1 ms, p95 2 ms, **p99 6 ms**, p99.9 25 ms |
| Runs completas | **172** (65 victorias, 107 derrotas); duración mediana ≈ 2 min |
| Asignaciones | 1 118 intentos, 911 sin servidor libre (`UnAllocated`, se reintenta cada 1 s) |
| Conexiones WebSocket | 621, 10 fallidas (1.6 %) |
| Duración del tick p99 (Prometheus) | ≤ **2.21 ms** (meta < 25 ms) |

### Pico con espectadores (`loadtest/resultados/pico_*.csv`)

| Métrica | Valor |
|---|---|
| Snapshots a espectadores | **51 039, 0 tardíos** (> 300 ms); intervalo p50 100 ms, p99 100 ms |
| RTT de jugadores | p50 1 ms, p99 3 ms, 0 fallos |
| Espectadores conectados (CCV) | 30–31 |

### Autoescalado (`escalado-rampa.csv`, gráfica `escalado.png`)

- **Capa 1, Agones (FleetAutoscaler):** los GameServers pasaron de **5 a 54**.
- **Capa 2, Cluster Autoscaler:** los nodos pasaron de **4 a 8** (el tope configurado):
  4 → 5 a los 288 s, → 6 a los 366 s, → 7 a los 458 s, → 8 a los 540 s.
- **Tiempo de reacción de nodos:** primer pod pendiente a los 80 s → primer nodo nuevo listo a los
  288 s = **208 s (≈ 3.5 min)**, con muestreo de ≈ 11 s. Ese tiempo incluye la decisión del Cluster
  Autoscaler, el arranque de la instancia EC2 y su registro en el clúster.
- **Límite alcanzado:** con 8 nodos, a partir del minuto 10–11 los Allocated se quedaron entre **35 y 39** (≈ 105–117
  jugadores, ~13–15 por nodo) y los pods pendientes subieron a 10. Por eso fallaron las asignaciones del final: no es el
  servidor el que se satura (tick p99 2 ms), sino la **reserva de CPU del clúster** (8 nodos × 2 vCPU con
  250m por GameServer, más Agones, Prometheus y el propio Locust).

### Recursos medidos por Prometheus (últimos 5 min de la rampa, 110 jugadores en 37.6 servidores)

| Métrica | Valor medido | Por unidad |
|---|---|---|
| CPU de los contenedores `torre` | 0.667 núcleos (máx. 0.731) | **17.7 milinúcleos por servidor**, 6.1 por jugador |
| Egress de jugadores | 13.07 Mbps (máx. 13.61) | **119 kbps por jugador** |
| Egress a espectadores (pico) | 1.72 Mbps con 30.2 espectadores | **57 kbps por espectador** |

## Gráficas (`loadtest/resultados/`)

- `ccu_vs_p95.png`: CCU contra p95. Con `--processes 2` Locust solo guarda la fila "Aggregated" en el
  historial, que mezcla el RTT con las asignaciones (300–500 ms). Por eso el "p95 máximo 500 ms" del
  resumen automático es el de las asignaciones, no el del juego: el RTT medido es p99 6 ms en toda la
  rampa (tabla de arriba). La meta de p95 < 80 ms **nunca se rompió para el RTT**.
- `escalado.png`: Ready, Allocated y total de GameServers contra nodos.
- `errores.png`: errores por segundo y snapshots tardíos en el pico (0).

## Capacidad y extrapolación a 20 000 jugadores (proyección)

Precios oficiales de us-east-2 (AWS Price List API, 16/11/2026): c7i-flex.large USD 0.08479/h, IPv4
pública USD 0.005/h, EKS USD 0.10/h, salida a internet USD 0.09/GB (primeros 10 TB/mes), 0.085
(siguientes 40 TB), 0.07 (siguientes 100 TB) y 0.05 (más de 150 TB).

- **Servidores:** 20 000 / 3 por partida = **6 667 GameServers**.
- **Cómputo con la configuración actual (250m por servidor):** un c7i-flex.large tiene ≈ 1.9 vCPU
  asignables → 7 servidores por nodo → **≈ 953 nodos** → USD 80.8/h + IPv4 USD 4.8/h ≈ **USD 86/h**.
- **Cómputo ajustado a lo medido:** cada servidor usa 18 milinúcleos. Con una reserva de 50m (≈ 2.8× lo
  medido), el límite pasa a ser el de pods por nodo del CNI de AWS (29 en c7i-flex.large) → ≈ 25
  servidores por nodo → **≈ 267 nodos** → USD 22.6/h + 1.3/h ≈ **USD 24/h**. Es la mejora más grande
  que deja la prueba: la reserva de 250m es ≈ 14 veces el consumo real.
- **Egress:** 20 000 × 119 kbps = **2.38 Gbps ≈ 1 071 GB por hora** → **USD 54–96/h** según el tramo
  (0.05–0.09 USD/GB). Con el cómputo ajustado, **el egress pasa a ser el costo dominante**: la siguiente
  optimización sería enviar deltas o comprimir los snapshots.
- **Autoescalado:** con ≈ 3.5 min de reacción por nodo, un pico de jugadores necesita colchón. El Buffer
  del 20 % se agotó durante la rampa; para eventos conviene subir el buffer o dejar nodos de reserva.

## Limitaciones honestas

- El generador comparte el clúster con los servidores (con CPU reservada para él). El tick del servidor
  (p99 ≤ 2.2 ms) y el RTT (p99 6 ms) indican que no hubo saturación del lado del juego.
- La carga máxima fue de 120 jugadores por el tope de 8 nodos que pusimos para cuidar el presupuesto;
  la extrapolación a 20 000 asume que el consumo por servidor y por jugador se mantiene lineal.
- En 302 casos de la rampa un jugador simulado pasó más de 5 s sin recibir estado (`snapshot`,
  WebSocketTimeout), casi siempre al final de una run, mientras el servidor se cierra. Además hubo 6
  respuestas inesperadas en la sala de espera. No se confirmó la causa; queda anotado como pendiente.

## Capturas

- `docs/capturas/3.4-01-grafana.png`: tablero con 112 jugadores, servidores Allocated y nodos 4 → 8
- `docs/capturas/3.4-02-locust.png`: resumen de Locust de la rampa
- `docs/capturas/3.4-03-nodos-escalando.png`: `kubectl get nodes` con 4 nodos nuevos (4–9 min de edad)

## Egress de espectadores extrapolado a 20 000 (fórmula del material)

GB/hora = CCV × kbps × 3600 / 8 000 000. Precios de salida a internet en us-east-2: USD 0.09/GB (primeros
10 TB del mes) a 0.05/GB (más de 150 TB).

| Caso | kbps por espectador | Datos en una hora | Costo de la hora |
|---|---|---|---|
| Estado del juego (medido) | 57 | 513 GB | USD 26–46 |
| Video 1080p (6 000 kbps) | 6 000 | 54 000 GB (54 TB) | USD 2 700–4 860 (≈ 4 599 con los tramos desde el inicio del mes) |
