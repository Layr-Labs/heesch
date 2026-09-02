"""§12.3 metamorphic suite: invariance under global symmetry, translation,
line order; reflection-ban behavior; duplicate digests."""

import random

from util import monomino_hc1, monomino_hc2, witness_text

from heesch_verify import (
    ErrorCode,
    GRIDS,
    VerifyConfig,
    VerifyError,
    Xform,
    parse_submission,
    verify_witness,
)


def _transform_submission_text(text: str, sym, dx: int, dy: int) -> str:
    """Apply a global point-group element plus translation to the tile AND
    all placements; return new submission text."""
    sub = parse_submission(text)
    g = Xform(sym.a, sym.b, sym.c0 + dx, sym.d, sym.e, sym.f0 + dy)
    new_cells = [g.apply(c) for c in sub.cells]
    # Conjugate each placement: new_xf = g . xf . g^{-1}? No — placements map
    # the ORIGINAL tile definition; when the tile definition itself is
    # rewritten as g(cells), a placement xf becomes g . xf . g^{-1} so that
    # the placed copies are the g-images of the originals.
    det = sym.a * sym.e - sym.b * sym.d
    # inverse of the linear part (integer, det = ±1)
    ia, ib, id_, ie = sym.e * det, -sym.b * det, -sym.d * det, sym.a * det
    # full inverse of g: x = A^{-1}(x' - t)
    itx = -(ia * (sym.c0 + dx) + ib * (sym.f0 + dy))
    ity = -(id_ * (sym.c0 + dx) + ie * (sym.f0 + dy))
    ginv = Xform(ia, ib, itx, id_, ie, ity)

    def conj(xf: Xform) -> Xform:
        # g . xf . ginv
        m1 = _compose(g, xf)
        return _compose(m1, ginv)

    patches = []
    for p in sub.patches:
        patches.append([(lvl, conj(xf).as_text()) for lvl, xf in p])
    return witness_text(sub.grid_id, new_cells, sub.hc_claim, sub.hh_claim, patches)


def _compose(p: Xform, q: Xform) -> Xform:
    """p after q (p . q)."""
    return Xform(
        p.a * q.a + p.b * q.d,
        p.a * q.b + p.b * q.e,
        p.a * q.c + p.b * q.f + p.c,
        p.d * q.a + p.e * q.d,
        p.d * q.b + p.e * q.e,
        p.d * q.c + p.e * q.f + p.f,
    )


def test_global_symmetry_invariance():
    base = verify_witness(monomino_hc2()).result
    grid = GRIDS["O"]
    for sym in grid.orientations:
        moved = _transform_submission_text(monomino_hc2(), sym, 0, 0)
        r = verify_witness(moved).result
        assert (r.hc_verified, r.hh_verified) == (base.hc_verified, base.hh_verified)
        assert r.canonical_digest == base.canonical_digest


def test_large_translation_invariance():
    base = verify_witness(monomino_hc2()).result
    grid = GRIDS["O"]
    ident = grid.orientations[0]
    moved = _transform_submission_text(monomino_hc2(), ident, 1000, -373)
    r = verify_witness(moved).result
    assert (r.hc_verified, r.hh_verified) == (base.hc_verified, base.hh_verified)
    assert r.canonical_digest == base.canonical_digest


def test_placement_line_shuffle_invariance():
    text = monomino_hc2()
    lines = text.strip().split("\n")
    head, count, placements = lines[:2], lines[2], lines[3:]
    rng = random.Random(7)
    for _ in range(5):
        rng.shuffle(placements)
        shuffled = "\n".join(head + [count] + placements) + "\n"
        r = verify_witness(shuffled).result
        assert r.hc_verified == 2


def test_reflection_banned_board():
    # A reflected placement on a reflections-banned board is rejected.
    text = monomino_hc1().replace("1 <1,0,1,0,1,1>", "1 <-1,0,1,0,1,1>")
    # (monomino is symmetric so the reflected copy still fits geometrically)
    r = verify_witness(text)  # allowed by default
    assert r.result.hc_verified == 1
    try:
        verify_witness(text, VerifyConfig(allow_reflections=False))
        raise AssertionError("reflection accepted on banned board")
    except VerifyError as e:
        assert e.code is ErrorCode.XFORM_REFLECTION_BANNED


def test_same_shape_two_rotations_same_digest():
    l1 = witness_text("O", [(0, 0), (1, 0), (2, 0), (2, 1)], 0, 0, [])
    l2 = witness_text("O", [(0, 0), (0, 1), (0, 2), (-1, 2)], 0, 0, [])
    d1 = verify_witness(l1).result.canonical_digest
    d2 = verify_witness(l2).result.canonical_digest
    assert d1 == d2


def test_mirror_pair_digest_depends_on_reflection_policy():
    # An L and its mirror image: same digest when reflections allowed,
    # different when banned.
    l = [(0, 0), (1, 0), (2, 0), (2, 1)]
    lm = [(0, 0), (1, 0), (2, 0), (2, -1)]
    tl = witness_text("O", l, 0, 0, [])
    tm = witness_text("O", lm, 0, 0, [])
    da = verify_witness(tl).result.canonical_digest
    db = verify_witness(tm).result.canonical_digest
    assert da == db
    cfg = VerifyConfig(allow_reflections=False)
    da2 = verify_witness(tl, cfg).result.canonical_digest
    db2 = verify_witness(tm, cfg).result.canonical_digest
    assert da2 != db2
