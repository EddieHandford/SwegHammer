# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 70 close (2026-05-31)

Branch `claude/sim-calibration-6`. The plan-level objective AI (#12, "the big
lever") — the clean version of the reverted blunt durable-camp experiment.

`code/strategy.py` `pick_move_intent`: a SHOOTY/HEAVY unit that can still shoot from
an objective now moves ONTO the best-scoring objective (scoring VP while firing)
instead of holding in open ground. Melee-primary units never reach this branch (they
keep charging — so the melee-monster mis-camp that sank the blunt version is gone),
and it is gated OUT for the tuned aggressive gunline postures (shimmy / alpha_strike
/ fast_strike) so the Aeldari/T'au over-shooters are not pushed further over. Internal
AI heuristic — no rule citation (an activation/intent scheduler, not a 10e mechanic).

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 69 close (faction buffs) | 11.57 | 8.29 | 5/22 |
| **Wave 70 close (objective AI #12)** | **9.47** | **5.98** | **4/22** |

Biggest single-change move of the campaign (gated -2.31). Confirmed the AI-positional
thesis: Chaos Knights -38.7 -> -3.3 (nearly fixed). Pulled the kill-centric
over-shooters toward 50% because their opponents now contest objectives (Sororitas
+18.3->+2.1, Aeldari +15.8->+2.6, T'au +10.0->+2.6 into band; Drukhari +27.7->+17.1,
Thousand Sons +20.4->+13.1). Collateral → re-fit (task #22) now mandatory: Imperial
Knights OVERSHOT to +27.8 (gun-heavy archetype + wave-69 Bondsman/Valourstrike buffs
STACK on the AI objective-hold); Astra -15.0, Chaos Daemons -19.5, AdMech -8.3,
Tyranids -7.5 swung under. Eval `data/wf_obj_ai_n40.json`.

