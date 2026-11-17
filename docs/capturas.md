# Capturas de la entrega (AWS us-east-2, 16/11/2026)

Todas están en `docs/capturas/` y aparecen en el reporte (`docs/reporte/La-Torre-Anexo-Practicas.pdf`).

| Práctica | Archivo | Qué muestra |
|---|---|---|
| — | `3.0-presupuesto.png` | Alerta de presupuesto de USD 10 en AWS Budgets |
| 3.1 | `3.1-01-entrenamiento.png` | Entrenamiento de 100 000 pasos en CPU (160.4 s) |
| 3.1 | `3.1-02-medir.png` | `medir.py`: victorias, latencia de inferencia, vCPU |
| 3.2 | `3.2-01-pipeline-verde.png` | GitHub Actions con los dos trabajos en verde |
| 3.2 | `3.2-02-imagen-sha.png` | Imagen en ECR con la etiqueta del commit |
| 3.2 | `3.2-03-flota-actualizada.png` | Flota con la imagen nueva; la partida asignada conserva la anterior |
| 3.3 | `3.3-01-docker-run.png` | Servidor en un contenedor local |
| 3.3 | `3.3-02-metrics.png`, `3.3-02b-metrics-final.png` | Métricas `torre_*` en `/metrics` |
| 3.3 | `3.3-03-eks-nodos.png` | `kubectl get nodes` en EKS |
| 3.3 | `3.3-04-gameservers-antes.png` | GameServers en Ready |
| 3.3 | `3.3-05a-asignacion.png`, `3.3-05b-gameservers-despues.png` | GameServerAllocation: uno pasa a Allocated |
| 3.3 | `3.3-06a-borrar-pod.png`, `3.3-06b-flota-repuesta.png` | Borrar el pod Allocated y la flota reponiéndolo |
| 3.3 | `3.3-07-ecr.png` | Repositorio `torre-server` en ECR |
| 3.4 | `3.4-01-grafana.png` | Tablero de Grafana durante la rampa |
| 3.4 | `3.4-02-locust.png` | Resumen de Locust de la rampa |
| 3.4 | `3.4-03-nodos-escalando.png` | Nodos nuevos agregados por el Cluster Autoscaler |
| 3.4 | `loadtest/resultados/ccu_vs_p95.png`, `escalado.png`, `errores.png` | Gráficas generadas con `analizar.py` |
| 3.5 | `3.5-01a-url-post.png`, `3.5-01b-url-get.png` | POST y GET a la Function URL |
| 3.5 | `3.5-02-concurrencia.png` | CloudWatch: ConcurrentExecutions y Throttles |
| 3.5 | `3.5-03-locust.png` | Resumen de Locust de la prueba 80/20 |
| 3.6 | `3.6-01-pr-plan.png`, `3.6-01b-pr-costos.png` | Pull request con el `terraform plan` y su costo |
| 3.6 | `3.6-02-apply.png` | Plan sin cambios y salidas de Terraform |
| 3.6 | `3.6-03-cluster.png` | Clúster EKS activo en la consola |
| 3.6 | `3.6-04-destroy.png` | `Destroy complete! Resources: 38 destroyed.` |
| 3.6 | `3.6-05-sin-huerfanos.png` | `scripts/comprobar-huerfanos.ps1` sin recursos |
| Juego | `juego-01-menu.png`, `juego-02-combate.png`, `juego-03-mejoras.png` | Menú, combate y mejoras |

No se tomaron: la GPU de Colab (3.1, no medida).
