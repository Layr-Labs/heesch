"""Project complete rings with all lattice symmetries, then test strict score without a radius cap."""
from collections import Counter
from pathlib import Path
import argparse
import json
import subprocess
import sys

here = Path(__file__).resolve().parent
alg = here/"solver"


def run(args, log):
    if not log.exists():
        with log.open("w") as stream:
            subprocess.run([sys.executable, "-u", *map(str, args)], stdout=stream, stderr=subprocess.STDOUT, check=True)
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.startswith("{")]
    return rows


def visit(source, d, dest, options):
    dest.mkdir(parents=True, exist_ok=True)
    samples = 10000
    result = run([alg/"joint.py", "--source", source, "--full-through", d, "--sample-domains", samples,
                  "--seconds", options.seconds, "--workers", 1, "--geometry-only",
                  "--output", dest/"patch.heesch"], dest/"project.log")
    end = next(r["status"] for r in reversed(result) if "status" in r)
    children = sorted(dest.glob("patch-*.heesch"))
    print(d, source, len(children), end, flush=True)
    stats = Counter({f"level{d}-{end}":1, f"level{d}-children":len(children)})
    for child in children:
        if d < 4:
            stats.update(visit(child, d+1, dest/child.stem, options))
        else:
            bound = run([alg/"boundary_bound.py", child, "--seconds", 20, "--workers", 1], dest/(child.stem+".bound.log"))[-1]
            lead = dest/(child.stem+"-lead.heesch")
            r = run([alg/"joint.py", "--source", child, "--target", 1, "--boundary-max", bound["upper_bound"],
                     "--damage-max", bound["max_damage"], "--seconds", 120, "--workers", 1,
                     "--geometry-only", "--output", lead], dest/(child.stem+".strict.log"))
            end = next(x["status"] for x in reversed(r) if "status" in x)
            stats["strict-"+end] += 1
            print("strict", child, end, "witness", lead if lead.exists() else None, flush=True)
    return stats


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--seconds", type=int, default=90)
    p.add_argument("--start", type=int, default=2)
    o = p.parse_args()
    stats = visit(o.source, o.start, o.output, o)
    (o.output/"counts.json").write_text(json.dumps(stats, indent=2)+"\n")
    print(stats)
