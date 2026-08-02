"""Génère l'icône : PNG multi-tailles + .ico Windows, sans dépendance.

Le motif encode ce que l'outil mesure — une **ligne de référence**, une barre
au-dessus (améliorée), une en dessous (détruite), une neutre. Pas de loupe, pas
d'engrenage : la marque dit ce que fait le programme, et elle reste lisible à
16 pixels parce qu'elle n'est faite que de rectangles.

Encodeur PNG et empaqueteur ICO écrits à la main : le paquet n'a aucune
dépendance d'exécution, l'outillage n'en aura pas non plus.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)

INK = (0x1B, 0x1F, 0x24, 0xFF)       # fond, presque noir
RULE = (0x8A, 0x8F, 0x96, 0xFF)      # ligne de référence
GAIN = (0x1E, 0x84, 0x49, 0xFF)      # améliorée
LOSS = (0xC0, 0x39, 0x2B, 0xFF)      # détruite
FLAT = (0x6B, 0x70, 0x77, 0xFF)      # inchangée


def blank(size: int) -> list[list[tuple[int, int, int, int]]]:
    return [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]


def fill(canvas, x0: float, y0: float, x1: float, y1: float, colour) -> None:
    size = len(canvas)
    left, right = sorted((round(x0 * size), round(x1 * size)))
    top, bottom = sorted((round(y0 * size), round(y1 * size)))
    right = max(right, left + 1)
    bottom = max(bottom, top + 1)
    for y in range(max(0, top), min(size, bottom)):
        for x in range(max(0, left), min(size, right)):
            canvas[y][x] = colour


def rounded_background(canvas) -> None:
    """Carré à coins adoucis, sans anticrénelage: net à toutes les tailles."""
    size = len(canvas)
    radius = max(1, round(size * 0.18))
    for y in range(size):
        for x in range(size):
            dx = min(x, size - 1 - x)
            dy = min(y, size - 1 - y)
            if dx < radius and dy < radius:
                ox, oy = radius - dx, radius - dy
                if ox * ox + oy * oy > radius * radius:
                    continue
            canvas[y][x] = INK


def draw(size: int):
    canvas = blank(size)
    rounded_background(canvas)
    # Ligne de référence, au centre exact: tout se lit par rapport à elle.
    rule = max(1 / size, 0.055)
    fill(canvas, 0.14, 0.5 - rule / 2, 0.86, 0.5 + rule / 2, RULE)
    # Trois barres: au-dessus, en dessous, et une qui ne bouge pas.
    fill(canvas, 0.20, 0.19, 0.36, 0.5, GAIN)
    fill(canvas, 0.42, 0.5, 0.58, 0.81, LOSS)
    fill(canvas, 0.64, 0.40, 0.80, 0.5, FLAT)
    return canvas


def to_png(canvas) -> bytes:
    size = len(canvas)
    raw = bytearray()
    for row in canvas:
        raw.append(0)  # filtre 0: aucun
        for red, green, blue, alpha in row:
            raw += bytes((red, green, blue, alpha))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def to_ico(images: dict[int, bytes]) -> bytes:
    entries, blobs = b"", b""
    offset = 6 + 16 * len(images)
    for size, payload in sorted(images.items()):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,
            0,
            1,
            32,
            len(payload),
            offset,
        )
        blobs += payload
        offset += len(payload)
    return struct.pack("<HHH", 0, 1, len(images)) + entries + blobs


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"
     width="256" height="256">
  <rect width="256" height="256" rx="46" fill="#1b1f24"/>
  <rect x="35.8" y="121" width="184.4" height="14" fill="#8a8f96"/>
  <rect x="51.2" y="48.6" width="41" height="79.4" fill="#1e8449"/>
  <rect x="107.5" y="128" width="41" height="79.4" fill="#c0392b"/>
  <rect x="163.8" y="102.4" width="41" height="25.6" fill="#6b7077"/>
</svg>
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    images: dict[int, bytes] = {}
    for size in SIZES:
        payload = to_png(draw(size))
        images[size] = payload
        (OUT / f"icon-{size}.png").write_bytes(payload)
    (OUT / "icon.ico").write_bytes(to_ico(images))
    (OUT / "icon.svg").write_text(SVG, encoding="utf-8")
    print(f"{len(SIZES)} PNG + icon.ico + icon.svg -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
