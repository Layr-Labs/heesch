"""Core-CNF proof checking (architecture §13.3 step 5b, proofcheck/core.py).

Soundness rests on ONE check: every clause of the submitted core is exactly
a clause of the regenerated formula F. These tests attack that check
directly — a clause not in F, a flipped literal, a near-miss, an empty
clause when F has none, a tautology, a duplicate-literal spelling, comments
and headers, a fabricated id, a core count mismatch — and confirm the
positive path (a real core + core-relative LRAT scores through the harness).
Proof generation goes through tools/prove.py's helpers, i.e. the participant
path."""

import hashlib
import importlib.util
import json
import lzma
import os
import subprocess
import sys

import pytest

from util import ROOT, census_baseline, checker_dir_for_tests, omino11_hc1, solve_drat

from heesch_encoder.proofcheck import core as core_mod
from heesch_encoder.proofcheck.pipeline import ProofStatus, ProofSubmission, Tier, check_proof_v2
from heesch_verify.canonical import canonical_form
from heesch_verify.proofgate import ProofCarryingGate
from heesch_verify.result import ErrorCode
from heesch_verify.witness import verify_witness

_spec = importlib.util.spec_from_file_location("prove", ROOT / "tools" / "prove.py")
prove = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prove)

BASELINE = census_baseline()


# ---------------------------------------------------------------- unit level

def _write(p, text):
    p.write_text(text, encoding="ascii")
    return str(p)


def test_canonical_clause_line_matches_encoder_order():
    # (abs, negative-first) is the encoder's frozen literal order.
    assert core_mod.canonical_clause_line([3, -1, 2, 1]) == "-1 1 2 3 0"
    assert core_mod.canonical_clause_line([2, 2, -5]) == "2 -5 0"
    assert core_mod.canonical_clause_line([]) == "0"


@pytest.mark.parametrize("bad,code", [
    ("1 -1 0\n", "GATE_PROOF_INVALID"),        # tautology
    ("c comment\n1 2 0\n", "GATE_PROOF_INVALID"),
    ("p cnf 3 1\n1 2 0\n", "GATE_PROOF_INVALID"),
    ("1 2\n", "GATE_PROOF_INVALID"),           # unterminated
    ("1 0 2 0\n", "GATE_PROOF_INVALID"),       # embedded 0
    ("x 2 0\n", "GATE_PROOF_INVALID"),
    ("", "GATE_PROOF_INVALID"),
])
def test_core_grammar_rejections(tmp_path, bad, code):
    with pytest.raises(core_mod.CoreError) as ei:
        core_mod.parse_core_file(_write(tmp_path / "c.txt", bad))
    assert ei.value.code == code


@pytest.mark.parametrize("raw", [
    b"\xff1 2 0\n",                 # audit 2026-08-19 Medium 3: leading 0xff
    b"1 2 0\n\x00",                  # NUL is not ASCII-printable but decodes; grammar rejects
    "\ufeff1 2 0\n".encode("utf-8"),  # UTF-8 BOM
    "1 2 0 \u2014\n".encode("utf-8"),  # non-ASCII token
])
def test_non_ascii_core_is_structured_rejection(tmp_path, raw):
    p = tmp_path / "c.txt"
    p.write_bytes(raw)
    with pytest.raises(core_mod.CoreError) as ei:
        core_mod.parse_core_file(str(p))
    assert ei.value.code == "GATE_PROOF_INVALID"


