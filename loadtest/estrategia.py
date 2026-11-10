"""Atajo: la estrategia de los jugadores simulados vive en el servidor (server/juego/estrategia.py),
porque también la usan los compañeros IA del modo "solo con bots". Locust, el bot de consola y las
pruebas la siguen importando desde aquí. En la VM de Locust copia también la carpeta server/juego.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from juego.estrategia import CLASES, ESTILO, decidir  # noqa: E402,F401