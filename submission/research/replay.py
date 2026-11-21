"""Replay checked triangle geometries and compare the F(S,5) hashes."""
from collections import Counter
from fractions import Fraction
from pathlib import Path
import hashlib,json,lzma
from heesch_verify import verify_witness
from heesch_verify.canonical import canonical_digest
from heesch_verify.defect import verify_defect
from heesch_verify.shape import holes_of

here=Path(__file__).resolve().parent; folder=here.parent
expected=json.loads((here/'results.json').read_text()); files={folder/'best.heesch':expected['submitted']};files.update({here/k:v for k,v in expected['other_witnesses'].items()})
for path,entry in files.items():
    w=verify_witness(path.read_text());s=w.submission;shape=frozenset(s.cells); d=verify_defect(shape,s.grid,w.hc_corona,s.defect,w.contact)
    assert w.result.hc_verified==4 and w.result.hh_verified==4
    assert canonical_digest(shape,s.grid,True)==entry['shape']
    assert (d.required,d.defect_hc,d.defect_hh,d.partial_tiles,d.pocket_cells)==(entry['required'],entry['defect_hc'],entry['defect_hh'],entry['partial'],entry['extra_pocket_cells'])
    outer=frozenset().union(*(xf.apply_all(shape) for _,xf in s.defect.tiles));holes=holes_of(w.hc_corona.patch_cells|outer,s.grid);assert len(holes)==entry['all_enclosed_cells'];score=4+Fraction(d.required-d.defect_hc,d.required);assert str(score)==entry['score_exact']
    print(path.name,score,float(score),'charged defects',d.defect_hc,'required',d.required,'extra pockets',d.pocket_cells)
with (folder/'proof.drat.xz').open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected['proof_file_sha256']
with lzma.open(folder/'proof.drat.xz','rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected['proof_payload_sha256']
print('Proof hashes match the published and locally reverified F(S,5) certificate.')
