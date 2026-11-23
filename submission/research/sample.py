"""Recover solid third rings in several coordinate frames of the same tile."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import subprocess

from heesch_verify import GRIDS, Xform, verify_witness


D = Path(__file__).resolve().parent
import os
BINARY = os.environ.get("HEESCH_SAT", "heesch-sat")
DEST = Path(os.environ.get("HEESCH_CHART_DIR", "reproduced-charts"))
DEST.mkdir(exist_ok=True, parents=True)
G = GRIDS["I"]
base = verify_witness((D / "cavity-bank/retry-three/1134.d3.heesch").read_text())
shape = frozenset(base.submission.cells)


def compose(x, y):
    return Xform(x.a*y.a+x.b*y.d, x.a*y.b+x.b*y.e, x.a*y.c+x.b*y.f+x.c,
                 x.d*y.a+x.e*y.d, x.d*y.b+x.e*y.e, x.d*y.c+x.e*y.f+x.f)


def inverse(x):
    p, q, r, s = x.det*x.e, -x.det*x.b, -x.det*x.d, x.det*x.a
    return Xform(p, q, -p*x.c-q*x.f, r, s, -r*x.c-s*x.f)


def sample(job):
    orientation, offset = divmod(job, 3)
    o = G.orientations[orientation]
    frame = Xform(o.a, o.b, 3*offset+o.c0, o.d, o.e, 6*offset+o.f0)
    p = DEST / f"frame{job:02}"
    p.mkdir(exist_ok=True)
    tile = frame.apply_all(shape)
    text = "I? " + " ".join(f"{a} {b}" for a,b in sorted(tile))
    (p/"input.shape").write_text(text+"\n")
    if not (p/"native.txt").is_file():
        subprocess.run([BINARY, "-show", "-maxlevel", "3",
                        "-noisohedral", p/"input.shape", "-o", p/"native.txt"],
                       capture_output=True, timeout=90, check=True)
    raw = (p/"native.txt").read_text().splitlines()
    assert len(raw) == 3+int(raw[2])
    original = "I "+" ".join(f"{a} {b}" for a,b in sorted(shape))
    body = [original, "~ 3 3 1", raw[2]]
    for line in raw[3:]:
        level, motion = line.split(maxsplit=1)
        t = Xform(*map(int, motion.strip("<>").split(",")))
        xf = compose(inverse(frame), compose(t, frame))
        body.append(f"{level} {xf.as_text()}")
    witness = "\n".join(body)+"\n"
    verified = verify_witness(witness)
    if verified.result.hc_verified != 3:
        return dict(frame=job, foot=None, hc=verified.result.hc_verified,hh=verified.result.hh_verified)
    (p/"full.heesch").write_text(witness)
    footprint = sha256(repr(sorted(verified.hc_corona.patch_cells)).encode()).hexdigest()
    return dict(frame=job, foot=footprint, copies=verified.result.patch_size)


if __name__ == "__main__":
    with (DEST/"frames.jsonl").open("w") as out, ThreadPoolExecutor(2) as workers:
        for row in workers.map(sample, range(36)):
            print(json.dumps(row), file=out, flush=True)
