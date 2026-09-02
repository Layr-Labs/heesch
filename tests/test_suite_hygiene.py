"""The live submission/best.heesch is participant-owned and changes with every
Yukon promotion — it can be any tier, including a record-tier shape whose
#PROOF block needs checkers and a record-scale re-encode the test matrix
cannot run. Tests must build on the frozen fixtures in util.py instead
(census_baseline, omino11_hc1, ...); this broke the whole matrix once, when
the first promoted record-tier submission landed on master (runs 32583790333
through 32718922048)."""

import pathlib
import re

TESTS = pathlib.Path(__file__).resolve().parent


def test_no_test_reads_the_live_submission():
    # ROOT-anchored access to the submission dir; scratch-repo writes like
    # (repo / "submission" / ...) are fine.
    pattern = re.compile(r'ROOT\s*/\s*"submission"')
    offenders = [
        f"{p.name}:{i}"
        for p in sorted(TESTS.glob("*.py"))
        if p.name != pathlib.Path(__file__).name
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not offenders, (
        "tests must not read the live submission/ (use util.census_baseline "
        f"or another frozen fixture): {offenders}"
    )
