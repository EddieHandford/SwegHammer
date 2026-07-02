# Avenue 2 — Physical Board-Control: staged implementation plan

**Status:** drafted 2026-06-06 (Plan agent, watchdog-reviewed). Reference doc for the
worker to execute wave-by-wave. This is the user-directed avenue-2 lever for the Imperial
Knights over-hold residual (production frame = the primary-mission deck rotation,
`SWEG_PRIMARY_DECK`, gated MAE ~4.89; IK still ~19.7 over).

**Goal:** add the physical board constraints the sim is missing so realistic displacement
EMERGES from the physics — no-overlap collision, ruin-walls blocking non-INFANTRY movement,
a walls-vs-area terrain model, and a make-way movement planner. Today movement is point-based
and collision-free, and ruins are movement-transparent.

**Rails (non-negotiable):** fidelity-first, every rule cited (rule-10); each stage env-gated
with a byte-identical OFF path; A/B at N=80 vs the deck frame; keep-if-faithful regardless of
metric direction; instrument-first; verify-before-flip with an explicit anti-jam tell.

---

## Orchestrator review notes (read FIRST — additions to the staged plan below)

**A. Generalise the make-way planner (USER STEER 2026-06-06).** Stage 2's coordination layer
must be designed as a REUSABLE coordination/lookahead substrate — "plan across units instead
of greedy per-unit" — so it can later extend to targeting/focus-fire, stratagem (command-point)
spending, objective allocation, and action selection. **Scope the avenue-2 BUILD to movement,
but do NOT architect a movement-only dead-end** (clean interface, not hard-wired to moves).

**B. The charge/pile-in leak is CRITICAL, not optional.** `_do_charge` and pile-in/consolidate
bypass `_move_toward`. If collision lands only in `_move_toward`, chargers and pile-ins phase
through screens and the no-overlap rule LEAKS — screening (a core reason the lever helps the
under-pole) silently fails. Stage 1 MUST route these through the end-overlap check. Measure the
charge-connect rate before/after: a DROP is faithful (screening now works), not a bug — log it
so it isn't mistaken for a regression.

**C. Performance is a real risk to the LOOP, not just runtime.** The sim runs N=80 many times a
day; an O(models²) collision scan can tank iteration throughput. Benchmark with
`scripts/bench_simulator.py` at Stage 1; if the gated path is >1.5× baseline wall-clock, do the
"assemble occupants once per phase" + coarse spatial-bucket optimisation BEFORE proceeding. Don't
let the physics throttle the calibration loop.

