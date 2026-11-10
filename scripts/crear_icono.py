"""Genera scripts/la-torre.ico: una torre en pixel art (32x32) escalada a 32, 64 y 256 px.

Sin librerías externas: escribe el PNG a mano (zlib + struct) y lo mete en un .ico.
Uso:  python scripts/crear_icono.py
"""
import os
import struct
import zlib

# Cada carácter es un píxel: . fondo, # borde, T torre, t sombra de la torre, A almena,
# V ventana encendida, P puerta, S suelo
DIBUJO = """
................................
..############################..
.##..........................##.
.#............................#.
.#.........A.A..A..A.A........#.
.#.........AAAAAAAAAAA........#.
.#.........TTTTTTTTTTT........#.
.#..........TTTTTTTTt.........#.
.#..........TTTTTTTTt.........#.
.#..........TTTVVTTTt.........#.
.#..........TTTVVTTTt.........#.
.#..........TTTVVTTTt.........#.
.#..........TTTTTTTTt.........#.
.#.........ATTTTTTTTtA........#.
.#.........AAAAAAAAAAA........#.
.#..........TTTTTTTTt.........#.
.#..........TTTTTTTTt.........#.
.#..........TTTVVTTTt.........#.
.#..........TTTVVTTTt.........#.
.#..........TTTTTTTTt.........#.
.#..........TTTTTTTTt.........#.
.#..........TTTTTTTTt.........#.
.#..........TTTPPTTTt.........#.
.#.........TTTPPPPTTt.........#.
.#.........TTTPPPPTTt.........#.
.#........TTTTPPPPTTTt........#.
.#.....SSSSSSSSSSSSSSSSSSS....#.
.#............................#.
.##..........................##.
..############################..
................................
................................
"""
COLORES = {
    ".": (0, 0, 0, 0), "#": (140, 116, 68, 255), "T": (216, 180, 106, 255), "t": (150, 118, 62, 255),
    "A": (232, 198, 120, 255), "V": (255, 138, 42, 255), "P": (26, 13, 34, 255), "S": (90, 80, 72, 255),
}
FONDO = (20, 15, 24, 255)


def pixeles():
    filas = [f for f in DIBUJO.strip("\n").split("\n")]
    assert len(filas) == 32 and all(len(f) == 32 for f in filas), "el dibujo debe ser de 32x32"
    out = []
    for y, fila in enumerate(filas):
        dentro = [x for x, ch in enumerate(fila) if ch == "#"]
        lo, hi = (min(dentro), max(dentro)) if dentro else (99, -1)
        linea = []
        for x, ch in enumerate(fila):
            if ch == "." and lo < x < hi and 1 < y < 29:
                linea.append(FONDO)                  # interior del recuadro: fondo oscuro
            else:
                linea.append(COLORES[ch])
        out.append(linea)
    return out


def png(pix, escala):
    lado = len(pix) * escala
    crudo = bytearray()
    for fila in pix:
        linea = bytearray([0])                       # filtro "ninguno"
        for c in fila:
            linea += bytes(c) * escala
        crudo += bytes(linea) * escala
    def bloque(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(bytes(crudo), 9)) + bloque(b"IEND", b""))


def main():
    pix = pixeles()
    imagenes = [(32, png(pix, 1)), (64, png(pix, 2)), (256, png(pix, 8))]
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    desplazamiento = 6 + 16 * len(imagenes)
    directorio, datos = b"", b""
    for lado, img in imagenes:
        directorio += struct.pack("<BBBBHHII", lado % 256, lado % 256, 0, 0, 1, 32, len(img), desplazamiento + len(datos))
        datos += img
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "la-torre.ico")
    with open(destino, "wb") as f:
        f.write(cabecera + directorio + datos)
    with open(destino.replace(".ico", "-256.png"), "wb") as f:   # vista previa
        f.write(imagenes[-1][1])
    print("Listo:", destino)


if __name__ == "__main__":
    main()
