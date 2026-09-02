"""§12.4 differential: fast path vs naive reference on random small patches.

Random patches are built by randomly perturbing valid monomino/domino
witnesses — some stay valid, some break; both implementations must agree on
the verdict either way."""

import random

import pytest

from util import monomino_hc1, monomino_hc2, domino_hc1, witness_text, xf_t
from reference_impl import naive_verdict

from heesch_verify import GRIDS, VerifyConfig, VerifyError, parse_submission, verify_witness

N_CASES = 2000


def _random_mutation(rng, text):
    """Return a possibly-broken variant of a valid witness."""
    lines = text.strip().split("\n")
    choice = rng.randrange(5)
    pl_start = 3
    if choice == 0 and len(lines) > pl_start + 1:
        # move one placement by a small delta
        i = rng.randrange(pl_start, len(lines))
        lvl, xf = lines[i].split(" ", 1)
        nums = xf.strip("<>").split(",")
        j = rng.choice((2, 5))
        nums[j] = str(int(nums[j]) + rng.choice((-1, 1)))
        lines[i] = f"{lvl} <{','.join(nums)}>"
    elif choice == 1 and len(lines) > pl_start + 1:
        # delete one placement
        i = rng.randrange(pl_start + 1, len(lines))
        del lines[i]
        lines[2] = str(int(lines[2]) - 1)
    elif choice == 2 and len(lines) > pl_start + 1:
        # relabel a level
        i = rng.randrange(pl_start, len(lines))
        lvl, xf = lines[i].split(" ", 1)
        lines[i] = f"{max(0, int(lvl) + rng.choice((-1, 1)))} {xf}"
    elif choice == 3 and len(lines) > pl_start + 1:
        # duplicate a placement
        i = rng.randrange(pl_start, len(lines))
        lines.append(lines[i])
        lines[2] = str(int(lines[2]) + 1)
    # choice 4: unchanged
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("seed", range(4))
def test_fast_vs_naive_agree(seed):
    rng = random.Random(seed)
    bases = [monomino_hc1(), monomino_hc2(), domino_hc1()]
    grid = GRIDS["O"]
    agree = 0
    for _ in range(N_CASES // 4):
        text = _random_mutation(rng, rng.choice(bases))
        # Parse; if unparseable both reject trivially.
        try:
            sub = parse_submission(text)
        except VerifyError:
            continue

        # Fast path.
        fast_ok, fast_hc = True, 0
        try:
            out = verify_witness(text, VerifyConfig(strict_claims=True))
            fast_hc = out.result.hc_verified
        except VerifyError:
            fast_ok = False

        # Naive path (structure checks only; claims compared separately).
        ok, hc, _reason = naive_verdict(
            sub.cells, sub.patches[0] if sub.patches else [], grid,
            "point", hole_mode="hc",
        )
        naive_ok = ok and hc >= sub.hc_claim

        assert fast_ok == naive_ok, (
            f"disagreement on:\n{text}\nfast={fast_ok} naive={naive_ok} ({_reason})"
        )
        if fast_ok:
            assert fast_hc == max(hc, 0)
        agree += 1
    assert agree > 0
