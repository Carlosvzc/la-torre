# PLAN — "La Torre" · Unidad 3 de Cómputo en la Nube

Roguelike de caballero contra 4 jefes, con servidor autoritativo y flota en Agones.
Adapta las prácticas 3.1 a 3.6 del PDF (Nebula Arena) a este juego.
Entrega: **16 nov 2026**. Trabajo individual.

> Regla de oro: **todo local hasta que haya cuenta de nube.** Nada de `gcloud`/`aws`/`terraform apply`
> que cree recursos sin explicar qué hace, cuánto cuesta (confirmado en la calculadora) y tener tu OK.
> Ningún resultado de carga ni costo se inventa: solo se reporta lo medido.

---

## 1. Estructura del repositorio

```
la-torre/
├── PLAN.md                      ← este archivo
├── README.md                    ← cómo correr todo en local y en la nube
├── server/                      ← servidor de partida (prácticas 3.3, 3.2)
│   ├── server.py                ← punto de entrada: WebSocket, tick 20/s, SDK Agones, /metrics
│   ├── juego/
│   │   ├── combate.py           ← vida, stamina, ataque, esquiva (i-frames), daño
│   │   ├── jefes.py             ← 4 jefes + jefe del día: ataques, fases, escalado de dificultad
│   │   ├── mejoras.py           ← catálogo de mejoras y sorteo de 3
│   │   ├── partida.py           ← máquina de estados de la run / duelo
│   │   └── bot.py               ← bot del duelo (reglas; luego la red de 3.1 en numpy)
│   ├── requirements.txt         ← websockets==12.0, prometheus-client==0.20.0 (numpy si entra el bot)
│   ├── Dockerfile               ← python:3.11-slim, USER 1000, puertos 7654 y 9100
│   └── tests/                   ← pytest: combate, jefes, mejoras, protocolo, ciclo Agones
├── emparejador/                 ← matchmaker del duelo (Deployment sin estado + HPA)
│   ├── main.py · Dockerfile · tests/
├── k8s/
│   ├── fleet-torre.yaml         ← Fleet de runs (1–4 jugadores por GameServer)
│   ├── fleet-duelo.yaml         ← Fleet de duelos (2 jugadores)
│   ├── fleet-jefedia.yaml       ← Fleet del jefe del día (MODO=jefe_dia; prueba de pico)
│   ├── autoscaler-*.yaml        ← FleetAutoscaler Buffer por flota
│   ├── emparejador.yaml         ← Deployment + Service + HPA
│   ├── podmonitor.yaml          ← Prometheus lee el puerto metrics
│   └── local/kind-config.yaml   ← clúster kind con puertos 7000–7100 expuestos
├── loadtest/                    ← práctica 3.4
│   ├── locustfile.py            ← Jugador (run completa con acciones aleatorias), Duelista, Espectador
│   ├── analizar.py              ← gráficas CCU vs p95, escalado y errores desde los CSV
│   └── resultados/              ← CSV y PNG de cada prueba real (con fecha)
├── serverless/leaderboard/      ← práctica 3.5 (Cloud Run + Firestore)
│   ├── main.py                  ← POST /resultado, GET /top/torre, GET /top/duelos
│   ├── requirements.txt · tests/
├── ia/                          ← práctica 3.1
│   ├── entorno_duelo.py         ← entorno Gymnasium: caballero vs jefe simplificado
│   ├── entrenar_bot.ipynb       ← PPO CPU vs GPU (Colab T4), latencia, decisiones/s
│   └── exportar.py              ← pesos de la política → .npz para inferir con numpy en el servidor
├── infra/                       ← práctica 3.6 (Terraform, Google Cloud)
│   ├── main.tf · variables.tf · red.tf · gke.tf · agones.tf · serverless.tf · outputs.tf
│   └── aws/                     ← variante AWS (solo si se cambia de nube)
├── grafana/tablero-torre.json   ← CCU, tick p99, servidores por estado, nodos, espectadores
├── .github/workflows/ci.yml     ← pytest → build → push con etiqueta = SHA del commit
├── docs/
│   ├── capturas.md              ← lista exacta de capturas y cuándo tomarlas
│   ├── practica-3.x.md          ← entregable de cada práctica
│   └── reporte-tecnico.md       ← máx. 6 páginas
└── cliente/                     ← EXTRA (solo si sobra tiempo): Three.js, 1 arena, 1 jefe
```

## 2. Decisiones de diseño (cambian algo respecto al PDF)

