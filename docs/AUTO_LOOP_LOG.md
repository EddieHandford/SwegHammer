# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 73 close (2026-05-31) — investigation + plan, no code change

Branch `claude/sim-calibration-6`. A pure investigation wave (the user steered the loop
off narrow nerf-grinding toward structural levers and named a "first structural lever":
the Pariah Nexus secondary VP is "computed every round into `_a_secondary_vp` and never
read, so `_decide_winner` uses primary VP only"). Verify-first overturned the premise and
found the real driver. No code changed (per the "report first" directive). Headline
unchanged at gated 5.89.

FINDING 0 — the named premise is WRONG. Secondaries ARE counted: they are added to
`_a_vp`/`_b_vp` (what `_decide_winner` reads) at `simulator.py:925`/`:954`, wired
2026-05-20 (`54e41427`, `dc07dc39`); `_a_secondary_vp` is a redundant UNREAD tracker.
Empirically `_a_vp`=61 = primary 35 + secondary 26. The literal fix would DOUBLE-COUNT.
(A clean example of "verify the machinery is wired up before assuming.")

FINDING 1 (the real driver) — the KILL-secondary asymmetry. Decomposing IK's secondary
VP: the over-credit is entirely kill-based (vs Tyranids IK scores 18.5 No Prisoners,
Tyranids score 0 back — they can't destroy a single durable Knight AS A UNIT under
per-model representation; vs Astra IK scores 12.8 Bring It Down + 7.2 Assassinate vs
4.0/0.5). Position secondaries (Engage/BEL) are even or favour the opponent. So the
secondary layer AMPLIFIES the kill-centric bias instead of counterbalancing it.

FINDING 2 — the missing counterbalance is the ACTION-economy secondary family. The sim
implements 2 of 9 tacticals (Engage, BEL) and NO action mechanic at all. The action
secondaries (Cleanse, Sabotage, Recover Assets…) reward unit availability / board
control over kills and impose an action-vs-fight tradeoff a 9-model durable camper
cannot afford but a horde can — the faithful, even-handed fix for the asymmetry.

FINDING 3 (dead mechanic) — Cull the Horde never fires: `_is_horde_unit` reads
`starting_strength`/`squad_size`/`count` (all None); the real field is `max_models`.
Scores 0 for everyone. Fix it only WITH the action work (alone it feeds the asymmetry).

Deliverables: `docs/SECONDARY_SCORING_ANALYSIS.md` (evidence) + `docs/ACTION_SECONDARIES_PLAN.md`
(wave-74 build plan: action-state mechanic, Cleanse vertical slice, AI surplus-unit
selection, scoring, picker/caps, env-gated N=40 A/B, risk assessment). User direction:
plan first (this wave), build next wave. Also stood up the watchdog-mediated `LOOP_QA.md`
question channel (worker no longer asks the user directly).

## Wave 72 close (2026-05-31)

Branch `claude/sim-calibration-6`. Pursued the #1 ranked lever (the systemic
threat-priority target AI) but it FAILED the A/B and a faithful stat-fidelity fix
was landed in its place. Two hard findings drove the wave.

FINDING 1 — the under-shooters lose on VICTORY POINTS WHILE STILL ALIVE, not by
being tabled. Chaos Daemons (the −20 #2 residual) lose 6-9 of every 10 with
survivors on the board (0-1 tabled). So per-faction COMBAT buffs (per-god rules,
Astra Orders) do not address the actual loss — it is the same objective/durability
complex as the Imperial Knights over-rate, from the under side. Per-faction combat
levers for the under-shooters are mostly mis-targeted.

FINDING 2 — improving the target AI REGRESSES the headline (second confirmation
this session of `project-ai-frozen-under-mae-first`). A value-based shooting-target
picker (kill-efficiency × target-value, mirroring `_melee_target_score`, so
anti-armour concentrates on durable threats instead of mopping the lowest-health
chaff — faithful real-10e weapon-target matching) was prototyped and A/B'd at N=40:
it made things WORSE (gated 5.97 → 6.11, Imperial Knights +29 → +32.9). Reason:
better targeting helps the killy over-shooters' OWN offence more than it helps their
victims, and Knights stay un-killable so concentrated anti-tank is still wasted while
the over-shooters' guns get sharper. Reverted. (The min-HP picker genuinely cannot
express threat-priority via a bonus — a full-Wounds W26 Knight scores ~26 vs ~2 for
chaff, so any bonus large enough to redirect fire distorts everything; a real fix
needs a value-based objective, which regresses while stats stay over-tuned.)

LANDED — Ion Shield ranged-only (a faithful stat-fidelity fix, the one metric-positive
lever found). BSData v10.6.0 verbatim: Imperial Knight Ion Shield is "a 5+ invulnerable
save against ranged attacks only" — big Imperial Knights have NO invulnerable save in
melee, only their 3+ armour. The sim applied invuln flat (melee + ranged). Added an
`invuln_ranged_only` profile flag (plumbed loader → UnitProfile), set on the 12
confirmed standard-codex Imperial Knights/Armigers via overrides.json (Forge World
Acastus/Magaera/Styrix excluded — unverified Ion Aegis, none fielded; Chaos Knights
left flat since their Ion Shield is ranged AND melee). Suppresses the datasheet invuln
for melee attacks. Cited `simulator.ion_shield_ranged_only`.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 71 close (Code Chivalric fidelity fix) | 9.38 | 5.97 | 6/22 |
| **Wave 72 close (Ion Shield ranged-only)** | **9.28** | **5.89** | **6/22** |

Imperial Knights +29.0 → +27.9 (gated 26.04 → 24.97); melee under-shooters edge up
(Chaos Daemons −20.0 → −19.7, Chaos Space Marines −7.7 → −7.3, Necrons −9.5 → −9.2);
no regressions. Modest (the melee invuln only matters in the minority of matchups
where an opponent reaches combat with a Knight) but faithful and net-positive. 926
tests pass; citation audit 289/289. Eval `data/wf_wave72_ionshield_n40.json`.

NEXT-LEVER NOTE: the headline is now firmly AI/structure-gated. Two AI levers have
regressed this session (objgreedy wave 71, value-targeting wave 72), both confirming
that AI improvements expose the over-tuned over-shooter stats/lists. The remaining
faithful levers are (a) more stat-fidelity audits like Ion Shield (durability/rule
corrections that nerf over-shooters or buff under-shooters without touching AI), and
(b) the re-calibration the goal doc restricts. A pure target-AI redesign will not
reduce the headline until the over-shooters are re-fitted. Approaching the mission's
"2-3 wave stall → report the structural finding" condition.

