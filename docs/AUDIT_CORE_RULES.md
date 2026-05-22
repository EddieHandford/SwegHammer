# 10e Core Rules Audit — Wahapedia vs SwegHammer (Track A)

HEAD `b4b2bd1`. Compared https://wahapedia.ru/wh40k10ed/the-rules/core-rules/
against `code/simulator.py` + `code/units.py` + `code/map.py` + `code/army.py`.
Supersedes `docs/CORE_RULES_AUDIT.md` (HEAD 945c840) for items now landed.

Classification: **FULL** (rule modelled to within abstraction floor),
**PARTIAL** (modelled with documented approximation), **MISSING** (no
implementation), **WRONG** (implemented but contradicts canonical text).

MAE delta is relative to current eval; signs indicate direction of nudge a
fix would produce. Complexity: **S** ≈ ≤30 LOC, **M** ≈ 30-150 LOC,
**L** ≈ 150+ LOC or new state.

---

## Movement phase

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Normal Move (M") | per-model, cohesion 2" | per-Unit move via `_move_toward`; cohesion auto (1 model = 1 Unit) | FULL | — | — |
| Advance | M + D6, no shoot/charge unless [ASSAULT]/Battle Focus/doctrine | `_do_move` rolls d6, `_advanced_this_round` gates `_do_shoot` & `_do_charge`. Aeldari Battle Focus, Mont'ka [ASSAULT], Gladius Devastator/Assault, Aggressive Mobility, Feigned Retreat, transient_assault_this_round all wired (sim 3669-3687, 3892-3902). | FULL | — | — |
| Fall Back | Normal move out of engagement; no shoot/charge unless FLY; Desperate Escape 1D6/model, 1=destroyed | `_do_move` FALL_BACK intent (sim 3525), `fell_back_this_round` flag, FLY exemption, 1D6 desperate escape (one roll per Unit since 1 model per Unit). | PARTIAL | low | — |
| Charge: 2D6 + mods, declare → charge target ≤12" | declare multi-target, roll 2D6, must reach 1" of every target | Strands of Fate substitution wired (sim 3919); single-target charge only (no multi-target); `pick_charge_target` heuristic decides. Charge bonuses (+1 from buffs/det) NOT applied to the 2D6 — only Fate dice mutates the roll. | PARTIAL | low | M |
| Engagement range = 1" | hardcoded core rule | Simulator uses **1.5"** as engagement floor (`sim:3702`, `sim:3984`). Charge ends at 1" but engagement check is 1.5". Mostly invisible but inflates "shooting blocked by engagement" by ~33% area. | WRONG | low | S |
| FLY | ignores vertical for movement; lets unit Fall Back + shoot/charge | `UnitProfile.fly` derived from FLY keyword; Fall Back exemption wired (`sim:3654, 3900`). Vertical FLY interactions N/A (no 3D map). | FULL | — | — |
| Deep Strike (Strategic Reserves) | arrives Round 2+, >9" from enemy | `_arrive_from_reserves` (sim:2742), R2+ default, ambush gate for GSC R1, mass-drop anchor + scoring. | FULL | — | — |
| Strategic Reserves (general, non-DS) | up to 25% of army may be placed in Strategic Reserves; arrives R2-4 with 9" rule depending on board edge | **MISSING** — only Deep Strike-flagged units enter reserves. Generic Strategic Reserves (Infiltrators/Marines/Guard often hold a unit) has no entry point. | MISSING | low-med | M |
| Reinforcements timing | Generic "Reinforcements" rule for units returning to play | Conflated with Reanimation / DS arrival paths. No general reinforcements gate. | MISSING | low | S |
| Towering | LoS through everything; can be drawn through walls for shooting | **MISSING** — `Map.has_line_of_sight` does not check Towering. Affects Knights, C'tan, Wraithknights, Mortarion, Greater Daemons. | MISSING | medium | M |
| Pile-In (3" toward closest enemy at start of Fight) | mandatory free 3" pile-in | **MISSING** — `_do_fight` (sim:3964) attacks straight from current position; no pile-in step. Means engagement that's "almost" within 1.5" never resolves into combat. | MISSING | medium | M |
| Consolidate (3" after Fight) | mandatory 3" toward closest enemy / objective | **MISSING** — no post-fight reposition. Hurts melee factions on objective grabs after the fight. | MISSING | medium | M |
| Heroic Intervention (3" core move, not strat) | core ability for CHARACTERS, 3" into 1" of charger | Implemented as **stratagem** via `_try_heroic_intervention` (sim:4661, 1 CP). Real 10e: it's an end-of-charge core action with no CP cost. | WRONG | low | S |

## Combat — to-hit, to-wound, save, AP

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Hit / Wound rolls | nat 1 fails, nat 6 succeeds + Critical | nat 1 fail / nat 6 = `crit_hit`/`crit_wound` (units 1123, 1148). | FULL | — | — |
| Modifier cap ±1 to hit | hit-roll modifiers cannot stack past ±1 | DG Contagion R3+ check guards against stacking with prior penalty (units 885-891) **only**. Heavy + Big Guns + Indirect + Heavy Cover + Stealth ALL compound without cap (each adds `min(7, hit_target+1)` unconditionally). | WRONG | low-med | S |
| Modifier cap ±1 to wound | same +/- cap on wound rolls | Not enforced. +1-to-wound buffs (Twist of Fate, Plague Weapons, Lance, WAAAGH!) stack with detachment +1; -1 (All Is Dust) stacks with everything. | WRONG | low | S |
| AP / save / cover / invuln stacking | save + AP + cover (max +1), invuln vs effective save min | `save_probability` + cover +1 (`units:127`); invuln via `min(save_after_ap, invuln)` (units:930). Cover stacks with `tgt_buffs[plus_one_save]` + `transient_plus_one_save` — both lower save_after_ap independently (no +1 cap). | PARTIAL/WRONG | low | S |
| Lethal Hits | crit-to-hit auto-wounds | First crit per shot auto-wounds (units 1127). Sustained extras don't auto-wound. | FULL | — | — |
| Sustained Hits N | crit-to-hit = +N normal hits | `effective_sustained_hits` (units 1124). | FULL | — | — |
| Devastating Wounds | crit-to-wound = mortal wounds | Bypasses saves; applies via receive_damage (units 1190). 10e core: D-Wounds are now MWs allocated like normal damage. Implementation OK. | FULL | — | — |
| Anti-X N+ | crit-wound threshold lowered vs keyword | `anti_keywords` tuple (units 894-899). Wound roll ≥ threshold = crit wound (units 1181). | FULL | — | — |
| Precision | allocates to attached CHARACTER | Only used to **bypass cover vs CHARACTER target** (units 905-909). 10e: bypasses Look Out Sir + lets attacker pick the CHARACTER model. Look Out Sir bypass not implemented. | PARTIAL | low | S |
| Twin-Linked | re-roll failed wound | Single re-roll, doesn't stack with full re-roll (units 1149). | FULL | — | — |
| Blast | +1 attack per 5 models in target | `same_squad` count via `army_ref.alive_units` (units 678). 1-Unit-per-model convention means "squad" = N units sharing profile name. | FULL | — | — |
| Hazardous | nat 1 = 3 MW to attacker | Per-shot? No — once per activation (units 1219). Real rule: once per phase per weapon. Acceptable approximation. | PARTIAL | trivial | — |
| Indirect Fire | LoS bypass, -1 to hit, no cover for target | `has_los=False` path; -1 to hit applied (units 851). No-cover-bonus for indirect targets NOT enforced. | PARTIAL | low | S |
| Melta N | +N damage at half range | `per_shot_dmg += p.melta` (units 675). | FULL | — | — |
| Heavy | +1 to hit if no move | `not self.moved_this_round` (units 840). | FULL | — | — |
| Pistol | can shoot in engagement | `_do_shoot` engagement check (sim:3707). | FULL | — | — |
| Assault | shoot after Advance | `p.assault` exempt (sim:3669). | FULL | — | — |
| Rapid Fire N | +N at half range | `n_attacks += rapid_fire` (units 674). | FULL | — | — |
| One Shot | once per battle | `_one_shot_fired` set (sim:3690). | FULL | — | — |
| Ignores Cover | bypass cover save | `ignore_cover` flag (units 644). | FULL | — | — |
| Torrent | auto-hit | `crit_hit = False; n_hits=1` skips to-hit (units 1072-1074). 10e: Torrent ignores hit modifiers — fine. | FULL | — | — |
| Big Guns Never Tire | VEHICLE/MONSTER may shoot in engagement at -1 to hit | `shooting_in_engagement` (sim:3710, units:846). | FULL | — | — |

## Terrain (user-flagged focus)

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Light Cover (Benefit of Cover, +1 save) | +1 save vs ranged, max 2+ | `TerrainType.LIGHT_COVER` sets `in_cover` (sim:3795), +1 save (units 910). | FULL | — | — |
| Heavy Cover | +1 save AND -1 to hit | `in_heavy_cover` flag, both effects applied (units 862, 910). | FULL | — | — |
| Obscuring | blocks LoS unless either endpoint inside | `has_line_of_sight` skips obscuring containing endpoint (map:104-109). 10e: tall obscuring is total; small obscuring blocks below 2". Single-tier model — fine. | PARTIAL | none | — |
| Ruins — INFANTRY shoot through walls | INFANTRY can draw LoS through Ruin walls; non-INFANTRY cannot | **MISSING** — Ruins are modelled as HEAVY_COVER + no through-wall LoS distinction. INFANTRY pay the same LoS cost as a Land Raider. Substantial: hurts infantry-heavy factions (Marines, Guard, Sisters, Custodes) and inflates ranged effectiveness for big-base shooters that should be blocked. | MISSING | high | M-L |
| Ruins — movement penalty for non-INFANTRY | Vehicles cannot enter; Walkers must declare top/bottom floor | **MISSING** — `is_blocked` only checks IMPASSABLE. Ruins are walkable by anyone. | MISSING | medium | M |
| Difficult / Dense terrain | Difficult: halve movement through; Dense: -1 to hit shooting through 2"+ | **MISSING** — no terrain type for difficult/dense. Cover-only model. | MISSING | low-med | M |
| Hills / elevation | Vantage point grants LoS over intervening; combat at elevation | **MISSING** — 2D map only, no Z. Affects skirmishes where high ground matters (gunlines on a hill). | MISSING | high (2D limit) | L |
| Walls / impassable | Block movement | `IMPASSABLE` blocks `is_blocked` (map:71-75). | FULL | — | — |
| Towering — visible-through-everything keyword | Towering units always grant + receive LoS over terrain | **MISSING** — see Movement table. | MISSING | medium | M |

**Top terrain gaps for MAE**: Ruins infantry-through-walls (#1) — currently INFANTRY-heavy armies are double-debuffed (cover save vs ranged + blocked LoS for return fire when actually they should be the ones who CAN see). Followed by Towering, then Difficult/Dense.

## Phase / round structure

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Command phase: CP +1, battleshock, rituals, doctrines, oath | drip CP, rituals, doctrines | `_run_round` does: CP drip (sim:3116), WAAAGH! decl, PFP tokens, Doctrina, Oath of Moment, Blood Tithe, transient clear, battle-shock, detachment strats, cabal rituals, markerlights. | FULL | — | — |
| Battle round = I-go-you-go | Player A whole turn, then Player B | Default `RulesConfig.vanilla_10e` uses `_run_round_vanilla_turns` (sim:3438) — true I-go-you-go. SwegHammer mode optional alternating. | FULL | — | — |
| Pile-in (3") | start of Fight phase, mandatory | **MISSING** — see Movement table. | MISSING | medium | M |
| Consolidate (3") | end of fight per unit | **MISSING** — see Movement table. | MISSING | medium | M |
| Heroic Intervention (3" core, free) | core CHARACTER 3" ability when an enemy ends a charge within 6" | Implemented as 1 CP stratagem (`_try_heroic_intervention`). Wrong cost model. | WRONG | low | S |
| Fights First (charged) | charger fights first sub-phase | `_charging_this_round` is tracked and (post CORE-RULE-FIX-1) used to sort chargers ahead of non-chargers within `_run_round_vanilla_turns`' active player fight pass. `_run_round_alternating` still resolves fights pair-by-pair, no two-pass sequencing there. Datasheet-level FIGHTS FIRST (Wyches, Custodian Wardens) still not flagged. | PARTIAL | medium | M |
| Fights First (other sources) | abilities like Marines Litany, Eldar power | Not implemented as a separate flag. Treated as plain activation. | MISSING | low | S |
| Counter-Offensive (2 CP, defender's out-of-sequence fight) | out-of-sequence fight after attacker's fight | `_try_counter_offensive` (sim:4019) fires after attacker fights AND kills. Real rule: fires regardless of kill, on any enemy fight, defender unit eligible. Eligibility gate is too restrictive. | PARTIAL | low | S |

## Mission / objectives

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Primary scoring per round | 5 VP per held objective, capped at 15 / round (Pariah) | `_score_objectives` (sim:522) awards `vp_per_round=5` per held. No 15-cap-per-round; an army holding 4 objectives at 5 VP = 20 VP/round. | WRONG | low | S |
| Objective placement | 4-6 markers per mission template | `_quincunx_objectives` always 5 (maps:13). Reasonable. | FULL | — | — |
| Control range (3") | radius for OC check | `Objective.control_radius=3.0` (map:55). | FULL | — | — |
| Sticky objectives (BATTLELINE) | unit with sticky stays on after leaving | `sticky_objective` flag + `_sticky_owner` dict (sim:603-617). | FULL | — | — |
| Battle-line keyword | many missions grant Sticky to BATTLELINE | sticky_objective set explicitly per profile, not by BATTLELINE keyword. So Guardsmen/Boyz/etc don't auto-sticky from BATTLELINE. | PARTIAL | medium | S |
| Secondary objectives (Take and Hold, BEL, etc.) | scored alongside primary, fixed/tactical | **MISSING** — no secondary scoring. Sim only awards Primary VP. Real games are ~50% determined by secondaries. | MISSING | high | M-L |
| Mission rules (Pariah Nexus suite) | per-mission special rules | **MISSING** — single mission template (5 quincunx objectives, no per-mission modifiers). | MISSING | medium | M |

## Battle-shock + Leadership

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Battle-shock at end of Command phase, below half strength | 2D6 vs Ld | `_run_battleshock_phase` (sim:2981) — fires R2+, 2D6 vs Ld, populates `_battleshocked_this_round`. Skipping R1 is **WRONG** (real rule fires every Command phase from R1 onward). | WRONG | low | S |
| Failure: OC=0, can't be subject of strats, lose primary | OC 0 + strat-target exclusion | `_battleshocked_this_round` blocks OC contribution (`sim:556, 571`) and strat-target picks (sim 901, 944, 974). Primary VP forfeit not modelled. | PARTIAL | low | S |
| Mob Rule (Orks) | 10+ Orks army-wide auto-pass | `mob_rule_active` (sim:3017). | FULL | — | — |
| Synapse | within 6" of SYNAPSE = auto-pass | own_synapse + 6" check (sim 3018-3021, used at sim 3040). | FULL | — | — |
| Shadow in the Warp | enemy within 12" of Tyranid SYNAPSE = -1 to test | shadow_sources (sim:3022). | FULL | — | — |
| Their Number Is Legion (Necron) | Necron auto-pass when on objective | **MISSING** — no Necron Battle-shock immunity gate. | MISSING | low | S |
| Marines Litany of Hate / Astartes | various litanies grant immunity / fight-first | **MISSING** — no per-Chapter litanies. | MISSING | low | M |
| Cult Ambush — GSC ambushers | not directly Battleshock; just deep-strike R1 | Cult Ambush is wired (sim:2770). | FULL | — | — |

## Deployment

| Mechanic | Wahapedia | SwegHammer | Class | MAE Δ | Cmplx |
|---|---|---|---|---|---|
| Strike Force default 2000 pts | standard tournament | `STARTING_CP=3` Strike Force standard (stratagems:833). Battle Focus pool fixed at 4 (Aeldari) regardless of points budget. | FULL | — | — |
| Deployment zones | 12" deep from short edge in most missions | `deployment_width=12.0` (map:68). | FULL | — | — |
| Scouts | pre-game Normal Move up to N" | `_run_scout_phase` (sim:2716). | FULL | — | — |
| Infiltrators | place outside enemy DZ, >9" from enemy | `_deploy_armies` puts infil at halfway-to-centre (sim:2683-2693). 9" check is by-deployment-line heuristic, not per-enemy. | PARTIAL | low | S |
| Strategic Reserves (non-DS placement) | up to 25% of army | **MISSING** — see Movement table. | MISSING | low-med | M |

## Other findings

- `pile-in`, `consolidate`, generic Reinforcements: no implementation.
- Heroic Intervention as core: implemented as stratagem.
- Modifier ±1 caps: only enforced for DG Contagion stacking; otherwise compound.
- Engagement-range geometry uses 1.5" instead of 1".
- Look Out Sir / Lone Operative: FULL (army.can_target_for_ranged).
- Embarked transports: FULL (embark/disembark/firing deck wired, sim:3502, 4508).
- Combat Doctrines (Marines Gladius): FULL (movement utility only — iter-9 fix removed fabricated wound buff).

---

## Top 10 ranked fixes by expected MAE impact

| # | Mechanic | Class | MAE Δ direction | Complexity |
|---|---|---|---|---|
| 1 | **Ruins INFANTRY-through-walls LoS** | MISSING | LARGE — affects every Marine/Guard/Sisters/Custodes vs vehicles match. Currently both sides equally LoS-blind but real rule asymmetrically buffs INFANTRY return fire. | M-L |
| 2 | **Modifier ±1 cap on hit and wound rolls** | WRONG | MEDIUM-LARGE — five hit-roll penalties (Heavy cover + Stealth + Indirect + Big Guns + Contagion) currently stack to -4/-5; real cap is -1. Inflates miss rate on debuffed targets, deflates on stacked-buff attackers. | S |
| 3 | **Pile-In + Consolidate** | MISSING | MEDIUM — melee units 1.5"-3" from target never resolve combat; objective-flip plays after melee never happen. Affects melee factions (Orks, World Eaters, Custodes, Aeldari Banshees). | M |
| 4 | **Secondary objectives (Pariah suite, fixed + tactical)** | MISSING | MEDIUM — secondaries are ~half the real VP economy. Currently every game is decided on primary alone → favours objective-camping armies, hurts mobility/scoring archetypes (GSC, Drukhari, Aeldari). | M-L |
| 5 | **Battle-shock from R1, not R2+** | WRONG | SMALL-MEDIUM — wounded R1 units never battle-shock-tested. Mostly nudges sim toward more aggressive R1 attrition, no battleshock fail = OC denial in R1. | S |
| 6 | **Fights First proper sequencing (chargers in first sub-phase)** | WRONG | SMALL-MEDIUM — currently activation-order dictates fight order, so a non-charger can fight before a charger if it activates first. Hurts chargers vs counter-chargers. | M |
| 7 | **Primary VP cap (15 per round)** | WRONG | SMALL-MEDIUM — armies holding 4-5 objectives currently score 20-25 VP/round instead of 15. Inflates objective-flooding archetypes. | S |
| 8 | **Engagement range 1" not 1.5"** | WRONG | SMALL — overstates the "locked in melee" radius by ~33% area. Small but pervasive. | S |
| 9 | **Heroic Intervention as core 3" move (not stratagem)** | WRONG | SMALL — currently costs 1 CP to fire; real rule is free for any CHARACTER. Underuses HI, leaks CP on a non-charge phase. | S |
| 10 | **Towering keyword (LoS through everything)** | MISSING | SMALL-MEDIUM — affects ~10 datasheets across all factions (Knights, C'tan, Greater Daemons, Mortarion). Direction: buffs Towering-bearing big-base factions. | M |

### Honourable mentions (deferred / lower-confidence)

- Strategic Reserves (non-DS, 25% rule) — MISSING — uncertain MAE.
- Marines Litanies, Necron "Their Number is Legion", per-faction battle-shock auto-passes — MISSING — small per-faction impact.
- Ruins movement penalty for non-INFANTRY — MISSING — moderate.
- Difficult/Dense terrain types — MISSING — small.

Citations all under https://wahapedia.ru/wh40k10ed/the-rules/core-rules/. Where a mechanic crosses with a faction rule (Marines Doctrines, DG Contagions, etc.) the codex Wahapedia URL applies — see `data/rule_citations.d/`.
