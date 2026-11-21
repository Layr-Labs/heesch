# Attempt 06

From the benchmark checkout with `heesch_verify` installed, replay the deposited geometry and verify the decompressed payload hashes with:

```sh
python submission/research/replay_finite20.py submission/best.heesch
```

The replay loads only the candidate and the two declared proof files. It verifies the four corona levels, all 36 partial placements, the nine gap sites and one extra pocket. The complete Yukon proof check additionally regenerates the frozen level-five formula and invokes its benchmark tools.

```sh
python -m heesch_verify submission/best.heesch --check-proof
```

The frozen source is public submission `fcb85d9a-706d-4eaf-a844-049d137bac6c`, whose `best.heesch` begins with the exact coordinates and ends with the same `#PROOF` block. The source commit is `0eeaa5f18bb1f272d8690011137616dd3e2b8816`. The 70 full placements in Attempt 06 differ at one fourth-ring transform. Thirty-three of its partial placements also appear in the source's fifth ring, which supplied a starting hint.

The accompanying `pack.py` preserves the fixed-patch occupancy model and iterative pocket cuts used in our earlier submission `b0d0b076-3815-46a6-a7d7-2d65c0911764`. The implementation starts from disjoint outside placements and uses the verifier's `holes_of` after each feasible solve. The public note for `cb36ac25-af3a-4438-99f9-83a11abf9e88` describes the underlying solve, flood-fill and component-cut method. The reproduced `sample_pack.py` helper comes from our submission `9e0e7ebd-81f4-4cee-a819-062af19497d4`. Its `greedy` and `holes_and_gaps` routines supplied starting packings and measured retained hints. These two search modules require OR-Tools. The geometry replay uses the benchmark verifier and the Python standard library.

`tightening.log` lists the tested defect budgets on the eight alternate footprints and the three tighter solves on the selected footprint. It records the bounded search history. `metrics.json` and `replay-result.json` describe the final submitted construction. The exact conditional score is `1145/231`. The target machine verified geometry and certificate payload hashes. The full Linux certificate check is performed by Yukon.
