"""The enforced proof path (architecture §2.2/§13), end to end through the
real harness entrypoint.

Fail-closed rule: a shape outside Kaplan's census scores ONLY with a verified
`#PROOF` block; every proof failure rejects with its own code; a census shape
scores without a proof but a present-and-broken proof still rejects.

Real-checker tests use tests/util.checker_dir_for_tests: the vendored
drat-trim/lrat-check plus (off x86-64 Linux) a shim standing in for cake_lpr
so the record-tier control flow runs everywhere; the formally-verified
cake_lpr itself is exercised on the Linux CI/benchmark runner.
"""

import hashlib
import json
import lzma
import os
import subprocess
import sys

import pytest

from util import ROOT, census_baseline, checker_dir_for_tests, omino11_hc1, solve_drat

from heesch_verify.canonical import canonical_form
from heesch_verify.parse import parse_submission
from heesch_verify.proofgate import PROOF_MAX_PAYLOAD_BYTES, ProofCarryingGate
from heesch_verify.result import ErrorCode
from heesch_verify.witness import verify_witness

CENSUS_11 = omino11_hc1()  # Kaplan non-tiler (Hc=1, Hh=2), above the O<=10 census


def _run_harness(tmp_path, shape_text, files=(), checker_dir=None):
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True, exist_ok=True)
    (repo / "submission" / "best.heesch").write_text(shape_text, encoding="ascii")
    for name, data in files:
        (repo / "submission" / name).write_bytes(data)
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "HEESCH_CHECKER_DIR": str(checker_dir if checker_dir else tmp_path / "no-checkers"),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=600,
    )
    score_path = repo / "score.json"
    score = json.loads(score_path.read_text()) if score_path.exists() else None
    return proc, score


def _block(m, cnf, nv, nc, name, fmt, comp, payload):
    return f"#PROOF 1\nencoder heesch-encoder/v2 2 {m}\ncnf {cnf} {nv} {nc}\nfile {name} {fmt} {comp} {payload}\n"


@pytest.fixture(scope="module")
def unsat_proof(tmp_path_factory):
    """A real F(S,3) DRAT for the 11-omino (Hh = 2, so F(S,3) is UNSAT),
    produced by tools/prove.py's worker (pysat in a child process — the same
    path participants use; see util.solve_drat)."""
    pytest.importorskip("pysat.solvers")
    from heesch_encoder.multilevel.api import encode_multilevel

    out = verify_witness(CENSUS_11)
    sub = out.submission
    tile = frozenset(canonical_form(sub.cells, sub.grid, True))
    enc = encode_multilevel(tile, sub.grid, out.contact, 3)
    sat, drat = solve_drat(enc.dimacs, tmp_path_factory.mktemp("proof"))
    assert not sat
    return {"enc": enc, "drat": drat, "sha": hashlib.sha256(drat).hexdigest()}


# --- rejections that need no checkers ---------------------------------------

def test_inconclusive_without_proof_is_rejected(tmp_path):
    proc, score = _run_harness(tmp_path, CENSUS_11)
    assert proc.returncode != 0 and score is None
    assert "REJECTED: GATE_INCONCLUSIVE" in proc.stdout


