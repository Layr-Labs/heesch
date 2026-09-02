"""V3/V5/V6 regression (2026-08 audit, archived in Linear).

V3: a symlinked submission/best.heesch would read an arbitrary runner-readable
    file and echo its first token into CI logs.
V5: a symlink to a character device (/dev/zero) would read unboundedly into an
    unstructured SIGKILL before the byte cap engages.
V6: parser error sites echoed the entire (up to 1M-char) first token verbatim.

All must fail closed: nonzero exit, a REJECTED line, no score.json, and the
echoed token bounded to ~80 chars.
"""

import os
import subprocess
import sys

import pytest

from util import ROOT, census_baseline  # noqa: F401

BASELINE = census_baseline()


def _run(repo):
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    return subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=60,
    )


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    return repo


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics")
def test_symlink_to_host_file_rejected(tmp_path):
    # V3: best.heesch -> a host file the participant does not own the bytes of.
    secret = tmp_path / "secret.txt"
    secret.write_text("root:x:0:0:root:/root:/bin/bash\n", encoding="ascii")
    repo = _make_repo(tmp_path)
    (repo / "submission" / "best.heesch").symlink_to(secret)
    proc = _run(repo)
    assert proc.returncode != 0
    assert "SHAPE_NOT_REGULAR_FILE" in proc.stdout
    assert "root:x:0:0" not in proc.stdout  # content never echoed
    assert not (repo / "score.json").exists()


@pytest.mark.skipif(not os.path.exists("/dev/zero"), reason="needs /dev/zero")
def test_symlink_to_char_device_rejected_fast(tmp_path):
    # V5: /dev/zero never EOFs; the bounded read + S_ISREG must reject it
    # quickly and structurally, not OOM.
    repo = _make_repo(tmp_path)
    (repo / "submission" / "best.heesch").symlink_to("/dev/zero")
    proc = _run(repo)  # 60s timeout; must return near-instantly
    assert proc.returncode != 0
    assert "SHAPE_NOT_REGULAR_FILE" in proc.stdout
    assert not (repo / "score.json").exists()


def test_oversized_first_token_is_truncated_in_log(tmp_path):
    # V6: a 200k-char single-token first line must not flood the log; the
    # echoed token is bounded to ~80 chars.
    repo = _make_repo(tmp_path)
    (repo / "submission" / "best.heesch").write_text("X" * 200_000 + "\n", encoding="ascii")
    proc = _run(repo)
    assert proc.returncode != 0
    reject_line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("REJECTED:"))
    assert len(reject_line) < 200  # nowhere near 200k
    assert not (repo / "score.json").exists()


def test_regular_baseline_still_scores(tmp_path):
    # The hardened loader must not regress the honest path.
    repo = _make_repo(tmp_path)
    (repo / "submission" / "best.heesch").write_text(BASELINE, encoding="ascii")
    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (repo / "score.json").exists()
