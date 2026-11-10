# Práctica 3.1 — Entrenar y servir el bot de La Torre

**Objetivo (PDF):** entrenar un agente de aprendizaje por refuerzo en un entorno simulado y medir el
costo y la latencia de su inferencia.

**Adaptación al juego:** en lugar de CartPole, el agente es **un caballero que pelea contra el Guardián
de Hierro** usando la lógica real del servidor (`server/juego`). Lo que aprende sirve en el juego:
como rival del duelo cuando no aparece nadie, o como jugador de IA.

## Entorno (`ia/entorno_duelo.py`)
| Elemento | Diseño |
|---|---|
| Biblioteca | Gymnasium 1.4.0 (pasa `check_env`); Stable-Baselines3 2.9.2, PPO `MlpPolicy` (64-64, tanh) |
| Frecuencia de decisión | **10 Hz**: cada acción dura 2 ticks del servidor (0.1 s) |
| Observación (14) | posición relativa y distancia al jefe, vida y resistencia propias, estado propio (3), estado del jefe (3), tiempo hasta el impacto, distancia al borde de la zona de golpe, vida del jefe |
| Acciones (7) | quieto, acercarse, alejarse, rodear izq./der., atacar, esquivar |
| Recompensa | +daño causado/10, −daño recibido/10, +10 victoria, −10 derrota, −0.01 por paso |
| Episodio | un combate; máximo 120 s |
| Velocidad del entorno | **21 779 pasos/s** (medido, 1 hilo) |

## Resultados medidos

**Equipo local:** AMD Ryzen 5 7533HS (6 núcleos / 12 hilos), sin GPU NVIDIA, Windows 11,
PyTorch 2.15.0 (CPU). **GPU:** Google Colab con NVIDIA T4 (pendiente de correr, ver abajo).

### 1. Tiempo de entrenamiento: CPU vs GPU
| Configuración | Dispositivo | Pasos | Tiempo | Pasos/s |
|---|---|---|---|---|
| PDF (1 entorno) | CPU local (Ryzen 5 7533HS) | 100 000 | **158.8 s** | 630 |
| 8 entornos | CPU local | 1 000 000 | _(en curso)_ | |
| PDF (1 entorno) | CPU de Colab | 100 000 | _pendiente (notebook)_ | |
| PDF (1 entorno) | GPU T4 de Colab | 100 000 | _pendiente (notebook)_ | |

### 2. Calidad del bot (50 combates contra el Guardián, semillas fijas)
| Jugador | Victorias | Vida media que le queda al jefe |
|---|---|---|
| Azar | 0/50 (0 %) | 72.9 % |
| **Bot PPO, 100 000 pasos** | **10/50 (20 %)** | 17.0 % |
| Bot de reglas, habilidad 0.85 | 46/50 (92 %) | 1.4 % |
| Bot de reglas, habilidad 1.0 | 50/50 (100 %) | 0 % |

### 3. Latencia de inferencia y capacidad (CPU local, 1 hilo, 10 000 decisiones)
| Forma de servir el modelo | Latencia media | Decisiones/s por núcleo | vCPU para 2 000 bots a 10 Hz | Con 30 % de margen |
|---|---|---|---|---|
| PyTorch (SB3 `predict`) | 0.4291 ms | 2 330 | 8.58 | 11.16, es decir **12 vCPU** |
| **Red exportada a numpy** | **0.0155 ms** | **64 623** | 0.31 | 0.41, es decir **1 vCPU** |

Cálculo (fórmula del PDF): decisiones/s = 2 000 bots × 10 Hz = **20 000**;
vCPU = 20 000 ÷ decisiones/s por núcleo × 1.3.

La red en numpy decide **exactamente igual** que la de PyTorch (1 000 de 1 000 decisiones
coinciden) y es **~28 veces más rápida**. Con una red de 14→64→64→7, el costo de llamar a PyTorch
(convertir a tensor, despachar, volver a numpy) pesa más que la multiplicación de matrices.
**Decisión de diseño:** el servidor usará la versión numpy (`ia/modelos/*.npz`), sin PyTorch en
la imagen (que pesaría cientos de MB más).

## Análisis
_(Se completa con los tiempos de Colab: ¿la GPU fue más rápida o más lenta que la CPU, y por qué?
El PDF anticipa que con redes tan pequeñas la GPU puede no ganar porque copiar datos a la GPU
cuesta más que el cálculo.)_

## Costo estimado por hora — pendiente de la calculadora oficial
No se ponen cifras de memoria. En https://cloud.google.com/products/calculator (región
**us-central1**), cotiza y anota aquí el precio por hora **bajo demanda** y **Spot** de:

| Recurso | Para qué | USD/h bajo demanda | USD/h Spot |
|---|---|---|---|
| `e2-standard-16` (16 vCPU) | Inferencia con PyTorch (12 vCPU) | | |
| `e2-standard-2` (2 vCPU) | Inferencia con numpy (1 vCPU) | | |
| `n1-standard-4` + 1 × NVIDIA T4 | Entrenamiento en GPU | | |

Captura: la pantalla de la calculadora con los tres recursos (`docs/capturas/3.1-costos.png`).
El entrenamiento es ocasional y tolera interrupciones (guarda el modelo), así que va en **Spot**;
la inferencia corre todo el tiempo junto a las partidas, así que va **bajo demanda**.

## Cómo reproducir
```powershell
& $HOME\.venvs\la-torre\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& $HOME\.venvs\la-torre\Scripts\python.exe -m pip install gymnasium stable-baselines3
& $HOME\.venvs\la-torre\Scripts\python.exe ia\entrenar.py --device cpu --pasos 100000
& $HOME\.venvs\la-torre\Scripts\python.exe ia\medir.py ia\modelos\bot_cpu_100k.zip --episodios 50
```
GPU: `python ia/empaquetar_colab.py`, abre `ia/entrenar_bot_colab.ipynb` en Colab con T4,
sube `ia/colab/la-torre-ia.zip` y ejecuta todas las celdas. Descarga `resultados_colab.zip`.

## Capturas para el entregable
1. `3.1-01-entrenamiento-cpu.png`: la terminal con `entrenar.py --device cpu` y su tiempo.
2. `3.1-02-colab-gpu.png`: celda 1 del notebook (GPU T4 asignada).
3. `3.1-03-colab-tabla.png`: tabla final del notebook (CPU vs GPU).
4. `3.1-04-medir.png`: salida de `medir.py` (victorias, latencias, vCPU).
5. `3.1-costos.png`: la calculadora de precios.
