# SwegHammer calibration — current state

**Last updated:** Wave 116 (2026-06-02) — DOUBLE CORRECTION to the diagnostic arc. (1) The eval ALREADY runs
vanilla IGOUGO per-player turns (verified: 0 alternating calls), NOT the alternating model — so (iii) was never
a "foundational un-interleaving" the user must authorise; the IGOUGO machinery exists. (2) Built the REAL
per-Command-phase primary scoring (gated `SWEG_CMDSCORE`, default-OFF, `_score_objectives(only_for=...)` inside
the IGOUGO loop, cited): **clean N=40 A/B is NET-NEUTRAL (OFF 4.41 == baseline, ON 4.41)** — it redistributes
(helps static holders Grey Knights/Astra, brings over-shooters Sororitas/Orks/Tyranids down, but HURTS mobile
takers Chaos Daemons −14.6 → −20.8) and **does NOT fix Imperial Knights (+26.5 → +27.3): the durable Knight
tightens its primary margin but still WINS, so its win rate is robust to the timing.** **REFUTES "scoring-timing
is the IK lever" — the IK over-shoot is a one-Unit-per-model durable-concentrated-holder REPRESENTATION limit,
not a timing artifact; the user does NOT need to authorise a foundational (iii) change.** `SWEG_CMDSCORE` kept
gated default-OFF (faithful real timing, net-neutral, +1 band). The faithful sim levers (timing, positional AI,
combat) are now ALL exhausted/net-neutral on the convergent residual — the genuine structural floor. Suite green
(1001). `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`, LOOP_QA wave-116.

**Wave 115** — CONVERGENCE UNIVERSALLY CONFIRMED: batch-checked the 8 remaining
out-of-band factions; across ALL 14 diagnosed factions the primary-VP delta tracks the win rate one-to-one
(Leagues of Votann +13.8 / Sororitas +11.1 over-hold and over-shoot; Astra Militarum / Grey Knights / AdMech
−2.7/−3.0 under-hold and under-shoot; tabling negligible, secondary a capped wash everywhere). **The whole
per-faction residual is ONE axis — primary board-control — and the single faithful lever is the user-gated (iii)
un-interleaving. The headline is genuinely blocked on the user's (iii) decision.** `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`.

**Wave 114** — CONVERGENCE: diagnosed Necrons + spot-checked CSM / World Eaters /
Thousand Sons; the WHOLE per-faction residual reduces to ONE axis — primary board-control / mission fidelity.
ALL never tabled, secondary always a 40-cap wash, primary the whole differential. Durable elites OVER-hold
(Imperial Knights +27, Thousand Sons +9); mobile-melee + out-massed holders UNDER-hold (Daemons, World Eaters,
Necrons −13.9, CSM −9). **No separable faction-specific mechanic anywhere — the user-gated (iii) un-interleaving
is the dominant remaining lever for the whole board, and the loop is genuinely blocked on the user's (iii)
decision.** Secondary contributing factor (noted, not pursued): every army maxes the 40 secondary cap, erasing
the secondary differentiator. Writeup `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`. Live baseline ~4.41. LOOP_QA
wave-114. Prior wave 113 detail follows.

**Wave 113** — over-arming sweep (watchdog hygiene): audited the 27 secondary-blanking
overrides; the prior MUTEX-SWEEP handled the genuine choices, ONE genuine under-arming found + fixed — the
Adeptus Mechanicus **Skorpius Disintegrator** had its real fixed Disruptor missile launcher (S9 AP-2 D3.5 A3
twin-linked) wrongly dropped for a blanket convention; RESTORED it (cited, Belleros main-cannon mutex kept
suppressed). Non-gated N=40 A/B: **gated 4.48 → 4.41; Adeptus Mechanicus −11.3 → −9.9 (+1.4, right direction);
IK/Daemons unchanged** — a rare NON-frozen-under win (a one-sided fidelity correction arming an under-shooter).
Live baseline now ~4.41. Full suite green (997). **The headline lever remains the user-gated (iii) un-interleaving
(both IK +27 and Daemons −14.7 depend on it — see wave 112).** Prior wave 112 detail follows.

**Wave 112** — DIAGNOSED the Chaos Daemons −14.7 under-shoot as the SAME primary
board-control residual as the Imperial Knights +27 (inverted), unifying the two biggest residuals → strengthens
the user-escalated (iii) un-interleaving fix (see the "Wave 112" section below). Prior wave 111 detail follows.

