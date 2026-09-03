"""2026-09-03 capacity rebalance: the whole family of record-scale resource
guards, fixed together after production week 1 (21 heap + 6 stack + 1 xz
rejections of drat-trim-VERIFIED proofs).

Covers: joint cake_lpr heap+stack sizing, bounded checker-output windows,
xz memlimit classification, the converted-LRAT cap, and the deadline
checkpoints in materialization and the core scan."""

import io
import lzma
import os
import pathlib
import tempfile

import pytest

from conftest import ROOT  # noqa: F401

from heesch_encoder.proofcheck import checkers as ck
from heesch_verify import proofgate as pg
from heesch_verify.result import ErrorCode


# --- joint heap + stack sizing ---------------------------------------------

def test_stack_scales_with_heap():
    assert ck.cake_lpr_stack_mb(98304) == 8192      # record cap -> 8 GB stack
    assert ck.cake_lpr_stack_mb(12288) == 1024      # standard cap -> old 1 GB
    assert ck.cake_lpr_stack_mb(4096) == ck.CAKE_LPR_STACK_MB_MIN
    assert ck.cake_lpr_stack_mb(0) == ck.CAKE_LPR_STACK_MB_MIN


def test_heap_plus_stack_fits_the_85_percent_budget():
    # The 12/13 factor exists so heap + heap/12 <= 0.85 * MemAvailable: the
    # CakeML runtime reserves both in ONE contiguous malloc.
    for avail_mb in (32_768, 65_536, 131_072, 262_144):
        budget = int(avail_mb * 0.85)
        heap = min(10**9, budget * 12 // 13)        # uncapped branch of the formula
        stack = ck.cake_lpr_stack_mb(heap)
        assert heap + stack <= budget + ck.CAKE_LPR_STACK_MB_MIN


def test_heap_env_override_still_exact(monkeypatch):
    monkeypatch.setenv("HEESCH_CAKE_HEAP_MB", "6000")
    assert ck.cake_lpr_heap_mb() == 6000


# --- bounded output windows -------------------------------------------------

def _tmp_with(data: bytes):
    fh = tempfile.TemporaryFile()
    fh.write(data)
    return fh


def test_windows_small_stream_is_verbatim():
    with _tmp_with(b"c parsing\ns VERIFIED\n") as fh:
        assert ck._windows(fh) == "c parsing\ns VERIFIED\n"


def test_windows_tail_carries_the_verdict():
    filler = b"c progress line\n" * 200_000          # ~3.2 MB >> head+tail
    with _tmp_with(filler + b"s VERIFIED\n") as fh:
        out = ck._windows(fh)
        assert out.endswith("s VERIFIED\n")
        assert len(out) <= ck._OUT_HEAD + ck._OUT_TAIL + 1


def test_windows_never_fabricates_a_line_at_the_cut():
    # A verdict string straddling the tail cut must not surface as a
    # line-anchored verdict: the partial leading line is dropped.
    data = b"x" * (ck._OUT_HEAD + 10) + b"s VERIFIED\n" + b"y" * (ck._OUT_TAIL + 10) + b"z end\n"
    with _tmp_with(data) as fh:
        lines = [ln.strip() for ln in ck._windows(fh).split("\n")]
        assert "s VERIFIED" not in lines


# --- xz memlimit is a RESOURCE outcome --------------------------------------

def test_xz_memlimit_classified_as_resource(monkeypatch, tmp_path):
    payload = lzma.compress(b"hello proof\n" * 64, preset=6)
    src = tmp_path / "p.lrat.xz"; src.write_bytes(payload)
    monkeypatch.setattr(pg, "_XZ_MEMLIMIT", 1024)    # far below any real dict
    with pytest.raises(pg.ProofFileError) as ei:
        pg.materialize_proof(src, tmp_path / "out.lrat", "xz")
    assert ei.value.code is ErrorCode.RESOURCE_EXCEEDED
    assert "memory usage limit" in ei.value.message.lower()


def test_xz_garbage_still_invalid(tmp_path):
    src = tmp_path / "p.lrat.xz"; src.write_bytes(b"\xfd7zXZ\x00not really xz")
    with pytest.raises(pg.ProofFileError) as ei:
        pg.materialize_proof(src, tmp_path / "out.lrat", "xz")
    assert ei.value.code is ErrorCode.PROOF_FILE_INVALID


# --- deadline checkpoints ----------------------------------------------------

def test_materialize_checkpoint_rejects_on_exhausted_deadline(tmp_path):
    src = tmp_path / "p.lrat"
    src.write_bytes(b"a" * (65 * 1024 * 1024))       # 65 chunks > the 64-chunk stride
    budget = ck.CheckBudget(deadline_seconds=0.0)
    with pytest.raises(pg.ProofFileError) as ei:
        pg.materialize_proof(src, tmp_path / "out.lrat", "none",
                             max_stored_bytes=1 << 30, max_payload_bytes=1 << 30,
                             budget=budget)
    assert ei.value.code is ErrorCode.RESOURCE_EXCEEDED
    assert "materializing" in ei.value.message


def test_core_scan_checkpoint_rejects_on_exhausted_deadline(tmp_path):
    from heesch_encoder.proofcheck import core as core_mod

    cnf = tmp_path / "f.cnf"
    with open(cnf, "w") as fh:
        fh.write("p cnf 3 1000001\n")
        for _ in range(1_000_001):
            fh.write("1 2 3 0\n")
    budget = ck.CheckBudget(deadline_seconds=0.0)
    with pytest.raises(core_mod.CoreError) as ei:
        core_mod.check_and_write_core(["9 9 0"], str(cnf), 3,
                                      str(tmp_path / "core.cnf"), budget=budget)
    assert ei.value.code == "RESOURCE_EXCEEDED"
    assert "deadline" in ei.value.message


# --- converted-LRAT cap ------------------------------------------------------

def test_converted_lrat_over_cap_is_resource_not_cake_time(tmp_path, monkeypatch):
    from heesch_encoder.multilevel.api import encode_multilevel
    from heesch_encoder.proofcheck.pipeline import (
        ProofStatus, ProofSubmission, Tier, check_proof_v2)
    from heesch_verify.parse import parse_submission

    corpus = sorted((pathlib.Path(ROOT) / "tests" / "corpus").glob(
        "omino8-nontiler-*-hc1hh1.txt"))
    sub_parsed = parse_submission(corpus[-1].read_text(encoding="ascii"))
    tile, grid = frozenset(sub_parsed.cells), sub_parsed.grid
    contact = grid.contact("point")
    enc = encode_multilevel(tile, grid, contact, 2)

    proof = tmp_path / "p.drat"
    proof.write_bytes(b"1 2 0\n0\n")

    cap = 4096
    spawned = []

    def fake_drat_trim(cnf, prf, emit_lrat=None, **kw):
        with open(emit_lrat, "wb") as fh:
            fh.truncate(cap + 1)                     # sparse: st_size > cap
        return ck.CheckResult("drat-trim", ck.CheckStatus.VERIFIED, 0.0)

    def fake_cake(*a, **k):
        spawned.append("cake_lpr")
        return ck.CheckResult("cake_lpr", ck.CheckStatus.VERIFIED, 0.0)

    monkeypatch.setattr(ck, "drat_trim", fake_drat_trim)
    monkeypatch.setattr(ck, "cake_lpr", fake_cake)

    sub = ProofSubmission(str(proof), enc.digest, enc.num_vars, enc.num_clauses)
    out = check_proof_v2(sub, tile, grid, contact, 2, Tier.RECORD,
                         max_proof_bytes=cap)
    assert out.status is ProofStatus.RESOURCE_EXCEEDED
    assert "converted LRAT" in out.detail
    assert spawned == []                             # cake_lpr never ran
