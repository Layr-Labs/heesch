"""§12.9: witness verification must be cheap enough for an agent's inner
search loop. CI asserts a generous bound (hardware noise); the 10 ms p95
target is reported for local tracking."""

import time

from util import witness_text, xf_t

from heesch_verify import verify_witness


def _big_witness():
    """100-cell tile (10x10 block) with a full 1-corona of copies, plus a
    second corona — a realistic large patch."""
    cells = [(x, y) for x in range(10) for y in range(10)]
    placements = [(0, xf_t(0, 0))]
    for dx in (-10, 0, 10):
        for dy in (-10, 0, 10):
            if (dx, dy) != (0, 0):
                placements.append((1, xf_t(dx, dy)))
    for dx in (-20, -10, 0, 10, 20):
        for dy in (-20, -10, 0, 10, 20):
            if max(abs(dx), abs(dy)) == 20:
                placements.append((2, xf_t(dx, dy)))
    return witness_text("O", cells, 2, 2, [placements])


def test_witness_check_speed():
    text = _big_witness()
    # warmup + correctness
    out = verify_witness(text)
    assert out.result.hc_verified == 2

    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        verify_witness(text)
        times.append(time.perf_counter() - t0)
    times.sort()
    p95 = times[int(len(times) * 0.95) - 1]
    print(f"\np95 witness check: {p95 * 1000:.1f} ms (target 10 ms, CI bound 250 ms)")
    assert p95 < 0.25, f"p95 {p95 * 1000:.0f} ms exceeds CI bound"
