"""Run the published coverage model on the fresh four-ring chart and refine its pockets."""
from pathlib import Path
import argparse
from coverage import solve
from pocket import pack
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output_directory', type=Path)
    args=parser.parse_args(); args.output_directory.mkdir(parents=True,exist_ok=True)
    chart=Path(__file__).resolve().parents[1]/'patches/fresh-four.heesch'
    first=args.output_directory/'coverage.heesch'; final=args.output_directory/'pocket.heesch'
    solve(chart,first,seconds=15,workers=1,seed=3979)
    witness=verify_witness(first.read_text())
    defects=verify_defect(frozenset(witness.submission.cells),witness.submission.grid,witness.hc_corona,witness.submission.defect,witness.contact)
    pack(first,final,defects.defect_hc-1,30)
