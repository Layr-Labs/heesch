# Baseline Heesch submission

## Context and objective

This submission records the untouched benchmark checkout obtained from Yukon
for the Heesch polyform challenge. The objective is to provide a valid,
reproducible witness for a non-tiling unmarked polyform and to preserve the
current best-known partial corona progress as a baseline for later search.
The challenge score is the verified complete-corona count plus fractional
coverage of the next corona. The scalar score is not itself a Heesch number;
the verified `hc` metric is the relevant geometric lower bound.

## Environment and setup

The Yukon CLI was installed using the official installer, followed by Yukon
authentication and cloning of benchmark ID
`af5dd63a-8242-432a-8288-d32464889153`. The clone command printed the
following benchmark work directory, which was followed exactly:

```text
/Users/prasiddhnaik/Documents/ChatGPT/shdd/heesch
```

The checkout identifies as `eigenlabs/heesch` on the `master` branch. The
benchmark manifest is schema version 1, with `submission/` as the only
editable path. No harness, verifier, encoder, benchmark script, or setup
file was modified.

The agent skill was installed with Yukon using the supported install targets.
The native Codex transcript was not found by the trace-status diagnostic, but
this does not affect the plain-text witness or proof artifacts. The local
setup command was:

```bash
yukon setup
```

Setup completed successfully. It created the benchmark virtual environment,
built `drat-trim` and `lrat-check`, and reported that `cake_lpr` is skipped
because it is an x86-64 Linux-only checker. This platform limitation is
important for interpreting the local run result below.

## Baseline contents

The baseline file is `submission/best.heesch`. It contains an 11-cell hex
shape, a complete four-corona witness, a partial level-five defect block, and
a checked-proof metadata block. The witness uses 63 placements in its main
patch and 33 partial placements in the defect block. The proof block targets
the frozen Heesch encoder formula `F(S,5)` and references the accompanying
compressed LRAT proof and compressed core clause list:

```text
submission/best.heesch
submission/proof.lrat.xz
submission/core.txt.xz
```

The proof and core files are data artifacts named by the witness. They are
not executed as participant code. Their digests are carried in the
`#PROOF` block and are intended to bind the proof to the exact shape and
encoder revision used by the harness.

## Local witness verification

Before submission, the cheap witness verifier was run against the current
file. It independently re-derived the geometry from the placements and
reported:

```json
{
  "grid": "H",
  "cell_count": 11,
  "patch_size": 63,
  "hc_claimed": 4,
  "hh_claimed": 4,
  "hc_verified": 4,
  "hh_verified": 4,
  "defect_block_present": true,
  "reflections_used": true,
  "span_x": 5,
  "span_y": 5
}
```

The direct witness pass is the fast geometry check: it checks legal grid
symmetries, disjoint placements, contacts, corona reconstruction, and the
absence of forbidden inner holes. The defect pass was also run directly with
the same contact relation used by the witness verifier. It computed:

```text
corona level: 5
required cells: 166
defect_hc: 6
defect_hh: 6
pocket cells: 0
partial tiles: 33
```

Thus the partial corona covers 160 of 166 required cells, giving the scalar
baseline `4 + 160/166 = 4.963855...` after rounding to six decimal places.

## Yukon baseline run

The requested baseline command was run from the printed work directory:

```bash
yukon run
```

The benchmark reached its verification stage but returned:

```text
REJECTED: CHECKER_UNAVAILABLE: proof checkers not available: cake_lpr
```

This is a host capability result, not a witness failure. The local machine
has the two portable proof checkers built by setup, while the benchmark's
fail-closed proof gate requires the Linux-only `cake_lpr` checker as well.
Consequently, this checkout has no local `score.json` artifact and no local
score is being claimed in this note. The official benchmark runner is the
appropriate environment for the complete proof-check path.

## Method and tradeoffs

The chosen baseline is the existing known `Hc = 4` direction rather than an
unproven larger shape. This follows the challenge ladder: first establish a
valid census witness, then reconstruct the known `Hc = 4` shapes and their
non-tiler proofs, and finally compete on the fractional corona-five defect
gradient. The current file is already at the known four-corona stage and
includes a near-complete next-corona packing, so it is a useful reproducible
starting point for incremental improvements.

No speculative edit was made to the shape, witness, defect placements, or
proof artifacts. In particular, a defect block is fail-closed: changing its
placements without recomputing the required set and all overlaps can reject
the entire submission. Similarly, changing the shape invalidates the CNF and
proof digests, so proof generation must be repeated whenever the shape
changes.

## Reproduction commands

From the benchmark work directory:

```bash
yukon setup
python -m heesch_verify submission/best.heesch
python tools/prove.py submission/best.heesch --check
yukon run
```

The first command completed here. The cheap verifier completed here and
reported the four-corona metrics above. The proof command and full benchmark
run require the checker environment described above for a complete local
acceptance result; the benchmark runner performs the authoritative sandboxed
verification.

## Next steps

The safest next experiment is to preserve this proof-backed 11-cell hex
shape and improve the level-five partial packing. The target is fewer than
six uncovered required cells, which yields a strict promotion without
requiring a new shape or a new non-tiler proof. Any proposed placement must
be checked for legal hex-grid symmetry, no overlap with the four-corona
patch or another defect tile, contact with the existing patch, and no entry
into an enclosed pocket. A complete level-five corona would cross the score
integer boundary and require updating the proof target to at least the next
required `m` before it could score as a higher exact lower bound.

This note intentionally reports local evidence and runner-dependent evidence
separately. It does not claim that the macOS checker limitation is equivalent
to a successful ranked benchmark run.
