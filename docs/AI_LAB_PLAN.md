# AI Lab — genetic-algorithm duel sandbox

## What this is

An exploratory sandbox where a genetic algorithm evolves small, readable
piloting knobs for one Intercessor Squad against a frozen baseline strain,
over seeded five-model mirror duels. Champions that clearly beat the
baseline are promoted to *be* the new baseline, and the succession of
promoted champions forms a strain lineage.

**This is explicitly outside the two-stage calibration pipeline.** It never
touches `data/calibrated_points.json`, `data/equilibrium_points*.json`, or
the tournament mean-absolute-error gate, and it needs no
`data/rule_citations.json` entries: nothing in it models a Warhammer 40k
rule. It is an artificial-intelligence tuning layer riding test hooks, the
same category as the pre-existing `Battle._pilot_focus` hook.

## Where things live

| Piece | Path |
|---|---|
| Genome (gene vector, mutation, crossover) | `code/ai_lab/genome.py` |
| Pilot layer (wires a genome onto a `Battle`) | `code/ai_lab/pilot.py` |
| Seeded duels (the fitness primitive) | `code/ai_lab/duel.py` |
| Genetic-algorithm engine + epoch loop | `code/ai_lab/ga.py` |
| Persistence (lineage comma-separated-values file, run snapshots) | `code/ai_lab/history.py` |
| Headless command-line runner | `scripts/ai_lab_run.py` |
| Dashboard tab | `app.py` ("AI Lab" tab) |
| Tests | `tests/test_ai_lab_pilot_hooks.py`, `tests/test_ai_lab_ga.py`, `tests/test_ai_lab_epoch.py` |
| Lineage record (one row per promoted champion) | `docs/ai_lab_lineage.csv` |
| Per-run snapshots (full generation detail) | `data/ai_lab_runs/<run_id>.json` |

Quick start:

```
python -m scripts.ai_lab_run                      # small default run
python -m scripts.ai_lab_run --population 30 --generations-per-epoch 40 \
    --duels-per-genome 20 --epochs 5 --seed 12345
```

or open the "AI Lab" tab in the Streamlit dashboard.

## The genome — five genes in version 1

Every gene is a numeric knob on one *specific existing* decision heuristic,
and every gene's override is **structurally skipped at its neutral value** —
so the neutral genome reproduces production behaviour byte-for-byte
(`tests/test_ai_lab_pilot_hooks.py` proves this event-for-event, and the
liveness of each gene in the flagship Intercessor mirror was verified
empirically by event-stream hashing).

| Gene | Neutral | Range | What it scales |
|---|---|---|---|
| `charge_aggression` | 1.0 | 0.4 – 2.5 | Multiplies melee damage-per-activation in `Battle._wants_to_charge` before the `max(ranged, 1.0)` comparison. The mirror flip point is about 0.79 — below it, Intercessors stop wanting to charge. |
| `charge_range_buffer` | 1.0 | 0.4 – 2.0 | Scales the 12-inch charge-threat buffer in `pick_move_intent`'s DUAL branch (via `_dual_engage_target`). |
| `melee_engage_score_min` | 1.0 | 0.2 – 20.0 | Scales the 0.1 melee-target-score acceptance threshold in the same branch. Range calibrated to the mirror: the raw Intercessor-versus-Intercessor score is about 1.19, so the veto goes live near gene value 11.9 — the range must reach past that or the knob is dead in the flagship duel. |
| `advance_vs_hold_bias` | 0.0 | −4.0 – +4.0 inches | Nudges a HOLD intent toward (positive) or away from (negative) the nearest enemy, capped at the unit's move; executed as REPOSITION so the move executor carries it out and its legality clamps apply. |
| `kite_hold_range` | 0.0 | 0.0 – 8.0 inches | Stand-off slack: on an ENGAGE intent, a ranged-dominant unit (under its own gene-scaled charge check) already inside weapon range holds instead of closing, provided staying keeps at least this many inches clear beyond engagement range. Structurally skipped at zero or below. |

Gene interactions worth knowing: `kite_hold_range` only fires for a unit
that does *not* want to charge under its own `charge_aggression` — so in the
Intercessor mirror (which charges at neutral), kiting is only reachable in
combination with a lowered `charge_aggression`. That pairing is a genuine
strategy the genetic algorithm can discover, not a bug.

### Deferred future genes (named so they are not forgotten)

