"""Empaqueta lo mínimo para entrenar en Google Colab (práctica 3.1, GPU T4).

Uso:  python ia/empaquetar_colab.py      → crea ia/colab/la-torre-ia.zip

Se usa Python y no Compress-Archive porque el de Windows PowerShell 5.1 guarda las rutas
con "\" y en Linux (Colab) se descomprimen mal.
"""
import glob
import os
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = (glob.glob(os.path.join(RAIZ, "server", "juego", "*.py"))
            + [os.path.join(RAIZ, "ia", n) for n in ("entorno_duelo.py", "entrenar.py", "medir.py")]
            + [os.path.join(RAIZ, "loadtest", "estrategia.py")])

os.makedirs(os.path.join(RAIZ, "ia", "colab"), exist_ok=True)
destino = os.path.join(RAIZ, "ia", "colab", "la-torre-ia.zip")
with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
    for ruta in ARCHIVOS:
        z.write(ruta, os.path.relpath(ruta, RAIZ).replace(os.sep, "/"))
print("Listo:", destino)
for nombre in zipfile.ZipFile(destino).namelist():
    print("  ", nombre)
