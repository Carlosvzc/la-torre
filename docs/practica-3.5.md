# Práctica 3.5 — Tabla de líderes serverless (AWS Lambda + DynamoDB)

Infraestructura: `infra/serverless.tf` (Terraform). Función `la-torre-default-lideres` (Python 3.12,
256 MB), tabla DynamoDB bajo demanda `la-torre-default-lideres` y Function URL pública en us-east-2.
Código: `serverless/leaderboard/lambda_function.py` (9 pruebas en `test_lambda.py`).

## 1. URL funcionando

```
POST https://su6erhyovhgplzvnxmo22qulu40glxpk.lambda-url.us-east-2.on.aws/resultado
     {"sala":"solo","jugadores":["Carlos"],"victoria":true,"tiempo_s":182.5}
→ {"registrados": 1}
GET  .../?sala=solo
→ [{"jugador": "Carlos", "mejor_tiempo": 182.5, "victorias": 1, "runs": 1}]
```

Hallazgo: la primera prueba dio **403 Forbidden**. Una Function URL pública necesita en la política
de la función los permisos `lambda:InvokeFunctionUrl` **y** `lambda:InvokeFunction`; la consola los
agrega sola, Terraform no. Se agregaron como `aws_lambda_permission` en `serverless.tf`.

## 2. Prueba de carga (16/11/2026, 19:44:41–19:49:44 UTC)

`loadtest/locust_lideres.py`: 80 % `GET` del top y 20 % `POST` de resultados, **500 usuarios**
(50 nuevos por segundo), 5 minutos, desde una PC en Colima (México) hacia us-east-2.
Las escrituras usan un grupo fijo de 200 jugadores (como jugadores reales que repiten partidas):
si cada escritura inventara un jugador nuevo, la tabla crecería sin parar y cada `GET` (un *scan*)
leería cada vez más; con 500 usuarios × 5 min el estimado era ≈ USD 2 contra ≈ USD 0.35.

### Resultados medidos (Locust, `loadtest/resultados/lideres_*.csv`)

| | Peticiones | Fallidas | p50 | p95 | p99 | p99.9 | Máx | req/s |
|---|---|---|---|---|---|---|---|---|
| GET top | 106 666 | 85 505 (80.2 %) | 71 ms | 150 ms | 360 ms | 2 400 ms | 4 880 ms | 357 |
| POST resultado | 26 703 | 21 435 (80.3 %) | 71 ms | 130 ms | 350 ms | 2 500 ms | 5 129 ms | 89 |
| **Total** | **133 369** | **106 940 (80.2 %)** | 71 ms | 150 ms | 360 ms | 2 500 ms | 5 129 ms | 447 |

Todas las fallas son **HTTP 429 Too Many Requests** (Lambda las rechaza sin ejecutarlas).

### Métricas de CloudWatch (por minuto, función `la-torre-default-lideres`)

| Minuto (hora local) | ConcurrentExecutions (máx) | Invocations | Throttles | Duration prom. |
|---|---|---|---|---|
| 13:44 | 10 | 931 | 3 530 | 52.7 ms |
| 13:45 | 10 | 5 375 | 21 220 | 39.9 ms |
| 13:46 | 10 | 5 628 | 21 948 | 52.7 ms |
| 13:47 | 10 | 5 321 | 22 022 | 56.5 ms |
| 13:48 | 10 | 5 399 | 22 098 | 58.6 ms |
| 13:49 | 10 | 2 712 | 10 900 | 60.1 ms |
| **Total** | — | **25 366** | **101 718** | ≈ 53 ms |

Logs de la función: **10 arranques en frío** en toda la prueba (uno por instancia), *Init Duration*
promedio 93.3 ms (máx. 103.1 ms); memoria usada 90 MB de 256 MB.

### Interpretación

- **Instancias concurrentes: 10, todo el tiempo.** `aws lambda get-account-settings` muestra
  `ConcurrentExecutions = 10`: es el límite de concurrencia de las cuentas nuevas de AWS (el normal es
  1 000). Lambda llegó al tope en el primer minuto y rechazó con 429 todo lo que pasaba de ahí.
  Es el resultado más importante de la práctica: **"serverless escala solo" tiene un límite de
  cuenta**, y hay que pedir el aumento (Service Quotas → Lambda → *Concurrent executions*) antes de
  un lanzamiento. Con 10 instancias la función atendió ≈ 85 peticiones/s exitosas.
- **Arranque en frío:** solo 10 de 25 366 invocaciones (0.04 %) lo pagaron, y su inicialización fue de
  ≈ 93 ms. Con tan pocos casos el arranque en frío **no explica** el p99 de 360 ms ni la cola de 2–5 s;
  esa cola coincide con la saturación (las peticiones esperan en la Function URL y en la red desde
  México, y la PC generaba 447 req/s). Con el límite normal de 1 000 se crearían más instancias y
  aparecerían más arranques en frío durante la subida.
- La función es rápida (≈ 53 ms por petición con un *scan* de ≈ 600 jugadores). El *scan* crece con la
  tabla: en producción, el top se guardaría ya calculado (índice secundario o caché).

## 3. Costo: serverless contra una VM pequeña todo el mes

Precios oficiales de us-east-2 (AWS Price List API, 16/11/2026): Lambda USD 0.20 por millón de
peticiones + USD 0.0000166667 por GB-s; DynamoDB bajo demanda USD 0.125 por millón de unidades de
lectura y USD 0.625 por millón de escritura; t3.micro USD 0.0104/h, t3.small USD 0.0208/h, IPv4 pública
USD 0.005/h, gp3 USD 0.08 por GB-mes.

**Esta prueba** (las peticiones rechazadas con 429 no se cobran):
Lambda 25 366 × 0.20/M = USD 0.005, más 25 366 × 0.053 s × 0.25 GB = 336 GB-s → USD 0.006;
DynamoDB ≈ 20 000 *scans* × 7.5 unidades = 150 000 lecturas → USD 0.02, más ≈ 6 600 escrituras →
USD 0.004. **Total ≈ USD 0.04** (estimado; se confirma en Cost Explorer al día siguiente).

**Un mes con 1 millón de peticiones** (80/20, misma tabla):

| Opción | Cálculo | USD/mes |
|---|---|---|
| Lambda + DynamoDB | 0.20 + 0.22 (cómputo) + 0.75 (6 M lecturas) + 0.16 (260 k escrituras) | **≈ 1.33** (≈ 0.91 con la capa gratuita de Lambda) |
| VM t3.micro 24/7 | 0.0104 × 730 + IPv4 3.65 + disco 8 GB 0.64 | **≈ 11.88** |
| VM t3.small 24/7 | 0.0208 × 730 + 3.65 + 0.64 | **≈ 19.47** |

Con estos precios, serverless sale más barato hasta ≈ **9 millones de peticiones al mes** contra la
t3.micro (11.88 / 1.33). Sin jugadores, la tabla serverless cuesta casi cero y la VM cobra igual. Para
una tabla de líderes (tráfico a ráfagas, alrededor de la partida) conviene serverless; el servidor
autoritativo de 20 ticks/s, en cambio, necesita proceso continuo y va en Agones.

## Capturas

- `docs/capturas/3.5-01-url.png` — `curl` POST y GET a la Function URL
- `docs/capturas/3.5-02-concurrencia.png` — CloudWatch, `ConcurrentExecutions` en 10 durante la prueba
- `docs/capturas/3.5-03-locust.png` — resumen de Locust
