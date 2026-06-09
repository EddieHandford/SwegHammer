# Band-program plan — closing the remaining mean absolute error on the squad frame

**Frame:** post-random-fill-re-base, gated mean absolute error 7.05 (squads-on default, wave 219).
**Goal:** drive per-faction noise-gated mean absolute error toward the ≤ 2 point target by adding
*faithful missing mechanics*, not by tuning numbers. Prepared 2026-06-09 from the current residual
table plus external research (competitive-game balance methodology + 10th-edition tournament meta).

## 1. The diagnosis (grounded)

Per-faction residual on the new frame, largest first (sim minus real, points):

| Over-rated (sim too high) | | Under-rated (sim too low) | |
|---|---|---|---|
| Imperial Knights | +17.0 | Chaos Daemons | −21.0 |
| Adeptus Custodes | +15.4 | Genestealer Cults | −20.5 |
| Adeptus Astartes | +14.2 | Astra Militarum | −14.1 |
| T'au Empire | +12.7 | Chaos Space Marines | −12.8 |
| Death Guard | +11.2 | Adepta Sororitas | −11.9 |
| Emperor's Children | +11.1 | Tyranids | −11.0 |

The structure is a single systemic bias: **the simulator rewards killing, durability, and
objective-control-by-unit-count, and under-rewards the "soft" win conditions** — secondary-objective
scoring through cheap actions, board control, reserves / deep strike / ambush tempo, and faction
resource economies. The over-rated cluster is durable, low-model, elite/big-model armies; the
under-rated cluster is cheap-body, reserve-reliant, or resource-engine armies.

**Two independent research streams converge on this.** The game-balance literature (Riot, Stardock,
Empirical Game-Theoretic Analysis, Sirlin) says: fix the missing *mechanic*, not the number, and
apply *systemic* (matrix-wide) levers before per-faction patches. The 10th-edition meta research
independently identifies the single highest-leverage mechanic as **action-based secondary scoring
plus the Vehicle / Monster / Titanic action restriction**, which lowers the elite over-pole (few
models, can't perform actions, get out-scored while winning the kill war) *and* raises the cheap-body
under-pole (farm action secondaries) at the same time.

## 2. Cross-faction discipline (how we avoid tunnel vision)

Every change ripples across the 22×22 matchup matrix. Standing rules for this program:

1. **One structural change per wave**, then re-read the *full* matrix. (Matchup-scoping only applies
   to genuinely single-faction changes; the systemic levers below need a full re-anchor.)
2. **Read the per-faction delta and the matchup variance, not just the headline.** A lever that fixes
   the mean but widens a faction's spread across opponents has introduced a counter-problem.
3. **The viable-options test after each change:** did it move the intended factions *without*
   cratering a third party? (The re-base just demonstrated the failure mode — it helped several
   factions but over-corrected Tyranids to under.)
4. **Expect and accept temporary headline regressions** when adding a faithful mechanic; then unwind
   any "frozen-under" compensatory offsets rather than stacking the new mechanic on top of old ones.
5. **Cluster the matrix** to confirm a lever is a shared root cause before reaching for a per-faction
   patch. Prefer the lever that moves a whole cluster.
6. **Stop at equilibrium-fidelity** (mean absolute error ≤ 2), not at perfect per-event fidelity.

## 3. Prioritised focus points

### Priority 1 — Audit and complete the action economy (the master systemic lever)
- **Why:** the one mechanic that moves *both* poles toward target. Over-pole armies (Imperial
  Knights, Custodes, Astartes, T'au, Emperor's Children, Death Guard) are out-scored in reality
  because Vehicles / Monsters / Titanic units cannot perform most secondary actions and a handful of
  models cannot blanket the objectives; under-pole armies (Genestealer Cults, Astra Militarum,
  Tyranids, Sororitas, Daemons) farm victory points through cheap action-bodies.
- **State:** PARTIALLY modelled — `simulator.py:_unit_can_perform_action` plus Sabotage / Burn /
  Cleanse and chaff-action logic in `secondaries.py`. So this is an *audit-and-complete*, not a
  build-from-scratch.
- **The audit:** (a) does `_unit_can_perform_action` correctly **exclude Vehicles / Monsters /
  Titanic** per Chapter Approved 2025-26? If Knights / Custodes / T'au battlesuits can perform actions
  in the simulator, that is a direct over-rate. (b) Is the set of action-based secondaries and their
  scoring weight faithful to how often real games score through actions? (c) Do the evaluation lists
  for body armies actually field the cheap chaff, and does the artificial-intelligence player use it
  for actions rather than feeding it into combat? (d) The action-versus-fight trade-off in the
  artificial-intelligence player.
- **Cross-faction caution:** matrix-wide. Confirm it does not over-correct the elite armies *below*
  target. Watch matchup variance. Needs a full re-anchor (not scoped).

### Priority 2 — Battle-shock reducing Objective Control to zero (systemic; Tyranids-skewed)
- **Why:** a battle-shocked unit has Objective Control 0 — it loses the objective even while alive.
  The simulator's unit-count objective contest is blind to this. Helps Tyranids (multiple −1
  battle-shock sources plus Shadow in the Warp mortal wounds) and is a faithful *core* rule touching
  every army's ability to hold an objective under pressure.
