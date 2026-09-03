"""Resource profiles (heesch_verify/profile.py, Plan 3): the machine selects
the profile, every budget is monotone from standard to record, the record band
admits the Hc=5/Hh=6 and Hc=6/Hh=7 certificates for record-candidate sizes, and
the standard band is unchanged."""

import pytest

from heesch_verify import profile as pf
from heesch_verify.proofgate import HARNESS_PROOF_BAND, ProofCarryingGate, named_band


def test_standard_is_the_historical_band_and_budgets():
    assert pf.STANDARD.harness_band == ((12, 6), (20, 5), (50, 3), (100, 2)) == HARNESS_PROOF_BAND
    assert pf.STANDARD.encode_timeout_s == 600
    assert pf.STANDARD.checker_deadline_s == 1500
    assert pf.STANDARD.checker_caps == {"drat-trim": 600.0, "cake_lpr": 900.0, "lrat-check": 300.0}


def test_record_admits_the_record_certificates():
    r = pf.RECORD
    # F(S,7) to 20 cells: every Hc = 5 certificate (Hh = 5 or 6) and the
    # Hc = 6, Hh = 6 case, for the sizes of every known Hc = 4 shape —
    # validated end-to-end on the runner (16-hex F(S,7): cake_lpr 318 s,
    # core LRAT 62 MB xz).
    for cells, m in [(11, 7), (12, 7), (13, 7), (16, 7), (20, 7), (11, 6), (20, 5)]:
        assert r.in_band(cells, m), (cells, m)
    # m = 8 measured OUT (2026-08-20): the 16-hex core LRAT is 2.2 GB xz and
    # cake_lpr needs 3.9 h — beyond the stored cap and checker cap. The
    # Hc = 6, Hh = 7 certificate goes through the maintainer path (§13.9).
    for cells, m in [(12, 8), (16, 8), (20, 8)]:
        assert not r.in_band(cells, m), (cells, m)
    assert not r.in_band(21, 7)
    # The standard (8 GB / 30 min) profile does NOT admit them — explicit.
    for cells, m in [(11, 7), (12, 8), (13, 7), (20, 7)]:
        assert not pf.STANDARD.in_band(cells, m), (cells, m)


def test_record_budgets_dominate_standard():
    s, r = pf.STANDARD, pf.RECORD
    assert r.encode_timeout_s >= s.encode_timeout_s
    assert r.checker_deadline_s >= s.checker_deadline_s
    assert all(r.checker_caps[k] >= s.checker_caps[k] for k in s.checker_caps)
    for f in ("proof_max_stored_bytes", "proof_max_payload_bytes", "max_proof_bytes",
              "core_max_clauses", "core_max_bytes", "cake_heap_max_mb", "min_scratch_bytes"):
        assert getattr(r, f) >= getattr(s, f), f
    # Every row of the standard band is admitted by the record band.
    for cells, max_m in s.harness_band:
        assert r.in_band(cells, max_m)
    # The record profile's stored cap still fits benchmark.json's maxSubmissionBytes
    # with the shape (<= 2 MiB) and a core list of the same cap.
    import json, pathlib
    cap = json.loads((pathlib.Path(__file__).resolve().parents[1] / "benchmark.json").read_text())["maxSubmissionBytes"]
    assert 2 * r.proof_max_stored_bytes + 2 * 1024 * 1024 <= cap


def test_detect_selects_by_machine(monkeypatch):
    monkeypatch.setattr(pf, "mem_available_bytes", lambda: 128 * pf.GiB)
    monkeypatch.setattr(pf, "scratch_free_bytes", lambda p=None: 200 * pf.GiB)
    assert pf.detect() is pf.RECORD
    monkeypatch.setattr(pf, "mem_available_bytes", lambda: 7 * pf.GiB)
    assert pf.detect() is pf.STANDARD
    monkeypatch.setattr(pf, "mem_available_bytes", lambda: 128 * pf.GiB)
    monkeypatch.setattr(pf, "scratch_free_bytes", lambda p=None: 20 * pf.GiB)
    assert pf.detect() is pf.STANDARD       # memory alone is not enough
    monkeypatch.setattr(pf, "mem_available_bytes", lambda: None)
    monkeypatch.setattr(pf, "scratch_free_bytes", lambda p=None: 200 * pf.GiB)
    assert pf.detect() is pf.STANDARD       # unknown machine -> the narrow profile


def test_by_name():
    assert pf.by_name("record") is pf.RECORD and pf.by_name("standard") is pf.STANDARD
    assert pf.by_name("auto") in (pf.RECORD, pf.STANDARD)
    with pytest.raises(ValueError):
        pf.by_name("huge")
    assert named_band("record") == pf.RECORD.harness_band


def test_gate_uses_its_profile_band(tmp_path):
    from heesch_verify.result import ErrorCode
    from util import omino11_hc1
    from heesch_verify.witness import verify_witness

    text = omino11_hc1() + "#PROOF 1\nencoder heesch-encoder/v2 2 7\ncnf " + "a" * 64 + " 1 1\nfile p.drat drat none " + "b" * 64 + "\n"
    subdir = tmp_path / "submission"
    subdir.mkdir()
    (subdir / "p.drat").write_bytes(b"0\n")
    out = verify_witness(text)
    chk = tmp_path / "no-checkers"
    # standard: m = 7 at 11 cells is outside the band — but the checker
    # preflight comes first, so use a fake executable checker dir.
    from heesch_encoder.proofcheck.checkers import checker_path

    chk.mkdir()
    for n in ("drat-trim", "lrat-check", "cake_lpr"):
        exe = checker_path(n, chk)  # .exe suffix on Windows
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o755)
    v = ProofCarryingGate(subdir, chk, profile=pf.STANDARD).check(out.submission, out)
    assert v.code is ErrorCode.RESOURCE_EXCEEDED and "standard profile" in v.detail
    # record: m = 7 passes the band and proceeds to the next cheap check
    # (payload digest mismatch) — the certificate is admitted in-harness.
    # (min_scratch_bytes=0: this test machine's disk is not the record runner's;
    # the scratch gate itself is exercised below.)
    import dataclasses
    record_here = dataclasses.replace(pf.RECORD, min_scratch_bytes=0)
    v = ProofCarryingGate(subdir, chk, profile=record_here).check(out.submission, out)
    assert v.code is ErrorCode.PROOF_FILE_DIGEST_MISMATCH, v.detail
    # Scratch gate: a profile demanding more free scratch than any disk has
    # refuses cleanly before materialising anything.
    huge = dataclasses.replace(pf.STANDARD, min_scratch_bytes=1 << 60,
                               harness_band=((12, 8),))
    v = ProofCarryingGate(subdir, chk, profile=huge).check(out.submission, out)
    assert v.code is ErrorCode.RESOURCE_EXCEEDED and "scratch" in v.detail