**Wave 111** — entering-round primary scoring (option ii, watchdog-approved, gated
`SWEG_ENTERSCORE` default-OFF): score Primary on control ENTERING each of rounds 2-5 (before that round's
combat) vs the baseline end-of-round-after-combat snapshot — a faithful approximation of 10e per-Command-phase
scoring, even-handed, cited `simulator.primary_vp_entering_round`. **Clean N=40 A/B REFUTES it as the IK lever:
OFF gated 4.48 == baseline (zero drift); ON 4.61 (+0.13, ~neutral) but Imperial Knights +26.6 → +27.5 (it
RAISED the Knight), Chaos Daemons −14.7 → −24.3 (COLLAPSED).** Pattern: entering-round scoring favours STATIC
HOLDERS (gunlines that hold entering the round — Astra Militarum −6.3 → −0.2, AdMech −11.3 → −5.6, Necrons
−13.9 → −11.4 all improved) and punishes MOBILE TAKERS (melee armies that charge onto markers DURING the round,
esp. their round-5 charges which entering-scoring drops). A single-snapshot timing fix in the
alternating-activation model is fundamentally biased — it collapses 10e's TWO per-player-Command-phase scorings
into one. **The clean fix REQUIRES (iii) un-interleaving to real per-player turns — FOUNDATIONAL + USER-ESCALATED
(do NOT build without the user's go); the (ii) experiment strengthens the case for it.** Kept `SWEG_ENTERSCORE`
gated default-OFF (live baseline 4.48 holds), not flipped. Full suite green (997), audit clean. LOOP_QA wave-111.

### Wave 112 — Chaos Daemons −14.7 under-shoot DIAGNOSED: it is the SAME residual as IK +27 (unified)

Per the watchdog steer, instrumented Daemons vs 8 opponents (200 games, `scripts/diag_daemons_wave112.py`;
writeup `docs/DAEMONS_UNDERSHOOT_DIAGNOSIS_2026-06-02.md`). Daemons are tabled 0x, keep 35-58% of units, all
games go 5 rounds → NOT a survival/arrival issue. The loss is PRIMARY VP (27-36 vs opponents' 30-41); secondary
a 40-cap wash. Only **22% of alive Daemon units are within 3" of a marker** (the deep-strike melee army fights
instead of holding; on-marker OC contest ~even). **The Daemons −14.7 and the IK +27 are the SAME primary
board-control / mission-fidelity gap, inverted — this unifies the two biggest residuals and strengthens the
user-escalated (iii) un-interleaving fix, which would address both at once.** No separable buildable-now
Daemon-only lever; did not touch Daemons stats. Live baseline holds at 4.48 (no code change). LOOP_QA wave-112.

### Earlier — wave 109-110: the VP-fidelity diagnostic that led here

VP-FIDELITY DIAGNOSTIC (user ruling: the re-fit path is KILLED; the
+27 is a SIM-FIDELITY gap in how the game is WON — tournaments use the SAME stats, so a win-rate gap cannot be
the stats). Instrumented IK vs 7 broad armies (`scripts/diag_ik_vp_wave109.py`; writeup
`docs/IK_VP_FIDELITY_DIAGNOSIS_2026-06-02.md`). FINDINGS: (1) **the Knight wins on VICTORY POINTS, NOT
combat/tabling** — it tables the opponent 0-2/25, never gets tabled, all games go 5 rounds, the broad army
keeps 25-37% of its units. (2) **The differential is PRIMARY VP (IK ~44 vs opp ~30, +14); secondary is a
40-cap WASH** (both blow past 40; Cleanse/Sabotage already live — not the lever). (3) **The Knight's primary
lead COMPOUNDS R2→R5 (+3.3 → +6.0); the broad army's board control COLLAPSES under attrition (8.4 → 5.9)** —
the one-Unit-per-model "elite combat over-rated / model-count board control under-rated" gap. Candidate fixes:
positional AI WASHED (`SWEG_MASS`); secondary is faithful; the **command-phase primary-scoring timing** fix is
BLOCKED by the alternating-activation round model (no per-player Command phases). Surfaced a build-direction
FORK to the watchdog (LOOP_QA wave-109): score primary on PEAK in-round control / start-of-round control /
authorise structural un-interleaving — the scoring surface, so plan-first + watchdog steer before building.
**This supersedes the "re-calibration is the next step" framing — the headline lever is now the PRIMARY
board-control fidelity fix, NOT a stat re-fit.** Live baseline holds at 4.48 (no code change this wave).
**Wave 110 follow-up CONFIRMED the premise:** of the markers the broad army controls ENTERING a round, 52%
(150/288 over 48 games) are STRIPPED by that round's combat before the end-of-round score — so the broad army
floods + controls markers but its bodies are killed in-round and it scores nothing, while the durable Knight
holds through combat. The end-of-round-after-all-combat single snapshot is the unfaithful mechanic; the lead
fix is option (ii) score primary on START-of-round control (plan-first, env-gated, awaiting watchdog steer).

### Earlier — wave 108: Go To Ground core stratagem (gated `SWEG_GTG`) — 8th FROZEN-UNDER lever

A targeted INFANTRY unit may spend 1 Command Point for a 6+ invuln + Benefit of Cover until end of phase
(even-handed `_maybe_go_to_ground`; reuses `transient_invuln_4`; verbatim-cited `simulator.go_to_ground`).
Clean N=40 A/B: OFF gated 4.48 == baseline (zero drift); ON 4.56 (+0.08, NOISE) — metric-neutral. REFUTED the
"helps the fragile under-shooters" hypothesis (Chaos Daemons WORSE, −14.7 → −16.2 — an even-handed defensive
save buff helps shooty gunlines, not a melee aggressor). Kept gated default-OFF. Committed `52539c6`.

### Earlier — wave 107: anti-tank picker fix (watchdog Q18) — REFUTED as an IK lever (7th frozen-under)

Built the watchdog's Q18 anti-tank fix; the wave-106 diagnosis was wrong on two counts. (1) OVERRIDE-pinned,
not a systemic mapper bias — a past de-over-arming (`data/overrides.json` DRK-DIAG-5) kept the anti-infantry
Disintegrator and discarded the anti-tank Dark Lance on the Ravager/Raider. (2) The systemic mapper mix-scoring
(b) was BUILT then REVERTED (net-unfaithful: re-labelled 71 ranged + 48 melee picks, promoted one-shot
Hunter-killer missiles, demoted specialists). (3) The cited override fix (c)'s N=40 A/B REFUTED the
"first non-frozen-under IK lever" hypothesis: Imperial Knights +27.3 → +26.6 (noise), Drukhari +4.6 → +9.0
(the bad loadout was COMPENSATING for Drukhari over-tuning), gated 4.13 → 4.30. KEPT the Ravager → Dark Lance
pin (faithful — the list's named anti-tank platform; Ravager-only gated 4.48), REVERTED the Raider pin
(a transport, not an anti-tank platform). Committed `e76956a`. Memory `project-antitank-picker-bias`;
LOOP_QA Q18-OUTCOME (fork: keep the Ravager now vs bundle the Drukhari loadout correction with the
re-calibration — open).

### Earlier — wave 105 (Fire Overwatch + the STRUCTURAL FLOOR)

**Fire Overwatch (gated `SWEG_OVERWATCH`), and the session's STRUCTURAL FLOOR.** Fire Overwatch (out-of-phase shooting at chargers/reserves, hits on 6s, 1
Command Point) is faithful but REGRESSES at N=80 (OFF 3.52 → ON 3.69) — driven by Imperial Knights +27.0 →
+30.4 (its big guns overwatch effectively); frozen-under, kept gated, not flipped. **SIX simulator-side
levers now (terrain, per-model structure, per-weapon dice, focus-fire, deployment, Fire Overwatch) are ALL
faithful but FROZEN-UNDER — none moves the IK +27, most are washes/small regressions.** The simulator-AI
track is at its FLOOR for this residual: the IK +27 (~half the gated error) is a STATS problem, needing the
FAITHFUL RE-CALIBRATION (re-fit per-faction stats/lists to the now-much-more-faithful sim) or the SCORING /
victory-point model — BOTH user-gated. Per the watchdog guardrail, the loop is REPORTING the floor and
HOLDING for the user's re-calibration go (the remaining queue levers #4-6 are expected to be the same
frozen-under washes; not worth grinding before the re-calibration). All fidelity work committed + gated
(default-OFF); live baseline holds. **The high-leverage next step is the re-calibration — the user's call.**

### Earlier — wave 103-104 (deployment lever: net-positive at N=40 but a wash at N=80; the IK-drop was an artifact)

