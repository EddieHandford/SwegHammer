# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 71 close (2026-05-31)

Branch `claude/sim-calibration-6`. A targeted Imperial Knights over-rate
investigation (task #22 / the +27.8 outlier) that turned into a deep fidelity
audit. The directed lever ("audit the wave-69 Bold Gallantry / Bondsman buffs
for over-rating — do they match the real detachment text?") was followed to
conclusion and the answer is: **the buffs are faithful; the over-rate is a
compensating error, not a rule defect.**

What was verified faithful (all confirmed against BSData v10.6.0 / the live
code, win-rate-attributed with env-gated A/B probes across all 21 opponents):
- **Bold Gallantry** (Valourstrike Lance detachment rule, ~21pt of IK's win
  rate): real detachment (BSData has "Valourstrike Lance" + "Bold Gallantry"),
  text verbatim ("Advance → IK ranged weapons gain [ASSAULT]"), correctly gated
  on the unit having actually Advanced, and the sim correctly blocks
  charge-after-advance. Faithful — NOT reverted.
- **Bondsman / Paladin's Duty** (~2.4pt): real datasheet mechanic, text verbatim
  ([LETHAL HITS] + melee [LANCE]); mild over-application (12" gate dropped,
  strongest variant applied uniformly) but low-impact.
- **Knight stats**: OC 10 (Questoris) / 6 (Armiger), T 11/12, W 26/28, Sv 3+ all
  match BSData exactly. **Maps**: 5-objective Leviathan quincunx — faithful.
- IK wins almost entirely by **VP (objective-holding), not tabling** (0/8 tabled
  vs Astra; wins 7-8/8 on VP) — so the residual is positional, not lethality.

The one genuine fidelity DEFECT found and FIXED:
- **Code Chivalric** re-rolled EVERY natural 1 on every die army-wide. The real
  rule is "re-roll ONE Hit roll and ONE Wound roll" per activation. Reroll-all-1s
  over-scales with shot volume (a 20-shot Knight gun got ~3-4 effective re-rolls
  vs the rule's one). Because SwegHammer is one-Unit-per-model, "each time this
  model is selected" maps exactly onto one re-roll per Unit activation — now
  implemented via a per-activation `_chiv_hit_reroll` / `_chiv_wound_reroll`
  budget spent on the first failed die. Citation `simulator.code_chivalric`
  updated (was wrongly described as an under-buff). **Metric-neutral** on gated
  magnitude (the rule existing at all is the ~10pt swing, not the over-scaling),
  but more faithful, and it nudged Death Guard and Chaos Knights into band.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 70 close (objective AI #12) | 9.47 | 5.98 | 4/22 |
| **Wave 71 close (Code Chivalric fidelity fix)** | **9.38** | **5.97** | **6/22** |

TESTED + SHELVED: an objective-greedy AI tweak (gunline troops step onto a
reachable objective instead of camping in open ground — faithful, addresses the
empirically-confirmed "30 Astra bodies sit OFF every objective at round 2" gap)
was a wash at N=40 (5.97→5.98) and knocked Chaos Knights back out of band,
because under-shooters holding objectives *better* still can't take them FROM
durable Knights. Reverted; the finding stands.

ROOT-CAUSE FINDING (the real next lever): the shooting-target AI is a min-HP
"finish off the weakest" picker (`simulator.py:6835`, `min(pool, key=current_health/bonuses)`).
Against Knights (all at full W26) it shoots the W14 Armigers and chaff first and
**never concentrates fire on a big Knight**, so durable Knights sit on objectives
untouched all game — the opposite of real play, where opponents focus anti-tank
on the big threat. This is why IK over-holds and why the board-control
under-shooters can't recover the objectives. A threat/value target-priority lever
(focus-fire high-value durable objective-holders) is the highest-leverage systemic
faithful fix left, but it is army-wide and high-risk — it needs its own dedicated
wave with a design pass, not a rushed env-gate. Eval `data/wf_wave71_chivalric_n40.json`.