def test_level_below_witness_is_inconsistent(tmp_path):
    text = CENSUS_11 + _block(1, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")])
    assert proc.returncode != 0 and score is None
    assert "REJECTED: PROOF_LEVEL_INCONSISTENT" in proc.stdout


def test_missing_checkers_reject_closed(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")])
    assert proc.returncode != 0 and score is None
    assert "REJECTED: CHECKER_UNAVAILABLE" in proc.stdout


def test_non_executable_checkers_reject_closed(tmp_path):
    """Audit 2026-08-19 Medium 7: present-but-unusable checker files (mode
    0644) must fail the preflight as CHECKER_UNAVAILABLE, not crash later
    with PermissionError inside subprocess.run."""
    d = tmp_path / "checkers-0644"
    d.mkdir()
    for n in ("drat-trim", "lrat-check", "cake_lpr"):
        (d / n).write_text("placeholder")
        (d / n).chmod(0o644)
    if os.access(d / "cake_lpr", os.X_OK):
        pytest.skip("X_OK is not meaningful on this platform")
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")], checker_dir=d)
    assert proc.returncode != 0 and score is None
    assert "REJECTED: CHECKER_UNAVAILABLE" in proc.stdout
    assert "Traceback" not in proc.stderr


def test_census_shape_with_broken_proof_still_rejects(tmp_path):
    baseline = census_baseline()
    text = baseline + _block(1, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")])
    assert proc.returncode != 0 and score is None
    assert "REJECTED: PROOF_LEVEL_INCONSISTENT" in proc.stdout


# --- proof-file handling (checkers present, gate run in-process) -------------

def _gate(tmp_path, text, files, **gate_kwargs):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    subdir = tmp_path / "submission"
    subdir.mkdir(exist_ok=True)
    for name, data in files:
        (subdir / name).write_bytes(data)
    out = verify_witness(text)
    return ProofCarryingGate(subdir, d, **gate_kwargs).check(out.submission, out)


def test_symlinked_proof_rejected(tmp_path):
    if os.name == "nt":
        pytest.skip("symlinks")
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    (tmp_path / "submission").mkdir()
    target = tmp_path / "outside.drat"
    target.write_bytes(b"0\n")
    (tmp_path / "submission" / "p.drat").symlink_to(target)
    v = _gate(tmp_path, text, [])
    assert v.code is ErrorCode.PROOF_FILE_INVALID


def test_missing_proof_file_rejected(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    assert _gate(tmp_path, text, []).code is ErrorCode.PROOF_FILE_INVALID


def test_payload_digest_mismatch_rejected(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    assert _gate(tmp_path, text, [("p.drat", b"0\n")]).code is ErrorCode.PROOF_FILE_DIGEST_MISMATCH


def test_xz_bomb_is_bounded(tmp_path, monkeypatch):
    # A few KB of xz that inflates past the payload cap: the gate must stop
    # at the cap, quickly, without materializing the whole payload.
    import dataclasses
    from heesch_verify.profile import STANDARD
    small = dataclasses.replace(STANDARD, proof_max_payload_bytes=4 * 1024 * 1024)
    bomb = lzma.compress(b"0" * (16 * 1024 * 1024), preset=9)
    assert len(bomb) < 64 * 1024
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat.xz", "drat", "xz", "b" * 64)
    v = _gate(tmp_path, text, [("p.drat.xz", bomb)], profile=small)
    assert v.code is ErrorCode.RESOURCE_EXCEEDED
    assert "decompressed" in v.detail


def test_xz_trailing_garbage_rejected(tmp_path):
    payload = b"0\n"
    data = lzma.compress(payload) + b"junk"
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat.xz", "drat", "xz",
                              hashlib.sha256(payload).hexdigest())
    v = _gate(tmp_path, text, [("p.drat.xz", data)])
    assert v.code is ErrorCode.PROOF_FILE_INVALID


def test_oversized_stored_proof_rejected(tmp_path, monkeypatch):
    import dataclasses
    from heesch_verify.profile import STANDARD
    small = dataclasses.replace(STANDARD, proof_max_stored_bytes=16)
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    v = _gate(tmp_path, text, [("p.drat", b"0\n" * 100)], profile=small)
    assert v.code is ErrorCode.RESOURCE_EXCEEDED


def test_out_of_band_rejected(tmp_path):
    text = CENSUS_11 + _block(8, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    v = _gate(tmp_path, text, [("p.drat", b"0\n")])
    assert v.code is ErrorCode.RESOURCE_EXCEEDED
    assert "band" in v.detail


# --- audit 2026-08-19 High 1: out-of-band band selection (architecture §13.9) ---

def _gate_with_band(tmp_path, text, files, band):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    subdir = tmp_path / "submission"
    subdir.mkdir(exist_ok=True)
    for name, data in files:
        (subdir / name).write_bytes(data)
    out = verify_witness(text)
    return ProofCarryingGate(subdir, d, band=band).check(out.submission, out)


def test_gate_band_param_narrow_rejects(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    v = _gate_with_band(tmp_path, text, [("p.drat", b"0\n")], band=((12, 2),))
    assert v.code is ErrorCode.RESOURCE_EXCEEDED
    assert "selected proof band" in v.detail


def test_gate_band_none_skips_the_band(tmp_path):
    """band=None (the `none` choice): m = 8 is past the standard band, yet the gate
    proceeds to the next cheap check (payload digest) instead of refusing."""
    text = CENSUS_11 + _block(8, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    v = _gate_with_band(tmp_path, text, [("p.drat", b"0\n")], band=None)
    assert v.code is ErrorCode.PROOF_FILE_DIGEST_MISMATCH


def test_named_bands():
    from heesch_verify.proofgate import HARNESS_PROOF_BAND, named_band
    from heesch_encoder.multilevel.api import feasibility_band
    assert named_band("harness") == HARNESS_PROOF_BAND
    assert named_band("encoder") == feasibility_band()
    assert named_band("none") is None
    with pytest.raises(ValueError):
        named_band("wide")


def test_check_proof_v2_enforce_band_false_reaches_the_encoder(tmp_path, monkeypatch):
    import heesch_encoder.multilevel.api as mlapi
    from heesch_encoder.proofcheck.pipeline import ProofSubmission, ProofStatus, Tier, check_proof_v2

    called = []

    def fake_encode(*a, **k):
        called.append(a[3])  # m
        raise RuntimeError("stop here")
    monkeypatch.setattr(mlapi, "encode_multilevel_stream", fake_encode)
    out = verify_witness(CENSUS_11)
    tile = frozenset(canonical_form(out.submission.cells, out.submission.grid, True))
    proof = tmp_path / "p.drat"
    proof.write_bytes(b"0\n")
    psub = ProofSubmission(str(proof), "0" * 64, 1, 1)
    # Enforced (default): m = 9 (past every band) never reaches the encoder.
    r = check_proof_v2(psub, tile, out.submission.grid, out.contact, 9, Tier.RECORD)
    assert r.status is ProofStatus.RESOURCE_EXCEEDED and called == []
    # Out of band: the encoder is invoked at m = 9.
    with pytest.raises(RuntimeError):
        check_proof_v2(psub, tile, out.submission.grid, out.contact, 9, Tier.RECORD, enforce_band=False)
    assert called == [9]


def test_wrong_cnf_digest_rejected_before_checkers(tmp_path, unsat_proof):
    text = CENSUS_11 + _block(3, "a" * 64, unsat_proof["enc"].num_vars,
                              unsat_proof["enc"].num_clauses, "p.drat", "drat", "none",
                              unsat_proof["sha"])
    v = _gate(tmp_path, text, [("p.drat", unsat_proof["drat"])])
    assert v.code is ErrorCode.PROOF_CNF_DIGEST_MISMATCH


def test_sat_model_is_not_a_proof(tmp_path, unsat_proof):
    enc = unsat_proof["enc"]
    fake = b"v 1 -2 3 0\n"
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat",
                              "none", hashlib.sha256(fake).hexdigest())
    v = _gate(tmp_path, text, [("p.drat", fake)])
    assert v.code is ErrorCode.GATE_PROOF_INVALID


# --- the positive path -------------------------------------------------------

def test_real_proof_scores_through_the_harness(tmp_path, unsat_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    xz = lzma.compress(unsat_proof["drat"], preset=6)
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "proof.drat.xz",
                              "drat", "xz", unsat_proof["sha"])
    proc, score = _run_harness(tmp_path, text, files=[("proof.drat.xz", xz)], checker_dir=d)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = score["metrics"]
    assert score["score"] == 1.0
    assert m["non_tiler_evidence"] == "proof"
    assert m["tier"] == "lower_bound"   # m = hh + 2: non-tiler certified, not exact
    assert m["gate_tier"] == "nontiler_proof"
    assert m["gate_detail"] == "nontiler:proof:v2:m=3"
    assert m["proof_m"] == 3 and m["proof_status"] == "VERIFIED"
    assert m["proof_cnf_digest"] == enc.digest and m["proof_sha256"] == unsat_proof["sha"]
    assert m["proof_checkers"] == ["cake_lpr", "drat-trim"]
    # m = 3 = hh + 2: non-tiler certified, hh NOT pinned exactly (Hh in {1,2}).
    assert m["hh_exact"] is False and m["exact"] is False
    assert m["record_eligible"] is False and m["record_exact"] is False  # hc = 1 < 5
    assert "checked UNSAT proof of F(S,3)" in m["verified_claim"]
    # Provenance: declared format AND what the bytes actually were.
    assert m["proof_format"] == "drat" and m["proof_format_detected"] == "drat-text"


def test_declared_format_must_match_detected(tmp_path, unsat_proof):
    """Audit 2026-08-19 Medium 4: an LRAT filed under a .drat name and declared
    `drat` used to be checked down the LRAT route and recorded as format drat.
    Now the declaration must agree with the sniffed bytes, and the mismatch
    rejects before any checker runs."""
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    # Convert the DRAT to an LRAT with drat-trim (the same converter the gate uses).
    work = tmp_path / "conv"
    work.mkdir()
    (work / "f.cnf").write_bytes(enc.dimacs)
    (work / "p.drat").write_bytes(unsat_proof["drat"])
    subprocess.run([str(d / "drat-trim"), str(work / "f.cnf"), str(work / "p.drat"),
                    "-L", str(work / "p.lrat")], capture_output=True, check=False)
    lrat = (work / "p.lrat").read_bytes()
    assert lrat, "drat-trim did not emit an LRAT"
    sha = hashlib.sha256(lrat).hexdigest()
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "proof.drat",
                              "drat", "none", sha)
    proc, score = _run_harness(tmp_path, text, files=[("proof.drat", lrat)], checker_dir=d)
    assert proc.returncode != 0 and score is None
    assert "REJECTED: GATE_PROOF_INVALID" in proc.stdout
    assert "declared format 'drat' but the file is lrat-text" in proc.stdout
    # And the honest declaration of the same bytes verifies.
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "proof.lrat",
                              "lrat", "none", sha)
    proc, score = _run_harness(tmp_path, text, files=[("proof.lrat", lrat)], checker_dir=d)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = score["metrics"]
    assert m["proof_format"] == "lrat" and m["proof_format_detected"] == "lrat-text"
    assert m["proof_checkers"] == ["cake_lpr", "lrat-check"]


def test_tampered_proof_is_rejected(tmp_path, unsat_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    # A syntactically fine DRAT that asserts an unjustified unit and then the
    # empty clause: drat-trim must say NOT VERIFIED.
    tampered = b"1 0\n0\n"
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat",
                              "none", hashlib.sha256(tampered).hexdigest())
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", tampered)], checker_dir=d)
    assert proc.returncode != 0 and score is None
    assert "REJECTED: GATE_PROOF_INVALID" in proc.stdout or "REJECTED: PROOF_TRUNCATED" in proc.stdout


def test_checker_cap_is_the_checkers_own_budget(tmp_path, unsat_proof):
    """Audit 2026-08-19 Medium 5: a slow checker is bounded by CheckBudget
    (per-checker cap / overall deadline) and reported as a checker resource
    limit — not by the 600 s encode guard, which no longer spans the checkers."""
    import stat as stat_mod
    from heesch_encoder.proofcheck.checkers import CheckBudget

    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    slow = d / "cake_lpr"
    slow.write_text("#!/bin/sh\nsleep 5\necho 's VERIFIED UNSAT'\n")
    slow.chmod(slow.stat().st_mode | stat_mod.S_IXUSR)
    enc = unsat_proof["enc"]
    subdir = tmp_path / "submission"
    subdir.mkdir(exist_ok=True)
    (subdir / "p.drat").write_bytes(unsat_proof["drat"])
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat",
                              "none", unsat_proof["sha"])
    out = verify_witness(text)
    import heesch_verify.proofgate as pg
    assert pg.ENCODE_TIMEOUT_S == 600  # the encode guard is not what fires here
    v = ProofCarryingGate(subdir, d, CheckBudget(per_checker={"cake_lpr": 1})).check(out.submission, out)
    assert v.code is ErrorCode.RESOURCE_EXCEEDED
    assert "checker resource limit" in v.detail and "cake_lpr" in v.detail
    assert "encoding" not in v.detail


def test_cli_check_proof_matches_harness(tmp_path, unsat_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    sub = tmp_path / "submission"
    sub.mkdir(exist_ok=True)
    (sub / "proof.drat").write_bytes(unsat_proof["drat"])
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "proof.drat",
                              "drat", "none", unsat_proof["sha"])
    (sub / "best.heesch").write_text(text, encoding="ascii")
    env = {**os.environ, "HEESCH_CHECKER_DIR": str(d), "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "heesch_verify", str(sub / "best.heesch"), "--check-proof"],
                          capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["proof"]["status"] == "VERIFIED" and out["proof"]["m"] == 3
    assert out["proof"]["band"] == "profile" and out["proof"]["profile"] in ("standard", "record")
    # --band harness / record / encoder / none verify the same proof and record the band used.
    for band in ("harness", "record", "encoder", "none"):
        proc = subprocess.run([sys.executable, "-m", "heesch_verify", str(sub / "best.heesch"),
                               "--check-proof", "--band", band],
                              capture_output=True, text=True, env=env, timeout=600)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        out = json.loads(proc.stdout)
        assert out["proof"]["status"] == "VERIFIED" and out["proof"]["band"] == band


def test_census_shape_plus_exact_proof(tmp_path):
    """A census shape may ALSO carry a proof: with m = hh + 1 the value is
    exact and both evidences are recorded (census+proof)."""
    pytest.importorskip("pysat.solvers")
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    from heesch_encoder.multilevel.api import encode_multilevel

    text = sorted((ROOT / "tests" / "corpus").glob("omino8-nontiler-*-hc1hh1.txt"))[0].read_text()
    out = verify_witness(text)
    sub = out.submission
    tile = frozenset(canonical_form(sub.cells, sub.grid, True))
    enc = encode_multilevel(tile, sub.grid, out.contact, 2)
    sat, drat = solve_drat(enc.dimacs, tmp_path)
    assert not sat
    sha = hashlib.sha256(drat).hexdigest()
    full = text + _block(2, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat", "none", sha)
    proc, score = _run_harness(tmp_path, full, files=[("p.drat", drat)], checker_dir=d)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = score["metrics"]
    assert m["non_tiler_evidence"] == "proof" and m["tier"] == "exact_proof"
    assert m["gate_detail"] == "nontiler:census+proof:v2:m=2"
    assert (m["census_hc"], m["census_hh"]) == (1, 1)
    assert m["hh_exact"] is True and m["exact"] is True
    assert m["record_eligible"] is False and m["record_exact"] is False  # exact, but hc = 1 < 5
    assert "Hc = Hh = 1 exactly" in m["verified_claim"]


def test_materialize_write_failure_is_structured(tmp_path, monkeypatch):
    # Write-side OSError during proof materialisation (ENOSPC on scratch mid
    # decompression) must reject with a code, never escape as a traceback
    # (2026-08-20 re-verification, item 3a).
    import errno

    import heesch_verify.proofgate as pg

    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    for err, code in ((errno.ENOSPC, ErrorCode.RESOURCE_EXCEEDED),
                      (getattr(errno, "EIO", errno.EACCES), ErrorCode.PROOF_FILE_INVALID)):
        def boom(*a, _err=err, **k):
            raise OSError(_err, os.strerror(_err))

        monkeypatch.setattr(pg, "materialize_proof", boom)
        v = _gate(tmp_path, text, [("p.drat", b"0\n")])
        assert v.code is code
        assert "materializing proof failed" in v.detail
