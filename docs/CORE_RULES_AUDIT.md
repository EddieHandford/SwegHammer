# 10e Core Rules Audit — Wahapedia vs SwegHammer

Compared https://wahapedia.ru/wh40k10ed/the-rules/core-rules/ against this
codebase at HEAD `945c840`. Output is a punch-list keyed by MAE impact.

## Already implemented (✓)

| Rule | Where |
|---|---|
| Hit / Wound / Save / Invuln / Mortal Wounds | `code/units.py:Unit.attack` |
| AP, save floor 2+ | `code/units.py:480` |
| FNP | `code/units.py:200`, runtime apply in `attack` |
| Stealth | `code/units.py:195` |
| All 18 weapon keywords | `code/units.py:171-193` (assault, heavy, pistol, rapid_fire, twin_linked, ignores_cover, torrent, lethal_hits, lance, melta, anti_X, sustained_hits, devastating_wounds, precision, blast, indirect_fire, hazardous, one_shot) |
| Cover (light + heavy + obscuring) | `code/simulator.py`, `simulator.cover_light` / `simulator.cover_heavy` cited |
| Big Guns Never Tire | `code/units.py`, `simulator.big_guns_never_tire` |
| Sticky Objectives | `simulator.sticky_objective` |
| Deep Strike / Scouts / Infiltrators | `simulator.deep_strike` / `simulator.scout` / `simulator.infiltrators` |
| Battle-shock + Mob Rule | `code/simulator.py:1289`, `simulator.battleshock` / `simulator.mob_rule` |
| Heroic Intervention, Counter-Offensive, Command Re-Roll, Tank Shock | `code/stratagems.py`, `code/simulator.py:1759/1803` |
| CP economy (3 start, +1/rd, cap 6) | `code/stratagems.py:STARTING_CP` |
| WAAAGH!, Reanimation, Cabal Points, Judgement Tokens, Battle Focus, Awakened Dynasty | per-faction citation files |
| Aura range from leaders | `code/leaders.py:LeaderAbility(aura_range=6.0)` |

## Tier 1 — Missing core rules with biggest MAE-closing potential

### 1.1 Death Guard "Disgustingly Resilient" army-wide FNP 5+ — **MISSING as army rule**
- Currently lives **only as a one-shot stratagem** (`code/stratagems.py:152`).
- Canonical: every Death Guard model has FNP 5+ ALL THE TIME (army rule).
- Compounded by mapper bug #142 which is dropping `fnp` even where it should be parsed.
- **Direction**: Death Guard at sim -8.0 (way too weak). Adding the army-wide FNP 5+ would close this huge.
- **Priority**: HIGHEST. Wait for #142 to land first, then wire the army rule.

### 1.2 Thousand Sons "All Is Dust" — **MISSING**
- Canonical: each TSON unit subtracts 1 from incoming Wound rolls of attacks with Damage 1.
- Affects Rubric Marines (the entire TSON troops line), Scarab Occult, etc.
- Not in codebase. Grep for `all_is_dust` returns nothing.
- **Direction**: TSON at sim -4.6 (too weak). Adding this caps 1-damage offence vs them → BUFFS them. Positive for MAE.
- **Priority**: HIGH. Self-contained per-attack gate in `Unit.attack`.

### 1.3 Death Guard "Contagions" aura — **MISSING as army rule**
- Canonical: enemy units within 6" of any DG model are at -1 Toughness OR -1 Ld OR -1 Strength (escalates by round in 10e).
- Currently only exists as detachment stratagems, not as the always-on contagion bubble.
- **Direction**: BUFF Death Guard further. Stacks with #1.1 to close -8.0 gap.
- **Priority**: HIGH.

## Tier 2 — Missing mechanics that affect multiple factions

### 2.1 Fall Back + Desperate Escape Test — **MISSING entirely**
- Canonical: a unit in Engagement can elect a Fall Back move (instead of Normal Move). Can't shoot or charge that turn. Falling Back through enemy models triggers Desperate Escape Test (1d6 per model, 1 = remove that model). 
- In our sim, charged ranged units are stuck and lose their shooting. IRL, T'au / Aeldari / Marines disengage routinely.
- **Direction**: mixed. T'au (+11.4) and Aeldari (+12.3) would gain disengage option but lose attrition + a turn of shooting. Net unclear without testing.
- **Priority**: MEDIUM. Big surface area to implement (movement + AI + stratagem gate "Heroic Tag Team-like"). Defer unless other tier-1 work doesn't close MAE.