**D. Sub-gate / separately A/B the Stage-3 line-of-sight change.** Doorway-gap LoS (segment-LoS
replacing rectangle-LoS) is a DISTINCT behaviour change from wall-movement. Keep it separately
gated (or at minimum separately A/B'd) so a faithfulness regression in one can't hide behind the
other.

**E. The Stage-1-only A/B is DIAGNOSTIC, not keep/reject.** Collision alone WILL jam (expected);
read its A/B as "does collision cap OC packing toward ≤100%?", not as a metric verdict. The real
keep/reject is the paired Stage-1+2 run. Do not revert collision on the Stage-1-only jam (that
would be the frozen-under reflex).

---

## Grounding (what the code does today)

- Movement is point-based + collision-free: `_move_toward` (`code/simulator.py:124-149`) clamps to
  bounds and aborts only if the *destination point* is in `IMPASSABLE` terrain (`map.is_blocked`,
  `map.py:108-113`); it never consults other models. Every move path funnels through it EXCEPT
  charge final placement (`_do_charge:10149-10156`) and pile-in/consolidate (`:10293`,`:10386`,
  `:10401`), which compute landings directly (the leak in note B).
- One Unit per physical model, grouped by `squad_id`; coherency = within `COHERENCY_INCHES=2.0`
  of a squadmate, enforced post-move (`_enforce_squad_coherency:8582`).
- Objective control sums `_effective_oc` (`:1253`) of every model within 3" of a marker; a squad
  credits ONE marker (`_assign_army_oc:885`). Today unbounded point-models stack in a 3" circle —
  exactly where no-overlap bites.
- Base footprints ALREADY exist as data on `UnitProfile` (`units.py:690`: `base_shape`,
  `base_diameter_mm`, `base_width_mm`, `base_length_mm`), derived by `mapper._derive_base_footprint`,
  but documented as RENDERER-ONLY. This plan promotes them into movement — the pipeline exists,
  de-risking Stage 1.
- Terrain is a solid axis-aligned rectangle (`Terrain`, `map.py:63-84`); no wall/segment concept.
  LoS already treats RUIN rectangles as blockers (`_segment_rect_intersects:201`, `_los_query:291`).
- Gate/instrument conventions: `SWEG_COHERE` etc. (default-on, `=0` to A/B), read-only stat dicts
  populated only under a gate (`OCFLIP_STATS:176`, driven by `scripts/diag_ocflip.py`). Eval =
  `scripts.evaluate_vs_meta --use-archetype`, `PYTHONHASHSEED=0`.

---

## Stage 0 — Instrument (read-only, zero behaviour change) — DO THIS FIRST

Build `scripts/diag_boardcontrol.py` modelled on `scripts/diag_ocflip.py`, + a read-only
`BOARDCONTROL_STATS` accumulator in `simulator.py` (mirroring `OCFLIP_STATS`), populated only when
`SWEG_BOARDCTRL_INSTR=1`, hooked into `_score_objectives` (settled positions) and `_do_move` end.
Measure per objective-round + per faction:
1. **Overlap pressure on objectives** — model-pairs whose base footprints (read `base_diameter_mm`,
   25.4 mm/in) overlap while both within 3"; plus *summed base area within 3" vs the 3"-circle area*
   (a >100% packing ratio = OC that no-overlap will physically cap). Sizes lever #1 + predicts the
   OC-stacking reduction.
2. **Big-model paths crossing ruin footprints** — `_do_move` activations where a VEHICLE/MONSTER/
   TITANIC (no FLY) start→end segment crosses a RUIN rect (reuse `_segment_rect_intersects`). Sizes
   levers #2/#3.
3. **OC concentration on contested markers** — holder model-count + packing ratio where both sides
   have OC; cross-ref `OCFLIP_STATS` flippable%.
4. **Jam baseline (anti-regression yardstick)** — per faction: mean models ending the game still in
   their own DZ, and mean min squad→nearest-objective distance at game end. Stages 1-4 must not move
   these the wrong way. This is the "units-still-reach-objectives" tell.

**Gate:** clean under `PYTHONHASHSEED=0 SWEG_BOARDCTRL_INSTR=1`; OFF path byte-identical (N=40 MAE
unchanged). Output drives the build order. **Risk: none.**

---

## Stage 1 — Base footprints + no-overlap collision (`SWEG_COLLISION`, default-OFF, HELD)

Promote base dims into `_move_toward`: pass the mover + occupant list (other alive models'
position/radius/is_enemy/has_fly). New end-validation — if the destination would leave the mover's
footprint overlapping any model, or end within Engagement Range (1") of an enemy, walk the
destination back along the travel vector to the last legal point (deterministic bisection, capped
iterations). FLY skips the enemy-overlap/ER test; non-FLY may pass THROUGH friendlies mid-segment
(only the END matters) but not through enemies. Keep the impassable check. Wire the gate through
ALL `_move_toward` callers AND (note B) `_do_charge` landing + pile-in/consolidate.

**Deps:** Stage 0. **HELD default-OFF until Stage 2 lands — flips ON paired with Stage 2.**
**A/B (diagnostic, note E):** N=80; re-run `diag_boardcontrol` with `SWEG_COLLISION=1` — packing
ratio must drop toward ≤100% AND IK over-hold OC must fall; jam metrics WILL worsen (expected).
**Risks:** jamming (silent regression — the jam tell guards it); charge-connect rate falls (measure
it; faithful = screening works).

---

## Stage 2 — Make-way movement planning (`SWEG_MOVEPLAN`, default-OFF → ON paired with Stage 1)

The coordination layer so collision doesn't jam. In the movement phase (`:8364-8398`, where
`pick_move_intent` is deterministic + side-effect-free and `_squad_move_intent` caches intents):
(a) order moves so models targeting the closest reachable objective slot move first; (b) when a
mover is blocked by a friendly at its target, the blocker takes a small shuffle within its own
remaining budget (like the coherency pull `:8630-8635`) to vacate, then the mover proceeds. Reuse
`effective_move` (`detachments.py:2113`) + remaining-move accounting. NO new RNG (determinism).
**Design per note A: a reusable coordination substrate, movement-scoped build.**

**Deps:** Stage 1. **These two flip default-ON as a PAIR.**
**A/B + tell:** N=80 `SWEG_COLLISION=1 SWEG_MOVEPLAN=1` vs Stage-1-only AND vs the deck frame. The
decisive tell: jam metrics return to AT-OR-BETTER than the no-collision baseline (make-way un-jams);
OC packing stays capped. If reach is restored AND IK over-hold narrows → flip the pair ON.
**Risk:** the planner must stay a physical-space un-jammer (sequencing + step-aside within legal
budget, no strategic look-ahead) or it becomes its own fidelity violation. Order by `(squad_id,uid)`.

---

## Stage 3 — Terrain WALLS vs AREA data model (`SWEG_RUINWALLS` data, default-OFF)

Split the solid `Terrain` rect into AREA/footprint (cover + standable interior; existing
`contains`/`cover_at`/"wholly within") and WALL line-segments (block non-INFANTRY movement + LoS;
gaps = passable). Add `walls: Tuple[Wall,...]` to `Terrain` (default empty → existing maps
unchanged) + `Map.wall_segments()`. Encode real per-ruin wall layouts in `maps._competitive_terrain`
(`:59-122`) from the Pariah Nexus / CA-2025-26 terrain pack (the L-shaped two-storey ruins the
docstring describes), as segments WITH gaps (doorways), gated so OFF emits today's bare rects.
Renderer (`:434-443`): draw walls as distinct segments over a translucent footprint. **LoS (note D):
keep rectangle-LoS as the OFF default; segment-LoS (doorway gaps) only under the gate, separately
A/B'd.** This stage is DATA + plumbing only — no movement change yet.

**Deps:** independent of Stages 1-2 (parallelisable). **MUST precede Stage 4.** `_los_cache` keys on
`_terrain_epoch` (new terrain tuple → new epoch → cache stays correct; confirm no stale reuse).
**A/B:** N=80 `SWEG_RUINWALLS=1`; small shooting uptick expected from doorway LoS (keep-if-faithful);
eyeball-render walls-with-gaps + footprint cover. **Risk:** hand-encoded layouts are a fidelity
surface — cite the exact terrain-pack page; keep the 180° rotational symmetry `_competitive_terrain`
already uses (`:114-121`).

---

## Stage 4 — Ruin walls block non-INFANTRY movement (`SWEG_RUINWALLS` logic, ON paired with Stage 3)

Extend the Stage-1 check: a non-INFANTRY/non-BEAST/non-FLY mover may not have its start→end segment
cross a movement-blocking wall (add `_segment_segment_intersects` to `map.py`); on rejection, walk
back to before the crossing. INFANTRY/BEAST/FLY pass through. Minimum viable = "stop at the wall"
paired with make-way (don't jam); a full route-around pathfinder is OUT OF SCOPE (note it only if
the jam tell shows big models stuck on walls).

**Deps:** Stage 3 (wall data); benefits from Stage 2. **Sequence 3 → 4; flip ON paired with Stage 3.**
**A/B + tell:** N=80; `diag_boardcontrol` metric #2 — VEHICLE/MONSTER through-wall crossings → ~0
(interior/gap crossings still allowed); big-model squad→objective distance must not blow up. **Risk:**
big models stuck against a wall → fidelity regression; mitigate with make-way + retry toward a gap.

---

## Cross-cutting risks & interactions

- **Collision × coherency:** the coherency pull uses `_move_toward`; under collision it can be
  blocked → model stays non-coherent → 0 OC. Make-way must run before/interleaved with coherency;
  track coherency-violation rate in `diag_boardcontrol`.
- **Collision × OC-within-3" (the intended lever):** no-overlap caps bases in a 3" circle → caps
  summed OC → attacks the IK over-hold (the Knight's huge base excludes over-stacking bodies). Watch
  over-correction via the packing ratio (cap must be physical ≤100%, not an arbitrary OC nerf); a
  squad pushed off a marker must still credit OC to a reachable marker.
- **Collision × charge/pile-in (note B):** route those through the end-overlap check or the rule
  leaks; expect (and log) a charge-connect drop.
- **Performance (note C):** assemble occupants once per phase, not per model; spatial bucket if
  `bench_simulator.py` shows >1.5×.
- **Determinism:** zero new RNG; order iteration by `(squad_id, uid)`, never `id()`/set-iteration.

---

## Citations needed (rule → source) — rule-10; do NOT invent, stop-and-ask if unsourceable

1. `simulator.collision_no_overlap` — Wahapedia core, Making a Move: "it cannot end its move on top
   of another model" + "can be moved through friendly models".
2. `simulator.engagement_range_placement` — core: "Models cannot be set up or end a Normal, Advance
   or Fall Back move within Engagement Range of any enemy models."
3. `simulator.fly_move_over` — core, FLY: "can be moved over enemy models as if they were not there".
4. `terrain.ruin_wall_movement` — **TERRAIN rules, NOT core-rules** — GW Pariah Nexus / CA-2025-26:
   INFANTRY/BEASTS can move through ruin walls; VEHICLES/MONSTERS cannot. Verify exact 2025-26 wording
   before coding (wall-vs-floor traversal wording changed across editions).
5. `terrain.competitive_pariah_nexus_layout` (exists, `maps.py:73`) — extend with the per-ruin
   wall-segment source (the Pariah Nexus Tournament Companion measured layouts in the docstring).
6. Make-way coordination = AI heuristic, NOT a 10e rule (like posture/coordinated-plan): code-comment
   only; the constraints it respects reuse `simulator.unit_coherency` / `coherency_enforcement`.

---

## Ordering

| Order | Stage | Gate | Default | Flip-on |
|---|---|---|---|---|
| 0 | Instrument | `SWEG_BOARDCTRL_INSTR` | OFF | n/a (read-only) |
| 1 | Collision / no-overlap | `SWEG_COLLISION` | OFF (built, held) | with Stage 2 |
| 2 | Make-way planning | `SWEG_MOVEPLAN` | OFF → ON paired with 1 | jam ≥ no-collision baseline AND A/B faithful |
| 3 | Terrain WALLS/AREA data | `SWEG_RUINWALLS` (data) | OFF | with Stage 4 |
| 4 | Ruin-wall movement | `SWEG_RUINWALLS` (logic) | OFF → ON paired with 3 | through-wall crossings → ~0, no big-model jam, A/B faithful |

Hard constraints (both honoured): collision (1) never lands without make-way (2) — flip as a pair;
terrain data (3) precedes wall-logic (4). Pairs 1-2 and 3-4 are independent (parallelisable), each
flips only after its own N=80 A/B is faithful and its anti-jam tell passes. Keep-if-faithful.

**First move:** Stage 0 — `scripts/diag_boardcontrol.py` + the read-only hook. No behaviour-changing
code until the packing-ratio + jam-baseline numbers exist.
