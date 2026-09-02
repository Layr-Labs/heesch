"""Review finding 3: per-checker line-anchored verdict matching.

The six-way matrix (each checker x pass/fail) plus the traps: drat-trim's
non-verdict "c VERIFIED derivation" progress line must not satisfy any
checker, and NOT VERIFIED overrides everything."""

import os
import subprocess
import types

import pytest

from conftest import ROOT  # noqa: F401

from heesch_encoder.proofcheck import checkers as ck


def _fake_run(stdout):
    def run(cmd, *args, **kwargs):
        # Tolerant of _run's kwargs (capture_output, text, timeout, and the
        # audit F3/F4 additions stdin=DEVNULL, errors="replace").
        return types.SimpleNamespace(stdout=stdout, stderr="", returncode=0)
    return run


def _fake_exe(path):
    """A regular, executable placeholder (what the preflight/spawn predicate
    requires); subprocess.run is patched so it is never actually exec'd."""
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def with_binary(monkeypatch, tmp_path):
    """Put executable placeholders for all checkers in place so _run reaches
    verdict parsing."""
    monkeypatch.setattr(ck, "_BIN", tmp_path)
    for n in ck.CHECKER_NAMES:
        _fake_exe(ck.checker_path(n, tmp_path))
    return monkeypatch


CASES = [
    # (checker fn, name, stdout, expected VERIFIED?)
    (ck.drat_trim, ("c", "p"), "c parsing...\ns VERIFIED\n", True),
    (ck.drat_trim, ("c", "p"), "s NOT VERIFIED\n", False),
    # The trap: derivation progress line alone is NOT a verdict.
    (ck.drat_trim, ("c", "p"),
     "c VERIFIED derivation: all lemmas preserve satisfiability\n", False),
    (ck.lrat_check, ("c", "p"), "c parsing\nc VERIFIED\n", True),
    (ck.lrat_check, ("c", "p"), "c NOT VERIFIED\n", False),
    # lrat-check's success line must not be accepted for drat-trim...
    (ck.drat_trim, ("c", "p"), "c VERIFIED\n", False),
    # ...and vice versa.
    (ck.lrat_check, ("c", "p"), "s VERIFIED\n", False),
    (ck.cake_lpr, ("c", "p"), "s VERIFIED UNSAT\n", True),
    (ck.cake_lpr, ("c", "p"), "c error: proof step failed\n", False),
    # NOT VERIFIED anywhere overrides an (impossible) later success line.
    (ck.drat_trim, ("c", "p"), "s NOT VERIFIED\ns VERIFIED\n", False),
    # \r-prefixed lines (drat-trim uses \r overwrites) still match.
    (ck.drat_trim, ("c", "p"), "\rs VERIFIED\n", True),
]


@pytest.mark.parametrize("fn,args,stdout,expect", CASES,
                         ids=[f"{c[0].__name__}-{i}" for i, c in enumerate(CASES)])
def test_verdict_matrix(fn, args, stdout, expect, with_binary, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout))
    result = fn(*args)
    got = result.status is ck.CheckStatus.VERIFIED
    assert got == expect, f"{fn.__name__} on {stdout!r}: {result.status}"


def test_cake_lpr_heap_exhaustion_is_resource_not_verdict(monkeypatch, tmp_path):
    """A checker running out of its fixed heap says nothing about the proof:
    RESOURCE_EXCEEDED, never NOT_VERIFIED (seen on the benchmark runner for a
    record-scale LRAT: 'CakeML heap space exhausted.')."""
    monkeypatch.setattr(ck, "_BIN", tmp_path)
    _fake_exe(ck.checker_path("cake_lpr", tmp_path))  # .exe on Windows
    seen = {}

    def run(cmd, *a, **k):
        seen["cmd"] = cmd

        class P:
            stdout = ""
            stderr = "CakeML heap space exhausted.\n"
        return P()

    monkeypatch.setattr(ck.subprocess, "run", run)
    r = ck.cake_lpr("f.cnf", "p.lrat")
    assert r.status is ck.CheckStatus.RESOURCE_EXCEEDED
    assert "heap" in r.detail
    # The wrapper sizes the heap explicitly instead of trusting the 4 GB default.
    assert any(str(x).startswith("--CML_HEAP_SIZE=") for x in seen["cmd"])
    assert any(str(x).startswith("--CML_STACK_SIZE=") for x in seen["cmd"])
    heap = int([x for x in seen["cmd"] if str(x).startswith("--CML_HEAP_SIZE=")][0].split("=")[1])
    assert heap >= ck.CAKE_LPR_HEAP_MB_MIN


def test_cake_lpr_heap_override(monkeypatch):
    monkeypatch.setenv("HEESCH_CAKE_HEAP_MB", "6000")
    assert ck.cake_lpr_heap_mb() == 6000


def test_cake_lpr_heap_override_non_numeric_falls_back(monkeypatch):
    """Audit 2026-08-19: misconfiguration must not crash the gate."""
    monkeypatch.setenv("HEESCH_CAKE_HEAP_MB", "lots")
    assert ck.CAKE_LPR_HEAP_MB_MIN <= ck.cake_lpr_heap_mb() <= ck.CAKE_LPR_HEAP_MB_MAX


# --- audit 2026-08-19 Medium 7: unusable checker files are CHECKER_MISSING ---

def test_non_executable_checker_is_missing_not_a_traceback(tmp_path):
    exe = ck.checker_path("cake_lpr", tmp_path)
    exe.write_text("not a program")
    exe.chmod(0o644)
    if os.access(exe, os.X_OK):
        pytest.skip("X_OK is not meaningful on this platform (root / Windows)")
    r = ck.cake_lpr("f.cnf", "p.lrat", bin_dir=tmp_path)
    assert r.status is ck.CheckStatus.CHECKER_MISSING
    assert "not executable" in r.detail


def test_directory_named_like_a_checker_is_missing(tmp_path):
    ck.checker_path("drat-trim", tmp_path).mkdir()
    r = ck.drat_trim("f.cnf", "p.drat", bin_dir=tmp_path)
    assert r.status is ck.CheckStatus.CHECKER_MISSING
    assert "regular file" in r.detail


def test_spawn_oserror_is_missing(tmp_path, monkeypatch):
    """Executable bit set but exec fails (ENOEXEC/EACCES at spawn): still a
    structured availability outcome."""
    _fake_exe(ck.checker_path("lrat-check", tmp_path))

    def run(*a, **k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(ck.subprocess, "run", run)
    r = ck.lrat_check("f.cnf", "p.lrat", bin_dir=tmp_path)
    assert r.status is ck.CheckStatus.CHECKER_MISSING
    assert "spawn failed" in r.detail
