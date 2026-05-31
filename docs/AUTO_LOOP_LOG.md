# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 69 close (2026-05-31)

Branch `claude/sim-calibration-6`. The win-win under-performer track: a 6-agent
faction-rules deep-dive (5 under-performers + an over-performer over-buff audit),
then implement each under-performer's missing rules — all verify-first against
Wahapedia/BSData (the over-performer audit's "phantom Aeldari Aspect-Warrior invuln"
claim was DEBUNKED on verification: Dark Reapers genuinely have a 5++). Five worktree
agents implemented, cherry-picked clean.

LANDED (gated 8.74 → 8.29):
- **Imperial Knights −21.8 → −16.0** (+5.8): real Valourstrike Lance detachment
  (Bold Gallantry advance→assault) + Bondsman abilities (Questoris buff Armigers each
  Command phase). Remapped off the empty Imperial-Knights `noble_lance`.
- **Chaos Daemons −19.0 → −14.6** (+4.4): per-god datasheet buffs — Tzeentch 4++
  correction (only the genuine ones, 5++ units left alone), Murderer's Cowl
  (advance+charge), Penumbral Puppetry (-1 to hit), Gloam Rot (-1 wound vs S>T).
- **TOWERING line-of-sight** (cross-faction): Obscuring/Ruins don't block LoS for
  TOWERING models — helps Knights/Wraithknight guns.
- **Chaos Knights** real Iconoclast Fiefdom detachment (Dread Tyrants aura) + **GSC**
  Patriarch/Primus leaders + Aberrant FNP.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 68 close (core-rules batch) | 12.05 | 8.74 | 5/22 |
| **Wave 69 close (faction buffs)** | **11.57** | **8.29** | **5/22** |

CAUGHT + REVERTED: **CSM Dark Pacts per-unit** auto-gamble crashed CSM 45.8→24.8%
(self-inflicted D3 mortal wounds on every squad every round outweigh the buff; real
players are selective — task #36). **Chaos Knights** barely moved from the detachment
alone (+0.5) — its −38 is AI-positional (the reverted durable-objective diagnostic
moved CK −38→−8.8), so CK needs the objective AI (#12). GSC's small −2.1 is
redistribution from the IK/Daemons buffs (verified-correct, not a bug). 926 tests
green; audit 288/288. Eval `data/wf_wave69b_n40.json`.

