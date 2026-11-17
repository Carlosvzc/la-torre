# La Torre

Roguelike de un caballero contra 4 jefes seguidos, con **servidor autoritativo** que corre como
flota de **Agones** sobre Kubernetes. Es el proyecto de la Unidad 3 de Cómputo en la Nube
(Infraestructura y despliegue de videojuegos en la nube, TecNM Colima).

**Entrega de la Unidad 3 (AWS, us-east-2):** el reporte está en
[docs/reporte/La-Torre-Reporte-Unidad3.pdf](docs/reporte/La-Torre-Reporte-Unidad3.pdf) y el detalle de cada
práctica en `docs/practica-3.x.md`. El plan inicial (escrito cuando la nube aún era Google Cloud) está
en [PLAN.md](PLAN.md).

## Cómo jugar (reglas)
- Vida, resistencia (stamina), ataque, esquiva con invulnerabilidad breve y una habilidad por clase.
- **4 clases** con estilos distintos (el servidor decide todo; el cliente solo elige):

| Clase | Ataque | Esquiva | Habilidad (`K`) | Pasiva |
|---|---|---|---|---|
| Caballero | Tajo rápido | Voltereta | Muro de escudo: 75 % menos daño, 2 s | Armadura 10 % |
| Bárbaro | Hachazo lento y amplio (32) | Voltereta corta | Grito de guerra: +40 % daño y doble resistencia, 6 s | Piel curtida 15 %; furia +50 % con poca vida |
| Cazadora | Flecha a 10 de alcance | Voltereta larga | Disparo perforante: carga 1 s, 40 de daño | +20 % de daño de lejos |
| Hechicero | Bola de fuego en zona (tarda 0.35 s: si el jefe se mueve, falla) | Destello (teletransporte) | Nova de escarcha: daño en área y frena al jefe 4 s | — |

  Balance medido con el bot (10 semillas, reflejos perfectos): las 4 clases ganan 10/10; runs de 3.3 a 5.7 min.
- 4 jefes por run; al vencer a cada uno, el servidor ofrece 3 mejoras al azar.
- **3 modos** (los elige el primero en entrar): **Solitario**; **Solo con bots** (tú + 2 compañeros
  IA dentro del servidor, con clases distintas a la tuya); **Multijugador** de hasta 3 personas en la
  red local (sala de espera: empieza cuando todos pulsan Enter, o a los 60 s). La run termina en
  victoria (4 jefes) o derrota (todos caídos). Medido: un jugador con errores gana 0/8 en solitario
  y 8/8 con bots.
- **Multijugador en red local:** el acceso del escritorio muestra la dirección para tus amigos
  (`http://IP-de-tu-PC:8080/retro/`); ellos solo abren esa página. La primera vez Windows pide
  permitir Python en el firewall: acepta solo **redes privadas**.

## Jugar con un doble clic

En el escritorio está el acceso **La Torre** (ícono de la torre). Al abrirlo:
1. apaga copias anteriores del juego (solo procesos de este proyecto) y cualquier contenedor de
   Docker que tape el puerto 7654;
2. arranca el servidor del juego y la página, y comprueba que responde el servidor actual;
3. abre http://localhost:8080/retro/ en el navegador.

Deja la ventana abierta mientras juegas; **pulsa Enter en ella para apagarlo todo**. Los registros
quedan en `logs/`. Si se borra el acceso, se recrea con:

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\La Torre.lnk")
$s.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$s.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\scripts\iniciar-juego.ps1`""
$s.WorkingDirectory = "$PWD"; $s.IconLocation = "$PWD\scripts\la-torre.ico,0"; $s.Save()
```

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
| `k8s/` | Fleet, FleetAutoscaler, PodMonitor, asignación, Locust en el clúster y monitoreo | 3.3, 3.4 |
| `loadtest/` | Locust: jugadores, espectadores y tabla de líderes; resultados y gráficas | 3.4, 3.5 |
| `serverless/` | Tabla de líderes (AWS Lambda + DynamoDB) | 3.5 |
| `infra/` | Terraform para AWS (VPC, EKS, Agones, ECR, Lambda, presupuesto) | 3.6 |
| `ia/` | Entrenamiento del bot | 3.1 |
| `grafana/` | Tablero de Grafana (CCU, tick p99, servidores, nodos, egress) | 3.4 |
| `.github/workflows/` | Pipeline CI/CD | 3.2 |
| `docs/` | Prácticas, capturas y reporte final | todas |
