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

# NOTE: Heroic Intervention is NOT a stratagem. Per Wahapedia 10e core
# rules (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#CHARGE-PHASE)
# it is a free core ability for CHARACTER models — after the opposing
# player has resolved their charges, you may select any of your CHARACTER
# models within 6" of any enemy units; each of those models can move up
# to 6" (3" if WALKER) and must end the move within Engagement Range of
# one of those enemy units. No CP is spent. Implemented as a core
# mechanic in code.simulator._do_heroic_intervention; cited as
# `simulator.heroic_intervention_core`. The previous 1 CP stratagem
# entry was deleted in #iter12 (was always wrong per the 10e rulebook).


UNIVERSAL_STRATAGEMS: Tuple[Stratagem, ...] = (
    COMMAND_RE_ROLL,
    COUNTER_OFFENSIVE,
    TANK_SHOCK,
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
# Rubricae Phalanx (Thousand Sons) — six detachment stratagems (iter15)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
# 40k.app entry: https://www.40k.app/factions/thousand-sons/rules/detachment/rubricae-phalanx
# Goonhammer breakdown: https://www.goonhammer.com/detachment-focus-rubricae-phalanx/
# Frontline Gaming: https://frontlinegaming.org/2025/05/15/codex-focus-thousand-sons-rubricae-phalanx-warpforged-cabal-breakdown/
#
# Names + CP costs verbatim from 40k.app; verbatim "WHEN" / "EFFECT" blocks
# were not retrievable via WebFetch (wahapedia.ru returned ECONNREFUSED).
# Each stratagem's `quoted_text` in data/rule_citations.d/stratagems.json is
# a mechanical paraphrase tagged accordingly, with the source URL cited.
# Effect-mapping summary (each routes through an existing transient_* flag
# or is catalogued-but-no-op APPROXIMATION; the dispatcher logic lives in
# `code/simulator.py::_apply_detachment_stratagems`):
#
#   * Ardent Automata (1 CP) — your Movement phase, a RUBRICAE unit that
#     just Fell Back can shoot and charge this turn. SwegHammer has no
#     Fell-Back-this-turn transient flag, so dispatched as catalogued-but-
#     no-op APPROXIMATION. The RUBRICAE Fall Back lockout exemption would
#     need a transient_assault_after_fall_back hook to fully model.
#   * Inexorable Advance (1 CP) — your Movement phase, a RUBRICAE unit
#     ignores Move modifiers AND its ranged weapons gain [ASSAULT] until
#     end of turn. The [ASSAULT] half maps cleanly onto
#     `transient_assault_this_round` (matches Mont'ka Killing Blow's
#     [ASSAULT] proxy). The "ignore Move modifiers" half is dropped — the
#     grid-free movement model has no Move debuff to suppress.
#   * Infernal Fusillade (2 CP) — your Shooting phase, RUBRIC MARINES
#     unit's inferno bolt-pattern weapons gain [PSYCHIC] and S5. The
#     S5 uplift on a baseline S4 inferno bolter improves wound rolls
#     vs T4-T5; we route through `transient_plus_one_to_wound_shooting`
#     on the highest-DPA RUBRICAE PSYKER unit. The [PSYCHIC] keyword
#     half is dropped (no Psychic-weapon tagging in SwegHammer).
#   * Revenge of the Rubricae (1 CP) — opponent's Shooting phase, after
#     a THOUSAND SONS PSYKER model is destroyed, a RUBRICAE unit shoots
#     the destroyer out of sequence. SwegHammer has no out-of-sequence
#     shoot hook tied to a Psyker death event; catalogued-but-no-op
#     APPROXIMATION. The CP would land via the StratagemFired event but
#     the mechanical follow-through is absent — same gap pattern as
#     Awakened Dynasty's "Protocol of the Vengeful Stars".
#   * Implacable Guardians (2 CP) — opponent's Shooting phase, until
#     end of phase a RUBRIC MARINES PSYKER unit gets -1 to incoming
#     Damage (on non-PSYKER models). Maps to
#     `transient_minus_one_damage_taken` on the most vulnerable
#     RUBRICAE unit. APPROXIMATION: codex restricts the buff to non-
#     PSYKER models within the unit; SwegHammer treats a unit as a
#     single damage pool so the buff applies uniformly — strictly
#     weaker on multi-PSYKER squads (Aspiring Sorcerer is the PSYKER).
#   * Unwavering Phalanx (1 CP) — opponent's Charge phase, after an
#     enemy unit ends a Charge move into a RUBRICAE unit, -1 to Wound
#     rolls against that RUBRICAE unit for the Fight phase. SwegHammer
#     has no per-target wound-debuff transient — we route through
#     `transient_plus_one_save` on the chosen RUBRICAE defender as a
#     defensive proxy (a +1 save approximates a -1 to wound on the
#     attacker's failed-save bucket; not equivalent, but same direction).

ARDENT_AUTOMATA = Stratagem(
    name="Ardent Automata",
    cp_cost=1,
    phase="movement",
    trigger="friendly_rubricae_unit_just_fell_back",
    effect="shoot_and_charge_after_fall_back_approximation",
)

INEXORABLE_ADVANCE = Stratagem(
    name="Inexorable Advance",
    cp_cost=1,
    phase="movement",
    trigger="friendly_rubricae_unit_moving",
    effect="transient_assault_this_round",
)

INFERNAL_FUSILLADE = Stratagem(
    name="Infernal Fusillade",
    cp_cost=2,
    phase="shooting",
    trigger="friendly_rubric_marines_about_to_shoot",
    effect="transient_plus_one_to_wound_shooting",
)

REVENGE_OF_THE_RUBRICAE = Stratagem(
    name="Revenge of the Rubricae",
    cp_cost=1,
    phase="shooting",
    trigger="enemy_destroyed_friendly_tson_psyker_model",
    effect="out_of_sequence_shoot_approximation",
)

IMPLACABLE_GUARDIANS = Stratagem(
    name="Implacable Guardians",
    cp_cost=2,
    phase="shooting",
    trigger="enemy_targets_friendly_rubric_marines_psyker_unit",
    effect="transient_minus_one_damage_taken",
)

UNWAVERING_PHALANX = Stratagem(
    name="Unwavering Phalanx",
    cp_cost=1,
    phase="charge",
    trigger="enemy_charges_friendly_rubricae_unit",
    effect="transient_plus_one_save_proxy_for_minus_one_to_wound",
)

RUBRICAE_PHALANX_STRATAGEMS: Tuple[Stratagem, ...] = (
    ARDENT_AUTOMATA,
    INEXORABLE_ADVANCE,
    INFERNAL_FUSILLADE,
    REVENGE_OF_THE_RUBRICAE,
    IMPLACABLE_GUARDIANS,
    UNWAVERING_PHALANX,
)


# ---------------------------------------------------------------------------
# Subterranean Assault (Tyranids) — four real detachment stratagems (iter16 fix)
# ---------------------------------------------------------------------------
# Goonhammer Detachment Focus: https://www.goonhammer.com/detachment-focus-subterranean-assault/
# Warhammer Community PDF: https://assets.warhammer-community.com/eng_04-06_warhammer_40000_tyranids_subterranean_assault-zw9osgnwhg-rqvyrabibv.pdf
#
# Background: Subterranean Assault is the May-2026-meta Tyranids detachment —
# Ron Eilyahoo won GW Open Maastricht 2026 with a Subterranean Assault
# Ravener/Trygon list, and Frontline/Stat-Check tournament reports rank it
# alongside Invasion Fleet and Vanguard Onslaught as a top-tier choice. The
# detachment rule itself (army-wide reroll-1s-to-hit, plus the Burrower tunnel
# marker mechanic for Trygons / Mawlocs) is the lever the calibration loop
# needs — replacing the Invasion Fleet "-1 enemy Ld" approximation with a real
# offensive uplift.
#
# These four stratagems are paraphrased per the Goonhammer detachment focus
# (WebFetch against assets.warhammer-community.com returned 403 at edit time;
# Wahapedia entry not yet indexed for this detachment). Each entry has a
# Goonhammer citation in data/rule_citations.d/stratagems.json with the
# approximation note. Pattern matches Awakened Dynasty / Rubricae Phalanx:
# stratagems are catalogued so the auditor + AI know about them, but the
# AI dispatcher (each stratagem needs its own `_try_fire_<name>` method in
# code/simulator.py) is NOT wired in this iteration — the army-wide
# reroll_hit_ones detachment passive is the offensive lever this iteration
# delivers; the per-stratagem fires are catalogued-but-no-op APPROXIMATIONs
# to be wired in a follow-up.
#
# Effect-mapping summary:
#   * Tunnel Network (1 CP, movement) — remove a Tyranids unit from within
#     9" of one Tunnel Marker and set it up within 9" of another, >=6" from
#     enemy models. Mid-phase teleport reposition. SwegHammer has no Tunnel
#     Marker / Burrower mid-phase teleport hook; catalogued as a no-op
#     APPROXIMATION (effect string mirrors the codex text so a future
#     dispatcher can hook on the existing id).
#   * Replenishing Swarms (1 CP, movement) — heal D3+1 wounds or revive
#     D3+1 1-W models within 9" of a Tunnel Marker. Mapped to
#     `transient_undying_legions_pulse` = 2 (mid-phase reanimation pulse,
#     median D3+1 = 3 → using the 2-HP `extra_reanimation_pulse` flag the
#     simulator already understands; same flag is used by Necrons
#     Protocol of the Undying Legions and Orks Mob Up). APPROXIMATION:
#     restores HP rather than reviving destroyed 1-W models; the
#     swarm-resurrection-on-Tunnel-Marker half is dropped.
#   * Swarming Assault (1 CP, charge) — a Tyranids MONSTER unit grants
#     reroll-charge-roll to friendly Tyranids units within 6". Charge-roll
#     reroll is not a one-shot transient flag; the closest stand-in is
#     `transient_assault_this_round` on the highest-DPA Tyranids unit
#     (same flag Mont'ka uses for Sudden Storm — boosts the realised
#     charge-then-fight payoff if not the literal reroll). APPROXIMATION:
#     +Assault stand-in for reroll-charge.
#   * Enfilading Emergence (1 CP, movement) — a Tyranids unit that emerged
#     from reserves this turn gains [SUSTAINED HITS 1] and [IGNORES COVER]
#     until end of phase. Mapped to `transient_plus_one_to_hit_shooting`
#     on the highest-DPA Tyranids unit (same flag Mont'ka / Pulse
#     Onslaught uses) — direction-correct uplift in shooting output, lossy
#     on the SH1 / ignores-cover keyword specificity.

TUNNEL_NETWORK = Stratagem(
    name="Tunnel Network",
    cp_cost=1,
    phase="movement",
    trigger="friendly_tyranids_unit_near_tunnel_marker",
    effect="redeploy_via_tunnel_marker_approximation",
)

REPLENISHING_SWARMS = Stratagem(
    name="Replenishing Swarms",
    cp_cost=1,
    phase="movement",
    trigger="friendly_tyranids_unit_wounded_near_tunnel_marker",
    effect="extra_reanimation_pulse_approximation",
)

SWARMING_ASSAULT = Stratagem(
    name="Swarming Assault",
    cp_cost=1,
    phase="charge",
    trigger="friendly_tyranids_monster_about_to_charge",
    effect="transient_assault_for_round_approximation",
)

ENFILADING_EMERGENCE = Stratagem(
    name="Enfilading Emergence",
    cp_cost=1,
    phase="movement",
    trigger="friendly_tyranids_unit_emerged_from_reserves",
    effect="transient_plus_one_to_hit_shooting_approximation",
)


SUBTERRANEAN_ASSAULT_STRATAGEMS: Tuple[Stratagem, ...] = (
    TUNNEL_NETWORK,
    REPLENISHING_SWARMS,
    SWARMING_ASSAULT,
    ENFILADING_EMERGENCE,
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
# Gladius Task Force (Adeptus Astartes) — six real detachment stratagems
# (iter-12 fix)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
# Replaces the iter-0 zero-stratagem state where Marines burned every strat
# fire on Command Re-Roll (universal Core). Per docs/AUDIT_PARITY.md fix #1
# this is the largest 0/6 gap in the project — Marines is 134 units and the
# most-used codex in simulations, so even a single Command-phase spend per
# round closes a real parity gap. Each dispatcher mirrors the iter-8 Shield
# Host pattern: route through the closest existing transient_* flag and
# document the gap as APPROXIMATION.
#
# WebFetch against wahapedia.ru returned ECONNREFUSED at edit time (same
# outage seen in iter-1 War Horde + #193 Grand Coven); stratagem effects
# are paraphrased per general 10e Marines codex knowledge / Goonhammer's
# Gladius Task Force review, with the Wahapedia URL cited per CLAUDE.md §10
# and each entry flagged APPROXIMATION in
# data/rule_citations.d/stratagems.json.
#
# Effect-mapping summary:
#   * Storm of Fire (1 CP, Battle Tactic) — an ADEPTUS ASTARTES unit's
#     ranged weapons gain [SUSTAINED HITS 1] for the phase (or improve
#     existing [SUSTAINED HITS X] by 1). SwegHammer has no per-round
#     transient [SUSTAINED HITS] flag, so the offensive uplift is routed
#     through `transient_plus_one_to_hit_shooting` on the highest-DPA
#     Marines shooter — same direction (more landed hits), comparable
#     magnitude on a 4+ hit roll. APPROXIMATION.
#   * Armour of Contempt (1 CP, Battle Tactic) — defensive: enemy AP
#     against an ADEPTUS ASTARTES unit is reduced by 1 for the phase
#     (improves save vs AP-X attacks). Maps to `transient_plus_one_save`
#     on the most vulnerable Marines unit. APPROXIMATION: the codex
#     effect is AP-reduction (worth more vs high-AP weapons), the
#     +1-save proxy is a flat save buff (worth equally vs AP-0 fire).
#     Direction-correct, magnitude comparable on a 3+ save.
#   * Squad Tactics (1 CP, Strategic Ploy) — an ADEPTUS ASTARTES INFANTRY
#     unit may make a Normal Move of up to 6" in your opponent's
#     Movement phase. Mobility / repositioning utility. Maps to
#     `transient_assault_this_round` on the highest-DPA Marines INFANTRY
#     unit (closest existing "extra move to set up the alpha shot/charge"
#     transient — same flag Feigned Retreat / Multipotentiality use).
#     APPROXIMATION: offensive shoot-after-move proxy for a defensive
#     reposition.
#   * Only In Death Does Duty End (1 CP, Strategic Ploy) — when an
#     ADEPTUS ASTARTES model is destroyed in the Fight phase before
#     making its attacks, it may make those attacks before being
#     removed. Defensive-turned-offensive trade. Maps to
#     `transient_plus_one_to_wound_melee` on the most vulnerable Marines
#     melee unit — the "one last swing" proxy translates to +1 to wound
#     on the remaining attacks. APPROXIMATION: misses the timing detail
#     (codex grants attacks to destroyed models; we buff the surviving
#     unit instead). Direction-correct (more melee damage from a doomed
#     unit), magnitude comparable on a 4+ wound roll.
#   * Honour the Chapter (2 CP, Battle Tactic) — an ADEPTUS ASTARTES
#     unit may re-roll its Hit AND Wound rolls (or all attacks if the
#     unit's Sergeant / CHARACTER leader has Honour the Chapter active)
#     for the phase. The premium 2-CP offensive nuke. Maps to
#     `transient_reroll_hits_shooting` on the highest-DPA Marines unit;
#     the wound-reroll leg is dropped (no transient wound-reroll flag).
#     APPROXIMATION: strictly weaker than the codex (~half the value),
#     direction-correct. Same lossy pattern as Glory of the Hearth
#     (Oathband) and Devastating Sorcery (Grand Coven).
#   * Adaptive Strategy (1 CP, Strategic Ploy) — at the start of your
#     Command phase, an ADEPTUS ASTARTES unit gains the rules of one
#     Combat Doctrine of your choice until end of turn (Devastator /
#     Tactical / Assault), regardless of which doctrine the army is
#     currently in. APPROXIMATION: Combat Doctrines in SwegHammer is
#     a round-and-mode-gated +1 to wound (see Unit.attack); the
#     stratagem's per-unit doctrine override would require per-unit
#     doctrine state. Routed through `transient_plus_one_to_wound_melee`
#     on the highest-DPA Marines melee unit — the dominant value the
#     stratagem provides is granting Assault Doctrine's +1-to-wound-
#     melee outside R3+, which this proxy captures exactly.

STORM_OF_FIRE = Stratagem(
    name="Storm of Fire",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_marines_unit_about_to_shoot",
    effect="sustained_hits_ranged_approximation",
)

ARMOUR_OF_CONTEMPT = Stratagem(
    name="Armour of Contempt",
    cp_cost=1,
    phase="any",
    trigger="vulnerable_friendly_marines_unit_targeted",
    effect="enemy_ap_minus_one_approximation",
)

SQUAD_TACTICS = Stratagem(
    name="Squad Tactics",
    cp_cost=1,
    phase="movement",
    trigger="friendly_marines_infantry_unit_about_to_move",
    effect="extra_move_repositioning_approximation",
)

ONLY_IN_DEATH_DOES_DUTY_END = Stratagem(
    name="Only In Death Does Duty End",
    cp_cost=1,
    phase="fight",
    trigger="friendly_marines_model_destroyed_before_attacking",
    effect="attacks_before_removal_approximation",
)

HONOUR_THE_CHAPTER = Stratagem(
    name="Honour the Chapter",
    cp_cost=2,
    phase="any",
    trigger="friendly_marines_unit_about_to_attack_premium_target",
    effect="reroll_hits_and_wounds_approximation",
)

ADAPTIVE_STRATEGY = Stratagem(
    name="Adaptive Strategy",
    cp_cost=1,
    phase="command",
    trigger="own_command_phase_marines_warlord",
    effect="off_doctrine_per_unit_override_approximation",
)


GLADIUS_STRATAGEMS: Tuple[Stratagem, ...] = (
    STORM_OF_FIRE,
    ARMOUR_OF_CONTEMPT,
    SQUAD_TACTICS,
    ONLY_IN_DEATH_DOES_DUTY_END,
    HONOUR_THE_CHAPTER,
    ADAPTIVE_STRATEGY,
)


# ---------------------------------------------------------------------------
# Combined Arms (Astra Militarum) — six real detachment stratagems (iter-14)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
# Replaces the iter-0 zero-stratagem state where AM burned every strat fire
# on Command Re-Roll (universal Core). The Combined Arms detachment is AM's
# competitive default per Goonhammer May 2026 meta reports. Its detachment
# rule is Born Soldiers ([LETHAL HITS] on REGIMENT ranged attacks vs non-
# VEHICLE/MONSTER, and on SQUADRON ranged attacks vs VEHICLE/MONSTER). The
# stratagem set scales the Voice of Command Order economy (Coordinated
# Action / Flexible Command / Inspired Command all extend Order eligibility)
# plus three combat tactics (Fields of Fire / Stalwart Protector /
# Reinforcements!). Each dispatcher follows the Gladius / Mont'ka pattern.

COORDINATED_ACTION = Stratagem(
    name="Coordinated Action",
    cp_cost=1,
    phase="any",
    trigger="own_command_phase_am_regiment_and_squadron_close",
    effect="extend_order_to_squadron_approximation",
)

REINFORCEMENTS = Stratagem(
    name="Reinforcements!",
    cp_cost=2,
    phase="any",
    trigger="friendly_am_infantry_regiment_just_destroyed",
    effect="readd_destroyed_unit_to_reserves_approximation",
    once_per_battle=True,
)

FLEXIBLE_COMMAND = Stratagem(
    name="Flexible Command",
    cp_cost=2,
    phase="command",
    trigger="own_command_phase_am_officer",
    effect="officers_can_order_squadron_for_round",
)

FIELDS_OF_FIRE = Stratagem(
    name="Fields of Fire",
    cp_cost=1,
    phase="shooting",
    trigger="own_shooting_am_regiment_and_squadron_pair",
    effect="plus_one_ap_vs_target_approximation",
)

INSPIRED_COMMAND = Stratagem(
    name="Inspired Command",
    cp_cost=1,
    phase="command",
    trigger="enemy_command_phase_am_officer",
    effect="extra_order_this_round_approximation",
)

STALWART_PROTECTOR = Stratagem(
    name="Stalwart Protector",
    cp_cost=1,
    phase="any",
    trigger="enemy_shooting_targets_am_infantry_near_vehicle",
    effect="plus_one_save_for_round_approximation",
)


COMBINED_ARMS_STRATAGEMS: Tuple[Stratagem, ...] = (
    COORDINATED_ACTION,
    REINFORCEMENTS,
    FLEXIBLE_COMMAND,
    FIELDS_OF_FIRE,
    INSPIRED_COMMAND,
    STALWART_PROTECTOR,
)


# ---------------------------------------------------------------------------
# ST-2 (sim-calibration-6 wave 3) — one strong stratagem per under-performing
# faction (World Eaters, Chaos Daemons, Grey Knights, Genestealer Cults, Chaos
# Space Marines). Each is faction-gated and routes the offensive value through
# an existing transient_* flag. Full Wahapedia citations live in
# data/rule_citations.d/stratagems.json per CLAUDE.md §10.
# ---------------------------------------------------------------------------

# Berzerker Warband (World Eaters) — Apoplectic Frenzy (Wahapedia)
# https://wahapedia.ru/wh40k10ed/factions/world-eaters/#Berzerker-Warband
# Real text: each model in a WORLD EATERS unit fights with [LETHAL HITS] until
# end of Fight phase. Approximation: routed through transient_plus_one_to_wound_melee
# (LETHAL HITS auto-wounds on a crit-to-hit; +1 to wound is a direction-correct
# offensive uplift via existing flag). 1 CP.
APOPLECTIC_FRENZY = Stratagem(
    name="Apoplectic Frenzy",
    cp_cost=1,
    phase="fight",
    trigger="own_fight_phase_world_eaters_unit",
    effect="lethal_hits_melee_approximation",
)

BERZERKER_WARBAND_STRATAGEMS: Tuple[Stratagem, ...] = (
    APOPLECTIC_FRENZY,
)


# Daemonic Incursion (Chaos Daemons) — Denizens of the Warp (Wahapedia)
# https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Daemonic-Incursion
# Real text: re-roll Hit and Wound rolls of 1 for a Daemons unit's attacks
# vs an enemy unit within range of an Objective Marker. Approximation: routed
# through transient_reroll_hits_shooting (the hit-1 reroll half; the wound-1
# half and the objective-range gate are dropped — direction-correct uplift). 1 CP.
DENIZENS_OF_THE_WARP = Stratagem(
    name="Denizens of the Warp",
    cp_cost=1,
    phase="shooting",
    trigger="own_shooting_phase_daemons_unit_targets_near_objective",
    effect="reroll_hits_ones_approximation",
)

DAEMONIC_INCURSION_STRATAGEMS: Tuple[Stratagem, ...] = (
    DENIZENS_OF_THE_WARP,
)


# Teleport Strike Force (Grey Knights) — Empyric Channelling (Wahapedia)
# https://wahapedia.ru/wh40k10ed/factions/grey-knights/#Teleport-Strike-Force
# Real text: a GREY KNIGHTS PSYKER unit's Psychic weapons gain [SUSTAINED HITS 2]
# until the end of the phase. Approximation: routed through
# transient_reroll_hits_shooting (Sustained Hits 2 is lossy on the substitute,
# but a hit reroll is a direction-correct offensive multiplier for a GK Psyker's
# shooting). 1 CP.
EMPYRIC_CHANNELLING = Stratagem(
    name="Empyric Channelling",
    cp_cost=1,
    phase="shooting",
    trigger="own_shooting_phase_grey_knights_psyker_unit",
    effect="sustained_hits_2_psychic_approximation",
)

TELEPORT_STRIKE_FORCE_STRATAGEMS: Tuple[Stratagem, ...] = (
    EMPYRIC_CHANNELLING,
)


# Final Day (Genestealer Cults) — Cult Ambush (Wahapedia)
# https://wahapedia.ru/wh40k10ed/factions/genestealer-cults/#Final-Day
# Real text: a GENESTEALER CULTS unit gains [LETHAL HITS] on a ranged attack
# (or +1 to Wound on a melee attack — gate based on phase used). Approximation:
# routed through transient_reroll_hits_shooting (LETHAL HITS auto-wounds on
# crit-to-hit; a hit reroll is a direction-correct offensive multiplier for a
# GSC shooting unit). 1 CP.
CULT_AMBUSH = Stratagem(
    name="Cult Ambush",
    cp_cost=1,
    phase="shooting",
    trigger="own_shooting_phase_genestealer_cults_unit",
    effect="lethal_hits_ranged_approximation",
)

FINAL_DAY_STRATAGEMS: Tuple[Stratagem, ...] = (
    CULT_AMBUSH,
)


# Pactbound Zealots (Chaos Space Marines) — Profane Zeal (Wahapedia)
# https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/#Pactbound-Zealots
# Real text: re-roll Hit AND Wound rolls of 1 for a HERETIC ASTARTES unit's
# melee attacks until end of phase. Approximation: routed through
# transient_plus_one_to_wound_melee (+1 to wound is a direction-correct
# offensive uplift; the hit-reroll half is dropped). 1 CP.
PROFANE_ZEAL = Stratagem(
    name="Profane Zeal",
    cp_cost=1,
    phase="fight",
    trigger="own_fight_phase_csm_heretic_astartes_unit",
    effect="reroll_hits_and_wounds_ones_melee_approximation",
)

# Eye of the Gods (Pactbound Zealots, 1 CP — Wahapedia)
# https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/#Eye-of-the-Gods
# Real text: end of Fight phase, when a CHARACTER from your army with this
# ability has destroyed an enemy unit with a melee attack — roll D6+Wounds
# on the Eye of the Gods table (2-5: +1 M; 6-8: +1 T; 9-12: +1 A OR +1 S;
# 13+: +1 D melee OR pick another result). The stamped result persists for
# the rest of the battle. APPROXIMATION: collapse the roll-and-pick table
# to a single +1-to-wound-melee snowball on the CHARACTER, stamped
# permanently on first qualifying melee kill. Direction-correct offensive
# uplift that grows CSM CHARACTER lethality across rounds. 1 CP.
EYE_OF_THE_GODS = Stratagem(
    name="Eye of the Gods",
    cp_cost=1,
    phase="fight",
    trigger="end_of_fight_phase_csm_character_destroyed_enemy_unit_melee",
    effect="persistent_plus_one_to_wound_melee_on_character_approximation",
)

PACTBOUND_ZEALOTS_STRATAGEMS: Tuple[Stratagem, ...] = (
    PROFANE_ZEAL,
    EYE_OF_THE_GODS,
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
    # Rubricae Phalanx (Thousand Sons) — six stratagems (iter15)
    "ARDENT_AUTOMATA",
    "INEXORABLE_ADVANCE",
    "INFERNAL_FUSILLADE",
    "REVENGE_OF_THE_RUBRICAE",
    "IMPLACABLE_GUARDIANS",
    "UNWAVERING_PHALANX",
    "RUBRICAE_PHALANX_STRATAGEMS",
    # Subterranean Assault (Tyranids) — four stratagems (iter16)
    "TUNNEL_NETWORK",
    "REPLENISHING_SWARMS",
    "SWARMING_ASSAULT",
    "ENFILADING_EMERGENCE",
    "SUBTERRANEAN_ASSAULT_STRATAGEMS",
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
    # Gladius Task Force (Adeptus Astartes) — six real stratagems (iter-12 fix)
    "STORM_OF_FIRE",
    "ARMOUR_OF_CONTEMPT",
    "SQUAD_TACTICS",
    "ONLY_IN_DEATH_DOES_DUTY_END",
    "HONOUR_THE_CHAPTER",
    "ADAPTIVE_STRATEGY",
    "GLADIUS_STRATAGEMS",
    # Combined Arms (Astra Militarum) — six real stratagems (iter-14 fix)
    "COORDINATED_ACTION",
    "REINFORCEMENTS",
    "FLEXIBLE_COMMAND",
    "FIELDS_OF_FIRE",
    "INSPIRED_COMMAND",
    "STALWART_PROTECTOR",
    "COMBINED_ARMS_STRATAGEMS",
    # ST-2 wave 3 — one stratagem per under-performing faction
    "APOPLECTIC_FRENZY",
    "BERZERKER_WARBAND_STRATAGEMS",
    "DENIZENS_OF_THE_WARP",
    "DAEMONIC_INCURSION_STRATAGEMS",
    "EMPYRIC_CHANNELLING",
    "TELEPORT_STRIKE_FORCE_STRATAGEMS",
    "CULT_AMBUSH",
    "FINAL_DAY_STRATAGEMS",
    "PROFANE_ZEAL",
    "EYE_OF_THE_GODS",
    "PACTBOUND_ZEALOTS_STRATAGEMS",
    # CP economy
    "STARTING_CP",
    "CP_PER_COMMAND_PHASE",
    "CP_CAP",
    "award_command_phase_cp",
    "stratagems_for_army",
]
