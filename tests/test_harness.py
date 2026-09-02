"""Harness e2e through the REAL entrypoint (subprocess, -P flag and all).

Every attack asserts the same two-part invariant (TNCOO pattern): nonzero
exit AND no score file. The baseline asserts a valid score.json."""

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

from util import ROOT, census_baseline

BASELINE = census_baseline()


def _run_harness(tmp_path, shape_text: str):
    """Materialize a scratch repo and run `python -P -m harness.verify`."""
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text(shape_text, encoding="ascii")
    # The packages are importable from ROOT via PYTHONPATH; cwd = scratch repo
    # so the harness grades the scratch submission.
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    score_path = repo / "score.json"
    score = json.loads(score_path.read_text()) if score_path.exists() else None
    return proc, score


def test_baseline_scores(tmp_path):
    proc, score = _run_harness(tmp_path, BASELINE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert score is not None
    assert score["score"] == 1.0
    m = score["metrics"]
    assert m["hc_verified"] == 1 and m["hh_verified"] == 1
    assert m["gate_tier"] == "nontiler_census"
    assert m["non_tiler_evidence"] == "census"
    assert "defect_achieved" not in m["verified_claim"] or "minimum" not in m["verified_claim"]


def test_tiler_rejected(tmp_path):
    mono = "O 0 0\n~ 1 1 1\n9\n0 <1,0,0,0,1,0>\n" + "".join(
        f"1 <1,0,{dx},0,1,{dy}>\n"
        for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)
    )
    proc, score = _run_harness(tmp_path, mono)
    assert proc.returncode != 0 and score is None
    assert "GATE_IS_TILER" in proc.stdout


def test_gap_rejected(tmp_path):
    broken = BASELINE.replace("8\n0 <1,0,0,0,1,0>\n", "7\n0 <1,0,0,0,1,0>\n", 1)
    # remove one corona line from the second patch
    lines = broken.strip().split("\n")
    lines.pop()  # drop last placement
    proc, score = _run_harness(tmp_path, "\n".join(lines) + "\n")
    assert proc.returncode != 0 and score is None
    assert "REJECTED" in proc.stdout


def test_garbage_rejected(tmp_path):
    proc, score = _run_harness(tmp_path, "not a shape file at all\n")
    assert proc.returncode != 0 and score is None
    assert "REJECTED" in proc.stdout


def test_missing_file_rejected(tmp_path):
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode != 0
    assert not (repo / "score.json").exists()


def test_shadowing_harness_is_ignored(tmp_path):
    """A hostile harness.py / sitecustomize.py under submission/ must not be
    importable: -P keeps cwd off sys.path, and submission/ is never on it."""
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text(BASELINE, encoding="ascii")
    evil = 'import json\njson.dump({"score": 999}, open("score.json", "w"))\n'
    (repo / "submission" / "harness.py").write_text(evil)
    (repo / "submission" / "sitecustomize.py").write_text(evil)
    (repo / "sitecustomize.py").write_text(evil)
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    score = json.loads((repo / "score.json").read_text())
    assert score["score"] == 1.0, "hostile shadowing changed the score!"


def test_defect_block_scores_gradient(tmp_path):
    """Baseline + a partial corona-2 block must score in (1, 2)."""
    from heesch_verify import parse, verify_witness
    from heesch_verify.patch import required_set

    out = verify_witness(BASELINE)
    R = required_set(out.hc_corona.patch_cells, out.contact)
    text = BASELINE.rstrip("\n") + f"\n#DEFECT 2 {len(R)} {len(R)} {len(R)}\n0\n"
    proc, score = _run_harness(tmp_path, text)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # empty partial corona: worst defect, fractional part 0
    assert score["score"] == 1.0
    assert score["metrics"]["defect_required"] == len(R)
    assert "defect_achieved" in score["metrics"]["verified_claim"]
    # The emitted flag agrees with the scoring rule (audit 2026-08-19 Low 13).
    assert score["metrics"]["defect_enabled"] is True


def test_p0_monohex_tiler_rejected(tmp_path):
    """Review finding 1 reproducer: a monohex (obvious plane tiler) with two
    complete coronas must be REJECTED by the gate, not scored 2.0."""
    def ring(k):
        if k == 0:
            return [(0, 0)]
        out = []
        for q in range(-k, k + 1):
            for r in range(-k, k + 1):
                if (abs(q) + abs(r) + abs(q + r)) // 2 == k:
                    out.append((q, r))
        return out

    lines = ["H 0 0", "~ 2 2 1"]
    placements = []
    for k in (0, 1, 2):
        for (q, r) in ring(k):
            placements.append(f"{k} <1,0,{q},0,1,{r}>")
    lines.append(str(len(placements)))
    lines.extend(placements)
    proc, score = _run_harness(tmp_path, "\n".join(lines) + "\n")
    assert proc.returncode != 0 and score is None
    assert "GATE_IS_TILER" in proc.stdout


def test_stale_score_removed_on_failure(tmp_path):
    """Review finding 2: a failing run must remove any pre-existing score,
    not leave the old trusted result in place."""
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text("garbage\n", encoding="ascii")
    (repo / "score.json").write_text('{"score": 999}')
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode != 0
    assert not (repo / "score.json").exists(), "stale score survived a failed run"
