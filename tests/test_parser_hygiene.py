"""V7/V8 regression (2026-08 audit, archived in Linear).

V7: the #DEFECT block was detected by startswith('#DEFECT'), so '#DEFECTXYZ …'
    parsed as a defect block — out-of-spec bytes admitted to the record (and to
    --emit-epoch exports). The marker token must equal '#DEFECT' exactly.
V8: assert_exhausted never enforced MAX_LINE_CHARS, so an oversized whitespace
    trailing line was silently accepted and the defect peek swallowed the
    "line too long" error as generic trailing garbage.
"""

import pytest

from util import ROOT, census_baseline  # noqa: F401

from heesch_verify import VerifyError, parse_submission, verify_witness
from heesch_verify.parse import MAX_LINE_CHARS
from heesch_verify.patch import required_set
from heesch_verify.result import ErrorCode

BASELINE = census_baseline()


def _defect_witness(marker: str) -> str:
    out = verify_witness(BASELINE)
    r = len(required_set(out.hc_corona.patch_cells, out.contact))
    return BASELINE.rstrip("\n") + f"\n{marker} 2 {r} {r} {r}\n0\n"


def test_exact_defect_marker_accepted():
    sub = parse_submission(_defect_witness("#DEFECT"))
    assert sub.defect is not None


def test_bogus_defect_marker_rejected():
    # '#DEFECTXYZ' is not the marker token, so it is not a defect block; it
    # lands as trailing garbage rather than being scored.
    with pytest.raises(VerifyError) as ei:
        parse_submission(_defect_witness("#DEFECTXYZ"))
    assert ei.value.code is ErrorCode.PARSE_SYNTAX


def test_oversized_trailing_line_rejected():
    text = BASELINE.rstrip("\n") + "\n" + " " * (MAX_LINE_CHARS + 1)
    with pytest.raises(VerifyError) as ei:
        parse_submission(text)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX
    assert "too long" in ei.value.message


def test_oversized_whitespace_after_defect_block_rejected():
    # Exercises assert_exhausted's new length check (audit V8): a valid defect
    # block fully parses, then an oversized whitespace-only trailing line must
    # still be rejected — previously strip() made it falsy and it was accepted.
    text = _defect_witness("#DEFECT").rstrip("\n") + "\n" + " " * (MAX_LINE_CHARS + 1)
    with pytest.raises(VerifyError) as ei:
        parse_submission(text)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX
    assert "too long" in ei.value.message


def test_unicode_digits_rejected():
    # int() alone accepts Unicode decimal digits (e.g. ARABIC-INDIC ONE),
    # which would let out-of-spec bytes canonicalize to an in-spec shape;
    # the frozen grammar is ASCII (2026-08-20 re-verification, item 3d).
    with pytest.raises(VerifyError) as ei:
        parse_submission("O 0 0 0 1 1 0 ١ 1\n~ 0 0 0\n")
    assert ei.value.code is ErrorCode.PARSE_SYNTAX


def test_underscore_and_plus_integers_rejected():
    # int() also accepts "1_0" and "+1"; the grammar is -?[0-9]+ only.
    for tok in ("1_0", "+1"):
        with pytest.raises(VerifyError) as ei:
            parse_submission(f"O 0 0 0 1 1 0 {tok} 1\n~ 0 0 0\n")
        assert ei.value.code is ErrorCode.PARSE_SYNTAX


def test_unicode_digit_placement_line_rejected():
    from heesch_verify.parse import _PLACEMENT_RE

    assert _PLACEMENT_RE.match("١<1,0,0,0,1,0>") is None
    assert _PLACEMENT_RE.match("1<1,0,0,0,1,0>") is not None
