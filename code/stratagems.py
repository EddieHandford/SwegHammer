"""
Stratagems and the Command Point (CP) economy.

10e armies pick a Detachment that grants 6 detachment-specific Stratagems on
top of the universal Core Stratagems every army can use. Stratagems cost CP
and fire on specific triggers during specific phases — they're the lever real
tournament play uses to swing close fights.

Sources for every stratagem entry are cited in
`data/rule_citations.d/stratagems.json` per CLAUDE.md §10.

Audit history (2026-05-15, commit fa9a957): 11 fabricated stratagems were
removed from this file — they had no Wahapedia equivalent. (2026-05-16,
#197): the Warhost (Aeldari) detachment stratagem set was completed —
Lightning-Fast Reactions + Fire and Fade survived the audit; the remaining
four real codex stratagems (Skyborne Sanctuary, Feigned Retreat, Blitzing
Firepower, Webway Tunnel) have been added. The current entries are: the
four universal Core Stratagems (verbatim 10e), the six real Warhost
(Aeldari) stratagems, and Disgustingly Resilient (DG) which was
re-anchored to Virulent Vectorium at 2CP. Per-detachment real stratagem
sets for other factions are wired in follow-up per-faction PRs.

Mont'ka rebuild (2026-05-16, #196): six real Mont'ka stratagems wired
from the Wahapedia page (Pinpoint Counter-Offensive, Aggressive Mobility,
Focused Fire, Combat Debarkation, Pulse Onslaught, Counterfire Defence
Systems) — see MONTKA_STRATAGEMS below.

Dispatch model:
  * `name` — display label.
  * `cp_cost` — integer CP price.
  * `phase` — when the stratagem may legally fire ("command", "movement",
    "shooting", "charge", "fight", or "any").
  * `trigger` — a short string identifier the simulator branches on at the
    relevant event (e.g. "failed_wound_roll", "vehicle_charges",
    "enemy_landed_fight_kill", "friendly_character_near_charge_target").
  * `effect` — a short string identifier the simulator branches on when
    applying the stratagem's effect (e.g. "reroll_one_failed_roll",
    "out_of_sequence_fight", "d3_mortal_wounds", "3_inch_move_into_engagement").
  * `once_per_battle` — for non-Core stratagems with a per-game cap. None of
    the four universals are once-per-battle; the flag is here for #104.

The Stratagem is intentionally a string-identifier dispatcher rather than
holding a callable so it stays hashable / frozen-dataclass friendly and
serialises cleanly to event-log / Streamlit replays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Stratagem:
    """A single Stratagem entry. Frozen + hashable so it can live in a
    Detachment's stratagems tuple and round-trip through the event log."""
    name: str
    cp_cost: int
    phase: str                           # "command" / "movement" / "shooting" / "charge" / "fight" / "any"
    trigger: str                         # identifier dispatched on by the simulator
    effect: str                          # identifier dispatched on by the simulator
    once_per_battle: bool = False


# ---------------------------------------------------------------------------
# Universal Core Stratagems
# ---------------------------------------------------------------------------
# Every army may spend these regardless of detachment. Cited in
# data/rule_citations.d/stratagems.json — keys are Stratagem.<name>.

COMMAND_RE_ROLL = Stratagem(
    name="Command Re-Roll",
    cp_cost=1,
    phase="any",
    trigger="failed_roll",
    effect="reroll_one_failed_roll",
)

COUNTER_OFFENSIVE = Stratagem(
    name="Counter-Offensive",
    cp_cost=2,
    phase="fight",
    trigger="enemy_unit_just_fought",
    effect="out_of_sequence_fight",
)

TANK_SHOCK = Stratagem(
    name="Tank Shock",
    cp_cost=1,
    phase="charge",
    trigger="vehicle_charges",
    effect="d3_mortal_wounds_to_charge_target",
)

HEROIC_INTERVENTION = Stratagem(
    name="Heroic Intervention",
    cp_cost=1,
    phase="charge",
    trigger="enemy_charges_near_friendly_character",
    effect="3_inch_move_into_engagement",
)


UNIVERSAL_STRATAGEMS: Tuple[Stratagem, ...] = (
    COMMAND_RE_ROLL,
    COUNTER_OFFENSIVE,
    TANK_SHOCK,
    HEROIC_INTERVENTION,
)


# ---------------------------------------------------------------------------
# Warhost (Aeldari) — six real detachment stratagems
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost
# The fabrication audit (commit fa9a957) confirmed Lightning-Fast Reactions
# and Fire and Fade as real entries; the remaining four (Skyborne Sanctuary,
# Feigned Retreat, Blitzing Firepower, Webway Tunnel) were added in #197
# from the Wahapedia stratagem list. The codex detachment name is "Warhost"
# (the launch-index name "Battle Host" was renamed).

LIGHTNING_FAST_REACTIONS = Stratagem(
    name="Lightning-Fast Reactions",
    cp_cost=1,
    phase="any",
    trigger="vulnerable_friendly_aeldari_unit",
    effect="plus_one_save_for_round",
)

