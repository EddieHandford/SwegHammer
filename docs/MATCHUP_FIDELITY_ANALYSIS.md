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

## Wave 79 result — #1 army focus fire BUILT + TESTED (env-gated `SWEG_FOCUS`); regresses solo

Built `Battle._nominate_focus_target` + the `_do_shoot` override: the army nominates the
most valuable durable enemy threat it can hurt (preferring one on an objective) and its
**anti-armour weapons only** (`_is_antiarmour_weapon`: D≥3 / AP≤-2 / Anti-MONSTER-VEHICLE-
TITANIC) concentrate on it. Smoke-confirmed (Chaos Space Marines focus-fire the Knight
Castellan and beat Imperial Knights in a matchup they normally lose). N=40 A/B: gated
**4.95 → 5.41 (REGRESSED +0.46)**. Per-faction:
- **Drukhari +18.6 → +14.2** (−4.4, HELPED — its fragile Ravagers/Talos get focus-removed).
- **Imperial Knights +19.1 → +25.9** (+6.8, WORSE), **GSC −5.4 → −15.9**, T'au up.

**Diagnosis (the user's "diagnose the over-shoot" step):** focus fire is the right tool for
FRAGILE high-value threats (Drukhari) but the WRONG tool for the DURABLE over-shooter Imperial
Knights — a Knight cannot be shot off (T11/W26/5++), so the victims' concentrated fire is
wasted, while IK's OWN anti-armour sharpens on the opponents' vehicles/dreadnoughts (its MEQ
opponents DO carry durable targets, contrary to the pre-build assumption). This is the third
confirmation (after wave-72 value-targeting) that better SHOOTING AI sharpens the durable
over-shooters. The faithful causes the regression exposes, per bucket:
1. **List-realism (bucket b):** the simulator's Imperial Knights archetype is big-Knight-heavy
   and OVER-GUNNED versus the real tournament-winning list (Armiger-heavy — ~12 Armigers +
   characters). With focus fire that over-gunning is what sharpens. The faithful re-fit (now
   permitted) is to rebuild the IK archetype toward the real Armiger-heavy list; Armigers are
   fragile (T9/W14) so focus fire would REMOVE them — IK should then come down. **This is the
   next test: IK Armiger re-fit PAIRED with focus fire.**
2. **AI (bucket a) — the real IK lever is CONTEST/DENY (#2), not shooting.** IK is beaten in
   real play by denying its primary VP (contest the objectives it is not on; body it off),
   not by killing the Knight. Build #2 next.

Focus fire is committed env-gated OFF (baseline 4.95 unchanged) as the AI half, pending the
paired re-fit (#1 cause above) and #2.

## Wave 81 result — #2 contest/deny BUILT + TESTED (env-gated `SWEG_CONTEST`); barely moves IK, regresses headline → the structural finding

Built the contest/deny branch in `pick_move_intent`: a cheap chaff unit not already on an
objective moves to CONTEST the nearest reachable enemy-CONTROLLED objective (deny the durable
camper its primary VP), prioritised over the AI-9 sacrificial enemy-DZ run. Naturally
asymmetric — a low-model durable army (Imperial Knights) carries no chaff, so its own
behaviour is unchanged; only its victims gain the contest. N=40 A/B vs baseline 4.95:

| Eval | MAE_gated | Imperial Knights | note |
|---|---:|---:|---|
| Wave 80 baseline | 4.95 | +19.1 (67.6%) | contest off |
| Contest ON (A/B) | **5.14** | **+18.2 (66.7%)** | regressed +0.19; IK only −0.9 |

Per-faction: Imperial Knights barely moved (+19.1 → +18.2, **still grossly over-rated at
+18.2**), while the OTHER over-shooters got WORSE — **Drukhari +18.6 → +20.6** (+2.0),
**Leagues of Votann +13.4 → +14.9** (+1.5), Orks +1.3, Chaos Knights −1.0 worse. In-band
6/22 → 5/22. Reverted (not a clear fidelity win — it unconditionally overrides AI-9's real
enemy-DZ tactic — and it fails its purpose while regressing the metric).

**THE FINDING (escalation-grade).** Contest/deny is the *last* faithful AI lever the diagnosis
pointed at for Imperial Knights, and it FAILED to bring IK down (−0.9; still +18.2). The
signature is identical to wave-79 focus fire and wave-72 value-targeting: **a generic, faithful
AI improvement applied symmetrically helps whoever has the better army — and the over-shooters
HAVE the better armies — so sharper play widens the residual instead of closing it.** This is
exactly memory `project-ai-frozen-under-mae-first` ("almost ALL AI improvements regress the
headline because stats are over-tuned and the bad AI compensates").

Mechanistically for IK: opponents *do* contest (the wave-71/81 per-round drills showed CSM
contesting and winning when it happened), but a Knight is durable enough that the contesters
get pushed off or die, so contesting fails to deny its primary VP. The over-rate is therefore
**IK's durability converting to held primary VP** — the sim's kill-centric scoring under-models
how real tournaments deny primary through the full secondary economy and board tempo (memory
`project-faction-residual-rootcause`: kill-centric, not VP/positional scoring). **IK is a
structural VP-vs-durability SCORING residual, not AI-fixable.** Per the watchdog's Q5 ruling
this is reported, not nerfed — escalated as `LOOP_QA.md` Q6 for the user's mission call (next
faithful lever = the scoring/VP model itself; or bank ~4.95 / declare substantial convergence).
