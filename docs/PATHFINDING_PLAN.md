# Pathfinding — staged implementation plan (unblocks avenue-2 collision + ruin-walls)

**Status:** drafted 2026-06-06 (Plan agent, watchdog-reviewed). USER authorized investing in real big-base
pathfinding to unblock board-wide collision (which crashed big-base reach 52%→16-20% across 4 make-way attempts)
AND the ruin-walls Stage 4 (they share the big-base-navigation dependency). This is the over-pole main thrust.
Companion to docs/BOARD_CONTROL_PLAN.md (whose collision Stages 1-2 + walls Stage 4 this unblocks).

---

## Orchestrator review notes (read FIRST)

**A. The Stage-3 keep/reject is NOT "reach restored" — it's "does collision HELP the over-hold."** Restoring Knight-reach
toward 52% is NECESSARY but NOT SUFFICIENT. The whole point (per the user) is to let collision narrow the IK over-hold. But the
diagnostic showed the over-hold is an UNDER-CONTEST problem and a 170mm Knight base could ENTRENCH (deny bodies the 3" contest
ring) even when it navigates fine. So **Stage 3's real keep/reject = the entrenchment render (opponent bodies within 3" of the
marker TOKEN around the Knight, before/after) + the IK over-hold delta + the headline — NOT just reach%.** Collision could
restore reach AND still entrench AND not help the over-hold; if so, that's the contest-geometry to fix (count center-within-3"-
of-token even when the Knight base fills the circle), and collision's over-hold value stays unproven until the bodies actually
contest. Don't declare victory on reach% alone.

**B. Stage 0 is a genuine GO/NO-GO feasibility gate, not just "size the budget."** If Stage 0 shows blocked-big-base-move
frequency × per-call A* cost blows ≤1.5× even coarse, board-wide collision-via-pathfinding may be infeasible for the loop's
throughput. If so, STOP and report (the investment doesn't pan out perf-wise) BEFORE sinking waves into Stages 1-5. Treat the
three Stage-0 numbers (reach baseline, blocked%, per-call cost) as the GO decision.

**C. Multi-wave Tier-3 — pace it, gate every stage.** Stage-by-stage with the ≤1.5× perf gate + determinism check + the A/B at
each flip. Verify-before-flip. Don't rush the flip-set (Stage 3).

---

## Algorithm: coarse integer-inch grid A*, blocked-moves-only, big-bases-only, per-phase obstacle grid, bounded expansions

The deployed "pathfinder" today is the FAILED 6-angle sidestep inside `_move_toward` (`simulator.py:184-227`) — purely local
(one ring around the immediate blocker), so a Knight facing a wall of blockers (screen + ruins) dead-ends. Replace it (for big
bases) with coarse grid A* that searches the connected free space and routes a multi-cell detour. Why grid-A* over alternatives:
the 6-angle steering is what's deployed and FAILED; a visibility graph would need constant rebuilds (obstacles are dynamic
per-phase model footprints); fine-grid A* tanks the loop (explicit FAIL). Coarse 1-2" cells + a bounded window + capped
expansions keeps each call cheap.