FIRE_AND_FADE = Stratagem(
    name="Fire and Fade",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_aeldari_unit_about_to_shoot",
    effect="reroll_hits_shooting_for_round",
)

# Skyborne Sanctuary: end of Fight phase, an AELDARI INFANTRY unit not in
# engagement range and wholly within 6" of a friendly AELDARI TRANSPORT can
# embark within it. Defensive re-embark; we approximate the offensive
# value via the same transient_plus_one_save flag (the canonical use case
# is saving a shot-up unit from a follow-up activation).
SKYBORNE_SANCTUARY = Stratagem(
    name="Skyborne Sanctuary",
    cp_cost=1,
    phase="fight",
    trigger="end_of_fight_aeldari_infantry_near_transport",
    effect="plus_one_save_for_round",
)

# Feigned Retreat: your Movement phase, just after an AELDARI INFANTRY unit
# Falls Back — until end of turn the unit can still shoot and declare a
# charge despite having Fallen Back. We approximate the offensive value
# via transient_assault_this_round (lets it shoot the same round it
# repositioned, the closest single-flag stand-in).
FEIGNED_RETREAT = Stratagem(
    name="Feigned Retreat",
    cp_cost=1,
    phase="movement",
    trigger="friendly_aeldari_infantry_just_fell_back",
    effect="transient_assault_for_round",
)

# Blitzing Firepower: your Shooting phase, when an AELDARI unit is selected
# to shoot — until end of phase its ranged weapons gain [SUSTAINED HITS 1]
# vs targets within 12" (or improve to 5+ Critical Hit if already having
# the ability). Approximated as +1 to hit shooting for the round, the
# nearest one-flag stand-in for the Sustained-Hits uplift.
BLITZING_FIREPOWER = Stratagem(
    name="Blitzing Firepower",
    cp_cost=1,
    phase="shooting",
    trigger="aeldari_unit_about_to_shoot_short_range",
    effect="plus_one_to_hit_shooting_for_round",
)

# Webway Tunnel: end of opponent's Fight phase, an AELDARI INFANTRY unit
# wholly within 9" of a battlefield edge and not in engagement range may
# enter Strategic Reserves. SwegHammer's reserve model is a single
# arrival queue with no mid-battle re-entry hook, so this stratagem is
# wired in but resolves as a defensive save buff (+1 save) — the
# strongest single-flag stand-in for "pull the unit off the table to
# avoid the next attack" while the reserves hook is not implemented.
WEBWAY_TUNNEL = Stratagem(
    name="Webway Tunnel",
    cp_cost=1,
    phase="fight",
    trigger="aeldari_infantry_near_board_edge_end_of_enemy_fight",
    effect="plus_one_save_for_round",
)

WARHOST_STRATAGEMS: Tuple[Stratagem, ...] = (
    LIGHTNING_FAST_REACTIONS,
    FIRE_AND_FADE,
    SKYBORNE_SANCTUARY,
    FEIGNED_RETREAT,
    BLITZING_FIREPOWER,
    WEBWAY_TUNNEL,
)


# ---------------------------------------------------------------------------
# Awakened Dynasty (Necrons) — six real Protocol stratagems
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
# Six real "Protocol of the …" stratagems verbatim from the Necrons codex.
# Replaces the two fabricated entries (Implacable Onslaught, Methodical
# Destruction) deleted in commit fa9a957 per the fabrication audit.
#
# Mapping summary (full notes in data/rule_citations.d/stratagems.json):
#   * Eternal Revenant (1 CP) — return a destroyed CHARACTER at half wounds.
#     No clean mapping (no model-resurrection hook); registered as a no-op
#     APPROXIMATION so the stratagem is catalogued but the AI never fires.
#   * Undying Legions (1 CP) — D3 (+1 if led) extra reanimation pulse on a
#     unit that just lost models. Maps to an inline mid-phase reanimation
#     hook (`transient_undying_legions_pulse`).
#   * Hungry Void (1 CP) — +1 S melee (+1 AP melee if led). Approximated as
#     `transient_plus_one_to_wound_melee` (same direction, lossy on AP).
#   * Sudden Storm (1 CP) — [ASSAULT] for the round. Maps cleanly to
#     `transient_assault_this_round`.
#   * Conquering Tyrant (1 CP) — re-roll Hit rolls of 1 within half range
#     (full re-roll if led). Approximated as `transient_reroll_hits_shooting`
#     (full re-roll always; same direction, slight over-buff for unled).
#   * Vengeful Stars (2 CP) — out-of-sequence shoot when an enemy destroys a
#     friendly unit near a CHARACTER. No out-of-sequence shoot hook;
#     registered as a no-op APPROXIMATION.

PROTOCOL_OF_THE_ETERNAL_REVENANT = Stratagem(
    name="Protocol of the Eternal Revenant",
    cp_cost=1,
    phase="any",
    trigger="necrons_character_just_destroyed",
    effect="return_character_half_wounds_approximation",
    once_per_battle=False,
)

