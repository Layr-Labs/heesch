"""§9.5 negative proof handling. The pre-checker stages (digest match,
header counts, size gate, format sniff, truncation) must reject BEFORE any
checker subprocess runs — asserted with a spy. Checker-dependent positive
paths are exercised in CI where tools/bin is built."""

import pathlib

import pytest

from conftest import FIXTURES, ROOT  # noqa: F401

from heesch_encoder.api import encode
from heesch_encoder.proofcheck import checkers as ck
from heesch_encoder.proofcheck import pipeline
from heesch_encoder.proofcheck.formats import ProofFormat, sniff
from heesch_encoder.proofcheck.pipeline import (
    ProofStatus,
    ProofSubmission,
    Tier,
    check_proof,
)
from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.transform import Xform


def _enc():
    grid = GRIDS["O"]
    contact = grid.contact("point")
    tile = frozenset([(0, 0), (1, 0)])
    corona = check_corona(tile, [(0, Xform(1, 0, 0, 0, 1, 0))], grid, contact,
                          hole_mode="hc")
    return tile, corona.patch_cells, grid, contact, encode(tile, corona.patch_cells, grid, contact)


@pytest.fixture
def spy_checkers(monkeypatch):
    calls = []

    def fake(name):
        def run(*a, **k):
            calls.append(name)
            return ck.CheckResult(name, ck.CheckStatus.VERIFIED, 0.0)
        return run

    monkeypatch.setattr(ck, "drat_trim", fake("drat-trim"))
    monkeypatch.setattr(ck, "lrat_check", fake("lrat-check"))
    monkeypatch.setattr(ck, "cake_lpr", fake("cake_lpr"))
    return calls


def _write(tmp_path, name, data: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_digest_mismatch_rejects_before_checkers(tmp_path, spy_checkers):
    tile, patch, grid, contact, enc = _enc()
    proof = _write(tmp_path, "p.drat", b"1 2 0\n0\n")
    sub = ProofSubmission(proof, "0" * 64, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.PROOF_CNF_DIGEST_MISMATCH
    assert spy_checkers == [], "checkers were invoked despite digest mismatch"


def test_header_mismatch_rejects_before_checkers(tmp_path, spy_checkers):
    tile, patch, grid, contact, enc = _enc()
    proof = _write(tmp_path, "p.drat", b"1 2 0\n0\n")
    sub = ProofSubmission(proof, enc.digest, enc.num_vars + 1, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.PROOF_HEADER_MISMATCH
    assert spy_checkers == []


def test_sat_model_rejected_at_sniff(tmp_path, spy_checkers):
    tile, patch, grid, contact, enc = _enc()
    proof = _write(tmp_path, "model.txt", b"s SATISFIABLE\nv 1 -2 3 0\n")
    sub = ProofSubmission(proof, enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.GATE_PROOF_INVALID
    assert "model" in out.detail
    assert spy_checkers == []


def test_empty_proof_rejected(tmp_path, spy_checkers):
    tile, patch, grid, contact, enc = _enc()
    proof = _write(tmp_path, "empty.drat", b"")
    sub = ProofSubmission(proof, enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.GATE_PROOF_INVALID
    assert spy_checkers == []


def test_truncated_proof_rejected(tmp_path, spy_checkers):
    tile, patch, grid, contact, enc = _enc()
    proof = _write(tmp_path, "trunc.drat", b"1 2 0\n-1 3 0\n5 -2")  # mid-line end
    sub = ProofSubmission(proof, enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.PROOF_TRUNCATED
    assert spy_checkers == []


def test_oversized_proof_is_resource_exceeded(tmp_path, spy_checkers, monkeypatch):
    tile, patch, grid, contact, enc = _enc()
    proof = _write(tmp_path, "big.drat", b"1 0\n")
    monkeypatch.setattr(pipeline, "MAX_PROOF_BYTES", 2)
    sub = ProofSubmission(proof, enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.RESOURCE_EXCEEDED
    assert "cap" in out.detail
    assert spy_checkers == []


def test_record_tier_requires_two_verified(tmp_path, monkeypatch):
    """Policy: record tier with a second checker returning NOT_VERIFIED must
    fail overall, one VERIFIED is not enough."""
    tile, patch, grid, contact, enc = _enc()

    monkeypatch.setattr(
        ck, "drat_trim",
        lambda *a, **k: ck.CheckResult("drat-trim", ck.CheckStatus.VERIFIED, 0.1),
    )
    monkeypatch.setattr(
        ck, "cake_lpr",
        lambda *a, **k: ck.CheckResult("cake_lpr", ck.CheckStatus.NOT_VERIFIED, 0.1),
    )
    monkeypatch.setattr(
        ck, "lrat_check",
        lambda *a, **k: ck.CheckResult("lrat-check", ck.CheckStatus.NOT_VERIFIED, 0.1),
    )
    proof = _write(tmp_path, "p.drat", b"1 2 0\n0\n")
    sub = ProofSubmission(proof, enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, patch, grid, contact, Tier.RECORD)
    assert out.status is ProofStatus.GATE_PROOF_INVALID

    # Triage tier: one VERIFIED suffices.
    out2 = check_proof(sub, tile, patch, grid, contact, Tier.TRIAGE)
    assert out2.status is ProofStatus.VERIFIED


def test_sniff_formats(tmp_path):
    cases = {
        b"": ProofFormat.EMPTY,
        b"s SATISFIABLE\nv 1 2 0\n": ProofFormat.SAT_MODEL,
        b"1 -2 3 0\nd 1 -2 0\n0\n": ProofFormat.DRAT_TEXT,
        b"5 1 -2 0 1 3 0\n6 0 4 5 0\n": ProofFormat.LRAT_TEXT,
    }
    for data, expected in cases.items():
        p = tmp_path / "f"
        p.write_bytes(data)
        assert sniff(str(p)) is expected, f"{data!r} -> {sniff(str(p))}"


CHECKERS_BUILT = (pathlib.Path(ROOT) / "tools" / "bin" / "drat-trim").exists() or (
    pathlib.Path(ROOT) / "tools" / "bin" / "drat-trim.exe"
).exists()


@pytest.mark.skipif(not CHECKERS_BUILT, reason="tools/bin checkers not built (CI-only)")
def test_real_checker_verifies_trivial_unsat(tmp_path):
    """Positive control with the real drat-trim: the slotted block's formula
    contains an empty clause, so the empty-clause DRAT proof verifies."""
    grid = GRIDS["O"]
    contact = grid.contact("point")
    cells = [(x, y) for x in range(5) for y in range(3)
             if (x, y) not in ((2, 1), (2, 2))]
    tile = frozenset(cells)
    corona = check_corona(tile, [(0, Xform(1, 0, 0, 0, 1, 0))], grid, contact,
                          hole_mode="hc")
    enc = encode(tile, corona.patch_cells, grid, contact)
    proof = _write(tmp_path, "p.drat", b"0\n")
    sub = ProofSubmission(proof, enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof(sub, tile, corona.patch_cells, grid, contact, Tier.TRIAGE)
    assert out.status is ProofStatus.VERIFIED, out.detail
