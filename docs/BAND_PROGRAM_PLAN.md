# Band-program plan — closing the remaining mean absolute error on the squad frame

**Frame:** post-random-fill-re-base, gated mean absolute error 7.05 (squads-on default, wave 219).
**Goal:** drive per-faction noise-gated mean absolute error toward the ≤ 2 point target by adding
*faithful missing mechanics*, not by tuning numbers. Prepared 2026-06-09 from the current residual
table plus external research (competitive-game balance methodology + 10th-edition tournament meta),
then **corrected 2026-06-09** after a user challenge to the action-restriction premise (see §2).

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
objective-control-by-unit-count, and under-rewards the "soft" win conditions** — board control,
reserves / deep strike / ambush tempo, faction resource economies, and the action / secondary game.
The over-rated cluster is durable, low-model, elite/big-model armies; the under-rated cluster is
cheap-body, reserve-reliant, or resource-engine armies. This matches the project's standing
residual diagnosis (kill-centric, not positional/tempo).

**The cross-faction lever (this is the key to not playing whack-a-mole):** the matchup matrix is
closed, so **raising the under-pole automatically lowers the over-pole.** The elite armies
(Knights, Custodes, T'au) are precisely the opponents that beat the under-dogs; give Daemons /
Genestealer Cults / Astra Militarum / Tyranids their real win conditions and the elite armies win
*less* against them, pulling both poles toward target at once. We should therefore drive the program
from the under-pole missing mechanics and **not** reach for a direct over-pole nerf (which would be a
forbidden knob, and the over-pole's residual is mostly the known positional-representation gap, §3.5).

## 2. CORRECTION — the action-restriction premise was wrong (verify-don't-assert)

The first draft, following a research agent, made the action economy the master lever on the claim
that "Vehicle / Monster / Titanic units cannot perform Actions." **A user challenge prompted a check
of the canonical rule, and that claim is false.** Chapter Approved 2025-26 bars a unit from starting
an Action only if it is an **AIRCRAFT**, is Battle-shocked, has Objective Control 0, is within
Engagement Range (*unless* it is a Titanic Character), Advanced or Fell Back this turn, or is not
eligible to shoot. There is **no Vehicle / Monster / Titanic keyword ban** — Titanic Characters are
in fact *exempted* from the engagement-range bar. (Source: Wahapedia, Chapter Approved 2025-26 core
rules, Actions section.)

Our simulator already handles this faithfully: `simulator.py:_unit_can_perform_action` bars
Objective-Control-0 units (which catches Aircraft) and units in Engagement Range, and uses an
*emergent* opportunity-cost heuristic — a unit that is a productive shooter with a target in range is
not peeled off for an Action — so a Knight's all-productive army naturally scores the Action cards 0
while a broad army's spare bodies do. **Do NOT add a Vehicle/Monster/Titanic action restriction — it
would be a fabricated rule (rule 10).** The genuine gaps in the action model are the *missing
eligibility conditions* (Battle-shocked and Advanced/Fell-Back cannot act) and the *calibration* of
the existing emergent model — see §3.4.

## 3. Cross-faction discipline (how we avoid tunnel vision)

1. **One structural change per wave**, then re-read the *full* matrix. (Matchup-scoping only applies
   to genuinely single-faction changes; the systemic levers need a full re-anchor.)
2. **Read the per-faction delta and the matchup variance, not just the headline.**
3. **The viable-options test after each change:** did it move the intended factions *without*
   cratering a third party? (The re-base just demonstrated the failure mode — it helped several
   factions but over-corrected Tyranids to under.)
4. **Expect and accept temporary headline regressions**; unwind "frozen-under" compensatory offsets
   rather than stacking a new mechanic on top of them.
5. **Cluster the matrix** to confirm a lever is a shared root cause before a per-faction patch.
6. **Stop at equilibrium-fidelity** (mean absolute error ≤ 2), not perfect per-event fidelity.

## 4. Prioritised focus points (corrected order — high-confidence missing mechanics first)

### Priority 1 — Battle-shock (systemic; appears missing; lifts the under-pole)
- **Why:** a battle-shocked unit has Objective Control 0 (loses the objective even while alive) **and
  cannot perform Actions** (per the verified rule above) — two effects the simulator is currently
  blind to. Tyranids generate it heavily (Synapse, Shadow in the Warp mortal wounds); it is a
  faithful *core* rule touching every army's hold-under-pressure. Closes part of the Tyranids −11 and
  ripples through the matrix.
- **State:** appears NOT modelled. Build: a battle-shock test (Leadership vs half-strength / sources
  of −1), OC→0 while shocked, action-ineligibility while shocked, and Shadow-in-the-Warp mortals.

### Priority 2 — Reserves / deep-strike fidelity (the two biggest residuals)
- **Why:** Chaos Daemons (−21) win via a 6-inch deep-strike window, arriving onto / contesting
  objectives, and Corrupt Realspace objective-locking; Genestealer Cults (−20.5) via the Cult Ambush
  resurrection engine (destroyed units return as blips). The simulator treats deep strike as generic
  9-inch or not at all and has no return engine.
- **State:** weak or missing. Build faction-correct arrival distances, arrive-onto-objective
  contesting, and a return/resurrection engine. Highest single-residual payoff.

### Priority 3 — Faction resource economies (several under-pole factions)
- **Sororitas Miracle Dice** (−11.9): a per-game pool the AI spends to substitute a chosen result on
  a key save / wound / charge — variance suppression the average-dice model misses.
- **Chaos Space Marines Dark Pacts** (−12.8): finish the per-activation Lethal/Sustained with the
  Leadership-test gate and the Pactbound 5+ critical-hit detachment (Veterans of the Long War landed).
- **Daemons summoning / Corrupt Realspace** (part of the −21): objective-lock without a unit present.

### Priority 4 — Action-economy calibration + missing eligibility (NOT a keyword ban)
- The action model is already largely faithful (§2). Faithful work here: (a) add the missing
  eligibility conditions — Battle-shocked (folds in from Priority 1) and Advanced/Fell-Back cannot
  act; (b) sanity-check the AI's productive-shooter threshold and the count/weighting of
  action-secondaries against how often real games score through Actions; (c) confirm body-army
  evaluation lists actually field and use the spare chaff. **No Vehicle/Monster/Titanic restriction.**

### Priority 5 — Over-pole positional representation (revisit last; the parked hard problem)
- After Priorities 1–3 pull the over-pole down via the matrix, whatever Knight / Custodes / T'au
  residual remains is the **known positional / objective-control-reach representation gap** (few-model
  armies park concentrated Objective Control; body armies have large total Objective Control that does
  not reach the markers — see [[project-oc-contest-faithful]]). The random-fill re-base changed the
  representation, so **re-measure this gap on the squad frame before assuming it is still there.**
  Faithful only — primary board-coverage / reach, never a per-faction objective-to-victory-point knob.

## 5. Sequencing
1. **Priority 1 (battle-shock)** — systemic, high-confidence, full re-anchor after.
2. **Priority 2 (reserves/deep-strike)** — the two biggest residuals (Daemons, Genestealer Cults).
3. **Priority 3 (resource economies)** — Sororitas, finish Chaos Space Marines, Daemons.
4. **Priority 4 (action calibration)** — light, mostly verification + the two eligibility conditions.
5. **Priority 5 (positional over-pole)** — re-measure on the squad frame; revisit last.
Re-anchor after every matrix-wide change; matchup-scoping only for the genuinely single-faction items
(e.g. completing Dark Pacts). Each under-pole win is expected to trim the over-pole as a side effect —
track that explicitly rather than nerfing the elites directly.

## 6. Sources
Game-balance methodology: Riot champion-balance framework; Stardock real-time-strategy dev journal;
Empirical Game-Theoretic Analysis survey (arXiv 2403.04018); Sirlin balancing-multiplayer-games;
clustering approach (arXiv 2502.01250); Bradley-Terry model. 10th-edition meta + rules: Goonhammer
competitive faction focuses; Stat Check meta dashboard; **Chapter Approved 2025-26 Actions rule
(Wahapedia) — the action-eligibility correction in §2.** Full URL list in the oversight log.