1. **Servidor autoritativo.** El cliente solo manda acciones (`mover`, `atacar`, `esquivar`, `bloquear`,
   `elegir_mejora`). El servidor simula todo a 20 ticks/s y manda un snapshot por tick. Esto hace que
   el tick **cueste CPU de verdad** (en Nebula el servidor solo reenvía posiciones), así que la capacidad
   por nodo saldrá menor y hay que medirla.
2. **Una sola imagen y un modo por variable:** `MODO=torre|duelo|jefe_dia`. Cada modo es su propia Fleet,
   así el autoescalado de cada una se ve por separado en Grafana.
3. **Ciclo Agones:** `/ready` al arrancar → la run se asigna (`Allocated`) → `/shutdown` cuando la run
   termina (victoria, muerte de todos o abandono) o tras un tiempo máximo. Latido `/health` cada 2 s.
4. **Duelo:** el `emparejador` (Deployment sin estado) junta parejas y pide un GameServer al allocator.
   Si en **5 s** no hay rival, el propio servidor del duelo mete al bot. El emparejador cubre la capa
   **HPA** del autoescalado, que la rúbrica pide (flota + pods + nodos).
5. **Espectadores por WebSocket** (`rol=espectador`, snapshot a 10 Hz, no ocupan lugar de jugador).
   Métricas `torre_spectators_connected` y `torre_bytes_sent_total` → el egress se **mide** y se
   extrapola a 20 000 con la fórmula del PDF. Si el profesor exige HLS, se agrega el escenario de video
   del PDF sin tocar lo demás.
6. **Bot de IA (3.1):** entorno Gymnasium propio del duelo en lugar de CartPole. La política se exporta a
   numpy para que la imagen no cargue PyTorch (cientos de MB). Si no da tiempo, el bot de reglas queda.
7. **Métricas del juego:** `torre_players_connected`, `torre_tick_seconds` (histograma), `torre_runs_total`
   (por resultado), `torre_boss_reached` (qué piso), `torre_spectators_connected`, `torre_bytes_sent_total`.
8. **Leaderboard:** el servidor manda el resultado al terminar (`LEADERBOARD_URL`). En local corre con
   almacenamiento en memoria/SQLite; Firestore solo en la nube. "Mejor tiempo" ordena ascendente.
9. **Local con kind:** Agones funciona en kind, pero el allocator no tiene IP pública; en local se asigna con
   `kubectl create -f` o `port-forward`. Los números de capacidad de kind **no** son los de la nube.

## 3. Límites de la nube a vigilar
- Prueba gratuita de Google Cloud: **máx. 8 vCPU**; la 3.4 necesita ~30–40 vCPU → hay que activar la
  cuenta completa (o pedir cuota) antes de esa práctica.
- Primera acción en la nube, siempre: **alerta de presupuesto de USD 10**.
- Al cerrar cada sesión: `terraform destroy` / borrar el clúster y verificar que no queden recursos.

---

## 4. Tareas

### Fase 0 — Herramientas (9 nov)
- [x] Leer el PDF completo
- [x] Instalar Helm 4.3.1, Terraform 1.17.0, kind 0.33.0, Python 3.11.9, gcloud 592
- [x] Docker Desktop encendido (Engine 29.9.2, 12 CPU, ~6.4 GB de RAM para Docker)
- [x] GitHub: `gh` 2.101 con sesión en la cuenta Carlosvzc (permisos repo + workflow)
- [x] Repo git en `Documentos\la-torre` + `.gitignore` + `.gitattributes` (LF) + README
- [x] Entorno virtual Python 3.11 fuera de OneDrive: `$HOME\.venvs\la-torre`
- [ ] Repo en GitHub para CI y para el PR de 3.6 (privado o público: a decidir)

> Nota: ~6.4 GB de RAM en Docker alcanzan para kind + Agones + 3–5 GameServers, pero
> kube-prometheus-stack es pesado; si se queda corto, subir la memoria en Docker Desktop
> (Settings → Resources) o instalar Prometheus/Grafana con valores reducidos.

