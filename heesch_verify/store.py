"""Append-only record store with best-per-shape supersession (§7 Stage 7).

Keyed by canonical_digest, holds the BEST result per shape, not the first.
This is load-bearing: the §9.2 defect gradient is the same shape improved
repeatedly (47 -> 31 -> 12 -> 0), and first-wins dedupe would make every step
after the first a DUPLICATE.

Not wired into the Yukon CI path (Yukon's own promotion handles the
single-track case); this backs the leaderboard service, which can replay
git history through it to reconstruct attribution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .result import Result
from .score import hc_board_key, improvement_component, strictly_better


@dataclass(frozen=True)
class StoreEntry:
    result: Result
    entrant: str
    submitted_at: str      # ISO timestamp, supplied by the caller
    discoverer: str        # original attribution, preserved across supersession
    superseded: bool = False
    supersede_reason: str = ""


class Verdict:
    def __init__(self, status: str, message: str = ""):
        self.status = status  # "PROMOTED" | "DUPLICATE"
        self.message = message

    def __repr__(self):
        return f"Verdict({self.status}, {self.message!r})"


class RecordStore:
    """In-memory store with an optional append-only JSONL journal."""

    def __init__(self, path=None, board=hc_board_key):
        self._best: dict[str, StoreEntry] = {}
        self._history: dict[str, list[StoreEntry]] = {}
        self._path = path
        self._board = board

    def _append_journal(self, kind: str, entry: StoreEntry):
        if self._path is None:
            return
        line = {
            "kind": kind,
            "digest": entry.result.canonical_digest,
            "entrant": entry.entrant,
            "discoverer": entry.discoverer,
            "submitted_at": entry.submitted_at,
            "result": entry.result.to_json(),
        }
        with open(self._path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")

    def get(self, digest: str) -> StoreEntry | None:
        return self._best.get(digest)

    def history(self, digest: str) -> list[StoreEntry]:
        return list(self._history.get(digest, []))

    def put(self, result: Result, entrant: str, submitted_at: str) -> Verdict:
        digest = result.canonical_digest
        existing = self._best.get(digest)

        if existing is None:
            entry = StoreEntry(
                result=result, entrant=entrant, submitted_at=submitted_at,
                discoverer=entrant,
            )
            self._best[digest] = entry
            self._history.setdefault(digest, []).append(entry)
            self._append_journal("promoted", entry)
            return Verdict("PROMOTED", "new shape record")

        if strictly_better(result, existing.result, self._board):
            # Supersede: old record kept in history, discoverer attribution
            # carried forward; the improvement is credited to this entrant.
            old = StoreEntry(
                result=existing.result, entrant=existing.entrant,
                submitted_at=existing.submitted_at, discoverer=existing.discoverer,
                superseded=True,
                supersede_reason=f"improved {improvement_component(result, existing.result, self._board)}",
            )
            self._history[digest][-1] = old
            entry = StoreEntry(
                result=result, entrant=entrant, submitted_at=submitted_at,
                discoverer=existing.discoverer,
            )
            self._best[digest] = entry
            self._history[digest].append(entry)
            self._append_journal("promoted", entry)
            return Verdict("PROMOTED", f"supersedes record held by {existing.entrant}")

        component = improvement_component(result, existing.result, self._board)
        if component == "identical":
            msg = (
                f"identical to the record for this shape held by {existing.entrant} "
                f"(submitted {existing.submitted_at})"
            )
        else:
            msg = (
                f"does not improve the record held by {existing.entrant}: "
                f"first differing component '{component}' is not better"
            )
        return Verdict("DUPLICATE", msg)
