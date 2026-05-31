# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 78 close (2026-05-31) — matchup-fidelity diagnosis + faithful-AI plan (no code change)

Branch `claude/sim-calibration-6`. First wave of the user-chosen phase (Q4 ruling): the
faithful target/positioning AI track + matchup-fidelity diagnosis. A diagnosis+plan wave
(like wave 73 → 74), because the AI redesign is big/risky and warrants clean context.
Headline unchanged at gated 4.95.

MATCHUP DIAGNOSIS (drilled per-cell, not aggregate). The over-shooters crush specific
victims: Imperial Knights beat CSM / AdMech / Marines **100%**, Drukhari beat Tyranids /
CSM / AdMech **90%**. The under-shooters get crushed: CSM loses **0%** to Emperor's
Children (10% to Sororitas/Votann); Chaos Daemons lose **0%** to AdMech / Drukhari / TSON.
These are impossible in real competitive play (~even). Compared to real May-2026 play, the
gap sorts almost entirely into **bucket (a) — the opponent AI**: it does not (1) focus-fire
the durable/key threat with concentrated anti-armour (the way a real list deletes a Knight
or a Ravager), (2) contest/deny the durable camper's objectives, or (3) allocate units to
actions sensibly (CSM/Daemons suicide spare units on Sabotage). Verified NOT a stat gap —
the sim's Knight stats (Questoris T11/W26) already reflect the December-2025 toughness
update, and the rules were verified faithful in waves 71-72. One list note (bucket b): the
real winning Knights list is Armiger-heavy vs the sim's big-Knight build — flagged, not
pulled (uncertain direction).

DELIVERABLE: `docs/MATCHUP_FIDELITY_ANALYSIS.md` — the per-cell findings, the real-play
comparison, the 3-bucket sort, and the faithful-AI redesign plan: (1) ARMY-LEVEL focus fire
on the highest-value reachable threat (weapon-target-matched — the per-UNIT value-picker
regressed in wave 72 because it sharpened the over-shooters' own offence symmetrically); (2)
contest/deny objectives (#13 positioning — body the camper off the VP); (3) action
allocation = spare-and-survivable only. Each env-gated A/B, and when the better AI exposes
an over-shoot, DIAGNOSE the faithful cause (re-calibration toward real lists now permitted)
— never a nerf. Build in the next waves, drilling the driving matchup cells before/after.

## Wave 77 close (2026-05-31) — per-unit Advance roll (correctness, metric-neutral); clean levers exhausting → strategic fork escalated

Branch `claude/sim-calibration-6`. A consolidation wave: the clean impactful faithful levers
are now largely exhausted, so this wave landed one small core-rule correctness fix and
escalated the strategic direction to the user (via the watchdog).

TESTED + REJECTED — rotation-gating the tactical secondaries. The deferred fidelity idea
(cleanse/sabotage score every round vs the real ~1-2/turn deck cadence) was checked by an
isolation A/B: **Sabotage OFF is gated 5.15 vs 4.91 ON**, i.e. the "over-scoring" is actually
NET-POSITIVE, so reducing it would regress the headline for an ambiguous fidelity gain. Not
done.

LANDED — **per-unit Advance roll**. Real 10e makes ONE Advance roll (one D6) per unit; the sim
rolled per model (same one-Unit-per-model bug class as the wave-76 charge fix). A codex squad
now shares one Advance D6 per round (`_squad_advance_roll` cache). Lower-impact than charge
(Advance adds distance, not a binary-success multiplier), so it is **metric-neutral**: gated
4.91 → 4.95 (within N=40 noise) but in-band 5 → 6. A faithful correctness fix, kept on its
correctness (like Code Chivalric, wave 71). Cited `simulator.advance_per_unit`. 926 tests pass;
citation audit 294/294. Eval `data/wf_wave77_advance_n40.json`.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 76 close (per-squad charge) | 8.16 | 4.91 | 5/22 |
| **Wave 77 close (per-unit Advance)** | **8.29** | **4.95** | **6/22** |

STRATEGIC FORK — ESCALATED TO THE USER (`LOOP_QA.md` Q4). The headline is gated 4.95 (down from
5.98 this session). The clean faithful levers are exhausted: rotation-gating is net-negative;
the per-model→per-unit vein's big hit (charge) is done; the two biggest residuals — Imperial
Knights +19.1 (durable primary-camper) and Drukhari +18.6 (fragile, should die to focused fire)
— both need the OPPONENT target/positioning AI, which REGRESSED when tried (wave 72). The
watchdog escalated the call: (b) take the target-AI redesign PAIRED with a re-fit (the goal doc
restricts this — needs the user's go), vs (c) bank Stage 1 at ~4.9. **Watchdog ruling: do NOT
start the AI-redesign+re-fit until the user rules; meanwhile keep taking small clean faithful
fixes** (e.g. the missing Be'lakor datasheet for Chaos Daemons, option d). Next wave does that.

