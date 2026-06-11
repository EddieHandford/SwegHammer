# Analysis toolbox — sweep this list in every diagnostic and research pass

**User directive (2026-06-10): considering these tools is part of the research process.**
Every residual diagnosis, research briefing, and adjudication should state which of these
tools were consulted and why each was used or skipped. Aggregate win rates hide what the
visual and instrument tools catch (the unit-stacking bug and the empty-marker gap were both
found by renders, not metrics). A new diagnostic tool is added to this file in the same
pull request that creates it.

## 1. Visual board-state renders (the eye catches what aggregates hide)

| Tool | What it reveals |
|---|---|
| `scripts/diag_render_displacement.py` | Board renders at three game phases for four matchups plus scoring tails. Standing question: "what is wrong with this board state?" |
| `scripts/diag_render_collision.py` | The original collision-era renderer; before/after renders are the visual anti-regression check for movement changes. |

## 2. Game-shape signatures (second axis of truth beyond win rates)

| Tool | What it reveals |
|---|---|
| `scripts/diag_signatures.py` | Sim scoring shape vs real reference values in `docs/REAL_META_SIGNATURES.md`: mean primary, going-first win rate, mean secondary, per-round trajectory, margin distribution. First full run found secondary saturation (38.3 vs real 22.7) and a going-first bias (63.8% vs real ~50%). |

## 3. Mechanic instruments (gated, observation-only)

| Tool | What it reveals |
|---|---|
| `SWEG_DISPLACE_INSTR` + `scripts/diag_displace_instr.py` | Per-marker fight-outcome classification: loser-held under-pole / uncontested durable hold over-pole / faithful tarpit, summed to per-faction displacement-addressable victory points. The first measurement of per-marker control anywhere (no public reference exists). |

## 4. Measurement stack (evals and statistics)

| Tool | What it reveals |
|---|---|
| `scripts/evaluate_vs_meta.py --use-archetype --log-games` | The headline: per-faction win rates vs the tournament aggregate, noise-gated mean absolute error. Always log games. |
| `--factions` scoping | Runs only a changed faction's row and column (about one tenth of the matrix); valid only for genuinely faction-localised changes. |
| `scripts/paired_delta.py` | Common-random-numbers paired comparison against a saved anchor log; real effects decisive at N=40. |
| `scripts/paired_sequential.py` | Sequential early-stop wrapper for cheap reject/keep verdicts. |
| `scripts/regression_sentinel.py` | Rolling check that previously-landed mechanics have not silently regressed. |
| Per-gate decomposition on existing logs | Re-reads logs already on disk to attribute a delta gate by gate — zero new evaluations. Check for an existing log before every run. |

## 5. One-question diagnostic scripts (about forty, `scripts/diag_*.py`)

Board control (`diag_boardcontrol`, `diag_ocflip`, `diag_reach`, `diag_contest_faction`),
kill chain (`diag_overshooter`, `diag_underoutput`, `diag_durability`, `diag_knight_survival`),
scoring (`diag_secondary_breakdown`, `diag_tacdeck_achieve`, `diag_overscore`),
list realism (`diag_list_realism`, `diag_am_composition`, `diag_antitank_pick`),
mechanics (`diag_battleshock`, `diag_tarpit_fires`, `diag_scout_presence`),
umbrella (`diag_multimetric`). Reuse before writing a new one.

## 6. Ground truth and audits

| Tool | What it reveals |
|---|---|
| `data/bsdata/cache/*.cat.gz` | Verbatim datasheet and rule text — the canonical stat source; cross-check at least two sources before any fabrication claim. |
| Wahapedia (live fetch) | Rule prose, stratagem lists, frequently-asked-question clarifications; may be unreachable from agent worktrees — orchestrator fetches. |
| `scripts/audit_rules.py` | Every rule-bearing flag has a verbatim citation (blocking pre-commit hook). |
| Test suite (1,315 tests) + `run.py --cli` + catalogue import smoke | Correctness floor before any push. |
| `scripts/sim_motion_proof.py` | Deterministic motion-proof fingerprint. Runs a fixed bundle of five seeded battles in-process and prints one secure-hash fingerprint of the full per-battle record. Used to prove that a pure code-motion refactor of the simulator (see `docs/SIM_MODULARIZATION_PLAN.md`) changed no observable behaviour: the fingerprint must match the recorded baseline byte for byte after every extraction. Seeds explicitly, mirroring the calibration evaluation's per-pair seeding, because `run.py --cli` does not seed and so is not reproducible. |

## 7. Event stream and research agents

| Tool | What it reveals |
|---|---|
| `--log-games` event stream (`UnitActivated`, `ObjectiveScored`, `RoundEnded`, …) | The substrate for new zero-rerun analyses — renderers and the signature harness both parse it. Prefer building on it over running new games. |
| Deep-research agents (Goonhammer, Stat Check, Metawatch, Wahapedia) | The WHY behind a residual — real-meta behaviour and reference values. Research claims about missing mechanics must be grounded in code before any build. |
