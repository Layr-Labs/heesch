"""Exhaust the immediately tighter fourth-ring budget on the selected solid third."""
from pathlib import Path
import argparse,time
from heesch_verify import verify_witness
from heesch_verify.defect import verify_defect
from pack import Packing


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('which',choices=('best','other'))
    parser.add_argument('--seconds',type=int,default=180)
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    src=here.parent/'best.heesch' if args.which=='best' else here/'compact-third.heesch'
    w=verify_witness(src.read_text());s=frozenset(w.submission.cells)
    d=verify_defect(s,w.submission.grid,w.hc_corona,w.submission.defect,w.contact).defect_hc
    model=Packing(w.submission.grid,s,w.hc_corona.patch_cells,w.contact,d-1)
    model.model.clear_objective()
    model.add_hint({t.apply_all(s) for l,t in w.submission.defect.tiles})
    selection,status=model.solve(time.monotonic()+args.seconds,2,192711)
    print({'certified_geometry':d,'tighter_budget':d-1,**status})
    if selection is not None or status['status']!='INFEASIBLE':raise SystemExit(1)


if __name__=='__main__':main()
