"""tools/prove.py as a CLI (audit 2026-08-19 High 2): an illegal `--out` is
refused BEFORE any encoding, nothing is ever written outside the submission
directory, best.heesch is never the proof target, every intermediate lives in
a private temp dir that is removed on every exit path, and the outputs are
installed atomically only after the new #PROOF block parses."""

import importlib.util
import os
import sys

import pytest

from util import ROOT, omino11_hc1

from heesch_verify.parse import parse_submission


def _load_prove():
    spec = importlib.util.spec_from_file_location("prove_cli", ROOT / "tools" / "prove.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def prove():
    return _load_prove()


@pytest.fixture
def subdir(tmp_path):
    d = tmp_path / "submission"
    d.mkdir()
    (d / "best.heesch").write_text(omino11_hc1(), encoding="ascii")
    return d


def _never_encode(monkeypatch, prove):
    def boom(*a, **k):
        raise AssertionError("encoder was invoked before --out validation")
    monkeypatch.setattr(prove, "encode_multilevel_stream", boom)


@pytest.mark.parametrize("out", [
    "../escaped.lrat.xz",
    "best.heesch",
    "sub/x.lrat.xz",
    "proof.drat.xz",          # suffix does not match --format lrat
    ".hidden.lrat.xz",
    "-S.lrat.xz",
    "x" * 70 + ".lrat.xz",
])
def test_illegal_out_is_refused_before_any_work(prove, subdir, monkeypatch, capsys, out):
    _never_encode(monkeypatch, prove)
    before = sorted(os.listdir(subdir.parent))
    shape_before = (subdir / "best.heesch").read_bytes()
    rc = prove.main([str(subdir / "best.heesch"), "--out=" + out])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
    assert (subdir / "best.heesch").read_bytes() == shape_before
    assert sorted(os.listdir(subdir.parent)) == before          # nothing escaped
    assert sorted(os.listdir(subdir)) == ["best.heesch"]         # nothing written, no temp dir


def test_existing_output_needs_force(prove, subdir, monkeypatch, capsys):
    _never_encode(monkeypatch, prove)
    # --format drat: its default name needs no drat-trim (which may not be
    # built, e.g. on Windows CI, where lrat would fall back to drat).
    (subdir / "proof.drat.xz").write_bytes(b"old")
    rc = prove.main([str(subdir / "best.heesch"), "--format", "drat"])
    assert rc == 1
    assert "--force" in capsys.readouterr().err
    assert (subdir / "proof.drat.xz").read_bytes() == b"old"


def test_non_ascii_shape_refused_up_front(prove, subdir, monkeypatch, capsys):
    _never_encode(monkeypatch, prove)
    (subdir / "best.heesch").write_bytes(omino11_hc1().encode() + "# café\n".encode("utf-8"))
    rc = prove.main([str(subdir / "best.heesch")])
    assert rc == 1
    assert "ASCII" in capsys.readouterr().err


def _need_solving():
    if not (ROOT / "tools" / "bin" / "drat-trim").exists():
        pytest.skip("tools/bin/drat-trim not built")
    pytest.importorskip("pysat")


def test_failed_solver_leaves_no_leftovers(prove, subdir, capsys):
    _need_solving()
    rc = prove.main([str(subdir / "best.heesch"), "--solver", "no-such-solver",
                     "--solver-bin", str(subdir.parent / "no-such-binary")])
    assert rc == 1
    assert sorted(os.listdir(subdir)) == ["best.heesch"]
    assert "#PROOF" not in (subdir / "best.heesch").read_text()


def test_happy_path_installs_atomically_and_cleans_up(prove, subdir):
    _need_solving()
    # The 11-omino has Hh = 2 (Kaplan), so F(S,2) is SAT and F(S,3) is UNSAT.
    assert prove.main([str(subdir / "best.heesch"), "--solver", "cadical153", "--no-xz"]) == 2
    assert sorted(os.listdir(subdir)) == ["best.heesch"]        # SAT path cleaned up too
    rc = prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "cadical153", "--no-xz"])
    assert rc == 0
    names = sorted(os.listdir(subdir))
    assert names == ["best.heesch", "core.txt", "proof.lrat"], names   # no .prove-* left behind
    sub = parse_submission((subdir / "best.heesch").read_text(encoding="ascii"))
    assert sub.proof is not None and sub.proof.file_name == "proof.lrat"
    assert sub.proof.core_file == "core.txt"
    # Re-running without --force refuses to clobber the installed proof.
    assert prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "cadical153", "--no-xz"]) == 1
    # --force re-proves over the existing files.
    assert prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "cadical153",
                       "--no-xz", "--force"]) == 0