PROTOCOL_OF_THE_UNDYING_LEGIONS = Stratagem(
    name="Protocol of the Undying Legions",
    cp_cost=1,
    phase="any",
    trigger="friendly_necrons_unit_just_lost_models",
    effect="extra_reanimation_pulse",
)

PROTOCOL_OF_THE_HUNGRY_VOID = Stratagem(
    name="Protocol of the Hungry Void",
    cp_cost=1,
    phase="fight",
    trigger="friendly_necrons_unit_about_to_fight",
    effect="plus_one_strength_melee_approximation",
)

PROTOCOL_OF_THE_SUDDEN_STORM = Stratagem(
    name="Protocol of the Sudden Storm",
    cp_cost=1,
    phase="movement",
    trigger="friendly_necrons_unit_in_movement",
    effect="assault_this_round",
)

PROTOCOL_OF_THE_CONQUERING_TYRANT = Stratagem(
    name="Protocol of the Conquering Tyrant",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_necrons_unit_about_to_shoot",
    effect="reroll_hits_shooting_approximation",
)

PROTOCOL_OF_THE_VENGEFUL_STARS = Stratagem(
    name="Protocol of the Vengeful Stars",
    cp_cost=2,
    phase="shooting",
    trigger="enemy_destroyed_friendly_necrons_near_character",
    effect="out_of_sequence_shoot_approximation",
)

AWAKENED_DYNASTY_STRATAGEMS: Tuple[Stratagem, ...] = (
    PROTOCOL_OF_THE_ETERNAL_REVENANT,
    PROTOCOL_OF_THE_UNDYING_LEGIONS,
    PROTOCOL_OF_THE_HUNGRY_VOID,
    PROTOCOL_OF_THE_SUDDEN_STORM,
    PROTOCOL_OF_THE_CONQUERING_TYRANT,
    PROTOCOL_OF_THE_VENGEFUL_STARS,
)


# ---------------------------------------------------------------------------
# Virulent Vectorium (Death Guard) — 6 detachment stratagems
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium
# Codex Death Guard, "Virulent Vectorium" detachment. The detachment rule is
# Worldblight (sticky-objective-style control plus Nurgle's Gift contagion on
# the objective itself). All six stratagems are present here verbatim per
# task #195.
#
# Effect-mapping notes per stratagem:
#   * Putrid Detonation — Deadly Demise auto-success + Afflict trigger.
#     Mapped to a Deadly-Demise-related transient flag; the Afflicted
#     keyword is APPROXIMATED (we don't model Afflicted as a unit state).
#   * Disgustingly Resilient — already routed to transient_minus_one_damage_taken
#     (APPROXIMATION; real text says "subtract 1 from the Damage characteristic
#     of that attack" which matches per-shot damage reduction).
#   * Plaguesurge — +3" Contagion Range. We don't currently model variable
#     contagion range (it's hard-coded to 6"); APPROXIMATION leaves the
#     transient unused but the stratagem is present with the real text cited.
#   * Leechspore Eruption — heal-self + mortal-wound payload on a damaged DG
#     model. Implementable via a custom dispatcher.
#   * Overwhelming Generosity — re-roll weapon attack-count rolls vs a target.
#     We don't model per-weapon attack-count dice; APPROXIMATED to
#     re-roll hits on a friendly DG CHARACTER unit's shooting for the round.
#   * Creeping Blight — re-roll hit AND wound vs Afflicted units. We don't
#     model Afflicted; APPROXIMATED to re-roll hits on a DG INFANTRY unit's
#     shooting (lossy: drops the wound-reroll half + the Afflicted gate).

DISGUSTINGLY_RESILIENT = Stratagem(
    name="Disgustingly Resilient",
    cp_cost=2,
    phase="any",
    trigger="wounded_friendly_dg_unit",
    effect="minus_one_damage_taken_for_round",
)

PUTRID_DETONATION = Stratagem(
    name="Putrid Detonation",
    cp_cost=1,
    phase="any",
    trigger="dg_vehicle_or_monster_destroyed",
    effect="auto_success_deadly_demise",
)

PLAGUESURGE = Stratagem(
    name="Plaguesurge",
    cp_cost=2,
    phase="command",
    trigger="own_command_phase_warlord",
    effect="plus_three_inch_contagion_range",
)

LEECHSPORE_ERUPTION = Stratagem(
    name="Leechspore Eruption",
    cp_cost=1,
    phase="command",
    trigger="own_command_phase_wounded_dg_model",
    effect="d6_per_wound_lost_mortal_and_heal",
)

OVERWHELMING_GENEROSITY = Stratagem(
    name="Overwhelming Generosity",
    cp_cost=1,
    phase="shooting",
    trigger="start_of_shooting_dg_character",
    effect="reroll_attack_count_vs_target",
)

CREEPING_BLIGHT = Stratagem(
    name="Creeping Blight",
    cp_cost=1,
    phase="shooting",
    trigger="own_shooting_dg_infantry_not_yet_shot",
    effect="reroll_hit_and_wound_vs_afflicted",
)


