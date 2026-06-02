# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

