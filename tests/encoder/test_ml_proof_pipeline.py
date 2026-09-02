"""Proof pipeline over v2 CNFs: the frozen pre-checker stages behave
identically (spy asserts no checker runs on early rejects), plus the §9.8
positive control through real drat-trim when tools/bin is built (CI)."""

import pathlib

import pytest

from conftest import ROOT

from heesch_encoder.multilevel.api import encode_multilevel
from heesch_encoder.proofcheck import checkers as ck
from heesch_encoder.proofcheck.pipeline import (
    ProofStatus,
    ProofSubmission,
    Tier,
    check_proof_v2,
)
from heesch_verify.grids import GRIDS

# The census-closed octomino: F(S,2) is genuinely UNSAT (its exactness proof
# target). Cells transcribed from the corpus witness.
_CORPUS = pathlib.Path(ROOT) / "tests" / "corpus"


def _unsat_octomino():
    from heesch_verify.parse import parse_submission

    files = sorted(_CORPUS.glob("omino8-nontiler-*-hc1hh1.txt"))
    assert files, "census-closed octomino corpus file missing"
    # Any hc1hh1 octomino whose F(S,2) is UNSAT works; the census-closed one
    # is guaranteed. Try each until one is UNSAT-by-encoding... cheaper: just
    # use the last-indexed file (the census closure).
    sub = parse_submission(files[-1].read_text(encoding="ascii"))
    return frozenset(sub.cells), sub.grid


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


def test_v2_digest_mismatch_rejects_before_checkers(tmp_path, spy_checkers):
    tile, grid = _unsat_octomino()
    contact = grid.contact("point")
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"1 2 0\n0\n")
    sub = ProofSubmission(str(proof), "0" * 64, 1, 1)
    out = check_proof_v2(sub, tile, grid, contact, 2, Tier.RECORD)
    assert out.status is ProofStatus.PROOF_CNF_DIGEST_MISMATCH
    assert spy_checkers == []


def test_v2_header_mismatch(tmp_path, spy_checkers):
    tile, grid = _unsat_octomino()
    contact = grid.contact("point")
    enc = encode_multilevel(tile, grid, contact, 2)
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"1 2 0\n0\n")
    sub = ProofSubmission(str(proof), enc.digest, enc.num_vars + 1, enc.num_clauses)
    out = check_proof_v2(sub, tile, grid, contact, 2, Tier.RECORD)
    assert out.status is ProofStatus.PROOF_HEADER_MISMATCH
    assert spy_checkers == []


CHECKERS_BUILT = (pathlib.Path(ROOT) / "tools" / "bin" / "drat-trim").exists() or (
    pathlib.Path(ROOT) / "tools" / "bin" / "drat-trim.exe"
).exists()


@pytest.mark.skipif(not CHECKERS_BUILT, reason="tools/bin checkers not built (CI-only)")
def test_v2_real_unsat_proof_verifies(tmp_path):
    """§9.8 positive control: solve the census-closed octomino's F(S,2) with
    a DRAT-emitting run and check the proof through the real pipeline. Uses
    pysat's cadical with proof tracing when available; skips otherwise."""
    from pysat.solvers import Solver

    tile, grid = _unsat_octomino()
    contact = grid.contact("point")
    enc = encode_multilevel(tile, grid, contact, 2)

    with Solver(name="cadical195",
                bootstrap_with=[list(c) for c in enc.formula.clauses],
                with_proof=True) as s:
        assert not s.solve(), "expected UNSAT for the census-closed octomino"
        proof_lines = s.get_proof()
    proof = tmp_path / "p.drat"
    proof.write_text("\n".join(proof_lines) + "\n0\n", encoding="ascii")

    sub = ProofSubmission(str(proof), enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof_v2(sub, tile, grid, contact, 2, Tier.TRIAGE)
    assert out.status is ProofStatus.VERIFIED, out.detail


def test_v2_out_of_band_rejects_before_encoding(tmp_path, monkeypatch):
    """Revision-2 feasibility band (multilevel spec §10.2) is enforced by
    policy BEFORE any encoding work starts."""
    import heesch_encoder.multilevel.api as mlapi

    called = []
    monkeypatch.setattr(mlapi, "encode_multilevel",
                        lambda *a, **k: called.append(1) or (_ for _ in ()).throw(AssertionError))
    tile = frozenset((x, y) for x in range(10) for y in range(6))  # 60 cells
    grid = _unsat_octomino()[1]
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"0\n")
    out = check_proof_v2(ProofSubmission(str(proof), "0" * 64, 1, 1), tile, grid,
                         grid.contact("point"), 4, Tier.RECORD)
    assert out.status is ProofStatus.RESOURCE_EXCEEDED
    assert "feasibility band" in out.detail
    assert not called


def test_explicit_bin_dir_missing_is_checker_missing(tmp_path):
    r = ck.drat_trim("x.cnf", "p.drat", bin_dir=tmp_path / "nowhere")
    assert r.status is ck.CheckStatus.CHECKER_MISSING
    assert str(tmp_path / "nowhere") in r.detail