VIRULENT_VECTORIUM_STRATAGEMS: Tuple[Stratagem, ...] = (
    PUTRID_DETONATION,
    DISGUSTINGLY_RESILIENT,
    PLAGUESURGE,
    LEECHSPORE_ERUPTION,
    OVERWHELMING_GENEROSITY,
    CREEPING_BLIGHT,
)


# ---------------------------------------------------------------------------
# Mont'ka (T'au Empire) — six real detachment stratagems (#196)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka
# Names, CP costs, triggers, and effects verified verbatim against the
# Wahapedia page on 2026-05-15. Each entry has a matching citation in
# data/rule_citations.d/stratagems.json with a per-effect APPROXIMATION
# note where the simulator's behaviour diverges from the canonical text
# (most often: gating clauses dropped, target restrictions widened).

PINPOINT_COUNTER_OFFENSIVE = Stratagem(
    name="Pinpoint Counter-Offensive",
    cp_cost=1,
    phase="any",
    trigger="friendly_tau_unit_destroyed",
    effect="reroll_hits_shooting_for_round",
)

AGGRESSIVE_MOBILITY = Stratagem(
    name="Aggressive Mobility",
    cp_cost=1,
    phase="movement",
    trigger="friendly_tau_unit_about_to_advance",
    effect="assault_this_round",
)

FOCUSED_FIRE = Stratagem(
    name="Focused Fire",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_tau_unit_about_to_shoot",
    effect="plus_one_to_hit_shooting_for_round",
)

COMBAT_DEBARKATION = Stratagem(
    name="Combat Debarkation",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_tau_unit_just_disembarked",
    effect="reroll_hits_shooting_for_round",
)

PULSE_ONSLAUGHT = Stratagem(
    name="Pulse Onslaught",
    cp_cost=2,
    phase="shooting",
    # TODO: APPROXIMATION — Pulse Onslaught's real effect is a Move /
    # Charge / Advance penalty on the enemy unit. SwegHammer has no
    # movement-debuff transient, so we route the offensive value through
    # an attacker hit-buff for the round (the unit that fires the
    # stratagem gets +1 to hit shooting for the round, modelling the
    # "shaken" enemy as easier to land hits on).
    trigger="friendly_tau_unit_about_to_shoot",
    effect="plus_one_to_hit_shooting_for_round",
)

COUNTERFIRE_DEFENCE_SYSTEMS = Stratagem(
    name="Counterfire Defence Systems",
    cp_cost=2,
    phase="any",
    trigger="friendly_tau_unit_targeted",
    effect="minus_one_damage_taken_for_round",
)


MONTKA_STRATAGEMS: Tuple[Stratagem, ...] = (
    PINPOINT_COUNTER_OFFENSIVE,
    AGGRESSIVE_MOBILITY,
    FOCUSED_FIRE,
    COMBAT_DEBARKATION,
    PULSE_ONSLAUGHT,
    COUNTERFIRE_DEFENCE_SYSTEMS,
)


# ---------------------------------------------------------------------------
# Grand Coven (Thousand Sons) — six real detachment stratagems (#193)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
# Stratagem names + CP costs confirmed against Wahapedia's Grand Coven
# detachment listing. Verbatim WHEN/EFFECT blocks were not reproducible
# via the WebFetch tool (the model refused on copyright grounds); the
# `quoted_text` in the citation file is a mechanical paraphrase tagged
# accordingly. Each stratagem's effect maps onto an existing transient_*
# flag where it can; gaps are flagged as APPROXIMATION in the dispatcher.

PSYCHIC_DOMINION = Stratagem(
    name="Psychic Dominion",
    cp_cost=1,
    phase="any",
    trigger="enemy_psychic_attack_targets_friendly_tson_unit",
    effect="transient_fnp_4_for_round",
)

DESTINED_BY_FATE = Stratagem(
    name="Destined by Fate",
    cp_cost=1,
    phase="any",
    trigger="friendly_tson_psyker_failed_save",
    effect="minus_one_damage_taken_for_round",
)

EGOTISTICAL_POWER = Stratagem(
    name="Egotistical Power",
    cp_cost=1,
    phase="command",
    trigger="command_phase_friendly_tson_psyker_unit",
    effect="reapply_kindred_sorcery_to_one_unit",
)

DESECRATION_OF_WORLDS = Stratagem(
    name="Desecration of Worlds",
    cp_cost=1,
    phase="command",
    trigger="command_phase_friendly_tson_holds_objective",
    effect="sticky_objective_for_battle",
)

ARCANE_FOCUS = Stratagem(
    name="Arcane Focus",
    cp_cost=1,
    phase="shooting",
    trigger="psychic_test_after_channel_the_warp",
    effect="reroll_psychic_test_dice",
)

DEVASTATING_SORCERY = Stratagem(
    name="Devastating Sorcery",
    cp_cost=2,
    phase="shooting",
    trigger="friendly_tson_psyker_unit_about_to_shoot",
    effect="reroll_hits_shooting_for_round",
)

