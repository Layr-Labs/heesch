"""Additive, non-scoring: render a parsed submission to a compact SVG string for
display (leaderboard gallery / hover). Emitted into score.json metrics["svg"];
it never affects scoring, gates, or verification — purely a picture of the shape
and its coronas. Renders hex (H), square (O), and iamond (I) grids.
"""
from __future__ import annotations
import math
from collections import Counter, defaultdict
from heesch_verify.patch import required_set
from heesch_verify.shape import holes_of

_SIZE = 10.0
_SQ3 = math.sqrt(3)
_PAL = {0:"#2b2622",1:"#875034",2:"#a9663a",3:"#c98a52",4:"#e6bd8b",5:"#9cbfb0"}

def _hex(q, r):
    cx, cy = _SIZE*1.5*q, _SIZE*_SQ3*(r + q/2.0)
    return [(round(cx+_SIZE*math.cos(math.pi/3*i)), round(cy+_SIZE*math.sin(math.pi/3*i))) for i in range(6)]
def _sq(x, y):
    s = _SIZE*1.7; X, Y = x*s, y*s
    return [(round(X), round(Y)), (round(X+s), round(Y)), (round(X+s), round(Y+s)), (round(X), round(Y+s))]
def _tri(x, y):
    k = _SIZE*1.6; cx = k*(x-y)*_SQ3/6.0; cy = k*(x+y)/2.0
    angs = (90, 210, 330) if x % 3 == 0 else (30, 150, 270)
    return [(round(cx+k*math.cos(math.radians(a)), 1), round(cy+k*math.sin(math.radians(a)), 1)) for a in angs]
def _poly(gid, c): return {"H": _hex, "O": _sq, "I": _tri}.get(gid, _hex)(c[0], c[1])
def _bnd(gid, cells):
    e = Counter()
    for c in cells:
        p = _poly(gid, c)
        for i in range(len(p)): e[tuple(sorted([p[i], p[(i+1)%len(p)]]))] += 1
    return [k for k, n in e.items() if n == 1]

def render_svg(sub, grid_id=None):
    """`sub` is a parsed submission (parse.parse_submission). Returns an SVG
    string, or None for unsupported grids / no witness."""
    gid = grid_id or getattr(sub, "grid_id", None)
    if gid not in ("H", "O", "I") or not getattr(sub, "patches", None):
        return None
    base = list(sub.cells)
    contact = sub.grid.contact("point")
    patch = set(); tiles = []
    for lvl, xf in sub.patches[0]:
        cs = [xf.apply(c) for c in base]; tiles.append((lvl, cs)); patch |= set(cs)
    R = set(required_set(frozenset(patch), contact)); covered = set()
    if getattr(sub, "defect", None):
        for lvl, xf in sub.defect.tiles:
            cs = [xf.apply(c) for c in base]; tiles.append((lvl, cs)); covered |= set(cs)
    defect = sorted((R - covered) | (holes_of(frozenset(patch | covered), sub.grid) - R))
    by = defaultdict(list)
    for lvl, cs in tiles:
        for c in cs: by[lvl].append(c)
    allpts = [p for cs in by.values() for c in cs for p in _poly(gid, c)]
    xs = [p[0] for p in allpts]; ys = [p[1] for p in allpts]
    mnx, mxx, mny, mxy = min(xs)-6, max(xs)+6, min(ys)-6, max(ys)+6
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{mnx} {mny} {mxx-mnx} {mxy-mny}" preserveAspectRatio="xMidYMid meet">']
    o.append(f'<rect x="{mnx}" y="{mny}" width="{mxx-mnx}" height="{mxy-mny}" fill="#f4efe6"/>')
    for lvl in sorted(by, reverse=True):
        d = "".join("M"+" ".join(f"{x},{y}" for x, y in _poly(gid, c))+"Z" for c in by[lvl])
        o.append(f'<path d="{d}" fill="{_PAL.get(lvl,"#999")}"/>')
    segs = []
    for lvl, cs in tiles: segs += _bnd(gid, cs)
    o.append('<path d="'+"".join(f"M{a[0]},{a[1]}L{b[0]},{b[1]}" for a, b in segs)+'" stroke="#12100e" stroke-width="1" fill="none"/>')
    if defect:
        o.append('<path d="'+"".join("M"+" ".join(f"{x},{y}" for x, y in _poly(gid, c))+"Z" for c in defect)+'" fill="#e23b2e" stroke="#7a0f0a" stroke-width="1.6"/>')
    o.append('</svg>')
    return "".join(o)
