"""Revision manifest (spec §11): the frozen constants, introspected from live
code for drift detection. Any change to the placement universe, variable
ordering, clause schema, emission order, or contact relation is a new
version and a new revision — bug fixes are not exempt."""

from __future__ import annotations

import hashlib
import json
import pathlib

from heesch_verify.grids import GRIDS

from . import amo

REVISIONS_DIR = pathlib.Path(__file__).parent / "revisions"


def live_constants() -> dict:
    """The values whose drift invalidates historical proofs, read from the
    running code (not from the manifest)."""
    point_groups = {}
    for gid, grid in sorted(GRIDS.items()):
        point_groups[gid] = [
            [s.a, s.b, s.c0, s.d, s.e, s.f0] for s in grid.orientations
        ]
    return {
        "amo_threshold": amo.AMO_THRESHOLD,
        "placement_order": "(symmetry_index, ty, tx)",
        "cell_order": "(y, x)",
        "literal_order": "(abs, negative-first)",
        "clause_emission": "amo-by-cell-then-pair, coverage-by-cell",
        "dimacs_profile": "p-cnf/newline/space/zero-terminated/no-comments/v1",
        "digest_algo": "sha256",
        "contact_relation": "point",
        "point_groups": point_groups,
    }


def constants_digest() -> str:
    payload = json.dumps(live_constants(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def load_revision(n: int = 1) -> dict:
    return json.loads((REVISIONS_DIR / f"rev-{n}.json").read_text(encoding="utf-8"))


def load_revision_addendum(n: int) -> dict | None:
    """Corrections to DOCUMENTARY fields of an immutable manifest (never to a
    frozen constant): `rev-<n>-addendum.json`, or None. The addendum is
    checked against the live code by test_revision_freeze.py."""
    p = REVISIONS_DIR / f"rev-{n}-addendum.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def live_constants_v2() -> dict:
    """v2 frozen constants (multilevel spec §11). NEVER fold these into
    live_constants(): its digest is pinned by the immutable revision-1
    manifest."""
    c = live_constants()
    c.update({
        "encoder_version": "heesch-encoder/v2",
        "families_active": ["1", "2", "4", "5", "6"],
        "weak_bound_B": 0,
        "level_window": "{l-1,l,l+1}",
        "universe_construction": "reachability-bfs/v1",
        "variable_order": "x:(l,symmetry_index,ty,tx); cov:none; sinz:group-emission",
        "clause_emission_v2": (
            "f1-by-cell, f2-by-cell-then-pair, f4-by-(l,p), "
            "f5-by-(l,p,j,q), f6-by-(l,q,cell)"
        ),
    })
    return c


def constants_digest_v2() -> str:
    payload = json.dumps(live_constants_v2(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
