# La Torre

Roguelike de un caballero contra 4 jefes seguidos, con **servidor autoritativo** que corre como
flota de **Agones** sobre Kubernetes. Es el proyecto de la Unidad 3 de Cómputo en la Nube
(Infraestructura y despliegue de videojuegos en la nube, TecNM Colima).

El plan completo y el avance están en [PLAN.md](PLAN.md).

## Cómo jugar (reglas)
- Vida, resistencia (stamina), ataque y esquiva con invulnerabilidad breve.
- 4 jefes por run; al vencer a cada uno, el servidor ofrece 3 mejoras al azar.
- Solo o cooperativo de 2 a 4 jugadores. La run termina en victoria (4 jefes) o derrota (todos caídos).

## Entorno local (Windows / PowerShell)

El entorno virtual va **fuera de OneDrive** para que no se sincronicen miles de archivos:

```powershell
py -3.11 -m venv $HOME\.venvs\la-torre
& $HOME\.venvs\la-torre\Scripts\Activate.ps1
pip install -r server\requirements.txt pytest
pytest -q server
```

## Estructura
| Carpeta | Contenido | Práctica |
|---|---|---|
| `server/` | Servidor del juego, pruebas y Dockerfile | 3.3, 3.2 |
| `k8s/` | Fleet, FleetAutoscaler, PodMonitor | 3.3, 3.4 |
| `loadtest/` | Locust: jugadores y espectadores simulados | 3.4 |
| `serverless/` | Tabla de líderes (Cloud Run + Firestore) | 3.5 |
| `infra/` | Terraform | 3.6 |
| `ia/` | Entrenamiento del bot | 3.1 |