| Future gene | Hook | Why deferred |
|---|---|---|
| `focus_target_bias` — which enemy model or unit to focus fire (the expansion axis the project owner flagged) | The existing `Battle._pilot_focus` hook, overriding shoot-target choice in `_do_shoot`. | In a bare Intercessor mirror the shoot-target formula already collapses to "lowest effective health", so the gene adds little until the sandbox generalises past the mirror. Cheapest future gene — the hook already exists. |
| `charge_target_bias` — whom to charge | Would need a third hook wrapping `pick_charge_target` inside `_do_charge`. | Version 1's `_pilot_charge` governs only *whether* to charge; in a mirror duel there is effectively one enemy squad, so a whom-gene is meaningless until mixed armies are fielded. The whether/whom split is a decision, not an oversight. |
| `cover_seek_radius_bonus` — widen the cover-snap search radius | Would ride `_best_nearby_cover_point`'s `search_radius` parameter. | `pick_move_intent` returns an already-snapped position; the pilot hook never sees the pre-snap centre, so a faithful neutral no-op cannot be proven from outside. Needs `pick_move_intent` to expose the pre-snap base position first. |

## The hooks

All three attachment points follow the `Battle._pilot_focus` precedent: an
attribute production code never sets, consulted through
`getattr(..., None)`, byte-identical when absent.

* `Battle._pilot_charge` — consulted in `_do_charge` just before
  `_wants_to_charge`; returns True/False to override *whether* the unit
  wants to charge, or None to defer.
* `Battle._pilot_move` — consulted in `_do_move` immediately after
  `pick_move_intent`; sees the baseline `(target_pos, intent)` and may
  replace it. Downstream processing (make-way spread, staging, the
  production kiting gates) applies to the override exactly as it would to
  the baseline decision.
* `Army._ai_lab_dual_scales` — a `(threat_buffer_scale, score_min_scale)`
  pair read *inside* `pick_move_intent`'s DUAL branch. Scaling inside the
  branch — rather than post-hoc in the pilot callable — is what lets a
  narrowed pick fall through to the objective-scoring logic naturally,
  exactly as a genuinely out-of-range target would.

Both sides of every duel always get a pilot attached; the "baseline" is
simply whichever genome is neutral (epoch one) or the previously promoted
champion (every epoch after). There is no special-cased unhooked side.

**Standing caution — `SWEG_SQUADACT`.** `pick_move_intent` is also called at
the squad-level move-decision cache in `code/simulator.py` (the
`SWEG_SQUADACT` stage-A precompute). That call is inert today — the cache is
populated but never applied — but if a future squad-rebuild stage starts
applying it, the pilot's move override would be silently bypassed.
`code/ai_lab/pilot.attach` and `run_duel` therefore refuse to run (raise
`RuntimeError`) when `SWEG_SQUADACT=1`. Graduating the squad-activation
cache requires wrapping that call site with the same pilot consultation.

### Squad cohesion under `_pilot_move`

Two related findings from manual testing, pulling in opposite directions.
Both are pinned by tests in `tests/test_ai_lab_pilot_hooks.py`'s
`SquadCohesionTests`.

**Finding 1 — ENGAGE-target divergence (a real bug, fixed).** Any gene on
the charge-desire axis (`charge_aggression`, `charge_range_buffer`,
`melee_engage_score_min`) can suppress the single-round charge Intercessors
normally take, forcing a multi-round *walk* instead. While walking, the
DUAL branch's per-model choice of WHICH ENEMY MODEL to engage
(`_dual_engage_target`) is computed independently per model — verified to
already be true of an **unmodified baseline battle** with a naturally
non-charging DUAL-role unit (Drukhari Wracks show the same splitting with
zero AI Lab code involved), so this is a pre-existing simulator
characteristic. Squad members only a few inches apart can rank enemies
differently and walk toward different models, splitting the squad far
beyond what `Battle._enforce_squad_coherency`'s post-move nudge can repair.
Fix: the `walk_targets` per-round, per-squad cache in `code/ai_lab/pilot.py`
shares the first squad member's own baseline ENGAGE target with the rest —
structurally inert (never populated) whenever all three charge-axis genes
sit at neutral.

