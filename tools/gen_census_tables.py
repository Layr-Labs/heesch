"""Regenerate heesch_verify/known_nontilers.json — the census non-tiler table.

Source: Kaplan 2022's complete per-size non-tiler lists (`*_0up.txt`, see
third_party/kaplan-heesch/PIN). Within a listed size every hole-free free
polyform is either in the list (a non-tiler, with its exact published Hc/Hh)
or absent (a tiler — Kaplan removed tilers with Myers's classifier before
computing Heesch numbers). That complement rule is what makes the gate exact
for polyominoes n<=10, polyhexes n<=8 and polyiamonds n<=12.

Every source file is verified against the pinned sha256 before use, every
per-size count is asserted against the published table, and the enumeration
is cross-checked against the published free-polyform counts. Any mismatch
aborts before anything is written.

Usage:
    python tools/gen_census_tables.py [--cache DIR]

DIR (default ~/.cache/kaplan-heesch) holds the downloaded files; delete it to
force a fresh download. Network access is needed only for files not cached.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from polyforms import FREE_COUNTS, free_polyforms, parse_kaplan_file  # noqa: E402
from heesch_verify.canonical import canonical_digest  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.shape import holes_of  # noqa: E402

BASE_URL = "https://cs.uwaterloo.ca/~csk/heesch/"
PIN = ROOT / "third_party" / "kaplan-heesch" / "PIN"
OUT = ROOT / "heesch_verify" / "known_nontilers.json"

# Largest size with a complete published list, per grid.
BOUNDS = {"O": 10, "H": 8, "I": 12}
FAMILY = {"O": "omino", "H": "hex", "I": "iamond"}
# Published non-tiler counts per (grid, n); sizes absent here have none.
PUBLISHED = {
    ("O", 7): 3, ("O", 8): 20, ("O", 9): 198, ("O", 10): 1390,
    ("H", 6): 4, ("H", 7): 37, ("H", 8): 381,
    ("I", 7): 1, ("I", 9): 20, ("I", 10): 103, ("I", 11): 594, ("I", 12): 1192,
}


def pinned_digests() -> dict[str, str]:
    out = {}
    for line in PIN.read_text(encoding="utf-8").splitlines():
        toks = line.split()
        if len(toks) >= 2 and toks[1].startswith("sha256=") and "/" in toks[0]:
            out[toks[0]] = toks[1][len("sha256="):]
    return out


def fetch(rel: str, cache: pathlib.Path, expected: str) -> str:
    dst = cache / rel.replace("/", "_")
    if not dst.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(BASE_URL + rel, timeout=60) as resp:
            dst.write_bytes(resp.read())
    raw = dst.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != expected:
        raise SystemExit(f"{rel}: sha256 {got} != pinned {expected}; refusing")
    return raw.decode("ascii")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(pathlib.Path.home() / ".cache" / "kaplan-heesch"))
    args = ap.parse_args()
    cache = pathlib.Path(args.cache)
    pins = pinned_digests()

    table = {"bounds": dict(BOUNDS), "sources": {}, "O": {}, "H": {}, "I": {}}
    for gid, bound in BOUNDS.items():
        grid = GRIDS[gid]
        for n in range(1, bound + 1):
            expected = PUBLISHED.get((gid, n), 0)
            entries = []
            if expected:
                rel = f"{FAMILY[gid]}/{n:02d}{FAMILY[gid]}_0up.txt"
                text = fetch(rel, cache, pins[rel])
                table["sources"].setdefault(gid, []).append(
                    {"file": rel, "sha256": pins[rel], "n": n})
                entries = parse_kaplan_file(text)
            assert len(entries) == expected, (
                f"{gid}{n}: {len(entries)} listed, published {expected}")

            # Enumeration cross-check: the list must sit inside the hole-free
            # free polyforms of that size, and the complement is the tilers.
            forms = free_polyforms(gid, n)
            assert len(forms) == FREE_COUNTS[gid][n], (
                f"{gid}{n}: enumerated {len(forms)}, published {FREE_COUNTS[gid][n]}")
            holefree = {canonical_digest(c, grid, True) for c in forms
                        if not holes_of(frozenset(c), grid)}
            digests = {}
            for cells, hc, hh in entries:
                assert not holes_of(frozenset(cells), grid), f"{gid}{n}: holed entry {cells}"
                d = canonical_digest(cells, grid, True)
                assert d in holefree, f"{gid}{n}: entry {cells} not a free {n}-form"
                assert d not in digests, f"{gid}{n}: duplicate entry {cells}"
                assert hc <= hh <= hc + 1, f"{gid}{n}: bad Hc/Hh {hc}/{hh}"
                digests[d] = [hc, hh]
            table[gid].update(digests)
            print(f"  {gid} n={n:2d}: {len(digests):5d} non-tilers, "
                  f"{len(holefree) - len(digests):5d} tilers, "
                  f"{len(forms) - len(holefree):3d} holed", flush=True)

    for gid in BOUNDS:
        table[gid] = dict(sorted(table[gid].items()))
    with open(OUT, "w", newline="\n", encoding="ascii") as fh:
        json.dump(table, fh, indent=0, sort_keys=False)
        fh.write("\n")
    print(f"wrote {OUT}: " + ", ".join(f"{g}={len(table[g])}" for g in BOUNDS))


if __name__ == "__main__":
    main()