# --- Plan 3 P4: external solver binary (DRAT streams to disk) ----------------

pytestmark_solver_bin = pytest.mark.skipif(os.name == "nt", reason="sh-script fake solver")


def _fake_solver(tmp_path, rc, drat_text=None):
    """A stand-in for cadical/kissat: `<bin> -q --no-binary formula.cnf proof.drat`."""
    exe = tmp_path / "fake-solver"
    body = "#!/bin/sh\n# args: -q --no-binary CNF DRAT\nfor last; do :; done\n"
    if drat_text is not None:
        body += f"printf '{drat_text}' > \"$last\"\n"
    body += f"exit {rc}\n"
    exe.write_text(body)
    exe.chmod(0o755)
    return exe


@pytestmark_solver_bin
def test_solver_bin_unsat_path(prove, tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    (work / "formula.cnf").write_text("p cnf 1 2\n1 0\n-1 0\n")
    exe = _fake_solver(tmp_path, 20, "1 0\\n0\\n")
    sat, drat = prove.solve_with_solver_bin(work / "formula.cnf", str(exe), work)
    assert sat is False and drat.read_text() == "1 0\n0\n"


@pytestmark_solver_bin
def test_solver_bin_sat_and_error_paths(prove, tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    (work / "formula.cnf").write_text("p cnf 1 1\n1 0\n")
    assert prove.solve_with_solver_bin(work / "formula.cnf", str(_fake_solver(tmp_path, 10)), work) == (True, None)
    with pytest.raises(RuntimeError):          # non-standard exit code
        prove.solve_with_solver_bin(work / "formula.cnf", str(_fake_solver(tmp_path, 1)), work)
    with pytest.raises(RuntimeError):          # UNSAT claimed, no terminated DRAT
        prove.solve_with_solver_bin(work / "formula.cnf", str(_fake_solver(tmp_path, 20, "1 0\\n")), work)


def test_drat_terminated_checks_the_tail_only(prove, tmp_path):
    p = tmp_path / "d.drat"
    p.write_bytes(b"1 2 0\n" * 100000 + b"0\n")
    assert prove._drat_terminated(p)
    p.write_bytes(b"1 2 0\n" * 100000)
    assert not prove._drat_terminated(p)


def test_happy_path_with_real_cadical_binary(prove, subdir):
    exe = ROOT / "tools" / "bin" / "cadical"
    if not exe.exists() or not (ROOT / "tools" / "bin" / "drat-trim").exists():
        pytest.skip("tools/bin/cadical (tools/build_solver.sh) or drat-trim not built")
    rc = prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "none",
                     "--solver-bin", str(exe), "--no-xz"])
    assert rc == 0
    sub = parse_submission((subdir / "best.heesch").read_text(encoding="ascii"))
    assert sub.proof is not None and sub.proof.m == 3


def test_worker_refuses_existing_outputs(tmp_path, prove):
    # The hidden --worker self-exec mode writes its two output paths without
    # argparse; it must never overwrite an existing file (2026-08-20
    # re-verification, item 1 residual).
    precious = tmp_path / "precious.txt"
    precious.write_text("keep me", encoding="ascii")
    fresh = tmp_path / "fresh.json"
    for drat, result in ((precious, fresh), (fresh, precious)):
        with pytest.raises(SystemExit) as ei:
            prove._worker(str(tmp_path / "f.cnf"), str(drat), str(result), "cadical153")
        assert "refusing to overwrite" in str(ei.value)
    assert precious.read_text(encoding="ascii") == "keep me"
    assert not fresh.exists()