**Finding 2 — CAPTURE/STEAL-target divergence must NOT be coordinated the
same way (a second, more severe bug, found and reverted).** The natural
instinct — extend the same "share the first squad member's target" fix to
`CAPTURE`/`STEAL` — was tried, and it broke the sandbox almost completely.
Individual squad members legitimately picking DIFFERENT objective markers
is not a defect: it is how a squad spreads across the board to hold
multiple objectives and score Victory Points, and the frozen baseline
opponent in every duel relies on exactly this behaviour to win. Forcing the
whole squad onto one shared `CAPTURE`/`STEAL` target glued every model onto
a single objective marker, so a genome forfeited three or four objectives'
worth of Victory Points to the baseline every game — regardless of how good
its underlying tactics were. Because `melee_engage_score_min`'s range
(0.2-20.0) essentially never lands exactly on its neutral value of 1.0 for
any mutated or randomly-initialised genome, this fired on almost every
genome the search ever produced: measured win rate against the neutral
baseline collapsed to roughly 6-10% even for a genome differing from
neutral by less than 1% in a single gene, in **either** direction and at
**any** magnitude (verified with `charge_aggression=0.99`,
`charge_range_buffer=1.06`, and `melee_engage_score_min=0.2` all producing
the identical catastrophic win/loss/draw split). **This — not the
promotion-gate math in the section below — was the actual cause of every
evolution run reporting "epoch exhausted without a promotion" regardless of
parameters.** The immediate revert was to never build the
`CAPTURE`/`STEAL` half of the coordination cache; finding 3 below then
reinstated walk coordination the RIGHT way (both sides, always) — the
lesson of finding 2 is not "never coordinate objectives" but "never
coordinate them for one side only".
`SquadCohesionTests.test_capture_target_is_not_coordinated` pins the
gene-gated regime's asymmetry directly, and
`test_tiny_perturbation_does_not_collapse_win_rate` is the regression
guard against reintroducing any one-sided handicap.

