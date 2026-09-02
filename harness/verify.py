"""Yukon evaluator: grade submission/best.heesch, write score.json (root; HEESCH_SCORE_DIR overrides for the sandbox).

Run as `PYTHONHASHSEED=0 python -P -m harness.verify` from the repo root
(benchmark.sh runs it as `python -I -m harness.verify`, which implies -P and
ignores the environment; determinism comes from canonical ordering in the
code, not the hash-seed pin).

Policy (mirrors the verifier architecture §3): the solver's search program
under submission/ is an inert artifact — nothing there is ever imported or
executed. The inputs are the plain-text shape file and, optionally, a proof
file it names — pure data, parsed by our own verifier and by the vendored
proof checkers inside the same sandbox.

Acceptance rule (architecture §2.2, fail closed): a submission scores only
when the witness verifies AND the shape's non-tilerhood is proven — by the
published census (small shapes) or by a machine-checked UNSAT proof of
F(S, m) carried in a #PROOF block. Everything else is REJECTED.

score.json is written only on full success; every rejection exits nonzero
with a REJECTED line naming the stable error code, and never writes a score.
"""

from __future__ import annotations

import json
import math
import pathlib
import stat
import sys

from heesch_verify import VerifyError, defect as defect_mod, score as score_mod
from heesch_verify.gates import IsohedralGate, Verdict
from heesch_verify.proofgate import ProofCarryingGate
from heesch_verify.result import Result
from heesch_verify.witness import VerifyConfig, verify_witness

import os

ROOT = pathlib.Path.cwd()
SHAPE_PATH = ROOT / "submission" / "best.heesch"
# benchmark.sh points HEESCH_SCORE_DIR at a sandbox scratch dir and copies
# the score to the repo root only after full success; direct invocations
# write to the repo root themselves.
SCORE_PATH = pathlib.Path(os.environ.get("HEESCH_SCORE_DIR", str(ROOT))) / "score.json"
MAX_SHAPE_BYTES = 2 * 1024 * 1024


class Reject(Exception):
    pass


def _strict_load_text(path: pathlib.Path, max_bytes: int) -> str:
    # Audit V3/V5: the submission file must be a real regular file, not a
    # symlink or a device. A symlinked best.heesch would read an arbitrary
    # runner-readable path (host-file exfil / existence oracle); a character
    # device (/dev/zero) never EOFs and read_bytes() would exhaust memory into
    # an unstructured SIGKILL before the size cap engages. O_NOFOLLOW refuses a
    # symlink at the final component, fstat/S_ISREG refuses every non-regular
    # file, and the read is bounded to max_bytes+1 so an endless source cannot
    # blow past the cap.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise Reject(f"SHAPE_NOT_REGULAR_FILE: cannot open {path.name}: {e}")
    with os.fdopen(fd, "rb", closefd=True) as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise Reject(f"SHAPE_NOT_REGULAR_FILE: {path.name} is not a regular file")
        try:
            raw = fh.read(max_bytes + 1)
        except OSError as e:
            raise Reject(f"cannot read {path.name}: {e}")
    if len(raw) > max_bytes:
        raise Reject(f"{path.name} exceeds the {max_bytes}-byte cap")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        raise Reject(f"{path.name} is not valid utf-8: {e}")


def _score_payload(result: Result, defect_res) -> dict:
    score = score_mod.yukon_score(result)
    if not math.isfinite(score):
        raise Reject("computed score is not finite")
    metrics = result.to_json()
    if defect_res is not None:
        frac_num = max(0, defect_res.required - defect_res.defect_hc)
        metrics["score_fraction_num"] = frac_num
        metrics["score_fraction_den"] = defect_res.required
    return {"score": round(score, 6), "metrics": metrics}


def _with(result: Result, **fields) -> Result:
    kwargs = {**result.__dict__}
    kwargs.update(fields)
    return Result(**kwargs)