- **State:** appears NOT modelled (only archetype comments reference battle-shock).
- **Cross-faction:** a core mechanic — lowers armies that get battle-shocked off objectives, raises
  armies that impose it; net should lift the psychic / horde under-pole.

### Priority 3 — Reserves / deep-strike fidelity (systemic; the two biggest under-pole residuals)
- **Why:** Chaos Daemons (−21, the largest single residual) win through a 6-inch deep-strike window,
  arriving onto / contesting objectives, and Corrupt Realspace objective-locking; Genestealer Cults
  (−20.5) through the Cult Ambush resurrection engine (destroyed units return as blips anywhere on the
  board). The simulator treats deep strike as generic 9-inch or not at all, and has no return /
  resurrection engine.
- **State:** weak or missing (reserves variety was already queued).
- **Cross-faction:** mostly lifts the reserve-reliant under-pole; modest ripple as the elite over-pole
  gets out-tempo'd.

### Priority 4 — Faction resource economies (several under-pole factions)
- **Sororitas Miracle Dice** (−11.9): variance suppression — substitute a chosen result on a key save
  / wound / charge. The simulator rolls average dice; Miracle Dice let the player pick outcomes.
  Model a per-game Miracle-dice pool the artificial-intelligence player spends on the
  highest-leverage roll.
- **Chaos Space Marines Dark Pacts** (−12.8): partially built (Veterans of the Long War landed).
  Complete the per-activation Lethal / Sustained Hits with the Leadership-test gate, and the
  Pactbound 5+ critical-hit detachment.
- **Daemons summoning / Corrupt Realspace** (part of the −21): objective-lock without a unit present.
- **Genestealer Cults resurrection** (overlaps Priority 3).

### Priority 5 — Distance-gated aura stacking (over-pole trim, refinement)
- **Why:** if the simulator grants Contagion (Death Guard), Shadow of Chaos (Daemons), or Synapse
  (Tyranids) from turn one at full army range, it inflates slow / short-range armies. Gate by actual
  proximity and turn. Trims the Death Guard over-rate.

## 4. Sequencing

1. **Priority 1 first** — it is the master lever and the post-Priority-1 frame becomes the baseline
   everything else is measured against. Full re-anchor after.
2. **Priorities 2 and 3** — the big under-pole levers (battle-shock, reserves) targeting Daemons,
   Genestealer Cults, Tyranids, Astra Militarum.
3. **Priority 4** — resource economies for the residual under-pole.
4. **Priority 5** — aura gating to trim the over-pole.
Re-anchor after every matrix-wide change; use matchup-scoping only for the genuinely single-faction
items (e.g. completing Dark Pacts).

## 5. Sources
Game-balance methodology: Riot champion-balance framework; Stardock real-time-strategy dev journal;
Empirical Game-Theoretic Analysis survey (arXiv 2403.04018); Sirlin balancing-multiplayer-games;
clustering approach (arXiv 2502.01250); Bradley-Terry model. 10th-edition meta: Goonhammer
competitive faction focuses (Daemons, Genestealer Cults, Astra Militarum, Chaos Space Marines,
Sororitas, Tyranids, Imperial Knights, Custodes, Death Guard); Stat Check meta dashboard; Chapter
Approved 2025-26 (Wahapedia). Full URL list in the oversight log.