### Fase 1 — Servidor de la Torre en local (9–10 nov) · base de 3.3
- [x] `combate.py`: vida, stamina (gasto y regeneración), ataque, esquiva con i-frames + tests
- [x] `jefes.py`: 4 jefes × 2–3 ataques, fases por % de vida, escalado por piso + tests
- [x] `mejoras.py`: catálogo de 9 y sorteo de 3 (semilla para tests) + tests
- [x] `partida.py`: run de 1–4 jugadores, jefe → mejora → siguiente jefe → fin + tests
- [x] Balance: bot de prueba con reflejos perfectos gana 10/10 semillas, runs de 5–8.5 min
- [x] `server.py`: WebSocket, tick 20/s, protocolo JSON, ping/pong, métricas, SDK Agones, espectadores
- [x] Pruebas de red con cliente WebSocket real (11 pruebas; 51 en total)
- [x] Bot cliente por WebSocket (`loadtest/jugar_bot.py` + `estrategia.py`, reutilizable por Locust)
- [x] Dockerfile (imagen de 189 MB); `docker build` + `docker run` + `/metrics` funcionando
- [x] Auditoría (9 nov): 8 fallos corregidos con 21 pruebas de regresión (72 en total), imagen 1.1
- [x] Cliente 2D de pruebas en el navegador (`cliente/prueba2d/`): jugar, cooperativo y espectador
- [x] Colisión caballero–jefe (encontrada al probar el cliente); imagen 1.3, 73 pruebas
- [ ] Tomar **capturas 3.3 (1 y 2)** siguiendo `docs/capturas.md`
- [x] Locust local: `Jugador` (run completa, RTT) y `Espectador` (huecos y bytes) contra el servidor
- [x] Corregido: el latido `/health` congelaba los ticks ~2 s cada 2 s (encontrado con Locust; 75 pruebas)
- [x] Auditoría de Locust: el cierre de la run congelaba ~3 s la partida (ahora en segundo plano),
      rechazos con código claro (4003/4004), espectadores ya no fallan en silencio, runs contadas
      una vez, pongs perdidos; métrica nueva `torre_tick_lag_seconds` (81 pruebas)
- [ ] Verificar en kind: `/ready` con el sidecar de Agones (hoy se intenta una sola vez al arrancar)
- [ ] Commit por cada pieza

### Fase 2 — Práctica 3.1 (11 nov)
- [x] `entorno_duelo.py` (Gymnasium) reutilizando la lógica real del servidor
- [x] Entrenar PPO en CPU local: 100k pasos en 158.8 s (20 % victorias); 1M pasos en 928.6 s (100 %)
- [ ] Entrenar en GPU T4 de Colab (**te toca**: notebook `ia/entrenar_bot_colab.ipynb`)
- [x] Latencia de inferencia y decisiones/s por núcleo (PyTorch 0.43 ms vs numpy 0.016 ms)
- [x] Cálculo de vCPU para 2 000 bots a 10 Hz (12 con PyTorch, 1 con numpy)
- [ ] Costo por hora con la calculadora oficial (**te toca**: 3 recursos en `docs/practica-3.1.md`)
- [x] `docs/practica-3.1.md` (falta solo la columna de GPU, el análisis CPU vs GPU y el costo)

### Fase 3 — Kubernetes local y archivos de nube validados (11 nov)
- [ ] Clúster kind + Agones con Helm
- [ ] Fleets, FleetAutoscalers, PodMonitor; `kubectl apply` en kind
- [ ] `kubectl get gameservers` antes/después de `GameServerAllocation` → **capturas 3.3 (3 y 4)**
- [ ] Borrar un pod `Allocated` y documentar lo que pasa
- [ ] Prometheus + Grafana en kind; tablero con CCU, tick p99, servidores por estado, nodos
- [ ] `infra/` Terraform: `terraform init -backend=false` + `terraform validate` + `fmt`
- [ ] `.github/workflows/ci.yml`: pytest en verde en GitHub (publicar imagen cuando haya registro)

### Fase 4 — Modos 2 y 3 (solo con la Torre funcionando)
- [ ] Duelo PvP 1v1 + emparejador + bot a los 5 s + tests
- [ ] Jefe del día (`MODO=jefe_dia`) + Fleet propia
- [x] Espectadores por WebSocket + métricas de egress (`torre_bytes_sent_total`, hecho en la Fase 1)

### Fase 5 — Leaderboard serverless en local (11–12 nov)
- [ ] `serverless/leaderboard/main.py` con almacén intercambiable (memoria / Firestore) + tests
- [ ] El servidor reporta tiempo de la torre y victorias de duelo

### Fase 6 — Nube (12–13 nov) · cada paso con tu OK y costo confirmado
- [ ] Resolver la cuenta (GCP o AWS) · alerta de presupuesto USD 10
- [ ] 3.3 en GKE: Artifact Registry, clúster, Agones, flota, asignación → capturas
- [ ] 3.2: pipeline publica `torre-server:<sha>`, actualización de flota con drenado, párrafo de rollback
- [ ] 3.5: Cloud Run + Firestore, URL, prueba Locust 80/20, métrica de concurrencia, costo vs VM
- [ ] 3.6: `terraform plan` en PR, `apply`, captura del clúster, `destroy` sin huérfanos
- [ ] `terraform destroy` al final de cada sesión

