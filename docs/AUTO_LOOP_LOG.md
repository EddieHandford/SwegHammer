# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 75 close (2026-05-31) — Sabotage + 40-VP secondary cap (gated 5.35 → 5.11)

Branch `claude/sim-calibration-6`. Continued the proven action-economy lever (watchdog
confirmed option (a) in `LOOP_QA.md` Q3). Two faithful changes, env-gated A/B then landed.

LANDED — **40-VP total-secondary cap** (`_decide_winner` now decides on primary +
min(secondary, 40)). Real Pariah Nexus caps secondary VP at 40/game; the sim's mixed
`_a_vp` totals never enforced it, so secondary-heavy shapes ran past it (Custodes ~39/game).
A faithful correctness fix AND the prerequisite that keeps further secondaries bounded.
Cited `simulator.secondary_vp_cap_40`. **Sabotage** (Pariah Nexus action secondary, card
text web-verified): a surplus chaff unit OUTSIDE its own DZ performs the action (shoot/charge
lockout) — 3 VP in No Man's Land, 6 VP in the enemy DZ, scored if it survives forward; capped
at one completion (6 VP)/round. Rewards deep forward push (deepstrike/infiltrate
under-shooters), which a durable low-model camper cannot do. Cited `simulator.secondary_sabotage`.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 74 close (Cleanse + Cull-fix) | 8.74 | 5.35 | 6→5/22 |
| **Wave 75 close (Sabotage + 40-cap)** | **8.50** | **5.11** | **5/22** |

DENTS THE #1 RESIDUAL: Imperial Knights +23.3 → +18.0 (−5.3, opponents sabotage/cleanse into
its zone, which it cannot reciprocate); Custodes +9.3 → +6.1 (the 40-cap biting its high
secondary); Tyranids into band; Astra / AdMech / Necrons / Marines / World Eaters all better.

HONEST COLLATERAL (over-correction of low-model armies): CSM −9.7 → −16.6, Chaos Knights
−6.1 → −12.9, Grey Knights +1.6 → −6.6; Votann / Orks further over. The DIRECTION is faithful
(low-model armies genuinely struggle with the secondary game), but the MAGNITUDE is amplified
because cleanse/sabotage are NOT yet rotation-gated like Engage/BEL — they score every round
vs the real draw-1-2/turn cadence, so they over-score. Tempering that (rotation-gating the
tactical layer) is a LATER secondary wave; per the watchdog it must NOT pre-empt wave 76.
926 tests pass; citation audit 292/292. Eval `data/wf_wave75_sabotage_cap_n40.json`.

WAVE 76 (watchdog-directed, firm): the per-model durability / activation tax — the genuine
root cause of Imperial Knights +18.0 (still #1) that the secondaries only chip at. Design it
as a FAITHFUL mechanic (real action-economy / objective-count / coherency effects), NOT a
metric-driven penalty on low-model armies. The watchdog will flag "one more bounded secondary"
as shying away.

## Wave 74 close (2026-05-31) — action-economy secondaries: Cleanse + Cull-fix (gated 5.89 → 5.35)

Branch `claude/sim-calibration-6`. Built the wave-73 structural lever: the action-economy
secondary family that counterbalances the kill-secondary asymmetry. Biggest single-wave
headline move in many waves, and a FAITHFUL one (a real Pariah Nexus secondary that was
missing). The user ratified the diagnosis (`098e8c0`) before the build.

WHAT LANDED — **Cleanse** (Pariah Nexus action secondary). Verified the card text via
web search (Wahapedia DNS down): a unit performs the Cleanse action while in range of an
objective marker OUTSIDE its own deployment zone that its army controls; each unit
cleanses one marker; 2 VP for one, 4 VP for two (cap); completes end of turn if still
controlled. New `Unit.action_this_round` state + a shoot/charge lockout (`_do_shoot` /
`_do_charge`): a unit performing the action cannot shoot or charge — the real
action-vs-fight tradeoff. `Battle._assign_cleanse_actions` (after Movement) flags up to 2
SURPLUS chaff units (per `strategy._is_chaff_unit`, <15 pts/model) on controlled forward
objectives; `_score_cleanse` awards the VP at end of round. The asymmetry falls out of
unit cost, EVEN-HANDEDLY: Imperial Knights (no chaff) score 0; hordes / MSU and elites
with cheap aux (Custodes' Sisters of Silence) score it. Cited `simulator.secondary_cleanse`.
Also fixed the dead **Cull the Horde** mechanic (`_is_horde_unit` read all-None
`starting_strength`; now reads `max_models`).

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 72 close (Ion Shield) | 9.28 | 5.89 | 6/22 |
| Cull-fix only (A/B isolation) | 9.28 | 5.92 | 6/22 |
| **Wave 74 close (Cleanse + Cull-fix)** | **8.74** | **5.35** | **5/22** |

The per-faction moves are exactly the predicted mechanism: durable over-shooters ease
down (Imperial Knights +27.9 → +23.3, World Eaters +16.5 → +12.5 — opponents cleanse
forward objectives the camper can't contest back) and board-control under-shooters rise
(Astra −15.5 → −10.6; AdMech, Daemons, Tyranids, Necrons, Emperor's Children all toward
band). The Cull fix alone regressed +0.03 (it rewards killing hordes, feeding the
asymmetry — as predicted); Cleanse more than counterbalanced it (−0.57 from there).
In-band dipped 6 → 5 (Aeldari 0.36 and Chaos Knights 2.78 fell just out by small margins;
Orks over-shot to +8.6 — Gretchin cleanse, faithful — a re-fit candidate, not a reason to
reject a correct structural fix). 926 tests pass; citation audit 290/290. Eval
`data/wf_wave74_cleanse_n40.json`.

FOLLOW-UPS (queued): the other action secondaries (Sabotage, Recover Assets); cleanse is
wired into the vanilla turn loop only (`_run_round_alternating` doesn't assign it — the
eval/balancer use vanilla, so no current impact); and the now-exposed re-fit candidates
(Orks, Chaos Knights, Custodes) once the structural layer settles.

