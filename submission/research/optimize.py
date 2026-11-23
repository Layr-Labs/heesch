"""Search all non-overlapping partial fourth-ring placements on the exhibited third footprint."""
import argparse
from pathlib import Path
import time

from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of
from pack import Packing

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=18)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = (HERE/"third.heesch").read_text()
    witness = verify_witness(source)
    shape = frozenset(witness.submission.cells)
    occupied = witness.hc_corona.patch_cells
    model = Packing(witness.submission.grid, shape, occupied, witness.contact, args.budget)
    model.model.clear_objective()
    previous = verify_witness((HERE.parent/"best.heesch").read_text())
    model.add_hint({pose.apply_all(shape) for _, pose in previous.submission.defect.tiles})
    chosen, result = model.solve(time.monotonic()+args.seconds, args.workers, 349146)
    print(result)
    if chosen is None:
        return
    filled = frozenset(cell for item in chosen for cell in item.cells)
    missing = model.required-filled
    pockets = holes_of(occupied | filled, witness.submission.grid)
    charged = missing | pockets
    candidate = source+f"#DEFECT 4 {len(charged)} {len(missing)} {len(model.required)}\n{len(chosen)}\n"
    candidate += "".join(f"4 {item.xf.as_text()}\n" for item in chosen)
    replay = verify_witness(candidate)
    measured = verify_defect(shape, replay.submission.grid, replay.hc_corona,
                             replay.submission.defect, replay.contact)
    assert measured.defect_hc == len(charged) <= args.budget
    if args.output:
        args.output.write_text(candidate)


if __name__ == "__main__":
    main()
