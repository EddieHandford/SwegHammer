# Plan — addressing the remaining over-shooters (2026-06-03)

**Context.** After the user-authorised fidelity-first work (Overwatch + Go To Ground flipped on, the illegal-Knight-
overwatch TITANIC bug fixed), the honest N=80 baseline is **gated MAE 4.05**. This plan is how we close the
over-shooter side faithfully — diagnose-don't-knob, every fix a general 10e mechanic, never a per-faction win-rate dial
(forbidden; poisons Stage 2). It sits ON TOP of the in-flight squad rebuild, which is the lever for one of the two
groups below.

## Current actionable over-shooters (N=80, honest 4.05 baseline)

| Faction | Diff | Gated | Flavour |
|---|---|---|---|
| Imperial Knights | +30.4 | **27.5** | TITANIC objective over-hold |
| World Eaters | +13.9 | **10.4** | melee attrition |
| Leagues of Votann | +10.0 | **6.9** | durable elite shooting |
| Chaos Knights | +9.3 | **6.0** | TITANIC objective over-hold |
| Tyranids | +8.8 | **5.0** | horde melee |
| Adepta Sororitas | +7.3 | **3.6** | elite mixed |
| Drukhari | +5.9 | **2.5** | mixed aggressive |

Thousand Sons (+9.6) and Emperor's Children (+6.7) read high but sit INSIDE their wide noise floors (8.75 / 5.67) —
not actionable, not over-shooters in the gated signal. Leave them.

## Two root causes → two different fixes

**Group 1 — TITANIC objective over-hold: Imperial Knights (27.5) + Chaos Knights (6.0) ≈ 33 gated, the dominant chunk.**
A single durable TITANIC model parks concentrated Objective Control on a marker; body-army opponents can't contest it
(scatter + piecemeal erosion). This is the one-model-per-Unit representation floor, verified end-to-end
(`project-oc-contest-faithful`, `project-faction-residual-rootcause`).
**Fix = the squad rebuild, Stages B + E** (coherency enforcement + cohesive holding let body armies cluster onto
markers and contest). ALREADY IN FLIGHT (Stage C landed byte-identical; A next, then B+E). No new work — just land it.

