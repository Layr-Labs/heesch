"""V4 regression (2026-08 audit, archived in Linear): MAX_LEVELS bounds corona
depth but not total work, so a deep, fully-valid patch of large coronas ran
stages 5c/5d ~L times over the whole accumulated patch — ~380 s per submission,
pure CI arson (never a hang, always fails closed). check_corona now carries an
opt-in cumulative work budget: the encoder oracle passes max_work=None (its
large round-trip patches are unaffected), and the participant path enforces
patch.MAX_CORONA_WORK.
"""

import pytest

from util import ROOT, monomino_hc2  # noqa: F401

from heesch_verify import GRIDS, VerifyError, parse_submission
from heesch_verify import patch as P
from heesch_verify.result import ErrorCode
from heesch_verify.witness import VerifyConfig, verify_witness


def _corona(sub, max_work):
    grid = sub.grid
    return P.check_corona(
        frozenset(sub.cells), sub.patches[0], grid, grid.contact("point"),
        hole_mode="hh", max_work=max_work,
    )


def test_budget_trips_on_valid_patch():
    sub = parse_submission(monomino_hc2())  # a valid 2-corona witness
    with pytest.raises(VerifyError) as ei:
        _corona(sub, max_work=1)  # any real work exceeds a budget of 1
    assert ei.value.code is ErrorCode.RESOURCE_EXCEEDED


def test_oracle_default_is_unbudgeted():
    # The encoder oracle (max_work=None) must be untouched: the same valid
    # patch that trips at max_work=1 verifies with no budget.
    sub = parse_submission(monomino_hc2())
    res = _corona(sub, max_work=None)
    assert res.max_level == 2


def test_generous_budget_admits_legitimate_witness():
    sub = parse_submission(monomino_hc2())
    res = _corona(sub, max_work=P.MAX_CORONA_WORK)
    assert res.max_level == 2


def test_participant_path_enforces_budget(monkeypatch):
    # witness.py reads patch.MAX_CORONA_WORK at call time; a valid witness that
    # verifies under the real budget must reject once the budget is tightened.
    text = monomino_hc2()
    assert verify_witness(text).result.hh_verified == 2  # real budget: fine
    monkeypatch.setattr(P, "MAX_CORONA_WORK", 1)
    with pytest.raises(VerifyError) as ei:
        verify_witness(text)
    assert ei.value.code is ErrorCode.RESOURCE_EXCEEDED