GRAND_COVEN_STRATAGEMS: Tuple[Stratagem, ...] = (
    PSYCHIC_DOMINION,
    DESTINED_BY_FATE,
    EGOTISTICAL_POWER,
    DESECRATION_OF_WORLDS,
    ARCANE_FOCUS,
    DEVASTATING_SORCERY,
)


# ---------------------------------------------------------------------------
# War Horde (Orks) — six real detachment stratagems (iter-1 Cluster B B1)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
# Names + CP costs cross-referenced against the iter-1 Cluster B diagnostic
# (docs/AUTO_LOOP_ITER1_CLUSTER_B.md) which audits the Wahapedia stratagem
# list. WebFetch against wahapedia.ru returned ECONNREFUSED at edit time;
# stratagem effects are paraphrased per general 10e Orks codex knowledge,
# with the Wahapedia URL cited and each entry flagged APPROXIMATION in
# data/rule_citations.d/stratagems.json. Effect mappings follow the same
# convention as Mont'ka / Warhost — route through the closest existing
# transient_* flag and document the gap.
#
# Effect-mapping summary:
#   * Insane Bravery (1 CP) — auto-pass a Battle-shock test on an OUTRIDE
#     INFANTRY unit. No clean simulator hook (battleshock is resolved per-
#     unit at round end and we don't expose a per-unit "this unit is
#     immune this round" flag), so the dispatcher is catalogued-but-no-op
#     APPROXIMATION; CP not spent.
#   * Power Of The WAAAGH! (1 CP) — an Orks unit's melee weapons gain
#     LETHAL HITS (or upgrade to 5+ Critical Hit if already carrying it)
#     for the fight phase. Maps to `transient_plus_one_to_wound_melee`
#     on the highest-DPA Orks melee unit — same direction (more landed
#     wounds in melee), strength comparable on an average matchup.
#   * Mob Up (1 CP) — an Orks INFANTRY unit absorbs a destroyed friendly
#     Orks INFANTRY unit's surviving models. No model-absorbing hook;
#     mapped to `transient_undying_legions_pulse` = 2 (mid-phase +2 HP
#     reanimation on a wounded Orks unit, the closest "regain bodies"
#     stand-in SwegHammer has).
#   * Big Krumpin' (2 CP) — an Orks unit re-rolls Wound rolls of 1 in
#     melee (or full re-roll if charging). Maps to
#     `transient_plus_one_to_wound_melee` on the highest-DPA Orks melee
#     unit. APPROXIMATION: the codex effect is a wound reroll (~14% extra
#     wounds at 4+), while +1 to wound (~25% extra wounds) is stronger;
#     mitigated by the 2 CP price gate.
#   * Tellyporta (1 CP) — pull an Orks INFANTRY unit off the battlefield
#     and place it back via Strategic Reserves next round. No mid-battle
#     reserve hook; mapped to `transient_plus_one_save` on the most
#     vulnerable Orks INFANTRY unit as a defensive stand-in (same as
#     Webway Tunnel's pattern).
#   * Da Biggest Boss (1 CP) — Warlord-targeted; the Warlord makes a
#     normal move of D6+1" in the Movement phase. No grid-free movement
#     buff hook; mapped to `transient_assault_this_round` on the
#     highest-DPA Orks CHARACTER as a stand-in for the "reposition then
#     shoot" offensive payoff.

INSANE_BRAVERY = Stratagem(
    name="Insane Bravery",
    cp_cost=1,
    phase="command",
    trigger="friendly_orks_infantry_battleshock_test_about_to_fail",
    effect="auto_pass_battleshock_approximation",
)

POWER_OF_THE_WAAAGH = Stratagem(
    name="Power Of The WAAAGH!",
    cp_cost=1,
    phase="fight",
    trigger="friendly_orks_unit_about_to_fight",
    effect="lethal_hits_melee_approximation",
)

MOB_UP = Stratagem(
    name="Mob Up",
    cp_cost=1,
    phase="command",
    trigger="friendly_orks_infantry_wounded",
    effect="extra_reanimation_pulse_approximation",
)

BIG_KRUMPIN = Stratagem(
    name="Big Krumpin'",
    cp_cost=2,
    phase="fight",
    trigger="friendly_orks_unit_about_to_fight_heavy_target",
    effect="reroll_wounds_melee_approximation",
)

TELLYPORTA = Stratagem(
    name="Tellyporta",
    cp_cost=1,
    phase="any",
    trigger="vulnerable_friendly_orks_infantry",
    effect="plus_one_save_for_round_approximation",
)

DA_BIGGEST_BOSS = Stratagem(
    name="Da Biggest Boss",
    cp_cost=1,
    phase="movement",
    trigger="friendly_orks_character_warlord",
    effect="transient_assault_for_round_approximation",
)