**Why Chaos Knights (6.0) over-shoots so much less than Imperial Knights (27.5) despite identical chassis stats**
(CK Desecrator = T11/26W/OC10, same as an IK Paladin; War Dogs = Armigers, identical): it is LIST + PLAYSTYLE, not
stats. (a) The CK list builder's cost cap squeezes out the expensive Chaos Questoris (the code notes it "excludes
Rampager entirely and Abominant in 67% of builds"), so CK fields more cheap killable War Dogs (OC6, the min-health AI
DOES chip them) and fewer big OC-10 holders. (b) IK chassis are SHOOTING platforms → the AI holds-and-shoots them on
markers (the over-hold mechanism's perfect victim); CK chassis are MELEE (Rampager/Desecrator/War Dogs) → the AI
advances+charges them, trading in combat instead of parking on objectives. So **IK is a pure Group-1 over-shooter; CK
is a HYBRID** (a little Group-1 from its few big knights + a little Group-2 from its aggressive War Dogs). CK will NOT
fully close from the rebuild alone — its War-Dog half is Group-2 work. This 3×-gap-at-identical-stats also CONFIRMS the
over-hold is holding/playstyle-driven, not a stat issue (which is what B+E targets).

**Group 2 — combat-output over-shoot: World Eaters (10.4) + Votann (6.9) + Tyranids (5.0) + Sororitas (3.6) +
Drukhari (2.5) ≈ 28 gated.** These over-perform on OUTPUT/attrition, NOT on objective-holding. The squad rebuild does
NOT directly reduce their output (Stage A caches the decision but executes per-model; B/E/holding may even INFLATE the
hordes — the M4-inseparability). **So Group 2 needs its own faithful diagnosis — the new work in this plan.**
Sub-flavours to tease apart: melee attrition (WE / Tyranids / Drukhari) vs durable elite shooting (Votann / Sororitas,
possibly the elite-low-model board-control issue, cf. `project-custodes-board-control`).

## Already verified faithful — ruled OUT as Group-2 drivers

- **Scoring is not kill-centric.** `_decide_winner` is victory-point-decided (primary + secondary, capped 50/40), the
  game runs all 5 rounds, and a one-sided tabling does NOT auto-win (simulator.py:640-724). A killy army that wins the
  kill race but loses on objectives LOSES in the sim. So the over-shoot is not a tabling/attrition scoring artifact.
- **Their rules are under-modelled, not over** (World Eaters audit, wave 150) — nothing faithful to remove.
- **Counter-play (screening / kiting / focus-fire) is pre-existing or washed** (waves 79/128-135/153) — the kiting
  probe BACKFIRED. So the answer is not "add counter-play AI" in the obvious form.

## The over-shoot and under-shoot are the SAME lever (symmetry — read the rebuild deltas with this)

The IK over-hold (a durable model parks on a marker and scores uncontested primary) has a mirror image: armies that
UNDER-hold leave that same primary VP on the table — out of position fighting, or picked off in the open, instead of
on objectives. B+E is symmetric: it lets body armies CONTEST the Knight's marker (IK down) AND gets those same armies
ONTO markers they currently ignore (under-holders up). So when B+E lands, expect movement on BOTH ends — IK/CK fall,
and the under-holding HOLDING armies rise.
- **Likely under-holders that should RISE from B+E:** Necrons (durable midfield), Astra Militarum (gunline + screens),
  part of AdMech. If they don't rise, the holding hypothesis is wrong for them — re-diagnose.
- **NOT under-holding (won't rise from B+E — different fix):** CSM (Dark Pacts output), AdMech infantry fragility,
  other under-outputters. Holding AI won't touch these.
- **RAIL:** this is "hold CORRECTLY" (enough OC on the markers needed to win primary, protected, rest trades) as a
  faithful even-handed AI improvement — NEVER a per-faction "dedicate X% to holding" dial (a knob; forbidden). Naive
  versions already failed pre-rebuild (clustering-geometry REGRESSED 4.15→4.30; the mass-onto-markers experiment
  washed) precisely because they lacked the per-squad substrate — which is why the rebuild is the proper vehicle.
- **CONFIRM with data:** the queued multi-metric review (per-faction turn-by-turn PRIMARY VP + objective-control on
  markers) is the smoking gun — under-holders should show low primary VP with normal secondary/kills.

## Phase 1 — Land the squad rebuild (handles Group 1; measures the Group-2 interaction)

Continue C (done) → A → **B + E** (the behavioural landing that reins the Knight over-hold) → D. Per-stage A/B,
per-faction deltas.
- **Group 1 is expected to fall** as B+E let body armies contest the markers the Knights monopolise.
- **Watch the Group-2 hordes (Tyranids especially):** B+E make body armies hold better, which may INFLATE them
  (M4-inseparability). This is EXPECTED and is NOT a reason to gate B/E off — the rebuild is faithful. It just means
  Group 2's output is a separate problem.
- **Deliverable:** the post-rebuild residual Group-2 over-shoot is Phase 2's target (re-measure at N=80 after B+E+D).

## Phase 2 — Diagnose the Group-2 combat-output over-shoot (the new work)

An INSTRUMENTED diagnostic wave (like the IK/Daemons probes), BEFORE any fix. Candidate faithful mechanisms, ranked by
expected leverage:

1. **Melee attacker-count (top candidate).** Does the sim let EVERY model in a charging unit fight, or only those that
   physically reach Engagement Range (~1.5")? Real 10e bounds melee by how many models get into base contact — a
   20-model unit charging a 5-model screen gets ~8-10 models in; the rest do nothing. If the sim over-counts
   attackers, hordes/large units massively over-kill. INSTRUMENT: per melee, log models-that-fought vs
   models-actually-in-Engagement-Range, for Group-2 armies. FIX (if over-counting): gate fighting on per-model
   Engagement Range — the rebuild's per-model positions make this clean.
2. **Fight-phase alternation.** Verify the fight phase faithfully alternates (units that charged fight first, then
   alternate starting with the NON-active player) even in the vanilla eval path. If the aggressor fights all its units
   before the opponent can swing back, it over-kills. FIX: enforce 10e fight alternation.
3. **Battle-shock crumbling.** Verify below-Half-strength Group-2 units crumble faithfully (Objective Control 0, no
   stratagems, Desperate Escape on Fall Back). If under-modelled, aggressive armies that take losses don't erode.
4. **Go-To-Ground / stratagem CP economy.** GtG is now on and inflates the infantry over-shooters. Check the AI isn't
   over-spending it (and the other defensive stratagems) beyond a realistic Command-Point budget — if they GtG every
   turn unrealistically, that's an AI-economy fidelity fix, not a faithful-mechanic problem.
5. **Opponent-side play (the other half).** The over-shoot is symmetric: a faithful OPPONENT reins the aggressor. The
   one genuinely-unmodelled counter is SCREENING (chaff blocking charge lanes / deep-strike) — complex deployment AI,
   regression-prone, lower priority, but the honest long-tail if 1-4 don't fully close Group 2.

## Phase 3 — Faithful fixes for whatever Phase 2 pins

Env-gated, A/B N=40→N=80, report per-faction deltas, keep-if-faithful. Expected direction: 1-3 reduce Group-2
over-output. Be direction-honest — a shared mechanic may nudge a non-over-shooter; fix it anyway (fidelity-first). Each
landed mechanic re-prices Stage 2 (re-run `balancer.py` gate-off vs gate-on).

## Rails (non-negotiable)

- **Every fix is a GENERAL faithful 10e mechanic.** Never a per-faction win-rate knob (`project-winrate-gap-is-sim-
  fidelity-not-stats`). The test: "would it still be correct if it moved the metric the WRONG way?"
- **The over-shoot is missing fidelity on BOTH sides** — the over-shooter's output AND the opponent's play. Prefer the
  mechanism that is faithfully WRONG, not the one that happens to move the metric.
- **Judge the rebuild on Group 1, not Group 2.** B+E may inflate the Group-2 hordes; that is the rebuild working
  correctly on the granularity, not a regression. Group 2 is a separate problem with a separate fix.

## Sequencing

Phase 1 (rebuild, in flight) → re-measure N=80 → Phase 2 diagnostic → Phase 3 fixes. The stratagem-fidelity cleanup
batch (7 items) and the AdMech under-side deeper diagnostic slot as fill between rebuild stages.

## Phase 2 RESULTS (waves 162-168, 2026-06-04) — DIRECT combat levers EXHAUSTED

The Group-2 melee diagnostic ran the direct combat candidates. All tried, instrument-first, no metric-tuning:
- **#1 melee attacker-count — REFUTED.** Lists are size-1 swarms (65-78% singletons, faction-neutral) → no big squads
  to over-count, no differential lever.
- **Split-fire (Stage D) — NEUTRAL** (faithful, gated; the over-shoot is melee not shooting).
- **#2 fight-phase alternation — built FAITHFULLY (corrected 10e order, user-greenlit) + DEFINITIVELY REJECTED.**
  Doubling (each locked unit fights both fight phases/round) overshoots badly (gated 4.20→7.31, IK +30→+40, WE +14→+23).
  **KEY: the sim's once/round melee is a FORTUNATE-CANCELLATION abstraction** — missing doubling ≈ missing Fall-Back-
  disengage + combat-resolution, so once/round ~matches reality; adding doubling alone runs away. Faithful doubling
  needs the BOUNDING fidelity first. Lever DEAD (SWEG_FIGHTALT gated-OFF, correct-but-rejected — do NOT re-litigate).

**So the Group-2 melee over-shoot is a SMALL residual on a roughly-right abstraction, not a gross model bug.** Remaining:
- **#3 battle-shock crumbling** — the last CHEAP probe (un-tried as of wave 168). Do below-Half units faithfully crumble
  (OC→0, strat-lockout, Desperate Escape), and do melee aggressors crumble more than gunlines? Instrument first.
- **THE BOUNDING-FIDELITY TRACK** (Fall-Back-to-disengage AI + one-exchange combat resolution) — the systemic fix that
  would let faithful doubling land. MULTI-WAVE, UNCERTAIN net reward (once/round already ≈ reality). **USER DECISION**,
  gated on #3. Vs **accept the Group-2 melee residual as a representation floor + pivot axis** (under-side / Stage 2).

### Phase-2 #3 RESULT (wave 169, 2026-06-04): battle-shock crumbling = NULL
Ran `diag_battleshock.py`: melee over-shooters go below-Half MORE than gunlines (4.2-4.9 vs 3.2-3.9/btl) and crumble at
~the same ~30% — NOT under-crumbled. Battle-shock is roughly faithful + faction-neutral → not the Group-2 lever. **ALL
cheap over-side Group-2 levers now EXHAUSTED.** Over-side remaining = the BIG bounding-fidelity track (user decision,
uncertain reward) vs accept the melee residual as a representation floor + pivot to the under-side (UNDERSHOOTER_PLAN).