def _record_eligible(evidence: str, hc_verified: int) -> bool:
    """The machine-checkable precondition for a new class record (§2.3/§13.9).

    Non-tilerhood established by a checked UNSAT proof of F(S, m) gives a
    finite upper bound Hh <= m - 1, and a verified witness gives Hc >= hc.
    Since Hc <= Hh, `hc >= 5` with ANY such certificate already beats the
    known value 4 — whatever the exact value turns out to be (Hc in
    {Hh - 1, Hh}, so a shape with Hc = 5 may well have Hh = 6 and need
    F(S,7)). Exactness is a separate flag (`exact` / `record_exact`); it is
    NOT required to be record-breaking (audit 2026-08-19 High 1). Census
    evidence cannot reach hc >= 5 (the census maxima are 2/3/3) and would
    trip CENSUS_CONTRADICTION first, but the predicate insists on a proof
    anyway."""
    return evidence == "proof" and hc_verified >= 5


def _run_proof_gate(sub, outcome, profile):
    # Checker binaries: the harness may be running from the installed copy in
    # .venv-bench (python -I), so the package-relative default in
    # heesch_encoder.proofcheck.checkers does not resolve — locate them
    # explicitly (HEESCH_CHECKER_DIR, else <repo>/tools/bin). Every budget
    # (band, encode guard, checker caps/deadline, size caps) comes from the
    # machine-derived resource profile (heesch_verify/profile.py): `record`
    # on the dedicated runner (docs/RUNNER.md), `standard` elsewhere.
    from heesch_encoder.proofcheck.checkers import CheckBudget

    checker_dir = pathlib.Path(os.environ.get("HEESCH_CHECKER_DIR") or (ROOT / "tools" / "bin"))
    budget = CheckBudget(per_checker=profile.checker_caps,
                         deadline_seconds=profile.checker_deadline_s)
    return ProofCarryingGate(SHAPE_PATH.parent, checker_dir, budget,
                             profile=profile).check(sub, outcome)