WAR_HORDE_STRATAGEMS: Tuple[Stratagem, ...] = (
    INSANE_BRAVERY,
    POWER_OF_THE_WAAAGH,
    MOB_UP,
    BIG_KRUMPIN,
    TELLYPORTA,
    DA_BIGGEST_BOSS,
)


# ---------------------------------------------------------------------------
# Shield Host (Adeptus Custodes) — six real detachment stratagems (iter-8 fix)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
# Replaces the iter-0 zero-stratagem state where Custodes burned 5/7 strat
# fires per battle on Command Re-Roll (universal Core) because no detachment
# stratagems were registered. iter-7 diagnostic
# (docs/AUTO_LOOP_ITER7_DG_VS_CUSTODES.md) identified this as the top fix
# for DG-vs-Custodes (+19.5pt over real meta).
#
# Effect-mapping summary (full notes in data/rule_citations.d/stratagems.json
# and data/rule_citations.d/adeptus_custodes.json):
#   * Arcane Genetic Alchemy (1 CP, Battle Tactic) — 4+ FNP vs mortal wounds
#     for the phase. SwegHammer doesn't model mortal-wound-only FNP buckets,
#     so the closest stand-in is `transient_fnp_5` (5+ FNP all-damage for the
#     round) on the most vulnerable Custodes unit. APPROXIMATION: 5+ FNP all-
#     damage is broader than 4+ FNP mortal-only — direction-correct but lossy.
#   * Unwavering Sentinels (1 CP, Strategic Ploy) — -1 to hit on an enemy
#     targeting a Custodes INFANTRY unit within range of a friendly objective.
#     SwegHammer has no per-target -1-to-hit transient flag, so the offensive
#     payoff is routed through `transient_plus_one_save` on the most
#     vulnerable Custodes INFANTRY unit (defensive proxy — both buffs reduce
#     incoming damage). APPROXIMATION: defensive +1 save instead of -1 to hit.
#   * Multipotentiality (1 CP, Strategic Ploy) — a Custodes unit that Fell
#     Back may still shoot and declare a charge this turn. Maps cleanly to
#     `transient_assault_this_round` on the highest-DPA Custodes unit (same
#     flag used by Feigned Retreat).
#   * Vigilance Eternal (1 CP, Strategic Ploy) — sticky objective control
#     for a Custodes BATTLELINE unit in range of an objective. SwegHammer's
#     sticky-objective hook is gated on per-faction detachment flags rather
#     than per-stratagem fire, so this dispatches as a no-op APPROXIMATION
#     (CP not spent if no other effect lands). Catalogued for auditor + AI.
#   * Archaeotech Munitions (1 CP, Wargear) — [LETHAL HITS] or [SUSTAINED
#     HITS 1] on a Custodes unit's ranged weapons for the phase. SwegHammer
#     has no per-round transient lethal-hits flag, so the offensive uplift
#     is routed through `transient_plus_one_to_hit_shooting` on the highest-
#     DPA Custodes shooter — same direction (more landed hits), comparable
#     magnitude on a 4+ hit roll. APPROXIMATION: +1 to hit instead of
#     Lethal/Sustained Hits.
#   * Avenge the Fallen (1 CP, Strategic Ploy) — +1 attack (or +2 if below
#     half strength) on a Custodes unit below Starting Strength. Maps to
#     `transient_plus_one_to_wound_melee` on the most vulnerable Custodes
#     melee unit (the +1 attack increases melee damage output similarly to
#     +1 to wound on a 4+ wound roll). APPROXIMATION: +1 to wound instead
#     of +1 attack count.

ARCANE_GENETIC_ALCHEMY = Stratagem(
    name="Arcane Genetic Alchemy",
    cp_cost=1,
    phase="any",
    trigger="mortal_wound_allocated_to_custodes",
    effect="fnp_5_for_round_approximation",
)

UNWAVERING_SENTINELS = Stratagem(
    name="Unwavering Sentinels",
    cp_cost=1,
    phase="fight",
    trigger="enemy_targets_custodes_infantry_on_objective",
    effect="plus_one_save_for_round_approximation",
)

MULTIPOTENTIALITY = Stratagem(
    name="Multipotentiality",
    cp_cost=1,
    phase="movement",
    trigger="friendly_custodes_unit_just_fell_back",
    effect="transient_assault_for_round",
)

VIGILANCE_ETERNAL = Stratagem(
    name="Vigilance Eternal",
    cp_cost=1,
    phase="movement",
    trigger="friendly_custodes_battleline_on_objective",
    effect="sticky_objective_approximation",
)

ARCHAEOTECH_MUNITIONS = Stratagem(
    name="Archaeotech Munitions",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_custodes_unit_about_to_shoot",
    effect="plus_one_to_hit_shooting_for_round_approximation",
)

AVENGE_THE_FALLEN = Stratagem(
    name="Avenge the Fallen",
    cp_cost=1,
    phase="fight",
    trigger="friendly_custodes_unit_below_starting_strength_about_to_fight",
    effect="plus_one_to_wound_melee_approximation",
)


