# Cliente 2D de pruebas

Vista desde arriba para jugar y ver runs en localhost. No decide nada: manda acciones y dibuja
el snapshot del servidor. Es una herramienta de pruebas y de la demo; el cliente gráfico 3D
retro es un extra aparte.

## Jugar en localhost

1. Arranca el servidor (deja la terminal abierta):

   ```powershell
   cd $HOME\OneDrive\Documents\la-torre\server
   docker build -t torre-server .
   docker run --rm -p 7654:7654 -p 9100:9100 torre-server
   ```

2. Abre `cliente/prueba2d/index.html` con doble clic (o sírvelo con
   `py -3.11 -m http.server 8080 --directory cliente/prueba2d` y entra a http://localhost:8080).
3. Escribe tu nombre, **Conectar**, y pulsa **Enter** para estar listo.

Para cooperativo, abre la página en 2–4 pestañas con nombres distintos antes de que empiece la run.
Para ver como espectador, elige **Espectador** antes de conectar.

## Controles
| Tecla | Acción |
|---|---|
| `W A S D` / flechas | Mover |
| `J` o clic | Atacar (apunta solo al jefe) |
| `Espacio` / `K` | Esquivar hacia donde te mueves (sin dirección: hacia atrás) |
| `Enter` | Listo (sala de espera) |
| `1` `2` `3` | Elegir mejora |

## Cómo leer la pantalla
- **Círculo rojo que se llena:** dónde va a golpear el jefe. Cuando se llena, impacta: sal o esquiva.
- **Anillo rojo en el jefe:** está preparando un ataque. **Anillo turquesa:** se está recuperando,
  es el momento de castigarlo.
- **Caballero semitransparente:** está esquivando (invulnerable los primeros 0.3 s).
- **Cono dorado:** tu golpe; solo alcanza si el jefe está dentro.