### 2.2 Deadly Demise X — **MISSING**
- Canonical: when a model with this ability is destroyed, roll 1d6 per unit within 6"; on 6, that unit suffers X mortals.
- Affects Custodes (Caladius, Telemon, Sky Talons), Marines (Dreads, Repulsors), T'au (Battlesuits with Demise 1), Necrons (Doomsday Ark), Astra Militarum (every tank).
- **Direction**: taxes vehicle stacking. Custodes (+3.5) and T'au (+11.4) currently over-perform — Deadly Demise would weaken them slightly. Slight positive.
- **Priority**: MEDIUM. Small implementation: emit a `_apply_deadly_demise` hook when a `VEHICLE` or `MONSTER` Unit dies, scan nearby enemies, roll, apply mortals.

### 2.3 Look Out Sir / Lone Operative — **MISSING**
- Look Out Sir: CHARACTER within 3" of a non-CHARACTER bodyguard can't be directly targeted by ranged unless attacker is within 12".
- Lone Operative: 12" targeting restriction for select solo characters (Eversor, Lictor, Callidus, Vindicare).
- **Direction**: makes support characters more durable → buffs leader-aura economies. Cross-faction effect; modest individual impact.
- **Priority**: LOW-MEDIUM. Wire via a `_can_target_for_ranged(target)` gate in target selection.

## Tier 3 — Missing but lower priority

### 3.1 Transports (Embark / Disembark / Firing Deck)
- Marines (Rhinos, Repulsors, Impulsors), T'au (Devilfish), Custodes (Caladius), Aeldari (Wave Serpents) deliver units 6" + 3" further.
- Huge implementation surface (transport state, embark events, disembark restrictions, Firing Deck attack proxying).
- **Direction**: buffs vehicle-heavy mobility factions. Marines (+0.5 — fine), T'au (+11.4 — bad direction), Custodes (+3.5 — bad). Net negative for MAE.
- **Priority**: DEFER unless we want detachment-list veracity (Goal A polish). Goal C calibrator can absorb the missing-transport effect into points.

### 3.2 Coherency (2" within model)
- We model squads as N independent Units, so coherency is automatic / doesn't apply.
- No action needed.

### 3.3 Engagement Range exact geometry (1" horizontal, 5" vertical)
- We use 1.5" flat. The 5" vertical case (multi-story terrain) doesn't apply on our 2D map.
- **Verdict**: captured.

### 3.4 Re-rolls happen before modifiers
- Our code re-rolls 1s and re-rolls failures. Sequencing matches 10e (we don't apply +1 then re-roll the new value).
- **Verdict**: captured.

## Tier 4 — Implementation divergences to verify (no new rule, possible bugs)

### 4.1 Battle-shock target — does `profile.leadership` populate from BSData?
- Our test: `_run_round` does `2d6 vs profile.leadership` for units `current_health < profile.health/2`.
- If `profile.leadership` is dropping silently on common units, our Battle-shock fires the wrong way.
- **Spot-check needed**: print Ld values for Boyz, Cultists, Guard Squad, Termagants. If any look wrong, escalate to mapper.

### 4.2 Aura range gate consistency
- `LeaderAbility.aura_range` is 6.0" canonically. Verify the runtime check actually computes distance and compares.

## Recommended next tasks (mapped to MAE-closing potential)

| New task | Goal-A target | Expected MAE direction |
|---|---|---|
| A14 Death Guard army-wide FNP 5+ | -8.0 → ~-3.0 | huge improvement (depends on #142 landing first) |
| A15 Thousand Sons All Is Dust | -4.6 → ~-1.5 | strong improvement |
| A16 Death Guard Contagions aura | DG further uplift | moderate improvement |
| A17 Deadly Demise X | Custodes / T'au down | moderate improvement |
| A18 Fall Back + Desperate Escape | T'au / Aeldari mixed | uncertain, may regress |
| A19 Look Out Sir + Lone Operative | support-character durability | minor |

Source: this audit. Citations to be added as tasks are picked up (Wahapedia URLs all
under https://wahapedia.ru/wh40k10ed/factions/ + the relevant codex).
