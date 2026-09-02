"""hole_mode oracle semantics (multilevel encoder spec §9.1 prerequisite).

The three modes must be monotone (hc accepts ⇒ hh accepts ⇒ none accepts)
and agree on levels/max_level whenever they accept; "none" never raises on
holes and is the hole-agnostic Stage 5 oracle the v2 round trips consume.
"""

import pathlib
import random

import pytest

from util import ROOT, monomino_hc2
from test_differential import _random_mutation

from heesch_verify import VerifyError, parse_submission
from heesch_verify.patch import check_corona
from heesch_verify.grids import GRIDS

CORPUS = pathlib.Path(ROOT) / "tests" / "corpus"


def _run(sub, patch_idx, mode):
    grid = sub.grid
    contact = grid.contact("point")
    try:
        return check_corona(frozenset(sub.cells), sub.patches[patch_idx],
                            grid, contact, hole_mode=mode)
    except VerifyError as e:
        return e


def test_invalid_mode_rejected():
    sub = parse_submission(monomino_hc2())
    with pytest.raises(ValueError):
        _run(sub, 0, "bogus")


def test_outer_holed_witness_three_modes():
    """An hc0hh1 corpus witness's second patch has holes in its outermost
    corona: hc rejects, hh accepts with has_outer_holes, none accepts and
    agrees on structure."""
    candidates = sorted(CORPUS.glob("*-hc0hh1.txt"))
    assert candidates, "corpus missing hc0hh1 witnesses"
    sub = parse_submission(candidates[0].read_text(encoding="ascii"))
    assert sub.patch_count == 2

    r_hc = _run(sub, 1, "hc")
    r_hh = _run(sub, 1, "hh")
    r_none = _run(sub, 1, "none")

    assert isinstance(r_hc, VerifyError) and r_hc.code.value == "PATCH_HOLE_IN_CORONA"
    assert not isinstance(r_hh, VerifyError) and r_hh.has_outer_holes
    assert not isinstance(r_none, VerifyError) and r_none.has_outer_holes
    assert r_hh.levels == r_none.levels
    assert r_hh.max_level == r_none.max_level


def test_monotonicity_over_mutations():
    """For random mutations of valid witnesses: acceptance is monotone
    hc ⇒ hh ⇒ none, and accepted modes agree on levels and max_level."""
    rng = random.Random(11)
    bases = [monomino_hc2()]
    for p in sorted(CORPUS.glob("omino7-nontiler-*.txt"))[:2]:
        bases.append(p.read_text(encoding="ascii"))

    checked = 0
    for _ in range(300):
        text = _random_mutation(rng, rng.choice(bases))
        try:
            sub = parse_submission(text)
        except VerifyError:
            continue
        if not sub.patches:
            continue
        results = {m: _run(sub, 0, m) for m in ("hc", "hh", "none")}
        ok = {m: not isinstance(r, VerifyError) for m, r in results.items()}
        assert (not ok["hc"] or ok["hh"]) and (not ok["hh"] or ok["none"]), (
            f"monotonicity violated: {ok}\n{text}"
        )
        accepted = [r for r in results.values() if not isinstance(r, VerifyError)]
        for r in accepted[1:]:
            assert r.levels == accepted[0].levels
            assert r.max_level == accepted[0].max_level
        checked += 1
    assert checked > 50
