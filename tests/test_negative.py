"""§12.2 negative suite: each case mutates a valid fixture so it isolates one
property, and asserts the exact error code."""

import pytest

from util import monomino_hc1, monomino_hc2, witness_text, xf_t

from heesch_verify import ErrorCode, VerifyConfig, VerifyError, verify_witness


def expect(text, code, config=None):
    with pytest.raises(VerifyError) as ei:
        verify_witness(text, config or VerifyConfig())
    assert ei.value.code is code, f"expected {code}, got {ei.value.code}: {ei.value.message}"


def test_overlap_two_placements():
    # Shift one corona-1 tile onto another.
    text = monomino_hc1().replace("1 <1,0,1,0,1,1>", "1 <1,0,0,0,1,1>")
    expect(text, ErrorCode.PATCH_OVERLAP)


def test_gap_from_deleted_tile():
    text = monomino_hc1().replace("9\n", "8\n").replace("1 <1,0,1,0,1,1>\n", "")
    expect(text, ErrorCode.PATCH_GAP)


def test_gap_in_inner_corona_of_two():
    # Delete the corona-1 edge tile at (1,0): every corona-2 tile still
    # touches some corona-1 tile (levels stay consistent), so the surround
    # check reports the inner gap.
    text = monomino_hc2().replace("25\n", "24\n").replace("1 <1,0,1,0,1,0>\n", "")
    expect(text, ErrorCode.PATCH_GAP)


def test_inner_corona_corner_deletion_breaks_levels():
    # Deleting the corona-1 corner tile at (1,1) strands the corona-2 corner
    # at (2,2), which then recomputes to level 3: checks run in order, so the
    # level mismatch surfaces before the gap.
    text = monomino_hc2().replace("25\n", "24\n").replace("1 <1,0,1,0,1,1>\n", "")
    expect(text, ErrorCode.PATCH_LEVEL_MISMATCH)


def test_level_mislabelled():
    text = monomino_hc1().replace("1 <1,0,0,0,1,1>", "2 <1,0,0,0,1,1>")
    expect(text, ErrorCode.PATCH_LEVEL_MISMATCH)


def test_orphan_tile_far_away():
    # Move one corona-1 tile far away; the corona now has a gap AND an
    # orphan. Levels are recomputed first, so the far tile surfaces as
    # unreachable before the gap check runs.
    text = monomino_hc1().replace("1 <1,0,1,0,1,1>", "1 <1,0,50,0,1,50>")
    expect(text, ErrorCode.PATCH_ORPHAN_TILE)


def test_claim_stronger_than_patch_lenient_accepts():
    text = monomino_hc1().replace("~ 1 1 1", "~ 5 5 1")
    out = verify_witness(text, VerifyConfig(strict_claims=False))
    assert out.result.hc_verified == 1
    assert out.result.claim_discrepancy


def test_claim_stronger_than_patch_strict_rejects():
    text = monomino_hc1().replace("~ 1 1 1", "~ 5 5 1")
    expect(text, ErrorCode.CLAIM_WEAKER_THAN_STATED, VerifyConfig(strict_claims=True))


def test_matrix_det2():
    text = monomino_hc1().replace("0 <1,0,0,0,1,0>", "0 <2,0,0,0,1,0>")
    expect(text, ErrorCode.XFORM_NOT_SYMMETRY)


def test_matrix_shear_det1():
    # The one naive det-checkers miss.
    text = monomino_hc1().replace("0 <1,0,0,0,1,0>", "0 <1,1,0,0,1,0>")
    expect(text, ErrorCode.XFORM_NOT_SYMMETRY)


def test_detached_cell():
    text = monomino_hc1().replace("O 0 0", "O 0 0 5 5")
    expect(text, ErrorCode.SHAPE_DISCONNECTED)


def test_ring_shaped_tile():
    ring = [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)]
    text = witness_text("O", ring, 0, 0, [])
    expect(text, ErrorCode.SHAPE_HAS_HOLE)


def test_hole_via_diagonal_pinch():
    # 7 cells around a center with one corner missing: the diagonal gap does
    # not connect the center to the outside under edge adjacency.
    cells = [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2)]
    text = witness_text("O", cells, 0, 0, [])
    expect(text, ErrorCode.SHAPE_HAS_HOLE)


def test_too_many_cells():
    cells = [(x, 0) for x in range(15)] + [(x, 1) for x in range(15)]
    big = [(x, y) for x in range(15) for y in range(14)]  # 210 cells
    text = witness_text("O", big, 0, 0, [])
    expect(text, ErrorCode.SHAPE_TOO_LARGE)


def test_span_exceeded():
    cells = [(x, 0) for x in range(30)]  # span 30 + 1 = 31 > 29
    text = witness_text("O", cells, 0, 0, [])
    expect(text, ErrorCode.SHAPE_SPAN_EXCEEDED)


def test_two_central_tiles():
    text = monomino_hc1().replace("1 <1,0,1,0,1,1>", "0 <1,0,1,0,1,1>")
    expect(text, ErrorCode.PATCH_MULTIPLE_CENTRAL)


def test_no_central_tile():
    text = monomino_hc1().replace("0 <1,0,0,0,1,0>", "1 <1,0,0,0,1,0>")
    expect(text, ErrorCode.PATCH_NO_CENTRAL_TILE)


def test_duplicate_cell_on_grid_line():
    text = monomino_hc1().replace("O 0 0", "O 0 0 0 0")
    expect(text, ErrorCode.SHAPE_DUPLICATE_CELL)


def test_count_mismatch():
    text = monomino_hc1().replace("9\n", "10\n")
    expect(text, ErrorCode.PARSE_COUNT_MISMATCH)


def test_unknown_grid():
    text = monomino_hc1().replace("O 0 0", "Q 0 0")
    expect(text, ErrorCode.PARSE_UNKNOWN_GRID)


def test_trailing_garbage():
    text = monomino_hc1() + "and now for something completely different\n"
    expect(text, ErrorCode.PARSE_SYNTAX)


def test_oversized_integer():
    text = monomino_hc1().replace("O 0 0", f"O 0 {2**63}")
    expect(text, ErrorCode.PARSE_SYNTAX)


@pytest.mark.skip(
    reason="needs a real Hh patch with an outer-corona hole from the "
    "heesch-sat fixture corpus — single-cell coronas cannot overhang"
)
def test_hole_in_outer_corona_strict_vs_lenient():
    # Filled in from tests/corpus once CI fixtures land: take a shape with
    # hh = hc + 1, relabel its Hh patch as the Hc patch; strict mode must
    # reject PATCH_HOLE_IN_CORONA, lenient must downgrade hc and keep hh.
    pass


def test_resource_exceeded_many_placements():
    n = 25_000
    lines = ["O 0 0", "~ 1 1 1", str(n)]
    lines.append("0 <1,0,0,0,1,0>")
    for i in range(n - 1):
        lines.append(f"1 <1,0,{i + 1},0,1,0>")
    with pytest.raises(VerifyError) as ei:
        verify_witness("\n".join(lines) + "\n")
    assert ei.value.code is ErrorCode.RESOURCE_EXCEEDED
