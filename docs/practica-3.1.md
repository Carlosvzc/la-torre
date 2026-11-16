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
| PDF (1 entorno), repetición del 16/11 | CPU local | 100 000 | **160.4 s** | 623 |
| 8 entornos | CPU local | 1 000 000 | **928.6 s** (15.5 min) | 1 077 |
| PDF (1 entorno) | CPU de Colab | 100 000 | _pendiente (notebook)_ | |
| PDF (1 entorno) | GPU T4 de Colab | 100 000 | _pendiente (notebook)_ | |

### 2. Calidad del bot (50 combates contra el Guardián, semillas fijas)
| Jugador | Victorias | Vida media que le queda al jefe |
|---|---|---|
| Azar | 0/50 (0 %) | 72.9 % |
| Bot PPO, 100 000 pasos (1 entorno) | 10/50 (20 %) | 17.0 % |
| **Bot PPO, 1 000 000 pasos (8 entornos)** | **50/50 (100 %)**, en **30.9 s** de media | 0 % |
| Bot de reglas, habilidad 0.85 | 46/50 (92 %), en 42.6 s | 1.4 % |
| Bot de reglas, habilidad 1.0 | 50/50 (100 %), en 53.4 s | 0 % |

Con 10 veces más experiencia el bot pasa de 20 % a 100 % de victorias y gana **42 % más rápido**
que el bot de reglas con reflejos perfectos: aprendió a castigar al jefe en sus ventanas de
recuperación en lugar de esperar con prudencia. 8 entornos en paralelo subieron el rendimiento
de 630 a 1 077 pasos/s en la misma CPU. Es la lección del PDF: entrenar es caro y ocasional
(15.5 min de CPU una vez), inferir es barato y continuo.

### 3. Latencia de inferencia y capacidad (CPU local, 1 hilo, 10 000 decisiones)
| Forma de servir el modelo | Latencia media | Decisiones/s por núcleo | vCPU para 2 000 bots a 10 Hz | Con 30 % de margen |
|---|---|---|---|---|
| PyTorch (SB3 `predict`) | 0.4291 ms | 2 330 | 8.58 | 11.16, es decir **12 vCPU** |
| **Red exportada a numpy** | **0.0155 ms** | **64 623** | 0.31 | 0.41, es decir **1 vCPU** |

Modelo de 100 000 pasos. El de 1 000 000 pasos tiene la misma red y midió prácticamente lo mismo:
0.4408 ms con PyTorch (12 vCPU) y 0.0157 ms con numpy (1 vCPU), con 1 000 de 1 000 decisiones iguales.
La calidad del bot no cambia el costo de inferencia: depende del tamaño de la red, no del entrenamiento.

Cálculo (fórmula del PDF): decisiones/s = 2 000 bots × 10 Hz = **20 000**;
vCPU = 20 000 ÷ decisiones/s por núcleo × 1.3.

La red en numpy decide **exactamente igual** que la de PyTorch (1 000 de 1 000 decisiones
coinciden) y es **~28 veces más rápida**. Con una red de 14→64→64→7, el costo de llamar a PyTorch
(convertir a tensor, despachar, volver a numpy) pesa más que la multiplicación de matrices.
**Decisión de diseño:** el servidor usará la versión numpy (`ia/modelos/*.npz`), sin PyTorch en
la imagen (que pesaría cientos de MB más).

## Análisis
La comparación con GPU (Colab T4) **no se corrió**, así que no hay tiempos de GPU que reportar. Lo
medido apunta a lo que anticipa el PDF: con una red tan pequeña (14→64→64→7), el cuello de botella no
es el cálculo sino la simulación del entorno y el costo fijo de cada llamada. Por ejemplo, la misma red
en numpy decide 28 veces más rápido que en PyTorch. Por eso se espera que la GPU no gane, pero queda
como hipótesis sin medir. El notebook `ia/entrenar_bot_colab.ipynb` está listo para comprobarlo.

## Costo estimado en AWS (us-east-2)

Precios oficiales consultados el 16/11/2026: bajo demanda con la AWS Price List API y Spot con
`aws ec2 describe-spot-price-history` (mínimo y máximo de las últimas 24 h, Linux).

| Recurso | Para qué | USD/h bajo demanda | USD/h Spot (24 h) | USD/mes 24/7 bajo demanda |
|---|---|---|---|---|
| `c7i.4xlarge` (16 vCPU, 32 GiB) | Inferencia con PyTorch (12 vCPU) | 0.714 | 0.1784–0.2292 | **521.22** |
| `c7i.large` (2 vCPU, 4 GiB) | Inferencia con numpy (1 vCPU) | 0.08925 | 0.0203–0.0289 | **65.15** |
| `g4dn.xlarge` (4 vCPU + 1 NVIDIA T4) | Entrenamiento en GPU | 0.526 | 0.2748–0.28 | — |

- **Servir 2 000 bots:** con PyTorch hacen falta 12 vCPU (USD 521/mes); con la red exportada a numpy,
  1 vCPU (USD 65/mes en una c7i.large propia). Es **8 veces más barato** con la misma calidad de
  decisiones. En la práctica, 0.31 vCPU caben en los nodos de juego que ya existen (en la 3.4 cada
  GameServer usó 18 milinúcleos), así que el costo extra de los bots es casi cero.
- **Entrenar:** el entrenamiento de 1 000 000 de pasos tardó 928.6 s (0.258 h) en la CPU local de 6
  núcleos. Suponiendo una velocidad parecida en una `c7i.2xlarge` (8 vCPU, USD 0.357/h), costaría
  **≈ USD 0.09 por entrenamiento**. La equivalencia de velocidad es una suposición, no una medición.
  El tiempo en la GPU T4 no se midió (Colab pendiente), así que no se calcula su costo.
- El entrenamiento es ocasional y tolera interrupciones (guarda el modelo), así que va en **Spot**
  (47–48 % más barato en la g4dn.xlarge); la inferencia corre todo el tiempo junto a las partidas, así
  que va **bajo demanda**.

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
