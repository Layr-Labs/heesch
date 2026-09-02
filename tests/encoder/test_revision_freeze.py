"""§11 freeze assertions: live-code constants must match the revision manifest;
golden CNF digests catch semantic drift the constants digest can't see;
the manifest itself is immutability-pinned."""

import hashlib
import json
import pathlib

from conftest import ROOT  # noqa: F401

from heesch_encoder import manifest

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


def test_live_constants_match_revision():
    revision = manifest.load_revision(1)
    assert revision["frozen_constants_digest"] == manifest.constants_digest(), (
        "encoder constants drifted from rev-1.json — a point group, "
        "ordering, threshold or emission rule changed. That is a NEW REVISION "
        "(heesch-encoder/v2 + re-verification), never an in-place edit."
    )


def test_revision_fields():
    revision = manifest.load_revision(1)
    for key in ("encoder_version", "revision", "amo_threshold", "placement_order",
                "cell_order", "dimacs_profile", "digest_algo", "point_groups",
                "checkers", "frozen_constants_digest"):
        assert key in revision, f"revision manifest missing {key}"
    assert revision["encoder_version"] == "heesch-encoder/v1"
    assert revision["revision"] == 1


def test_manifest_immutability_pin():
    """rev-1.json's own sha256 is committed; editing the manifest without
    adding rev-2.json fails here."""
    p = manifest.REVISIONS_DIR / "rev-1.json"
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    pin_file = GOLDEN_DIR / "manifest.sha256"
    if not pin_file.exists():
        pin_file.parent.mkdir(parents=True, exist_ok=True)
        pin_file.write_text(digest + "\n")
    assert pin_file.read_text().strip() == digest, (
        "rev-1.json was edited. Revision manifests are immutable — write "
        "rev-2.json and bump the version instead."
    )


def test_live_constants_v2_match_revision2():
    revision = manifest.load_revision(2)
    assert revision["frozen_constants_digest"] == manifest.constants_digest_v2(), (
        "v2 encoder constants drifted from rev-2.json — that is heesch-"
        "encoder/v3 + re-verification, never an in-place edit."
    )
    assert revision["encoder_version"] == "heesch-encoder/v2"
    assert revision["revision"] == 2
    for key in ("families_active", "weak_bound_B", "level_window",
                "universe_construction", "feasibility_band", "checkers"):
        assert key in revision, f"revision-2 manifest missing {key}"
    assert revision["weak_bound_B"] == 0
    assert revision["families_active"] == ["1", "2", "4", "5", "6"]


def test_revision2_manifest_immutability_pin():
    p = manifest.REVISIONS_DIR / "rev-2.json"
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    pin_file = GOLDEN_DIR / "manifest-2.sha256"
    if not pin_file.exists():
        pin_file.write_text(digest + "\n")
    assert pin_file.read_text().strip() == digest, (
        "rev-2.json was edited. Revision manifests are immutable — write "
        "rev-3.json and bump the version instead."
    )


def test_golden_digests_present_and_stable():
    goldens = json.loads((GOLDEN_DIR / "digests.json").read_text())
    assert len(goldens) >= 10
    # Regeneration equality is asserted per-fixture in test_determinism.py;
    # here just pin that the golden file itself is tracked and non-empty.
    for name, digest in goldens.items():
        assert len(digest) == 64, f"{name}: malformed digest"


def test_rev2_addendum_matches_code():
    """Audit 2026-08-19 Low 12: rev-2.json's documentary checker policy and
    band are stale and the manifest is immutable; the addendum carries the
    corrected provenance and must agree with what the code enforces."""
    from heesch_encoder.multilevel.api import FEASIBILITY_BAND
    from heesch_verify.profile import RECORD, STANDARD

    add = manifest.load_revision_addendum(2)
    assert add is not None and add["addendum_to"] == "rev-2.json"
    rev = manifest.load_revision(2)
    fixes = add["corrections"]
    assert fixes["checkers.record_tier_policy"]["rev-2.json_says"] == rev["checkers"]["record_tier_policy"]
    pol = fixes["checkers.record_tier_policy"]["enforced"]
    assert pol["formally_verified_slot"] == "cake_lpr"
    assert pol["lrat_check_may_substitute_for_cake_lpr"] is False
    assert pol["record_tier_requires"] == 2
    band = fixes["feasibility_band.supported"]
    assert [(r["max_cells"], r["max_m"]) for r in band["rev-2.json_says"]] == \
        [(r["max_cells"], r["max_m"]) for r in rev["feasibility_band"]["supported"]]
    assert tuple((r["max_cells"], r["max_m"]) for r in band["enforced"]) == FEASIBILITY_BAND
    assert tuple((r["max_cells"], r["max_m"]) for r in band["in_harness_band_standard"]) == STANDARD.harness_band
    assert tuple((r["max_cells"], r["max_m"]) for r in band["in_harness_band_record"]) == RECORD.harness_band
    # The addendum never touches a frozen constant.
    assert rev["frozen_constants_digest"] == manifest.constants_digest_v2()

