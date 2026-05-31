# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 76 close (2026-05-31) — per-squad charge roll: the per-model activation tax (gated 5.11 → 4.91)

Branch `claude/sim-calibration-6`. The watchdog-mandated per-model durability/activation
tax (`LOOP_QA.md` Q3) — and verify-first found the concrete, faithful mechanism the prior
washes missed.

DIAGNOSIS (verify-first, because the decision-overlay washed): the per-model over-rate is
NOT spread/coherency (Drukhari squads spread across 2+ quarters only ~1% of the time — they
cluster), and the over-shooters win on VP not tabling. The real per-model bug is in the
CHARGE phase: SwegHammer rolls 2D6 **per model**, so an 11-model Ork mob got 11 independent
charge attempts (152 of 288 squad-rounds had >1 roll). Real 10e: a unit makes ONE charge
roll — an 11-model mob makes a 9" charge ~97% of the time in the sim vs the real ~28%. A
massive melee-reliability over-rate.

LANDED — **per-squad charge roll**: a codex squad (models sharing a `squad_id`) shares ONE
2D6 charge roll per round (cached in `Battle._squad_charge_roll`); lone models keep their
own. This is the activation-economy half of the per-model tax that the decision-overlay
could not reach — it works *because it cuts the horde's effective melee output*, not just
its decisions (the exact reason the overlay washed, per
`project-squad-activation-contained-wash`). Core-rule correctness fix; cited
`simulator.charge_per_unit`.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 75 close (Sabotage + 40-cap) | 8.50 | 5.11 | 5/22 |
| **Wave 76 close (per-squad charge)** | **8.16** | **4.91** | **5/22** |

Brings down the melee over-shooters (Orks +10.3 → +8.1, Votann +14.7 → +12.4) and pulls
Grey Knights back toward band (−6.6 → −2.7); Custodes, Thousand Sons, Emperor's Children,
Necrons, Aeldari all better. Collateral the other way (re-fit territory, not reasons to
reject a core-rule fix): Drukhari +16.4 → +18.7 and T'au / Sororitas up — their melee
*opponents* now charge less reliably, so these (more shooty) armies survive better. 926
tests pass; citation audit 293/293. Eval `data/wf_wave76_squadcharge_n40.json`.

NEXT: the residual is now Imperial Knights +19.6 (durable primary-camper — NOT a per-model
issue; it has 1-model units, unaffected by per-squad charge), Drukhari +18.7, Chaos Daemons
−17.0, CSM −17.3. Candidate faithful levers: (1) rotation-gate the tactical secondaries
(would temper the wave-75 over-correction of CSM/CK and the cheap-unit over-scoring of
Votann/Sororitas — a fidelity fix); (2) more per-model activation-economy taxes in the
charge-vein (other per-model rolls that should be per-unit — overwatch, desperate escape,
battleshock counts); (3) IK's durable-camp over-rate (its own diagnostic — likely the
opponents not contesting, which the AI-targeting fix regressed on).

