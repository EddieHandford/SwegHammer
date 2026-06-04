# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 181 (2026-06-04) — PARALLEL BATCH: anti-tank picker bias QUANTIFIED (the #1 lever, UNIFIED) + Tactical kill-card schedules landed

Two file-disjoint background agents (parallelize directive); both committed (worktree post-commit-stall meant I integrated
from their commits directly), cherry-picked + verified. Default-path baseline unchanged (5.84) — neither piece touches it.

**#65 — anti-tank weapon-picker bias QUANTIFIED (diagnostic, e3aaf2c, `scripts/diag_antitank_pick.py`).** The mapper's
`_best_candidate` picks weapon CHOICE options by `expected_damage_through_baseline` (vs a MARINE: 3+ save, no wound roll),
so multi-shot anti-infantry options beat single-shot anti-armour, and the picker DROPS anti-tank. Quantified the EV-vs-Tank
(Toughness 11 / 2+ save) left on the table per faction:
```
Faction            Biased groups   Anti-tank EV lost
Aeldari                  9              8.05
Drukhari                 9              7.50
Astra Militarum         13              6.06  <<< under-shooter
Adeptus Astartes        15              4.86
Adeptus Mechanicus       5              2.47  <<< under-shooter
Imperial Knights         2              1.87
World Eaters             3              0.66
```
Worst single cases: Wraithknight (Suncannon over Heavy Wraithcannon), Onager Dunecrawler (Eradication beamer over Neutron
laser), Voidraven (Dark Scythe over Void Lance), Ravager (Disintegrator over Dark Lance). **CONFIRMS the watchdog's
UNIFIED-lever hypothesis:** the bias is SYSTEMIC; AM/AdMech lose real anti-tank output (under-output), AND the OPPONENTS
lose MORE (Aeldari/Drukhari/Marines) → they under-threaten the durable Knights. So one faithful mapper fix RAISES the
under-shooters AND reins Imperial Knights (whose own 2 groups barely matter — the IK fall comes from opponents arming up).
Selectivity rail visible in the data: Ravager (gunboat) should get Dark Lance; Raider (transport) should stay Disintegrator
(incidental) — the fix must be target-aware/mix-scoring, not "always anti-tank". → the systemic mapper FIX is task #65b.

**#67 — Tactical kill-card Fixed-vs-Tactical victory-point split LANDED (569377e, gated SWEG_TAC_DECK path only).** The sim
applied the per-unit FIXED schedule on the Tactical track too; real CA-2025-26 Tactical kill cards are a flat once-per-turn
trigger. Added `tactical=True` routing in `_score_one_card` → `score_round_delta` (Assassination flat 5/turn, Bring It
Down 4/turn, Cull 5/turn; No Prisoners stays per-unit-capped 2/5 in both tracks). Three new cited entries (verbatim
CA-2025-26 text), registered in the auditor. OFF/union path byte-identical; a new test pins 5-flat-Tactical vs
8-per-unit-Fixed. audit clean, 111 tests pass, run.py --cli clean. Only bites once the deck track is used (gated, off) —
no headline move, faithful fidelity banked for when the deck lands.

## Wave 180 (2026-06-04) — PARALLEL BATCH: AI-pursuit (B) refuted (maps lack own-zone objectives); the dominant under-shooter lever is combat UNDER-OUTPUT (C)

Parallelized the watchdog's file-disjoint batch (user PARALLELIZE directive): A = secondaries.py FIXED-secondary
fidelity (worktree Sonnet), B = the AI-pursuit fix (orchestrator, simulator.py), C = the attrition dealt-vs-taken
diagnostic (worktree Sonnet). Results:

**B — board take-and-hold card pursuit: BUILT (94f6054, gated SWEG_TAC_PURSUE) but REFUTED as the secondary-stall fix.**
Extended `_assign_card_pursuit` to route a spare chaff per UNMET held board card to the marker it needs. The achieve-rate
diagnostic (SWEG_TAC_PURSUE=1) shows it does NOT work — Defend Stronghold stays 7−10%, Extend Battle Lines 8−14%
(≈unchanged), overall achieve 23→24 / 25→28. **Root cause found: most rotation maps place ALL objectives in No Man's
Land** (map0/1/3 have ZERO own-deployment-zone markers; only map2/map4 have one per side), so Defend Stronghold / Extend
Battle Lines are structurally near-unachievable — no own-zone marker to hold, regardless of pursuit. Secure No Man's Land
already achieves 62−79% without help. So the secondary stall is NOT a pursuit-routing gap; it is (i) the MAP OBJECTIVE
LAYOUT (a fidelity gap — real Pariah Nexus / CA-2025-26 missions DO place markers in deployment zones; note the
`terrain.competitive_pariah_nexus_layout` citation, worth a fidelity check) and (ii) the contest/representation gap. Kept
B gated (harmless, OFF byte-identical; becomes useful only after a map-objective fix); NO N=80 A/B run (the diagnostic
already shows it inert; wave-122 precedent confirms deck+pursuit washes).

**C — attrition dealt-vs-taken (9fa33f3, `scripts/diag_attrition_split.py`): the dominant under-shooter problem is combat
UNDER-OUTPUT.** Astra Militarum / Adeptus Mechanicus deal ~HALF the opponent's damage (51 / 57 wounds per game vs the
opponent's 101); dealt-to-taken ratio 0.48 / 0.59 vs the opponent's 1.87. They are comprehensively OUT-GUNNED, not merely
fragile (the high damage-taken is largely downstream of the output gap — their weak guns let opponents survive and keep
shooting). For Astra Militarum a secondary over-fragility signal exists on durable vehicles (56% of wounds taken, only
28% of damage dealt). **This is a separate, larger, faithful COMBAT-fidelity lever** — likely related to the anti-tank
weapon-picker bias (the mapper picks low-expected-value weapon options → the under-shooters' own guns under-pick their
anti-tank). It does NOT depend on the secondary subsystem at all.

**PIVOT:** the secondary-scoring path (deck cadence + pursuit) is NOT the tractable under-shooter lever right now — it is
blocked by the map-objective placement + the representation/contest gap (both confirmed). The dominant, faithful, and
more tractable lever is the under-shooters' combat UNDER-OUTPUT (deal half the damage). Next: diagnose WHY AM/AdMech guns
under-output (weapon-picker fidelity — `project-antitank-picker-bias`).

