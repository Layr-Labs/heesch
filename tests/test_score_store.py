"""§9.2.4/§9.2.5 score ordering and §12.6 record store supersession."""

from dataclasses import replace

from util import ROOT  # noqa: F401  (sys.path bootstrap)

from heesch_verify.result import Result
from heesch_verify.score import (
    hc_board_key,
    hh_board_key,
    strictly_better,
    yukon_score,
)
from heesch_verify.store import RecordStore


def mk(digest="d0", hc=2, hh=2, cells=9, span=(4, 3), patch=30,
       block=True, dhc=5, dhh=5, req=20, level=3) -> Result:
    return Result(
        hc_verified=hc, hh_verified=hh, cell_count=cells, span_x=span[0],
        span_y=span[1], symmetry_order=1, patch_size=patch, grid="O",
        reflections_used=True, canonical_digest=digest,
        defect_block_present=block, defect_corona_level=level,
        defect_hc=dhc, defect_hh=dhh, defect_required=req,
        defect_pocket_cells=dhc - dhh, defect_partial_tiles=4,
    )


def test_fraction_ranking_cross_multiplied_no_floats():
    # u=3/r=20 vs u=3/r=187: the second is closer to complete and ranks
    # better. 3/20 > 3/187 as fractions; lower fraction = better.
    a = mk(dhc=3, dhh=3, req=20)
    b = mk(dhc=3, dhh=3, req=187)
    assert hc_board_key(b) > hc_board_key(a)


def test_integer_heesch_dominates_defect():
    # Defect 2 at corona 3 must never outrank defect 40 at corona 5.
    low = mk(hc=3, hh=3, dhc=2, dhh=2, req=30, level=4)
    high = mk(hc=5, hh=5, dhc=40, dhh=40, req=44, level=6)
    assert hc_board_key(high) > hc_board_key(low)


def test_hc_board_reads_defect_hc_only():
    # Two records identical except defect_hh: the Hc board must not
    # distinguish them (ranking an Hc board on defect_hh is the §9.2.1 bug).
    a = mk(dhc=5, dhh=5)
    b = mk(dhc=5, dhh=1)
    assert hc_board_key(a) == hc_board_key(b)
    # And the Hh board must distinguish them.
    assert hh_board_key(b) > hh_board_key(a)


def test_missing_block_is_worst_fraction():
    with_block = mk(dhc=19, dhh=19, req=20)     # bad but present
    without = mk(block=False, dhc=0, dhh=0, req=0)
    assert hc_board_key(with_block) > hc_board_key(without)


def test_yukon_score_gradient_and_clamp():
    assert yukon_score(mk(hc=2, dhc=20, req=20)) == 2.0     # zero progress
    assert yukon_score(mk(hc=2, dhc=0, req=20)) == 2.999999  # clamped below 3
    s = yukon_score(mk(hc=2, dhc=5, req=20))
    assert 2.74 < s < 2.76
    assert yukon_score(mk(hc=2, block=False, dhc=0, req=0)) == 2.0


def test_store_gradient_sequence_four_promotions_zero_duplicates():
    # The §9.2 regression: 47 -> 31 -> 12 -> 0 on one shape, four promotions.
    store = RecordStore()
    outcomes = []
    for i, d in enumerate((47, 31, 12, 0)):
        r = mk(digest="shape1", dhc=d, dhh=d, req=60)
        outcomes.append(store.put(r, entrant=f"e{i}", submitted_at=f"t{i}"))
    assert [o.status for o in outcomes] == ["PROMOTED"] * 4
    assert len(store.history("shape1")) == 4
    # Attribution: discoverer stays with the first entrant.
    assert store.get("shape1").discoverer == "e0"
    assert store.get("shape1").entrant == "e3"


def test_store_duplicate_names_existing_record():
    store = RecordStore()
    store.put(mk(digest="s", dhc=10), "alice", "t0")
    v = store.put(mk(digest="s", dhc=10), "bob", "t1")
    assert v.status == "DUPLICATE"
    assert "alice" in v.message


def test_store_worse_tuple_duplicate_names_component():
    store = RecordStore()
    store.put(mk(digest="s", dhc=10), "alice", "t0")
    v = store.put(mk(digest="s", dhc=15), "bob", "t1")
    assert v.status == "DUPLICATE"
    assert "defect_fraction" in v.message


def test_store_supersession_retains_old_record():
    store = RecordStore()
    store.put(mk(digest="s", hc=2), "alice", "t0")
    v = store.put(mk(digest="s", hc=3), "bob", "t1")
    assert v.status == "PROMOTED"
    hist = store.history("s")
    assert len(hist) == 2
    assert hist[0].superseded and "primary" in hist[0].supersede_reason
    assert store.get("s").discoverer == "alice"  # attribution carried


def test_store_same_shape_rotated_is_same_digest_not_second_entry():
    # Digest equality is established by the canonical tests; here: same
    # digest with a better tuple promotes rather than duplicating.
    store = RecordStore()
    store.put(mk(digest="rot", hc=1), "alice", "t0")
    v = store.put(mk(digest="rot", hc=2), "bob", "t1")
    assert v.status == "PROMOTED"
    assert len(store.history("rot")) == 2


def test_journal_appends(tmp_path):
    p = tmp_path / "records.jsonl"
    store = RecordStore(path=str(p))
    store.put(mk(digest="j1"), "alice", "t0")
    store.put(mk(digest="j1", dhc=1), "bob", "t1")
    lines = p.read_text().strip().split("\n")
    assert len(lines) == 2


def test_defect_enabled_flag_gates_the_fraction():
    """Audit 2026-08-19 Low 13: the emitted `defect_enabled` and the score
    agree — with the flag off, defect credit enters neither the scalar nor
    the ranking."""
    from dataclasses import replace
    on = mk(hc=2, dhc=5, req=20)
    off = replace(on, defect_enabled=False)
    assert on.defect_enabled is True
    assert yukon_score(on) > 2.0
    assert yukon_score(off) == 2.0
    assert hc_board_key(off) < hc_board_key(on)
    assert hc_board_key(off) == hc_board_key(replace(on, defect_block_present=False))