**Finding 3 — the resolution: squad-move-as-unit, both sides, always.**
Finding 2's revert restored fair fitness measurements but left the
user-visible scatter (models walking to different objectives), which the
project owner rejected on watchability and fidelity grounds — real 10e
Unit Coherency (every model within two inches of a squadmate) flatly
forbids one squad parking models on markers twenty inches apart; the
scatter is an infidelity of the calibration simulator's one-Unit-per-model
representation that its post-move coherency nudge cannot fully repair once
a model has spent its whole move walking elsewhere. The resolution
threads the needle both earlier attempts missed: coordinate every walk
intent (`CAPTURE` / `STEAL` / `ENGAGE`) once per squad per round, but
apply it to **both sides symmetrically, always, regardless of genome** —
a harness-level rule of the AI Lab duel (`squad_move_as_unit=True`, the
default on `pilot.attach` and `duel.run_duel`), not a gene side-effect.
Symmetry is what makes it fair: the frozen baseline plays under exactly
the same movement discipline as every challenger, so nobody forfeits the
Victory Point race (finding 2's failure), and squads visibly move as one
body (finding 1 and the owner's request). Measured: mean squad spread
1.0-2.1 inches across seeds under active genomes (the calibration
representation's per-model walks measured 4.5-9.5 inches), the
neutral-versus-neutral mirror still washes to about 0.47 at two hundred
duels, and the gene landscape stays live — a pure
`advance_vs_hold_bias=-3` genome measures a genuine 0.68 win rate under
the new regime while an over-extending `charge_range_buffer=2.0` is
punished at 0.27. One deliberate side effect: cohesive mirrors draw far
more often (about seventy percent of neutral-mirror duels), since two
one-squad armies each holding one marker tie on Victory Points — draws
count half a win in the fitness signal and the margin term breaks ties,
so the search still discriminates. Passing `squad_move_as_unit=False`
(used by the hook-inertness tests) restores the strict
byte-identical-at-neutral regime with only finding 1's narrow, gene-gated
ENGAGE coordination. Position-relative intents (`HOLD` / `REPOSITION` /
`FALL_BACK`) are never coordinated in either regime.
`SquadMoveAsUnitTests` in `tests/test_ai_lab_pilot_hooks.py` pins the
symmetric-coordination behaviour, the lone-model exemption (lone models
key their decision caches by their own identity, never sharing a slot),
and the real-battle spread bound.

## The duel

Five-model Intercessor Squad versus five-model Intercessor Squad on the
default map, one squad each (`build_homogeneous_army` with an explicit
`squad_size=5` — its default would field the ten-model maximum). Duels run
under the squad-move-as-unit regime (`run_duel(...,
squad_move_as_unit=True)`, the default): both sides' squads pick one
shared walk target per round — see "Squad cohesion under `_pilot_move`",
finding 3.

Seeding follows the evaluation-protocol discipline (paired common random
numbers): `duel_seed(epoch, generation, duel_index)` is plain integer
arithmetic over *when* the duel happens, never over which genomes fight, so
every genome in a generation faces the exact same dice. Confirmation
batches use a disjoint seed lane (`CONFIRMATION_LANE`) so a champion is
never confirmed on the dice it was selected on. All genetic randomness
(selection, crossover, mutation) comes from a dedicated `random.Random`
instance, never the global module — the exact lesson recorded in
`docs/PILOT_FINDINGS.md`.

## The loop

1. Population of genomes (default twelve), Gaussian-jittered around the
   current baseline.
2. Each generation: every genome fights the baseline over
   `duels_per_genome` seeded duels, alternating sides. Fitness = win rate
   (draws count half) plus `margin_weight` times the mean points-remaining
   margin.
3. Elitism keeps the top genomes unchanged; the rest of the next generation
   is tournament selection, blend crossover, Gaussian mutation.
4. Promotion gate: when a generation's champion clears the promotion
   threshold on its cheap in-generation read, a fresh-seed confirmation
   batch (default five hundred duels) re-measures it. Promotion requires the
   confirmation point estimate to clear the threshold *and* its Wilson
   95 percent lower bound to clear 0.5 — "clearly better" and "not just
   noise".
5. On promotion the champion becomes the baseline, the population reseeds
   around it, and one row lands in `docs/ai_lab_lineage.csv`. An epoch that
   exhausts its generation budget without promoting ends the lineage.

The whole loop is exposed as the generator
`code/ai_lab/ga.py::evolve_lineage`, which yields
`("generation" | "confirmation" | "promotion" | "epoch_exhausted", payload)`
events — the headless runner and the dashboard tab both drive this one
implementation.

### Promotion-gate consistency

A real bug found in manual testing: the two promotion-gate conditions
(confirmation win rate clears `promotion_threshold`; the Wilson 95 percent
lower bound clears 0.5) are **not automatically consistent with each
other**. At a small confirmation sample size, a win rate sitting exactly at
the threshold can have a Wilson lower bound *below* 0.5, making promotion
mathematically impossible regardless of how good the evolved genome
actually is. The version that shipped first had exactly this defect:
`confirmation_n=200` at the default `promotion_threshold=0.55` gives a
Wilson lower bound of 0.4808 — always below 0.5 — so every run reported
"epoch exhausted without a promotion," no matter how good the search got at
finding genuinely better genomes (confirmed empirically: a 25-generation,
20-population run regularly found genomes scoring 0.55-0.70 on the cheap
in-generation read, none of which could ever have promoted under the old
defaults).

`code/ai_lab/ga.py::min_confirmation_n_for_threshold(promotion_threshold)`
computes the smallest `confirmation_n` at which the gate is even
mathematically satisfiable (385 for the default 0.55 threshold).
`evolve_lineage` calls it at the start of every run and raises `ValueError`
immediately — before running a single generation — if `confirmation_n` is
below that minimum, so a bad configuration fails loud instead of silently
burning a full epoch's compute on an unwinnable search (CLAUDE.md rule 13).
The shipped default `confirmation_n` (`DEFAULT_CONFIRMATION_N` in
`code/ai_lab/ga.py`) is five hundred, comfortably above the 385 minimum.
The Streamlit tab's Advanced-parameters panel shows the live minimum for
whatever threshold is selected and disables Run below it, and
`scripts/ai_lab_run.py --confirmation-n` inherits the same default and the
same validation.

Reproducibility: given `PYTHONHASHSEED=0` (the command-line runner re-execs
with it pinned; launch Streamlit with it set for exact identity), the same
seed and parameters reproduce the same lineage end to end.

## Delivery checklist

- [x] Pure code motion: extract `_dual_engage_target` from
  `pick_move_intent` (proven byte-identical over thirty seeded battles).
- [x] Hook substrate + genome + pilot layer, with the neutral-genome
  byte-identity regression guard and one behaviour test per gene.
- [x] Fitness + genetic-algorithm engine + headless runner.
- [x] Epoch loop, promotion gate, lineage + run-snapshot persistence.
- [x] Dashboard "AI Lab" tab: live per-strain survival chart (one line per
  genome, elites continue their line, a culled strain's line stops, gold =
  current best, hover shows gene values; rebuilt in place each generation
  inside the streaming fragment), champion-versus-baseline replay
  (round-overview reuse), lineage table, plain-language glossary panel.
- [x] Squad-move-as-unit duel regime (finding 3): squads walk as one body
  on both sides symmetrically; measured mean spread 1.0-2.1 inches under
  active genomes versus 4.5-9.5 inches under per-model walks.
- [x] Verified end-to-end after the fixes documented in "Squad cohesion
  under `_pilot_move`" and "Promotion-gate consistency": a real
  `scripts.ai_lab_run` run (population 20, duels per genome 20,
  generations per epoch 25, seed 42) produced a genuine promotion at
  epoch 0 generation 9 — confirmation win rate 0.580 at n=500, Wilson
  lower bound 0.536 — with confirmation win rates across both epochs
  clustering sensibly around 0.42-0.58 rather than being universally
  crushed below 0.45 as they were before the CAPTURE/STEAL-coordination
  bug was found and reverted.
- [ ] Deferred: `focus_target_bias` shoot gene via `_pilot_focus`;
  `charge_target_bias`; `cover_seek_radius_bonus` (needs the pre-snap
  centre exposed); background-subprocess mode for very long runs that
  should survive a page reload.