### Fase 7 — Práctica 3.4 en la nube (14 nov)
- [ ] VM de Locust en la misma región
- [ ] Rampa 1 000 jugadores, pico 1 000 en 20 s (jefe del día), 500 espectadores
- [ ] Gráficas: CCU vs p95, Ready/Allocated/nodos en el tiempo, errores durante el pico
- [ ] Capacidad por nodo, tiempo de reacción, recomendación de bufferSize/máquina/mínimo de nodos
- [ ] Extrapolación de espectadores a 20 000 · `destroy`

### Fase 8 — Entrega (15–16 nov)
- [ ] Reporte técnico (≤ 6 páginas) con costo por hora y por jugador
- [ ] Tablero de Grafana exportado
- [ ] Presentación de 10 min + guion de la demo del autoescalado
- [ ] Revisar `docs/capturas.md` completo

### Extra — Cliente gráfico (solo si sobra tiempo)

**Dirección de arte:** 3D retro de la era de 64 bits (finales de los 90), **no realista**: low-poly
de aventura en tercera persona, con texturas nítidas en alta resolución y ambiente oscuro de fantasía.
Inspiración de *época y técnica*, no de un juego concreto: nada de personajes, lugares, logos,
música ni diseños reconocibles de Nintendo o FromSoftware. Caballero, jefes y arena son diseños propios.

| Rasgo de la época | Cómo se logra en Three.js |
|---|---|
| Pocos polígonos | Personajes de ~500–1 500 triángulos, arena de geometría simple |
| Sombreado plano o Gouraud, sin PBR | `MeshLambertMaterial` / `flatShading`, sin mapas normales ni reflejos |
| Niebla de distancia | `scene.fog` oscura que esconde el fondo |
| Paleta limitada y saturada | Colores de vértice + texturas con paleta reducida |
| Sombra simple | Círculo oscuro bajo cada personaje (*blob shadow*) |
| Cámara de aventura | Tercera persona con fijación de objetivo sobre el jefe |
| Efectos de sprite | Destellos y polvo como *billboards* |

- **Texturas en alta resolución** (decisión tuya): se conserva la forma low-poly y la nitidez moderna.
  Opción de un filtro "pixelado" (render a baja resolución + escalado `nearest`) para comparar.
- **El servidor ya da lo que el cliente necesita:** posición y orientación (`x, y, dx, dy`), estado
  (`atacando`, `esquivando`, `muerto`) para elegir la animación, y el **aviso** del jefe (`zonas`,
  `radio`, `en`) que se dibuja como un círculo rojo en el suelo que se va llenando.
  El servidor simula en un plano 2D y el cliente lo pinta en 3D sobre el suelo de la arena.
- **Assets libres (CC0) en estilo parecido:** Quaternius (personajes y armas low-poly), Kenney
  (piezas de mazmorra), OpenGameArt (texturas de piedra). Se anota la licencia de cada uno en
  `cliente/CREDITOS.md`.
- **Alcance máximo:** una arena y un jefe. Se califica la infraestructura, así que el cliente nunca
  retrasa una práctica.

- [x] Escena Three.js (`cliente/retro/`): arena con niebla, braseros, columnas y puerta; texturas
      generadas en alta resolución (losas, ladrillo, metal, tela) — sin assets de terceros
- [x] Caballero y 5 jefes low-poly generados por código, con animaciones (paso, tajo, voltereta,
      muerte; el jefe alza el arma y brilla al preparar, surge del suelo y se hunde al morir)
- [x] Cámara en tercera persona con el jefe fijado y movimiento relativo (estilo Souls)
- [x] Avisos en el suelo, ondas de impacto, chispas, números de daño, sacudida de cámara, sonido sintetizado
- [x] HUD: vida/resistencia, barra del jefe con fases, bendiciones, sala de espera, fin de run
- [x] Modo espectador (cámara orbital) y modo pixelado (`P`)
- [ ] Probarlo jugando tú (balance, sensación de control) y ajustar

## 5. Decisiones pendientes
- ¿El profesor acepta espectadores por WebSocket en lugar de HLS?
- ¿Dónde vive el repo en tu PC? (la carpeta actual de la sesión es temporal)
- ¿Google Cloud o AWS? (se decide cuando se resuelva la facturación)