SHIELD_HOST_STRATAGEMS: Tuple[Stratagem, ...] = (
    ARCANE_GENETIC_ALCHEMY,
    UNWAVERING_SENTINELS,
    MULTIPOTENTIALITY,
    VIGILANCE_ETERNAL,
    ARCHAEOTECH_MUNITIONS,
    AVENGE_THE_FALLEN,
)


# ---------------------------------------------------------------------------
# Oathband (Leagues of Votann) — six real detachment stratagems (iter-9 fix)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
# Replaces the iter-0 zero-stratagem state where Votann fired Core only.
# iter-8 anti-DG audit (docs/AUTO_LOOP_ITER8_ANTI_DG_AUDIT.md fix #2) flagged
# Oathband as one of the top-priority missing stratagem sets — Votann is one
# of the 7 unsampled-but-positive DG matchups (~+8pt over real per iter-5).
#
# Six stratagems per the iter-8 audit table, drawn from the codex Oathband
# detachment listing. SwegHammer's OATHBAND is a generic stub for the
# Votann codex detachments (Hearthband, Needgaard Oathband, etc.); the
# six stratagems chosen here are the canonical "Oathband-style" set that
# share the Judgement-Token-leveraging trigger spine.
#
# Effect-mapping summary (full notes in data/rule_citations.d/stratagems.json):
#   * Warrior Pride (1 CP) — Re-roll Wound rolls vs a Judgement-Token-bearing
#     enemy. Maps to `transient_plus_one_to_wound_melee` +
#     `transient_plus_one_to_wound_shooting` on the highest-DPA Votann unit
#     (full wound-reroll APPROXIMATED as +1 to wound on a 4+ wound roll,
#     same direction). Stacks naturally with `simulator.judgement_tokens`
#     plumbing that already grants per-attack re-roll buffs at 1+/3+ token
#     thresholds.
#   * Wrath of the Ancestors (1 CP) — [LETHAL HITS] on ranged vs token-bearing.
#     Maps to `transient_plus_one_to_hit_shooting` on highest-DPA Votann
#     shooter (LETHAL HITS APPROXIMATED as +1 to hit — same direction,
#     comparable magnitude on a 4+ hit roll).
#   * Glory of the Hearth (1 CP) — Re-roll Hit AND Wound for a Votann VEHICLE
#     shooting. Maps to `transient_reroll_hits_shooting` on the highest-DPA
#     Votann VEHICLE (the wound-reroll leg is dropped — APPROXIMATION).
#   * Ironkin Sequence (1 CP) — IRONKIN unit gets +1 to hit. Maps directly to
#     `transient_plus_one_to_hit_shooting` on the highest-DPA IRONKIN unit
#     (clean mapping, no approximation gap).
#   * Ancestral Sentence (2 CP) — Issue a Judgement Token to an enemy unit at
#     the start of the phase. Maps DIRECTLY onto the existing
#     `Army.judgement_tokens[uid]` dict — increments the token count on
#     the highest-threat enemy unit so subsequent Votann attacks fire the
#     1+/3+ re-roll thresholds. No approximation: this is a clean wiring.
#   * Void-Armoured Resilience (1 CP) — 5+ Feel No Pain for the phase. Maps
#     directly to `transient_fnp_5` on the most vulnerable Votann unit
#     (clean mapping).

WARRIOR_PRIDE = Stratagem(
    name="Warrior Pride",
    cp_cost=1,
    phase="any",
    trigger="friendly_votann_unit_attacks_token_bearer",
    effect="reroll_wounds_vs_token_bearer_approximation",
)

WRATH_OF_THE_ANCESTORS = Stratagem(
    name="Wrath of the Ancestors",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_votann_unit_shoots_token_bearer",
    effect="lethal_hits_ranged_approximation",
)

GLORY_OF_THE_HEARTH = Stratagem(
    name="Glory of the Hearth",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_votann_vehicle_about_to_shoot",
    effect="reroll_hits_and_wounds_shooting_approximation",
)

IRONKIN_SEQUENCE = Stratagem(
    name="Ironkin Sequence",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_votann_ironkin_unit_about_to_shoot",
    effect="plus_one_to_hit_shooting_for_round",
)

ANCESTRAL_SENTENCE = Stratagem(
    name="Ancestral Sentence",
    cp_cost=2,
    phase="command",
    trigger="own_command_phase_votann_warlord",
    effect="issue_judgement_token_to_enemy",
)

VOID_ARMOURED_RESILIENCE = Stratagem(
    name="Void-Armoured Resilience",
    cp_cost=1,
    phase="any",
    trigger="vulnerable_friendly_votann_unit",
    effect="fnp_5_for_round",
)


OATHBAND_STRATAGEMS: Tuple[Stratagem, ...] = (
    WARRIOR_PRIDE,
    WRATH_OF_THE_ANCESTORS,
    GLORY_OF_THE_HEARTH,
    IRONKIN_SEQUENCE,
    ANCESTRAL_SENTENCE,
    VOID_ARMOURED_RESILIENCE,
)


