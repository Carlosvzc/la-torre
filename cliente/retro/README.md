# Cliente 3D retro

Estética 3D de 64 bits (finales de los 90), no realista: low-poly con sombreado plano, niebla de
distancia, sombra redonda bajo cada personaje, paleta oscura y texturas nítidas en alta resolución.
**Todo se genera por código** (modelos, arena, texturas y sonidos): no hay assets de terceros
que licenciar. Usa [Three.js](https://threejs.org) 0.160 desde CDN (licencia MIT), así que la primera
vez necesita internet.

## Jugar en localhost
1. Servidor del juego:
   ```powershell
   cd $HOME\OneDrive\Documents\la-torre\server
   docker build -t torre-server .
   docker run --rm -p 7654:7654 -p 9100:9100 torre-server
   ```
2. Servir los clientes (los módulos de JavaScript no cargan con doble clic, hace falta http):
   ```powershell
   cd $HOME\OneDrive\Documents\la-torre
   py -3.11 -m http.server 8080 --directory cliente
   ```
3. Abre http://localhost:8080/retro/ , escribe tu nombre, **Entrar** y **Enter** para estar listo.

Cooperativo: varias pestañas o PCs en la misma red (cambia `localhost` por la IP de la PC del servidor).

## Controles
| Tecla | Acción |
|---|---|
| `W A S D` | Mover **relativo al jefe** (W acerca, S aleja, A/D lo rodean) |
| `J` o clic izquierdo | Atacar (el golpe apunta al jefe) |
| `Espacio`, `Shift` o clic derecho | Esquivar (sin dirección: hacia atrás; el Hechicero hace un destello) |
| `K`, `Q` o clic central | Habilidad de la clase |
| `Enter` | Listo |
| `1 2 3` o clic en la carta | Elegir bendición (mejora) |
| `P` | Modo pixelado (render a baja resolución) |
| `M` | Silenciar |

## Qué se ve
- **Aviso del jefe:** anillo rojo en el suelo con un disco que se llena; parpadea rápido justo antes del impacto.
  El jefe alza su arma y brilla en rojo mientras prepara el golpe.
- **Ventana de castigo:** tras el impacto el jefe baja el arma y se inclina: es el momento de atacar.
- **Números:** blancos = daño al jefe, rojos = daño recibido, azules = esquiva.
- Los caballeros cooperativos tienen colores distintos (rojo, azul, morado, verde).

## Fluidez
- **Búfer de interpolación:** se dibuja ~90 ms en el pasado (170 ms como espectador), entre dos
  snapshots que ya llegaron y con horas regulares. Los eventos (golpes, números, sonidos) se disparan
  cuando su snapshot llega a la pantalla. Prueba controlada (caballero a 5 u/s, red con la
  irregularidad medida, 60 fps): velocidad dibujada **4.9–5.0 u/s** (antes 2.5–8.1 u/s).
- **Resortes de segundo orden:** cada articulación arranca suave, acelera y se asienta con un leve
  rebote. Da peso y más "cuadros intermedios" **sin cambiar la duración** de cada gesto (la fija el servidor).
- **Esqueleto articulado:** el caballero tiene rodillas, codos, torso, cuello y una capa de 3
  segmentos en cadena; los jefes, piernas que caminan (el Sabueso en pares diagonales) y cabeza que
  sigue al caballero.
- **Fotogramas clave:** el tajo (0.55 s) tiene anticipación, carga, estocada, seguimiento y regreso,
  con **estela de la espada**; la voltereta (0.4 s) se agacha, rueda y aterriza con polvo; la muerte
  dobla primero las rodillas. Los jefes bajan el arma antes de alzarla y rebotan tras el golpe.
- Respiración y cambio de peso en guardia, cabeza estable al caminar, tambaleo al recibir golpes.

> Si Docker Desktop está abierto y existe un contenedor viejo del servidor publicando el puerto
> 7654, se queda con `localhost` y el cliente habla con código antiguo. Revisa con
> `docker ps` y bórralo (`docker rm -f <nombre>`) antes de correr el servidor con Python.

## Modelos
| Jefe | Diseño |
|---|---|
| Guardián de Hierro | Gólem acorazado con martillo y visor ardiente |
| Bruja de Ceniza | Túnica flotante y báculo con orbe de fuego |
| Sabueso Abismal | Bestia de cuatro patas con cráneo y ojos violetas |
| Rey sin Corona | Figura alta con espadón y corona incompleta |
| Coloso del Eclipse | Gigante de roca con un halo de eclipse (jefe del día) |

Para depurar desde la consola del navegador: `laTorre.estado` (último snapshot) y
`laTorre.avanzar(60)` (avanza cuadros a mano si la pestaña está oculta).
