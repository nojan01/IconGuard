#!/usr/bin/env python3
"""Erzeugt ein macOS .icns App-Icon für Desktop Icon Manager."""

from PIL import Image, ImageDraw, ImageFont
import subprocess
import shutil
from pathlib import Path

ICON_DIR = Path(__file__).parent / "icon.iconset"
OUTPUT = Path(__file__).parent / "icon.icns"
OUTPUT_PNG = Path(__file__).parent / "icon.png"

SIZES = [16, 32, 64, 128, 256, 512, 1024]


def draw_icon(size: int) -> Image.Image:
    """Zeichnet das App-Icon in der gewünschten Größe."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size * 0.08
    r = size * 0.18  # Eckenradius

    # Hintergrund: Abgerundetes Quadrat mit Gradient-Effekt
    x0, y0 = margin, margin
    x1, y1 = size - margin, size - margin

    # Hintergrundfarbe: kräftiges Blau
    bg_color = (41, 98, 255)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=bg_color)

    # Obere Hälfte etwas heller (Gradient-Simulation)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([x0, y0, x1, y1 * 0.55], radius=r, fill=(255, 255, 255, 35))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Grid / Raster-Linien (symbolisiert Desktop-Layout)
    cx, cy = size / 2, size / 2
    grid_area = size * 0.52
    gx0 = cx - grid_area / 2
    gy0 = cy - grid_area / 2.2
    gx1 = cx + grid_area / 2
    gy1 = cy + grid_area / 2.2

    line_w = max(1, int(size * 0.018))
    line_color = (255, 255, 255, 200)

    # 3x3 Grid
    cols, rows = 3, 3
    col_w = (gx1 - gx0) / cols
    row_h = (gy1 - gy0) / rows

    # Grid-Rahmen
    draw.rounded_rectangle([gx0, gy0, gx1, gy1], radius=size * 0.03,
                           outline=line_color, width=line_w)

    # Vertikale Linien
    for i in range(1, cols):
        x = gx0 + i * col_w
        draw.line([(x, gy0), (x, gy1)], fill=line_color, width=line_w)

    # Horizontale Linien
    for i in range(1, rows):
        y = gy0 + i * row_h
        draw.line([(gx0, y), (gx1, y)], fill=line_color, width=line_w)

    # Kleine Icon-Punkte in einigen Zellen
    dot_r = max(2, size * 0.035)
    dot_color = (255, 255, 255, 240)
    cells_with_dots = [(0, 0), (1, 0), (2, 1), (0, 2), (2, 2)]
    for col, row in cells_with_dots:
        dx = gx0 + col * col_w + col_w / 2
        dy = gy0 + row * row_h + row_h / 2
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                     fill=dot_color)

    # Pfeil unten rechts (Wiederherstellen-Symbol)
    arrow_size = size * 0.16
    ax = cx + grid_area / 2.8
    ay = cy + grid_area / 2.2 + arrow_size * 0.6
    arrow_w = max(2, int(size * 0.028))
    arrow_color = (130, 255, 170, 255)

    # Kreisbogen-Pfeil
    bbox = [ax - arrow_size, ay - arrow_size, ax + arrow_size, ay + arrow_size]
    draw.arc(bbox, start=180, end=90, fill=arrow_color, width=arrow_w)
    # Pfeilspitze
    tip_len = arrow_size * 0.45
    tip_x = ax
    tip_y = ay + arrow_size
    draw.polygon([
        (tip_x - tip_len * 0.5, tip_y - tip_len * 0.6),
        (tip_x + tip_len * 0.4, tip_y),
        (tip_x - tip_len * 0.5, tip_y + tip_len * 0.2),
    ], fill=arrow_color)

    return img


def main():
    ICON_DIR.mkdir(exist_ok=True)

    # Alle Größen erzeugen
    for s in SIZES:
        img = draw_icon(s)

        # 1x Variante
        if s <= 512:
            name = f"icon_{s}x{s}.png"
            img_resized = img.resize((s, s), Image.LANCZOS)
            img_resized.save(ICON_DIR / name)

        # 2x Variante (Retina) – die nächsthöhere Auflösung
        half = s // 2
        if half in [16, 32, 64, 128, 256, 512]:
            name = f"icon_{half}x{half}@2x.png"
            img.save(ICON_DIR / name)

    # PNG für Menüleiste (klein)
    icon_small = draw_icon(64)
    icon_small.save(OUTPUT_PNG)

    # iconutil erzeugt .icns aus dem .iconset Ordner
    subprocess.run(["iconutil", "-c", "icns", str(ICON_DIR), "-o", str(OUTPUT)],
                   check=True)

    # Aufräumen
    shutil.rmtree(ICON_DIR)

    print(f"✅ Icon erstellt: {OUTPUT}")
    print(f"✅ PNG erstellt:  {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