# ---------------------------------------------------------------------------
# CP economy
# ---------------------------------------------------------------------------

STARTING_CP: int = 3                     # Strike Force standard (10e core rules)
CP_PER_COMMAND_PHASE: int = 1
CP_CAP: int = 6                          # 10e core: armies can't bank more than 6 CP


def award_command_phase_cp(army) -> None:
    """Grant the start-of-Command-phase CP, capped at CP_CAP.

    Called by Battle._run_round at the top of every round. The Strike Force
    starting allotment (STARTING_CP) is set on Army.__init__ — this function
    handles the per-round drip only.
    """
    army.command_points = min(CP_CAP, army.command_points + CP_PER_COMMAND_PHASE)


def stratagems_for_army(army) -> Tuple[Stratagem, ...]:
    """Every Stratagem this army can fire — the four universals plus any
    detachment-specific stratagems exposed on
    `Army.resolve_detachment().stratagems`.
    """
    extra: Tuple[Stratagem, ...] = ()
    det = army.resolve_detachment() if hasattr(army, "resolve_detachment") else None
    if det is not None:
        extra = tuple(getattr(det, "stratagems", ()) or ())
    return UNIVERSAL_STRATAGEMS + extra


__all__ = [
    "Stratagem",
    "COMMAND_RE_ROLL",
    "COUNTER_OFFENSIVE",
    "TANK_SHOCK",
    "HEROIC_INTERVENTION",
    "UNIVERSAL_STRATAGEMS",
    # Warhost (Aeldari) — six real stratagems
    "LIGHTNING_FAST_REACTIONS",
    "FIRE_AND_FADE",
    "SKYBORNE_SANCTUARY",
    "FEIGNED_RETREAT",
    "BLITZING_FIREPOWER",
    "WEBWAY_TUNNEL",
    "WARHOST_STRATAGEMS",
    # Awakened Dynasty (Necrons) — six real Protocol stratagems
    "PROTOCOL_OF_THE_ETERNAL_REVENANT",
    "PROTOCOL_OF_THE_UNDYING_LEGIONS",
    "PROTOCOL_OF_THE_HUNGRY_VOID",
    "PROTOCOL_OF_THE_SUDDEN_STORM",
    "PROTOCOL_OF_THE_CONQUERING_TYRANT",
    "PROTOCOL_OF_THE_VENGEFUL_STARS",
    "AWAKENED_DYNASTY_STRATAGEMS",
    # Virulent Vectorium (Death Guard) — 6 detachment stratagems
    "DISGUSTINGLY_RESILIENT",
    "PUTRID_DETONATION",
    "PLAGUESURGE",
    "LEECHSPORE_ERUPTION",
    "OVERWHELMING_GENEROSITY",
    "CREEPING_BLIGHT",
    "VIRULENT_VECTORIUM_STRATAGEMS",
    # Mont'ka (T'au Empire) — six real stratagems (#196)
    "PINPOINT_COUNTER_OFFENSIVE",
    "AGGRESSIVE_MOBILITY",
    "FOCUSED_FIRE",
    "COMBAT_DEBARKATION",
    "PULSE_ONSLAUGHT",
    "COUNTERFIRE_DEFENCE_SYSTEMS",
    "MONTKA_STRATAGEMS",
    # Grand Coven (Thousand Sons) — six real stratagems (#193)
    "PSYCHIC_DOMINION",
    "DESTINED_BY_FATE",
    "EGOTISTICAL_POWER",
    "DESECRATION_OF_WORLDS",
    "ARCANE_FOCUS",
    "DEVASTATING_SORCERY",
    "GRAND_COVEN_STRATAGEMS",
    # War Horde (Orks) — six real stratagems (iter-1 Cluster B B1)
    "INSANE_BRAVERY",
    "POWER_OF_THE_WAAAGH",
    "MOB_UP",
    "BIG_KRUMPIN",
    "TELLYPORTA",
    "DA_BIGGEST_BOSS",
    "WAR_HORDE_STRATAGEMS",
    # Shield Host (Adeptus Custodes) — six real stratagems (iter-8 fix)
    "ARCANE_GENETIC_ALCHEMY",
    "UNWAVERING_SENTINELS",
    "MULTIPOTENTIALITY",
    "VIGILANCE_ETERNAL",
    "ARCHAEOTECH_MUNITIONS",
    "AVENGE_THE_FALLEN",
    "SHIELD_HOST_STRATAGEMS",
    # Oathband (Leagues of Votann) — six real stratagems (iter-9 fix)
    "WARRIOR_PRIDE",
    "WRATH_OF_THE_ANCESTORS",
    "GLORY_OF_THE_HEARTH",
    "IRONKIN_SEQUENCE",
    "ANCESTRAL_SENTENCE",
    "VOID_ARMOURED_RESILIENCE",
    "OATHBAND_STRATAGEMS",
    # CP economy
    "STARTING_CP",
    "CP_PER_COMMAND_PHASE",
    "CP_CAP",
    "award_command_phase_cp",
    "stratagems_for_army",
]