def main() -> None:
    # Review finding 2: a stale score must never survive into a failed run
    # (benchmark.sh also wipes the repo-root copy before anything fallible).
    try:
        SCORE_PATH.unlink()
    except OSError:
        pass

    text = _strict_load_text(SHAPE_PATH, MAX_SHAPE_BYTES)

    config = VerifyConfig()
    try:
        outcome = verify_witness(text, config)
    except VerifyError as e:
        raise Reject(f"{e.code.value}: {e.message}")

    result = outcome.result
    sub = outcome.submission

    # Defect pass (§9.2): runs after Stage 5, reusing the same threaded
    # contact relation.
    defect_res = None
    if sub.defect is not None:
        if outcome.hc_corona is None:
            raise Reject("DEFECT_LEVEL_MISMATCH: defect block requires a witness patch")
        try:
            defect_res = defect_mod.verify_defect(
                frozenset(sub.cells), sub.grid, outcome.hc_corona, sub.defect,
                outcome.contact, allow_reflections=config.allow_reflections,
            )
        except VerifyError as e:
            raise Reject(f"{e.code.value}: {e.message}")
        # Rebuild the frozen Result with defect fields populated.
        kwargs = {**result.__dict__}
        kwargs.update(
            defect_corona_level=defect_res.corona_level,
            defect_hc=defect_res.defect_hc,
            defect_hh=defect_res.defect_hh,
            defect_required=defect_res.required,
            defect_pocket_cells=defect_res.pocket_cells,
            defect_partial_tiles=defect_res.partial_tiles,
        )
        result = Result(**kwargs)

    # §9.2.2 / §9.2.6: what was established, never "minimum defect", and the
    # scalar is never labelled a Heesch number.
    claim = result.verified_claim
    if defect_res is not None:
        claim += (
            f"; defect_achieved {defect_res.defect_hc}/{defect_res.required}"
            f" at corona {defect_res.corona_level}"
        )

    # Stage 6 — the fail-closed non-tiler rule (architecture §2.2). A shape
    # scores only when its non-tilerhood is PROVEN: by Kaplan's complete
    # census (exact for small shapes) or by a machine-checked UNSAT proof of
    # F(S, m) carried in the submission. A constructive TILER verdict rejects
    # outright; INCONCLUSIVE without a proof rejects too.
    gate = IsohedralGate(sub.grid).evaluate(frozenset(sub.cells))
    if gate.verdict is Verdict.TILER:
        raise Reject(
            f"GATE_IS_TILER: shape tiles the plane ({gate.detail}); "
            "its Heesch number is not finite"
        )

    evidence = ""
    tier = "lower_bound"
    exact = False
    hh_exact = False
    gate_detail = gate.detail
    if gate.verdict is Verdict.NON_TILER:
        # Soundness tripwire: a verified witness deeper than the census's
        # exact value means the verifier or the census is wrong. Never score.
        if result.hc_verified > gate.census_hc or result.hh_verified > gate.census_hh:
            raise Reject(
                "CENSUS_CONTRADICTION: verified hc/hh "
                f"{result.hc_verified}/{result.hh_verified} exceed the published "
                f"census values {gate.census_hc}/{gate.census_hh}"
            )
        evidence = "census"
        hh_exact = result.hh_verified == gate.census_hh
        exact = hh_exact and result.hc_verified == gate.census_hc == gate.census_hh
        claim += f"; non-tiler by census (Kaplan 2022: Hc={gate.census_hc}, Hh={gate.census_hh})"
        result = _with(result, census_hc=gate.census_hc, census_hh=gate.census_hh)

    from heesch_verify.profile import detect as detect_profile

    profile = detect_profile()
    proof_verdict = None
    if sub.proof is not None:
        proof_verdict = _run_proof_gate(sub, outcome, profile)
        # Any block that is present is verified or the submission is rejected
        # (same rule as #DEFECT); a failed proof is never silently ignored.
        if proof_verdict.code is not None:
            raise Reject(f"{proof_verdict.code.value}: {proof_verdict.detail}")
        evidence = "proof"
        hh_exact = proof_verdict.hh_exact
        exact = proof_verdict.exact
        # `exact_proof` = Hc = Hh = k established by a checked proof; every
        # other accepted entry (census-backed, or a proof at m > hh + 1) is a
        # lower bound with certified non-tilerhood.
        tier = "exact_proof" if exact else "lower_bound"
        gate_detail = (
            f"nontiler:{'census+' if gate.verdict is Verdict.NON_TILER else ''}"
            f"proof:v2:m={proof_verdict.m}"
        )
        claim += f"; non-tiler by checked UNSAT proof of F(S,{proof_verdict.m})"
        if exact:
            claim += f"; Hc = Hh = {result.hc_verified} exactly"
        elif _record_eligible(evidence, result.hc_verified):
            claim += (f"; record-breaking lower bound: Hc >= {result.hc_verified}, "
                      f"Hh <= {proof_verdict.m - 1}")
        result = _with(
            result,
            proof_status="VERIFIED",
            proof_m=proof_verdict.m,
            proof_cnf_digest=proof_verdict.cnf_digest,
            proof_sha256=proof_verdict.proof_sha256,
            proof_format=proof_verdict.fmt,
            proof_format_detected=proof_verdict.detected_format,
            proof_checkers=tuple(proof_verdict.checkers_verified),
            proof_core_clauses=proof_verdict.core_clauses,
        )

    if not evidence:
        raise Reject(
            "GATE_INCONCLUSIVE: non-tilerhood not established — the shape is "
            "outside the published census and the submission carries no #PROOF "
            "block (see README: fail-closed rule)"
        )

    result = _with(
        result,
        gate_tier=f"nontiler_{evidence}",
        verified_claim=claim,
        non_tiler_evidence=evidence,
        tier=tier,
        hh_exact=hh_exact,
        exact=exact,
        record_eligible=_record_eligible(evidence, result.hc_verified),
        record_exact=bool(_record_eligible(evidence, result.hc_verified) and exact),
        resource_profile=profile.name,
    )
    payload = _score_payload(result, defect_res)
    payload["metrics"]["gate_detail"] = gate_detail
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORE_PATH, "w", encoding="ascii", newline="\n") as fh:
        json.dump(payload, fh, sort_keys=True)
    print(f"score {payload['score']}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Reject as e:
        print(f"REJECTED: {e}", flush=True)
        sys.exit(1)