**Deployment/screening (gated `SWEG_DEPLOY`).** Refined (gunlines at the zone midline, screen forward) →
N=40 4.13 → 3.75 (helped gunline under-shooters), but **N=80 confirmed a WASH** (3.52 → 3.44, inside noise) →
NOT flipped,
kept gated as a faithful metric-neutral fix (gunline under-shooters slightly better, IK slightly worse, net
wash); revisit at the re-calibration. The IK +27 remains a
re-calibration / scoring problem (the user's morning go). 17 tests pass, audit clean.

### Earlier — wave 102 (crude deployment: regressed; the IK-drop was a buried-own-Knights artifact, refined in w103)

**Intelligent deployment + screening (gated `SWEG_DEPLOY`), watchdog #2.** Crude version put gunlines at the
board edge → regressed (4.13 → 4.67) and showed an apparent IK-drop that wave 103 proved was an artifact
(buried IK's own Knights). Refined in wave 103 (above).

### Earlier — wave 101 (focus-fire: headline +better / IK +worse, frozen-under #4)

**Army-level FOCUS-FIRE (gated `SWEG_FOCUSFIRE`), watchdog #1 IK lever.** Opponents killed 0.00 big
Knights/game (won't-crack penalty); focus-fire concentrates when the army can collectively crack a brick. N=40
4.13 → 3.85 (headline better) but IK +27.3 → +29.0 (worse, frozen-under). FOUR simulator-side levers (terrain,
per-model structure, per-weapon dice, focus-fire) all leave/worsen IK +27 → it needs the RE-CALIBRATION or
SCORING model. Kept gated (bundle into the re-calibration; ~2× eval perf cost noted).

### Earlier — wave 100 (per-model Stage 4: per-weapon dice; both halves of the Knight hypothesis refuted)

**Per-model loadouts STAGE 4 (per-weapon Damage-dice rolling, gated `SWEG_ROLLDMG`).** BOTH halves of the
Knight hypothesis REFUTED — neither the weapon over-count (Stage 3) nor the mean-damage overkill (Stage 4)
reduces the Imperial Knights over-rate.
N=80 three-cell A/B: OFF 3.52 → per-model-mean 3.79 → per-model+dice **4.17**; Imperial Knights +27.0 →
+28.3 → +28.8 (flat/worse throughout), the strong elite armies (Votann +7→+13, Chaos Knights +2→+7) got
WORSE (frozen-under), and dice variance hurt the low-model elites (Custodes −3.8→−6.1). The IK over-rate is
durability/objective-holding, **triangulated THREE ways** (terrain + per-model structure + per-weapon dice)
— nothing about a Knight's guns moves its win rate. The re-architecture is a genuine FIDELITY win (each
model fires its real weapons with real dice, special weapons lost on death) but REGRESSES the headline
3.52 → 4.17 because per-faction stats are tuned to the OLD averaged sim — the fidelity-first debt the
deferred re-calibration (Q13) absorbs. Committed + GATED (default OFF). The real IK lever remains durability
/ objective scoring, NOT firepower. NEXT (pending user): Stage 5 + the re-calibration, vs pivoting to the
durability lever.

### Earlier — wave 99 (per-model Stages 2-3: firing reads each model's weapons; over-count refuted as the IK lever)

**Stages 2-3 (gated `SWEG_PERMODEL`):** plumbed `model_loadouts` onto `UnitProfile` and made `add_squad`
build one Unit per model from the loadout (each fires its own weapons, lost on death; pistols in melee;
single-model units stop over-collecting). The over-count fix went live but did NOT move Imperial Knights
(+27 flat) — it helped the strong elite armies over-shoot more (frozen-under). Faithful, kept, gated.

**Wave 99 / Stages 2-3:** Stage 2 plumbed `model_loadouts` onto `UnitProfile` (gate-inert, 4.13 unchanged).
Stage 3 made `add_squad` build one `Unit` per model from the loadout (`SWEG_PERMODEL`); single-model units
now fire only their actually-equipped guns (the Stage-1 over-count fix goes live); weapon-loss-on-death and
pistols-in-melee fall out of the existing per-Unit machinery; cited `simulator.per_model_loadouts`.
**THE A/B refuted the hypothesis:** same-N comparisons regress slightly (N=40 4.13→4.24, N=80 3.52→3.79) but
within the gated-MAE sampling noise (the OFF baseline alone swings 4.13→3.52 across N). The reliable
cross-N signal is per-faction: per-model HELPS the strong elite armies over-shoot MORE (Leagues of Votann
+6, Chaos Knights +5) and leaves Imperial Knights FLAT (+27→+28). So the weapon over-count was real (Stage 1
fixed it, a fidelity win) but removing it does NOT cut the Knight win rate — TRIANGULATED TWICE (terrain +
per-model): **the IK over-rate is durability / objective-holding, not firepower.** Per-model is a faithful
upgrade (kept, gated) but the frozen-under pattern, not the Knight lever. METHODOLOGY: per-model widens
variance → use N≥80 for its A/Bs. Stage 4 (per-weapon dice = the mean-overkill half of the hypothesis) is
the untested remaining piece. 949 tests pass, audit clean, run.py OK both gate states.

### Earlier — wave 98 (per-model Stage 1: mapper preserves loadouts + dice; over-collection diagnosed/fixed in data)

**Wave 98 / Stage 1 (data only):** the mapper now preserves `model_loadouts` (per-model weapons + raw dice)
and single-model units use proper option-picking instead of a flat weapon-walk. Diagnostic: 523 of 907
single-model units were over-collecting weapons (the Wraithknight fired both alternative arm cannons). Data-
only, metric 4.13 unchanged; the correction went live at Stage 3 (and, per above, did not move Imperial
Knights). The regen also synced a stale `deadly_demise` field (metric-neutral, kept per rule 7).

### Earlier — wave 97 (terrain rebuilt to competitive density, gated 3.59 → 4.13, refuted as the IK lever)

**Wave 97 rebuilt all stock maps to competitive Pariah Nexus terrain density** (`_competitive_terrain`: ~11
line-of-sight-blocking ruins + scatter, ~19% area, 180-degree even-handed, no clean cross-table sightline;
cited). N=40 gated 3.59 → 4.13 (regressed), and REFUTED the hypothesis: Imperial Knights got WORSE (+25.9 →
+27.3) — realistic terrain shields the durable Knight from return fire more than it limits its shooting, and
helps melee close. KEPT per the prime directive (the May-2026 target was played on realistic terrain;
reverting to sparse would be metric-tuning). Terrain is NOT the IK lever; the over-hold is durability
(LOOP_QA Q14).

### Earlier — wave 96 (core-rules quick-fix batch, gated 3.76 → 3.59)

**Wave 96 ran the core-rules-audit quick-fix batch** as three parallel worktree streams. LANDED Stream D+E
(rules-correctness): single Benefit of Cover (stale −1-to-hit removed), current-10e Ruins/Woods line of
sight (TOWERING no longer sees through ruins), Benefit-of-Cover AP0/Save-3+ exception for all models, Fall
Back FLY exemption removed. Gated 3.76 → 3.59, driven by Imperial Knights +27.0 → +25.9 and Drukhari +6.4 →
+4.7. Plus Stream B1 (Counter-Offensive citation). HELD Stream A (AI Objective-Control fidelity — faithful
but frozen-under regression) on `held/stream-a-ai-oc-fidelity` (`452ce81`), to land at the re-calibration
(Q13). DEFERRED Stream B2 (Insane Bravery registered but inert; P2 build) and unblocked P1.5 roll-damage.

### Earlier — wave 95 (positional re-model Candidate B landed, gated 4.15 → 3.76)

**Wave 95 LANDED the Q11 positional re-model** (Candidate B): the move AI masses a unit holding no
objective AND out of its own firing range onto the best holdable objective (arrive-in-cover) — the faithful
"idle units play the objectives" tactic, the dominant sub-cause. Gated 4.15 → 3.76, in band 8 → 9, Chaos
Daemons −22.7 → −14.7; Imperial Knights unchanged (+27, the over-shooter half can't be shot off).
Default-ON (`SWEG_MASS=0` re-gates).

### Earlier — wave 94 (geometry candidate regressed, reverted)

**Wave 94** built the geometry/clustering candidate (a unit on an objective credits Objective Control over
a coherency-extended footprint) → REGRESSED 4.15 → 4.30 (frozen-under: helped already-holding over-shooters,
not the under-shooters who don't reach markers). Reverted; pointed to Candidate B, which landed wave 95.

### Earlier — wave 93 (Q11 positional re-model scoped)

**Wave 93 scoped the Q11 positional re-model** (`docs/POSITIONAL_REMODEL_PLAN.md`). A within-3"-vs-6"
drill pinned the body-army on-marker OC gap to geometry/spread (secondary) + AI-not-massing (dominant).
Plan = `docs/POSITIONAL_REMODEL_PLAN.md` (Candidate A geometry first, then B AI-massing).

### Earlier — wave 92 (CA-2025-26 deck re-alignment complete)

**Wave 92 completed the CA-2025-26 secondary re-alignment** (Bring It Down 2+2(15+W)+2(20+W) max 6;
Assassination 4(4+W)/3(<4), no Warlord bonus; via destroyed-unit wound data in the snapshot). Across both
parts the deck re-alignment moved the headline 4.08 → **4.15** (cap-wash, flat), kept as fidelity. 7
cards re-valued, 5 board cards confirmed unchanged.

### Earlier — wave 91 (CA-2025-26 re-alignment part 1, 5 cards, metric-flat)

**Wave 91 did CA-2025-26 re-alignment part 1** (5 cards: No Prisoners 3→2, Cull 10/3→13/5, Engage
2/3/5→1/2/4, Behind Enemy Lines flat-4→3/4, Extend 5→4), ≥2-CA-source-verified; metric-flat (4.08→4.10,
cap-wash). The user ruled Q10 = Chapter Approved 2025-26 + Q11 = (c) the positional re-model.

### Earlier — wave 90 (Daemons re-diagnosed positional; secondary cap-wash; structural floor)

**Wave 90 re-diagnosed Chaos Daemons** as POSITIONAL (they survive 40-75% but lose the primary race),
not combat/attrition; found secondary is a CAP-WASH (both sides max 40, primary decides); consolidated
the dominant residual as ONE axis (primary/objective control: IK +27 over, Daemons −22 under). Gated 4.08
identified as a structural floor on the faithful track → escalated as Q11 (ruled this wave).

### Earlier — wave 89 (over-shooter detachments swept clean; over-rates are structural)

**Wave 89 audited the over-shooter detachments for fabricated buffs** — BSData-verified NEGATIVE finding:
they are already clean (fabrications swept in prior waves), so the over-shooter over-rates are structural,
not fabricated buffs. Two minor deferred flags (Custodes crit-on-5+ edition-conflict; a zero-metric Agents
fix). No code change. Memory `project-detachment-fabrication-pattern`.

### Earlier — wave 88 (Daemonic Manifestation built, real but metric-neutral)

**Wave 88 built Daemonic Manifestation** (the missing friendly half of the Chaos Daemons Shadow of Chaos
army rule) — real, cited, faction-gated, default-on — but the N=40 A/B was metric-neutral (Daemons
−22.2 → −22.5). The wave-87 diagnosis over-attributed; the Daemons residual needs re-diagnosis.

### Earlier — wave 87 (diagnosed Chaos Daemons −22; build planned)

**Wave 87 diagnosed the largest residual, Chaos Daemons (−22.2)** to the missing Daemonic Manifestation
rule and planned the build — which wave 88 then built and found metric-neutral (see above), so the
diagnosis over-attributed and the Daemons residual remains open.

### Earlier — wave 86 (mission-deck fork escalated; Tier B parked)

**Wave 86: verifying Tier B's secondary-card values surfaced that the sim targets the wrong mission
deck** — Pariah Nexus 2024 (what the sim approximates) vs Chapter Approved 2025-26 (the current standard
the May-2026 calibration target used). Escalated as a project-scope fork (`LOOP_QA.md` Q10, memory
`project-mission-deck-ca-2025`); Tier B parked for a unified deck-aligned re-alignment after the ruling.

### Earlier — wave 85 (Knights damaged-objective-control bracket re-added, real, gated 4.17 → 4.08)

**Wave 85 re-added the Knights' damaged-objective-control bracket** after the user reversed the wave-84
removal — it is a REAL 10e datasheet rule (BSData verbatim: Questoris −5 at ≤9 wounds, Armiger −3 at
≤5), cited, Knights-faction-gated, floored at 0. Gated 4.17 → 4.08; Imperial Knights +29.2 → +27.2.
Leftover IK +27.2 is the positioning finding. Lesson: `feedback-verify-stats-against-bsdata`.

### Earlier — wave 84 (OC contest verified faithful; damaged-OC removal later reversed)

**Wave 84 verified the summed-objective-control contest is FAITHFUL** (credited == raw per-model within
3"); the Knight over-controls because body armies have huge total objective control but get almost none
onto markers — a positioning / one-Unit-per-model representation gap. (Wave 84 also REMOVED the
damaged-OC bracket on a flawed read; that was wrong and wave 85 re-added it.) Reported
`project-oc-contest-faithful`.

### Earlier — wave 83 (Tier A board-control secondaries built + landed)

**Wave 83 built + landed Tier A** (the five real Pariah Nexus objective-holding / board-control
secondaries). N=40: gated **4.95 → 4.17 (−0.78)**, in band **6 → 9** — a clear faithful aggregate
win. Most over-shooters eased (Drukhari +18.6 → +9.7, Custodes/Sororitas/T'au down); board-control
under-shooters rose (Chaos Space Marines −19.2 → −11.3, Chaos Knights into band). It made Imperial
Knights WORSE (+19.1 → +29.2) because a durable Knight over-controls objectives and banks the new
board secondaries itself — which is what wave 84 then diagnosed. Full result + the sharpened
finding: `docs/SCORING_MODEL_OVERHAUL_PLAN.md`.

### Earlier — wave 82 (scoring overhaul scoped)

**Wave 82 scoped the user-authorised scoring-model overhaul** (`LOOP_QA.md` Q6: build the
scoring/victory-point overhaul, diagnose-don't-nerf, plan-first). Deliverable
`docs/SCORING_MODEL_OVERHAUL_PLAN.md`: primary scoring is faithful; the gap was the SECONDARY
economy (only 4 of ~12 tactical secondaries modelled). Wave 83 built Tier A from this plan.

### Earlier — wave 81 (contest/deny tested + reverted; the AI track concluded)

**Wave 81 built + tested redesign step #2 (contest/deny positioning) and it failed — the
diagnosis-predicted outcome.** Env-gated `SWEG_CONTEST`: a cheap chaff unit not on an
objective moves to CONTEST the nearest reachable enemy-controlled objective, to deny the
durable camper (Imperial Knights) its primary VP (naturally asymmetric — IK carries no chaff).
N=40 A/B vs 4.95: gated **4.95 → 5.14 (REGRESSED +0.19)**, **Imperial Knights +19.1 → +18.2
(only −0.9, still grossly over-rated)**, while the OTHER over-shooters got worse (Drukhari
+18.6 → +20.6, Votann +13.4 → +14.9). Reverted. The structural law (3rd confirmation): every
generic faithful AI improvement helps whoever has the better army, and the over-shooters HAVE
the better armies, so sharper play WIDENS the headline. Imperial Knights is a structural
VP-vs-durability SCORING residual, not AI-fixable → escalated as Q6 → user chose the scoring
overhaul (see above).

### Earlier — wave 80 (IK Armiger re-fit tested + reverted)

**Wave 80 ran the user's AI+re-fit hypothesis on the #1 residual (Imperial Knights)
and it failed.** The faithful re-fit toward the real Armiger-heavy tournament list made
IK WORSE — alone (gated 4.95 → 5.66, the efficient Armigers over-perform more in the sim)
and paired with focus fire (5.90, IK +39.5 / 88%). Reverted. **Firm diagnosis:** the IK
over-rate is the objective-HOLDING (the sim over-rates a durable camper because opponents
do not DENY its primary VP) — NOT the list (both shapes over-perform), the stats (current),
the rules (verified), or the shooting AI (a Knight can't be shot off — better targeting
only sharpens IK's own offence, confirmed 3×).

### Earlier — wave 79 (army focus fire built + tested, env-gated, regresses solo)

**Wave 79 built redesign step #1 (army-level focus fire) of the faithful AI track.**
Env-gated `SWEG_FOCUS`: the army nominates the most valuable durable enemy threat it
can hurt and its anti-armour weapons concentrate on it. It regresses solo (4.95 →
5.41): it HELPS the fragile over-shooter Drukhari (+18.6 → +14.2, its Ravagers get
focus-removed) but WORSENS the durable Imperial Knights (+19.1 → +25.9 — a Knight
can't be shot off, so the victims' fire is wasted while IK's own anti-armour sharpens
on the opponents' vehicles). Third confirmation that better SHOOTING AI sharpens the
durable over-shooters. **Next (the user's AI+re-fit path):** (1) rebuild the IK
archetype toward the real Armiger-heavy tournament list (the sim's big-Knight list is
over-gunned; Armigers are fragile so focus fire would remove them → IK down) — test the
re-fit PAIRED with focus fire; (2) build step #2 contest/deny (the real IK lever — deny
its primary VP, don't kill the Knight). Committed env-gated OFF; baseline unchanged.
Full detail: `docs/MATCHUP_FIDELITY_ANALYSIS.md`.

### Earlier — wave 78 (matchup-fidelity diagnosis + faithful-AI plan)

**Wave 78 opened the user-chosen phase (Q4 ruling): the faithful target/positioning
AI track + matchup-fidelity diagnosis.** A diagnosis+plan wave. Drilling per-matchup
(not aggregate) shows the residuals are driven by impossible-in-real-play lopsided
cells: Imperial Knights beat CSM/AdMech/Marines **100%**, Drukhari beat
Tyranids/CSM/AdMech **90%**; CSM loses **0%** to Emperor's Children, Daemons **0%** to
AdMech/Drukhari/TSON. Compared to real May-2026 play, the gap is almost entirely
**bucket (a), the opponent AI** — it does not focus-fire the durable/key threat, contest
and deny the camper's objectives, or allocate units to actions sensibly. Stats/rules
verified faithful (Knight T11/W26 already reflects the Dec-2025 update); one list note
(real winning Knights list is Armiger-heavy — flagged, not pulled). Full diagnosis + the
faithful-AI redesign plan: `docs/MATCHUP_FIDELITY_ANALYSIS.md`. The AI build executes in
the next waves (env-gated A/B; when it exposes an over-shoot, diagnose the faithful cause
— re-fit toward real lists now permitted — never a nerf).

### Earlier — wave 77 (per-unit Advance, metric-neutral; clean levers exhausting)

**Wave 77 was a consolidation wave.** Rotation-gating the tactical secondaries was
tested and REJECTED (Sabotage-off is gated 5.15 vs 4.91 on — the over-scoring is
net-positive, so reducing it regresses). Landed the per-unit Advance roll (real 10e:
one Advance roll per unit, not per model — the same bug class as the wave-76 charge
fix), a faithful correctness fix that is metric-neutral: gated 4.91 → **4.95** (within
N=40 noise) but in-band 5 → 6. **The clean impactful faithful levers are now exhausted**
— the two biggest residuals (Imperial Knights +19.1 durable camper, Drukhari +18.6
fragile) both need the opponent target/positioning AI, which regressed when tried
(wave 72). The strategic fork — take the AI-redesign + re-fit (goal-doc-restricted) vs
bank Stage 1 at ~4.9 — is **escalated to the user** (`LOOP_QA.md` Q4). The watchdog
ruled: do NOT start the AI-redesign + re-fit until the user rules; keep taking small
clean faithful fixes meanwhile (next: the missing Be'lakor datasheet for Chaos Daemons).

### Earlier — wave 76 (per-squad charge roll, gated 5.11 → 4.91)

**Wave 76 landed the per-model activation tax the watchdog mandated — as a
concrete core-rule fix.** Verify-first found the mechanism the prior washes
missed: the per-model over-rate is NOT spread/coherency (hordes cluster), it is the
CHARGE phase — SwegHammer rolled 2D6 *per model*, so an 11-model mob got 11 charge
attempts (~97% to make a 9" charge vs the real ~28%). Real 10e: a unit makes ONE
charge roll. A codex squad now shares one roll per round. Gated 5.11 → **4.91**,
bringing down the melee over-shooters (Orks +10.3→+8.1, Votann +14.7→+12.4) and
pulling Grey Knights back toward band. It works *because it cuts the horde's
effective melee output* — the exact thing the decision-overlay wash could not reach.
A clear core-rule correctness fix. Collateral (re-fit territory): Drukhari / T'au /
Sororitas up (their melee opponents now charge less reliably).

### Earlier — wave 75 (Sabotage + 40-VP secondary cap, gated 5.35 → 5.11)

**Wave 75 extended the proven action-secondary lever (watchdog confirmed).** Two
faithful changes: the real **40-VP total-secondary cap** (the sim never enforced it;
secondary-heavy shapes like Custodes ran past it) and **Sabotage** (a chaff unit
pushed forward performs an action — 3 VP in No Man's Land, 6 in the enemy DZ — with
the shoot/charge lockout). Gated 5.35 → **5.11**, and it dents the #1 residual:
Imperial Knights +23.3 → +18.0 (opponents score forward actions it can't reciprocate);
Custodes, Tyranids, Astra, AdMech, Necrons, Marines all better. **Honest collateral:**
the low-model armies that can't reciprocate over-corrected (CSM −16.6, Chaos Knights
−12.9, Grey Knights −6.6) — faithful in DIRECTION (low-model armies do struggle with
the secondary game) but amplified because cleanse/sabotage aren't rotation-gated yet
(they over-score vs the real draw-1-2/turn cadence). Tempering = a LATER secondary
wave, not wave 76.

**WAVE 76 IS FIRMLY THE PER-MODEL DURABILITY / ACTIVATION TAX** (watchdog-directed,
`LOOP_QA.md` Q3) — the genuine root cause of Imperial Knights +18.0 (still #1) that the
secondaries only chip at. It must be a FAITHFUL mechanic (real action-economy /
objective-count / coherency effects), NOT a metric-driven penalty on low-model armies.
"One more bounded secondary" instead = shying away (the watchdog will flag it).

### Earlier — wave 74 (Cleanse action secondary, gated 5.89 → 5.35)

**Wave 74 built the wave-73 structural lever and it worked.** The
action-economy secondary **Cleanse** (a real Pariah Nexus secondary that was
missing) now counterbalances the kill-secondary asymmetry: a unit performs the
Cleanse action on a controlled objective OUTSIDE its own deployment zone and
cannot shoot/charge that turn (the real action-vs-fight tradeoff), scoring 2 VP
for one / 4 for two. The asymmetry is even-handed — it falls out of unit cost
(`_is_chaff_unit`, <15 pts/model surplus bodies): Imperial Knights (no chaff)
score 0; hordes / MSU and elites with cheap aux score it. Gated MAE 5.89 → **5.35**
with exactly the predicted moves — durable over-shooters ease down (Imperial
Knights +27.9 → +23.3, World Eaters +16.5 → +12.5) and board-control under-shooters
rise (Astra −15.5 → −10.6; AdMech / Daemons / Tyranids / Necrons toward band). Also
fixed the dead Cull the Horde mechanic. In-band dipped 6 → 5 (small margins). This
is a faithful structural fix that moves the metric the right way by being more
correct — the first real win after three small/investigation waves.

### Earlier — wave 73 (investigation: the over/under split is the kill-secondary asymmetry)

**Wave 73 (investigation, no code change, headline unchanged at gated 5.89).** The
user steered the loop off narrow nerf-grinding toward structural levers. Verify-first
overturned the named lever ("secondaries never read") — they ARE counted (added to
`_a_vp`/`_b_vp` since 2026-05-20; `_a_secondary_vp` is a redundant unread tracker; the
literal fix would double-count). The real over/under driver is the **kill-secondary
asymmetry**: durable killers score Bring It Down / No Prisoners / Assassinate against
victims who score ~0 back (a horde scores 0 No Prisoners vs IK — they can't destroy a
durable Knight AS A UNIT under per-model representation). The missing counterbalance is
the **action-economy secondary family** (the sim models NO actions; only 2 of 9
tacticals) — the faithful, even-handed fix that rewards board-control under-shooters
and taxes low-model campers with an action-vs-fight tradeoff. Evidence in
`docs/SECONDARY_SCORING_ANALYSIS.md`; build plan in `docs/ACTION_SECONDARIES_PLAN.md`.
**Wave 74 = build the Cleanse vertical slice per that plan** (+ fix the dead Cull the
Horde mechanic: `_is_horde_unit` reads `starting_strength`/None, should read `max_models`).
Worker questions now route to the gitignored `LOOP_QA.md` watchdog channel, not the user.

### Earlier — wave 72 (Ion Shield ranged-only, gated 5.97 → 5.89)

**Status:** Headline gated MAE **5.89** (raw 9.28), **6/22 in band**. Wave 72
landed a faithful Imperial Knight durability fix (Ion Shield is "5+ invulnerable
**against ranged attacks only**" per BSData — big Knights have no melee invuln; the
sim applied it flat). Imperial Knights +29.0 → +27.9; melee under-shooters edge up.
Modest but the one metric-positive faithful lever found this wave.

**The headline is now firmly AI/structure-gated — TWO findings nail this down.**
(1) The under-shooters lose on VICTORY POINTS WHILE STILL ALIVE (Chaos Daemons lose
6-9/10 with survivors on the board, 0-1 tabled) — so per-faction COMBAT buffs do not
address their loss; it is the same objective/durability complex as the Knights
over-rate, from the under side. (2) Improving the target AI REGRESSES the headline:
a faithful value-based shooting-target picker (anti-armour concentrates on durable
threats, real weapon-target matching) was A/B'd and made it WORSE (5.97 → 6.11, IK
+29 → +32.9) because better targeting sharpens the killy over-shooters' own offence
more than it helps their victims remove un-killable Knights. This is the SECOND AI
lever to regress this session (objgreedy was the first, wave 71), both confirming
`project-ai-frozen-under-mae-first`: AI improvements expose over-tuned over-shooter
stats/lists. **A target-AI redesign will not reduce the headline until the
over-shooters are re-fitted.**

### Earlier — wave 71 (Code Chivalric fidelity fix, gated 5.98 → 5.97)

Wave 71 fixed the one genuine fidelity defect behind the Imperial Knights over-rate
(Code Chivalric was re-rolling all natural 1s; the real rule is one re-roll per
activation) and **proved the rest of that over-rate is a compensating error, not a
rule defect** — Bold Gallantry, Bondsman, all Knight stats and the maps verified
faithful end to end.

**Code Chivalric** (Imperial Knights army rule) was re-rolling EVERY natural 1
army-wide; the real rule is "re-roll ONE Hit and ONE Wound roll" per activation.
Reroll-all-1s over-scales with shot volume (a 20-shot Knight gun got ~3-4
effective re-rolls vs the rule's one). Now a single per-activation re-roll budget
(`code/units.py` `_chiv_hit_reroll`/`_chiv_wound_reroll`), faithful to the
one-Unit-per-model representation. Metric-neutral (the rule existing is the swing,
not the over-scaling) but correct.

**The Imperial Knights +29 over-rate is NOT a rule/stat defect — it is a
compensating error in the opponents' AI.** Everything was verified faithful:
Bold Gallantry (real Valourstrike Lance detachment, ~21pt, correctly gated on
Advance, charge-after-advance correctly blocked), Bondsman/Paladin's Duty (real,
~2.4pt), all Knight stats (OC 10/6, T 11/12, W 26/28 — match BSData), and the
maps (5-objective Leviathan quincunx). IK wins by **VP/objective-holding, not
tabling**. The root cause: the shooting-target AI is a min-HP "finish the weakest"
picker, so opponents shoot the W14 Armigers and chaff first and **never
concentrate fire on a big W26 Knight** — durable Knights sit on objectives
untouched all game. Under-shooters holding objectives better (tested via an
objective-greedy AI tweak — a wash, reverted) doesn't help, because they can't
take objectives FROM the un-killed Knights.

### Earlier — wave 69 (under-performer faction buffs, gated 8.74 → 8.29)

Headline gated MAE was **8.29** (raw 11.57), in-band 5/22. Wave 69 = the
win-win under-performer track: a 6-faction rules deep-dive (5 under-performers + an
over-performer over-buff audit) → implement each under-performer's missing rules
(verify-first against Wahapedia/BSData). Landed (gated 8.74→8.29): **Imperial Knights
−21.8→−16.0** (real Valourstrike Lance detachment + Bold Gallantry + Bondsman
abilities), **Chaos Daemons −19.0→−14.6** (per-god datasheet buffs — Tzeentch 4++
correction, Murderer's Cowl, Penumbral Puppetry/Gloam Rot), plus TOWERING
line-of-sight (cross-faction), Chaos Knights real Iconoclast Fiefdom detachment, and
GSC Patriarch/Primus leaders + Aberrant FNP. All verify-first (the over-performer
audit's "phantom Aeldari invuln" claim was DEBUNKED — Dark Reapers really have a
5++; the Daemons agent correctly corrected only the genuine Tzeentch 4++).

CAUGHT + REVERTED: CSM Dark Pacts per-unit auto-gamble crashed CSM 45.8→24.8% (the
self-inflicted D3 mortal wounds on every squad every round outweigh the buff — real
players are selective; task #36). Chaos Knights barely moved from the detachment
alone — its −38 is dominated by the AI-positional gap (the durable-objective
diagnostic moved CK −38→−8.8), so CK needs the objective AI (#12), not just rules.

### Earlier — wave 68 (core-rules-correctness batch, gated 7.80 → 8.74)

Headline gated MAE was **8.74** (raw 12.05), in-band 5/22. Wave 68 was a
deliberate **fidelity-first** wave from the full 10e core-rules audit
(`docs/CORE_RULES_AUDIT.md`): removed the **Heroic Intervention fabrication** (not a
10e rule — was a free defensive move for every Character) and fixed five real bugs —
Fall Back no longer always rolls Desperate Escape (only when battle-shocked or
crossing enemies); Indirect Fire now applies its unmodified-1-3-auto-fail + Benefit
of Cover; in-engagement (Pistol/Big Guns) and Blast target restrictions; unmodified-6
always hits; disembark can't place within Engagement Range; battle-shocked units
fight first in Remaining Combats. 919 tests green (deleted the HI test file), audit
280/280.

The headline rose +0.94 (7.80 → 8.74) — expected: the fixes move factions away from
a calibration fitted on the old wrong rules. Concentrated on **Chaos Daemons
−13.7 → −19.0** (HI removal correctly weakened a Character-heavy melee army that the
fabrication propped up) and the shooty over-shooters **Aeldari/Sororitas** (Fall Back
fix lets them disengage and keep firing). The **archetype-list re-fit (task #22)** is
now the gating next step and must lift Daemons + Knights while trimming
Aeldari/Sororitas/Thousand Sons.

### Earlier — wave 67 (per-unit-mechanics batch, gated 7.56 → 7.80, in-band 3 → 5)

Headline gated MAE was **7.80** (raw 11.11), **in-band 5/22** (was 3/22).
Wave 67 landed all six top findings from the per-unit-mechanics audit in parallel
(one worktree agent each, cherry-picked to `ba2a8b4`): unit coherency (cluster
squads at deployment + objective control credited per unit), per-unit secondary
scoring (No Prisoners / Cull count destroyed units), Reanimation/Undying Legions
grouped by `squad_id`, stratagem transient buffs applied to the whole squad (60
sites), per-squad battleshock + Mob Rule by squad_id, and the once-per-unit gate
re-keys (Oath, Acts of Faith, Strands, Miracle die, Markerlight, Blood Surge,
Beacons). All rules-correct; 922 tests green; citation 281/281 (new
`simulator.unit_coherency`).

The gated headline rose +0.24 (7.56 → 7.80) even though in-band improved 3→5 and
big structural fixes landed (Necrons +4.2→−1.3 from reanimation; Drukhari
+30.1→+27.8 from coherency). The regression is one faction: **Adepta Sororitas
+10.1→+17.2** (gated 6.3→13.4) — stratagem-buff propagation + the Acts-of-Faith
squad re-key correctly made Sororitas stronger, past a list tuned around the old
bugs. This is the fidelity-then-refit pattern: the sim is now more correct, so the
**archetype-list re-fit (task #22)** is the immediate next step, Sororitas first.

### Earlier — wave 66 (mortal-wound spillover + Deadly Demise + Blast, gated 7.78→7.56)

Wave 66
landed the mortal-wound half of the allocation rule (`Battle._apply_mortal_wounds`:
excess mortal wounds carry to the next model of the unit, unlike normal damage),
fixed **Deadly Demise** to hit each *unit* once (was per-model), and scoped **Blast**
to the targeted unit via `squad_id`. Eval 7.78 → 7.56 (small, rules-correct).

A user question about per-model vs per-unit framing then triggered a four-agent
**per-unit-mechanics audit** (`docs/PER_UNIT_MECHANICS_AUDIT.md`): the per-model
representation pervades the codebase and `squad_id` is the fix key. Top open items
(tasks #23-28): coherency wave (deployment clustering + OC-per-unit — the likely
remaining lever on horde over-shoot), per-unit secondary scoring (No Prisoners /
Cull count models not units), Reanimation profile.name→squad_id pooling, stratagem
transient-buff propagation to squad siblings, per-squad battleshock.

### Earlier this session — wave 65 (damage-allocation spillover, gated 9.27→7.78)

Wave 65 landed the biggest fidelity fix in many waves: **damage-allocation spillover**
(`simulator.damage_allocation_spillover`). The sim previously dumped a whole
volley into ONE model of a multi-model unit and wasted the overkill; now each
unsaved wound allocates to the next surviving same-`squad_id` model, with a
destroyed model's excess damage lost (kills bounded by unsaved-wound count, not
damage total — the actual 10e rule). This was the real "Lever 1" win: it moved
exactly the structural-residual factions (Tyranids −10.4, Imperial Knights +8.0,
Orks −7.2, Drukhari −7.2, Chaos Knights +4.8, AdMech −4.6). Built on the P1
`squad_id` infrastructure (behaviour-neutral) added the same session. See
`docs/RULE_ACCURATE_FIX_DESIGN.md` and memory `project-squad-activation-contained-wash`.

Second-order effect to chase next: elite/MEQ armies (Custodes +9.9, Marines
+10.3, Thousand Sons +21.7, Aeldari +13.5) now clear chaff more efficiently and
drifted further over — candidates for an archetype-list re-fit.

This file is the fast-pickup point for any session continuing the loop.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 59 close (`f1c2825`) | 14.28 | 10.73 | 3/22 |
| Wave 60 close (`e1f3f53`+docs) | 14.27 | 10.71 | 2/22 |
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |
| Wave 63 close (`96fd68e`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 65 close (spillover+docs) | 11.15 | 7.78 | 2/22 |
| Wave 66 close (mortal+demise+blast) | 11.08 | 7.56 | 3/22 |
| Wave 67 close (per-unit batch ×6) | 11.11 | 7.80 | 5/22 |
| Wave 68 close (core-rules batch, fidelity) | 12.05 | 8.74 | 5/22 |
| Wave 69 close (under-performer faction buffs) | 11.57 | 8.29 | 5/22 |
| Wave 70 close (objective-aware AI #12) | 9.47 | 5.98 | 4/22 |
| Wave 71 close (Code Chivalric fidelity fix) | 9.38 | 5.97 | 6/22 |
| Wave 72 close (Ion Shield ranged-only) | 9.28 | 5.89 | 6/22 |
| Wave 73 (investigation only, no code change) | 9.28 | 5.89 | 6/22 |
| Wave 74 close (Cleanse action secondary + Cull-fix) | 8.74 | 5.35 | 6→5/22 |
| Wave 75 close (Sabotage + 40-VP secondary cap) | 8.50 | 5.11 | 5/22 |
| Wave 76 close (per-squad charge roll) | 8.16 | 4.91 | 5/22 |
| **Wave 77 close (per-unit Advance — metric-neutral)** | **8.29** | **4.95** | **6/22** |

Wave 65's lever was a **core-rule fidelity fix** (damage allocation), not AI or
stats — confirming the `project-faction-residual-rootcause` thesis that the big
residuals are structural representation bugs, not tuning. In-band count is flat
at 2/22 but the error *magnitude* dropped sharply (gated −1.49); the improved
factions are still outside their noise floors but much closer.

## Handoff context — wave 61 close

Three fixes landed (all on `claude/sim-calibration-6`, pushed through
`d141a69`; `c4d6da6` is the AI-gate commit, docs/close on top):

- **KNIGHTS-TITANIC-ESCAPE** (`31e477c`): TITANIC/FLY exempt from Desperate
  Escape + threshold 1→1-2 (Wahapedia verbatim).
- **KNIGHTS-DEMISE-D6PLUS2** (`d141a69`): mapper D6+2 parse + 11 chassis
  overrides (Deadly Demise was 1, should be 5).
- **KNIGHTS-AI-FALLBACK** (`c4d6da6`, the dominant lever): melee-primary
  units stay and fight instead of Falling Back. Corrected Knights UP
  (IK +10.1) AND over-shooters DOWN (Votann/AdMech/Orks/Marines/AstraMil).

New over-shoots introduced by the gate (melee units now staying engaged):
**World Eaters +7.1, CSM slightly over** — top carry-forward to re-tune.

## Next ranked levers for wave 77

Current biggest gated errors (wave 76 eval `data/wf_wave76_squadcharge_n40.json`):
Imperial Knights +19.6 (16.6), Drukhari +18.7 (15.3), Chaos Daemons −17.0 (13.8),
CSM −17.3 (14.9), Votann +12.4 (9.3), Chaos Knights −12.4 (9.1).

1. **MORE per-model activation-economy taxes in the charge-vein (the proven wave-76
   pattern).** Per-squad charge (5.11 → 4.91) confirms: find other per-model rolls/events
   that should be per-UNIT in real 10e and fix them. Candidates to verify-first: Desperate
   Escape tests (per model vs per unit), Battle-shock tests, overwatch, any "roll for the
   unit" event the sim does per model. Each is a core-rule correctness fix that cuts
   per-model over-rating.
2. **Rotation-gate the tactical secondaries (the deferred fidelity fix is now due).**
   cleanse/sabotage score every round; the real tactical deck draws ~1-2/turn. Gating them
   (like Engage/BEL via LC-2) would temper the wave-75 over-correction of the low-model
   armies (CSM −17.3, Chaos Knights −12.4) and the cheap-unit over-scoring (Votann,
   Sororitas) — a genuine fidelity fix, no longer pre-empting the per-model tax.
3. **Imperial Knights +19.6 (still #1) is NOT per-model** (1-model units, unaffected by
   per-squad charge) — it is the durable primary-camper over-rate. Its own diagnostic:
   likely the opponents not contesting it off objectives (the AI-targeting fix regressed,
   wave 72) or a durability/scoring angle. Drukhari +18.7 rose this wave (its melee
   opponents charge less reliably) — re-diagnose now that the melee layer changed.
4. **Re-fit candidates (archetype-list care rules):** re-measure after the above.

## Structural track (owns the remaining headline)

- **The over/under split is now understood and single-rooted.** Over-shooters are
  killy/durable elite armies (IK +29, WE +16.5, Drukhari +16.9, TSON +12.8,
  Custodes +10.0, Marines +8.6, Votann +9.0); under-shooters are board-control
  armies (Daemons −20, Astra −15.5, Necrons −9.5, AdMech −8.7, GSC −7.5,
  Tyranids −7.2). Wave 71 proved this is NOT rules/stats/lists (IK verified
  faithful end-to-end) — it is the min-HP target AI never removing durable
  objective-holders. Lever #1 above is the fix.
- The objective-greedy AI tweak (gunline troops claim reachable objectives) was
  tested and shelved as a wash — confirms holding-better is not the bottleneck;
  taking-from-durable-holders is.

NOTE: the IK/CK multi-profile weapon mapper is DONE (shipped pre-wave-60);
do not re-implement it. See memory `project-knights-multiprofile-weapons`.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go".
- Per CLAUDE.md §10: every rule fix needs a Wahapedia/BSData citation. The citation audit is ENFORCING on commit (`BLOCK_ON_MISSING_CITATIONS=True`).
- **Always** prefix the eval: `PYTHONHASHSEED=0 ... python -m scripts.evaluate_vs_meta --battles 40 --use-archetype` (segfault workaround; memory `project-eval-pythonhashseed-segfault`).
- Model tiering (global `~/.claude/CLAUDE.md`): set `model` per Agent dispatch; sonnet for T2 audits, never inherit Opus.
- Verify-first: agent and memory claims have been wrong repeatedly this branch — confirm file:line / rule text before acting.
- cwd-leak into agent worktrees is recurring — `cd` to main worktree and confirm `pwd` before git ops.

## Wave close checklist

1. Cherry-pick agent commits from the main worktree (check cwd).
2. pytest sweep + N=40 eval (`PYTHONHASHSEED=0`, `--use-archetype`).
3. Per-faction diff vs prior eval JSON.
4. Archive oldest wave-close block to `AUTO_LOOP_LOG_archive.md` (keep ~3).
5. Write new wave-close block at top of `AUTO_LOOP_LOG.md`.
6. Update this file with new headline + next levers.
7. `python scripts/loop_cleanup.py`.
8. Commit + push (push only on explicit user "go").
