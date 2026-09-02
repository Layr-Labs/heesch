"""Record flags (audit 2026-08-19 High 1): a verified Hc >= 5 plus ANY checked
finite upper bound on Hh is record-breaking; exactness is a separate flag."""

import importlib.util

from util import ROOT


def _harness():
    spec = importlib.util.spec_from_file_location("harness_verify", ROOT / "harness" / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_record_eligible_predicate():
    h = _harness()
    assert h._record_eligible("proof", 5) is True      # Hc >= 5, Hh <= m-1: record whatever Hc is
    assert h._record_eligible("proof", 6) is True
    assert h._record_eligible("proof", 4) is False     # ties the known value, not a record
    assert h._record_eligible("census", 5) is False    # a record is proof-backed by construction
    assert h._record_eligible("", 5) is False


def test_result_json_carries_both_flags():
    from heesch_verify.result import Result

    r = Result(hc_verified=5, hh_verified=6, cell_count=11, span_x=4, span_y=4, symmetry_order=1,
               patch_size=10, grid="H", reflections_used=False, canonical_digest="0" * 64,
               non_tiler_evidence="proof", tier="lower_bound", exact=False,
               record_eligible=True, record_exact=False)
    j = r.to_json()
    assert j["record_eligible"] is True and j["record_exact"] is False and j["exact"] is False
