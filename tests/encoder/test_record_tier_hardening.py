"""F1-F5 regression (2026-08 audit deep sweep, archived in Linear). The
record-tier proof pipeline is now the ENFORCED acceptance path for every
out-of-census submission (heesch_verify.proofgate.ProofCarryingGate,
architecture §2.2), so these are live invariants.

F1/F2: a RECORD must rest on the formally-verified checker (cake_lpr). The old
       code substituted lrat-check when cake_lpr was absent; lrat-check is not
       formally verified and is vacuously forgeable, so a record must never
       rest on it. cake_lpr absent => CHECKER_UNAVAILABLE, never a record.
F3:    a proof path whose basename begins with '-' is an argv-injection vector
       (drat-trim -S/-D); reject it before any checker runs.
F5:    an honest trivially-UNSAT record (formula carries the empty clause) stays
       recordable via the checker-independent empty-clause proof when the formal
       checker is unavailable.
"""

import pytest

from conftest import ROOT  # noqa: F401

from heesch_encoder.api import encode
from heesch_encoder.proofcheck import checkers as ck
from heesch_encoder.proofcheck import pipeline
from heesch_encoder.proofcheck.pipeline import (
    ProofStatus,
    ProofSubmission,
    Tier,
    check_proof,
)
from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.transform import Xform

_ID = Xform(1, 0, 0, 0, 1, 0)


def _enc(cells):
    grid = GRIDS["O"]
    contact = grid.contact("point")
    tile = frozenset(cells)
    corona = check_corona(tile, [(0, _ID)], grid, contact, hole_mode="hc")
    return tile, corona.patch_cells, grid, contact, encode(tile, corona.patch_cells, grid, contact)


# A plain domino: its F(S, P_1) is a normal (non-trivial) formula.
DOMINO = [(0, 0), (1, 0)]
# The slotted block whose formula carries the empty clause (trivially UNSAT).
SLOTTED = [(x, y) for x in range(5) for y in range(3) if (x, y) not in ((2, 1), (2, 2))]


def _sub(tmp_path, enc, body=b"1 2 0\n0\n", name="p.drat"):
    p = tmp_path / name
    p.write_bytes(body)
    return ProofSubmission(str(p), enc.digest, enc.num_vars, enc.num_clauses)


def test_record_needs_cake_lpr_no_lrat_check_fallback(tmp_path, monkeypatch):
    # drat-trim verifies, cake_lpr is absent. The FV slot must NOT fall back to
    # lrat-check; the record is denied as CHECKER_UNAVAILABLE.
    tile, patch, grid, contact, enc = _enc(DOMINO)
    calls = []
    monkeypatch.setattr(ck, "drat_trim", lambda *a, **k: (
        calls.append("drat-trim"),
        ck.CheckResult("drat-trim", ck.CheckStatus.VERIFIED, 0.0))[1])
    monkeypatch.setattr(ck, "cake_lpr", lambda *a, **k: (
        calls.append("cake_lpr"),
        ck.CheckResult("cake_lpr", ck.CheckStatus.CHECKER_MISSING, 0.0, "not built"))[1])
    monkeypatch.setattr(ck, "lrat_check", lambda *a, **k: (
        calls.append("lrat-check"),
        ck.CheckResult("lrat-check", ck.CheckStatus.VERIFIED, 0.0))[1])

    out = check_proof(_sub(tmp_path, enc), tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.CHECKER_UNAVAILABLE
    assert "lrat-check" not in calls, "record leaned on the non-FV checker"


def test_record_granted_when_cake_lpr_and_backer_verify(tmp_path, monkeypatch):
    tile, patch, grid, contact, enc = _enc(DOMINO)
    monkeypatch.setattr(ck, "drat_trim", lambda *a, **k:
                        ck.CheckResult("drat-trim", ck.CheckStatus.VERIFIED, 0.0))
    monkeypatch.setattr(ck, "cake_lpr", lambda *a, **k:
                        ck.CheckResult("cake_lpr", ck.CheckStatus.VERIFIED, 0.0))
    out = check_proof(_sub(tmp_path, enc), tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.VERIFIED


def test_dashed_proof_basename_rejected(tmp_path, monkeypatch):
    tile, patch, grid, contact, enc = _enc(DOMINO)
    called = []
    for n in ("drat_trim", "cake_lpr", "lrat_check"):
        monkeypatch.setattr(ck, n, lambda *a, **k: called.append(1))
    sub = _sub(tmp_path, enc, name="-S")  # basename begins with '-'
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.GATE_PROOF_INVALID
    assert not called, "a checker ran on a '-'-prefixed path"


def test_trivial_unsat_recordable_without_formal_checker(tmp_path, monkeypatch):
    # F5: empty-clause formula, cake_lpr absent -> still VERIFIED (sound).
    tile, patch, grid, contact, enc = _enc(SLOTTED)
    assert pipeline._has_empty_clause(enc.dimacs), "fixture must be trivially UNSAT"
    monkeypatch.setattr(ck, "drat_trim", lambda *a, **k:
                        ck.CheckResult("drat-trim", ck.CheckStatus.VERIFIED, 0.0))
    monkeypatch.setattr(ck, "cake_lpr", lambda *a, **k:
                        ck.CheckResult("cake_lpr", ck.CheckStatus.CHECKER_MISSING, 0.0))
    out = check_proof(_sub(tmp_path, enc, body=b"0\n"), tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.VERIFIED
    assert "empty clause" in out.detail


def test_no_empty_clause_still_unavailable(tmp_path, monkeypatch):
    # The F5 recovery must NOT fire for a normal formula: missing checker stays
    # CHECKER_UNAVAILABLE.
    tile, patch, grid, contact, enc = _enc(DOMINO)
    assert not pipeline._has_empty_clause(enc.dimacs)
    monkeypatch.setattr(ck, "drat_trim", lambda *a, **k:
                        ck.CheckResult("drat-trim", ck.CheckStatus.VERIFIED, 0.0))
    monkeypatch.setattr(ck, "cake_lpr", lambda *a, **k:
                        ck.CheckResult("cake_lpr", ck.CheckStatus.CHECKER_MISSING, 0.0))
    out = check_proof(_sub(tmp_path, enc), tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.CHECKER_UNAVAILABLE
