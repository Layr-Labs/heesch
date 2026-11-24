"""Visualize how often the spatial refutations used each tile-relative halo site."""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


here = Path(__file__).resolve().parent
trials = (14, 19)
data = []
for r in trials:
    source = here / f"geometric-core-r{r}.json"
    if not source.is_file():
        source = here / "local-native" / f"r{r}-cover" / "geometric-core.json"
    data.append(json.loads(source.read_text()))
central = set(map(tuple, data[0]["central"]))
halo = {tuple(row[:2]) for row in data[0]["by_tile_halo"]}
palette = [(244, 230, 199), (227, 149, 97), (162, 58, 49)]
mac_font = Path("/System/Library/Fonts/Supplemental/Arial.ttf").is_file()
page = Image.new("RGB", (1410, 775), "#f6f5ef")
draw = ImageDraw.Draw(page)


def text(pos, line, size, bold=False, align=None, ink="#243a42"):
    name = ("Arial Bold.ttf" if bold else "Arial.ttf") if mac_font else (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/" + name if mac_font else name, size)
    draw.text(pos, line, font=font, fill=ink, anchor=align)


def xy(cell):
    x, y = cell
    return math.sqrt(3) * (x + y / 2), -1.5 * y


def color(t):
    segment = min(1, int(2 * t))
    lo, hi = palette[segment:segment + 2]
    frac = 2 * t - segment
    return tuple(round(a + frac * (b - a)) for a, b in zip(lo, hi))


radius = 30
xs, ys = zip(*(xy(p) for p in central | halo))
x_min = min(xs)
y_min = min(ys)
common_top = [tuple(row[:2]) for row in data[0]["by_tile_halo"][:4]]
assert common_top == [tuple(row[:2]) for row in data[1]["by_tile_halo"][:4]]
text((45, 32), "Which parts of the outline enter the proof?", 40, True)
text((46, 100), "Rotate and translate each retained surround implication back to the 20-hex it constrains.", 23)
for col, r in enumerate(trials):
    left = 47 + 690 * col
    text((left, 181), f"Radius {r}", 26, True)
    counts = {tuple(row[:2]): row[2] for row in data[col]["by_tile_halo"]}
    peak = max(counts.values())
    assert counts.keys() == halo
    for p in sorted(central | halo):
        gx, gy = xy(p)
        cx = left + 32 + (gx - x_min) * radius
        cy = 260 + (gy - y_min) * radius
        vertices = [(cx + radius * math.cos(math.radians(30 + 60 * j)),
                     cy + radius * math.sin(math.radians(30 + 60 * j))) for j in range(6)]
        draw.polygon(vertices, fill="#264957" if p in central else color(counts[p] / peak),
                     outline="#f6f5ef", width=2)
        if p in common_top:
            text((cx, cy), str(common_top.index(p) + 1), 23, True, "mm", ink="#ffffff")
    for rank, p in enumerate(common_top, 1):
        text((left, 545 + 34 * (rank - 1)), f"{rank}.  ({p[0]}, {p[1]})", 19, True)
        text((left + 125, 545 + 34 * (rank - 1)), f"{counts[p]:,} uses", 19)
text((46, 714), "Blue cells form the tile. Warmer halo cells appear more often in each proof core.", 20)
page.save(here / "tile-relative-obstruction.png")
