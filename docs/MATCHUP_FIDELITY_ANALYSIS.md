# Matchup-fidelity diagnosis + faithful-AI plan (wave 78)

**Date:** 2026-05-31. **Phase:** the user's "faithful AI track + matchup-fidelity
diagnosis" (`STAGE1_AUTONOMOUS_GOAL.md` Current phase; `LOOP_QA.md` Q4 user ruling).
**Status:** diagnosis + plan. The AI build executes in fresh-context waves (the redesign
is big/risky; this mirrors the successful wave-73→74 plan→build).

## Method

Per the user's directive, do NOT work from aggregate per-faction win rates alone — drill
into the specific matchups driving each big residual, and compare the simulator to real
May-2026 tournament play. Each gap sorts into one of three FAITHFUL buckets (never a
win-rate nerf): (a) a real tactic the sim's AI cannot execute; (b) a real-list counter the
archetype lacks; (c) a mis-modelled rule/stat.

## Sim-side: the lopsided matchups driving the residuals (N=10/cell)

| Strong (over) | crushes | sim win% | Under (under) | loses to | sim win% |
|---|---|---:|---|---|---:|
| Imperial Knights | CSM / AdMech / Marines | **100%** | Chaos Space Marines | Emperor's Children | **0%** |
| Imperial Knights | Sororitas | 90% | Chaos Space Marines | Sororitas / Votann | 10% |
| Drukhari | Tyranids / CSM / AdMech | **90%** | Chaos Daemons | AdMech / Drukhari / TSON | **0%** |
| Drukhari | Orks / Necrons / Chaos Knights | 80% | Chaos Daemons | Grey Knights / Votann | 10% |

100% / 0% matchups are impossible in real competitive play (these are roughly even). The
simulator has specific opponents losing far too hard to the durable/efficient factions.

## Real-play comparison + bucket sort

**Imperial Knights over (vs CSM / AdMech / Marines = 100%).** Real play: every competitive
list removes Knights with **concentrated anti-tank focus fire** (multiple anti-tank units
onto ONE Knight over 1-2 turns) and **contests/denies objectives** (a 9-11-model Knight army
cannot be on every objective; you score the ones it is not on and body it off with cheap
high-OC infantry). Verified NOT a stat/rule gap: the simulator's Knight statistics already
reflect the December-2025 update (Questoris T11 / W26 — "lost a point of Toughness, gained
wounds"), and the rules were verified faithful end-to-end in waves 71-72. → **Bucket (a),
AI:** the opponents do not focus-fire the durable threat (the min-HP picker spreads fire and
the value-picker regressed because it sharpened the over-shooters' own offence too) and do
not aggressively contest/deny the Knight's objectives. A minor **bucket (b)** note: the
real tournament-winning Knights list is **Armiger-heavy** (massed cheap Armigers + a couple
of characters), where the simulator's archetype is big-Knight-heavy — flagged, but the
direction is uncertain (Armigers are *more* efficient, so swapping could raise IK), so it is
NOT a lever to pull blind; revisit only if the AI fix exposes it.

**Drukhari over (vs Tyranids / CSM / AdMech = 90%).** Drukhari is a fragile glass-cannon
that in real play **dies in droves to focused fire** and trades down. Stats verified faithful
(static FNP already stripped, Pain Token amplification fixed — memories
`project-bsdata-static-vs-runtime-double-count`, `project-one-unit-per-model-amplification`).
→ **Bucket (a), AI:** opponents do not focus-fire the fragile high-value Drukhari units
(Ravagers, Talos, the Archon's squad). Same focus-fire lever as Knights, from the other side.

**CSM / Chaos Daemons under (lose 0-20% to EC / Sororitas / Votann / AdMech / TSON).** These
are the wave-75 secondary over-correction (the cheap-unit armies over-score cleanse/sabotage;
the low-model CSM cannot reciprocate) COMPOUNDED by an AI mis-allocation: CSM/Daemons throw
their few cheap units at Sabotage in the enemy DZ where they die, losing the shooting for no
VP. → **Bucket (a), AI:** the action-allocation must only commit GENUINELY spare units that
can survive to score — not suicide a needed unit. (This is the "commit only spare units to
actions" tactic the user named.)

## The faithful AI redesign (the build, for the next waves — env-gated, diagnose-don't-nerf)

A tournament-realistic target + positioning + action AI. Build each as an env-gated A/B,
measure cleanly, and when it exposes an over-shoot, **DIAGNOSE the faithful sim cause and fix
THAT** (a mis-modelled rule, a stat wrong vs BSData, an unrealistic list), never a nerf. Accept
a temporary headline regression that a faithful re-calibration recovers (the frozen-under
problem, `project-ai-frozen-under-mae-first`).

1. **Army-level focus fire on the highest-value reachable threat.** The wave-72 per-unit
   value-picker regressed because each unit independently re-valued and it sharpened the
   over-shooters' offence symmetrically. The faithful version is ARMY-LEVEL: each turn the
   army nominates the single highest-value reachable enemy its anti-armour CAN meaningfully
   hurt, and concentrates that fire to REMOVE it over 1-2 turns (matching how real players
   delete a Knight). Gate the nomination to anti-armour-vs-durable (do not dump bolters into
   a Knight) so it is weapon-target-matched, not blunt.
2. **Contest / deny objectives (#13 positioning).** Under-shooters should move cheap high-OC
   bodies onto the objectives a durable camper is NOT on (score the spread) and onto contested
   ones to body it off — denying the camper its primary VP, which is how a 9-model Knight army
   is actually beaten. Distinct from the #12 camp behaviour (which helped the campers).
3. **Action allocation = spare-and-survivable only.** Only commit a unit to Cleanse/Sabotage
   if it is genuinely surplus to the firefight AND can plausibly survive to score (not deep in
   the enemy DZ surrounded). Fixes the CSM/Daemons self-inflicted secondary losses.

Sequence: build #1 (army focus fire) first as the clearest matchup gap, env-gated A/B; then
diagnose the over-shoots it exposes (faithful re-calibration toward real lists / diagnosed
causes, now permitted); then #2 (contest/deny) and #3 (action allocation). Each wave: drill
the driving matchups (sim win% per cell) before AND after, not just the aggregate.
