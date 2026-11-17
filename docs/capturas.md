# Capturas de pantalla para la entrega (AWS, us-east-2)

Guárdalas en `docs/capturas/` con el nombre indicado. Que se vea la **fecha/hora** (barra de
tareas de Windows) y el comando completo. Te aviso en el chat cuándo tomar cada una.

## 3.1 — Bot de IA
| Archivo | Qué debe verse |
|---|---|
| `3.1-01-entrenamiento.png` | Terminal con `python ia\entrenar.py --device cpu --pasos 100000` y su tiempo |
| `3.1-02-medir.png` | Salida de `python ia\medir.py ia\modelos\bot_cpu_1m_8env.zip` (victorias, latencias, vCPU) |
| `3.1-03-colab-gpu.png` | (si se hace) notebook de Colab con la GPU T4 y la tabla CPU vs GPU |

## 3.3 — Contenedores y Agones
| Archivo | Qué debe verse |
|---|---|
| `3.3-01-docker-run.png` | `docker run --rm -p 7654:7654 -p 9100:9100 torre-server:1.5` arrancando |
| `3.3-02-metrics.png` | `curl.exe -s localhost:9100/metrics` filtrado a `torre_` con jugadores > 0 |
| `3.3-03-eks-nodos.png` | `kubectl get nodes` del clúster EKS |
| `3.3-04-gameservers-antes.png` | `kubectl get gameservers` con los servidores en **Ready** |
| `3.3-05-gameservers-despues.png` | Tras `kubectl create -f k8s/asignacion.yaml`: uno en **Allocated** |
| `3.3-06-borrar-allocated.png` | `kubectl delete pod <pod Allocated>` y lo que hace la flota |
| `3.3-07-ecr.png` | Consola de AWS → ECR → `torre-server` con la imagen y su etiqueta |

## 3.2 — CI/CD
| Archivo | Qué debe verse |
|---|---|
| `3.2-01-pipeline-verde.png` | GitHub → Actions → la corrida en verde con los dos trabajos |
| `3.2-02-imagen-sha.png` | ECR con la imagen etiquetada con el SHA del commit |
| `3.2-03-flota-actualizada.png` | `kubectl get gameservers` tras actualizar la flota a la imagen nueva |

## 3.4 — Carga y autoescalado
| Archivo | Qué debe verse |
|---|---|
| `3.4-01-grafana.png` | Tablero "La Torre" en Grafana durante la prueba |
| `3.4-02-locust.png` | Resumen de Locust al terminar la rampa |
| `3.4-03-nodos-escalando.png` | `kubectl get nodes` con nodos nuevos agregados por el autoescalado |
| Gráficas | `loadtest/resultados/ccu_vs_p95.png`, `escalado.png`, `errores.png` (se generan solas) |

## 3.5 — Serverless
| Archivo | Qué debe verse |
|---|---|
| `3.5-01-url.png` | `curl` a la Function URL: POST de un resultado y GET del top |
| `3.5-02-concurrencia.png` | CloudWatch → Lambda → `ConcurrentExecutions` durante la prueba 80/20 |
| `3.5-03-locust.png` | Resumen de Locust de la prueba 80/20 (p50, p99, errores) |

## 3.6 — Terraform
| Archivo | Qué debe verse |
|---|---|
| `3.6-01-pr-plan.png` | El pull request #1 con el plan revisado |
| `3.6-02-apply.png` | Final de `terraform apply`: `Apply complete! Resources: 60 added` y las salidas |
| `3.6-03-cluster.png` | Consola de AWS → EKS → clúster `la-torre-default` activo |
| `3.6-04-destroy.png` | Final de `terraform destroy`: `Destroy complete!` |
| `3.6-05-sin-huerfanos.png` | Comprobación de que no quedan EKS, EC2, ECR ni Lambda del proyecto |