def test_budget_exhausted_does_not_spawn(tmp_path):
    b = ck.CheckBudget(deadline_seconds=0.0)
    d = tmp_path
    exe = ck.checker_path("drat-trim", d)  # .exe on Windows
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)  # the spawn predicate now requires a regular, executable file
    r = ck.drat_trim("x.cnf", "p.drat", bin_dir=d, budget=b)
    assert r.status is ck.CheckStatus.RESOURCE_EXCEEDED
    assert "deadline" in r.detail


# --- audit 2026-08-19 Medium 5: the encode guard bounds ONLY the encoder -----

def _has_alarm():
    import signal
    import threading
    return hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()


def test_encode_timeout_is_resource_exceeded(tmp_path, monkeypatch, spy_checkers):
    if not _has_alarm():
        pytest.skip("SIGALRM guard is a no-op here")
    import time
    import heesch_encoder.multilevel.api as mlapi

    def slow(*a, **k):
        time.sleep(3)
        raise AssertionError("encoder should have been interrupted")
    monkeypatch.setattr(mlapi, "encode_multilevel_stream", slow)
    tile, grid = _unsat_octomino()
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"0\n")
    out = check_proof_v2(ProofSubmission(str(proof), "0" * 64, 1, 1), tile, grid,
                         grid.contact("point"), 2, Tier.RECORD, encode_timeout_s=1)
    assert out.status is ProofStatus.RESOURCE_EXCEEDED
    assert "encoding F(S,2)" in out.detail
    assert spy_checkers == []


def test_encode_guard_does_not_cover_checkers(tmp_path, monkeypatch):
    """The guard is disarmed before check_proof_encoded runs: a checker stage
    longer than encode_timeout_s is NOT interrupted by it (the checkers have
    their own CheckBudget)."""
    if not _has_alarm():
        pytest.skip("SIGALRM guard is a no-op here")
    import time
    import heesch_encoder.multilevel.api as mlapi
    import heesch_encoder.proofcheck.pipeline as pl

    sentinel = pl.ProofOutcome(ProofStatus.GATE_PROOF_INVALID, "sentinel")

    # Instant stub encoder (a real encode can exceed the 1 s test limit on a
    # slow CI runner, which would be the guard firing legitimately); only the
    # checker stage is slow here.
    monkeypatch.setattr(mlapi, "encode_multilevel_stream", lambda *a, **k: object())

    def slow_checked(*a, **k):
        time.sleep(2)
        return sentinel
    monkeypatch.setattr(pl, "check_proof_encoded", slow_checked)
    tile, grid = _unsat_octomino()
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"0\n")
    out = pl.check_proof_v2(ProofSubmission(str(proof), "0" * 64, 1, 1), tile, grid,
                            grid.contact("point"), 2, Tier.RECORD, encode_timeout_s=1)
    assert out is sentinel


def test_encode_limit_is_clipped_to_budget_deadline(tmp_path, monkeypatch):
    """An exhausted CheckBudget refuses to start the encoder at all."""
    import heesch_encoder.multilevel.api as mlapi
    called = []
    monkeypatch.setattr(mlapi, "encode_multilevel_stream", lambda *a, **k: called.append(1))
    tile, grid = _unsat_octomino()
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"0\n")
    out = check_proof_v2(ProofSubmission(str(proof), "0" * 64, 1, 1), tile, grid,
                         grid.contact("point"), 2, Tier.RECORD,
                         budget=ck.CheckBudget(deadline_seconds=0.0))
    assert out.status is ProofStatus.RESOURCE_EXCEEDED
    assert "before encoding" in out.detail
    assert not called


def test_portable_encode_deadline_without_sigalrm(tmp_path, monkeypatch):
    """The monotonic deadline inside the encoder fires even where SIGALRM is
    unavailable (Windows / worker threads): run the check in a worker thread,
    where the alarm guard is a no-op by construction."""
    import threading
    import time
    import heesch_encoder.multilevel.universe as uni

    # Make every level of the universe BFS "slow" by moving the clock.
    real = time.monotonic
    t = {"now": real()}
    monkeypatch.setattr(time, "monotonic", lambda: t["now"])
    orig = uni._check_deadline

    def advancing(deadline):
        t["now"] += 10.0
        orig(deadline)
    monkeypatch.setattr(uni, "_check_deadline", advancing)

    tile, grid = _unsat_octomino()
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"0\n")
    box = {}

    def run():
        box["out"] = check_proof_v2(ProofSubmission(str(proof), "0" * 64, 1, 1), tile, grid,
                                    grid.contact("point"), 2, Tier.RECORD, encode_timeout_s=1)
    th = threading.Thread(target=run)
    th.start()
    th.join(120)
    assert box["out"].status is ProofStatus.RESOURCE_EXCEEDED
    assert "encoding F(S,2)" in box["out"].detail
