# Feasibility measurements — what the bands are built on

The measured costs of encoding, solving and checking `F(S, m)` at every
scale the benchmark admits. These numbers — not estimates — set the resource
profiles' bands (`heesch_verify/profile.py`, architecture §13.5). Reproduce
any row with `tools/measure_record_cycle.py --shape <name> --m <m>` (full
cycle) or `tools/ml_feasibility.py --shape <name> --m <m>` (counts only);
the reference shapes are `KAPLAN_SHAPES` in `tools/ml_feasibility.py`.
Bulk corpus counts: `ml-feasibility-counts.md` (generated). Exactness
cross-check (46/46 corpus shapes reproduce their published values):
`ml-weak-gap.md`.

## Full proof cycles (encode → solve → drat-trim → lrat-check → core)

Apple M-series laptop, single core, streamed encoder, external CaDiCaL
unless noted.

| shape | cells | m | clauses | DIMACS | encode | RSS | solve | DRAT | core LRAT (xz) | core check |
|---|---|---|---|---|---|---|---|---|---|---|
| Kaplan Hc=4 11-hex | 11 | 5 | 6.9 M | 0.99 GB | 61 s | 1.6 GB | 22 s | 0.72 GB | 136 MB (11 MB) | 1 s |
| Kaplan Hc=4 11-hex | 11 | 6 | 17.2 M | 2.1 GB | 112 s | 2.5 GB | 157 s¹ | 2.2 GB | 513 MB LRAT (25 MB) | 16 s |
| Kaplan Hc=4 11-hex | 11 | 7 | 36.5 M | 4.0 GB | 187 s | 3.1 GB | 227 s¹ | 3.0 GB | 358 MB (18 MB) | 3 s |

¹ pysat cadical153 in a worker process; the external-binary path
(`tools/build_solver.sh`) produces the same proofs with ~1.6 GB peak RSS
instead of ~9× the DRAT size.

All checks: drat-trim `s VERIFIED`, lrat-check `c VERIFIED` on full LRAT and
core; the core is 2–5 % of F, which is why record-scale checking is seconds.

## Encoding counts at record-candidate sizes (2026-08-19/20)

Counts from universes (`tools/ml_feasibility.py`); encode ≈ 5 µs/clause,
DIMACS ≈ 110 B/clause. RSS is the count's peak, ≈ the encoder's.

| shape | cells | m | vars | clauses | est. DIMACS | RSS |
|---|---|---|---|---|---|---|
| hex13-kaplan-hc4hh4 | 13 | 5 | 0.86 M | 9.6 M | 1.1 GB | 2.4 GB |
| hex13-kaplan-hc4hh4 | 13 | 6 | 1.5 M | 24.3 M | 2.7 GB | 3.6 GB |
| hex13-kaplan-hc4hh4 | 13 | 7 | 2.3 M | 51.6 M | 5.7 GB | 4.3 GB |
| hex13-kaplan-hc4hh4 | 13 | 8 | 3.4 M | 97.3 M | 10.7 GB | 5.8 GB |
| hex15-kaplan-hc4hh4-a | 15 | 7 | 2.6 M | 53.2 M | 5.9 GB | 4.5 GB |
| hex16-kaplan-hc4hh4 | 16 | 6 | 2.3 M | 36.4 M | 4.0 GB | 5.1 GB |
| hex16-kaplan-hc4hh4 | 16 | 7 | 3.6 M | 77.3 M | 8.5 GB | 7.6 GB |
| hex16-kaplan-hc4hh4 | 16 | 8 | 5.3 M | 145.7 M | 16.0 GB | 9.1 GB |
| iamond20-kaplan-hc4hh4 | 20 | 6 | 2.2 M | 26.3 M | 2.9 GB | 3.1 GB |
| iamond20-kaplan-hc4hh4 | 20 | 7 | 3.4 M | 54.1 M | 5.9 GB | 4.2 GB |
| iamond20-kaplan-hc4hh4 | 20 | 8 | 5.0 M | 99.8 M | 11.0 GB | 5.8 GB |

Hex universes are the densest per cell; iamonds the leanest. The one
band-relevant case not yet grounded is a 20-cell **hex** at `m = 8`
(≈ 1.9 × the 16-hex ⇒ ~275 M clauses / ~30 GB DIMACS / ~15–18 GB RSS):
comfortable on the 128 GB Blacksmith runner but excluded from the band
until `measure.yml` times it there.

## What this buys (architecture §13.5, §13.9)

The record profile's band `(20,7) (50,4) (100,3) (200,2)` — every `Hc = 5`
certificate (`F(S,6)`/`F(S,7)`, for `Hh = 5` or `6`) and the `Hc = 6,
Hh = 6` certificate (`F(S,7)`), for shapes to 20 cells — verified inside the
benchmark job on the Blacksmith runner (`RUNNER.md`, 32 vCPU / 128 GB /
1.5 TB), worst measured case clearing every budget with 5–10× margin. The
one certificate outside the band is `F(S,8)` (`Hc = 6, Hh = 7`): measured
beyond the checking budgets (above), maintainer path per §13.9. The 8 GB CI
runner keeps the standard band `(12,6) (20,5) (50,3) (100,2)`.

## Record-runner measurements (2026-08-20, run 32409736648)

Full cycles on the production runner (`blacksmith-32vcpu-ubuntu-2404`,
128 GB), `measure.yml` / `tools/measure_record_cycle.py --cake`. Every
checker verified, including `cake_lpr` at both levels.

| shape | m | clauses | DIMACS | encode / RSS | solve | drat-trim | core (xz) | cake_lpr core | lrat-check core |
|---|---|---|---|---|---|---|---|---|---|
| 16-hex Hc=4 | 7 | 77.3 M | 11.2 GB | 697 s / 7.0 GB | 696 s | 332 s | 1.10 M cl, 1.59 GB (**62 MB**) | **318 s** | 11 s |
| 16-hex Hc=4 | 8 | 145.7 M | 19.1 GB | 1162 s / 8.6 GB | 1664 s | 1882 s | 2.84 M cl, **33.4 GB (2.2 GB)** | **13 903 s** | 239 s |

**What the m=8 row decided.** Encoding `F(S,8)` is comfortable, but the
*proof object* explodes: the core LRAT alone is 2.2 GB xz — 11× the record
profile's 200 MiB stored cap — and the formally-verified check takes 3.9 h,
3.9× the 3600 s checker cap. So **no `m = 8` row is in the harness band**:
the `Hc = 6, Hh = 7` certificate (`F(S,8)`) goes through the maintainer
re-check of architecture §13.9 (the encoder band keeps `(20, 8)` exactly for
that path). The m=7 row, by contrast, validates the whole record band: it is
the heaviest `m = 7` instance in the class (the 20-cell shapes are lighter —
the 20-iamond `F(S,7)` is 54 M clauses), and it clears every budget with
5–10× margin.