Perf containment (the four levers): (1) **blocked-only** — straight-line check stays O(1), pathfinder fires only on the blocked
minority; (2) **big-bases-only** — small INFANTRY keep the existing O(1) sidestep (never the problem); (3) **per-phase obstacle
grid** assembled once from the `_collision_kwargs` occupant list, cached by (turn, phase, mover-radius-bucket); (4) **bounded
expansions** (cap ~400, search radius = move+~3" slack) → graceful on boxed-in (best partial cell / stay put, never hang).
Determinism: A* tie-break `(f, g, cell_index)`, heapq, occupants in (friendly, enemy)→alive_units order, ZERO RNG. Gate
`SWEG_PATHFIND` (default-OFF byte-identical: fires only when occupants present AND gate set AND mover big AND straight end
blocked — all false on production today). Config-space expansion (inflate footprints by the mover radius → treat the Knight as
a point).

---

## Stages

**Stage 0 — Perf/feasibility spike + the missing Knight-reach metric (read-only). DO FIRST = GO/NO-GO (note B).**
- Add **"Knight-reaches-a-marker%"** to `diag_boardcontrol.py` (it has JAM but not the reach% headline; ~52% collision-OFF
  baseline). 
- Quantify **blocked-move frequency** (a gated counter in `_move_toward`: total vs blocked, big-vs-small) under
  `SWEG_COLLISION=1`, one N=40 sample — sizes the perf budget.
- Add a **boxed-in Knight matchup to `bench_simulator.py`** (Knights vs a horde on competitive terrain — the bench has NO big-
  base case today) + record the OFF baseline ms/battle.
- **Throwaway prototype** of the A* per-call cost on a boxed-in Knight (time 1000 calls). 
- Budget: gated-ON ≤ **1.5× baseline** wall-clock on the bench. Acceptance: the three numbers exist; OFF byte-identical. **GO/NO-GO.**

**Stage 1 — Pathfinder core module + unit test (`SWEG_PATHFIND` built, NOT wired → byte-identical).**
- New `code/pathfind.py` (imports only `map` to avoid a cycle): `find_path(start, goal, max_dist, mover_radius, occupants,
  walls, map_, max_expansions) -> point`. Rasterize occupants (inflated by mover_radius) + walls + impassable into a coarse
  blocked-cell set bounded to a window; A* 8-connected, Euclidean heuristic, deterministic `(f, g, cell_index)`; return furthest
  reachable point along the path within max_dist (validated legal by `_collision_pos_legal`); on cap/no-path → best partial cell,
  never illegal, never loops.
- Determinism unit test (identical output, PYTHONHASHSEED=0). Micro-bench vs the Stage-0 per-call budget. N=80 byte-identical
  (inert). Tests: boxed Knight routes around; open Knight returns straight; walled-in Knight stays put (graceful).

**Stage 2 — Wire into `_move_toward` for big bases (`SWEG_PATHFIND`, default-OFF, A/B vs collision).**
- In `_move_toward` (`:184-227`): when occupants present + straight end illegal + `SWEG_PATHFIND` + mover big (caller `:9292-
  9306` already computes `_big_mover`) → call `find_path` instead of the 6-angle sidestep; small bases keep the sidestep. Plumb
  the per-phase grid cache on `Battle`. Make `_clear_lane` redundant (keep behind a sub-flag for A/B).
- **PERF GATE (critical):** `bench_simulator.py` with `SWEG_COLLISION=1 SWEG_PATHFIND=1` (incl. the Knight matchup) ≤ 1.5×
  baseline; gate stays OFF until in budget (tighten cap / 2" cells / shrink window). Determinism: two PYTHONHASHSEED=0 runs
  identical.
- A/B N=80 (collision+moveplan+pathfind) vs the dead collision+moveplan-only (4.89→6.81 reject) vs deck frame. **Success tell:
  Knight-reach% climbs 16-20% → toward 52%; JAM recovers; headline returns toward 4.89.**

**Stage 3 — Re-enable board-wide collision on the pathfinder + FIX the charge leak (flip-set).**
- Flip `SWEG_COLLISION`+`SWEG_MOVEPLAN`+`SWEG_PATHFIND` together = BOARD_CONTROL_PLAN Stages 1-2 landing on working navigation.
- **Fix the ONE remaining collision leak:** charge final placement (`simulator.py:10628-10636`) bypasses `_move_toward` — route
  it through `_move_toward(..., **_collision_kwargs(attacker, allow_engagement=True))` like pile-in/consolidate/blood-surge
  already do, so big chargers route around screens (faithful screening; log the charge-connect drop, not a bug).
- Perf ≤1.5×. **KEEP/REJECT = note A: the entrenchment render (bodies within 3" of the marker TOKEN around the Knight) + the IK
  over-hold delta + OC packing capped toward ≤100% + headline — NOT just reach%.** Keep-if-faithful. If reach lags 52%, loosen
  the cap before reverting; if it entrenches (bodies pushed out), fix the contest-geometry.

**Stage 4 — Encode ruin wall layouts (`SWEG_RUINWALLS` data, parallelisable; BOARD_CONTROL_PLAN Stage 3).**
- Encode per-ruin `Wall` segments with doorway gaps in `maps._competitive_terrain` (`:59-122`), 180° symmetry, CITED to the
  Pariah Nexus / CA-2025-26 terrain pack (rule-10 / fidelity surface — do it carefully, cite the page). `wall_segments()` is
  empty today. Independent of 1-3 (parallel) but MUST precede Stage 5. LoS sub-gate already built; A/B faithful.

**Stage 5 — Walls block non-INFANTRY movement, routed THROUGH the pathfinder (`SWEG_RUINWALLS` logic; BOARD_CONTROL Stage 4).**
- Feed wall segments into `find_path`'s rasterization (a cell is blocked for a non-INFANTRY/BEAST/FLY mover where a wall crosses
  it); a big mover's straight end crossing a wall → pathfinder routes around to a doorway. INFANTRY/BEAST/FLY pass through.
  Perf ≤1.5×. Success: big-model through-wall crossings → ~0; big-model squad→objective distance doesn't blow up (routed to
  doorways); Knight-reach% holds ≥52%. **This is where pathfinding UNBLOCKS the route-around-walls that BOARD_CONTROL_PLAN
  Stage 4 had deferred.**

## Ordering

| Order | Stage | Gate | Flip-on tell |
|---|---|---|---|
| 0 | Reach metric + blocked% + bench worst-case | `SWEG_BOARDCTRL_INSTR` | read-only; **GO/NO-GO** |
| 1 | Pathfinder core + unit test | `SWEG_PATHFIND` (inert) | byte-identical; tests pass |
| 2 | Wire into `_move_toward` (big bases) | `SWEG_PATHFIND` | reach% → 52%; ≤1.5× bench |
| 3 | Re-enable collision + fix charge leak | `SWEG_COLLISION`+`SWEG_MOVEPLAN`+`SWEG_PATHFIND` | **over-hold narrows + bodies contest (note A)**, not just reach |
| 4 | Encode ruin walls (data) | `SWEG_RUINWALLS` (data) | parallel; LoS A/B faithful |
| 5 | Walls block movement via pathfinder | `SWEG_RUINWALLS` (logic) | through-wall → ~0; reach holds |

## Cross-cutting risks
- **Perf (dominant):** every stage behind the ≤1.5× bench gate; blocked-only + big-only + per-phase grid + bounded expansions
  are the containment. Over budget → coarsen 1"→2" / shrink window / lower cap; gate stays OFF.
- **Determinism:** zero RNG; `(f, g, cell_index)` tie-break; unit test reproducibility under PYTHONHASHSEED=0.
- **Oscillation:** return a single furthest-progress point per activation; if best reachable not strictly closer to goal than
  start → return start (never worse, no ping-pong).
- **Coherency + OC-within-3":** the coherency pull + make-way both call `_move_toward` → inherit the pathfinder; watch the
  coherency-violation rate.
- **Boxed-in:** graceful (best partial / stay put), expansion cap guarantees bounded time, never hangs.

## Critical files
- `code/simulator.py` (`_move_toward` :142-227, `_collision_kwargs` :1611, `_clear_lane`/`_make_way` :8941-9105, movement caller
  :9292-9306, **charge leak :10628-10636**)
- `code/map.py` (`Wall`/`Terrain.walls`/`wall_segments` :63-233, `_segment_segment_intersects` :330-351 — and the home a new
  `pathfind.py` imports)
- `scripts/diag_boardcontrol.py` (add Knight-reach% + blocked-move readout); `scripts/bench_simulator.py` (add the boxed-in
  Knight matchup); `code/maps.py` (`_competitive_terrain` :59-122 — Stage 4 walls)

**First move: Stage 0** — no behaviour-changing code until the three numbers (reach baseline, blocked%, per-call cost) exist;
they are the GO/NO-GO on perf feasibility.
