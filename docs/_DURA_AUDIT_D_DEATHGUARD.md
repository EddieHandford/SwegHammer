# Durability fidelity audit D — Death Guard defensive economy

Read-only audit against the printed 10th-edition Death Guard rules. Death Guard is
the top over-pole: simulator 61.5 percent versus the real Warp Friends aggregate
46.1 percent, an over-pole of plus 15.4 — larger than either Knights faction. A
prior archetype audit already recorded that Death Guard's durable-share (list
composition) "matches reality", so the brief was to find whether something subtler
in the defensive economy is wrong, or whether the over-pole is not a durability
effect at all.

Base branch: `claude/sim-calibration-18`, top commit `215301c`. All rule text is
quoted verbatim from the local BSData cache (`data/bsdata/cache/Chaos - Death
Guard.cat.gz`, the project's canonical stat source per standing rule six) and
cross-checked against Wahapedia. Scratch scripts: `scripts/_dura_audit_d_fnp.py`,
`scripts/_dura_audit_d_units.py`, `scripts/_dura_audit_d_winshape.py`,
`scripts/_dura_audit_d_quick.py`.

## Headline verdict

**The over-pole is scoring-shaped (primary-objective uptime), not
durability-statistic-shaped, and emphatically not attrition-shaped.** Every
defensive statistic and every Feel No Pain value the live default simulator uses
for Death Guard is faithful to the printed codex. The army rule is, if anything,
UNDER-modelled — the simulator's version is strictly weaker than the printed rule.
The replayed anchor games show Death Guard's own units dying FASTER than its
opponents' (23.3 percent survival versus 31.9 percent across all its games) while
it wins on primary victory points (+18.7 average margin in its wins, secondary
margin near zero). This is the survivor-snapshot representation over-reward
documented in `docs/DURABILITY_OVERREWARD_INVESTIGATION.md`, confirmed here with
fresh Death-Guard-specific numbers — the same scoring-shaped pattern the Emperor's
Children crater diagnostic found.

---

## 1. The army rule — Nurgle's Gift / Contagions of Nurgle

### Printed rule (BSData verbatim, `Chaos - Death Guard.cat.gz`)

> If your Army Faction is DEATH GUARD, while an enemy unit is within Contagion
> Range of one or more Death Guard units from your army, it is Afflicted.
>
> CONTAGION RANGE
> 1st Battle Round: Contagion Range = 3"
> 2nd Battle Round: Contagion Range = 6"
> 3rd Battle Round Onwards: Contagion Range = 9"
>
> AFFLICTED
> During the Declare Battle Formations step, select one of the Plagues below.
> Until the end of the battle, while an enemy unit is Afflicted, subtract 1 from
> the Toughness characteristic of models in that unit, and that unit has the effect
> of your chosen Plague.
>
> Skullsquirm Blight — Each time a model in this unit makes an attack, subtract 1
> from the Hit roll.
> Rattlejoint Ague — Worsen the Save characteristic of models in this unit by 1.
> Scabrous Soulrot — Worsen the Move, Leadership and Objective Control
> characteristics of models in this unit by 1 (this rule can only worsen a model's
> Objective Control characteristic to a minimum of 1).

Wahapedia cross-check (https://wahapedia.ru/wh40k10ed/factions/death-guard/):
same text; the army rule grants NO army-wide Feel No Pain, and "Disgustingly
Resilient" in 10th edition is a 2-command-point stratagem ("Subtract 1 from the
Damage characteristic of that attack"), not an army rule.

### Simulator implementation

`code/units.py` (`_contagion_round_for`, `_is_near_enemy_dg_model`) and
`code/simulator.py` (`_run_battleshock_phase` and the Command-phase block of
`_run_round`), cited as `simulator.contagions_of_nurgle` in
`data/rule_citations.d/death_guard.json`:

- Round 1 — nothing (the legacy launch-index "Virulent Rot" minus-1-Toughness
  branch was removed at iter-4).
- Round 2 — Maladictive Pall: enemy units within **3 inches** of any Death Guard
  model take minus 1 Leadership (a Battle-shock test penalty only).
- Round 3 onward — Fulminating Plague: enemy units within **3 inches** take minus
  1 to hit, and only when no other minus-1-to-hit source already applies (the
  10th-edition modifier cap).

### Divergences (all in the simulator-WEAKER direction)

1. **Contagion Range does not escalate.** The simulator fixes the aura at 3 inches
   every round; the printed rule expands it to 6 inches (round 2) and 9 inches
   (round 3 onward). Direction: simulator weaker. Magnitude class: moderate.
2. **The always-on Afflicted minus-1-Toughness is entirely absent.** The printed
   rule reduces the Toughness of every Afflicted enemy unit in every round; the
   simulator models none of it. This is an offensive buff for Death Guard (it
   makes their wound rolls easier), so its absence makes the simulator's Death
   Guard weaker on offence, not more durable. Direction: simulator weaker
   (offence). Magnitude class: large offensively, nil defensively.
3. **The chosen-Plague mechanic is approximated.** The real player picks one
   Plague for the whole battle, active from round 1. The simulator applies a
   fixed cross-round mix (round 2 Leadership penalty, round 3 onward hit penalty)
   and never models Rattlejoint Ague's save worsening at all. Direction: net
   simulator weaker (delayed onset, one plague never modelled). Magnitude class:
   moderate.

Net: the army rule as modelled is a conservative, direction-correct approximation
that is strictly weaker than the printed rule. Faithfully completing it (adding
the Toughness reduction and the escalating range) would make Death Guard win MORE,
not less. The army rule is therefore not the source of the over-pole. There is no
always-on or over-wide contagion, and no leaked ninth-edition Disgustingly
Resilient in the army-rule path.

---

## 2. Feel No Pain economy

The specific hazard — an army-wide Feel No Pain, or the ninth-edition
"Disgustingly Resilient" (which WAS an army-wide Feel No Pain 5+ in the previous
edition) — is present in the DATA FILES but neutralised in the LIVE default
simulator.

### Ground truth (BSData catalog, cross-checked on Wahapedia)

| Unit | Real 10th-edition Feel No Pain | Source |
|---|---|---|
| Plague Marines | **None** (ability is the offensive "Infused with the Blessings of Nurgle") | catalog + https://wahapedia.ru/wh40k10ed/factions/death-guard/Plague-Marines |
| Blightlord Terminators | **None** ("Blistering Fusillade" is offensive) | catalog + https://wahapedia.ru/wh40k10ed/factions/death-guard/Blightlord-Terminators |
| Deathshroud Terminators | **None on the unit** — "Silent Bodyguard" verbatim: "While a CHARACTER model is leading this unit, that CHARACTER model has the Feel No Pain 4+ ability" (it belongs to the led character, not the Deathshroud) | catalog + https://wahapedia.ru/wh40k10ed/factions/death-guard/Deathshroud-Terminators |
| Typhus | **None** ("The Destroyer Hive" is a minus-1-to-hit melee aura) | catalog |
| Mortarion | Feel No Pain 5+ (CORE) | catalog + https://wahapedia.ru/wh40k10ed/factions/death-guard/Mortarion |
| Poxwalkers | Feel No Pain 5+ (CORE) | catalog + https://wahapedia.ru/wh40k10ed/factions/death-guard/Poxwalkers |
| Plaguebearers | Feel No Pain 5+ | Daemons datasheet |

### The latent fabrication in `data/overrides.json`

`data/overrides.json` still carries `fnp: 5` on Plague Marines, Blightlord
Terminators, and Typhus, with notes claiming "Death Guard army rule Disgustingly
Resilient grants every DEATH GUARD model FNP 5+" — a rule that does not exist in
10th edition. The project's own `data/rule_citations.d/death_guard.json` records
this exact fabrication as identified and removed at iter-15; the override entries
are the residue. `data/bsdata/parsed.json` also carries a mis-parsed `fnp: 4` on
Deathshroud Terminators (the mapper stamped the led-character's Silent Bodyguard
Feel No Pain onto the unit itself).

### Why none of it reaches the live simulator

Three default-ON gates strip exactly these fabrications before the catalogue is
built:

- `SWEG_DG_PLAGUE_FNP_FAITHFUL` (`code/bsdata/loader.py:935` block) resets Plague
  Marines and Blightlord Terminators to no Feel No Pain.
- `SWEG_AUDIT2_FNP_FABS` (same block) resets Typhus to no Feel No Pain.
- `SWEG_FIX_BODYGUARD_FNP` (`code/units.py:5997`) resets Deathshroud Terminators
  to no Feel No Pain (the Silent Bodyguard mis-parse).

Confirmed by dumping the live `UNIT_CATALOG`: Plague Marines, Blightlord,
Deathshroud, and Typhus all carry no Feel No Pain; Mortarion 5+, Poxwalkers 5+,
and Plaguebearers 5+ remain — all three real. **The live Feel No Pain economy is
faithful.** The residual override entries are a data-hygiene liability (a
kill-switch flip or an override-precedence regression would silently re-introduce
the fabrication) but are inert at defaults.

---

## 3. Datasheet stats of the sourced template

`SWEG_DG_REALISM` (default-on, `code/archetypes.py` `_effective_template`) fields
the effective Death Guard list: Mortarion, 2 Foetid Bloat-drones, 2 Plague Marines
squads, 2 Poxwalkers squads, 2 Deathshroud Terminators squads, 1 Plagueburst
Crawler, 1 Daemon Prince of Nurgle, 2 Lords of Contagion, 1 Myphitic Blight-hauler
(Typhus and the Foul Blightspawn dropped as phantoms). Live simulator stats versus
the BSData catalog verbatim:

| Unit | Toughness | Wounds | Save | Invulnerable | Feel No Pain | Verdict |
|---|---|---|---|---|---|---|
| Mortarion | 12 | 16 | 2+ | 4+ | 5+ | faithful |
| Foetid Bloat-drone | 9 | 10 | 3+ | 5+ | — | faithful |
| Plague Marines | 6 | 2 | 3+ | — | — | faithful (fabricated Feel No Pain gated off) |
| Poxwalkers | 4 | 1 | 7+ | — | 5+ | faithful |
| Deathshroud Terminators | 7 | 4 | 2+ | 4+ | — | faithful (bodyguard Feel No Pain gated off) |
| Plagueburst Crawler | 10 | 12 | 2+ | 5+ | — | faithful |
| Daemon Prince of Nurgle | 12 | 10 | 2+ | 4+ | — | faithful |
| Lord of Contagion | 7 | 6 | 2+ | 4+ | — | faithful |
| Myphitic Blight-hauler | 9 | 10 | 3+ | 5+ | — | faithful (100 points, cited) |

Every Toughness, Wounds, Save, and invulnerable-save value matches a catalog
characteristic or "Invulnerable Save" ability line verbatim (for example the
Plagueburst Crawler: "INVULNERABLE SAVE: 5+", statline Movement 10", Toughness 10,
Save 2+, Wounds 12, Leadership 6+, Objective Control 3 — confirmed at
https://wahapedia.ru/wh40k10ed/factions/death-guard/Plagueburst-Crawler). No
inflated defensive statline was found anywhere in the template.

The Disgustingly Resilient stratagem is modelled faithfully in
`code/simulator.py` (`_try_disgustingly_resilient`): 2 command points, subtract 1
from Damage, INFANTRY or CHARACTER scope with VEHICLE and MONSTER excluded —
matching https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium.

---

## 4. Win-shape — is the over-pole even defensive?

Replayed the Death Guard cells of the standing anchor
`data/_anchor_sc50a_n80_log.json` using the exact evaluate-vs-meta reconstruction
(same seeds, same maps, same missions; harness mirrors
`scripts/_ec_crater_replay.py`). Scripts: `scripts/_dura_audit_d_winshape.py`
(full harness) and `scripts/_dura_audit_d_quick.py` (stratified subset — the
first 15 seeds against each of the 21 opponents, 315 games).
**Winner reproduction: 315 of 315 (100 percent)** — these replays are the
anchor's own games.

Death Guard record in the subset: 175 wins, 137 losses (56.1 percent; the full
anchor Death Guard cells are 1800 wins / 1504 losses = 54.5 percent of decided
games — the 61.5 headline is the evaluate-vs-meta weighting over the same cells).

### The decomposition (all 312 non-empty games)

| Measure | Death Guard | Opponent | Margin |
|---|---|---|---|
| Primary victory points (objectives) | 35.7 | 30.2 | **+5.46** |
| Secondary victory points | 8.9 | 10.3 | **−1.40** |
| Capped victory points | 44.8 | 41.7 | +3.07 |
| Unit survival rate | **23.3 percent** | **31.9 percent** | −8.6 points |

In Death Guard WINS (n = 175): primary margin **+18.70**, secondary margin only
+1.74; Death Guard finishes with 13.8 of 52.7 starting units alive (26 percent)
versus the beaten opponent's 17.1 of 58.7 (29 percent). **Even in its wins, Death
Guard ends with a LOWER survival fraction than the army it beat.** In its losses
it keeps 20 percent versus the winner's 36 percent.

Sample replayed games across opponent classes (all reach round 5):

- versus Imperial Knights, seed 0 — WIN 55–25 capped: primary 55–25, secondaries
  5–0, Death Guard survivors 11 of 74 versus Knights 4 of 7. Death Guard loses 63
  units and still wins comfortably on primary uptime alone.
- versus Astra Militarum, seed 1 — WIN 49–24: primary 45–15, survivors 7 of 67 —
  ninety percent of the Death Guard army is dead at the end of a blowout win.
- versus T'au Empire, seed 1 — WIN 56–41: primary 50–20 while LOSING the
  secondary race 6–19.
- versus Adeptus Custodes, seed 0 — WIN 54–27: primary 40–25, secondaries 14–0.
- versus Orks, seeds 0 and 1 — LOSSES 23–46 and 25–53: the opponent class that
  out-bodies Death Guard on the markers wins the primary race instead (24–20 and
  40–20) and harvests kill-based secondaries (22–3).

### Reading

The over-pole is **not attrition-shaped**: Death Guard does not out-survive its
opponents — it dies faster than they do, in wins and losses alike, and its
secondary scoring is a net negative. The entire edge is **primary-objective
uptime**: the durable pillars (Plagueburst Crawler, Mortarion, Daemon Prince,
Blight-haulers, the 4-wound 2+/4++ Deathshroud bricks) are alive AT each
Command-phase scoring snapshot and bank Objective Control while the cheap bodies
(Poxwalkers, Plague Marines) trade themselves away; the Virulent Vectorium
Worldblight sticky-objective rule (faithful, cited) then holds each banked marker
until the opponent physically out-controls it, extending uptime past the pillars'
presence. This is exactly the survivor-snapshot representation over-reward of
`docs/DURABILITY_OVERREWARD_INVESTIGATION.md` — two individually faithful pieces
(the per-model contest sum and the Command-phase scoring snapshot) composing into
an uptime premium for durable-pillar armies — and it matches the Emperor's
Children crater precedent: the divergence is scoring-shaped, not
durability-statistic-shaped. No defensive-statistic fix can close it, because the
defensive statistics are already correct.

---

## 5. Mortarion and the named characters

- **Mortarion** is fielded (the template anchor). Statline Toughness 12,
  Wounds 16, Save 2+, invulnerable 4+, Feel No Pain 5+, Movement 10 inches,
  Objective Control 6 — verbatim faithful to BSData and Wahapedia
  (https://wahapedia.ru/wh40k10ed/factions/death-guard/Mortarion). His ranged
  weapon basket was zeroed by a prior stat-audit override (Silence is melee-only;
  the mapper had been double-counting) — an offensive correction, unrelated to
  durability.
- **Lord of Contagion** (2 copies) and the **Daemon Prince of Nurgle** are the
  other character pillars; both have faithful defensive statlines (2+ save with
  4+ invulnerable each) and no Feel No Pain, matching the codex.
- **Typhus** is dropped from the effective template (zero sourced tournament
  lists field him), and his fabricated override Feel No Pain is additionally
  gated off.

---

## Divergence list

| # | Printed rule (verbatim, source) | Simulator behaviour | Code location | Direction | Magnitude class |
|---|---|---|---|---|---|
| D1 | "1st Battle Round: Contagion Range = 3" / 2nd Battle Round: Contagion Range = 6" / 3rd Battle Round Onwards: Contagion Range = 9"" (BSData catalog; https://wahapedia.ru/wh40k10ed/factions/death-guard/) | fixed 3-inch radius every round | `code/units.py` `_is_near_enemy_dg_model` (callers pass radius 3.0); `code/simulator.py` battleshock block | simulator weaker | moderate |
| D2 | "while an enemy unit is Afflicted, subtract 1 from the Toughness characteristic of models in that unit" (same sources) | not modelled at all | `code/units.py` `_contagion_round_for` (round-1 branch removed at iter-4) | simulator weaker (offence) | large offensively, nil defensively |
| D3 | chosen Plague active from round 1 for the whole battle (Skullsquirm Blight / Rattlejoint Ague / Scabrous Soulrot, same sources) | fixed mix: round 2 Leadership penalty + round 3 onward hit penalty; Rattlejoint Ague's save worsening never modelled | `code/simulator.py` `_run_round` / `code/units.py` | simulator weaker | moderate |
| D4 (latent, gated off) | Plague Marines / Blightlord Terminators / Typhus have NO Feel No Pain (datasheets, sources in section 2) | `data/overrides.json` carries `fnp: 5` on all three, citing a non-existent army-wide rule; `parsed.json` carries a mis-parsed 4+ on Deathshroud | neutralised by `code/bsdata/loader.py:935` + `code/units.py:5997` (both default-on) | would be simulator-stronger if un-gated | large if un-gated; ZERO live |

**No live divergence in the simulator-stronger direction was found.** Every live
defensive number is faithful; the only simulator-stronger items (D4) are inert at
defaults but should be cleaned out of `data/overrides.json` to remove the
kill-switch hazard.

## Faithful list

- Every template unit's Toughness / Wounds / Save / invulnerable save (section 3
  table, checked against the BSData catalog verbatim).
- Live Feel No Pain values: Mortarion 5+, Poxwalkers 5+, Plaguebearers 5+ (all
  real); Plague Marines, Blightlord Terminators, Deathshroud Terminators, Typhus
  none (matching their datasheets).
- Disgustingly Resilient as a 2-command-point stratagem with subtract-1-Damage,
  INFANTRY/CHARACTER scope, VEHICLE and MONSTER excluded
  (`_try_disgustingly_resilient`).
- Worldblight (Virulent Vectorium) sticky-objective half, with the
  contagion-on-objective half documented as an approximation
  (`data/rule_citations.d/death_guard.json`).
- Plaguesurge extending Contagion Range by 3 inches for a round (stratagem,
  round-scoped flag).
- Mortarion, Lord of Contagion, and Daemon Prince of Nurgle defensive statlines.

## Win-shape verdict

**Scoring-shaped, with numbers.** Across 312 replayed anchor games (100 percent
winner reproduction): Death Guard survival 23.3 percent versus opponent 31.9
percent — it out-dies its opponents while out-scoring them on primary objectives
(+5.46 average margin overall, +18.70 in its wins) with a NEGATIVE secondary
margin (−1.40). A durability audit cannot close this over-pole because the
defensive economy is already faithful and the army does not actually out-survive
anyone; the over-pole lives in primary-objective uptime through the scoring
snapshot (durable pillars plus faithful sticky objectives), the structural
representation question already teed up for the owner. The one faithful lever
this audit adds to that discussion: completing the UNDER-modelled army rule
(divergences D1–D3) would push Death Guard further UP, so any structural remodel
should account for the fact that the faction's rules-fidelity deficit currently
masks part of the very over-pole being corrected.
