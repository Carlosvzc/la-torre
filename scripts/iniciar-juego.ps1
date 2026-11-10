# La Torre: arranca el servidor del juego y la página, y abre el juego en el navegador.
# Lo usa el acceso directo del escritorio. Pulsa Enter en esta ventana para apagarlo todo.
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "La Torre"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $HOME ".venvs\la-torre\Scripts\python.exe"
$logs = Join-Path $raiz "logs"
New-Item -ItemType Directory -Force $logs | Out-Null

function Escribir($texto, $color = "Gray") { Write-Host $texto -ForegroundColor $color }
# Solo procesos de ESTE proyecto (la ruta de la-torre va en la línea de comando): nunca toca
# servidores de otros proyectos aunque también se llamen server.py.
function ProcesosDelJuego {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($raiz) -and $_.CommandLine -match "server\.py|http\.server|servir_cliente\.py" }
}

Escribir ""
Escribir "  L A   T O R R E" "Yellow"
Escribir ""

if (-not (Test-Path $python)) {
    Escribir "No encuentro el entorno de Python en $python" "Red"
    Escribir "Créalo con:  py -3.11 -m venv `$HOME\.venvs\la-torre  y  pip install -r server\requirements.txt" "Red"
    Read-Host "Enter para salir"; exit 1
}

# 1. Apagar copias anteriores (de una sesión vieja o de Docker) que ocupen los puertos
Escribir "Apagando copias anteriores..."
foreach ($p in ProcesosDelJuego) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
        $contenedores = & docker ps --filter "publish=7654" --format "{{.Names}}" 2>&1 | Where-Object { $_ -is [string] }
        foreach ($c in $contenedores) {
            if ($c -and $c -notmatch "error|cannot|failed") {
                Escribir "  Deteniendo el contenedor de Docker '$c' (tapaba el puerto 7654)" "DarkYellow"
                & docker stop $c 2>&1 | Out-Null
            }
        }
    } catch { }   # Docker Desktop apagado: no hay contenedores que detener
}
Start-Sleep -Milliseconds 500

# 2. Arrancar el servidor del juego y el de la página (en segundo plano, con registro)
Escribir "Arrancando el servidor del juego..."
$servidor = Start-Process $python -ArgumentList "`"$(Join-Path $raiz 'server\server.py')`"" -WorkingDirectory (Join-Path $raiz "server") `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs\servidor-salida.log" -RedirectStandardError "$logs\servidor.log"
$pagina = Start-Process $python -ArgumentList "`"$(Join-Path $raiz 'scripts\servir_cliente.py')`"", "8080" `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs\pagina-salida.log" -RedirectStandardError "$logs\pagina.log"

# 3. Esperar a que respondan, y comprobar que contesta ESTE servidor (no uno viejo)
$listo = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $metricas = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:9100/metrics").Content
        $pag = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:8080/retro/"
        if ($metricas -match "torre_tick_lag_seconds" -and $pag.StatusCode -eq 200) { $listo = $true; break }
    } catch { }
}
$otros = Get-NetTCPConnection -LocalPort 7654 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -ne "0.0.0.0" -and $_.LocalAddress -ne "::" }
if (-not $listo) {
    Escribir "El juego no arrancó. Revisa $logs\servidor.log" "Red"
    Get-Content "$logs\servidor.log" -Tail 8 -ErrorAction SilentlyContinue
    Read-Host "Enter para salir"; exit 1
}
if ($otros) {
    Escribir "Aviso: otro programa también escucha en el puerto 7654 (proceso $($otros[0].OwningProcess))." "DarkYellow"
    Escribir "Si el juego se comporta raro, ciérralo (¿Docker Desktop?)." "DarkYellow"
}

# 4. Abrir el juego
if (-not $env:LA_TORRE_SIN_NAVEGADOR) { Start-Process "http://localhost:8080/retro/?v=$(Get-Date -Format yyyyMMddHHmmss)" }   # la variable sirve para pruebas
Escribir ""
Escribir "  El juego está corriendo:" "Green"
Escribir "    Juego 3D ........ http://localhost:8080/retro/"
Escribir "    Cliente 2D ...... http://localhost:8080/prueba2d/"
Escribir "    Métricas ........ http://localhost:9100/metrics"
Escribir "    Registros ....... $logs"
Escribir ""
Escribir "  Para jugar en cooperativo, abre más pestañas con nombres distintos." "DarkGray"
Escribir ""
Read-Host "  Pulsa Enter para APAGAR el juego"

# 5. Apagar todo
foreach ($p in @($servidor, $pagina)) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
# el lanzador del entorno virtual crea un proceso hijo: también se apaga
ProcesosDelJuego | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Escribir "Juego apagado." "Yellow"
Start-Sleep -Seconds 1
