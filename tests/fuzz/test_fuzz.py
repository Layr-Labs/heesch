"""§12.7 fuzz: never crash, never hang, always a structured error."""

import random
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from util import monomino_hc1  # noqa: E402

from heesch_verify import VerifyError, verify_witness  # noqa: E402

WALL_CLOCK_CAP = 5.0  # seconds per input, generous CI bound


def _check(text):
    t0 = time.time()
    try:
        verify_witness(text)
    except VerifyError:
        pass
    dt = time.time() - t0
    assert dt < WALL_CLOCK_CAP, f"verifier took {dt:.1f}s"


def test_random_bytes():
    rng = random.Random(42)
    for _ in range(200):
        blob = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 400)))
        _check(blob.decode("latin-1"))


def test_random_ascii_lines():
    rng = random.Random(43)
    vocab = "OHI~<>,-0123456789 \n?#DEFECT"
    for _ in range(300):
        text = "".join(rng.choice(vocab) for _ in range(rng.randrange(1, 600)))
        _check(text)


def test_truncations_of_valid_file():
    text = monomino_hc1()
    for i in range(len(text)):
        _check(text[:i])


def test_bad_counts():
    for n in ("999999999", "-5", "0", str(2**62)):
        _check(f"O 0 0\n~ 1 1 1\n{n}\n0 <1,0,0,0,1,0>\n")


def test_huge_grid_line():
    cells = " ".join(f"{i} 0" for i in range(10_000))
    _check(f"O {cells}\n~ 0 0 0\n")


def test_integers_near_2_63():
    big = 2**63 - 1
    _check(f"O 0 0 {big} {big}\n~ 0 0 0\n")
    _check(f"O 0 0\n~ {big} {big} 1\n1\n0 <1,0,0,0,1,0>\n")


def test_unicode_and_crlf():
    _check("O 0 0\r\n~ 0 0 0\r\n")
    _check("O 0 0\n~ 0 0 0\né中文\n")
    _check("﻿O 0 0\n~ 0 0 0\n")


def test_crlf_valid_file_accepted():
    text = monomino_hc1().replace("\n", "\r\n")
    out = verify_witness(text)
    assert out.result.hc_verified == 1


def test_large_file_rejected_fast():
    # ~30 MB of junk: must return quickly with a structured error, not hang.
    blob = "9 " * 15_000_000
    t0 = time.time()
    try:
        verify_witness("O " + blob + "\n~ 0 0 0\n")
    except VerifyError:
        pass
    assert time.time() - t0 < 30.0