def test_unreadable_core_is_structured_rejection(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text("1 2 0\n", encoding="ascii")
    p.chmod(0)
    if os.access(p, os.R_OK):
        pytest.skip("permission bits not enforced here (root / Windows)")
    try:
        with pytest.raises(core_mod.CoreError) as ei:
            core_mod.parse_core_file(str(p))
        assert ei.value.code == "GATE_PROOF_INVALID"
        assert "unreadable" in ei.value.message
    finally:
        p.chmod(0o644)


def test_membership_is_exact(tmp_path):
    F = _write(tmp_path / "F.cnf", "p cnf 4 4\n1 2 0\n-1 3 0\n-2 -3 4 0\n2 3 0\n")
    ok = core_mod.parse_core_file(_write(tmp_path / "c.txt", "2 1 0\n4 -3 -2 0\n"))
    res = core_mod.check_and_write_core(ok, F, 4, str(tmp_path / "core.cnf"))
    assert res.num_clauses == 2
    # The checker file is F's own bytes, submitter order, header names F's vars.
    assert (tmp_path / "core.cnf").read_text() == "p cnf 4 2\n1 2 0\n-2 -3 4 0\n"
    for bad in ["1 -2 0\n",       # flipped literal
                "1 2 3 0\n",      # superset (weaker clause) is NOT a clause of F
                "1 0\n",          # subset (stronger clause) is NOT a clause of F
                "0\n",            # empty clause when F has none
                "-1 -3 0\n",      # near-miss
                "1 2 0\n5 0\n"]:  # one good, one bad
        lines = core_mod.parse_core_file(_write(tmp_path / "c.txt", bad))
        with pytest.raises(core_mod.CoreError) as ei:
            core_mod.check_and_write_core(lines, F, 4, str(tmp_path / "core.cnf"))
        assert ei.value.code == "GATE_PROOF_INVALID"
        assert "not clauses of the regenerated formula" in ei.value.message


def test_duplicate_literal_spelling_maps_to_the_same_clause(tmp_path):
    F = _write(tmp_path / "F.cnf", "p cnf 2 1\n1 2 0\n")
    lines = core_mod.parse_core_file(_write(tmp_path / "c.txt", "2 1 1 0\n"))
    core_mod.check_and_write_core(lines, F, 2, str(tmp_path / "core.cnf"))
    assert (tmp_path / "core.cnf").read_text() == "p cnf 2 1\n1 2 0\n"


def test_core_size_caps(tmp_path, monkeypatch):
    monkeypatch.setattr(core_mod, "CORE_MAX_CLAUSES", 2)
    with pytest.raises(core_mod.CoreError) as ei:
        core_mod.parse_core_file(_write(tmp_path / "c.txt", "1 0\n2 0\n3 0\n"))
    assert ei.value.code == "RESOURCE_EXCEEDED"


# ------------------------------------------------------------ pipeline level

@pytest.fixture(scope="module")
def baseline_core_proof(tmp_path_factory):
    """Real F(S,2) for the census heptomino: DRAT via the participant worker,
    then core list + core-relative LRAT via prove.make_core_lrat."""
    pytest.importorskip("pysat.solvers")
    drat_trim = ROOT / "tools" / "bin" / "drat-trim"
    if not drat_trim.exists():
        pytest.skip("tools/bin/drat-trim not built")
    from heesch_encoder.multilevel.api import encode_multilevel_stream

    work = tmp_path_factory.mktemp("core")
    out = verify_witness(BASELINE)
    sub = out.submission
    tile = frozenset(canonical_form(sub.cells, sub.grid, True))
    enc = encode_multilevel_stream(tile, sub.grid, out.contact, 2, work / "formula.cnf")
    sat, drat = solve_drat(work / "formula.cnf", work)
    assert not sat
    (work / "proof.drat").write_bytes(drat)
    core_txt, core_lrat, n_core, n_formula = prove.make_core_lrat(
        work / "formula.cnf", work / "proof.drat", drat_trim, work)
    assert 0 < n_core < n_formula == enc.num_clauses
    return {"enc": enc, "core": core_txt.read_bytes(), "lrat": core_lrat.read_bytes(),
            "n_core": n_core, "grid": sub.grid, "tile": tile, "contact": out.contact}


def _run_v2(tmp_path, bp, core_bytes, lrat_bytes, n_core=None, checker_dir=None):
    (tmp_path / "p.lrat").write_bytes(lrat_bytes)
    (tmp_path / "c.txt").write_bytes(core_bytes)
    enc = bp["enc"]
    sub = ProofSubmission(str(tmp_path / "p.lrat"), enc.digest, enc.num_vars, enc.num_clauses,
                          claimed_core_clauses=(bp["n_core"] if n_core is None else n_core))
    return check_proof_v2(sub, bp["tile"], bp["grid"], bp["contact"], 2, Tier.RECORD,
                          bin_dir=checker_dir, core_path=str(tmp_path / "c.txt"))


def test_core_proof_verifies_at_record_tier(tmp_path, baseline_core_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("checkers not built")
    out = _run_v2(tmp_path, baseline_core_proof, baseline_core_proof["core"],
                  baseline_core_proof["lrat"], checker_dir=d)
    assert out.status is ProofStatus.VERIFIED, out.detail
    assert out.core_clauses == baseline_core_proof["n_core"]
    assert sorted(r.checker for r in out.checker_results) == ["cake_lpr", "lrat-check"]


def test_core_with_foreign_clause_is_rejected_before_checkers(tmp_path, baseline_core_proof, monkeypatch):
    calls = []
    from heesch_encoder.proofcheck import checkers as ck
    monkeypatch.setattr(ck, "cake_lpr", lambda *a, **k: calls.append("cake") or ck.CheckResult("cake_lpr", ck.CheckStatus.VERIFIED, 0.0))
    monkeypatch.setattr(ck, "lrat_check", lambda *a, **k: calls.append("lrat") or ck.CheckResult("lrat-check", ck.CheckStatus.VERIFIED, 0.0))
    # Append a clause that is NOT in F (a unit that would make anything UNSAT):
    # even with checkers monkeypatched to say VERIFIED, the pipeline must
    # reject on membership alone.
    bad = baseline_core_proof["core"] + b"1 0\n"
    out = _run_v2(tmp_path, baseline_core_proof, bad, baseline_core_proof["lrat"],
                  n_core=baseline_core_proof["n_core"] + 1)
    assert out.status is ProofStatus.GATE_PROOF_INVALID
    assert "not clauses of the regenerated formula" in out.detail
    assert calls == []


def test_non_ascii_core_rejected_through_pipeline(tmp_path, baseline_core_proof):
    """Audit 2026-08-19 Medium 3 (pipeline level): a core beginning with 0xff
    is GATE_PROOF_INVALID, not a UnicodeDecodeError."""
    out = _run_v2(tmp_path, baseline_core_proof, b"\xff" + baseline_core_proof["core"],
                  baseline_core_proof["lrat"])
    assert out.status is ProofStatus.GATE_PROOF_INVALID
    assert "ASCII" in out.detail


def test_core_count_mismatch_rejected(tmp_path, baseline_core_proof):
    out = _run_v2(tmp_path, baseline_core_proof, baseline_core_proof["core"],
                  baseline_core_proof["lrat"], n_core=baseline_core_proof["n_core"] + 1)
    assert out.status is ProofStatus.PROOF_HEADER_MISMATCH


def test_core_requires_lrat(tmp_path, baseline_core_proof):
    drat = b"1 2 0\n0\n"
    out = _run_v2(tmp_path, baseline_core_proof, baseline_core_proof["core"], drat)
    assert out.status is ProofStatus.GATE_PROOF_INVALID
    assert "only valid with an LRAT" in out.detail


def test_tampered_core_lrat_not_verified(tmp_path, baseline_core_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("checkers not built")
    # Drop the proof's last lemma (the empty clause): must NOT verify.
    lines = baseline_core_proof["lrat"].split(b"\n")
    tampered = b"\n".join(lines[:-2]) + b"\n"
    out = _run_v2(tmp_path, baseline_core_proof, baseline_core_proof["core"], tampered, checker_dir=d)
    assert out.status is not ProofStatus.VERIFIED


# ------------------------------------------------------------- harness level

def test_core_submission_scores_through_harness(tmp_path, baseline_core_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("checkers not built")
    enc = baseline_core_proof["enc"]
    core_xz = lzma.compress(baseline_core_proof["core"])
    lrat_xz = lzma.compress(baseline_core_proof["lrat"])
    block = (f"#PROOF 1\nencoder heesch-encoder/v2 2 2\ncnf {enc.digest} {enc.num_vars} {enc.num_clauses}\n"
             f"file proof.lrat.xz lrat xz {hashlib.sha256(baseline_core_proof['lrat']).hexdigest()}\n"
             f"core core.txt.xz xz {hashlib.sha256(baseline_core_proof['core']).hexdigest()} "
             f"{baseline_core_proof['n_core']}\n")
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text(BASELINE + block, encoding="ascii")
    (repo / "submission" / "proof.lrat.xz").write_bytes(lrat_xz)
    (repo / "submission" / "core.txt.xz").write_bytes(core_xz)
    env = {"PYTHONHASHSEED": "0", "PYTHONPATH": str(ROOT),
           "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "HEESCH_CHECKER_DIR": str(d)}
    proc = subprocess.run([sys.executable, "-P", "-m", "harness.verify"], cwd=repo, env=env,
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = json.loads((repo / "score.json").read_text())["metrics"]
    assert m["non_tiler_evidence"] == "proof" and m["exact"] is True
    assert m["proof_core_clauses"] == baseline_core_proof["n_core"]
    assert m["proof_checkers"] == ["cake_lpr", "lrat-check"]
