"""§10/§12.1 calibration: reproduce known truth from tests/corpus.

Corpus files are heesch-sat-format witnesses named
  <family><n>-nontiler-<j>-hc<H>hh<H>.txt   (verified witnesses)
  <family><n>-holed-<j>.txt                 (must reject SHAPE_HAS_HOLE)
plus corpus/MANIFEST.json recording the expected population counts per
family/size (from Kaplan 2022's tables), asserted when the corpus for that
family/size is marked complete.

If the verifier disagrees with any of these, the contact convention or
surround rule is wrong (spec §10) — do not paper over it.
"""

import json
import pathlib
import re

import pytest

from util import ROOT  # noqa: F401

from heesch_verify import ErrorCode, VerifyConfig, VerifyError, verify_witness
from heesch_verify.gates import IsohedralGate, Verdict
from heesch_verify.grids import GRIDS

CORPUS = pathlib.Path(__file__).parent / "corpus"

WITNESS_RE = re.compile(r"^(omino|hex|iamond)(\d+)-nontiler-\d+-hc(\d+)hh(\d+)\.txt$")
HOLED_RE = re.compile(r"^(omino|hex|iamond)(\d+)-holed-\d+\.txt$")

witness_files = sorted(p for p in CORPUS.glob("*.txt") if WITNESS_RE.match(p.name)) if CORPUS.exists() else []
holed_files = sorted(p for p in CORPUS.glob("*.txt") if HOLED_RE.match(p.name)) if CORPUS.exists() else []

pytestmark = pytest.mark.skipif(
    not CORPUS.exists() or not witness_files,
    reason="calibration corpus not yet generated (tools/classify.py / CI fixtures)",
)


@pytest.mark.parametrize("path", witness_files, ids=[p.name for p in witness_files])
def test_witness_reproduces_known_truth(path):
    m = WITNESS_RE.match(path.name)
    hc, hh = int(m.group(3)), int(m.group(4))
    out = verify_witness(path.read_text(encoding="ascii"), VerifyConfig(strict_claims=True))
    assert out.result.hc_verified == hc, path.name
    assert out.result.hh_verified == hh, path.name
    # Known non-tilers must NOT be flagged TILER by the gate.
    grid = GRIDS[out.submission.grid_id]
    assert IsohedralGate(grid).check(frozenset(out.submission.cells)) is not Verdict.TILER, (
        f"{path.name}: gate claims a known non-tiler tiles — criterion bug"
    )


@pytest.mark.parametrize("path", holed_files, ids=[p.name for p in holed_files])
def test_holed_shape_rejects(path):
    with pytest.raises(VerifyError) as ei:
        verify_witness(path.read_text(encoding="ascii"))
    assert ei.value.code is ErrorCode.SHAPE_HAS_HOLE


def test_population_counts():
    manifest_path = CORPUS / "MANIFEST.json"
    if not manifest_path.exists():
        pytest.skip("no corpus manifest yet")
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["complete_families"]:
        fam, n = entry["family"], entry["n"]
        expected = entry["by_hc"]  # {"0": count, "1": count, ...}
        found: dict[str, int] = {}
        for p in witness_files:
            m = WITNESS_RE.match(p.name)
            if m.group(1) == fam and int(m.group(2)) == n:
                found[m.group(3)] = found.get(m.group(3), 0) + 1
        assert found == expected, f"{fam}-{n}: witness census {found} != published {expected}"
        holed = sum(
            1 for p in holed_files
            if (hm := HOLED_RE.match(p.name)) and hm.group(1) == fam and int(hm.group(2)) == n
        )
        assert holed == entry["holed"], f"{fam}-{n}: holed count"