**A — secondaries.py FIXED-secondary fidelity (cherry-picked 0216257):** LANDED Fix #1 — `no_prisoners` removed from the
FIXED pool (it is BANNED as a Fixed pick in tournament play, per the sim's own citation) and made Tactical-only; the
Fixed slot-1 fallback is now `cull_the_horde`. A faithful card-level fix that nudges the secondary count-bias the right
way (less body-army Fixed over-banking). audit clean, 105 tests pass, run.py --cli clean. N=80 = gated **5.84** vs 5.87
(`data/wf_wave180_noprisoners_fix_n80.txt`) — metric-NEUTRAL (−0.03, within noise; Imperial Knights eased 26.11→25.81).
Expected: on the union scoring path the moved card is still scored, so the nudge washes — the real benefit lands under
SWEG_TAC_DECK. Kept as a faithful rules-correctness fix. **Fix #2 VERIFIED (Wahapedia reachable), NOT yet implemented:** the
CA-2025-26 Fixed-vs-Tactical scoring split is REAL — the Tactical versions of the kill cards are a flat "did any
qualifying unit die this turn?" trigger (Assassination 5 victory points/turn, Bring It Down 4/turn, Cull 5/turn), NOT the
per-unit Fixed schedule the sim currently uses for both. The sim over-scores Tactical-track kill cards. Implementing the
Tactical schedules (a track check in `_score_one_card` + new cited entries with the verbatim Tactical card text the agent
captured) is a clean follow-up → task #67. Only matters on the SWEG_TAC_DECK path.

## Wave 179 (2026-06-04) — SWEG_TAC_DECK A/B: REGRESSES (5.87→6.77) — the real cadence is blocked by the AI-PURSUIT STALL (held objective-control cards achieve <20%)

A/B'd the candidate fix from wave 178 — `SWEG_TAC_DECK` ON (the real CA-2025-26 2-card cadence) vs the OFF default
(every-round-9), N=80 on the de-flattered real-list baseline. **It REGRESSED the headline:**

```
Faction              OFF gated   ON gated    Δ        Sim% OFF→ON
Chaos Space Marines    11.94      12.49    +0.55      41.2→40.7
Astra Militarum        13.54      13.76    +0.22      28.6→28.3
Adeptus Mechanicus     11.92      10.68    -1.24      28.3→29.6
World Eaters           14.31      11.82    -2.49      62.7→60.2
Imperial Knights       26.11      29.61    +3.50      76.8→80.3  (WORSE)
MAE gated               5.87       6.77    +0.90  (REGRESSED)
```
The under-shooters did NOT cleanly rise (AdMech better, CSM/AM slightly worse), and the OVER-side got WORSE (Imperial
Knights 76.8→80.3). This is the watchdog's predicted failure mode, and the achieve-rate probe
(`scripts/diag_tacdeck_achieve.py`) confirms the mechanism exactly:

```
Faction            TACTICAL%  achieve%      key board-card achieve-rates
Astra Militarum      100%       23%   defend_stronghold 9% / extend 7% / area_denial 17%
Adeptus Mechanicus   100%       25%   defend_stronghold 9% / extend 11% / area_denial 13%
Chaos Space Marines   38%       24%   defend_stronghold 10% / extend 11% / area_denial 4%
Imperial Knights       0%        -    (always FIXED — 2 kill cards every round)
World Eaters         100%       30%   defend_stronghold 8% / extend 12% / area_denial 19%
```

**ROOT CAUSE (the watchdog's crux, CONFIRMED): the AI-pursuit STALLS.** TACTICAL armies achieve only 23−30% of their
held cards, and the OBJECTIVE-CONTROL/board cards — the exact ones that should let body armies out-score the durable
Knight — basically never achieve (defend_stronghold 8−10%, extend_battle_lines 7−12%, area_denial 4−19%). Meanwhile
**Imperial Knights go 0% TACTICAL → always FIXED**, scoring 2 kill cards RELIABLY every round. So the deck makes the
durable FIXED armies out-score the stalling TACTICAL body armies → IK over-rate UP, MAE worse. Wave 121's AI-pursuit
layer is plainly insufficient.

**CONCLUSION: the deck flip does NOT land alone, and is NOT the fix by itself.** The real, faithful #1 lever is the
AI-PURSUIT: make a TACTICAL army move bodies to ACHIEVE its held board cards (hold the markers defend_stronghold /
extend_battle_lines / storm_hostile_objective require). That IS faithful (real players pick cards they can do and play to
do them) and it's the body army's real advantage (it has the bodies to hold markers). The real cadence (deck) and a
strong AI-pursuit are COUPLED — only together would body armies out-score Knights on secondaries, closing the over-side
AND the under-side at once. SWEG_TAC_DECK stays default-OFF (the OFF path is byte-identical; no regression banked). Routed
to the watchdog: the localized #1 lever is now the AI-pursuit stall — a real Stage-1 AI build, sized by the watchdog.

## Wave 178 (2026-06-04) — #1 lever LOCALIZED: the secondary gap is over-scored objective-control/action cards (every round, not the real 2-card cadence) → candidate fix already built (SWEG_TAC_DECK)

Decomposed the wave-177 secondary gap by card TYPE (`scripts/diag_secondary_breakdown.py`, wraps the scoring functions
to attribute every VP to the scoring side; 7 opp × 10 seeds). The eval runs the DEFAULT secondary path (SWEG_TAC_DECK
OFF), AND `_tier_a_enabled` / `_cleanse_enabled` / `_sabotage_enabled` are all DEFAULT-ON — so each side scores the UNION
of ~9 cards (4 kill + Engage + BEL + Cleanse + Sabotage + 5 board) EVERY round, not the real CA-2025-26 "hold 2 cards,
score at most those per turn" cadence:

```
Under-shooter         dKill   dPos   dObj   dTOT   (meObj/oppObj)
Astra Militarum       -14.5   -2.0   -7.8  -24.4   (42.7/50.5)
Adeptus Mechanicus     -6.1   -1.3  -14.3  -21.7   (38.3/52.6)
Chaos Space Marines    -3.1   -1.9  -19.8  -24.8   (28.9/48.7)
```
dKill = kill cards (BID/NP/Cull/Assn); dPos = Engage+BEL; dObj = Cleanse+Sabotage+5 board cards. dTOT reconciles to the
−22..−25 dSec from wave 177.

**LOCALIZED.** The dominant, growing component is dObj (objective-control/action cards): AM −7.8, AdMech −14.3, CSM
−19.8. Engage/BEL positional is tiny (−1.3..−2.0) — so it is NOT a spread/projection gap. It is the OBJECTIVE-CONTROL +
ACTION cards: body armies (high total OC, spare chaff to do actions) score 48−52 of these per game; low-model/low-OC
durable armies concede them (CSM only 28.9). **For CSM (NOT out-attrited) dObj −19.8 is almost the ENTIRE −24.8 loss** —
confirming CSM's problem is conceding objective-control secondaries, not combat (Dark Pacts #52 cannot help it). For AM
the kill gap also bites (dBID −8.7 vehicles + dAssn −9.3 characters = attrition, on top of dObj −7.8).

**This is a KNOWN fidelity gap with a fix already built.** The sabotage docstring (simulator.py:1148) already flags it:
cleanse/sabotage/board score every round, not rotation-gated to the real 2-card draw — "this over-scores them and
amplifies the over-correction of low-model armies." The M2 Tactical deck (`SWEG_TAC_DECK`, wave 119) models the real
CA-2025-26 cadence (each side picks FIXED = 2 kill cards, or TACTICAL = a 2-card draw/achieve/redraw hand — at most 2
scoring sources, not 9). It was **the first faithful lever to move the headline (4.41 → 4.13)** but kept default-OFF
pending an AI-pursuit refinement (the 2-card hand STALLS — the AI holds board cards it rarely achieves: defend_stronghold
11% / extend_battle_lines 9%), which wave 121 then built (AI-pursuit layer for held Tactical cards).

→ Resolves the watchdog's scoring-bias-vs-AI-pursuit question: BOTH are real. The every-round over-generation IS the
count-bias (deck-off); the held-card stall is a secondary AI-pursuit gap inside the deck-on path (wave 121 addresses it).
The candidate FAITHFUL fix exists and was previously net-positive — but its only A/B was on the OLD FLATTERED 4.41
baseline. **NEXT: re-run the `SWEG_TAC_DECK` A/B (OFF vs ON) on the CURRENT de-flattered real-list baseline (gated 5.87,
N=80), report the per-faction deltas for AM/AdMech/CSM + the over-side, and the held-card achieve-rates (AI-pursuit
health).** Measure-only (gated); a default-flip would need user greenlight (coherency-flip precedent). NO fabrication —
this is the real CA-2025-26 secondary cadence, faithful regardless of metric direction.

## Wave 177 (2026-06-04) — #1 lever diagnostic: COVER REFUTED; loss segments to SECONDARY (biggest) + AM/AdMech ATTRITION

The de-flattered baseline's #1 lever is the durable-shooty-vehicle under-valuation (AM/AdMech/CSM). Watchdog/user
hypothesis: the sim under-grants cover (point-inside-terrain only, no behind-cover) → durable vehicles over-exposed →
over-die. Instrumented it (`scripts/diag_vehicle_cover.py`): when a durable VEHICLE (VEHICLE + ≥8W) is damaged, how often
is it in cover? **Result: 63% (Astra Militarum), 69% (AdMech), 44% (CSM) — NOT ~never. COVER hypothesis REFUTED.** The
vehicles ARE in cover a majority of the time (their positions land inside terrain), and cover wouldn't help vs the
anti-tank that kills vehicles anyway. So the no-behind-cover gap is NOT the driver. Cover stays as-is (the point-vs-base /
behind-cover 10e gap is a minor separate fidelity item, noted not chased).

Then segmented the loss for all three (`scripts/diag_undershooter.py`, generalizing the AdMech diag — primary VP /
secondary VP / survival, vs 7 opponents × 10 seeds each):

```
Under-shooter         win%  dPrim   dSec   MEsurv OPPsurv  dSurv
Astra Militarum        36%   -9.2  -24.4    28%    61%    -33%
Adeptus Mechanicus     23%  -15.2  -21.7    28%    61%    -33%
Chaos Space Marines    33%   -9.4  -24.8    39%    43%     -4%
```

NOT one clean mechanism — three findings:
1. **The SECONDARY gap is the LARGEST, most consistent component** (−22 to −25 across all three) — bigger than the
   primary gap. Not predicted; points at the M2 actions-cost-units secondary deck under-scoring for low-model-count
   armies (fewer spare unit-activations to spend on actions + fewer kills for kill-cards).
2. **AM/AdMech are heavily OUT-ATTRITED** (28% survive vs opp 61% — ground down), but **CSM is NOT** (−4%, even). So
   AM/AdMech have an attrition problem on top (out-traded — NOT cover; next test = damage DEALT vs TAKEN by their
   vehicles to split under-output from over-fragility). CSM does not.
3. **CSM survives fine yet still loses primary (−9.4) AND secondary (−24.8)** — so CSM's loss is SCORING/POSITIONAL, not
   attrition. (This is why CSM Dark Pacts #52 — a combat buff — would NOT close CSM; its problem is scoring, not killing.)

The unifying thread is the SECONDARY under-scoring (all three, the biggest single factor, a known sim subsystem) — the
likely under-side mirror of the over-side representation floor (the scoring game rewards model/unit COUNT; low-count
durable armies under-hold objectives AND under-spend on action-secondaries). The AM/AdMech attrition is a separate combat
factor. NEXT (instrument-first, my default unless the watchdog redirects): decompose the −24 secondary gap by card type
(kill-based vs positional vs action) to confirm it is a real low-count representation bias and not just a losing-army
artifact, AND split AM/AdMech attrition into damage dealt-vs-taken. NO fix until the secondary gap's cause is localized.

## Wave 170-171 (2026-06-04) — COHERENCY FLIPPED default-ON (re-base 4.05→3.93) + AdMech under-side diagnostic: loses on ATTRITION

**Coherency flip (user-greenlit, watchdog-executed, commit `73ee2f4`):** Stage B (`SWEG_COHERE`) now default-ON. N=80
confirm = **gated 3.93** (re-based from 4.05; `data/wf_wave170_cohere_default_n80.txt`). Symmetry CONFIRMED: Imperial
Knights gated 27.45→24.09 (−3.3), under-holder Necrons 4.88→3.27 rose, Sororitas 4.05→2.29. Accepted collateral (the
over-side floor): Astartes 0→2.52, World Eaters 10.0→11.57. Net +0.12. REFINEMENT: Astra Militarum did NOT rise (~flat)
— NOT a clean under-holder (its gap is output/screening/list). OFF path (`=0`) still reproduces 4.05.

**AdMech under-side diagnostic (`scripts/diag_admech.py`, on the new coherency-on baseline):** segmented where AdMech
(biggest under-shooter) loses across 8 matchups (win 39%). **It loses dominantly on ATTRITION** — survival 38% vs
opponents' 60% (−22 pts) — which drives a primary-VP loss (AMprim 32.0 vs OPP 39.5, dPrim −7.5); secondary is nearly
competitive (63.7 vs 71.7). Worst: Imperial Knights (10% win, survival 26% vs 85%, dPrim −21.5), Tyranids (30%); its one
win is vs Astra Militarum (60%). So AdMech is OUT-DAMAGED + FRAGILE (a two-sided attrition deficit), not out-secondaried.
**Doctrina Imperatives is already modelled + impactful** (offensive Conqueror + defensive Protector effects in
`units.py`, picked per Command phase) — NOT the missing lever. So AdMech's deficit is STRUCTURAL. NEXT sub-diagnostic
(don't pre-judge): split the survival gap into under-OUTPUT (doesn't kill enough) vs over-FRAGILITY (takes too much) —
and check the remaining watchdog candidates (archetype list competitiveness, mid-model-shooty representation, residual
fragility beyond Go To Ground). Stage-2 re-price (balancer gate-off-vs-on) still queued.

**Wave 172 — AdMech LIST-REALISM check (watchdog step 1): the list IS representative → NOT the lever → AdMech is an
under-side REPRESENTATION FLOOR.** The archetype is a CURATED, CITED list (`code/archetypes.py:1058`, "Skitarii Hunter
Cohort", referencing Goonhammer May-2026 Detachment Focus + Frontline GT + Stat Check aggregate). It carries the durable
core (Cawl, Kataphron Breachers + Destroyers, Onager, Skorpius Disintegrator, Skitarii battleline); the infantry-heavy
silhouette is BY DESIGN (Skitarii Hunter Cohort is an infantry detachment). So the fragile-infantry weighting is
faithful, not a builder bug (one minor artifact: the expensive Onager realizes at 0.4/btl vs seed weight 1 — cheap
Skitarii crowd it out — but reshaping that edges into win-rate tuning, left alone). With the list representative + Doctrina
modelled + no missing rule, AdMech's attrition deficit is the mid-model-shooty REPRESENTATION FLOOR (a representative
fragile-infantry army over-dies in the one-Unit-per-model + size-1-swarm representation, 38% survival) — the under-side
MIRROR of the over-side melee floor. No clean faithful fix; ACCEPT it (per the over-side precedent) and pivot to CSM
(#52 Dark Pacts holistic — the more concrete under-modelled army rule, the tractable under-outputter). NEXT: CSM.

## Wave 169 (2026-06-04) — GROUP-2 #3 battle-shock crumbling DIAGNOSTIC → NULL (melee crumbles faithfully) → over-side levers EXHAUSTED

The last cheap Group-2 probe (watchdog-steered, instrument-first). `scripts/diag_battleshock.py` wraps
`_run_battleshock_phase` and counts, per faction, below-Half squad-rounds vs crumbles (failed 2D6-vs-Ld → OC 0). The
sim already models crumbling (per-squad below-Half gate, OC→0 + stratagem lockout on failure, Mob Rule / Synapse
auto-pass short-circuits). **Result — the melee over-shooters crumble at LEAST as much as gunlines:** below-Half/btl
World Eaters 4.89 / Tyranids 4.17 / Drukhari 4.83 (vs gunlines 3.2-3.9 — they grind and take more casualties), crumble%
~30% across both (Astra Militarum 23%, Votann 21% slightly less). So the sim is NOT under-crumbling the melee
aggressors — they erode (lose OC when depleted) faithfully. **#3 is NULL as a Group-2 lever.**

**All cheap Group-2 over-side levers are now exhausted on evidence:** melee attacker-count (refuted — size-1-swarm
lists), split-fire (neutral, landed gated), fight-alternation (rejected — doubling over-rates durable melee),
battle-shock crumbling (null — faithful). **The over-side melee residual is confirmed as needing the BIG
bounding-fidelity track (Fall-Back-to-disengage AI + one-exchange combat resolution — multi-wave, uncertain reward) OR
accepting it as a representation floor — the USER's call** (routed via watchdog, was gated on this #3 result). The
queued PIVOT axis is the under-side (docs/UNDERSHOOTER_PLAN.md): Phase 1 = the standing Stage-B coherency FLIP decision
(faithful + metric-positive 4.05→3.93 + closes under-holders Necrons/Guard — a free win, also the user's call); Thread B
= the AdMech deep diagnostic (biggest under-shooter, structural, instrument-first). Honest baseline UNCHANGED: N=80
gated **4.05** default / **3.93** Stage B on.

## Wave 168 (2026-06-04) — COMBAT REBUILD (fight-phase alternation) — user-greenlit, order CORRECTED, fairly A/B'd → DEFINITIVELY REJECTED

The user greenlit the combat rebuild. The wave-166 build used the WRONG alternation order (active-first both steps);
the watchdog verified the authoritative 10e order from Wahapedia quick-start ("Units that charged this turn fight before
all others. Then, starting with the player not currently taking their turn, players alternate"). Corrected
`_run_fight_alternation` (Fights First step starts ACTIVE; Remaining Combats step starts NON-active/defender), updated
the `simulator.fight_alternation` citation verbatim, commit `afdd2a3` (audit clean, run.py both paths, tests green, OFF
still byte-identical).

**Corrected-order A/B (alt-only N=40): gated 7.31** (vs OFF 4.20 — even WORSE than the wrong-order 6.70). Same severe
backfire, slightly amplified: World Eaters +23.4 (gated 20.0), **Imperial Knights +39.7 (gated 36.7, up from 30.4
baseline)**, Chaos Knights 14.8, Death Guard, Custodes, Daemons, GSC, Grey Knights — durable melee/elite ALL UP; Necrons,
T'au, **Astra Militarum 12.8, AdMech 10.9** — fragile shooters crushed.

**DEFINITIVE REJECT (the order detail doesn't matter — the DOUBLING dominates).** Faithful 10e ~doubles fight frequency
for locked combats; durable melee armies (which usually charge → strike first in the Fights First step regardless of the
remaining-step order) fight twice per round and over-accumulate, while fragile shooters are ground down twice as fast.
The defender-first-remaining fix just adds MORE doubling, hence slightly worse. **Not metric-protection:** real
tournaments use twice-per-round melee yet show World Eaters +13.9 (sim hits +23.4) and Imperial Knights +30.4 (sim hits
+39.7) — so the doubling moves the sim FAR from reality. The sim's melee is already calibrated (via its other
approximations) to once-per-round; the faithful doubling would need the MISSING bounding fidelity (Fall-Back-to-disengage
AI + realistic one-exchange combat resolution) BEFORE it matched reality. Faithful-in-isolation, unfaithful-in-effect
(the Stage-E pattern). Swings dwarf noise → no N=80. `SWEG_FIGHTALT` kept gated default-OFF as the rejected experiment
(the corrected code is the correct 10e implementation, available post-recalibration). Honest baseline UNCHANGED: N=80
gated **4.05** default / **3.93** Stage B on.

**The fight-phase lever is dead.** The Group-2 melee over-shoot needs the missing bounding fidelity (Fall-Back AI /
combat resolution) — a bigger, separate fidelity track — or candidate #3 (battle-shock crumbling), NOT the alternation.

## Wave 166 (2026-06-04) — GROUP-2 #2 BUILT: faithful 10e fight-phase alternation (gate `SWEG_FIGHTALT`, OFF byte-identical) — A/B pending

STEP 2 of the watchdog-confirmed Group-2 lever (the over-credit differential was proven in wave 163: denied-retaliation
per battle World Eaters 56.5 vs T'au 1.9, ~30x). The vanilla fight loop fought ONLY the active army's units, deferring
the defender's retaliation to its own later turn — letting melee aggressors delete defenders before they swing back.
`Battle._run_fight_alternation` (gate `SWEG_FIGHTALT`) restores 10e: BOTH armies' eligible units fight in this Fight
phase, alternating ONE at a time (Fights First step — chargers + the Fights First keyword — then Remaining Combats),
the active player selecting first in each step; each unit fights at most once per phase, and because a round runs both
turns a locked unit fights in both fight phases (twice/round, as 10e intends). Cited `simulator.fight_alternation`
(Wahapedia core rules; the two-step alternation is verbatim, the active-first first-selector is the canonical reading —
secondary summaries differ on that second-order tie-break, flagged for confirmation; the dominant in-phase-retaliation
mechanism is order-robust).

**Build verified:** audit clean, run.py exit 0 both paths, full suite **1127 passed** (3 new `tests/test_fight_alternation.py`
proving the defender retaliates in-phase, the vanilla per-model fight gives no retaliation, and no unit fights twice per
phase), and **OFF N=40 reproduces 4.20 / 8-in-band exactly** (gate unset runs the original active-only loop verbatim →
byte-identical). Committed as a build (A/B follows) per the Stage-A stash-loss lesson.

**A/B RESULT — variant (a) full-doubling REJECTED (severe backfire; the doubling confound dominated):**
alt-only N=40 gated **6.70** (vs OFF 4.20, +2.50 WORSE), 5/22 in band. Per-faction the OPPOSITE of intended — the
DURABLE-melee/elite armies went UP and the fragile shooters DOWN: World Eaters 64→69 (gated ~21), Imperial Knights
gated 34.3, Chaos Knights 12.9, Death Guard 8.4, Adeptus Custodes 7.3, Chaos Daemons, Genestealer Cults, Emperor's
Children — all UP; Necrons (gated 11.7), T'au (5.2), Astra Militarum (9.7), Adeptus Mechanicus (7.1) DOWN. Faithful 10e
~doubles fight frequency for locked combats, and the doubling (durable melee fighting twice/round, accumulating across
rounds) DOMINATED the in-phase-retaliation rein, the design-wave worry confirmed.

**Why this is a REJECT, not metric-protection:** real tournaments DO use 10e twice-per-round melee yet show World
Eaters at +13.9, NOT +24.5 — so naive doubling moves the sim FURTHER from reality. The sim lacks the compensating
fidelity that bounds twice-per-round melee in real play (Fall-Back-to-disengage AI, and most combats resolving in ONE
exchange so they never reach the second fight phase). Doubling WITHOUT that is unfaithful-in-EFFECT (like Stage E) — it
over-credits durable melee. Swings dwarf noise → no N=80 needed.

**The lever is not dead — the DOUBLING is.** The STEP-1 over-credit is real (World Eaters denies 56.5 retaliation/btl),
so variant **(b)** — the defender retaliates IN the attacker's phase but does NOT also fight in its own turn (each unit
still ~once/round, just better-ordered so the defender isn't over-killed before swinging) — isolates the rein from the
doubling confound. `SWEG_FIGHTALT` (a) is kept gated default-OFF (rejected experiment + the infra `_run_fight_alternation`
that (b) refines). NEXT: build (b) (per-round fought-tracking so a retaliating defender skips its own-turn re-fight),
A/B; if (b) also washes/backfires, the fight-phase lever is dead → move to #3 (battle-shock crumbling). Watchdog to
confirm (b) vs #3.

## Wave 162 (2026-06-04) — GROUP-2 DIAGNOSTIC: melee attacker-count (#1) REFUTED by the data → fight-phase alternation (#2) is the real lead

The watchdog-confirmed next lever (OVERSHOOTER_PLAN Phase 2 #1): instrument the melee attacker-count BEFORE building —
does the sim let a large unit land more attackers than can physically reach base contact? Two read-only probes
(`scripts/diag_melee_attacker_count.py` + a list-composition probe):

**Finding 1 — the sim IS one-Unit-per-model** (`add_squad` builds `size` Units sharing `squad_id` on the legacy /
gates-off path). So the premise (N models per squad) is real in principle.

**Finding 2 — but the LISTS are size-1 swarms, universally.** The archetype builder re-picks the same profile across
fill iterations and stacks many size-1 squads (World Eaters seed-1: TWO real squads — 10 Berzerkers, 10 Jakhals — then
10 separate single Chaos Terminators, 8 single Chaos Spawn, loose single Jakhals/Bloodletters). Across factions, **65-78%
of units sit in size-1 squads** (World Eaters 69%, Tyranids 72%, Drukhari 67%, **Astra Militarum 77%**, AdMech 64%),
mean squad size 1.3-1.5. This is FACTION-NEUTRAL — the under-shooter Astra Militarum is the HIGHEST.

**Finding 3 — melee attacker-per-defender ratios are plausible.** At fight time the typical attacking squad is ~1.5-2.9
alive Units, ~88% in Engagement Range, vs ~1.1-1.8-model targets; attacker-models-in-ER per defender-model ≈ 1.0-1.95
(World Eaters highest 1.95). No gross over-count (a "20 swing on a 5-screen" bug would read ~4+).

**→ #1 (per-model Engagement-Range melee cap) is REFUTED:** there are no large squads to cap (size-1 swarms), the
ratios are geometrically plausible, and the size-1 representation is faction-neutral so it cannot drive the over-shoot
differential. Per the watchdog's branch ("if attacker-count is faithful → move to #2/#3"), the lever is not here.

**THE REAL LEAD — #2 fight-phase alternation.** While in the fight code: the Fight phase loop (`_run_round_vanilla_turns`)
iterates ONLY `active.units` — the active player fights ALL its units this phase, and the defender does NOT swing back
until its OWN turn (confirmed by the code + the comment "the other player's reactive fights resolve in their own turn's
Fight phase"). Real 10e ALTERNATES (chargers fight first, then players alternate selecting units, starting with the
NON-active player), so a charged unit fights back IN THE SAME phase and can blunt the attacker before it finishes. The
sim's "active kills before the defender hits back" differentially favours MELEE AGGRESSORS (melee is their whole output;
a gunline already shot) — which is exactly the Group-2 over-shooter profile (World Eaters / Tyranids / Drukhari). This
is faction-neutral fidelity (the test: correct even if it moved the metric the wrong way) and a far better-fitting lead
than #1. NEXT: instrument + (watchdog-confirmed) build the 10e fight-phase alternation. Diagnostic wave — no code change.

## Wave 161 (2026-06-04) — SQUAD REBUILD STAGE D: unit-orchestrated split-fire shooting BUILT (gate `SWEG_SQUADSHOOT`, OFF byte-identical) — A/B pending

The rebuild's last behavioural lever, per the watchdog's confirmed shape (C+A infra → B coherency → D split-fire; E
dropped). 10e lets a unit split its fire — "all of the models in the unit do not have to target the same enemy unit" —
but SwegHammer's one-Unit-per-model representation fires each model independently and the lowest-effective-health
picker piles the whole squad onto one target, wasting overkill. Stage D adds `Battle._plan_squad_fire`: computed once
on a squad's first firing model, it walks the squad tracking expected wounds COMMITTED to each enemy — anti-armour
models concentrate on the nominated focus brick, the rest take the lowest-effective-health target they can still
meaningfully hurt that is not yet lethally committed, so once a target has lethal fire the next model moves on (real
split-fire: remove MORE units, don't over-kill one). `_do_shoot` validates each assignment against the firing model's
own legal pool (range / line-of-sight / engagement stay per-model) and falls back to the per-model pick if the assigned
target is dead or unreachable — "wrapper-not-mutate" per the watchdog. Deterministic (no RNG). Cited
`simulator.split_fire` (data/rule_citations.d/core_split_fire.json).

**Build verified:** audit clean, run.py exit 0 both paths, full suite **1127 passed** (3 new `tests/test_split_fire.py`
covering the two-shooters-split, single-enemy-no-split, and no-enemies cases), and **OFF N=40 reproduces 4.20 / 8-in-band
exactly** (the gate unset leaves the plan empty and `_assigned` None → byte-identical). Gate default-OFF, so the default
baseline is unchanged (N=80 gated 4.05). Committed as a build (the A/B follows next wave to avoid holding the large,
risky shooting change uncommitted) — per the Stage-A stash-loss lesson.

**A/B RESULT (landed gated, faithful + metric-NEUTRAL):**
- D-only N=40 gated **4.19** (vs OFF 4.20) — a wash; per-faction moves all within noise.
- B+D N=40 gated **4.17** (Imperial Knights 74.4, B's coherency effect showing through) — D adds nothing harmful.
- B+D N=80 gated **4.03** (Imperial Knights 74.4 / gated 23.76) vs B-only N=80 **3.93** and OFF **4.05**.
- The sign of D's effect FLIPS across N (−0.01 at N=40, +0.10 at N=80) — the signature of sampling noise, not signal.
  So **split-fire is faithful and metric-neutral**: a legitimate fidelity improvement (real 10e — a unit's models need
  not all target one enemy) that does not move the headline. Expected: the over-shoot is a MELEE representation issue,
  not shooting inefficiency, so better target allocation cannot reach it.

**Verdict:** D LANDS gated default-OFF (keep-if-faithful), already committed `a9f87bf`. It is NOT part of the
metric-improving default — B alone (3.93) is the rebuild's gain; B+D (4.03) adds ~0.10 of noise, so any future flip is
B-only, not B+D. **This concludes the squad rebuild's behavioural investigation:** B (coherency) faithful + metric-
POSITIVE (the one real gain, 4.05→3.93, Knight −3.3); D (split-fire) faithful + metric-NEUTRAL; E (cohesive hold)
unfaithful-in-effect + REJECTED. The rebuild DENTS the Knight floor (27→24) but does not close it — the residual is
the MELEE one-Unit-per-model over-representation (Group-2 / OVERSHOOTER_PLAN: melee attacker-count), which the
positional rebuild structurally cannot reach. NEXT lever is that Group-2 work, or Stage 2, per the watchdog.

## Wave 160 (2026-06-04) — SQUAD REBUILD STAGE E: cohesive objective holding TESTED and REJECTED (net regression; reverted, not landed)

Stage E was the plan's next behavioural stage: promote the Objective-Control-massing positioning that the anti-Knight
`SWEG_M4` experiment proved (a model carrying Objective Control near a marker genuinely moves into the 3" scoring band,
`_m4_cluster_intent`) from a Knight-specific stack component to the general squad-hold default, behind its own sub-gate
`SWEG_COHEREHOLD`. Built, gate-tested (4 new + 11 existing M4 tests green, audit clean, both run.py paths exit 0, OFF
byte-identical), then A/B'd at N=40 — **and rejected on the result.**

**N=40 A/B (OFF / B-only baseline both 4.20):**
- **E-only (`SWEG_COHEREHOLD=1`): gated 4.73** — a regression.
- **B+E (`SWEG_COHERE=1 SWEG_COHEREHOLD=1`): gated 4.49** — still a regression (coherency only partly tames it).
- Per-faction the distortion is structural and far above noise: it crushes Imperial Knights (79.5 → 62.9, −16.6, the
  biggest Knight drop of anything tested) BUT wildly inflates cheap-Objective-Control spam factions — Drukhari +12
  (gated 1.79 → 13.68), Orks +9 (0 → 7.62), Sororitas — while cratering Chaos Daemons −9, Astra Militarum −6, T'au −8.

**Why rejected (and why this is NOT metric-protection):** forcing every Objective-Control carrier to rush the nearest
marker over-credits the one-Unit-per-model HORDE representation — cheap bodies flood markers in a way real play (with
screening, casualties, board geometry) does not. It crushes the Knight by an *unfaithful sledgehammer* that amplifies
the very over-representation the rebuild is fighting, not by a faithful fix. So E makes the sim LESS faithful; rejecting
it is correct, not metric-tuning. The N=40 per-faction swings dwarf the noise floors, so the verdict is robust without
an N=80 (no point spending it on a clearly-rejected candidate). The faithful coherency gain already landed in Stage B
(Knight −3.3 at N=80 without distorting the table); E over-does it.

**Action:** reverted the Stage E code entirely (the `SWEG_COHEREHOLD` gate was redundant over the existing `SWEG_M4`,
which gives the identical mechanism for any future test). Tree restored to wave-159 `644efef`. Honest baseline unchanged
at N=80 gated 4.05 (default) / Stage B `SWEG_COHERE` 3.93. RECONSIDERS the rebuild shape: B (landed) delivers the
faithful positional gain; E drops out; **next is Stage D (unit-orchestrated split-fire shooting, `SWEG_SQUADSHOOT`)** —
a distinct lever (firepower distribution, not objective massing). Flagged to the watchdog (the E rejection + the still-
open Stage-B flip-timing fork). No code change this wave — the negative result is the deliverable.

## Wave 159 (2026-06-04) — SQUAD REBUILD STAGE B: mid-game Unit Coherency enforcement (gate `SWEG_COHERE`) — first behavioural landing; N=80 gated 4.05 → 3.93, Imperial Knights −3.3

The first INTENTIONAL behaviour change of the squad rebuild. After every model of the active army has taken its
individual Movement-phase move, `Battle._enforce_squad_coherency` pulls any model left out of Unit Coherency (more
than 2" from its nearest squadmate) back toward its squad centroid, spending only the move the model has left this
phase (Move characteristic minus distance already moved). This is the real 10e core rule — "all of its models must
be ... moved so that the unit is in Unit Coherency" — that the one-Unit-per-model representation breaks: the per-model
move AI lets a squad scatter, stranding models outside the 3" Objective Control band. Deterministic (no random draws),
lone models and Advanced / Fell-Back models skipped. Cited as `simulator.coherency_enforcement`. Gate default-OFF;
the OFF path is byte-identical (verified: N=40 OFF reproduces 4.20, N=80 OFF reproduces the 4.05 honest baseline
exactly — 9/22 in band, Imperial Knights +30.4 / gated 27.45).

**N=80 A/B (the robust read; N=40 was a noise-level wash 4.20→4.20):**
- Headline **gated 4.05 → 3.93** (−0.12, a genuine small improvement — the over-side gains beat the collateral).
- **Imperial Knights 78.1% → 74.8% (−3.3), gated 27.45 → 24.09 (−3.36)** — the #1 residual, moving in the intended
  direction and above its 2.96 noise floor. This is the rebuild lever working: coherent body squads mass their
  Objective Control onto markers, contest the Knight's objectives, and cut its victory-point dominance.
- Other faithful gains: Necrons (under-shooter) gated 5.13 → 3.27, Sororitas 3.57 → 2.29, Thousand Sons 1.05 → 0.37,
  Votann 7.20 → 6.77.
- Collateral (the M4-α inseparability, predicted): Adeptus Astartes leaves the band (gated 0.00 → 2.52 — tighter
  Marine squads over-hold), plus small over-side ticks (World Eaters +0.61, Emperor's Children +0.55, Drukhari +0.47).
  The in-band count 9 → 5 overstates this: Orks/T'au/Death Guard only crossed by 0.12–0.31 (noise-edge); only Astartes
  meaningfully left.

**Honest caveat:** Stage B *dents* the representation floor — the Knight is still +27 (gated 24.09), far out of band.
It is a partial fix, not a resolution; the full lever is the B+E+D stack (cohesive hold + split-fire) plus the
over-shooter fidelity work. Verification: audit clean, run.py exit 0 both paths, full suite 1124 passed / 1 skipped
(5 new `tests/test_squad_coherency.py`). Landed gated default-OFF (default baseline unchanged at 4.05).

NEXT: a flip-timing fork for the watchdog (flip `SWEG_COHERE` default-ON now — it is faithful AND improves the
headline, per the fidelity-first rail — vs hold for the combined B+E landing the plan sequences together). Then
Stage E (cohesive objective holding, reuses `SWEG_COHERE`), then Stage D (split-fire shooting, `SWEG_SQUADSHOOT`).

## Wave 158 (2026-06-04) — SQUAD REBUILD STAGE A: per-squad activation scaffold (gate `SWEG_SQUADACT`, byte-identical inert cache)

The second stage of the user's Q11=(c) authorised positional re-model, built on the Stage C budget infra (wave 157).
Stage A adds the per-squad activation substrate the behavioural stages (B coherency, D split-fire, E cohesive hold)
will read, but is itself a **no-behaviour-change scaffold**. In `Battle.__init__` two caches are added —
`_squad_move_intent: dict` and `_squad_activated_this_phase: set`; both are reset at the top of each Movement phase in
`_run_round_vanilla_turns`. Behind `SWEG_SQUADACT=1`, the Movement loop now computes `pick_move_intent(...)` ONCE on
the first alive model of each squad (keyed by `squad_id`, falling back to `id(unit)` for single-model units), caches
it in `_squad_move_intent[skey]`, and emits one `UnitActivated` telemetry event per squad. Every model still runs its
own `_do_move` exactly as before — the cached intent is **unread**, so the scaffold is inert.

Two facts make this byte-identical with the gate ON or OFF: `pick_move_intent` is deterministic (no random draws), and
`UnitActivated` is renderer-only telemetry that the evaluator never reads. **Verified three-way byte-identical**: a
clean-base N=40, gate-OFF N=40, and gate-ON N=40 eval are all identical (2213 bytes, gated MAE 4.20, 8/22 in band).
Audit clean, run.py exits 0 on both paths, full suite **1119 passed / 1 skipped**. (Recovered from a background build
agent that completed the work + the three-way verification but stalled before committing; the patch was applied to the
branch and re-verified here.)

NEXT: Stage B — mid-game coherency enforcement (gate `SWEG_COHERE`), the first INTENTIONAL behaviour change of the
rebuild (a straggler >2" from its nearest squadmate is nudged toward the squad centroid within its remaining move).
This is where the representation lever starts to bite (Knight over-hold vs body over-shoot), so it gets a full N=40
then N=80 A/B. The stratagem-fidelity cleanup batch (7 items) still slots between rebuild stages.

## Wave 156 (2026-06-03) — TITANIC overwatch BUG FIXED (user-corrected): TITANIC units CANNOT Fire Overwatch. Removes the illegal Knight overwatch → honest baseline 4.17 → 4.05

The "overwatch TITANIC fix" the watchdog flagged as part of the main event, timely now that Overwatch is default-ON
(wave 155). Verbatim 10e restriction (now in the `simulator.fire_overwatch` citation): "You cannot target a TITANIC
unit with this Stratagem" — the stratagem's TARGET is the FIRING/overwatching unit (user-corrected an earlier
watchdog mis-read that put the restriction on the enemy), so a TITANIC unit cannot be SELECTED as the overwatcher.
Fix: exclude TITANIC units from the eligible-shooter loop in `_fire_overwatch` (skip `unit` if "TITANIC" in its
keywords). One line + the citation.

**N=80 A/B (vs the 4.17 honest baseline): headline 4.17 → 4.05.** The Knights came DOWN — they were ILLEGALLY
overwatching: Chaos Knights +12.7→+9.3 (gated 9.40→6.01), Imperial Knights +31.8→+30.4 (28.82→27.45). A faithful
over-side improvement (removing illegal firepower), NOT a knob. **So the truly-honest baseline — faithful core
mechanics ON minus the illegal TITANIC overwatch — is N=80 gated 4.05, 9/22 in band.** Net of waves 155-156: 3.90
(flattered) → 4.17 (honest but with the TITANIC bug) → 4.05 (honest, TITANIC fixed). Audit clean, 1119 tests green,
run.py exit 0. 4.05 is the new reference baseline for the squad rebuild A/Bs.

NEXT: the squad rebuild Stage C (the user's Q11=(c) authorised positional re-model, pure-infra first stage) on the
4.05 baseline. Plus the watchdog's user-requested stratagem-fidelity cleanup batch (7 items: Counter-Offensive
already-fought guard, Tank Shock MW math, Heroic Intervention re-add, Command Re-Roll WHEN-expansion, Aeldari Warhost
INFANTRY subfilter, unimplemented core strats, Disgustingly Resilient MONSTER check) to slot between rebuild stages.

## Wave 154-155 (2026-06-03) — CORE-MECHANIC AUDIT + user-authorised FLIP: Fire Overwatch + Go To Ground are faithful → default-ON. HONEST re-base 3.90 → N=80 gated 4.17 (9/22 in band, up from 6)

The watchdog's queued core-mechanic re-eval, which outranked another micro-ability because it asks whether the
BASELINE itself is faithful. **Audit verdict (wave 154): both `SWEG_OVERWATCH` and `SWEG_GTG` are FAITHFULLY
implemented** (Overwatch: 1 CP, once-per-round-per-army, unmodified-6s-only, both sides, only the moving/charging
target; GtG: 1 CP, INFANTRY-only, 6++ + Benefit of Cover, even-handed — 10e has no Normal-Move restriction, so the sim
is correct). No bug. But both were gated default-OFF, so the 3.90 baseline was missing two universal core mechanics.

A/B (N=40, OFF 4.15): both-on 4.29, GtG-alone 4.30 — both REGRESS, because the OVER-RATED armies exploit the faithful
mechanics (Fire Overwatch: durable Knights overwatch hard on 6s, Chaos Knights +6.3→+13.9; GtG: infantry over-shooters
GtG their bodies, WE +14.7→+17.7). So the 3.90 was FLATTERED by suppressing them — the 5th+6th line of evidence for
the per-model representation floor.

**Wave 155 — FLIPPED both to default-ON (user pre-authorised fidelity-first baseline; the audit was the only
condition).** `os.environ.get("SWEG_X", "1") == "0"` — default-ON, disable only via explicit `=0` (retained for A/B).
Two stale gate-off tests updated to the new explicit-disable semantics. **HONEST N=80 re-base: gated 3.90 → 4.17, 9/22
in band (UP from 6)** (`data/wf_wave155_honest_baseline_n80.txt`). This is an honest RE-BASE, NOT a regression — the
distribution is MORE accurate (3 more factions correctly placed); the MAE rose only because the already-out-of-band
Knights widened (IK 28.82, Chaos Knights 9.40 — Overwatch). Flipping faithful core mechanics ON is the OPPOSITE of
metric-tuning (it raises the headline). 4.17 is the new reference baseline for all rebuild A/Bs. Audit clean, 1119
tests green, run.py exit 0.

**AdMech diagnostic (wave 155):** the archetype is MISSING Kastelan Robots (T9 W7 2+/5++, the durable anchor) + Hastarii
— a real list-fidelity gap (held for after the rebuild per the watchdog). NB the N=40 AdMech-GtG improvement
(−12.6→−7) WASHED at N=80 (AdMech −12.2 unchanged) — so that infantry-fragility lead is weaker than N=40 showed.

**NEXT: the squad rebuild (the user's authorised Q11=(c) positional re-model) on the honest 4.17 baseline** — the
systemic lever for the IK + over-shooter representation floor.

## Wave 150-153 (2026-06-03) — OVER-SIDE diagnosis CONCLUSIVE: the over-shooter cluster is the per-model REPRESENTATION FLOOR. WE rule-audit (clean), CSM holistic re-scoped (needs infra), kiting counter-play A/B REGRESSED (backfires). Path below 3.90 = the systemic user-fork

Four waves working the over-side per the watchdog's "diagnose, don't knob" pivot. **Conclusion (4 independent lines
of evidence): the over-shooter cluster (WE +13.4, Drukhari, Votann, Tyranids, Sororitas) + the IK floor + AdMech
structural = the one-Unit-per-model MELEE REPRESENTATION over-rating, NOT faithfully-removable rules or a missing
counter-play.**

- **Wave 150 — World Eaters rule audit:** every WE buff is conservative-to-UNDER-modelled (Blessings 3/12, the
  Berzerker Warband detachment over-bias fab already removed, Blood Tithe deduped against the one-model amplification,
  charges 2D6 + per-squad-capped) yet WE still over-shoots +13.4. Rules out the over-modelled-rule hypothesis. No knob
  committed (correct — a negative diagnostic, not a failure).
- **Wave 151 — CSM holistic (#52) re-scoped to multi-wave:** the offsetting synergies don't exist at wave scale — the
  army-wide Marks of Chaos need PER-UNIT MARK-ASSIGNMENT infra (a list-build data layer; assuming a mono-mark army to
  force the offset would be a metric-chasing knob), the Dark-Pact enhancements are one-per-roster (too small), and the
  Dark Apostle "Ld-mitigation" the watchdog assumed DOESN'T EXIST at BSData (declined per the no-fabrication rail).
  So the isolated Dark Pacts fix stays unshipped (wave-146 band-aid) and CSM is parked behind the mark-assignment infra.
- **Wave 152-153 — kiting counter-play:** the two faithful kiting moves are largely PRE-EXISTING (fall-back-from-melee
  exists; coordinated focus-fire = SWEG_FOCUS already washed). Built the bounded `SWEG_KITE` move-(2) probe — an
  env-gated, default-OFF, OFF-byte-identical target-priority bias toward EXPOSED enemy melee-class units (no extra
  shots, no re-shoot — faithful to the watchdog's rail). **N=40 A/B: headline 4.15 → 4.50 (REGRESSED); World Eaters
  +14.7 → +16.5 (WORSE, not better).** The bias BACKFIRES: focusing fire on durable T4 Berzerkers wastes shots that
  don't kill them instead of clearing easier targets, so the melee army survives and wins MORE. **The problem isn't
  target selection — it's the per-model melee OUTPUT.** Kept gated default-OFF as a documented experiment (the OFF
  baseline 3.90 is unaffected).

**Strategic state:** the autonomous per-faction + AI-counter-play exploration has CONCLUSIVELY run its course (N=80
4.55 → 3.90). The path below 3.90 is the SYSTEMIC representation work — the squad-rebuild / Q11 positional re-model
(needs explicit user build-go; re-prices Stage 2) or screening AI (complex, regression-prone). That fork is with the
USER (the watchdog surfaced it). 1119 tests green, audit clean, run.py OFF+ON exit 0.

## Wave 149 (2026-06-03) — T'au Markerlights base army-rule buff (+1 BS + [SUSTAINED HITS 1] vs Guided) was UNMODELLED — wiring it CLOSES T'au's under-shoot: T'au −4.4 → −0.2 (in band), headline 4.23 → 4.15

The watchdog steered to "T'au markerlights via the new designation substrate," but the diagnosis REFINED it: markerlights
are NOT a single-target designation, and they were already PARTLY modelled — `Battle._run_markerlight_phase` populates
`Army.guided_enemy_uids` every round (each alive MARKERLIGHT carrier marks the highest-points enemy in 36"+LoS), but the
ONLY consumer in `Unit.attack` was the Mont'ka detachment's `lethal_hits_on_guided` (rounds 1-3). **The BASE army-rule
buff was genuinely UNMODELLED.** Verbatim (T'au cat, Markerlight ability): "...ranged weapons ... have their Ballistic
Skill characteristic improved by 1 and have the [SUSTAINED HITS 1] ability while targeting an enemy unit that is visible
to one or more friendly MARKERLIGHT units...". It applies in EVERY detachment, EVERY round, and STACKS WITH (does not
double-count) the Mont'ka [LETHAL HITS]. Built directly (small two-point injection in `attack()`): a
`_tau_markerlight_guided` flag (T'au, ranged, target in `guided_enemy_uids`) → `hit_mod_delta += 1` (the +1 BS, under the
10e ±1 cap) at the hit-modifier block + `effective_sustained_hits += 1` at the sustained accumulator. Updated the stale
`simulator.markerlights` citation (its quoted_text described an older "Marked/Guided LETHAL HITS" wording; replaced with
the v10.6.0 verbatim + the now-applied base effect). The sim marks one highest-points enemy per carrier — a conservative
UNDER-approximation of "any target visible to a Markerlight unit."

**N=40 A/B: T'au 49.9 → 54.1 (−4.4 → −0.2, gated 0.18 → 0.00 — IN BAND, essentially ON target 54.3), headline 4.23 →
4.15 (−0.08).** No faction regressed meaningfully. The BEST under-shooter close since Relentless Onslaught + the faction
fix — a genuinely-unmodelled faithful army rule, removing it from the residual. KEPT. 1119 tests green, audit clean,
run.py exit 0. (N=40 T'au was already near-band on its high noise floor 4.23; at the N=80 baseline T'au was −8.5/4.30, so
expect a larger visible close there.) NEXT: confirm at N=80 + continue — CSM holistic (#52), or the over-shooter cluster
diagnosis (WE +14.7).

## Wave 148 (2026-06-03) — AdMech Machine Vengeance (Cawl per-target designation, mirroring Oath of Moment) — the watchdog's top AdMech lever LANDS modestly: AdMech −10.8 → −9.8, headline 4.27 → 4.23. Validates "army-wide mechanics > leader auras"

Built **Belisarius Cawl's Invocation of Machine Vengeance** as a per-target-designation mechanic (commit `0407e09`,
Opus worktree agent `223c0d8` cherry-picked) — the watchdog's refined-thesis top pick after the AdMech leader
auras came up neutral ("army rules move the needle, leader auras mostly don't"). Cawl's offensive Canticle is
army-wide re-roll Hit vs ONE designated enemy unit; the sim previously left it un-wired because it had "no
per-target designation system" (the prior `cp_discount_hq.json` ADMECH-DIAG-5 note). It is STRUCTURALLY IDENTICAL
to Adeptus Astartes Oath of Moment, so the build MIRRORS the Oath substrate piece-for-piece: a new
`machine_vengeance_target_uid` on Army; `_pick_machine_vengeance_target` (gated on a live Belisarius Cawl, reusing
Oath's value scorer); a parallel Command-phase designation block in `_run_round`; and a parallel re-roll gate in
`attack()` (AdMech attacker + target is the designated unit → `att_reroll_all_hits`). FAITHFUL APPROXIMATION
(noted + cited): Cawl picks one of three Canticles per Command phase; we model him always choosing the offensive
Machine Vengeance (the common competitive pick). No over-application — the re-roll fires only vs the one designated
unit, only while Cawl is alive, only for AdMech attackers.

**N=40 A/B: AdMech −10.8 → −9.8 (gated 6.66 → 5.64), headline 4.27 → 4.23.** Machine Vengeance added ~+0.8 AdMech on
top of the neutral leader auras — the FIRST AdMech lever to move the needle, **validating the refined thesis
(army-wide designation mechanics > single-unit leader auras)**. KEPT (faithful + metric-positive). Two bonuses: (1)
it closes the exact gap the project flagged as un-wireable, and (2) the per-target-designation substrate is now
REUSABLE for T'au markerlights/Guided, Necrons Worthy Foes, Lord Discordant Spirit Thief. AdMech is still −9.8
under, so the BULK of its gap is structural (output/durability vs field, or representation), not abilities — but
the abilities are now faithfully modelled. Audit clean, 1119 tests green (+ 3 new Machine Vengeance tests), run.py
exit 0. NEXT: the reusable designation substrate (T'au markerlights — T'au is −4.4 under) OR the over-shooter
cluster diagnosis (World Eaters +14.4).

## Wave 147 (2026-06-03) — AdMech leader auras (faithful, BSData-verified) land METRIC-NEUTRAL; the −12 AdMech under-shoot is NOT the leader auras. Fresh N=80 baseline dumped: gated 4.09

Two parts this wave.

**(1) Fresh N=80 baseline dumped to disk** (`data/wf_wave147_baseline_n80.txt`, watchdog's request — the on-disk
tables were stale from wave 122). Post measurement-fix + faction-fix + Relentless Onslaught: **gated MAE 4.09 at
N=80** (the N=40 4.27 was noisier). The honest landscape: IK +30.3/27.32 (representation floor) · World Eaters
+13.3/9.87 · **AdMech −12.2/8.07** · CSM −9.1/6.63 · Drukhari +9.2/5.86 · Votann +9.0/5.97 · T'au −8.5/4.30 ·
Sororitas +8.0/4.24 · Tyranids +8.0/4.23 · Necrons −6.8/3.54 · Daemons −5.1/1.89 (now ~in band). AdMech is the
biggest actionable under-shooter after the IK floor.

**(2) AdMech leader auras built (commit `3caecdd`, Opus worktree agent `092c0b2` cherry-picked).** VERIFIED each
ability verbatim at the BSData AdMech cat — which CORRECTED the watchdog's specs: the Manipulus is "Galvanic Field"
(led unit's weapons gain [LETHAL HITS]), NOT "+6 range"; the Skitarii Marshal "Control Edict" is FULL re-roll Hit,
not just 1s; Cawl's offensive Canticle (Machine Vengeance) is army-wide re-roll Hit vs ONE designated enemy
(target-restricted). ALSO found the AdMech +1-to-hit army rule (Doctrina Imperatives) is ALREADY modelled. Built
the two cleanly-faithful auras: **Manipulus Galvanic Field** ([LETHAL HITS] via a new `lethal_hits_ranged`
LeaderAbility field, host-keyed to `kataphron_destroyers`) and a re-point of the NEUTERED **Dominus FNP 5+**
(host-keyed from no-op electro-priests to `kataphron_breachers`). Both hosts are SINGLE-OCCURRENCE in the Skitarii
Hunter Cohort archetype, so the proximity broadcast reaches exactly one unit each — faithfully modelling the
one-attachment rule WITHOUT over-applying (the trap that neutered the Dominus). Deferred the Marshal (2× Rangers →
over-application) and Cawl (target-restricted) with that reasoning recorded.

**N=40 A/B: AdMech −10.8 → −10.6 (gated 6.66 → 6.39), headline 4.27 → 4.26 — METRIC-NEUTRAL.** Same lesson as Dark
Pacts in milder form: the watchdog's hypothesis was PARTIALLY right (the auras WERE genuinely missing — now added,
faithful, cited) but two single-unit buffs are far too small to close a −12 gap on a 16-unit army. The AdMech
under-shoot is mostly ELSEWHERE (overall output/durability vs the field, or representation). KEPT as fidelity per
the prime directive (real cited abilities, single-attachment, no over-application — correct regardless of the
neutral metric). Audit clean, 1116 tests green, run.py exit 0. NEXT: re-target the remaining dive on the N=80
table — World Eaters over-shoot (+13.3, diagnose-first), T'au under (−8.5), or the deeper AdMech/CSM diagnosis.

## Wave 145b (2026-06-03) — P0 DATA BUG FIXED: CSM/Daemons faction misassignment (the queue's highest-leverage item). Headline gated 4.55 → 4.27. Chaos Daemons −14.8 → −4.1 (the residual was a data-contamination artifact, NOT a sim gap)

The watchdog's P0 data bug, root-caused and fixed. **Root cause** (a clean faction-keyword name mismatch, not a
structural quirk): the generic Heretic Astartes datasheets (Legionaries, Chosen, Havocs, Chaos Lord, Possessed,
Raptors, Chaos Terminators, Dark Apostle, Master of Possession, Sorcerer, Cultists, Traitor Guard, etc.) are
defined once in a shared library and imported by BOTH `Chaos - Chaos Space Marines.cat` AND `Chaos - Chaos
Daemons.cat` (Daemons take them as allies). Their BSData "Faction:" keyword is "Heretic Astartes", but
`faction_of()` of the real CSM codex returns "Chaos Space Marines" — so `iter_unit_entries`'s importer-matching
step (which credits the importer whose faction matches the entry's keyword) found no match and fell through to
"first non-library importer", which was the Daemons catalogue. Result: 31 CSM datasheets filed under faction
"Chaos Daemons" — CSM could not field its own battleline (its catalogue had NO BATTLELINE at all), so its archetype
ran a fake cult-marine soup, and the same marines polluted the Daemons `_random_fill` pool.

**Fix** (3 lines + a regen + an archetype rebuild): added `FACTION_KEYWORD_ALIASES = {"Heretic Astartes": "Chaos
Space Marines"}` + `canonical_faction_keyword()` in `code/factions.py`, used in `iter_unit_entries`'s choice-1
(`code/bsdata/parser.py`) so the keyword maps to our faction name before the importer match. None of the affected
entries have a mono-god (Death Guard/Thousand Sons/World Eaters/Emperor's Children) co-importer — those carry their
own uniquely-named datasheets — so the alias cannot mis-steal. Regenerated `parsed.json`: EXACTLY 31 units re-keyed
`chaos_daemons_*` → `chaos_space_marines_*`, **0 other content changes** (verified by full diff). Re-keyed 2 matching
overrides (Chaos Lord / Sorcerer in Terminator Armour — their notes already cited the chaos-space-marines Wahapedia
page) and 31 keys across the 3 provisional Stage-2 data files (a pure re-key; a unit's price doesn't change because
its faction key was corrected). Rebuilt the CSM "Pactbound Zealots" archetype around the real Legionaries backbone
(×3) + Abaddon + Chaos Lord + Dark Apostle + Chosen + Terminators + Obliterators + daemon-engines, dropping the
cult-marine soup (Berzerkers/Plague/Rubric/Noise belong to the standalone mono-god codices in 10e).

**N=40 A/B (both P0 fixes in, vs measurement-only 4.55): headline gated 4.55 → 4.27 (−0.28).** Chaos Daemons
−14.8 → −4.1 (gated 11.68 → 0.95 — nearly in-band; the contamination was most of the "residual"). CSM −9.0 → −12.0
(gated 6.57 → 9.51, WORSE but FAITHFUL — the real Legionaries list under-shoots where the killier cult soup did
not; the residual is now a clean target for the unmodelled Dark Pacts army rule, queue #48). The Daemons win
dominates. Kept per the prime directive — a real army beats a fake soup regardless of the metric direction. Full
suite green (1117 pass; fail-loud rule 13 correctly caught the override + Stage-2 key references mid-build, all
fixed), audit clean, run.py --cli exit 0, app presets resolve, Daemons pool confirmed clean (0 marines). No 10e
rule implemented (data-attribution fix) → no new citation. NEXT: the abilities dive on the now-honest under-shoots
— #48 CSM Dark Pacts (directly targets the −12 this exposed) and #47 AdMech leader auras (−10.8/6.66).

## Wave 145 (2026-06-03) — P0 MEASUREMENT FIDELITY (watchdog wide-investigation re-prioritised queue): two faithful "make-the-comparison-correct" fixes to the eval; the sim is byte-identical so this RE-BASES the metric, not a regression. Gated MAE 4.14 → 4.55

The watchdog's 5-agent wide pass found the residual table was partly a MEASUREMENT artifact (upstream of
every mechanic). Two fixes, both faithful (correct the comparison to reality — the opposite of metric-tuning):

1. **Live tournament target.** `TOURNAMENT_TARGET` was a hand-transcribed dict that had drifted from the live
   Warp Friends scrape — Chaos Space Marines hardcoded 52.8 but **55.6 live** (so CSM was measured as
   less-under than reality), Emperor's Children 47.9 vs 53.3, Aeldari 44.4 vs 41.6, Custodes 52.1 vs 49.5,
   Chaos Knights 47.5 vs 44.7 (11/22 off by ≥1pt). Now read LIVE from `data/warpfriends_rolling.json`
   (`_load_tournament_target`), the same source as the noise floor + game counts — one self-consistent scrape.
   Fails loud per CLAUDE.md §13.

2. **Field-weighted matchup average.** `run_matrix` averaged each faction's 21 opponents UNIFORMLY, but the
   real field is heavily skewed (Adeptus Astartes 6599 games ≈ 21%, Adeptus Mechanicus 545 ≈ 1.7%, a 12.1×
   gap) and the Warp Friends per-faction win rate is itself measured against that skewed field. A uniform mean
   over-weights rare opponents and under-weights the dominant Marine population — a systematic ±1-2pt bias that
   penalised melee armies that beat Marines. Now weighted by each opponent's `TOURNAMENT_GAMES` share.

**RE-BASED N=40 baseline: gated MAE 4.14 → 4.55** (raw 7.89, 6/22 in band). The OLD measurement was flattering
the sim; 4.55 is the honest signal the loop's stopping criterion now reads. The corrected table SHARPENS the
targets — IK +30.5/gated 27.58 (representation floor, unchanged); Chaos Daemons −14.8/11.68 (worst actionable
under-shoot); World Eaters +13.1/9.65; AdMech −11.3/7.12; Necrons −10.2/6.97; CSM −9.0/6.57 (deeper than the
old target showed). Crucially, the #1 and #5 actionable under-shoots (Daemons, CSM) are exactly what the next
item — the **faction-misassignment data bug (#51)** — fixes: 10 CSM datasheets (Legionaries, Chosen, Havocs,
Chaos Terminators, Chaos Lord, Sorcerer, Dark Apostle, Possessed, Raptors, Warp Talons) are filed
`faction=Chaos Daemons` because BSData's `Chaos - Chaos Daemons.cat.gz` catalogue contains them and
`faction_of()` keys faction on the cat filename. Confirmed: the CSM catalogue (81 units) has NO battleline at
all — CSM cannot field its own backbone, so its archetype runs a fake cult-marine soup, and these marines also
pollute the Daemons random-fill pool. Audit clean, run.py --cli exit 0, phase5 5/5 green. No sim/rule-bearing
change → no new citation needed. NEXT: #51 faction bug (highest leverage), then abilities dive on whatever's
still under.

## Wave 144 (2026-06-03) — UNMODELLED-ABILITIES DIVE #1 (watchdog/user new direction): Necrons Cursed Legion RELENTLESS ONSLAUGHT — the first METRIC-REDUCING faithful lever since the floor. Necrons −11.2 → −7.4, headline 4.34 → 4.14. The under-shooter residual IS unmodelled faithful abilities, NOT the representation floor

NEW DIRECTION (watchdog 4-agent audit, user-directed): the UNDER-shooters under-deal damage because LEADER AURAS
/ ARMY+DETACHMENT RULES / datasheet abilities are UNMODELLED — faithful fixes (real cited rules; not modelling
them is the error, the OPPOSITE of metric-tuning). This re-opens real headroom on the under-side, DISTINCT from
the over-shooter representation floor. Implemented #1 (highest impact). VERIFIED at BSData (Necrons.cat.gz, Cursed
Legion rule id 1dfc-5377-99ac-a700): "Each time a NECRONS model makes an attack that targets a unit within range
of one or more objective markers, add 1 to the Hit roll" + [ASSAULT] on NECRONS VEHICLE/MOUNTED (non-TITANIC).
Caught + corrected the watchdog's "rounds 2-5" misattribution (NO round restriction — it's a detachment rule, not
army). Built via Opus worktree agent (cherry-picked `dd79371`): +1-to-hit gate in `Unit.attack` (Necrons +
`target.on_objective` + Cursed-Legion detachment, clamped at the 10e ±1 cap), the [ASSAULT]-after-Advance clause
in `_do_shoot`, Cursed Legion promoted to the DEFAULT Necrons detachment, cited `simulator.relentless_onslaught`
(BSData verbatim), 14 tests + full suite green (1118).

**N=40 A/B (always-on default change): Necrons gated −11.2 → −7.4 (+3.8, ~⅓ of the under-shoot), headline gated
4.34 → 4.14 (−0.20), win 42.6%.** The FIRST metric-reducing faithful lever since the representation floor — the
watchdog's abilities-dive thesis is VALIDATED: the under-side residual is unmodelled faithful abilities. KEPT
(faithful real rule, lands regardless of magnitude; combined N=80 re-test at the end of the queue per the
sequence). NEXT: #2 AdMech leader auras (Cawl/Manipulus/Skitarii Marshal — 3 leaders at zero offense), #3 CSM Dark
Pacts fix, #4 Daemons datasheet abilities — each BSData-verified, cited, A/B'd. Then re-test combined + M4
(re-opened) N=80. LOOP_QA wave-144.

## Wave 140 (2026-06-03) — MULTI-METRIC candidate TESTED + REFUTED: the M2 deck OVERSHOOTS the secondary-VP fidelity (52-80 → 8-22, past the real ~30-40). Secondary fidelity is REPRESENTATION-gated (card-achievement = the same floor)

Tested the wave-138 leading candidate (M2 deck as the secondary-over-generation fix) directly via the deck-on
multi-metric profile: **deck-OFF secVP ~52-80 (over) → deck-ON secVP ~8-22 (UNDER)**. The deck OVERSHOOTS past
the realistic ~30-40 into under-generation, because the 2-card Tactical hand STALLS (the AI can't ACHIEVE its
held action/position cards — the wave-120 finding; card-achievement needs dedicated units the one-Unit-per-model
representation can't deliver, the same gap that made the wave-121 pursuit ineffective). **So the secondary-VP
fidelity loops back to the SAME representation floor** as the primary over-hold — neither over-generation (no
deck) nor under-generation (deck stalls) is realistic, and the in-between requires card-achievement the
representation bounds. The strongest multi-metric candidate is REFUTED; the residual is, end-to-end (primary
over-hold AND secondary VP), the one-Unit-per-model representation. (Win-rate swings in the small diagnostic are
noise; the secVP drop is robust + the deck is win-rate-neutral.) Pending the user's real per-faction secondary-VP
reference to confirm the ~30-40 target. LOOP_QA wave-140.

## Wave 138 (2026-06-03) — MULTI-METRIC instrumentation built (`scripts/diag_multimetric.py`) + first per-faction profile. Three fidelity signals; the SECONDARY OVER-GENERATION (raw 52-80 VP) is the strongest actionable — the M2 deck may be justified on the SECONDARY-FIDELITY metric even though it washed on win rate

First worker contribution to the user's MULTI-METRIC fidelity review (watchdog leads the analysis + real-data
sourcing). The diagnostic dumps the per-faction profile: win% / rounds / opp-tabled% / self-tabled% / survivor%
/ kills / final PRIMARY VP / final SECONDARY VP / per-round PRIMARY-VP accrual curve (RoundEnded subscriber).
Three signals (LOOP_QA wave-138 has the full table + numbers):
1. **SECONDARY VP OVER-GENERATED — raw 52-80/game** vs real competitive ~30-40 (cap 40). The sim has BOTH sides
   blow past the 40-cap → secondary is a non-differentiator (the known wash). **The M2 deck (gated OFF,
   win-rate-neutral) brings raw secondary toward realistic levels → the multi-metric view may JUSTIFY the M2 deck
   on the SECONDARY-FIDELITY metric.** Strongest actionable fix — pending the real secondary-VP reference.
2. **Tabling ~0%, rounds always 5.0** — confirms low-lethality / never-tabled from the dynamics angle.
3. **Primary-by-round accrual = the over/under-hold axis** — durable elites accrue fastest (IK 0/12/23/34/45),
   mobile/fragile slowest (Daemons 0/6/14/22/32). The representation floor, from the DYNAMICS not just win rate.

Reported to the watchdog for analysis. Next: the watchdog sources real per-metric data + directs which divergence
to fix; meanwhile the worker clears queued hygiene (#37 detachment fabs / #38 anti-tank). Diag is throwaway
(untracked). LOOP_QA wave-138.

## Wave 137 (2026-06-03) — TABLING PLAY-OUT fix (#41, watchdog-prioritized + multi-metric-fidelity): a one-sided wipe no longer truncates the battle — it plays out all 5 rounds (survivor scores uncontested primary). Faithful, METRIC-NEUTRAL (4.34→4.34, tablings rare)

`Battle.run()` ended early on EITHER side reaching zero (`a_total_left == 0 or b_total_left == 0: break`).
Real 10e lasts five battle rounds — a one-sided tabling does NOT end the game; the survivor keeps playing the
remaining rounds and scoring primary on the uncontested board (combat/AI already no-op vs an empty opponent; the
50-VP cap bounds it). Changed the break to `and` (MUTUAL wipe only). Always-on (faithful core rule, not gated);
cited `simulator.battle_length_five_rounds`; full suite green (1103); **N=40 4.34 → 4.34 (metric-NEUTRAL**, as
the watchdog predicted — tablings are rare in these games). First fix of the MULTI-METRIC fidelity phase: it
corrects the rounds/VP series the review compares + removes an edge case (a tabler behind on VP at the tabling
moment was mis-scored). LOOP_QA wave-137.

## Wave 136 (2026-06-03) — WHOLLY-WITHIN squad-granularity fix for Engage/BEL (user catch) — completes the authentic secondary; faithful + FAVOURS the compact Knight (reinforces position cards aren't the Knight-penalty)

User catch (watchdog 2590): real Engage/BEL score for units WHOLLY WITHIN a quarter (>6" from centre) / the
enemy DZ; the sim's `score_position_delta` used an "any model inside" check → the one-Unit-per-model
representation OVER-credited (a spread squad registered in several quarters via different models, never paying the
straddle penalty). Fixed `score_position_delta` (gated `SWEG_SECONDARY`): group by `squad_id`, count a quarter
only when ALL a squad's models are wholly within ONE quarter AND >6" from centre (straddling squad → no quarter);
BEL counts a unit only when ALL its models are wholly within the enemy DZ. Even-handed, emergent; cited
`simulator.secondary_wholly_within`; 57 tests green; OFF byte-identical. **N=40: deck+secondary 4.04 → 3.97**
(within noise) with **IK +26.8 UNCHANGED** — confirms it FAVOURS the compact Knight (a 1-model Knight is
trivially wholly-within), so it does NOT penalise the Knight; the rules-clean low-unit penalty stays the Action
cards. The authentic secondary economy is now COMPLETE + faithful, gated default-OFF.

**NEXT PHASE (user directive, watchdog 2609): the MULTI-METRIC FIDELITY REVIEW.** Shift calibration from
win-rate-only to the underlying dynamics — instrument turn-by-turn PRIMARY/SECONDARY VP, kill counts, survivors,
rounds, tabling, points; compare to real data; analyze + explain divergence; build fixes (usual loop). The
WATCHDOG LEADS (instrument + compare + analyze); the worker builds the fixes. CRUX = real-data sourcing
(win rates from Warp Friends; VP-splits / turn-by-turn / kills need sourcing — Woehammer / Goonhammer / Stat
Check, via the user). Memory `project-multi-metric-fidelity-review`. The anti-Knight package conclusion stands
(representation floor). LOOP_QA wave-136.

## Wave 135 N=80 VERDICT (2026-06-03) — the AUTHENTIC secondary does NOT fix the Knight (IK +26.6 unchanged); the two halves FIGHT not stack (combined 4.41 > either alone). The ENTIRE anti-Knight package is EXHAUSTED faithfully — the Knight over-rate is a REPRESENTATION FLOOR

**N=80 (decisive):**
- **deck + authentic secondary 3.55**, IK **+26.6** (UNCHANGED), Daemons −13.6, band 8/22. The authentic
  secondary does NOT fix the Knight — hypothesis REFUTED at the decisive N (the Knight achieves most secondaries
  via kill cards / occupancy; the action-card penalty is negligible). (3.55 vs the 3.83 plain baseline MIGHT be a
  small faithful headline gain, but the M2 deck was ~neutral at N=80 before → within noise, NOT an anti-Knight
  fix, needs a clean A/B to claim.)
- **combined (M4+Tarpit+FOCUS + deck + secondary) 4.41**, IK +19.6 — WORSE than either half alone (deck+secondary
  3.55, M4-stack 4.16). The two levers FIGHT: M4's frozen-under regression dominates AND its positioning bias
  competes with the secondary's for the same spare units.

**CONVERGENCE — the entire anti-Knight package (waves 123-135) is EXHAUSTED faithfully.** Built to the rules,
NEITHER board control (M4, washes/regresses, frozen-under, inseparable) NOR the secondary economy (neutral on IK)
fixes the Knight's aggregate over-rate; the combined is worse than either. The Knight over-rate (IK ~+26 N=80) is
a one-Unit-per-model REPRESENTATION FLOOR, not a faithfully-fixable aggregate lever. Per the §7 criteria + the
watchdog's wave-131 sequence ("if the COMBINED ALSO washes → hypothesis tested + exhausted, report the floor +
stop"): **report the floor + STOP the anti-Knight package; no knob, no re-fit, no reach-back for the gate.** All
components (SWEG_M4 / SWEG_TARPIT / SWEG_FOCUS / SWEG_TAC_DECK / SWEG_SECONDARY) stay gated default-OFF. The
authentic secondary is faithful + kept gated (a possible small default-on pending a clean N=80 A/B, SEPARATE from
the anti-Knight goal). Proposing to the watchdog: (b) accept the neutral signal as exhaustion (do NOT build the 3
remaining action cards — the watchdog predicted, and the data confirms, ~negligible). The loop continues on the
queued post-package hygiene (#41 tabling play-out). LOOP_QA wave-135.

## Wave 135 (2026-06-03) — SECONDARY economy REBUILT AUTHENTICALLY (user+watchdog correction: the dedication scoring-gate was a fabricated knob) — revert the gate, positioning-bias only, rules-clean ACTION COST. A/B confirms the watchdog's prediction: the authentic Knight secondary weakness is NEGLIGIBLE (NEUTRAL)

User + watchdog caught that gating POSITION/board card scoring on `dedicated_card` FABRICATES a requirement not
in 10e (Engage/BEL score on presence, no action) = a knob. Rebuilt authentically via an Opus worktree agent
(cherry-picked `73e30fb`): (1) REVERTED the position-card scoring gate (Engage/BEL auto-score on occupancy, any
qualifying unit); (2) the spare-unit logic is now an AI POSITIONING bias only (the planner spreads spare units
into quarters/DZ — a Knight with no spare doesn't spread → emergently fewer quarters → less Engage, NO gate);
(3) built the rules-clean ACTION COST for Cleanse/Sabotage — a unit must have OC>0, be out of Engagement Range,
forgo shoot+charge (`action_this_round` blocks both), and SURVIVE to score (`_unit_can_perform_action` +
`_action_completes`); a Knight can't spare a unit → scores those 0, emergent, NO faction/model-count branch.
Cited `simulator.secondary_action_cost`; 1104 tests green; OFF byte-identical.

**N=40 A/B — the authentic secondary is NEUTRAL (confirms the watchdog's point-4 prediction):**
- deck-only 4.07 → deck+authentic-secondary **4.04** (within noise); **IK +26.3 → +26.7 (NO meaningful drop)** —
  the Knight achieves most secondaries via kill cards / occupancy; the action-card penalty is small.
- combined (M4-stack + deck + authentic secondary) **4.13** — WORSE than the M4-stack alone (4.03); even the
  positioning bias DIVERTS spare units off M4's markers (IK +13.3 → +22.1). So the secondary half does NOT push
  the combined positive.

**VERDICT (emerging, N=40):** built faithfully, the secondary economy is a SMALL lever that does NOT make the
Knight under-score, and it slightly FIGHTS M4 over spare units. The user's secondary-half hypothesis is under
heavy pressure — exactly the watchdog's prediction. Running the COMBINED at N=80 (decisive) to confirm. Layer 3
(timing) + the 3 new action cards (Establish Locus / Recover Assets / A Tempting Target) are UNBUILT — but the
strong neutral signal suggests completing them is unlikely to flip the verdict (proposing to the watchdog:
complete for a fuller test, or accept the neutral signal as the hypothesis-exhaustion). All gated default-OFF.
LOOP_QA wave-135.

## Wave 134 (2026-06-03) — SECONDARY economy Stage A BUILT (deliberate-dedication, gated `SWEG_SECONDARY`, via Opus worktree agent `7d962ad`) + A/B — the dedication mechanism was MIS-TARGETED at POSITION cards (net-negative, unfaithful); RE-SCOPE to the ACTION cards (Stage B)

Built Stage A (Layer-2 dedication CRUX) via an Opus worktree agent (cherry-picked `7d962ad`): a `dedicated_card`
field, an AI dedication planner committing SPARE units to held cards, and the even-handed spare-unit predicate
`_unit_is_dedicatable` (alive + not-acted + not-holding-objective + not-in-melee + not-a-productive-shooter; NO
faction/model-count branch — reviewed clean). 69 tests green, audit clean, OFF byte-identical. The agent scoped
the SCORING gate to the POSITION cards (Engage / Behind Enemy Lines) per the plan.

**N=40 A/B — the position-card scoping is the WRONG target + net-negative:**
- deck-only 4.07 → deck+dedication **4.20** (worse); IK +26.3 → **+29.5** (the Knight got RELATIVELY BETTER —
  the OPPOSITE of the hypothesis).
- combined (M4+Tarpit+FOCUS+deck+dedication) **4.62** — worse than the M4-stack (4.03), and it **LOST the M4 IK
  fix** (+13.3 → +25.0): the dedication planner DIVERTS the broad army's spare units OFF the markers M4 was
  massing them onto — M4 and dedication FIGHT over the same spare units.

**Root cause — MIS-TARGETING:** Engage / Behind Enemy Lines are POSITIONAL cards (score on quarter / enemy-DZ
OCCUPANCY) in real 10e, NOT actions — the few-units weakness is ALREADY captured by occupancy (a Knight occupies
fewer quarters). Gating them on "dedication" (only dedicated units count) is an UNFAITHFUL under-count AND a
combat-cost diversion that hurt the broad armies more. **The dedication / action-cost mechanism belongs on the
ACTION cards** (Cleanse, Sabotage, Establish Locus, Recover Assets, A Tempting Target), which genuinely require a
unit to commit. The substrate (`dedicated_card` + planner + spare predicate) is CORRECT and reusable; only the
position-card scoring gate was the wrong target.

**RE-SCOPE (Stage B):** keep position cards scoring on occupancy (faithful); apply the dedication/action-cost to
the ACTION cards (the unit forgoes shoot/charge, stays, SURVIVES; a Knight can't spare a unit → scores those
0); revert/repurpose the position-card scoring gate. All gated `SWEG_SECONDARY` default-OFF (no default impact).
LOOP_QA wave-134; surfacing the re-scope to the watchdog.

## Wave 133 (2026-06-03) — SECONDARY ECONOMY plan written (`docs/SECONDARY_ECONOMY_PLAN.md`) — the package's OTHER half, asymmetric on a DIFFERENT axis (low-MODEL armies can't churn the deck / spare units), which may break the primary-half inseparability

Plan-first the user's authorised secondary-authenticity build (the watchdog confirmed: do NOT stop, this is a
SEPARATE faithful build, not an M4 refinement). Read the current secondary architecture: `_score_one_card`
(simulator.py:1487) AUTO-AWARDS on condition — position cards (`score_position_delta`) score on INCIDENTAL
position (a Knight with a body in a quarter scores Engage free); the `pursue_target` substrate (wave 121) only
biased movement on top of auto-scoring, never gated scoring on dedication. The rebuild's 3 authenticity layers:
(1) action cards (Establish Locus / Recover Assets / A Tempting Target + Cleanse/Sabotage) cost a unit (forgo
shoot/charge, stay, SURVIVE); (2) **THE CRUX — scoring from DELIBERATE DEDICATION**: a `dedicated_card` field +
an AI dedication planner assigns ONE SPARE unit per held card, and the position/board/cleanse scorers gate on
`dedicated_card` (incidental presence no longer scores) — a 5-6-unit Knight has no spare bodies → scores those
cards 0; a broad army dedicates its surplus → scores (even-handed, emergent from unit count, no faction branch);
(3) per-turn timing (reuse the wave-116 `only_for` plumbing). **WHY it may break the inseparability** (the user's
hypothesis): the secondary axis ALSO punishes low-MODEL armies, so it pulls DOWN the OTHER low-model elites M4
inflated (Chaos Knights, Custodes) — potentially counteracting M4's inflation where M4-alone couldn't — while
rewarding high-model under-shooters; EMPIRICAL via the combined test. Build sequence: Stage A (dedication
substrate + Layer 2 CRUX, gated `SWEG_SECONDARY`) → B (action cards) → C (timing) → D (COMBINED M4-narrow +
secondary, ablated, N=40→N=80, per-faction secondary-VP). Reference `data/reference/wahapedia_ca2025-26.txt` has
the card text. LOOP_QA wave-133; surfacing the plan for the watchdog's scrutiny vs the 3 layers before building.

## Wave 132 (2026-06-03) — CORRECTED the gunline exemption to the watchdog's NARROW rails (move-costs-a-shot, pull hold-and-shoot). N=80 confirms the PRIMARY-half inseparability on the correct rails: IK fix KEPT (+17.0) but NO aggregate gain (4.26); Astra is FROZEN-UNDER not gunline-disruption. PIVOT to the SECONDARY economy (the package's other half) per the watchdog's sequence

The watchdog's wave-130 N=80 review (seen only after wave 131) gave NARROWER exemption rails than my wave-131
blanket version: exempt a model from the cluster-pull ONLY when moving onto the marker would COST a productive
shot (target in range now, out of range from the marker) — a HOLD-AND-SHOOT model (target in range from the
marker too) is STILL pulled. Rebuilt `_m4_move_costs_a_shot` to those rails; 11 M4 tests (hold-and-shoot,
move-costs-a-shot, no-target, cheap-trooper) + strategy suite green; OFF byte-identical.

**N=80 narrow exemption: gated 4.26** (baseline 3.83; unrefined 4.16; broad-w131 4.13). IK +17.0 (FIX KEPT —
hold-and-shoot models still mass vs the unkillable Knight), Daemons −4.0 (fixed), BUT Astra −17.3 (WORSE),
Drukhari +16.0 / World Eaters +10.1 / Chaos Knights −10.1 (all still inflated). Band 4/22.

**The three exemption versions triangulate the SAME conclusion — the IK fix and the frozen-under inflation are
INSEPARABLE:** broad exemption recovers the over-shooters but LOSES IK; narrow exemption KEEPS IK but recovers
NOTHING. And **Astra's regression is FROZEN-UNDER, not gunline-disruption** (broad recovered it only +1.2, narrow
made it worse) — M4-α's blunt board-control buff helps Astra's TOUGHER body-army opponents mass more than fragile
Astra does. The faithful primary half regresses +0.43 (the `project-ai-frozen-under-mae-first` law: faithful AI
makes the metric worse because the over-massing was compensating). **The board-control representation is
exhausted as a PRIMARY-VP lever** (now confirmed on the watchdog's own rails). Kept the narrow exemption (most
faithful, watchdog's rails) gated default-OFF.

**PIVOT per the watchdog's SEQUENCE:** the primary half is only HALF the anti-Knight work. **NEXT (wave 133+):
build the SECONDARY ECONOMY** — the user's authorised authenticity directive + the 3 layers (action-cost,
DELIBERATE-DEDICATION scoring, end-of-your-turn timing; task #44). The user's hypothesis: the secondary half is
what makes the few-units weakness BITE (a 5-6-unit Knight can't spare units to dedicate to held cards). THEN the
combined test (M4-narrow + full-secondary), ablated, N=40→N=80, per-faction secondary-VP. Plan-first the
secondary build (watchdog scrutinises vs the 3 authenticity layers). LOOP_QA wave-132.

## Wave 131 (2026-06-03) — M4-α gunline refinement (exempt productive shooters) RE-RUN N=80: it RECOVERED the over-shooters but KILLED the IK fix → the board-control fix and the frozen-under inflation are INSEPARABLE. The anti-Knight package WASHES at N=80 (representation floor). VERDICT: report the floor + the WIN-vs-wash decision to the user; keep all gated default-OFF; no further metric-chasing

Built the gunline-disruption refinement: `_m4_is_productive_shooter` exempts a model with meaningful ranged
output AND a target in weapon range from the cluster pull (a gunline holds objectives with cheap bodies, not its
heavy weapons). Even-handed, faithful, 9 M4 tests + strategy suite green, OFF byte-identical. Re-ran the full
stack at N=80.

**N=80 refined full stack: gated 4.13** (baseline 3.83 = +0.30 regression; unrefined 4.16 = negligible Δ). Per
faction: Imperial Knights +16.1 → **+24.9 (IK FIX LOST)**, Drukhari +16.2 → **+11.1 (recovered)**, Chaos Knights
−10.5 → −4.8 (recovered), Astra −16.3 → −15.1 (**+1.2 only** — so Astra was NOT mainly gunline-disruption, my
wave-130 hypothesis is FALSIFIED), Daemons −3.9 → −5.2, World Eaters +9.6 → +7.9. Band 4 → 6.

**THE FINDING — the IK-fix and the frozen-under inflation are INSEPARABLE.** M4-α's board-control massing is
exactly what out-holds the Knight (fixes IK); exempting "productive shooters" exempts the very opponent models
that were massing to contest the Knight, so over-shooter recovery and the IK fix TRADE OFF. A uniform faithful
board-control mechanic cannot fix IK without inflating other body armies (frozen-under); capturing only the good
half would be a knob. **This is the representation FLOOR the wave-93 plan anticipated.**

**VERDICT: the anti-Knight package WASHES at N=80 (+0.30 refined / +0.33 unrefined).** The board-control fix is
REAL + faithful (it genuinely halves the two biggest residuals — IK +25→+16, Daemons −9→−4 in the unrefined
stack) but inseparable from frozen-under inflation. Per the user's pre-agreed §7 criteria, WASHES → report the
floor + STOP, no knob, no re-fit, no further metric-chasing refinement (the "exempt-only-on-killable-target"
idea is a slippery 3rd iteration — flagged to the watchdog, NOT pursued autonomously). **All components stay
gated default-OFF.** Surfacing to the user the watchdog's nuance: the UNREFINED stack CAN halve the two biggest
residuals IF the user accepts the aggregate-regression cost (the over-shooter residuals — Drukhari/WE over-rated
for non-board-control reasons — become the next diagnosis); the worker's faithful default is floor-reported,
gated-OFF. LOOP_QA wave-131. Per-faction representation work is genuinely exhausted as an aggregate lever.

## Wave 130 (2026-06-03) — full-stack A/B + ablations (component 3 = existing `SWEG_FOCUS`). N=40 LANDED (4.34→4.03) but N=80 REVERSED it (3.83→4.16, +0.33 regression) — the N=40 move was NOISE. The package ROBUSTLY fixes the targets (IK −9, Daemons −5.4 at N=80) but regresses the aggregate, DOMINATED by the Astra gunline-disruption (fixable artifact, +6.25 gated)

Component 3 needed no build (`SWEG_FOCUS` = the wave-79 army focus-fire layer, confirmed present). Ran the
decisive full-stack (M4+Tarpit+FOCUS) + per-component ablations at N=40, then the N=80 confirmation.

**N=40 (noisy):** full stack 4.34 → **4.03** (−0.31 LAND). Ablations: FOCUS-alone 4.16 (claws back M4's
over-shooter inflation), M4+FOCUS 4.27, full stack 4.03 (Tarpit adds −0.24 ON TOP of M4+FOCUS). This CORRECTED
my wave-129 "Tarpit inert" read — Tarpit was measured only WITHOUT FOCUS; the components INTERACT.

**N=80 (decisive): baseline 3.83 → full stack 4.16 (+0.33 REGRESSION); band 7/22 → 4/22.** The N=40 −0.31 land
was NOISE (the M2/pursuit lesson again). BUT the per-faction picture is the real finding:
- **The two biggest residuals are ROBUSTLY fixed at N=80:** Imperial Knights +25.1 → +16.1 (−9.0), Chaos
  Daemons −9.3 → −3.9 (−5.4) — both beyond noise. The board-control representation fix is REAL and faithful.
- **The aggregate regresses from side-effects:** Astra Militarum −10.1 → −16.3 (gated +6.25 — the DOMINANT
  cause, ≈0.28 of the +0.33), Drukhari +10.8 → +16.2, World Eaters +5.4 → +9.6, Chaos Knights −0.8 → −10.5.
- **The Astra regression is a FIXABLE ARTIFACT, not frozen-under:** M4-α drags Astra's lascannon/heavy-weapon
  models (which carry OC) off their firing lines onto markers (the gunline-disruption flagged wave 128). The
  faithful refinement — exempt a model that is forgoing productive shooting — is wrong-way-test clean (a real
  gunline holds objectives with cheap bodies, not its heavy weapons) and could tip the aggregate positive.

**Pin-fires check (watchdog request):** the Tarpit pin DOES fire end-to-end (vs melee armies opponent survival
rises modestly with the gate on, e.g. Daemons 38%→41%), so its weakness on the IK win rate is board-control,
not a bug. Diag `scripts/diag_tarpit_fires.py` (throwaway, untracked).

**Disposition:** all components stay gated default-OFF (they regress the aggregate at N=80). NOT yet a clean
wash — the dominant regression cause (Astra) is a fixable faithfulness artifact. **NEXT (wave 131): the M4-α
gunline-disruption refinement (exempt productive shooters) + re-run the stack at N=80.** If it tips positive →
the package LANDS (keep + flag Stage-2 + queue the exposed Drukhari/WE over-shooter residuals as the next
diagnosis); if it still regresses → report the representation floor + the exposed residuals and STOP (no knob,
no re-fit). LOOP_QA wave-130.

## Wave 129 (2026-06-02) — built anti-Knight stack COMPONENT 2: general Tarpit-charge valuation (`SWEG_TARPIT`, default-OFF). A/B: INERT — Tarpit alone is a wash (4.34→4.43) and does NOT move IK (+24.8→+25.0); M4+Tarpit ≈ M4-alone (4.64≈4.65), claws back NONE of the over-shooter inflation. Re-confirms IK is positional, not combat

Built component 2: in `pick_charge_target`'s won't-crack branch (gated `SWEG_TARPIT`), an EXPENDABLE (chaff,
non-CHARACTER) attacker pinning a DURABLE high-ranged brick it can't crack is valued by the enemy ranged output
it DENIES (Big Guns Never Tire — the pin execution is already faithful in `_do_shoot`) instead of suppressed.
Even-handed (universal points + toughness, no faction branch); a low-ranged melee brick yields a small pin value
and is not tarpitted. AI heuristic on the cited pin rule (same class as the existing per-faction tarpit bonuses,
no new citation). `_is_tarpit_charge` + `_tarpit_enabled`; 8 tests; strategy suite + smoke green; OFF
byte-identical.

**N=40 A/B vs the 4.34 baseline:**
- **Tarpit ALONE:** gated **4.43** (+0.09, wash); **Imperial Knights +24.8 → +25.0 (UNCHANGED)**; Daemons
  −14.6 → −13.5 (slight). Tarpit denies the Knight's SHOOTING, but the convergence established these games are
  decided on PRIMARY board control, not combat — so the combat-denial lever can't move IK.
- **M4 + TARPIT:** gated **4.64 ≈ M4-alone 4.65** — Tarpit adds NOTHING on top of M4 and claws back NONE of the
  over-shooter inflation (Drukhari +18.3, World Eaters +11.4, Chaos Knights −14.8 still inflated).

So the **combat half of the package is INERT on the primary-decided IK game** (refutes the Tarpit/FOCUS
claw-back hypothesis; re-confirms the convergence). FOCUS (also combat-targeting) is likely similarly inert →
the package verdict hinges entirely on M4-α. Tarpit kept gated default-OFF (stack component). NEXT: component 3
(`SWEG_FOCUS` on) + the decisive full-stack A/B + ablations N=40→N=80, characterising the over-shooter
inflation (faithful exposed-residual vs M4 artifact) per the watchdog. LOOP_QA wave-129.

## Wave 128 (2026-06-02) — built anti-Knight stack COMPONENT 1: M4-α squad-cluster positioning (`SWEG_M4`, default-OFF). N=40 A/B: HALVES the target axis (IK +24.8→+13.3, Daemons −14.6→−8.8) but REGRESSES the aggregate (4.34→4.65) — the frozen-under spread; expected for M4-alone, value is the STACK

Built component 1 of the user-authorised package. In `pick_move_intent` (gated `SWEG_M4`): a model carrying
Objective Control that is near a marker (≤6") but not tight on it, and not locked in melee, genuinely MOVES to
a cover-rich slot inside the 3" scoring band (`_m4_cluster_intent` + `_m4_enabled`), so a squad masses its
surviving OC on the objective instead of stranding half in the 3"-6" ring (the wave-93 spread). Faithful A1
positioning (the models really move; per-model OC scoring unchanged), even-handed (a 1-model Knight targets the
centre and is unaffected). Cited `simulator.m4_squad_cluster`; 7 tests; strategy suite green (34); OFF path
gated byte-identical.

**N=40 A/B (OFF = current baseline with Insane Bravery on = gated 4.34; ON `SWEG_M4=1`):**
- **Imperial Knights +24.8 → +13.3** (gated, ≈HALVED; 74.8% → 63.3% toward 48.5% real — not overshot).
- **Chaos Daemons −14.6 → −8.8** (gated, ≈HALVED; 35.4% → 41.2% toward 50.8% real — not overshot).
- **Aggregate gated 4.34 → 4.65 (+0.31 REGRESSION); raw 7.50 → 8.03.**

So M4-α does exactly its job — it nearly halves the dominant IK/Daemons axis (and unlike the reverted
Candidate A, it actually MOVES that axis) — but the aggregate worsens because it inflated OTHER factions (the
frozen-under spread; full per-faction diagnostic to identify them queued). This is the expected "M4 alone
doesn't land the aggregate; the value is in the STACK" outcome. KEPT gated default-OFF (stack component).
NEXT: component 2 (Tarpit-charge `SWEG_TARPIT`), then the decisive full-stack A/B where M4's axis-fix may
combine with Tarpit + SWEG_FOCUS to net-land. LOOP_QA wave-128.

## Wave 127 (2026-06-02) — USER DECISION: (A) authorised the combined anti-Knight PACKAGE — hard-gate LIFTED. Wrote the component-1 (M4-α squad-cluster) build plan; build next wave

The user resolved the M4 fork in `M4_REPRESENTATION_PLAN.md` §7: **(A) — run the combined anti-Knight package**
(NOT M4-α in isolation). The hard-gate is lifted for this package. Build a STACK of three faithful, env-gated,
even-handed components, each plan-first + own A/B, then a decisive full-stack-vs-baseline run + ablations at
N=40 then N=80, with the per-matchup IK/Daemons on-marker + Knight-kill drill and over-shooter watch.
Pre-agreed: LANDS (IK +27 down + Daemons up, beyond noise, no over-shooter re-inflation) → keep + flag the
Stage-2 re-derivation (do NOT auto-run Stage 2) + report; WASHES → report the representation floor and STOP
(no knob, no re-fit, wave-93 instruction). Components: (1) **M4-α** `SWEG_M4` — on-objective squads genuinely
MOVE their living models to cluster in the 3" band (faithful A1 positioning, NOT the forbidden A2 counting);
(2) **Tarpit-charge** `SWEG_TARPIT` — un-suppress the won't-crack penalty for pin-charges that tie up a durable
Knight (value by enemy output denied, expendable units, model the Knight's Fall-Back); (3) **`SWEG_FOCUS`** —
the existing wave-79 anti-armour-redirect targeting, turned on in the stack. This wave: wrote the component-1
build plan (`docs/M4A_BUILD_PLAN.md`) — confirmed the spread mechanism (models that arrive at the 3" edge HOLD
and never tighten onto the marker, so half the near-marker OC sits in the 3"-6" band) and specced the genuine-
movement cluster hook in `_do_move`. Build next wave. Tasks #36 (M4-α), #39 (Tarpit), #40 (full-stack A/B).
LOOP_QA wave-127.

## Wave 126 (2026-06-02) — wired the universal Insane Bravery core stratagem (was catalogued-but-no-op) — faithful, even-handed, net-neutral (N=40 4.41 → 4.34); landed default-ON as fidelity

A real, bounded, faithful absent mechanic (queued task #6) to keep the loop substantively alive while M4 holds
for the user. `UNIVERSAL_INSANE_BRAVERY` was registered but a no-op ("no in-phase hook"). Wired it into
`Battle._run_battleshock_phase`: when a squad would FAIL its Battle-shock test (roll < target), the owning army
spends 1 Command Point to auto-pass it — **once per battle** (`self._insane_bravery_used`, NOT reset per round),
**CP-gated** (`command_points >= 1`), and **only when the squad is contesting an objective**
(`self._squad_on_objective` — the case a real player burns it, since Battle-shock would zero the unit's Objective
Control). Modelled by forcing the 2D6 roll up to the test target, so the existing fail / pass (incl. the Daemonic
Manifestation pass) branches resolve it as a pass. **Even-handed** (every army has it; the objective-gate makes
the benefit accrue to whoever holds markers, no faction branch). Gated `SWEG_INSANE` (default ON; =0 for the
isolation A/B). Cited `simulator.insane_bravery` (verbatim core-stratagem text). Effect string flipped from
`auto_pass_battleshock_no_op_pending_in_phase_hook` to `auto_pass_battleshock`; 5 new tests
(`tests/test_insane_bravery.py`) + one existing battle-shock test isolated (CP=0, the unit sat on the objective);
full suite green (1046 passed). **N=40 A/B: OFF (SWEG_INSANE=0) gated 4.41 == baseline (clean isolation), ON
gated 4.34 (−0.07, within noise; raw +0.04 flat).** Landed default-ON as a FIDELITY improvement (a real
universal core rule the sim should model), not on the metric — the −0.07 is within N=40 noise, not a claim. The
loop continues holding for the user's M4 decision. LOOP_QA wave-126.

## Wave 125 (2026-06-02) — worked the watchdog's "while-holding" hygiene list: stale primary-cap citation `_comment` fixed + the Drukhari anti-tank read DONE — REAL+systemic picker bias but a WEAK IK lever (re-confirms M4 from a 3rd angle)

Per the watchdog's wave-122/123 steer (HOLD for the user on M4, do faithful NON-M4 hygiene meanwhile), did two
of its three named items. (1) The `simulator.primary_vp_cap_15` citation entry was already corrected to
CA-2025-26 in the wave-116 audit; only the file-level `_comment` was stale ("Leviathan Tournament Companion") —
fixed to CA-2025-26 + the chapter-approved URL; audit clean. (3) The Drukhari anti-tank read (Sonnet diagnostic):
**the anti-tank picker bias is REAL + systemic but a WEAK IK lever.** The mapper scores every mutex weapon-option
pick against a fixed baseline Marine (`expected_damage_through_baseline`, mapper.py:249-267), so high-S/low-shot
anti-tank options lose to multi-shot anti-infantry ones (Carnifex picks Stranglethorn S7 over Venom S9; the
Ravager picked Disintegrators S6 until the wave-107 override pin) — and it IS in the default eval path. BUT the
wave-107 A/B moved IK only +27.3 → +26.6 (within noise) while Drukhari moved +4.6 → +9.0, so opponents' firepower
deficiency is NOT why the Knight over-rates — **the old "could lower IK" hope (Q18) is REFUTED by data; the IK
root is M4 (positional), re-confirmed independently.** The faithful fix (target-aware weapon selection at firing
time — keep both options as profiles, AI fires the right gun for the target; per-model Stage 5 territory, NOT the
reverted wave-107 mixed-target score) is queued (task #38), headline-weak — not built while M4 awaits the user.
THREE independent angles now (terrain w97, per-model w99, anti-tank w125) confirm the IK over-rate does not yield
to firepower/data levers → M4 is the root, the user's call. LOOP_QA wave-125.

## Wave 124 (2026-06-02) — detachment fab AUDIT (layer is CLEAN: 29/34 faithful, 2 minor fabs queued) + corrected the STALE watchdog queue (P0 Candidate B + P1 terrain were BOTH already resolved) — M4 confirmed the only headline lever, the loop is at the faithful floor

Per never-halt (M4 user-gated), worked the next-best faithful lever — the detachment fabrication sweep. A
read-only Sonnet audit of all 34 detachments found the layer essentially CLEAN: **29 faithful, 2 minor fabs, 3
design-uncertain.** The historical fabrications were already swept in the SC5 / fab-audit waves. The 2 residual
fabs (F1: PLAGUE_COMPANY/ANNIHILATION_LEGION share `AWAKENED_DYNASTY_STRATAGEMS` as a placeholder — Necron strats
wrongly attributed, cross-faction for Death Guard; F2: ANNIHILATION_LEGION `reroll_wound_ones` is all-mode vs the
ranged-only real rule) are minor + delicate (band-aid risk; real fixes need a BSData stratagem pull / a 3-file
schema change) → QUEUED (task #37), not rushed at the floor. Also discovered the **watchdog TASK QUEUE's top two
levers were STALE**: P0 Candidate B (`SWEG_MASS`) LANDED wave 95 (not in-flight), and P1 terrain-realism (the
"HIGHEST estimated impact") was DONE wave 97 and REFUTED (realistic terrain made IK WORSE) — both corrected in
the goal-doc. **So every faithful lever around the representation is confirmed exhausted (terrain refuted,
per-model neutral, mission neutral, massing landed, detachment layer clean); M4 is the only headroom lever and it
is user-gated.** The loop is at the legitimate floor — but NOT silently ending: LOOP_QA asks the watchdog to
re-prioritize for the next non-M4 lever (suggested: Strategic Reserves variety, a still-absent faithful mechanic)
or confirm the floor. LOOP_QA wave-124.

## Wave 123 (2026-06-02) — M4 representation PLAN written (`docs/M4_REPRESENTATION_PLAN.md`); the build is a USER FORK, not a routine wave: every faithful mission/scoring/movement lever is exhausted, so M4 is localised to ONE architectural axis

Wrote the M4 plan-first doc (hard-gated; no code). The reconnaissance reframed M4: **the faithful MOVEMENT
half already landed** — Candidate B (`SWEG_MASS`, the AI massing idle out-of-range bodies onto markers)
LANDED wave 95 default-ON, gated 4.15 → 3.81 (Daemons −22.7 → −16.4, IK +27 → +25.5) and is already in the
current N=80 3.69 baseline; Candidate A (geometry/clustering, `SWEG_CLUSTER`) was built+REVERTED (regressed
4.15 → 4.30, frozen-under + unfaithful). The OC contest is verified faithful (wave 84, credited == raw
per-model within 3"); the scoring timing is verified faithful (M3 per-Command-phase neutral; wave-116
correction: the eval ALREADY runs IGOUGO, so the convergence doc's "(iii) un-interleaving" lever was a
misnomer); and the whole mission/secondary economy (M1 cap, M2 deck, pursuit) is net-neutral. **So everything
faithful around the representation has been built — the residual is the one-Unit-per-model representation
itself.** The plan defines the deep change (M4-α: a multi-model squad holds/contests a marker as a COHERENT
board-control actor — combat stays per-model; only the holding footprint becomes coherent), its Stage-2
tie-in (board-control representation feeds pricing → forces a Stage-2 re-derivation), the strong frozen-under
prior (likely wash), and the honest alternative (M4-β: declare the representation FLOOR and stop chasing the
axis, the wave-93-authorised outcome). **The fork — (A) authorise the M4-α build vs (B) declare the floor —
goes to the user; do NOT begin coding M4 until they pick.** LOOP_QA wave-123. The loop does NOT halt: it
continues on the next faithful queued lever while the user decides M4.

## Wave 121-122 close (2026-06-02) — AI-pursuit layer BUILT (gated `SWEG_TAC_PURSUE`) + measured: INEFFECTIVE / net-neutral at N=80 — decoupled to default-OFF. The whole MISSION-SCORING layer is gated by the one-Unit-per-model REPRESENTATION (M4) — the single remaining root for BOTH the IK primary over-hold and the secondary stall

Branch `claude/sim-calibration-6`. Built the watchdog-prescribed AI-pursuit layer via a Sonnet agent (cherry-picked
`b98b460`): `_assign_card_pursuit` sends up to 2 SPARE chaff units toward a held card's goal (enemy DZ for Behind
Enemy Lines, a forward objective for Cleanse) via a `pursue_target` that `pick_move_intent` honours; even-handed
by capability (a Knight has no chaff → no pursuit, faithful); achievement still flows through the real scorers.
20 tests, suite green.

**The 3-way A/B (OFF / deck-only / deck+pursuit), N=40 then N=80, shows the pursuit is INEFFECTIVE and
net-neutral.** N=40 deck+pursuit 3.96 (−0.17 vs deck-only) looked promising but **washed at N=80 (deck-only 3.62
→ deck+pursuit 3.60, −0.02)**. And the achieve-rate instrumentation is decisive: pursuit did NOT raise Behind
Enemy Lines / Cleanse achievement (35%→34% / 27%→24%, UNCHANGED) — the redirected chaff cannot reach the lethal
enemy DZ or hold an uncontrolled forward objective. So the small N=40 move was noise + a COMBAT-COST artifact
(diverting chaff weakens the pursuing army — which hurt the under-shooters Daemons −1.7 / Astra −0.7 and pulled
over-shooters down). NOT a faithful recovery → **decoupled the pursuit to explicit opt-in (`SWEG_TAC_PURSUE`
default-OFF); the deck (M2) runs deck-only by default.**

**CONVERGENT CONCLUSION: the ENTIRE mission-scoring layer (M1 50-cap inert, M2 deck net-neutral, M3 timing
net-neutral, pursuit net-neutral) is gated by the one-Unit-per-model REPRESENTATION gap.** Fragile distributed
bodies cannot reach/hold objectives — so they under-hold PRIMARY (the IK +27 mirror) AND cannot achieve the
board-control OR even the action/position secondary cards. The representation (M4) is the SINGLE remaining root
for the whole residual. Per the watchdog it is an ARCHITECTURAL change (how Objective Control / board control is
represented), warranting **plan-first + a watchdog/user check** (its size + the Stage-2 tie-in), NEVER a
per-faction OC knob. M2 + pursuit kept gated default-OFF (faithful mechanics, net-neutral, defeated by the
representation). LOOP_QA wave-122. **M4 is the next big lever — surfacing for the user's go before the build.**

## Wave 120 close (2026-06-02) — M2 at N=80 + the hold-vs-achieve instrumentation (watchdog steer): the N=40 −0.28 was NOISE (N=80 −0.07, neutral); the AI-PURSUIT ARTIFACT is CONFIRMED and is the dominant blocker — the AI-pursuit layer is the next build

Branch `claude/sim-calibration-6`. Ran the watchdog's two follow-ups on M2.

**1. N=80 confirm: the N=40 −0.28 was optimistic noise.** N=80 OFF gated 3.69 → ON 3.62 (**−0.07, within noise**),
band 7/22 → 5/22 (WORSE). So M2 alone is essentially NEUTRAL on the headline and slightly worsens the band. The
gains (Custodes −3.9→+0.0, AdMech −11.4→−8.6, CSM −7.9→−5.7, Votann/Orks/Tyranids down toward band) are CANCELLED
by two artifacts: **Grey Knights −3.0→+8.8 (+11.8 overshoot)** and **Chaos Daemons −10.0→−15.2 (−5.2)**.

**2. Hold-vs-achieve instrumentation CONFIRMS the AI-pursuit artifact (watchdog Risk 1).** Under M2-ON: Daemons
and Astra land on the TACTICAL track and score only **~10 secondary** (a real Tactical army churns ~25-35). Their
2-card hands STALL — they hold board-control cards they rarely achieve (defend_stronghold 11%, extend_battle_lines
9%, area_denial 16%) and even action/position cards the AI COULD pursue stay low (cleanse 28%, behind_enemy_lines
37%). Grey Knights and Imperial Knights are on the FIXED track scoring a moderate ~17 (NOT inflated). **So the GK
overshoot is NOT GK over-scoring — it is GK's TACTICAL opponents UNDER-scoring (the stall), so the FIXED kill-elites
win the secondary comparison.** The combat-focused AI does not PURSUE its held Tactical cards (spread for Engage,
push into the enemy deployment zone for Behind Enemy Lines, commit bodies to Cleanse) → an AI ARTIFACT, not a
faithful drop.

**CONCLUSION: M2's mechanic is faithful but is defeated by the AI-pursuit artifact — net-neutral at N=80.** The
even-handed AI-PURSUIT LAYER (the AI plays toward its held Tactical card when its units CAN, exactly as a real
player does) is the next build: it should let the Tactical armies recover to a faithful ~25-35 secondary WHILE
keeping the over-shooter correction → M2(+pursuit) then net-improves. (The board-control cards — defend/extend/
area_denial — stall partly FAITHFULLY, downstream of the one-Unit-per-model representation gap, M4-adjacent.)
**M2 KEPT gated default-OFF** (do NOT flip — net-neutral + band-worse without the pursuit layer). IK still
isolated to the board-control representation (not the mission layer). LOOP_QA wave-120; the AI-pursuit layer is
the next build (even-handed, no faction awareness). Live baseline holds.

## Wave 119 close (2026-06-02) — M2 BUILT (real 2-card Tactical secondary deck, gated `SWEG_TAC_DECK`): the FIRST faithful lever to MOVE the headline (4.41 → 4.13). Kept gated; one fidelity gap (per-Fixed-card 20 cap) → next refinement

Branch `claude/sim-calibration-6`. Built M2 (Stage A+B) via a dispatched Opus agent (worktree, cherry-picked
`bbab0f2`), reviewed faithful: a per-card dispatcher (`_score_one_card`, singleton-`chosen`, fails loud on
unknown keys), the real Fixed-OR-Tactical track model (FIXED = 2 kill cards every round; TACTICAL = a 2-card
hand with draw→score→achieve→discard→redraw — at most 2 sources, not the union of ~9-11), an even-handed
unit-count Fixed/Tactical choice (`chaff>=2 and units>=8` → Tactical; else Fixed → the Knight lands on Fixed-kill
emergently), a deterministic CRC32-seeded deck (no global-RNG perturbation), gated `SWEG_TAC_DECK` (OFF
byte-identical), cited `simulator.tactical_secondary_deck`. 19 new tests; full suite green (1020); audit clean.

**Clean N=40 A/B: OFF gated 4.41 == baseline (zero drift); ON gated 4.13 (−0.28) — the FIRST faithful lever all
session to REDUCE the headline.** Band 6/22 → 7/22. It tightens the spread faithfully (Leagues of Votann
+6.2→+1.8, Adeptus Custodes −5.7→−1.0, Adeptus Mechanicus −9.9→−7.0, Chaos Space Marines −9.0→−6.6 toward band).
Two blemishes: **Grey Knights +11.2 OVERSHOOT (−5.9→+5.3)** and Chaos Daemons −4.7 (worse); and **Imperial
Knights did NOT drop (+26.5→+27.6)** — it is on the FIXED kill track, which the deck-churn restriction does not
touch. The Grey Knights overshoot (and the Knight) point to the one fidelity GAP the agent flagged: **the real
per-Fixed-card 20-VP/game cap is NOT implemented**, so a kill-elite army's Fixed cards over-score. That is a real
CA-2025-26 rule and the immediate next refinement (M2b). KEPT M2 gated default-OFF (faithful + net-positive, but
the Grey Knights overshoot + N=40 noise warrant the 20-cap + an N=80 confirm before flipping default-ON). Live
baseline holds at 4.41. LOOP_QA wave-119. Stage C (the ~6 missing action cards) left TODO (reference file is
untracked in the agent's worktree; orchestrator has it locally).

## Wave 118 close (2026-06-02) — M2 PLAN written (the real 2-card Tactical secondary deck — watchdog's leading lever). Plan-first; build next

Branch `claude/sim-calibration-6`. Per the user-approved plan-first sequence, wrote the M2 plan
(`docs/M2_TACTICAL_DECK_PLAN.md`) after mapping the secondary machinery. Diagnosis confirmed in code: the sim
over-generates ~9-11 secondary sources EVERY round (`pick_secondaries` returns 2 Fixed + 2 position Tactical +
Cleanse + Sabotage + all 5 Board Tier-A; `_score_secondaries` scores all of them), so both armies trivially
exceed the 40 cap → secondary never differentiates ("the wash"). Real CA-2025-26: each army uses 2 Fixed OR a
2-card Tactical hand (draw 2, achieve→discard→redraw per Command phase) — at most 2 scoring sources, not 11.
This hands the durable Knight back its real weakness: a low-model no-action-doer army cannot churn a 2-card
Tactical deck the way a broad army can. Plan: (A) the 2-card hand state machine (deterministic deck, draw/
achieve/redraw, score ONLY the hand); (B) the Fixed-vs-Tactical choice (even-handed, falls out of unit count —
Knight→Fixed kill, horde→Tactical); (C) add the ~6 missing real action cards (Establish Locus, Recover Assets,
A Tempting Target — the broad army's tools); (D) measure + keep-if-faithful regardless of direction. Env-gate
`SWEG_TAC_DECK`, OFF byte-identical. Hypothesis: the Knight's secondary drops relative to broad armies, narrowing
+27; if it washes, that's a real finding pointing to the one-Unit-per-model representation (M4-adjacent). LOOP_QA
wave-118; surfaced for watchdog review before building. Build (Stage A) is the next wave. No code change this wave.

## Wave 117 close (2026-06-02) — M1 (Primary 50-VP total cap, watchdog/user-approved): faithful real rule LANDED always-on, but metric-INERT. Confirms VP-margin levers don't move the win rate; M2 (secondary differentiation) is the real lever

Branch `claude/sim-calibration-6`. Built the watchdog's M1 (user-approved mission-pack audit): CA-2025-26 v1.5
caps the Primary Mission at 50 VP/game, but the simulator only enforced the per-round 15 cap, so an army could
run to 4×15 = 60 primary and over-score by up to 10. Added `min(primary, 50)` in `Battle._decide_winner`, kept
ON by default (`SWEG_PRIMARY_CAP_50=0` disables for the A/B), cited `simulator.primary_vp_cap_50`; also fixed the
stale `primary_vp_cap_15` citation (Leviathan → CA-2025-26 v1.5). Suite green (1001), audit clean.

**N=40 A/B: capOFF gated 4.41 == baseline; capON gated 4.41 — EXACTLY ZERO across all 22 factions
(Imperial Knights +26.5 → +26.5).** The 50 cap is metric-inert: primary tops out ~44 in practice, so it rarely
binds, and when it clamps a high game 60→50 the durable Knight still WINS it → no win rate flips. **Kept
always-on anyway (it's a real CA-2025-26 rule — the A/B was to measure, not to decide keep).**

**This + the wave-116 M3 net-neutral together prove VP-MARGIN levers (primary cap, scoring timing) do NOT move
the win rate** — the Knight wins the VP COMPARISON regardless of margins. The win-rate lever must make the
OPPONENT out-score the Knight more often → that is M2: the real 2-card Tactical secondary deck (the sim scores
~9 secondary sources/round so both armies trivially max 40 = the "wash"; the real deck gives a broad army a
secondary edge a Knight army cannot churn). M2 is the next build (plan-first). LOOP_QA wave-117. Live baseline
holds at 4.41.

## Wave 116 close (2026-06-02) — DOUBLE CORRECTION: the eval already runs IGOUGO (so (iii) was never foundational), and building the REAL per-Command-phase scoring is NET-NEUTRAL — refuting "scoring-timing is the Imperial Knights lever"

Branch `claude/sim-calibration-6`. Two corrections to the wave 109-115 diagnostic arc, both important:

**1. The eval ALREADY runs vanilla IGOUGO per-player turns, NOT the alternating model.** Verified empirically
(`Battle` default `rules=None` → `RulesConfig.vanilla_10e()` = all-False = `alternating_activations=False` →
`_run_round_vanilla_turns`; instrumented: 0 alternating calls, 5 vanilla-turn calls). My wave-109 reading was
wrong — I assumed the eval used the alternating model and framed (iii) as a "foundational un-interleaving the
user must authorise." It is NOT foundational: the IGOUGO machinery already exists; the only remaining (iii)
piece is per-Command-phase primary SCORING, a tractable env-gated change.

**2. Built the real per-Command-phase scoring — and it is NET-NEUTRAL; it does NOT fix Imperial Knights.**
Gated `SWEG_CMDSCORE` (default-OFF): score each player's Primary at its own Command phase (turn start) inside
`_run_round_vanilla_turns` via `_score_objectives(only_for=<army>)`, instead of once at end of round. Cited
`simulator.primary_vp_command_phase`; 4 tests; suite green (1001). **Clean N=40 A/B: OFF gated 4.41 == baseline
(zero drift); ON gated 4.41 (+0.00) — NET-NEUTRAL.** It REDISTRIBUTES (helps static holders Grey Knights −5.9 →
−0.2, Astra −6.4 → −3.6; brings over-shooters down Sororitas +6.6 → +2.7, Orks +7.6 → +4.1, Tyranids +7.4 →
+5.1; but HURTS mobile takers Chaos Daemons −14.6 → −20.8, same mobile-taker problem as wave-111) — gains and
losses cancel. **Crucially Imperial Knights +26.5 → +27.3 (UNCHANGED): the durable Knight tightens its primary
MARGIN but still WINS, so its win rate is robust to the timing.**

**CONCLUSION (refutes the arc's central hypothesis): the Imperial Knights over-shoot is NOT a scoring-timing
artifact.** The real 10e per-Command-phase scoring — the (iii) the whole arc pointed to — is net-neutral and
leaves IK untouched. The Knight over-holds at ANY scoring moment because it is genuinely durable + concentrated
(a one-Unit-per-model representation limit), not because of WHEN primary is scored. So **the user does NOT need
to authorise a foundational (iii) change** (it is already IGOUGO, and the timing fix does not help). `SWEG_CMDSCORE`
kept gated default-OFF (the faithful real timing, net-neutral, +1 band — a documented experiment). The
convergent residual is the durable-concentrated-holder representation gap, where the faithful sim levers
(timing, positional AI, combat) are now ALL exhausted/net-neutral — the genuine structural floor. LOOP_QA
wave-116. Live baseline holds at 4.41.

## Wave 114 close (2026-06-02) — the out-of-band factions CONVERGE: the WHOLE per-faction residual is ONE axis (primary board-control / mission fidelity → user-gated (iii)). No separable mechanic anywhere

Branch `claude/sim-calibration-6`. Per the watchdog steer #2 (diagnose the out-of-band factions for a separable
missing mechanic), instrumented Necrons and spot-checked Chaos Space Marines / World Eaters / Thousand Sons the
way wave 109 instrumented Imperial Knights (writeup `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`). No code change
(diagnostic).

They ALL show the same pattern: NEVER tabled (every game full 5 rounds, 28-60% survive — combat is not the
decider); secondary is ALWAYS a 40-cap wash (every army's raw secondary 54-77 > 40); PRIMARY VP is the entire
differential. **Necrons −13.9** (reanimation works — never tabled; out-held 1.67 vs 2.09 markers/round, out-OC'd
2.4 vs 3.6 — UNDER-holds). **CSM −9** (primary ≈even 36.1 vs 36.5). **World Eaters** (mobile melee LOSES primary
33.1 vs 36.3 vs strong armies). **Thousand Sons +9** (durable elite WINS primary 39.7 vs 31.8 — OVER-holds like
IK).

**CONCLUSION: the ENTIRE per-faction residual structure reduces to ONE axis — primary board-control / mission
fidelity. Durable elites over-hold (IK +27, Thousand Sons +9); mobile-melee + out-massed armies under-hold
(Daemons, World Eaters, Necrons, CSM). There is NO separable faction-specific missing mechanic** — every
residual is the same gap the wave 109-111 chain rooted in the alternating-activation single-snapshot scoring.
**(iii) un-interleaving (per-player Command-phase scoring) is the dominant remaining lever for the WHOLE board,
and the loop is genuinely blocked on the user's (iii) decision.** Secondary contributing factor (noted, not
pursued — delicate): every army maxes the 40 secondary cap, erasing the secondary differentiator; best
addressed alongside (iii). Live baseline holds at ~4.41. LOOP_QA wave-114. Per never-halt, the next wakes do
faithful one-sided hygiene while (iii) awaits the user.

## Wave 113 close (2026-06-02) — over-arming sweep (watchdog hygiene steer): one genuine under-arming found + fixed (Skorpius Disruptor restored). Faithful + slightly POSITIVE (the rare non-frozen-under direction)

Branch `claude/sim-calibration-6`. While (iii) un-interleaving awaits the user, did the watchdog's faithful
non-scoring hygiene: the over-arming sweep of the 27 `data/overrides.json` entries that blank a secondary
weapon (wave-107 finding). The prior MUTEX-SWEEP handled the genuine choices correctly (Wave Serpent turret is
one-of-four; Hive Tyrant / Ghostkeel pick one ranged gun; the Predator sponson is the separate anti-tank-picker
issue, not under-arming). **The ONE genuine under-arming: the Adeptus Mechanicus Skorpius Disintegrator** — its
own override note ADMITS the Disruptor missile launcher is a REAL FIXED-MOUNT weapon (not exclusive with the
main cannon) but it was knowingly DROPPED for a blanket "clean-cut" convention. RESTORED the Disruptor as the
secondary (real stats S9 AP-2 D3.5 A3 twin-linked) while keeping `extra_ranged_profiles` empty so the Belleros
(the genuine mutex with the Ferrumite cannon) stays suppressed and the two main cannons do not double-count.
The Skorpius now fires its real loadout (Ferrumite + Disruptor). Cited to the datasheet + BSData; non-gated data
fix.

**N=40 A/B (non-gated, vs 4.48 baseline): gated 4.48 → 4.41 (−0.07, slight improvement); Adeptus Mechanicus
−11.3 → −9.9 (+1.4 toward target); Imperial Knights +26.5 and Chaos Daemons −14.6 unchanged.** A clean faithful
data-correctness win that helps the under-shooting Adeptus Mechanicus the RIGHT direction (restoring a real
anti-vehicle weapon) WITHOUT helping the over-shooters — a rare non-frozen-under result, because it is a
one-sided fidelity correction (arms an under-shooter), not an even-handed mechanic. Kept (live baseline now
~4.41). Full suite green (997), audit clean. LOOP_QA wave-113. The (iii) un-interleaving remains the headline
lever, user-gated.

## Wave 112 close (2026-06-02) — Chaos Daemons −14.7 under-shoot DIAGNOSED (watchdog steer): it is the SAME primary board-control residual as the Imperial Knights +27, inverted — UNIFIES the two biggest residuals, strengthens the (iii) escalation

Branch `claude/sim-calibration-6`. Per the watchdog steer, instrumented the Chaos Daemons under-shoot the way
wave 109 instrumented the Imperial Knights over-shoot (Daemons vs 8 opponents, 200 games;
`scripts/diag_daemons_wave112.py`, writeup `docs/DAEMONS_UNDERSHOOT_DIAGNOSIS_2026-06-02.md`). No code change
(diagnostic).

FINDINGS: (1) **NOT a survival/arrival issue** — Daemons are tabled 0x in 200 games, keep 35-58% of their
units, all games go 5 rounds. The "shot off the board before arriving" hypothesis is REFUTED. (2) **The loss is
PRIMARY VP** — Daemons 27-36 vs opponents 30-41 (lose ~6-12, worst vs Imperial Knights −11.8 / Aeldari −12.4);
secondary is a 40-cap wash. (3) **Surviving bodies, but only 22% of alive Daemon units are within 3" of any
marker** — the army fights instead of holding; the on-marker Objective Control contest is ~even (2.7 vs 2.9);
46/71 models deep-strike (low Objective Control ~2) and `_pick_arrival_point` weights objectives LOW for melee
(`objective_w = 0.7` vs 1.6 shooty), so the AI deep-strikes them to CHARGE not hold.

**CONCLUSION: the Chaos Daemons −14.7 and the Imperial Knights +27 are the SAME single residual — the primary
board-control / mission-fidelity gap — at opposite ends.** No separable Daemon-specific missing RULE (Shadow of
Chaos combat half is modelled; the real rule has no Objective-Control buff; raising the melee deep-strike
objective-weight would be metric-tuning, not a fidelity bug, so NOT pursued). Did NOT touch Daemons stats (per
the sim-fidelity ruling). **This UNIFIES the project's two biggest residuals and strengthens the user-escalated
(iii) un-interleaving (per-player Command-phase scoring), which would address BOTH ends at once.** Memory
`project-daemons-manifestation-missing` updated; LOOP_QA wave-112. Live baseline holds at 4.48. Next (never-halt,
(iii) user-gated): faithful non-scoring hygiene unless the user authorises (iii).

## Wave 111 close (2026-06-02) — entering-round primary scoring (option ii, watchdog-approved, gated `SWEG_ENTERSCORE`): REFUTED as the lever, but the bias pattern REINFORCES the (iii) un-interleaving escalation

Branch `claude/sim-calibration-6`. Built the watchdog's approved option (ii): score Primary VP on the control
state ENTERING each of battle rounds 2-5 (before that round's combat) instead of the baseline's
end-of-round-after-combat snapshot — faithfully approximating 10e's per-Command-phase scoring (a unit holds an
objective from when it takes it until an enemy takes it). Env-gated `SWEG_ENTERSCORE` (default-OFF), even-handed
(round-loop order flip in `Battle.run`; same four scoring rounds + 15 VP/round cap), verbatim-cited
`simulator.primary_vp_entering_round`. 3 call-order tests; full suite green (997); audit clean.

**Clean N=40 A/B: OFF gated 4.48 == baseline (zero drift); ON gated 4.61 (+0.13, ~neutral) with BIG per-faction
swings that REFUTE it as the IK lever:** Imperial Knights +26.6 → +27.5 (it did NOT lower the Knight, it slightly
RAISED it); Chaos Daemons −14.7 → **−24.3 (−9.6, collapsed)**; but it HELPED static gunlines (Astra Militarum
−6.3 → −0.2, Adeptus Mechanicus −11.3 → −5.6, Necrons −13.9 → −11.4). **The pattern: entering-round scoring
favours STATIC HOLDERS (gunlines that hold entering the round) and punishes MOBILE TAKERS (melee armies that
take markers by charging in DURING the round — and especially their decisive round-5 charges, which
entering-round scoring drops, there being no round-6 to score them).** It trades the durable-holder
over-credit for a mobile-taker under-credit — not a clean faithfulness win.

**This is the informative result the watchdog's sequence wanted:** a SINGLE-snapshot timing fix in the
alternating-activation model is fundamentally biased (static vs mobile, round-5 drop) because it collapses 10e's
TWO per-player-Command-phase scorings into one. The clean fix — credit BOTH the static holder (its Command
phase) AND the mobile taker (its next Command phase) without the round-5 drop — REQUIRES **(iii) un-interleaving
to real per-player turns**, which is FOUNDATIONAL and USER-ESCALATED. So the (ii) experiment strengthens the
case for (iii). Kept `SWEG_ENTERSCORE` gated default-OFF (live baseline 4.48 holds); not flipped (refuted +
flawed). Reported to the watchdog (LOOP_QA wave-111) with the keep/revert flag and the (iii) reinforcement.

## Wave 109 close (2026-06-02) — VP-FIDELITY DIAGNOSTIC (user ruling: re-fit KILLED, the +27 is a sim-fidelity gap in how the game is WON). Pinned the mechanism (PRIMARY board-control compounding); surfaced a build-direction fork to the watchdog

Branch `claude/sim-calibration-6`. The user ruled the re-calibration / re-fit-stats path is KILLED — tournaments
use the SAME GW stats + points, so a per-faction win-rate gap CANNOT be the stats; the +27 is a SIMULATION
fidelity gap (the sim under-models how 40k is WON on the mission, over-models combat). Ran the diagnostic-first
probe (no code change): instrumented Imperial Knights vs 7 broad armies (`scripts/diag_ik_vp_wave109.py`; full
writeup `docs/IK_VP_FIDELITY_DIAGNOSIS_2026-06-02.md`).

FINDINGS: (1) **The Knight wins on VICTORY POINTS, not combat/tabling** — tables the opponent 0-2/25, never
tabled, all games go 5 rounds, the broad army keeps 25-37% of its units. (2) **The differential is PRIMARY VP
(IK ~44 vs opp ~30, +14); secondary is a 40-cap WASH** (both sides blow past the cap; secondary selection +
caps + live Cleanse/Sabotage already pulled the Knight down once — not a missing secondary). (3) **The Knight's
primary lead COMPOUNDS R2→R5 (+3.3 → +6.0, peaks the final round); the broad army's board control COLLAPSES
under attrition (8.4 → 5.9)** — the one-Unit-per-model "elite combat over-rated / model-count board control
under-rated" gap the user named.

CANDIDATE FIXES + STATUS: positional AI (broad army onto markers) — TRIED (`SWEG_MASS`) and WASHED; secondary —
already faithful, a capped wash; **command-phase primary-scoring timing** (real 10e scores each army's primary
at its own Command phase, crediting transient marker control; the sim scores ONCE/round at end-of-round, crediting
only the post-combat survivor = the durable Knight) — the cleanest NEW idea, but BLOCKED by the
alternating-activation round model (`_run_round_alternating` interleaves both armies → no per-player Command
phases). Surfaced a FORK to the watchdog (LOOP_QA wave-109): score primary on PEAK in-round control (lead rec) /
start-of-round control / authorise structural un-interleaving. This is the scoring surface (sharpest
metric-tuning surface), so plan-first + watchdog steer before building. **This supersedes the "re-calibration is
next" framing.** Live baseline holds at 4.48 (no code change).

## Wave 108 close (2026-06-02) — Go To Ground core stratagem (gated `SWEG_GTG`), watchdog queue P2.2: faithful but the 8th FROZEN-UNDER lever (metric-neutral; refuted the "helps under-shooters" hypothesis)

Branch `claude/sim-calibration-6`. Built the Go To Ground 10e universal core Battle Tactic stratagem
(env-gated `SWEG_GTG`, default-OFF): just after an enemy unit selects a friendly INFANTRY unit as a shooting
target, the defender may spend 1 Command Point to give that unit a **6+ invulnerable save + Benefit of Cover**
until end of phase. Reuses the proven `transient_invuln_4` machinery (new per-Unit `go_to_ground_active` flag,
6++ at the save branch in `Unit.attack`, +1 save via `in_cover` in `_do_shoot`, cleared per round). The
defender heuristic (`Battle._maybe_go_to_ground`) is EVEN-HANDED — INFANTRY keyword + squad model-count +
incoming-threat + Command-Point pool only, NO faction awareness; the Command-Point economy (~1/round) is the
throttle. Verbatim-cited from the captured primary core-rules reference (`simulator.go_to_ground`,
`data/rule_citations.d/core_go_to_ground.json`). Caught + fixed a one-Unit-per-model representation bug in the
build (an absolute per-model wounds floor would have blocked all infantry → switched to a squad model-count
gate). 6 new tests; full suite green (994 passed); audit clean; OFF smoke clean.

**Clean N=40 A/B: OFF gated 4.48 == the wave-107 baseline (zero drift confirmed); ON gated 4.56 (+0.08, within
noise) — METRIC-NEUTRAL.** The hypothesis that an even-handed defensive stratagem would help the fragile
under-shooters (Chaos Daemons get shot off the board crossing to markers) is **REFUTED**: Chaos Daemons got
WORSE (−14.7 → −16.2). The frozen-under law in a defensive form — an even-handed save buff helps whoever
fields fragile infantry UNDER FIRE best (shooty-infantry gunlines), not the specific under-shooters; Daemons,
a melee aggressor, benefit less than their gunline opponents. Per-faction scatter (Genestealer Cults +4.4,
Adeptus Mechanicus +2.9, Chaos Daemons −1.5) is mostly N=40 noise around a neutral headline. **8th faithful
simulator lever to land frozen-under** (terrain, per-model structure, per-weapon dice, focus-fire, deployment,
Fire Overwatch, the anti-tank loadout pin, and now Go To Ground). Kept gated default-OFF (live baseline holds
at 4.48); not flipped (no gain to flip on). Surfaced to the watchdog as LOOP_QA wave-108. The
stats/scoring re-calibration remains THE high-leverage next step (user-gated).

## Wave 107 close (2026-06-02) — built the wave-106 anti-tank fix (watchdog Q18): the diagnosis was wrong on two counts; the IK hypothesis is REFUTED (7th frozen-under lever). Kept the one clear faithful pin (Ravager → Dark Lance), reverted the over-reach (Raider)

Branch `claude/sim-calibration-6`. Built the watchdog's Q18 anti-tank fix and the result materially refined
wave 106:

**(1) It is OVERRIDE-pinned, not a systemic mapper bias.** The clear platforms (Ravager/Raider/Razorwing)
bypass the mapper option-picker entirely — `data/overrides.json` pins them (the DRK-DIAG-5 de-over-arming,
which correctly fires ONE of the two mutually-exclusive cannon mounts but kept the anti-INFANTRY Disintegrator
and discarded the anti-tank Dark Lance). The fix is an override correction, not a mapper change.

**(2) (b) the systemic mapper mix-scoring — BUILT, MEASURED, REVERTED.** Added a target-toughness-mix wound
roll to `expected_damage_through_baseline()` (which had NO Strength-vs-Toughness term). It re-labelled 71
ranged + 48 melee picks with clear OVER-corrections (one-shot Hunter-killer missiles promoted to primary on
~8 Astra Militarum vehicles, Bright Lance → Starcannon, Knight Volcano-lance demoted) because a mix-AVERAGE
rewards high-volume generalists over specialists. Not faithful → reverted; the lone-Marine baseline stays.

**(3) (c) the cited override fix — A/B REFUTES the wave-106 IK hypothesis.** Corrected the Ravager → 3 Dark
Lances and (provisionally) the Raider → Dark Lance, cross-checked against the project's own Skysplinter
archetype (`code/archetypes.py`: 3 Raiders + 1 Ravager, "anti-tank from Ravager triples"). Clean N=40 A/B
(baseline gated 4.13): Imperial Knights +27.3 → +26.6 (−0.7, NOISE — NOT the predicted selective threat,
frozen-under like the prior six levers); Drukhari +4.6 → +9.0 (REAL — the bad anti-infantry loadout was
COMPENSATING for Drukhari being over-tuned; arming it just buffs Drukhari globally). Gated 4.13 → 4.30.

**Disposition.** KEPT the Ravager Dark Lance pin (unambiguously faithful — the list's named anti-tank
platform; kept per the watchdog's "keep faithful regardless of metric direction", though the Ravager-only
confirm showed it too degrades the headline — gated 4.48, Drukhari +11.7 — i.e. it carries re-calibration
debt). REVERTED the Raider pin (a TRANSPORT, not an anti-tank platform; the archetype assigns anti-tank to the
Ravager, not its 3 Raiders — an over-correction). Tests green (the lone equilibrium-phase4 failure was a
CPU-contention timing flake; passes 6.2s alone), smoke clean, audit clean. **This is the 7th lever to confirm
the IK +27 is a STATS/SCORING problem, not reachable by any simulator/loadout lever — the user-gated
re-calibration remains THE next step.** Surfaced to the watchdog as LOOP_QA Q18-OUTCOME (fork: keep the
Ravager now vs bundle the Drukhari loadout correction with the re-calibration). Memory
`project-antitank-picker-bias` rewritten.

## Wave 106 (2026-06-02) — diagnostic (no code change): the "Drukhari zero anti-tank" gap (watchdog hygiene #1) is a SYSTEMIC mapper option-picker bias — and a candidate FIRST non-frozen-under Imperial-Knights lever

Branch `claude/sim-calibration-6`. Per the watchdog's post-floor hygiene re-rank, investigated #1 (Drukhari
anti-tank). The cause is NOT the Strength≥9 tally threshold (the Dark Lance is S12). It is the BSData mapper's
weapon option-picker (`_collect_weapons_for_model`): it resolves a unit's weapon CHOICE groups by highest
expected damage **versus a baseline Marine** (anti-infantry), so anti-tank options lose to high-volume
anti-infantry options. Verified: the Drukhari Ravager — the archetype's literal "anti-tank from Ravager
triples" platform — is catalogued firing a Disintegrator Cannon (S6 D2), NOT a Dark Lance (S12 D6). SYSTEMIC,
not Drukhari-only: across all factions, choice-group units get mis-loadout'd onto anti-infantry guns, so
opponents UNDER-THREATEN vehicles / Monsters / KNIGHTS.

WHY THIS IS POTENTIALLY BIG: it is a candidate FIRST NON-FROZEN-UNDER lever on the IK +27. Unlike the six
even-handed levers (all helped the Knight too), this is a ONE-SIDED data-fidelity correction — giving the
Knight's OPPONENTS their real anti-tank loadouts raises their threat to the Knight WITHOUT helping the Knight
(its own single-model loadout has no such mis-pick). So it could lower IK without the frozen-under offset. It
is ALSO essential pre-re-calibration hygiene (cannot re-fit on lists with silently-absent anti-tank). Recorded
as memory `project-antitank-picker-bias`, surfaced as LOOP_QA Q18 (recommended fix (a): keep BOTH role-distinct
weapon options as fire-able profiles so the per-shot multi-profile picker chooses Dark Lance vs the Knight,
Disintegrator vs infantry — reuses the per-model loadout machinery). NOT band-aided (the systemic fix beats a
one-unit override). NEXT: build the option-picker fix and measure vs IK +27 — the most promising IK angle of
the session.

## Wave 105 close (2026-06-02) — Fire Overwatch core stratagem (gated `SWEG_OVERWATCH`), watchdog queue #3: faithful but REGRESSES at N=80 (frozen-under via Imperial Knights). SIXTH lever → the simulator-AI track is at its FLOOR; the IK +27 needs the RE-CALIBRATION (user's go)

Branch `claude/sim-calibration-6`. Built the missing 10e core Fire Overwatch stratagem (env-gated
`SWEG_OVERWATCH`): out-of-phase reaction shooting at chargers (`_do_charge`) and arriving reserves
(`_arrive_from_reserves`), hitting only on unmodified 6s, 1 Command Point, once per army per round; the AI
only overwatches when it can do meaningful damage (no wasted Command Point). Cited `simulator.fire_overwatch`.
The agent also caught + fixed a real double-Command-Point bug. 989 tests pass (+10 overwatch tests), audit
clean, run.py OK both gate states.

A/B: N=40 OFF 4.13 → ON 3.91 (−0.22), but **N=80 OFF 3.52 → ON 3.69 (+0.17, REGRESSED)** — the N=40
improvement was noise. Driver: **Imperial Knights +27.0 → +30.4 (gated 24.08 → 27.47, +3.4 WORSE)** — the
frozen-under effect: a Knight's big guns overwatch effectively, so IK benefits from punishing chargers far
more than the bled gunline under-shooters benefit. Faithful (a real missing mechanic) → KEPT gated; NOT
flipped (regresses).

**FLOOR REACHED — the session's structural conclusion.** SIX simulator-side levers now — terrain (w97),
per-model weapon structure (w99), per-weapon dice (w100), focus-fire (w101), deployment (w102-104), Fire
Overwatch (w105) — are ALL faithful but FROZEN-UNDER: none moves the Imperial Knights +27 (the dominant
residual, ~half the gated mean absolute error), and most are washes or small regressions on the headline,
because every even-handed improvement helps whoever has the stronger army (the over-shooters). The
simulator / artificial-intelligence calibration track has reached its practical floor for this residual. The
IK +27 is firmly a STATS problem, not a simulator-behaviour problem: it needs the FAITHFUL RE-CALIBRATION
(re-fit the per-faction stats/lists to the now-much-more-faithful sim — the session accumulated a lot of
fidelity the old stats no longer match) or the SCORING / victory-point model. BOTH are USER-GATED. Per the
watchdog's overnight guardrail ("if you run out of clean faithful levers, REPORT it and hold; do NOT cross
into the re-fit/scoring without the user"), the loop is REPORTING the floor and HOLDING for the user's
re-calibration go. The remaining queue levers (#4 trading-up, #5 combined-arms, #6 pile-in) are lower-impact
and expected to be the same frozen-under washes; not worth grinding the thrashed box before the
re-calibration. All the session's fidelity work is committed + gated (default-OFF), so the live baseline
holds; the re-calibration is the high-leverage next step.

## Wave 103 close (2026-06-02) — REFINED the deployment lever (gunlines at the zone midline, not buried): NET-POSITIVE headline (4.13 → 3.75) by un-burying the gunline under-shooters; the wave-102 "Imperial Knights drop" was an ARTIFACT (it buried IK's OWN Knights)

Branch `claude/sim-calibration-6`. Refined wave-102 per watchdog Q16: the high-value gunline group now
deploys at the deployment-zone MIDLINE (legacy single-line position, clear firing lane) instead of buried at
the board edge; the expendable screen stays forward. A/B (N=40, gated `SWEG_DEPLOY`):

| | gated MAE | Imperial Knights | Astra Militarum | Adeptus Mechanicus |
|---|---:|---:|---:|---:|
| OFF | 4.13 | +27.3 | −6.2 | −10.9 |
| crude (w102) | 4.67 | +25.4 | −8.1 | −12.3 |
| **refined (w103)** | **3.75** | +27.5 | −5.8 | **−8.4** |

The refinement flipped the lever to NET-POSITIVE (4.13 → 3.75) by un-burying the guns — the gunline
under-shooters recovered (Adeptus Mechanicus −10.9 → −8.4, BETTER than baseline; Astra Militarum −6.2 →
−5.8). BUT the wave-102 Imperial-Knights drop is GONE (IK back to +27.5 ≈ baseline). THE CORRECTION: the
crude IK-drop was an ARTIFACT, not a screening mechanism — burying the high-value group buried IK's OWN big
Knights at the board edge (slow to objectives), so the Knight army did worse for the wrong reason; restoring
them to the midline restores IK. So deployment is the FIFTH lever that does NOT fix Imperial Knights — but
the REFINED version is a genuine, faithful, NET-POSITIVE headline lever in its own right (a forward screen +
guns in a firing position = real screen-first deployment, helping the gunline under-shooters). KEPT gated;
recommended to the watchdog to confirm at N=80 and flip default-ON. **N=80 (wave 104) confirmed it is a WASH:
OFF 3.52 → ON 3.44 (gain −0.08, inside the noise band) — the N=40 −0.38 was mostly noise, so NOT flipped,
kept gated as a faithful metric-neutral fix; revisit at the re-calibration.** 17 deployment tests pass, audit clean,
run.py OK both gate states. Per the overnight guardrail, the re-calibration / scoring (the real IK fix)
remains the user's morning go.

## Wave 102 close (2026-06-02) — intelligent deployment + SCREENING (gated `SWEG_DEPLOY`), watchdog queue #2: REGRESSES the headline, but is the FIRST lever to move Imperial Knights DOWN (screening denies the Knight) — crude gunline placement hurts the under-shooters

Branch `claude/sim-calibration-6`. Built the watchdog's #2 lever (overnight-appropriate, faithful). The sim
line-deploys every unit on one line (`_deploy_armies`/`_deploy_line`) with no screening. The lever (env-gated
`SWEG_DEPLOY`) role-splits each army: expendable SCREENS / chaff deploy FORWARD (toward mid-board, to control
space + deny the deep-strike bubble + body-block charges), and high-value SHOOTING / durable / character units
deploy at the REAR of the deployment zone, protected. Role split reuses `code/roles.py` classify; even-handed,
cited `simulator.intelligent_deployment` (flagged AI tactic). 977 tests pass (incl. 17 new deployment tests),
audit clean, run.py OK both gate states.

A/B (N=40): gated 4.13 → **4.67** (REGRESSED +0.54). Mixed per-faction:

| | Imperial Knights | Chaos Daemons | Astra Militarum | Adeptus Mechanicus | Genestealer Cults |
|---|---:|---:|---:|---:|---:|
| OFF | +27.3 | −14.5 | −6.2 | −10.9 | +0.1 |
| ON | +25.4 | −11.3 | −8.1 | −12.3 | +3.1 |

THE INTERESTING FINDING: this is the FIRST lever to move Imperial Knights DOWN (+27.3 → +25.4, gated
24.37 → 22.47) — a screen body-blocks the Knight and denies it targets/charges, so SCREENING is a partial,
firepower-independent IK lever (distinct from the four refuted offence/AI levers). It also helped Chaos
Daemons (−14.5 → −11.3). BUT the crude "gunline to the back of the zone" placement HURT the gunline
under-shooters — Astra Militarum (−6.2 → −8.1) and Adeptus Mechanicus (−10.9 → −12.3) got MORE bled, not
less, because burying their guns at the board edge denies them early sightlines — and some deep-strikers got
stronger (Genestealer Cults +0.1 → +3.1). Net headline regressed. So: faithful CONCEPT, CRUDE implementation.
KEPT gated (preserves the IK-down finding); FLAGGED for refinement — screen forward AND keep gunlines with
sightlines (not buried), which might bank the IK-down without the gunline regression. Logged to watchdog.
Per the overnight guardrail: continuing clean faithful levers; the re-calibration / scoring (the real IK
fix) stays for the user's morning go.

## Wave 101 close (2026-06-02) — army-level FOCUS-FIRE targeting (gated `SWEG_FOCUSFIRE`), the watchdog's #1 Imperial-Knights lever: it IMPROVES the headline but makes Imperial Knights WORSE — even focus-fire is frozen-under

Branch `claude/sim-calibration-6`. Built the watchdog's #1 lever for the Imperial Knights +27 (the DEFENCE
half, after the per-model work refuted the offence over-count). Watchdog + user instrumented the root cause:
the per-unit target picker's "won't-crack penalty" makes every unit AVOID a 22-26-wound Knight (no single
unit cracks it) and shoot killable chaff, so opponents kill **0.00** big Knights/game despite carrying the
anti-tank to do it. FIX (`code/simulator.py`, env-gated `SWEG_FOCUSFIRE`): once per Shooting phase the army
nominates the most dangerous enemy brick it can crack COLLECTIVELY this phase (summed expected wounds ≥ 0.85
of its wounds, ≥2 contributing units), and every unit that can wound it concentrates fire. Only nominates a
collectively-crackable brick (no wasted fire on an unkillable target — the wave-79 pathology); a unit that
cannot wound the brick is never redirected. Faithful + even-handed (real tactic, all factions, any brick),
cited `simulator.focus_fire`. 12 tests pass (fixed an unseeded-RNG flake in the agent's harness), audit clean.

THE A/B (N=40 — the N=80 ON run was abnormally slow, ~2× normal, and was killed; the N=40 pattern is clear):

| Eval | gated MAE | Imperial Knights |
|---|---:|---:|
| OFF (baseline) | 4.13 | +27.3 |
| ON (`SWEG_FOCUSFIRE=1`) | **3.85** | **+29.0** |

The headline IMPROVED (4.13 → 3.85, −0.28) but Imperial Knights got WORSE (+27.3 → +29.0). The lever did NOT
crack the Knights — it is the **frozen-under pattern a 4th time**: even-handed focus-fire helps whoever has
the biggest guns, and the Knights HAVE the biggest guns, so a Knight army benefits from focusing ITS targets
more than its opponents benefit from finally focusing the Knight. The headline gain comes from OTHER matchups
(many armies now coordinate fire onto bricks). So: faithful + headline-positive, but NOT the IK lever — every
simulator-side lever tried (terrain, per-model structure, per-weapon dice, now focus-fire) leaves or worsens
IK +27. KEPT gated (faithful, real tactic) — the watchdog decides flip-default-ON vs keep-gated (the headline
gain is within the eval noise band, it worsens the #1 residual, and it carries a ~2× eval-time perf cost;
recommend pairing the flip with the re-calibration). The IK +27 is now structurally confirmed to need the
RE-CALIBRATION (re-fit stats to the faithful sim) or the SCORING / victory-point model — NOT any AI/firepower
lever. Logged to the watchdog (LOOP_QA). NEXT: continue the watchdog queue (#2 deployment/screening) and/or
the re-calibration inflection.

## Wave 100 close (2026-06-02) — Per-model weapon loadouts, STAGE 4: per-weapon Damage-dice ROLLING (gated `SWEG_ROLLDMG`). The OVERKILL half of the hypothesis is REFUTED too — rolling each weapon's real dice does NOT trim the big-gun / elite over-shooters; the Imperial Knights over-rate is durability, triangulated THREE ways

Branch `claude/sim-calibration-6`. Stage 4 of the per-model re-architecture (plan
`graceful-kindling-forest.md`). Now that per-model weapons are in place (Stage 3), Stage 4 rolls EACH
weapon's REAL Damage dice per shot instead of the mean (a Knight's anti-tank gun rolls its big dice, its
anti-horde gun its small dice — no averaging, no mean-overkill). Behind a SEPARATE env gate `SWEG_ROLLDMG`
so the dice effect is isolable from the per-model-structure effect; `roll_damage(dice, mean)` returns the
mean and draws NOTHING when the gate is unset or the weapon has no dice, so OFF and per-model-mean RNG
streams are byte-identical. Cited `simulator.rolled_damage` (10e Inflict Damage). 960 tests pass, audit
clean, run.py OK in all three gate states.

THE THREE-CELL A/B (N=80 — per-model variance needs N≥80):

| N=80 | gated MAE | Imperial Knights | Chaos Knights | Leagues of Votann | Adeptus Custodes |
|---|---:|---:|---:|---:|---:|
| OFF (legacy) | 3.52 | +27.0 | +2.0 | +7.4 | −3.8 |
| per-model, MEAN | 3.79 | +28.3 | +6.1 | +13.4 | −4.4 |
| per-model + DICE | 4.17 | +28.8 | +7.6 | +13.5 | −6.1 |

THE OVERKILL HALF IS REFUTED. Rolling each weapon's real dice (cell 3 vs cell 2) did NOT trim the big-gun /
elite over-shooters — Imperial Knights +28.3 → +28.8, Chaos Knights +6.1 → +7.6, Votann flat — and it
WIDENED the headline 3.79 → 4.17, mostly by adding variance that hurts the low-model elite armies (Custodes
−4.4 → −6.1). So NEITHER half of the user's hypothesis was the lever: not the weapon over-count (Stage 3),
not the mean-overkill (Stage 4). The Imperial Knights over-rate is now triangulated THREE ways (terrain
wave 97 + per-model structure + per-weapon dice) as durability / objective-holding — nothing about a
Knight's GUNS (count, dice, or overkill) moves its win rate, because it wins by sitting on a marker it
cannot be shot off.

What the re-architecture DID deliver is genuine FIDELITY — each model now fires its actual weapons with real
dice, special weapons lost on death, no over-collection, no mean-overkill. But it REGRESSES the headline
3.52 → 4.17 because the per-faction stats are still tuned to the OLD averaged-weapon sim — the expected
fidelity-first debt that the deferred re-calibration (LOOP_QA Q13) absorbs. The re-architecture is committed
and GATED (default OFF); Stage 5 (artificial-intelligence aggregate-isolation) completes it. The real
Imperial-Knights lever remains durability / objective scoring (threat-priority target AI or the
victory-point model), NOT firepower. DECISION on Stage 5 + the re-calibration vs pivoting to the durability
lever is pending the user.

## Wave 99 close (2026-06-02) — Per-model weapon loadouts, STAGES 2 + 3: firing now reads each model's own weapons (gated `SWEG_PERMODEL`). The Knight weapon over-count hypothesis is REFUTED at the metric — per-model is headline-neutral (within noise) and does NOT reduce the Imperial Knights over-rate

Branch `claude/sim-calibration-6`. Two stages of the per-model weapon re-architecture (plan
`~/.claude/plans/graceful-kindling-forest.md`). **Stage 2** (gate-inert) plumbed `model_loadouts` onto
`UnitProfile` (hashable flattened tuple + `_unflatten_model_loadouts`), metric 4.13 unchanged. **Stage 3**
(behavioural, env-gated `SWEG_PERMODEL`) made `Army.add_squad` instantiate one `Unit` per model from the
per-model loadout: each model fires its OWN weapons, a special weapon is lost when its model dies, a pistol
fires at engagement range, and single-model units fire only their actually-equipped guns (the over-count
fix from Stage 1 goes live here). Damage stays at the mean (dice is Stage 4). OFF (gate unset) is the legacy
shared-profile loop verbatim — byte-identical, no extra RNG. Cited `simulator.per_model_loadouts` (10e
Weapons / Making Attacks). 949 tests pass, audit clean, run.py OK in both gate states.

THE A/B (the headline test of the user's Imperial-Knights over-count hypothesis):

| Eval | gated MAE | Imperial Knights | Chaos Knights | Leagues of Votann |
|---|---:|---:|---:|---:|
| OFF N=40 | 4.13 | +27.3 | +1.0 | +6.7 |
| ON N=40 | 4.24 | +27.7 | +7.0 | +12.2 |
| OFF N=80 | 3.52 | +27.0 | +2.0 | +7.4 |
| ON N=80 | 3.79 | +28.3 | +6.1 | +13.4 |

REFUTED at the metric. Same-N comparisons show a small regression (N=40 +0.11, N=80 +0.27), but the gated
MAE itself has LARGE sampling noise — the OFF baseline alone swings 4.13 (N=40) → 3.52 (N=80) — so the
headline move is within noise. The RELIABLE, cross-N-consistent signal is per-faction: per-model firing
HELPS the strong multi-wound elite armies over-shoot MORE (Leagues of Votann +6, Chaos Knights +5) and
leaves Imperial Knights essentially FLAT (+27 → +28). So removing the Knight weapon over-count (a genuine
fidelity win) does NOT reduce the Knight win rate — TRIANGULATED TWICE now (terrain wave 97 + per-model
here): **the Imperial Knights over-rate is durability / objective-holding, not firepower.** Per-model is a
faithful representation upgrade (kept, gated) but it is the frozen-under pattern, not the Knight lever.
METHODOLOGY FINDING: per-model widens per-faction variance — N=40 is inadequate, use N≥80 for per-model
A/Bs (and the gated-MAE noise band is wider than previously treated). Stage 4 (per-weapon dice rolling) is
the UNTESTED other half of the hypothesis (mean-damage overkill of big guns) and sits on this. Decision on
continuing to Stages 4-5 pending the user.

## Wave 98 close (2026-06-01) — Per-model weapon loadouts, STAGE 1 of 5: the mapper preserves per-model loadouts + raw damage dice (DATA ONLY, additive, metric 4.13 unchanged); single-model weapon OVER-COLLECTION diagnosed + fixed in the data

Branch `claude/sim-calibration-6`. The user redirected the per-shot-damage-roll task into a fuller, faithful
re-architecture: move combat from one *averaged* weapon per squad to **per-model weapon loadouts** — each
model fires its own weapons with real damage dice rolled per shot, and loses that weapon when it dies; a
pistol can fire (weakly) at engagement range. The approved plan stages this across five env-gated steps
(`SWEG_PERMODEL`), each of which must keep the OFF eval at the 4.13 baseline; the aggregate
(`weighted_basket_average`) profile is kept unchanged so the whole AI / pricing / test blast radius keeps
working (additive dual representation).

STAGE 1 (data only, nothing reads the new data yet): `code/bsdata/mapper.py` now preserves a structured
`model_loadouts` per unit (each model type: name, count, and its ranged / melee weapons, each carrying the
raw Attacks / Damage **dice strings** alongside the existing means). Crucially, **single-model units now use
the same option-per-choice-group picker that multi-model squads already used** — they previously fell to a
legacy flat weapon-walk that collected EVERY weapon option, including mutually-exclusive arm weapons. The
aggregate is untouched; 1344 units gained `model_loadouts`.

KEY DIAGNOSTIC — this validates the user's Imperial-Knights over-rate hypothesis. **523 of 907 single-model
units were over-collecting weapons.** The Wraithknight dropped from five firing weapons (including BOTH
alternative arm cannons, Suncannon AND Heavy Wraithcannon) to its actual loadout (one arm cannon); the Knight
Castellan / Paladin / Errant shed their mutually-exclusive carapace options. So Knights have been firing guns
they cannot simultaneously equip — the suspected driver of the +27 over-rate the artificial-intelligence and
terrain tracks could not reach. This correction goes LIVE when firing reads the loadout (Stage 3).

The necessary parsed.json regeneration also synced a stale `deadly_demise` field (1 → 5 on 55 large chassis):
the committed parsed.json predated a prior "Deadly Demise D6+2" mapper fix and was never regenerated. Kept
per rule 7 (parsed.json must equal the mapper's output, not a hand-preserved stale value); it is
metric-neutral (4.13 with either value at N=40) and a constant across every per-model A/B, so it does not
confound the staging.

Verification: OFF N=40 gated MAE = **4.13 exactly** (unchanged — proves data-only), Imperial Knights +27.3
unchanged; 933 tests pass (the only failures are the pre-existing Stage-2 equilibrium-solver timing tests),
new `tests/test_model_loadouts.py` green, citation audit clean, `run.py --cli` exits cleanly. Next: Stage 2
(plumb `model_loadouts` onto `UnitProfile`, gate-inert).

## Wave 97 close (2026-06-01) — terrain rebuilt to the competitive Pariah Nexus density (Stream C, P1); FAITHFUL but REGRESSED gated 3.59 → 4.13 and REFUTED the sparse-terrain hypothesis (Imperial Knights got WORSE)

Branch `claude/sim-calibration-6`. Unparked Stream C with the watchdog's supplied competitive-terrain
reference (Q12) and rebuilt every stock map's terrain to the published Pariah Nexus density. KEPT despite
the regression — realistic terrain is faithful by construction (the May-2026 target was played on it), and
the result is an important DIAGNOSIS, not a lever to chase.

BUILT: `code/maps._competitive_terrain(width, height)` — mirrors a seed set of ruins / woods / barricades
through 180-degree rotation about the board centre (EVEN-HANDED by construction, neither deployment zone
favoured), producing ~11 large line-of-sight-blocking RUIN rectangles (about five-to-six inch footprints) +
~6 scatter pieces per map, ~19% coverage (up from the old sparse ~8%), with no clean cross-table sightline
(10% of deployment-zone-to-deployment-zone lines remain clear). Applied to all nine stock maps (the
five-map eval rotation plus four others); objectives left exactly where each mission places them. Cited
`terrain.competitive_pariah_nexus_layout` (Games Workshop Pariah Nexus Tournament Companion + Goonhammer
review).

| Eval (N=40) | MAE_gated | in band | Imperial Knights | Chaos Daemons | World Eaters | Orks |
|---|---:|---:|---:|---:|---:|---:|
| Baseline (wave 96, sparse terrain) | 3.59 | 7/22 | +25.9 | −15.6 | +6.2 | +2.7 |
| **Competitive terrain (LANDED)** | **4.13** | 6/22 | **+27.3** | **−14.5** | +9.8 | +7.7 |

THE HYPOTHESIS IS REFUTED. The watchdog ranked terrain P1-HIGHEST expecting it to crack the Imperial
Knights over-hold (sparse boards letting Knights shoot across the table). The opposite happened: Imperial
Knights got WORSE (+25.9 → +27.3). Chaos Daemons improved slightly as predicted (+1.1 — cover helps melee
advance), but the dominant effect is that realistic terrain HELPS the durable / melee over-shooters: it
shields the unkillable Knight objective-holder from return fire MORE than it limits the Knight's own (now
ruin-blocked) shooting, and it lets melee close (World Eaters, Orks). DIAGNOSIS: the IK over-hold is
durability-as-objective-holder, NOT table-wide shooting; realistic terrain AMPLIFIES it. Terrain is NOT the
IK lever (re-ranked).

KEPT per the prime directive + the watchdog's Q12 ("keep the realism even if it moves the metric the wrong
way"): reverting to sparse boards to protect 3.59 would be choosing a KNOWN INFIDELITY to flatter the
metric. The 3.59-on-sparse figure was a partly-spurious fit on the wrong board; 4.13-on-realistic is the
honest current fidelity. The regression is fidelity-versus-metric debt feeding the planned re-calibration
(Q13: terrain plus the per-shot damage roll land, then re-fit toward real data and land the held
artificial-intelligence Objective-Control fix). 927 tests pass (the Marines-mirror smoke test passes in
isolation; only the pre-existing Stage-2 solver timing test fails), citation audit clean, `run.py --cli`
exits cleanly. Finding logged (LOOP_QA Q14). Session headline gated 5.98 → 4.13 — the honest number on
realistic terrain. Next: P1.5 (per-shot damage roll).

## Wave 96 close (2026-06-01) — core-rules audit quick-fix batch (three parallel worktree streams); LANDED Stream D+E rules-correctness (gated 3.76 → 3.59); HELD Stream A AI-fidelity (frozen-under)

Branch `claude/sim-calibration-6`. Ran the watchdog's core-rules-audit quick-fix batch (per the user's
2026-06-01 parallel-fan-out directive) as THREE file-disjoint concurrent worktree agents, then merged the
faithful winners and held the frozen-under regressor. This wave's value is in the clean split between
rules-correctness (helps the headline) and artificial-intelligence-planning fidelity (regresses it).

LANDED:
- **Stream D+E (rules-correctness — `map.py` / `units.py` / `simulator.py`).** Collapsed cover to a single
  Benefit of Cover (removed the stale 9th-edition −1-to-hit and the Light/Heavy split); corrected Ruins /
  Woods line of sight to current 10e (TOWERING no longer sees through ruins — only AIRCRAFT does; removed
  the stale infantry "shoot through ruin walls" pass, which is movement-only in 10e); added the
  Benefit-of-Cover Armour-Penetration-0 / Save-3+ exception for ALL models (was mis-gated to infantry);
  removed the stale Fall Back FLY exemption (a unit that Fell Back cannot shoot or declare a charge — no
  FLY exception). All re-cited verbatim to the current 10e core rules. Tests rewritten to the new rules,
  not weakened.
- **Stream B1.** Counter-Offensive citation `quoted_text` corrected to current 10e ("has not already been
  selected to fight this phase").

HELD / DEFERRED (honestly, not discarded):
- **Stream A (artificial-intelligence Objective-Control fidelity).** Aligned the planner's Objective-
  Control view with the scorer (the damaged-Knight bracket + battle-shock Objective-Control = 0; plus my
  enemy-snapshot symmetry + `SWEG_DMGOC` gate completions). Genuinely faithful, but it REGRESSED the
  headline and reversed Stream D+E's Imperial-Knights / Drukhari gains — the frozen-under signature. HELD
  in full on branch `held/stream-a-ai-oc-fidelity` (commit `452ce81`), re-queued, and the keep-versus-hold
  fork escalated to the watchdog (`LOOP_QA.md` Q13). Did not bank a headline regression; nothing is lost.
- **Stream B2 (universal Insane Bravery).** Registered + cited but mechanically INERT — the auto-pass needs
  an in-phase hook + a Command-Point spend policy in `_run_battleshock_phase`. Re-queued as a P2 build, NOT
  landed as a live-but-fake rule.
- **Stream C (terrain density).** Parked on the watchdog supplying citable real Pariah Nexus layouts
  (`LOOP_QA.md` Q12); it also correctly sequences after Stream D's line-of-sight fixes, which just landed.

| Eval (N=40) | MAE_gated | in band | Imperial Knights | Drukhari | Chaos Daemons |
|---|---:|---:|---:|---:|---:|
| Baseline (wave 95) | 3.76 | 9/22 | +27.0 | +6.4 | −14.7 |
| Stream A combined (HELD) | 3.89 | 5/22 | +27.8 | +5.7 | −15.3 |
| **Stream D+E + B (LANDED)** | **3.59** | 7/22 | **+25.9** | **+4.7** | −15.6 |

Result: gated 3.76 → **3.59** (−0.17), driven by the two factions the watchdog's D2 (ruin line of sight)
and E1 (no shooting after Fall Back) hypotheses targeted — Imperial Knights and Drukhari. Chaos Daemons
marginally worse (−0.9, its separate combat/positional residual). In band 9 → 7 (the cover / line-of-sight
changes nudged a couple of borderline factions) but the gated mean absolute error — the primary signal —
improved. 928 tests pass (2 pre-existing Stage-2 equilibrium-solver timing failures, unrelated), citation
audit clean, `run.py --cli` exits cleanly. Also unblocked: P1.5 (roll damage per shot) now that Stream D's
`units.py` work landed. Session headline gated 5.98 → 3.59, all faithful.

## Wave 95 close (2026-06-01) — positional re-model Candidate B (idle-unit objective massing) LANDED — gated 4.15 → 3.76, the first positional candidate to work; Chaos Daemons −22.7 → −14.7

Branch `claude/sim-calibration-6`. Built the plan's Candidate B (the move AI massing body-army units
onto markers, the DOMINANT sub-cause). A first aggressive version regressed; a faithful refinement
LANDED. The Q11 positional axis is finally moving — the dominant under-shooter cracked.

THE PROGRESSION (env-gated A/B, SWEG_MASS):
- Aggressive (ALL non-holding units mass, abandoning shooting): gated 4.15 → **6.50** — REGRESSED
  chaotically (T'au +0.9 → +26.7, etc.) because it pulled in-range shooters off their fire-lanes. BUT it
  moved the target axis the RIGHT way (IK +27 → +18.4, Daemons −22.7 → −13.3) — the first candidate to do
  so (geometry w94 helped the wrong factions).
- Faithful refinement (only units OUT of their own firing range mass; in-range shooters keep shooting) +
  arrive-in-cover snap: gated 4.15 → **3.76** — LANDED. In band 8 → 9.

| Eval (N=40) | MAE_gated | in band | Chaos Daemons | Imperial Knights |
|---|---:|---:|---:|---:|
| Baseline (wave 92-94) | 4.15 | 8/22 | −22.7 | +27.0 |
| **Candidate B (landed)** | **3.76** | **9/22** | **−14.7** | +27.0 |

LANDED default-ON (`SWEG_MASS=0` to re-gate). The dominant under-shooter Chaos Daemons improved
−22.7 → −14.7 (+8.0 — its idle Daemons now reach the markers), and Drukhari (+11 → +6.4), T'au, Custodes
eased; a few armies regressed (Astra −4.9 → −8.9, Adeptus Mechanicus, Chaos Space Marines — their idle
units massing is net-negative for them) but the headline NET improved. Imperial Knights unchanged at +27
— the over-shooter half of the axis did NOT move (a Knight can't be shot off and there is no
representation fix for its durability), but the UNDER-shooter half cracked, which is the bigger residual
mass. Faithful: idle out-of-range units play the objectives and take cover — a real tactic, even-handed
across all factions, NOT a per-faction or per-model-count knob, NOT a scoring conversion. Passes every
§5 hard-rail. 927 tests pass; audit clean; run.py OK. Memory `project-ai-frozen-under-mae-first` (the
exception: a faithful AI fix that LANDED because it helps the non-reachers, not the already-strong).
Session headline now gated 5.98 → 3.76, all faithful.

## Wave 94 close (2026-06-01) — positional re-model Candidate A (geometry/clustering) BUILT + A/B'd → REGRESSED (frozen-under), reverted. Candidate B (AI massing, the dominant sub-cause) next

Branch `claude/sim-calibration-6`. Built the plan's lead candidate — the geometry/clustering
correction (`SWEG_CLUSTER`) — A/B'd it, and it REGRESSED. Reverted per the user's "if it washes,
report honestly — do not force, no knob" rule. The result is informative for Candidate B. No net code
change; headline back at gated 4.15.

BUILT (env-gated, reverted): in `Battle._assign_army_oc`, a squad genuinely ON an objective (≥1 model
within the true 3" radius) credited its Objective Control over models within a coherency-extended
footprint (3" + 2" Unit Coherency), modelling that a real unit holding a marker clusters on it rather
than the sim's one-Unit-per-model spread (wave-93: near-marker OC within 6" ≈ 2× within 3"). Even-handed
(a 1-model Knight counts only itself). Cited `simulator.objective_control_clustering` (representation
correction). 927 tests pass, audit clean.

| Eval (N=40) | MAE_gated | in band | IK | Daemons |
|---|---:|---:|---:|---:|
| Cluster OFF | 4.15 | 8/22 | +27.0 | −22.7 |
| **Cluster ON** | **4.30** | 8/22 | +27.0 | −22.7 |

REGRESSED (+0.15) — the FROZEN-UNDER signature. IK unchanged (1-model Knight, correctly unaffected) and
Daemons unchanged (the geometry fix can't reach them — their models are not near markers at all, the
DOMINANT AI-not-massing sub-cause). The worsening came from the OVER-shooters (Custodes +3.1→+4.3, Votann
+11.9→+12.6) — the clustering boost helps multi-model units ALREADY HOLDING markers, which are the
over-shooters, while the under-shooters (Astra −4.9→−5.9) did not benefit. So the geometry fix is
faithful-ish but the WRONG lever: it amplifies whoever already holds markers (the over-shooters), not the
under-shooters whose problem is they do not REACH markers.

THE READ FOR CANDIDATE B. A addressed the SECONDARY sub-cause (near-marker spread) and helped the
already-holders. The DOMINANT sub-cause is AI-not-massing (under-shooters' models are nowhere near
markers). Candidate B (the move AI massing body-army units ONTO markers) pushes the OPPOSITE direction —
it would help the non-reachers (the under-shooters) reach markers, NOT the over-shooters who already
reach. So B is genuinely distinct from A's failure and worth trying, even though it is the contest/deny
class (w81) that washed once. Next (wave 95): build Candidate B (`SWEG_MASS`), env-gated, per-matchup
measured on the IK + Daemons cells; expect a likely wash (the plan's stance) — if it washes, REPORT the
axis as a one-Unit-per-model representation limit that resists faithful fixes, and stop chasing it.

## Wave 93 close (2026-06-01) — positional re-model SCOPED (Q11 plan wave): the body-army on-marker OC gap is geometry/spread (secondary) + AI-not-massing (dominant); plan-first, no code

Branch `claude/sim-calibration-6`. The deck re-alignment is done, so per the user's sequence this wave
plans the Q11 positional re-model (the user mandated plan-first for this high-risk, sharpest-surface
change). Deliverable `docs/POSITIONAL_REMODEL_PLAN.md`. Headline unchanged at gated 4.15.

NEW DIAGNOSTIC (pins the sub-cause). A within-3"-vs-within-6" drill (Imperial Knights vs Chaos Daemons /
Astra / Tyranids) shows the body army's per-marker objective control within 6" is ~2× the within-3":
Daemons 5.8 / 9.4, Astra 4.5 / 8.4, Tyranids 7.7 / 15.6 (army totals ~111 / ~95 / ~185). Two sub-causes:
(1) GEOMETRY/SPREAD (secondary, cleaner lever) — half a body army's NEAR-marker objective control sits in
the 3"–6" band outside the 3" scoring radius (units near a marker are spread by the one-Unit-per-model +
coherency placement; real units cluster on the marker); (2) AI-NOT-MASSING (dominant) — even the within-6"
figure is a tiny fraction of the army total, so most of the army is nowhere near a marker (the regress-prone
AI-positioning class). The within-3" body-army OC (4.5–7.7) is BELOW a big Knight's ~10, so the body army
loses the contest at the marker — a geometry fix recovering the 3"–6" band would roughly DOUBLE on-marker
OC and let body armies out-control a Knight.

PLAN. Candidate A (LEAD, the user's authorised geometry category, least like the washed AI lever): a
clustering correction so a unit on an objective has its models within the 3" scoring radius (A1 real
placement / A2 representation, even-handed, Knight unaffected). Candidate B (the dominant sub-cause but
the washed class): AI massing body-army units onto objectives — build only if A is insufficient, expect a
likely wash. Build env-gated (SWEG_CLUSTER / SWEG_MASS), per-matchup measured (IK + Daemons holding cells,
watch Drukhari/Votann for the frozen-under signature), keep only a clear faithful axis-win; if it washes,
REPORT it as a one-Unit-per-model representation limit — do NOT force, do NOT reach for a knob, do NOT nerf.
Hard-rails self-check in the plan §5. Next (wave 94): build Candidate A1 env-gated.

## Wave 92 close (2026-06-01) — Chapter Approved 2025-26 secondary re-alignment COMPLETE (part 2/2: Bring It Down + Assassination wound-tiers) — metric-flat as predicted (4.10 → 4.15); deck re-align done, positional re-model next

Branch `claude/sim-calibration-6`. Completed the CA-2025-26 deck re-alignment (the user's Q10 ruling)
with the two wound-data cards deferred from wave 91. Metric-flat (cap-wash), kept as the faithful match
to the target deck. Headline gated 4.15 (was 4.10 after part 1 / 4.08 at the floor — all within the
deterministic noise of the secondary cap-wash). The deck re-alignment is now COMPLETE.

BUILT (part 2): threaded destroyed-unit Wounds-characteristic data through the round snapshot (three new
`RoundSnapshot` frozensets: MONSTER/VEHICLE ids at 15+ and 20+ wounds, CHARACTER ids at 4+ wounds — from
`profile.health`, the datasheet max). Then: **Bring It Down** flat-3 → CA-2025-26 **2 +2(15+ total
wounds) +2(20+), max 6/unit, no per-round cap** (a Knight = 6 VP, a Rhino = 2); **Assassination**
flat-3/char → CA-2025-26 **4 VP (4+ wound CHARACTER) / 3 (<4), no per-round cap, no Warlord bonus** (the
Pariah Nexus +1 removed). Three citations rewritten to CA-2025-26 verbatim (Bring It Down, Assassination,
Warlord designation); 3 tests updated + 2 new wound-bracket tests; 927 tests pass; audit clean; run.py OK.

| Eval (N=40) | MAE_gated | in band |
|---|---:|---:|
| Floor (wave 90) | 4.08 | 8/22 |
| CA-2025-26 part 1 (wave 91) | 4.10 | 8/22 |
| **CA-2025-26 part 2 (complete)** | **4.15** | 8/22 |

Metric-flat across both parts (+0.07 total, deterministic but tiny) — the wave-90 cap-wash prediction
holds: both armies max the 40-VP secondary cap, so secondary-value changes barely move the headline.
KEPT as the faithful match to the deck the May-2026 calibration target was played under (fidelity, not
metric — the user's explicit framing). DECK RE-ALIGNMENT COMPLETE (7 cards re-valued: No Prisoners, Cull,
Engage, Behind Enemy Lines, Extend Battle Lines, Bring It Down, Assassination; the 5 board cards — Storm
Hostile Objective, Secure No Man's Land, Area Denial, Defend Stronghold + Extend — confirmed unchanged).
NEXT (wave 93): plan + build the Q11 positional re-model (the one structural axis — IK over-holds /
Daemons under-holds the markers; diagnose-not-nerf, faithful/even-handed/plan-first, NOT a per-faction
objective-control→primary-VP knob; high-risk, may wash — report honestly if so).

## Wave 91 close (2026-06-01) — Chapter Approved 2025-26 secondary re-alignment, part 1/2 (5 cards) — faithful, metric-flat as predicted (4.08 → 4.10, within noise); user Q10/Q11 ruled

Branch `claude/sim-calibration-6`. The user ruled the structural-floor checkpoint (commit 0541e23):
**Q10 = Chapter Approved 2025-26** (re-align the secondary model + re-check Tier A to CA-2025-26,
sourced from ≥2 CA sources, never 40k.app); **Q11 = (c)** authorise the hard positional-representation
re-model (diagnose-not-nerf, faithful/even-handed/plan-first, not a per-faction OC→VP knob). Sequence:
deck re-align first, then the re-model. This wave did part 1 of the deck re-align.

VERIFICATION (the user's ≥2-CA-source requirement). A research agent confirmed the current CA-2025-26
values against wahapedia chapter-approved-2025-26 + the GW Tournament Companion PDF + Goonhammer's CA-2025
review (NOT 40k.app). Five cards changed value, five Tier-A board cards are UNCHANGED from Pariah Nexus
(Storm Hostile Objective, Secure No Man's Land, Area Denial, Defend Stronghold = no action; Extend
Battle Lines dropped 5→4).

BUILT (5 cards, direct value/logic changes — these are the faithful target-deck values, not env-gated):
No Prisoners 3→**2** VP/unit; Cull the Horde 10-model/3 VP → **13-model / 5 VP** (no per-round cap);
Engage on All Fronts 2/3/5 → **1/2/4** at 2/3/4 quarters; Behind Enemy Lines flat-4 → **3** (one unit) /
**4** (two+); Extend Battle Lines 5 → **4**. 5 citations rewritten to CA-2025-26 verbatim text + sources;
8 tests updated; 926 tests pass; audit clean; run.py OK.

| Eval (N=40) | MAE_gated | in band |
|---|---:|---:|
| Wave 90 baseline | 4.08 | 8/22 |
| **CA-2025-26 part 1** | **4.10** | 8/22 |

Metric-FLAT (+0.02, within noise) — exactly the wave-90 cap-wash prediction (both sides max the 40-VP
secondary cap, so secondary-value changes barely move the headline). KEPT because it is the faithful
match to the deck the May-2026 target was played under (fidelity, not metric — the user's explicit
framing). DEFERRED to wave 92 (need destroyed-unit wound-data plumbing in the round snapshot): Bring It
Down flat-3 → **2 +2(15+ wounds) +2(20+ wounds)** per unit; Assassination 3/char → **4** (4+ wound
character) / **3** (<4) + remove the Warlord bonus. THEN (wave 93+): plan + build the Q11 positional
re-model.

## Wave 90 close (2026-06-01) — Chaos Daemons re-diagnosed: POSITIONAL (primary-VP / objective-massing), not combat or attrition; secondary is a CAP-WASH; the residual floor is one structural axis. Strategic checkpoint escalated (no code change)

Branch `claude/sim-calibration-6`. Re-diagnosed the Daemons residual (attrition ruled out wave 88) with a
combat-vs-positional drill (Daemons vs AdMech / Drukhari / Thousand Sons / Astra, survival + primary/
secondary VP split). Two structural findings consolidate the whole remaining residual picture. No code
change; headline gated 4.08. Strategic checkpoint logged `LOOP_QA.md` Q11.

FINDING 1 — Daemons is POSITIONAL, not combat/attrition. Daemons SURVIVE (40–75% of units alive at game
end; not tabled, except vs Drukhari) but LOSE THE PRIMARY race: their primary VP (15–50) trails the
opponent's (20–50) in the losses, while their secondary is capped (see finding 2). So their surviving
bodies do NOT translate to objective control — the same "body army has total Objective Control but does
not mass it onto the markers" gap diagnosed for the under-shooters generally (`project-oc-contest-faithful`).
NOT combat-power (they live), NOT attrition (wave 88 was neutral).

FINDING 2 — secondary VP is a CAP-WASH after Tier A. Both sides generate 80–115 RAW secondary VP, all
clamped to the real 40-VP cap (`_decide_winner`), so secondary contributes ~40 to BOTH and no longer
DIFFERENTIATES — the winner is decided on PRIMARY VP (objectives). Tier A helped (4.95→4.17) by lifting
under-scorers toward the cap, but the secondary layer is now saturated; further secondary work has
diminishing returns because both armies already max it.

THE CONSOLIDATED PICTURE. The dominant remaining residual is ONE structural axis — PRIMARY VP /
objective control: Imperial Knights +27 OVER-holds the markers (durable, uncontestable), Chaos Daemons
−22 UNDER-holds them (survives but does not mass on objectives). Together ≈ half the gated MAE. This is
the one-Unit-per-model positional/representation gap, and the faithful AI levers for it have been
exhausted and REGRESS/WASH (value-targeting w72, focus fire w79, contest/deny w81; the contest is
faithful w84; per `project-ai-frozen-under-mae-first`). So the headline ~4.08 is a STRUCTURAL FLOOR on
the faithful track. The remaining clean lever is the secondary deck re-alignment (Q10, blocked on the
user's ruling, and likely small per finding 2). Strategic checkpoint Q11: rule on Q10 for the small
deck win, and assess whether 4.08 is "substantially converged" vs investing in the hard positional-
representation work (high-risk). Memory `project-faction-residual-rootcause` updated.

## Wave 89 close (2026-06-01) — detachment-fabrication sweep on the over-shooters: NEGATIVE finding — they are already clean; the over-rates are structural, not fabricated buffs (no code change)

Branch `claude/sim-calibration-6`. With Tier B parked (Q10 deck ruling still OPEN) and the Daemons
attrition lever spent, took a different clean deck-independent angle: a detachment-fabrication audit on
the over-shooter factions (memory `project-detachment-fabrication-pattern` — removing a fabricated
always-on buff is faithful AND reduces an over-shoot). Negative-but-useful result; no code change.
Headline unchanged at gated 4.08.

THE FINDING. The over-shooter detachments (Leagues of Votann, Drukhari, Adeptus Custodes, World Eaters,
Adepta Sororitas, T'au, Thousand Sons) are LARGELY CLEAN — the fabricated always-on attack buffs were
already swept in prior waves (Invasion Fleet enemy-Ld, Pactbound reroll-wounds, Sororitas plus-wound,
World Eaters plus-hit, Grand Coven psychic mortals, etc. — all already removed). The audit (BSData-
verified, not just grep) found NO active unconditional fabricated buff on any over-shooter. So the
over-shooter over-rates are STRUCTURAL (positioning / scoring / representation), NOT fabricated
detachment buffs — a useful negative that focuses future work away from this lever.

Two minor flags (neither a clean metric-positive fix, both deferred):
- **Custodes Shield Host `melee_crit_on_5_plus_hits`** was removed earlier citing a Wahapedia 3-bullet
  Martial Mastery; BSData v10.6.0 has it as a real 2-bullet "pick one at battle-round start" rule (crit-
  on-5+ AND AP+1), so the removal cited the wrong source. BUT this is edition-uncertain (BSData 2-bullet
  vs Wahapedia 3-bullet — possible stale-BSData), restoring it WORSENS Custodes (an over-shooter), and it
  needs an even-round-alternation build. Deferred to a careful fidelity pass; not a clean win.
- **Inquisition Task Force `reroll_hit_ones`** (Agents of the Imperium) is a real name+scope fabrication
  (army-wide vs the real CHARACTER-gated Daemon Hunters rule), but Agents is not one of the 22 evaluated
  factions, so it is zero-metric correctness cleanup — deferred.

STRATEGIC STATE. The clean faithful levers are thinning at gated 4.08 (down from 5.98 this session). The
residual mass is now IK +27 (positioning/structural, reported not faithfully fixable) and Daemons −22
(attrition neutral; combat/positional, hard); the biggest remaining clean lever is the secondary
deck-re-alignment, BLOCKED on the Q10 deck ruling. Memory `project-detachment-fabrication-pattern`
updated (over-shooters swept clean).

## Wave 88 close (2026-06-01) — DAEMONIC MANIFESTATION built + landed (real rule, cited), but METRIC-NEUTRAL — it does NOT fix the Chaos Daemons residual; the wave-87 diagnosis over-attributed

Branch `claude/sim-calibration-6`. Built the wave-87-planned fix — the missing friendly half of the
Chaos Daemons army rule. It is a real rule, correctly implemented and cited, and it is KEPT (fidelity),
but the N=40 A/B shows it is **metric-neutral**: it does NOT account for the Daemons −22 residual. An
honest negative result — the wave-87 diagnostic was over-confident.

BUILT: Daemonic Manifestation in `_run_battleshock_phase` (cited `simulator.daemonic_manifestation`,
verbatim BSData text, rule id a312-a2f1-e1c0-30ed). While a Chaos Daemons unit is in its Shadow of
Chaos (proxied as own deployment zone OR within 18" of centre — parity with the existing Daemonic
Terror proxy) it gets +1 to its Battle-shock test, and ON A PASS returns up to D3 destroyed models
(BATTLELINE) / D3 lost wounds via the existing reanimation pulse (`transient_undying_legions_pulse`,
the same plumbing Foetid Resurgence uses; consumed end-of-round by `_apply_undying_legions_pulse`).
Faction-gated to Chaos Daemons (correct — only they have it). Env-gated SWEG_DAEMONIC (default ON).

| Eval (N=40) | MAE_gated | in band | Chaos Daemons |
|---|---:|---:|---:|
| DAEMONIC OFF (=0) | 4.08 | 8/22 | −22.2 (28.6%) |
| **DAEMONIC ON** | **4.08** | 8/22 | **−22.5 (28.3%)** |

Within noise — no real movement. Verified the implementation is NOT a silent no-op (faction matches the
existing Terror check; `_initial_unit_counts` is populated for ALL armies so the revival pulse fires for
Daemons; the pulse is not clobbered between Command-phase set and end-of-round consume). So the rule
genuinely fires but is marginal for the metric. Likely reasons: (1) aggressive Daemons push PAST their
own Shadow into enemy territory, so they are rarely in-Shadow when dying (the own-DZ + 18"-centre proxy
excludes the enemy zone, where the real rule WOULD apply if they hold ≥half the objectives there); (2)
more fundamentally, the −22 residual is not the attrition rule — Daemons lose the firefight / get tabled
before attrition resistance matters, or it is the broader positional/VP-while-alive class. KEPT default-ON
(a real rule the sim was missing — fidelity, metric-neutral, no regression; the damaged-OC precedent),
but the Chaos Daemons residual needs RE-DIAGNOSIS (combat-power / positional, not this rule). 926 tests
pass; audit clean. Memory `project-daemons-manifestation-missing` updated with the negative result.

## Wave 87 close (2026-06-01) — diagnosed the #1 residual (Chaos Daemons −22.2): a real missing rule, DAEMONIC MANIFESTATION; build planned for next wave (no code change)

Branch `claude/sim-calibration-6`. With Tier B parked pending the deck ruling (Q10 still OPEN), did
the clean non-secondary work I committed to: diagnosed the largest residual, Chaos Daemons (sim 28.6%
vs real 50.8%, −22.2). High-confidence, faithful, non-secondary, deck-independent finding. Headline
unchanged at gated 4.08. Build planned for next wave (clean context — it needs a model-revival path,
not a tail-of-session rush; the wave-84/85 lesson).

THE FINDING (BSData-verified myself, not just the sub-agent). The simulator implements only HALF of
the Chaos Daemons army rule "The Shadow of Chaos". The enemy-debuff half, **DAEMONIC TERROR** (enemy
units in the Shadow take Battle-shock at −1 and D3 mortal wounds on a fail), IS implemented
(`_run_battleshock_phase`, cited `simulator.shadow_of_chaos`, proxied as "enemy within 18\" of board
centre while a Daemons army opposes"). The friendly-attrition half, **DAEMONIC MANIFESTATION, is
entirely missing** — grep returns zero hits. BSData cache (`Chaos - Chaos Daemons Library.cat.gz`,
rule id `a312-a2f1-e1c0-30ed`) verbatim: "While a LEGIONES DAEMONICA unit from your army is within
your army's Shadow of Chaos, each time that unit takes a Battle-shock test, add 1 to that test and, if
that test is passed, one model in that unit regains up to D3 lost wounds (if that unit is a BATTLELINE
unit and that test is passed, up to D3 destroyed models can be returned to that unit instead)." The
Shadow itself (verbatim): "Your deployment zone is always within your army's Shadow of Chaos" + No
Man's Land / opponent's zone if Daemons control ≥half the objectives there.

WHY IT IS THE CAUSE. Daemons' battleline (Bloodletters / Plaguebearers / Daemonettes / Pink Horrors —
T3–T5, Sv7+, 5++) is the bulk of every mono-god archetype and is extremely fragile. Daemonic
Manifestation is their core attrition mechanic — it returns D3 models per round a battleline unit
passes Battle-shock in the Shadow, keeping them on objectives. Without it they evaporate under fire 2–3
rounds early and cannot hold the board; this is mechanically why Daemons got WORSE (−18.3 → −22.2) when
board-control secondaries landed (wave 83), and why the residual has been stable since wave 10.

BUILD PLAN (next wave). In `_run_battleshock_phase`: (1) compute `in_daemons_shadow` for a Chaos
Daemons rep — faithful proxy = its OWN deployment zone (the rule GUARANTEES the DZ is in Shadow; clean
y-band like cleanse/sabotage) OR within 18\" of centre (parity with the existing Terror proxy, covering
the forward/objective-holding case); (2) +1 to the test for Daemons units in Shadow (a Ld bonus, same
convention as the existing modifiers); (3) on PASS, for BATTLELINE return up to D3 destroyed models via
the Necron reanimation revival path (`_apply_reanimation` is the model to reuse), else restore D3 lost
wounds to one model. Env-gated A/B, cited `simulator.daemonic_manifestation` from the BSData rule id
above; even-handed (the real Daemons faction rule, applied only to Daemons, like the Knights damaged-OC
bracket). Recorded `project-daemons-manifestation-missing`.

## Wave 86 close (2026-06-01) — Tier B verification surfaced a MISSION-DECK fork (Pariah Nexus 2024 vs Chapter Approved 2025-26); escalated, Tier B parked (no code change)

Branch `claude/sim-calibration-6`. Opening Tier B (kill-card formula corrections), I applied the
wave-84/85 lesson — verify the real values against ≥2 sources before changing — via a Sonnet research
agent. It surfaced a fork I did not know about, which is the wave's deliverable. Headline unchanged at
gated 4.08. Escalated `LOOP_QA.md` Q10; no code change (parking Tier B for a unified pass).

THE FINDING. The 10e secondary-mission values were UPDATED between two decks: **Pariah Nexus (2024)**
(the project's namesake; the sim's current values approximate it plus some Leviathan-era values) and
**Chapter Approved 2025-26** (debuted Adepticon March 2025, the CURRENT tournament standard for all
competitive play since). **The May-2026 Warp Friends calibration target was played under Chapter
Approved 2025-26, not Pariah Nexus 2024** — so the canonical secondary values for matching that data
are arguably the CA-2025-26 ones, but the sim AND the landed Tier A board secondaries (wave 83) were
built from Pariah-Nexus-2024 values. Confirmed deltas (≥2 sources each — Goonhammer Pariah Nexus review
+ Goonhammer Chapter-Approved-2025 review + Bell of Lost Souls):
- Cull the Horde: PN 20+ models / 25+ wounds → CA-2025 **13+ models incl. attached**, both 5 VP (sim: 10+ models, 3 VP — wrong vs both).
- Engage on All Fronts: PN 2/4 @ 3q/4q (no 2q tier) → CA-2025 **1/2/4 @ 2q/3q/4q** (sim: 2/3/5 @ 2/3/4, Leviathan-ish).
- Assassination: PN 4 VP/character → CA-2025 **4 VP (4+ wound char) / 3 VP (<4 wound)** (sim: 3 VP/char cap 4).
- Bring It Down / No Prisoners / Behind Enemy Lines: identical in BOTH decks (BID 2+2+2 max 6; No Prisoners 2+1×units max 5; BEL 3/4) — the sim's flat values are wrong vs both (deck-independent).

WHY ESCALATED, NOT FIXED. Which deck is canonical is a genuine project-scope call: it touches the
landed Tier A and the project's Pariah-Nexus identity, and the calibration data is CA-2025-26. The
sim's current values are a stale Leviathan/Pariah-Nexus mix with per-card wording subtleties, so a
single UNIFIED deck-aligned re-alignment after the ruling is cleaner and lower-risk than piecemeal
edits (and avoids another edition error of the wave-84/85 kind). Recommended (a) align to CA-2025-26;
parked Tier B pending the user's deck ruling. Finding recorded `project-mission-deck-ca-2025`.

## Wave 85 close (2026-06-01) — Knights damaged-OC bracket RE-ADDED as a real rule (gated 4.17 → 4.08); the wave-84 "fabrication" verdict was itself wrong

Branch `claude/sim-calibration-6`. The wave-84 conclusion that the damaged-Objective-Control bracket
was fabricated was REVERSED by the user/watchdog (commits f72a100 / 6135a62 / 6dcccbc): it is a REAL
10e datasheet rule and was re-added this wave, properly sourced and cited. Headline gated 4.17 → 4.08.

THE CORRECTION CHAIN. Wave 84 removed `_effective_oc` after a flawed read suggested Objective Control
does not change on the damage bracket. That read was wrong — both the worker's AND the watchdog's
"BSData shows constant OC" greps hit the wrong lines and never read the damage-table rows. This wave I
extracted the rows CLEANLY from the canonical BSData cache (the proper way): a Questoris Knight carries
"While this model has 1-9 wounds remaining, subtract 5 from this model's Objective Control characteristic
..."; an Armiger / War Dog "1-5 wounds remaining, subtract 3 ..."; Dominus chassis "1-10, subtract 5".
So the rule is real and my original −5/−3 values were correct. (The goal-doc directive expected a codex
−4 for the Questoris; RESOLVED by the watchdog to use the canonical cache −5 — BSData rule-6 governs;
the −4 was an unreliable web summary. ±1 is metric-negligible.) Lesson: `feedback-verify-stats-against-bsdata`
— cross-check ≥2 sources and actually READ the rows before declaring a cited rule fabricated OR building
one; 40k.app serves INDEX data, not codex.

RE-ADDED: `Battle._effective_oc` — Knights-faction-gated (correct: only Knights have this datasheet
rule), reduces a chipped Knight's Objective Control (Armiger −3 at ≤5 wounds, Questoris −5 at ≤9,
Dominus −5 at ≤10), floored at 0, applied in `_oc_within` and `_assign_army_oc`. Env-gated SWEG_DMGOC
(default ON). Cited `simulator.damaged_objective_control_bracket` with the verbatim BSData text (audit
288/288).

| Eval (N=40) | MAE_gated | in band | Imperial Knights | note |
|---|---:|---:|---:|---|
| DMGOC OFF (=0) | 4.17 | 9/22 | +29.2 | identical to wave-83 baseline |
| **DMGOC ON** | **4.08** | 8/22 | **+27.2** | −0.09 headline; IK −2.0 |

Marginal net-positive (a chipped Knight loses Objective Control → easier to contest off a marker), but
small because Knights are durable and rarely enter the bracket while still contested. Chaos Knights
worsen (−1.1 → −4.3) — they ALSO lose Objective Control when damaged, the real rule applied even-handedly
(NOT gated to help the metric). KEPT because it is real (the directive: "keep it because it is real,
regardless"), and it is also net-positive. 926 tests pass; run.py clean. The leftover Imperial Knights
+27.2 re-confirms the wave-84 positioning finding (`project-oc-contest-faithful`): even with the faithful
Objective-Control bracket, the Knight over-controls because body armies do not mass bodies onto markers.
Next: Tier B (kill-card formula corrections), then Tier C / clean under-shooter fixes.

## Wave 84 close (2026-06-01) — objective-control contest verified FAITHFUL; IK over-control is body-army positioning (no code change)

> **PARTIALLY SUPERSEDED by wave 85 (above):** the "damaged-OC bracket is fabricated" conclusion in
> this wave was WRONG — it is a real 10e rule, re-added in wave 85. The summed-OC-contest-is-faithful
> finding below still stands.

Branch `claude/sim-calibration-6`. Investigated the re-aimed Imperial Knights lever (Q8:
objective-takeability / the objective-control contest). A mid-wave MISSTEP and the watchdog
correction are part of this record. Headline unchanged at gated 4.17.

THE MISSTEP (caught + corrected). Mid-wave I built `Battle._effective_oc` — a "damaged Knight
loses Objective Control" rule (Armiger −3 at ≤5 wounds, Questoris −5 at ≤9), gated on the Knight
factions, on the strength of a 40k.app datasheet reading. **This was a fabrication / metric-tuning**
(a faction-gated penalty on the #1 over-shooter, moving the metric the convenient way) and the
watchdog caught it (commit 9f599c0). In real 10e, Objective Control does NOT change on the damage
bracket — BSData (canonical) shows Knight Paladin Objective Control 10 / Armiger 6 in EVERY profile;
the Knights' "Damaged: 1-9 Wounds Remaining" ability grants Lethal Hits / Lance / re-rolls / +1 to
Hit (a damaged Knight gets MORE dangerous, unchanged Objective Control). Reverted entirely (not even
gated-off, no citation). Lesson recorded: `feedback-verify-stats-against-bsdata` — verify stat/rule
claims against BSData before building, and treat "faction-gated AND conveniently moves a residual"
as a hard stop for self-review.

THE FAITHFUL DIAGNOSTIC (the real deliverable). Drilled the summed-Objective-Control contest in
Imperial Knights vs body armies (Astra Militarum, Tyranids), comparing the credited `a_oc`/`b_oc`
(the one-objective-per-squad `_assign_army_oc`) to the RAW summed Objective Control of every alive
model within 3" (the real 10e per-model rule). **Result: credited == raw in every case — the
contest is FAITHFUL.** Each model within 3" contributes its Objective Control; the
one-objective-per-squad modelling does not under-count the body army; a body army that gets bodies
onto a marker DOES out-control a Knight (Tyranids took a marker raw 15 vs the Knight's 6).

THE FINDING (per the watchdog's "if the contest is faithful, report it" branch). The Knight
over-controls because body armies have huge TOTAL Objective Control (Astra ~77 / 49 units,
Tyranids ~159 / 111) but get almost NONE onto the markers (on-marker Objective Control 0–15, often
0 in round 2) while each Knight parks concentrated Objective Control 10 on a marker. The residual is
the body army not MASSING bodies onto objectives — a positioning / one-Unit-per-model representation
gap, NOT an Objective-Control-math bug, NOT a Knight penalty. This is the AI-positioning class that
has historically regressed/washed (wave-81 contest/deny), so it is REPORTED, not chased blindly.
`LOOP_QA.md` Q9; memories `project-oc-contest-faithful`, `project-oc-does-not-bracket`. The scoring
overhaul (wave 83) already cut the headline to 4.17; the leftover IK spike is this positional core.

## Wave 83 close (2026-06-01) — Tier A board-control secondaries BUILT + LANDED (gated 4.95 → 4.17, in-band 6 → 9); sharpens the Imperial Knights finding to objective-over-control

Branch `claude/sim-calibration-6`. First BUILD wave of the scoring-model overhaul (plan Tier A;
watchdog Q7 approved). Added the five real Pariah Nexus objective-holding / board-control
secondaries the sim was missing. Validated as a clear fidelity win and LANDED ON (default-on,
`SWEG_TIER_A=0` to re-gate). Biggest single-wave headline move in a while.

BUILT: `Battle._score_board_secondaries` + `_score_area_denial` + zone helpers (`_obj_in_own_dz`,
`_obj_in_nml`, `_objective_controllers`) + a round-start objective-controller snapshot (for Storm
Hostile Objective). Five cards, scored per the verbatim real text, control = strictly-greater
Objective Control (same test as Cleanse): **Secure No Man's Land** (2/5), **Defend Stronghold**
(3), **Extend Battle Lines** (5), **Storm Hostile Objective** (4 — take an objective the opponent
held), **Area Denial** (2/5 centre). Every army brings the whole package (identical pool + scoring
both sides — even-handed; the asymmetry is purely in COMPLETION), bounded by the existing 40-VP
secondary cap and each card's natural ≤20-VP/game ceiling (the real per-Fixed-mission 20-cap,
honoured by construction). Five citations added to `secondaries_pariah_nexus.json` (audit 288/288).

| Eval (N=40) | MAE_gated | in band | Imperial Knights | note |
|---|---:|---:|---:|---|
| Tier A OFF | 4.95 | 6/22 | +19.1 | baseline (identical to wave 82 — inert keys don't perturb) |
| **Tier A ON** | **4.17** | **9/22** | **+29.2** | **−0.78 headline; IK WORSE** |

Most over-shooters eased hard (Drukhari +18.6 → +9.7, Custodes +7.4 → +2.7, Adepta Sororitas
+8.4 → +2.8, T'au +5.9 → +0.6, World Eaters +7.9 → +1.8, Emperor's Children +5.7 → +2.2) and the
board-control under-shooters rose (Chaos Space Marines −19.2 → −11.3, Chaos Knights −12.3 → −1.1
into band). A few under-shooters worsened (Chaos Daemons −18.3 → −22.2, Necrons, Adeptus Mechanicus,
Genestealer Cults) — they lose the board so their opponents bank the new board VP; their own
positional/AI weakness is a separate diagnosis.

THE SHARPENED IK FINDING (watchdog Q7 pre-authorised this exact scenario — "if Tier A doesn't move
campers, report it as a primary-economy / model-count finding; don't nerf"). Tier A made Imperial
Knights WORSE (+19.1 → +29.2). Mechanism, proven by the delta itself: the only thing Tier A adds is
objective-CONTROL-based scoring, and IK's win rate jumped +10 the moment it was added — so IK
out-controls objectives relative to its opponents and banks the new board secondaries ITSELF. The
IK residual is therefore **objective-OVER-CONTROL** (a durable, high-Objective-Control 9-to-13-unit
army holds the board uncontested — consistent with the wave-81 finding that opponents cannot contest
it off), NOT missing scoring paths. The next IK lever re-aims at objective-takeability / the
Objective-Control contest (does a body army correctly out-Objective-Control a Knight on a shared
marker?), a model-count/representation question — NOT more scoring and NOT a nerf. Tier A kept (clear
faithful aggregate win); IK finding reported to the watchdog (`LOOP_QA.md` Q8). 926 tests pass.

## Wave 82 close (2026-06-01) — scoring / victory-point model overhaul SCOPED (user Q6 ruling); plan wave, no code change

Branch `claude/sim-calibration-6`. First wave of the user-authorised scoring-model phase (Q6
RESOLVED: build the scoring/victory-point overhaul, diagnose-don't-nerf, plan-first). A
diagnosis+plan wave (mirroring wave 73→74 and 78), because the scoring layer is the sharpest
metric-tuning surface in the project and warrants a scoped plan before any code. Headline
unchanged at gated 4.95.

DELIVERABLE: `docs/SCORING_MODEL_OVERHAUL_PLAN.md`. Mapped the current scoring model from the
code (verified): primary is faithful (5/objective, 15/round cap, rounds 2–5, strictly-greater
control); the GAP is the SECONDARY economy — the sim models only 4 tactical secondaries (Engage,
Behind Enemy Lines, Cleanse, Sabotage) of the real ~12-card pool. THE KEY FINDING: the missing
cards are exactly the OBJECTIVE-HOLDING / BOARD-CONTROL family (Storm Hostile Objective, Secure
No Man's Land, Area Denial, Defend Stronghold, Extend Battle Lines, Overwhelming Force) — the
scoring paths a body army uses to out-score a durable camper, which a 9-model Imperial Knights
army physically cannot complete as well. This ALSO explains why wave-81 contest/deny failed:
taking a Knight's objective only denied 5 primary in the sim, but in real play also SCORES 4
(Storm Hostile Objective) — the reward for the anti-camper play was missing from the model.
Real card text sourced + verified against wahapedia pariah-nexus-battles (cross-checked vs the
Goonhammer review); each card a build wave implements gets a verbatim `rule_citations.d` entry.

BUILD SEQUENCE (env-gated, per-matchup Imperial Knights cells + per-faction + headline
before/after, citation before commit): wave 83 = Tier A (add the take-and-hold secondaries +
per-Fixed 20-cap — the targeted lever the ruling named first); wave 84 = Tier B (formula
corrections to the 4 modelled cards — Engage/Behind-Enemy-Lines/Bring-It-Down/No-Prisoners/Cull/
Assassination, correctness, direction mixed); wave 85 = Tier C (primary-economy correctness:
sticky control on ties at any control level — flagged as RAISING Imperial Knights, so isolated +
implemented because-it-is-the-real-rule, never for direction). Hard rails restated in the plan:
cited, even-handed, no per-faction weights, would-it-be-correct-if-it-moved-the-metric-wrong.

## Wave 81 close (2026-06-01) — contest/deny built + tested + REVERTED; the LAST faithful AI lever for Imperial Knights fails → escalated the structural scoring-residual finding (no net code change)

Branch `claude/sim-calibration-6`. Built redesign step #2 (contest/deny positioning) of the
faithful AI track per `docs/MATCHUP_FIDELITY_ANALYSIS.md` and the watchdog's Q5 confirmation.
It barely moved the #1 residual and regressed the headline — the diagnosis-predicted failure.
Reverted. Headline unchanged at gated 4.95. The finding is the deliverable and is escalated.

THE TEST (env-gated `SWEG_CONTEST`). A cheap chaff unit not on an objective moves to CONTEST
the nearest reachable enemy-CONTROLLED objective (deny the durable camper its primary VP),
prioritised over the AI-9 sacrificial enemy-DZ run. Naturally asymmetric: Imperial Knights
carry no chaff, so only their victims gain the contest. N=40 A/B vs baseline 4.95:
- gated **4.95 → 5.14 (REGRESSED +0.19)**; in-band 6/22 → 5/22.
- **Imperial Knights +19.1 → +18.2 (only −0.9; still grossly over-rated at +18.2).**
- The other over-shooters got WORSE: Drukhari +18.6 → +20.6, Votann +13.4 → +14.9, Orks +1.3.

THE FINDING (escalation-grade, `LOOP_QA.md` Q6). Contest/deny was the last faithful AI lever
the diagnosis pointed at for Imperial Knights, and it FAILED. This is the THIRD confirmation
(after wave-72 value-targeting, wave-79 focus fire) of one structural law: **every generic,
faithful AI improvement helps whoever has the better army; the over-shooters HAVE the better
armies; so sharper play WIDENS the headline** (memory `project-ai-frozen-under-mae-first`).
Mechanism for IK: opponents do contest, but a Knight is durable enough to hold/retake, so its
durability converts to held primary VP — the sim's kill-centric scoring under-models how real
tournaments deny primary through the full secondary economy + board tempo. **Imperial Knights
(and the durable over-shooters generally) is a structural VP-vs-durability SCORING residual,
not AI-fixable.** Per the watchdog's Q5 ruling: reported, not nerfed; escalated to the user as
a mission call (Q6: (a) build the scoring/VP-model lever — the real root cause; (b) bank ~4.95
and declare substantial convergence; (c) keep small clean UNDER-shooter fixes meanwhile). My
non-blocking default: (c) now + recommend (a). 926 tests / audit 294/294 expected green
(no net code change — revert restored `code/strategy.py` to baseline).

## Wave 80 close (2026-05-31) — IK Armiger re-fit tested + REVERTED; the AI+re-fit shooting/list routes fail for Imperial Knights (no net code change)

Branch `claude/sim-calibration-6`. Ran the user's AI+re-fit hypothesis on the #1 residual
(Imperial Knights): the faithful list-realism re-fit toward the real Armiger-heavy
tournament-winning list, alone and paired with the wave-79 focus fire. BOTH regress; IK
climbs. Reverted. Headline unchanged at gated 4.95. The finding is the deliverable.

THE TEST. Re-fit the IK archetype from big-Knight-heavy to the real Armiger-heavy list (6
Helverin / 6 Warglaive / Moirax / Canis Rex anchor — the proven competitive shape per the
Goonhammer / Sprues & Brews 2025 reviews). The builder produced a correct ~13-Armiger,
~1970pt list.
- Re-fit ALONE (focus fire off): gated 4.95 → **5.66** — IK UP. The efficient Armigers
  over-perform MORE in the sim (their real-world fragility tax is not modelled).
- Re-fit PAIRED with focus fire: gated **5.90**, **Imperial Knights +39.5 / 88%** — the
  fragile Armigers get focus-removed but they are cheap and many, and both lists' offence
  sharpens. Worst IK result yet.

DIAGNOSIS (firm now): the Imperial Knights over-rate is NOT the list — both the big-Knight
and the Armiger shapes over-perform in the sim (the Armiger one more). It is not the stats
(T11/W26 already current), not the rules (verified 71-72), and not the shooting AI (a Knight
cannot be shot off, so better targeting only sharpens IK's OWN offence — confirmed a 3rd
time). The over-rate is the **objective-HOLDING**: the sim over-rates a durable camper
because opponents do not **deny its primary VP**. Reverted the re-fit (both shapes are
realistic, so the regressing swap is not a clear fidelity win). The remaining faithful lever
is **contest/deny positioning (step #2)** — opponents sacrifice cheap bodies onto the
objectives IK is NOT on / contested ones to deny its primary VP, the real way Knights are
beaten. Logged `LOOP_QA.md` Q5; building step #2 next, env-gated, drilling IK's objective
holding before/after. If it too fails, IK is a structural scoring residual (VP-vs-durability),
not AI-fixable — and that is the finding to report.

## Wave 79 close (2026-05-31) — army focus fire built + tested (env-gated, regresses solo); diagnosis → Armiger re-fit + contest/deny next

Branch `claude/sim-calibration-6`. Built redesign step #1 of the faithful AI track (army-level
focus fire) per `docs/MATCHUP_FIDELITY_ANALYSIS.md`. It regresses solo, exactly the
accept-regression-then-re-fit scenario the user described. Committed env-gated OFF — baseline
gated 4.95 unchanged.

BUILT (env-gated `SWEG_FOCUS`): `Battle._nominate_focus_target` + a `_do_shoot` override. The
army nominates the most valuable durable enemy threat it can hurt (Knight/Monster/Vehicle or
8+ wound model, preferring one on an objective), and its ANTI-ARMOUR weapons only
(`_is_antiarmour_weapon`: damage≥3 / AP≤-2 / Anti-MONSTER-VEHICLE-TITANIC) concentrate on it —
weapon-target matched, so bolters keep clearing chaff. Smoke-confirmed: Chaos Space Marines
focus-fire the Knight Castellan and win a matchup they normally lose 0%.

| Eval | MAE_gated | note |
|---|---:|---|
| Wave 78 baseline | 4.95 | focus fire OFF |
| Focus fire ON (A/B) | **5.41** | regressed +0.46 |

Per-faction: Drukhari +18.6 → +14.2 (HELPED, −4.4 — its fragile Ravagers/Talos get
focus-removed) but Imperial Knights +19.1 → +25.9 (WORSE, +6.8), GSC −5.4 → −15.9, T'au up.

DIAGNOSIS (the user's diagnose-the-over-shoot step): focus fire is the right tool for FRAGILE
high-value threats (Drukhari) but WRONG for the durable Imperial Knights — a Knight cannot be
shot off (T11/W26/5++), so the victims' fire is wasted while IK's own anti-armour sharpens on
the opponents' vehicles/dreadnoughts. Third confirmation (after wave-72 value-targeting) that
better SHOOTING AI sharpens the durable over-shooters. The faithful next steps the regression
exposes: (1) **IK list-realism re-fit** — the sim's big-Knight archetype is OVER-GUNNED vs the
real Armiger-heavy tournament list; rebuild it toward the real list (Armigers are T9/W14, so
focus fire would REMOVE them → IK down). Test: Armiger re-fit PAIRED with focus fire. (2)
**Contest/deny (#2)** — the real IK lever is denying its primary VP (contest the objectives it
is not on; body it off), not killing the Knight. 926 tests pass; audit 294/294. Focus fire
committed env-gated OFF, pending those.

