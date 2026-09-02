"""CLI: verify a shape file -> exit code + JSON on stdout."""

from __future__ import annotations

import argparse
import json
import sys

from .result import VerifyError
from .witness import VerifyConfig, verify_witness


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="heesch_verify", description="Heesch witness verifier")
    ap.add_argument("file", help="shape file (heesch-sat text format)")
    ap.add_argument("--strict", action="store_true", help="reject weaker-than-claimed witnesses")
    ap.add_argument("--no-reflections", action="store_true", help="ban reflected placements")
    ap.add_argument(
        "--emit-epoch",
        metavar="OUT",
        help="after successful verification, write an Epoch-compatible copy (defect and proof blocks stripped)",
    )
    ap.add_argument(
        "--check-proof",
        action="store_true",
        help="also run the #PROOF block through the same ProofCarryingGate the harness uses "
             "(checkers from $HEESCH_CHECKER_DIR or ./tools/bin); exit 0 only if VERIFIED",
    )
    ap.add_argument(
        "--profile",
        choices=("auto", "standard", "record"),
        default="auto",
        help="with --check-proof: the resource profile (budgets, band, size caps; "
             "heesch_verify/profile.py) — `auto` (default) picks what the harness would pick "
             "on this machine, `record` / `standard` force one",
    )
    ap.add_argument(
        "--band",
        choices=("profile", "harness", "record", "encoder", "none"),
        default="profile",
        help="with --check-proof: which (cells, m) band to enforce — `profile` (default: the "
             "selected profile's band, i.e. what the benchmark job enforces), `harness` (the "
             "standard profile's band), `record` (the record profile's band), `encoder` (the "
             "encoder's measured feasibility band), or `none` (no band at all, maintainer "
             "re-check, architecture §13.9)",
    )
    args = ap.parse_args(argv)

    try:
        with open(args.file, "r", encoding="utf-8", errors="strict") as fh:
            text = fh.read()
    except OSError as e:
        print(json.dumps({"error": "IO", "message": str(e)}))
        return 1
    except UnicodeDecodeError as e:
        print(json.dumps({"error": "PARSE_SYNTAX", "message": f"not utf-8: {e}"}))
        return 1

    config = VerifyConfig(
        strict_claims=args.strict,
        allow_reflections=not args.no_reflections,
    )
    try:
        outcome = verify_witness(text, config)
    except VerifyError as e:
        print(json.dumps(e.to_json(), sort_keys=True))
        return 1

    if args.emit_epoch:
        # Strip the optional blocks (§9.2.7 defect, §13.2 proof): everything
        # from the first #DEFECT / #PROOF marker line onward (the proof block
        # always follows the defect block, so breaking on either strips both).
        # Only a verified witness is exported — an invalid submission must not
        # leave an "Epoch-compatible" file.
        out_lines = []
        for line in text.split("\n"):
            toks = line.split()
            if toks and toks[0] in ("#DEFECT", "#PROOF"):  # exact marker token (audit V7)
                break
            out_lines.append(line)
        body = "\n".join(out_lines).rstrip("\n") + "\n"
        try:
            with open(args.emit_epoch, "w", encoding="ascii", newline="\n") as fh:
                fh.write(body)
        except (OSError, UnicodeEncodeError) as e:
            print(json.dumps({"error": "IO", "message": f"emit-epoch: {e}"}))
            return 1

    if args.check_proof:
        import os
        import pathlib

        from .profile import by_name
        from .proofgate import ProofCarryingGate, named_band

        sub = outcome.submission
        if sub.proof is None:
            print(json.dumps({"error": "PROOF_FILE_INVALID", "message": "no #PROOF block"}))
            return 1
        shape_path = pathlib.Path(args.file).resolve()
        checker_dir = pathlib.Path(
            os.environ.get("HEESCH_CHECKER_DIR") or (pathlib.Path.cwd() / "tools" / "bin")
        )
        profile = by_name(args.profile)
        gate_kwargs = {"profile": profile}
        if args.band != "profile":
            gate_kwargs["band"] = named_band(args.band)
        try:
            verdict = ProofCarryingGate(shape_path.parent, checker_dir, **gate_kwargs).check(sub, outcome)
        except OSError as e:
            # Same discipline as the load path: a maintainer misconfiguration
            # (unreadable scratch, bad checker dir) reports, never tracebacks.
            print(json.dumps({"error": "IO", "message": f"check-proof: {e}"}))
            return 1
        out = outcome.result.to_json()
        out["proof"] = verdict.to_json()
        out["proof"]["band"] = args.band
        out["proof"]["profile"] = profile.name
        print(json.dumps(out, sort_keys=True, separators=(",", ":")))
        return 0 if verdict.code is None else 1

    print(outcome.result.to_json_str())
    return 0


if __name__ == "__main__":
    sys.exit(main())
