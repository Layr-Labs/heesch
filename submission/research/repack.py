"""Reproduce both fixed-footprint fourth-ring searches with OR-Tools 9.15.6755."""
import argparse
from pathlib import Path
from coverage import solve
from pocket_pack import pack

HERE=Path(__file__).resolve().parent

def run(dest):
    dest.mkdir(parents=True,exist_ok=True)
    for size,source in [(27,HERE.parent/'best.heesch'),(16,HERE/'companion16/best.heesch')]:
        base=dest/f'{size}-rings.heesch';output=dest/f'{size}-partial.heesch'
        base.write_text(source.read_text().split('#DEFECT')[0].rstrip()+'\n')
        solve(base,output,seconds=8,workers=1,seed=7119)
        header=next(r for r in output.read_text().splitlines() if r.startswith('#DEFECT'))
        pack(output,dest/f'{size}-improved.heesch',int(header.split()[2])-1,35)

if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('output',type=Path);run(cli.parse_args().output)
