"""Non-tiler gates (docs/heesch-verifier-architecture.md §2.1–2.3). May shell out; never
imported by witness.py or anything it imports.

The acceptance rule is fail-closed (§2.2): a submission scores only when the
shape's non-tilerhood is PROVEN. Two kinds of proof are accepted —

  * census   — the shape is inside Kaplan 2022's complete published census
               (polyominoes n <= 10, polyhexes n <= 8, polyiamonds n <= 12);
               there every hole-free shape is decided exactly: listed shapes
               are non-tilers with published Hc/Hh, unlisted shapes are
               tilers.
  * proof    — the submission carries a machine-checked UNSAT proof of the
               multilevel formula F(S, m) (ProofCarryingGate), which
               establishes Hh <= m-1 over ALL patches and hence non-tilerhood.

`TilerGate` (kept under its historical name `IsohedralGate`) decides the
census range exactly and, above it, returns TILER only on a constructive
proof that a tiling exists (a boundary-word factorization or a periodic
tiling). It never returns NON_TILER from failed criteria — anisohedral tilers
exist, so absence of a factorization proves nothing; such shapes are
INCONCLUSIVE and the harness rejects them unless a proof is supplied.
"""

from __future__ import annotations

import dataclasses
import enum


class Verdict(str, enum.Enum):
    TILER = "TILER"
    NON_TILER = "NON_TILER"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclasses.dataclass(frozen=True)
class GateVerdict:
    """`verdict` plus a machine-readable `detail` naming WHICH proof fired
    or WHY a shape escaped evaluation, and — for census non-tilers — the
    published exact Heesch numbers.

      nontiler:census            — listed in Kaplan's complete census
      tiler:census               — hole-free, in-census, unlisted
      tiler:translation|conway|quarter_turn — boundary-word factorization
      tiler:periodic:...         — periodic tiling found (PeriodicTilingGate)
      unchecked:boundary_error   — boundary-word extraction failed
      unchecked:boundary_length  — over the per-grid cap (unreachable for
                                   legal shapes; kept as a tripwire)
      unchecked:unsupported_grid — no criteria for this grid
      evaluated:no_factorization — above the census, every criterion ran,
                                   nothing matched: INCONCLUSIVE
    """

    verdict: Verdict
    detail: str
    census_hc: int | None = None
    census_hh: int | None = None

    def __iter__(self):
        # Backward-compatible `verdict, detail = gate.check_detailed(...)`.
        yield self.verdict
        yield self.detail


def _load_census() -> dict:
    import json
    import pathlib

    path = pathlib.Path(__file__).parent / "known_nontilers.json"
    # Fail loud: a missing table would silently drop the gate's exact layer
    # and turn every small shape into an INCONCLUSIVE rejection.
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "bounds": {gid: int(n) for gid, n in data["bounds"].items()},
        "table": {gid: {d: (int(v[0]), int(v[1])) for d, v in data[gid].items()}
                  for gid in data["bounds"]},
    }


class IsohedralGate:
    """Gate 1 (§2.1): the census layer plus constructive tiling criteria.
    Fast, deterministic, polynomial; runs on every submission."""

    _CENSUS = None

    def __init__(self, grid):
        self.grid = grid
        if IsohedralGate._CENSUS is None:
            IsohedralGate._CENSUS = _load_census()

    @classmethod
    def census_bound(cls, grid_id: str) -> int:
        if cls._CENSUS is None:
            cls._CENSUS = _load_census()
        return cls._CENSUS["bounds"].get(grid_id, 0)

    def check(self, cells) -> Verdict:
        return self.evaluate(cells).verdict

    def check_detailed(self, cells) -> GateVerdict:
        return self.evaluate(cells)

    def evaluate(self, cells, *, use_census: bool = True) -> GateVerdict:
        """`use_census=False` skips the census layer and reports only what the
        constructive criteria prove — used by the calibration tests that
        validate those criteria AGAINST the census (never by the harness)."""
        from . import boundary
        from .canonical import canonical_digest

        cells = frozenset(cells)
        gid = self.grid.grid_id
        census = IsohedralGate._CENSUS
        bound = census["bounds"].get(gid, 0)
        if use_census and 0 < len(cells) <= bound:
            # Inside the complete census every hole-free shape is decided.
            # (The verifier has already rejected holed shapes upstream; a
            # holed shape reaching here would be reported as a tiler only if
            # it were unlisted, so guard explicitly.)
            from .shape import holes_of

            entry = census["table"][gid].get(canonical_digest(cells, self.grid, True))
            if entry is not None:
                return GateVerdict(Verdict.NON_TILER, "nontiler:census", entry[0], entry[1])
            if not holes_of(cells, self.grid):
                return GateVerdict(Verdict.TILER, "tiler:census")

        try:
            if gid == "O":
                word, n_dirs = boundary.boundary_word(cells, self.grid), 4
            elif gid == "H":
                word, n_dirs = boundary.hex_boundary_word(cells, self.grid), 6
            elif gid == "I":
                word, n_dirs = boundary.iamond_boundary_word(cells, self.grid), 6
            else:
                return GateVerdict(Verdict.INCONCLUSIVE, "unchecked:unsupported_grid")
        except (boundary.UnsupportedGrid, boundary.BoundaryError):
            return GateVerdict(Verdict.INCONCLUSIVE, "unchecked:boundary_error")
        # The per-grid caps sit above the longest boundary any legal
        # (<= 200-cell, hole-free) shape can have, so this branch is
        # unreachable for every submittable shape; kept so that if the cell
        # cap or perimeter bound ever changes, an over-cap word segregates
        # as unchecked instead of silently passing.
        if len(word) > boundary.max_boundary(n_dirs):
            return GateVerdict(Verdict.INCONCLUSIVE, "unchecked:boundary_length")
        if boundary.translation_criterion(word, n_dirs):
            return GateVerdict(Verdict.TILER, "tiler:translation")
        if boundary.conway_criterion(word, n_dirs):
            return GateVerdict(Verdict.TILER, "tiler:conway")
        if n_dirs == 4 and boundary.quarter_turn_criterion(word):
            return GateVerdict(Verdict.TILER, "tiler:quarter_turn")
        # Reflection factorization forms (Langerman–Winslow types 4–7) and
        # the hex 60/120-degree rotation forms are not implemented: a wrong
        # TILER verdict rejects a legitimate submission, so each form ships
        # only after differential validation against the census. Their
        # absence only weakens this filter; under the fail-closed rule it
        # never admits a tiler.
        try:
            from . import periodic
        except ImportError:  # pragma: no cover - periodic gate is optional
            periodic = None
        if periodic is not None:
            found = periodic.find_periodic_tiling(cells, self.grid)
            if found is not None:
                return GateVerdict(Verdict.TILER, "tiler:periodic:" + found)
        return GateVerdict(Verdict.INCONCLUSIVE, "evaluated:no_factorization")


TilerGate = IsohedralGate
