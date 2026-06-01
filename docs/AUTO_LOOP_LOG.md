# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

