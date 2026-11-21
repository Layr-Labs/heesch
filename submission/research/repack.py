"""Repeat the two published optimization steps on each archived footprint."""
import argparse
from pathlib import Path

from coverage import solve
from pocket_pack import pack


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("output", type=Path)
    cli.add_argument("--seconds", type=float, default=45)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inputs = sorted(Path(__file__).with_name("patches").glob("*.heesch"))
    for i, src in enumerate(inputs):
        seed = args.output / src.name
        solve(src, seed, seconds=12, workers=1, seed=501+i)
        defect = next(row for row in seed.read_text().splitlines() if row.startswith("#DEFECT "))
        budget = int(defect.split()[2]) - 1
        pack(seed, args.output / (src.stem + ".fixed.heesch"), budget, args.seconds)
