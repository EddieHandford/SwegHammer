# Core rules coverage audit (10e)

Coverage matrix mapping the Wahapedia 10e core rules
(https://wahapedia.ru/wh40k10ed/the-rules/core-rules/) to SwegHammer
simulator state. Driven by the observation in `code/detachments.py:767`
that the sim has "no embark / disembark cycle" — likely one of several
core-rule gaps contributing to gated MAE.

Status legend:
- ✓ implemented (cite file:line)
- ◐ partial (cite + gap note)
- ✗ not implemented
- ⚠️ unverified (flag exists, simulator wiring unconfirmed by this audit)

## 1. The Battle Round

| Rule | Status | Where / gap |
|---|---|---|
| Command phase (CP gain, stratagems) | ✓ | `simulator.py:_run_round`, `_apply_detachment_stratagems` |
| Movement phase | ✓ | `simulator.py:_do_move` |
| Shooting phase | ✓ | `simulator.py:_do_shoot` |
| Charge phase | ✓ | `simulator.py:_do_charge` |
| Fight phase | ✓ | `simulator.py:_do_fight` |
| Alternating activations (SwegHammer mod) | ✓ | `simulator.py:_run_round_alternating` (opt-in via `RulesConfig.sweghammer`) |
| Vanilla I-go-you-go | ✓ | `simulator.py:_run_round_vanilla_turns` (default) |

## 2. Movement

| Rule | Status | Where / gap |
|---|---|---|
| Normal Move | ✓ | `simulator.py:_do_move` |
| Advance (+D6") | ⚠️ | Flag-driven; verify D6 distribution applies |
| Fall Back | ✓ | `simulator.py` `fell_back_this_round` flag, `_pick_fall_back_destination` |
| Remain Stationary | ✗ | No explicit modeling — units always move toward target. Affects Heavy weapon stationary bonus and certain stratagems |
| Engagement Range (1") | ✓ | `simulator.py:6141` |
| Pile In + Consolidate (3" free moves) | ✓ | `simulator.py:6115` |

## 3. Shooting

| Rule | Status | Where / gap |
|---|---|---|
| Hit / Wound / Save / Damage | ✓ | `units.py:Unit.attack` |
| Look Out, Sir (CHARACTER protection in unit) | ✓ | `simulator.py:5719` |
| Lone Operative (12" targeting restriction) | ✓ | `simulator.py:5719`, `units.py:389` |
| Stealth (-1 to hit > 12") | ✓ | `units.py:2032` |
| Big Guns Never Tire (VEHICLE/MONSTER shoot in engagement) | ✓ | `simulator.py` `shooting_in_engagement` flag |
| Indirect Fire | ✓ | `units.py:1984`, `simulator.py:5700` |
| Cover (Light / Heavy) | ⚠️ | `in_cover` / `in_heavy_cover` flags on Unit; verify the +1 save / -1 to-hit application path |
| Line of Sight (terrain blocking) | ⚠️ | `_nearest_obscuring_centre` in `strategy.py:299`; verify true-LoS test happens at hit time |
| **Wound allocation order (closer model first)** | ✗ | No `_allocate_damage`, `closer_model`, or `wound_allocation` references. Affects screening: weak front models should soak first, sim probably allocates evenly |

## 4. Weapon abilities

| Keyword | Status | Where / gap |
|---|---|---|
| Pistol (shoot in engagement) | ⚠️ | Flag exists; verify it gates engagement-range shooting separately from BGNT |
| Heavy (+1 hit when stationary) | ⚠️ | Flag exists; depends on Remain Stationary modeling |
| Rapid Fire X (extra shots at half range) | ✓ | `units.py:rapid_fire` flag, attack-time application |
| Assault (shoot after Advance) | ⚠️ | Flag exists; verify the post-Advance shoot path |
| Anti-X (improved wound roll vs keyword) | ✓ | `anti_keywords` tuple, damage path |
| Blast (more shots vs large units) | ⚠️ | Flag exists; verify model-count scaling |
| Devastating Wounds (Crits → mortal) | ✓ | `devastating_wounds` flag, attack path |
| Hazardous (D6 self-harm) | ✓ | `units.py:3024` |
| Ignores Cover | ✓ | `ignores_cover` flag |
| Lance (+1 wound on charge) | ⚠️ | Flag exists; verify per-charge gating |
| Lethal Hits (Crit-6 = auto-wound) | ✓ | `lethal_hits` flag |
| Melta X (extra damage at half range) | ⚠️ | Flag exists; verify half-range gate |
| One Shot | ⚠️ | Flag exists |
| Precision (target attached CHARACTER) | ⚠️ | Flag exists; verify it bypasses Look Out, Sir |
| Sustained Hits X | ✓ | `sustained_hits` flag, attack path |
| Torrent (auto-hit) | ⚠️ | Flag exists |
| Twin-linked (re-roll wound) | ✓ | `twin_linked` flag, attack path |

## 5. Charge phase

| Rule | Status | Where / gap |
|---|---|---|
| Declare charge | ✓ | `simulator.py:_do_charge` |
| 2D6 charge distance | ⚠️ | Verify distribution matches 2D6 not flat / linear |
| Heroic Intervention | ✓ | `simulator.py:_do_heroic_intervention` (reactive after enemy charge) |
| Overwatch (defensive shoot on enemy charge) | ⚠️ | Stratagem flagged; verify reactive firing path |
| **Counter-charge (proactive defensive)** | ✗ | No explicit logic; AI charges offensively only |

## 6. Fight phase

| Rule | Status | Where / gap |
|---|---|---|
| Fight First / Last | ✓ | `fights_first` flag, activation-order gate |
| Tank Shock | ⚠️ | Stratagem flagged; verify proactive use |

## 7. Battle-shock

| Rule | Status | Where / gap |
|---|---|---|
| Battle-shock test (below half strength) | ✓ | `simulator.py:_run_battleshock_phase` |
| **OC = 0 while Battle-shocked** | ✗ | No matches for `shocked.*oc` or `oc.*shock`. Affects objective scoring directly — Battle-shocked units should not contribute to OC |
| Stratagems unusable while Battle-shocked | ⚠️ | Verify the gate |

## 8. Reinforcements

| Rule | Status | Where / gap |
|---|---|---|
| Deep Strike | ✓ | `simulator.py:_pick_arrival_point`, `_run_scout_phase` |
| Scout X" | ✓ | `simulator.py:_run_scout_phase` |
| Infiltrators (9" from enemy at deployment) | ✓ | `infiltrator` flag on profile |
| **Strategic Reserves (arrive turn 2-3, anywhere)** | ✗ | No `strategic_reserve`, `reserves_until`, `arrives_round` references. Conflated with Deep Strike (which lands within 9" of enemy); Strategic Reserves can come on a board edge, no 9" restriction. Affects all factions with reserve-heavy lists |

## 9. Transports

| Rule | Status | Where / gap |
|---|---|---|
| **Embark / Disembark cycle** | ✗ | **Acknowledged in `detachments.py:767` and `archetypes.py:133`.** Cargo deploys un-embarked and acts every turn; transports operate independently. Highest-leverage structural gap. Phase 2 EMBARK-V1 target |
| Firing Deck X (passengers shoot from transport) | ✓ | `simulator.py:6826` `_apply_firing_deck` — gated on `firing_deck > 0` and embarked passengers (but no passengers ever embarked, so this path never fires today) |
| Emergency disembark on transport destruction | ✗ | Couples with Embark-V1 |

## 10. Aircraft & Towering

| Rule | Status | Where / gap |
|---|---|---|
| **Aircraft Zooming (mandatory 20" straight, no ground)** | ✗ | Only referenced in detachment text. Affects ~3 factions with Aircraft (T'au Tigersharks, IG Valkyries, Aeldari Crimson Hunters) |
| **Aircraft Hover (switch to ground)** | ✗ | Same |
| **Towering / Titanic line-of-sight benefit** | ◐ | `code/bsdata/mapper.py:1657` and `code/renderer.py:268` use TITANIC/TOWERING for base sizing only. Simulator doesn't grant LoS-over-terrain to Towering units. Affects Knights (already structurally parked at -26/-39 gated) and Tyranids Hierodule/Tervigon |

## 11. Mission / Scoring

| Rule | Status | Where / gap |
|---|---|---|
| Primary VP (objective control) | ✓ | `simulator.py:_score_objectives`, gated rounds 2-5 per PRIMARY-VP-AUDIT |
| **Pariah Nexus Secondary selection (pick 2 of 4 Fixed, or Tactical)** | ✓ | `secondaries.pick_secondaries` picks 2 Fixed + 2 Tactical per army at battle start (heuristic on enemy MONSTER/VEHICLE count + own FLY/MOUNT count). `Army.chosen_secondaries` tuple is read by `simulator._score_secondaries` to gate `score_round_delta` / `score_position_delta` — only picked secondaries score VP. Implemented in iter 44 SECONDARY-SELECTION-V1 |
| Sticky Objectives | ✓ | `simulator.py:293, 593, 609` |
| Battle-shock impact on objective control | ⚠️ | Depends on OC=0-while-shocked (gap above) |

## 12. CP / Stratagems

| Rule | Status | Where / gap |
|---|---|---|
| 1 CP per Command phase | ✓ | `stratagems.py:1352`, `simulator.py` |
| Stratagem affordability gate | ✓ | `simulator.py:6898`, `strategy.py:2844` |
| **Multiple stratagems per phase per army** | ◐ | iter44 STRATAGEM-CHAIN-V1: `DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` widened from 1 to 2 in `_apply_detachment_stratagems`. Tournament play stacks 2-3 strats on alpha-strike units; the 3+ stack is still parking-lot work |
| Once-per-phase / once-per-game limiters | ⚠️ | Verify per-stratagem state tracking |
| Heroic Intervention (CHARACTER ability not strat) | ✓ | `simulator.py:_do_heroic_intervention` |

## 13. Models / Coherency

| Rule | Status | Where / gap |
|---|---|---|
| Unit Coherency (2" between models, 5" diagonal) | n/a | Sim is per-model; coherency is implicit through positions. Not a 10e violation but may distort screening |
| Base sizes | ◐ | Tracked via `base_diameter_mm` etc.; used for renderer + footprint sims |

## Headline gaps by leverage

| Gap | Factions affected | Leverage | Plan phase |
|---|---|---|---|
| Embark / Disembark | All transport-using (~15/22) | HIGH | Phase 2 |
| Secondary objective selection | All 22 (asymmetric) | HIGH | Phase 2.5 |
| Stratagem chaining | All (asymmetric, more strat-rich factions over-suffer) | HIGH | Phase 4 |
| Aircraft Zooming/Hover | ~3 factions | MEDIUM | parking lot |
| Towering LoS benefit | 2 factions (both parked) | LOW (gated by parking) | parking lot |
| Battle-shock OC = 0 | All | MEDIUM | parking lot |
| Strategic Reserves != Deep Strike | All | MEDIUM | parking lot |
| Wound allocation closer-first | All (screening tactics) | LOW–MEDIUM | parking lot |
| Counter-charge logic | All | LOW | parking lot |
| Remain Stationary modeling | Heavy-weapon factions | LOW | parking lot |
| Various weapon-keyword ⚠️ verifications | Variable | unknown until verified | parking lot — single-pass audit |

The bottom-rows ⚠️ verifications (weapon keywords flagged but path
unverified) are worth a single structural audit pass when MAE
compression slows: most are probably implemented correctly, but a
few likely have wiring bugs.

Audit author: Claude Opus 4.7 (1M context).
Audit date: 2026-05-28.
