"""
Detachment rules — army-wide passive buffs.

10e armies pick a Detachment at list-build time. Each detachment carries:
  - a passive "Detachment Rule" that applies to every model in the army
  - a Stratagem list (deferred — see Phase E)
  - an Enhancement list (deferred)

This module models JUST the always-on passive piece, captured as flags on a
`Detachment` dataclass. The simulator reads `Army.detachment` (if set) and
applies the matching modifiers during the relevant phase.

This is intentionally a thin MVP. Real 10e detachments have many bespoke
mechanics that can't be reduced to a flag (e.g. Oath of Moment picks a target
each turn; Reanimation Protocols restore W with specific roll mechanics).
We capture the headline effect of the canonical "first detachment" per
faction and document the simplification.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

from .enhancements import Enhancement, enhancements_for_detachment
from .stratagems import (
    Stratagem,
    WARHOST_STRATAGEMS,
    AWAKENED_DYNASTY_STRATAGEMS,
    DISGUSTINGLY_RESILIENT,
    MONTKA_STRATAGEMS,
    VIRULENT_VECTORIUM_STRATAGEMS,
    GRAND_COVEN_STRATAGEMS,
    RUBRICAE_PHALANX_STRATAGEMS,
    WAR_HORDE_STRATAGEMS,
    SHIELD_HOST_STRATAGEMS,
    OATHBAND_STRATAGEMS,
    GLADIUS_STRATAGEMS,
    COMBINED_ARMS_STRATAGEMS,
)


@dataclass(frozen=True)
class Detachment:
    """
    Army-wide passive modifiers. Most slots default to 'off'; setting a flag
    or value applies it to every friendly unit during the matching phase.

    The fields here are 10e-flavoured but lossy — see notes per detachment
    in DETACHMENTS for the rule each one approximates.
    """
    name: str
    faction: str
    notes: str = ""

    # Shooting / melee modifiers
    reroll_hit_ones: bool = False        # Re-roll natural 1s to hit (army-wide)
    reroll_wound_ones: bool = False      # Re-roll natural 1s to wound
    plus_one_to_hit: bool = False        # +1 to hit rolls (capped at 2+ canon)
    plus_one_to_wound: bool = False      # +1 to wound rolls
    plus_one_attack: int = 0             # Extra attacks per weapon (rare)

    # Defensive
    plus_one_save: bool = False          # +1 to armour save (cap 2+)
    extra_invuln: int = 7                # Cheap army-wide invuln (rare)
    fnp: int = 7                         # Army-wide Feel No Pain (7 = none)

    # Healing / recovery
    reanimate_per_round: int = 0         # W restored per unit per round end

    # Conditional attack buffs — apply only when the unit has an attached
    # friendly CHARACTER in aura range. Awakened Dynasty's Command
    # Protocols rule (Necrons 10e): "While a NECRONS CHARACTER model is
    # leading this unit, each time a model in this unit makes an attack,
    # add 1 to the Hit roll." The whole detachment's identity is "stack
    # characters into squads", so this is the right trigger to model.
    bonus_to_hit_when_led: bool = False

    # Psychic mortal-wound payload at end of each round. Models the
    # Thousand Sons Cabal-Points → Doombolt spell loop: the army's
    # collective psyker output cracks off N mortal wounds against the
    # highest-threat enemy, ignoring armour and toughness rolls. Median
    # of D3 = 2 maps cleanly to the typical Cult-of-Magic Doombolt yield.
    psychic_mortal_wounds_per_round: int = 0

    # Keyword-gated attack buffs introduced in #126 (second-detachment pass).
    # Each fires only when the ATTACKER unit matches the detachment's gate:
    #   * vehicles_reroll_hit_ones — Adeptus Astartes Ironstorm Spearhead.
    #     Friendly VEHICLE units re-roll Hit rolls of 1. Gate: attacker has
    #     the VEHICLE keyword.
    #   * canoptek_plus_one_to_wound — Necrons Canoptek Court. Friendly
    #     CANOPTEK units get +1 to wound rolls. Gate: attacker profile name
    #     starts with "Canoptek".
    #   * aspect_warrior_or_bike_plus_one_move — Aeldari Saim-Hann Wild Host.
    #     Aspect Warriors and Bike-mounted units gain +1" Movement. Gate:
    #     attacker profile name matches an Aspect Warrior datasheet (Howling
    #     Banshees, Striking Scorpions, Fire Dragons, Dark Reapers, Swooping
    #     Hawks, Warp Spiders, Shining Spears) or a bike chassis (Windriders,
    #     Shining Spears, Shroud Runners). Applied via `effective_move`.
    #   * plague_marines_plus_one_to_wound — Death Guard Plague Marines
    #     Onslaught. Plague Marines get +1 to wound rolls. Gate: attacker
    #     profile name == "Plague Marines".
    vehicles_reroll_hit_ones: bool = False
    canoptek_plus_one_to_wound: bool = False
    aspect_warrior_or_bike_plus_one_move: bool = False
    plague_marines_plus_one_to_wound: bool = False

    # Martial Grace — Warhost (Aeldari) detachment rule (#197). Real text:
    # "At the start of the battle round, you receive 1 additional Battle Focus
    # token. Each time a unit from your army performs the Swift as the Wind
    # Agile Manoeuvre, until the end of the phase, add an additional 1\" to
    # the Move characteristic of models in that unit. Each time a unit from
    # your army performs an Agile Manoeuvre that involves rolling a D6, add
    # 1 to the result." Modelled in the simulator as a +1 to the round-start
    # Battle Focus token refresh (so the Aeldari Agile Manoeuvre / Star
    # Engine spend is more readily available). The Swift-as-the-Wind +1"
    # move and the D6 +1 Agile-Manoeuvre boon are APPROXIMATED away — the
    # simulator's grid-free movement model can't usefully consume per-phase
    # +1" / +1-to-d6 buffs.
    martial_grace: bool = False

    # Mont'ka (T'au Empire) Killing Blow detachment rule (#196). Two flags,
    # both round-gated to battle rounds 1-3 by the simulator:
    #   * army_wide_assault_rounds_1_3 — grants the [ASSAULT] keyword to
    #     every T'AU EMPIRE ranged weapon during rounds 1-3. Read by
    #     `_do_shoot` to exempt T'au attackers from the Advance-then-
    #     no-shoot lockout (mirrors the Aeldari Battle Focus / Matchless
    #     Agility pathway, but army-wide and free during the window).
    #   * lethal_hits_on_guided — grants [LETHAL HITS] to Guided units'
    #     ranged weapons. Read by Unit.attack via the attacker's
    #     `Army.guided_enemy_uids` set (populated each round by
    #     Battle._run_markerlight_phase from alive MARKERLIGHT-keyword
    #     units in the T'au army). APPROXIMATION: the Mont'ka detachment
    #     text repeats the rounds-1-3 window for the LETHAL HITS half, but
    #     the underlying Markerlight army rule grants Guided-target
    #     LETHAL HITS in every Shooting phase, so SwegHammer applies the
    #     buff army-wide regardless of round when the flag is True.
    army_wide_assault_rounds_1_3: bool = False
    lethal_hits_on_guided: bool = False

    # Orks War Horde detachment rule (Get Stuck In). Real text (BSData
    # verbatim, v10.6.0): "Melee weapons equipped by ORKS models from your
    # army have the [SUSTAINED HITS 1] ability." Simulator gate: when this
    # flag is True AND the attacker is faction=="Orks" AND mode=="melee",
    # `Unit.attack` adds +1 to the sustained-hits multiplier on a crit-to-hit
    # (matches how per-weapon sustained_hits already composes). Army-wide
    # passive — no proximity / keyword filter beyond the Orks faction tag.
    melee_sustained_hits_army_wide: bool = False

    # Adeptus Custodes Shield Host detachment rule (Martial Ka'tah /
    # Martial Mastery). Wahapedia verbatim: "At the start of the battle
    # round, you can select one of the bullet points below. If you do,
    # until the start of the next battle round, that bullet point's
    # effects apply: Each time an ADEPTUS CUSTODES model from your army
    # with the Martial Ka'tah ability makes a melee attack, a successful
    # unmodified Hit roll of 5+ scores a Critical Hit. Improve the Armour
    # Penetration characteristic of melee weapons equipped by ADEPTUS
    # CUSTODES models from your army with the Martial Ka'tah ability
    # by 1." The detachment rule picks ONE bullet per round; SwegHammer's
    # simulator has no per-round selection hook so we apply BOTH bullets
    # army-wide for Adeptus Custodes melee attackers (offensive uplift
    # for the whole battle). APPROXIMATION: in real play the player
    # alternates per round between the Crit-on-5 stance and the AP+1
    # stance; modelling both as always-on is strictly stronger than the
    # codex but captures the dual offensive nature the iter-7 diagnostic
    # called out as missing.
    #
    # Simulator gates (both read in Unit.attack):
    #   * melee_crit_on_5_plus_hits — when True AND mode=="melee" AND
    #     attacker.faction == "Adeptus Custodes", a to-hit roll of 5+
    #     scores a Critical Hit (in addition to the canonical 6+).
    #   * melee_ap_plus_one — when True AND mode=="melee" AND
    #     attacker.faction == "Adeptus Custodes", the melee AP is
    #     improved by 1 (e.g. AP-1 -> AP-2).
    melee_crit_on_5_plus_hits: bool = False
    melee_ap_plus_one: bool = False

    # Astra Militarum Combined Arms detachment rule (Born Soldiers). Real text
    # (Wahapedia): "Each time a model in a REGIMENT unit from your army makes
    # a ranged attack that targets a visible unit (excluding MONSTERS and
    # VEHICLES), that attack has the [LETHAL HITS] ability. Each time a model
    # in a SQUADRON unit from your army makes a ranged attack that targets
    # a visible MONSTER or VEHICLE unit, that attack has the [LETHAL HITS]
    # ability." Simulator implementation (iter-14): a new flag
    # `am_born_soldiers_lethal_hits` read by `Unit.attack` when the attacker
    # faction is Astra Militarum, mode is ranged, and the keyword/role gate
    # matches (REGIMENT = INFANTRY-keyword non-VEHICLE/MONSTER; SQUADRON =
    # VEHICLE-keyword). The matrix gate (REGIMENT vs non-VEHICLE/MONSTER /
    # SQUADRON vs VEHICLE/MONSTER) is enforced inline at the LH branch.
    # APPROXIMATION: the codex uses bespoke keywords REGIMENT / SQUADRON
    # that don't appear as datasheet keywords in BSData v10.6.0; we map
    # REGIMENT → "INFANTRY" and SQUADRON → "VEHICLE" (matches the codex
    # split where REGIMENT covers the infantry rosters and SQUADRON covers
    # the Leman Russ / Sentinel / Rogal Dorn vehicle squadrons).
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
    am_born_soldiers_lethal_hits: bool = False

    # Thousand Sons Rubricae Phalanx detachment rule (All Is Dust). Wahapedia
    # verbatim: "Each time an attack with an unmodified Damage characteristic
    # of 1 is allocated to a RUBRICAE model from your army, add 1 to any
    # armour saving throw made against that attack." When this flag is True
    # AND the defender carries the RUBRICAE unit-keyword AND the incoming
    # attack's per_shot_dmg == 1.0, `Unit.attack` applies +1 to the defender's
    # armour save at the save-modifier layer (capped at 2+). Gated on this
    # detachment flag instead of always-firing for any TSON RUBRICAE defender;
    # this fixes the iter-14 APPROXIMATION where All Is Dust fired regardless
    # of which TSON detachment the army actually picked.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    all_is_dust: bool = False

    # Death Guard Virulent Vectorium detachment rule (Worldblight). Real text
    # (Wahapedia): "If you control an objective marker at the end of your
    # Command phase and a DEATH GUARD unit from your army (excluding Battle-
    # shocked units) is within range of that objective marker, that objective
    # marker remains under your control until your opponent's Level of Control
    # over that objective marker is greater than yours at the end of a phase.
    # In addition, until you lose control of that objective marker, it has
    # the Nurgle's Gift ability as if it were a DEATH GUARD model from your
    # army." Modelled as army-wide sticky-objective behaviour on DG units —
    # the Nurgle's-Gift-on-the-objective half is APPROXIMATED (not modelled).
    # Gate: at the end of each Command phase the simulator promotes any DG-
    # held objective into the sticky-owner set so it persists until an enemy
    # outscores the DG army on it (matches the real lock-until-flipped
    # mechanic; loses the contagion-on-objective half).
    worldblight_sticky_dg_objectives: bool = False

    # Morale
    ld_bonus: int = 0                    # +N to friendly Ld (lower target)
    enemy_ld_penalty: int = 0            # -N to enemy Ld (higher target)

    # Detachment-specific Stratagems. Empty for now — the four UNIVERSAL
    # Core Stratagems are always available regardless of detachment (see
    # code/stratagems.py). Detachment-specific entries land in #104.
    stratagems: Tuple[Stratagem, ...] = ()

    # Detachment-specific Enhancements (10e core: each Detachment offers a
    # short list of Warlord upgrades available to one CHARACTER each). A
    # `Detachment` instance carries the tuple statically; `army_builder`
    # picks one Enhancement at construction time and assigns it to a
    # CHARACTER. See `code.enhancements` for the dataclass + registry.
    enhancements: Tuple[Enhancement, ...] = ()

    # Composition affinity — used by the army builder to pick a detachment
    # that suits the actual unit mix. Not a rule, just a selection tag.
    # One of: "vehicle", "infantry", "monster", "character", "balanced", or
    # "" (no preference, treated as balanced for scoring purposes).
    preferred_composition: str = ""


# ---------------------------------------------------------------------------
# Canonical detachments — start small, one per major faction
# ---------------------------------------------------------------------------

GLADIUS_TASK_FORCE = Detachment(
    name="Gladius Task Force",
    faction="Adeptus Astartes",
    notes=(
        "Combat Doctrines: round-rotating +1 to wound active for ADEPTUS "
        "ASTARTES units (Devastator R1 ranged-only / Tactical R2 both / "
        "Assault R3+ melee-only). The doctrine rotation lives in Unit.attack, "
        "gated on this detachment's name + faction. Cited as "
        "`simulator.combat_doctrines`. The detachment dataclass intentionally "
        "carries no offensive flags — Doctrines is round-and-mode-gated, "
        "not a static buff, so it can't be reduced to a single boolean field. "
        "iter-12 fix: the six real Gladius detachment stratagems (Storm of "
        "Fire, Armour of Contempt, Squad Tactics, Only In Death Does Duty "
        "End, Honour the Chapter, Adaptive Strategy) are now attached via "
        "`stratagems=GLADIUS_STRATAGEMS`, closing docs/AUDIT_PARITY.md fix "
        "#1 (largest 0/6 gap)."
    ),
    stratagems=GLADIUS_STRATAGEMS,
    preferred_composition="balanced",
)

AWAKENED_DYNASTY = Detachment(
    name="Awakened Dynasty",
    faction="Necrons",
    notes=(
        "Reanimation Protocols: dead models flip back to alive at end of "
        "round (simulator handles this directly via reanimate_per_round + "
        "_apply_reanimation). PLUS Command Protocols (Wahapedia): '\"While "
        "a NECRONS CHARACTER model is leading this unit, each time a model "
        "in this unit makes an attack, add 1 to the Hit roll.\"' The whole "
        "detachment's offensive teeth are gated on being character-led; "
        "lone Warrior squads get nothing. Detachment stratagems (#194 "
        "rebuild) are the six real 'Protocol of the …' entries from the "
        "Necrons codex: Eternal Revenant, Undying Legions, Hungry Void, "
        "Sudden Storm, Conquering Tyrant, Vengeful Stars. Two of those "
        "(Eternal Revenant, Vengeful Stars) have no clean simulator hook "
        "and are catalogued-but-no-op APPROXIMATIONs; the other four map "
        "onto existing transient_* flags (plus a new "
        "transient_undying_legions_pulse for the extra reanimation pulse)."
    ),
    reanimate_per_round=1,
    bonus_to_hit_when_led=True,
    stratagems=AWAKENED_DYNASTY_STRATAGEMS,
    preferred_composition="balanced",
)

INVASION_FLEET = Detachment(
    name="Invasion Fleet",
    faction="Tyranids",
    notes=(
        "Shadow in the Warp: enemies have -1 Ld for Battleshock. Real rule "
        "is range-gated; we apply army-wide."
    ),
    # APPROXIMATION: always-on -1 Ld passive substitutes for a once-per-battle Battleshock test.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet
    # Real rule: Shadow in the Warp — once-per-battle army-wide Battleshock test, not a passive Ld debuff.
    enemy_ld_penalty=1,
    preferred_composition="balanced",
)

# WAAAGH_DETACHMENT (the "WAAAGH! Tribe" placeholder) was deleted per the
# 2026-05-15 fabrication audit (commit fa9a957). The detachment name was not
# in the 10e Orks codex — real Ork detachments are War Horde, Da Big Hunt,
# Kult of Speed, Dread Mob, Green Tide, Bully Boyz, Taktikal Brigade, More
# Dakka!, Freebooter Krew, Speedwaaagh!, Blitz Brigade. The army rule
# (WAAAGH! once-per-game declaration) is unaffected and stays in
# `simulator.waaagh`; a real detachment replacement lands in a follow-up.

NOBLE_LANCE = Detachment(
    name="Noble Lance",
    faction="Imperial Knights",
    notes=(
        "Code Chivalric: lossy as army-wide +1 to wound. Real rule has "
        "conditional triggers (charged turn, lance keyword)."
    ),
    plus_one_to_wound=True,
    preferred_composition="vehicle",
)

HALLOWED_MARTYRS = Detachment(
    name="Hallowed Martyrs",
    faction="Adepta Sororitas",
    notes=(
        "Sacrifice-themed: +1 to wound army-wide. Real rule triggers off "
        "destroyed Sororitas units; we apply it always-on for the MVP."
    ),
    plus_one_to_wound=True,
    preferred_composition="infantry",
)

SHIELD_HOST = Detachment(
    name="Shield Host",
    faction="Adeptus Custodes",
    notes=(
        "Martial Ka'tah / Martial Mastery (Wahapedia verbatim): \"At the "
        "start of the battle round, you can select one of the bullet "
        "points below. If you do, until the start of the next battle "
        "round, that bullet point's effects apply: Each time an ADEPTUS "
        "CUSTODES model from your army with the Martial Ka'tah ability "
        "makes a melee attack, a successful unmodified Hit roll of 5+ "
        "scores a Critical Hit. Improve the Armour Penetration "
        "characteristic of melee weapons equipped by ADEPTUS CUSTODES "
        "models from your army with the Martial Ka'tah ability by 1.\" "
        "Simulator implementation: both bullets are applied always-on for "
        "Adeptus Custodes melee attackers via `melee_crit_on_5_plus_hits` "
        "and `melee_ap_plus_one` (real codex picks ONE bullet per battle "
        "round). APPROXIMATION: dual offensive uplift instead of per-round "
        "alternation. Six real detachment stratagems wired (iter-8 fix, "
        "Wahapedia: Arcane Genetic Alchemy, Unwavering Sentinels, "
        "Multipotentiality, Vigilance Eternal, Archaeotech Munitions, "
        "Avenge the Fallen). Replaces the iter-0 `plus_one_save` "
        "approximation which inflated Custodes durability (defensive) "
        "rather than melee output (offensive). iter-7 diagnostic in "
        "docs/AUTO_LOOP_ITER7_DG_VS_CUSTODES.md identified this swap as "
        "the top fix for DG-vs-Custodes (+19.5pt residual over real meta)."
    ),
    # Real rule: Martial Ka'tah / Martial Mastery — Crit-on-5+ OR AP+1 on
    # melee attacks (offensive). One bullet per round in real play;
    # SwegHammer applies BOTH always-on as an APPROXIMATION.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    melee_crit_on_5_plus_hits=True,
    melee_ap_plus_one=True,
    stratagems=SHIELD_HOST_STRATAGEMS,
    preferred_composition="infantry",
)

SKITARII_HUNTER_COHORT = Detachment(
    name="Skitarii Hunter Cohort",
    faction="Adeptus Mechanicus",
    notes=(
        "Conqueror Doctrina Imperatives: lossy as army-wide re-roll hit 1s. "
        "Real rule rotates between offensive / defensive imperatives."
    ),
    reroll_hit_ones=True,
    preferred_composition="infantry",
)

INQUISITION_TASK_FORCE = Detachment(
    name="Inquisition Task Force",
    faction="Agents of the Imperium",
    notes=(
        "Inquisitorial Authority: re-roll hit 1s army-wide for the assembled "
        "Imperial agents. Real rule is bespoke per Inquisitor archetype."
    ),
    reroll_hit_ones=True,
    preferred_composition="balanced",
)

COMBINED_REGIMENT = Detachment(
    # iter-14: renamed to "Combined Arms" (Wahapedia codex name). The previous
    # "Combined Regiment" label was a SwegHammer mis-naming legacy. The
    # detachment rule is now the real "Born Soldiers" Lethal-Hits-on-Guided-
    # split-by-keyword rule rather than the previous +1-to-hit approximation,
    # plus the six real Combined Arms detachment stratagems and Voice of
    # Command Order economy (implemented in `code.orders`).
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
    name="Combined Arms",
    faction="Astra Militarum",
    notes=(
        "Born Soldiers (Wahapedia, verbatim): \"Each time a model in a "
        "REGIMENT unit from your army makes a ranged attack that targets a "
        "visible unit (excluding MONSTERS and VEHICLES), that attack has the "
        "[LETHAL HITS] ability. Each time a model in a SQUADRON unit from "
        "your army makes a ranged attack that targets a visible MONSTER or "
        "VEHICLE unit, that attack has the [LETHAL HITS] ability.\" Simulator "
        "implementation: a new flag `am_born_soldiers_lethal_hits` read by "
        "`Unit.attack` when the attacker faction is Astra Militarum and the "
        "REGIMENT/SQUADRON vs target-type matrix matches; the LH branch fires "
        "via the existing `effective_lethal_hits` plumbing. APPROXIMATION: "
        "the codex REGIMENT / SQUADRON keywords don't appear in BSData "
        "v10.6.0; we map REGIMENT → INFANTRY-keyword (non-VEHICLE/MONSTER) "
        "and SQUADRON → VEHICLE-keyword (matches the codex split). "
        "Voice of Command Order economy (iter-14): officers issue Orders to "
        "BATTLELINE INFANTRY units at the start of each Command phase via "
        "`code.orders.dispatch_orders` — see that module for the four wired "
        "Orders (Take Aim! / Fix Bayonets! / First Rank Fire Second Rank "
        "Fire! / Take Cover!). Six real detachment stratagems wired below "
        "(Coordinated Action, Reinforcements!, Flexible Command, Fields of "
        "Fire, Inspired Command, Stalwart Protector)."
    ),
    am_born_soldiers_lethal_hits=True,
    stratagems=COMBINED_ARMS_STRATAGEMS,
    preferred_composition="balanced",
)

TELEPORT_STRIKE_FORCE = Detachment(
    name="Teleport Strike Force",
    faction="Grey Knights",
    notes=(
        "Teleportarium precision: army-wide re-roll wound 1s. Real rule "
        "includes deep strike and bespoke psychic mechanics."
    ),
    reroll_wound_ones=True,
    preferred_composition="infantry",
)

WARHOST = Detachment(
    # #197: renamed from BATTLE_HOST (launch-index name) to WARHOST (codex
    # name). The detachment rule is now the real "Martial Grace" Battle
    # Focus token buff rather than the previous reroll_hit_ones approximation.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost
    name="Warhost",
    faction="Aeldari",
    notes=(
        "Martial Grace (Wahapedia): \"At the start of the battle round, you "
        "receive 1 additional Battle Focus token. Each time a unit from your "
        "army performs the Swift as the Wind Agile Manoeuvre, until the end "
        "of the phase, add an additional 1\" to the Move characteristic of "
        "models in that unit. Each time a unit from your army performs an "
        "Agile Manoeuvre that involves rolling a D6, add 1 to the result.\" "
        "Simulator implementation: the round-start Battle Focus token refresh "
        "for any Aeldari army is incremented by 1 when this detachment is "
        "active (gates on Detachment.martial_grace). The Swift-as-the-Wind "
        "+1\" move and the D6 +1 Agile-Manoeuvre boon are APPROXIMATED away "
        "— the grid-free movement model can't usefully consume per-phase "
        "+1\" / +1-to-d6 buffs. Detachment stratagems (six real entries, all "
        "from Wahapedia, #197): Lightning-Fast Reactions (+1 save), Fire and "
        "Fade (re-roll hits on a friendly Aeldari unit's shoot), Skyborne "
        "Sanctuary (+1 save proxy for end-of-fight re-embark), Feigned "
        "Retreat (transient Assault proxy for shoot-after-Fall-Back), "
        "Blitzing Firepower (+1 to hit shooting proxy for Sustained Hits 1), "
        "Webway Tunnel (+1 save proxy for end-of-enemy-fight reserve pull)."
    ),
    martial_grace=True,
    stratagems=WARHOST_STRATAGEMS,
    preferred_composition="infantry",
)

SKYSPLINTER_ASSAULT = Detachment(
    name="Skysplinter Assault",
    faction="Drukhari",
    notes=(
        "Hit-and-run raiders: approximated as army-wide re-roll wound 1s. "
        "Real rule grants +1 to wound on the turn a unit charged."
    ),
    reroll_wound_ones=True,
    preferred_composition="vehicle",
)

MONTKA = Detachment(
    name="Mont'ka",
    faction="T'au Empire",
    notes=(
        "Killing Blow (real 10e rule, #196). Two parts, both gated on "
        "battle rounds 1-3: every T'AU EMPIRE ranged weapon gains [ASSAULT] "
        "(simulator: army_wide_assault_rounds_1_3 — read by _do_shoot to "
        "exempt T'au attackers from the Advance-then-no-shoot lockout in "
        "rounds 1-3), AND Guided units' ranged weapons gain [LETHAL HITS] "
        "(simulator: lethal_hits_on_guided — read by Unit.attack via the "
        "attacker army's `guided_enemy_uids` set, populated each round by "
        "Battle._run_markerlight_phase from alive MARKERLIGHT-keyword units). "
        "Six real stratagems wired below from "
        "https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka."
    ),
    # Real rule: Killing Blow grants [ASSAULT] army-wide rounds 1-3 +
    # [LETHAL HITS] on Guided units during rounds 1-3.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka
    army_wide_assault_rounds_1_3=True,
    lethal_hits_on_guided=True,
    stratagems=MONTKA_STRATAGEMS,
    preferred_composition="balanced",
)

PACTBOUND_ZEALOTS = Detachment(
    name="Pactbound Zealots",
    faction="Chaos Space Marines",
    notes=(
        "Dark Pacts: lossy as army-wide re-roll wound 1s. Real rule grants "
        "Lethal Hits or Sustained Hits at the cost of Battleshock checks."
    ),
    reroll_wound_ones=True,
    preferred_composition="balanced",
)

# PLAGUE_COMPANY (Death Guard) and CULT_OF_MAGIC (Thousand Sons) were deleted
# per the 2026-05-15 fabrication audit (commit fa9a957). Neither detachment
# exists in the 10e codex. Real DG detachments: Virulent Vectorium,
# Mortarion's Hammer, Champions of Contagion, Tallyband Summoners,
# Shamblerot Vectorium, Death Lord's Chosen, Flyblown Host. Real TSons
# detachments: Grand Coven, Changehost of Deceit, Warpmeld Pact, Rubricae
# Phalanx, Warpforged Cabal, Hexwarp Thrallband. Disgustingly Resilient
# (the real DG stratagem) has been re-anchored to Virulent Vectorium at
# 2CP in code/stratagems.py.

VIRULENT_VECTORIUM = Detachment(
    name="Virulent Vectorium",
    faction="Death Guard",
    notes=(
        "Worldblight: at the end of each Command phase, any objective the DG "
        "army controls with a non-Battle-shocked DG unit in range stays "
        "locked to the DG army until the opponent's Level of Control on it "
        "exceeds the DG army's at the end of a phase. In addition, the "
        "objective gains Nurgle's Gift while locked (the contagion-on-"
        "objective half is APPROXIMATED — not modelled; only the sticky-"
        "control half is implemented). Six detachment stratagems wired: "
        "Putrid Detonation, Disgustingly Resilient, Plaguesurge, Leechspore "
        "Eruption, Overwhelming Generosity, Creeping Blight. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium"
    ),
    # APPROXIMATION: only the sticky-control half is modelled — the
    # "objective also has Nurgle's Gift" contagion-on-objective half is
    # dropped (we don't model objective markers as aura sources).
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium
    # Real rule: Worldblight — sticky control PLUS Nurgle's Gift on each
    # locked objective until the DG army loses control of it.
    worldblight_sticky_dg_objectives=True,
    stratagems=VIRULENT_VECTORIUM_STRATAGEMS,
    preferred_composition="infantry",
)


# ---------------------------------------------------------------------------
# Grand Coven (Thousand Sons) — psychic-pressure detachment (#193)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
#
# Detachment Rule (Kindred Sorcery, verbatim from BSData v10.6.0): once per
# battle each, the Thousand Sons player picks ONE of three abilities during
# their Command phase, active until the start of their next Command phase:
#   * Imbued Manifestation — +6" range to Psychic weapons
#   * Psychic Maelstrom — +1 to wound rolls with Psychic weapons
#   * Wrath of the Immaterium — Psychic weapons gain [DEVASTATING WOUNDS]
#
# The selectable, once-per-battle-each, Psychic-weapon-gated structure does
# not map cleanly onto any existing always-on transient_* flag, so we model
# the army's psychic teeth via the simulator-level Cabal of Sorcerers ritual
# pass (real 2D6 + optional D6 Psychic test) PLUS the legacy
# `psychic_mortal_wounds_per_round = 2` baseline (covering median-D3 Doombolt
# when the Ritual fails its test or no Ritual was selected). The Kindred
# Sorcery toggle itself remains UNIMPLEMENTED at the detachment-flag layer;
# see APPROXIMATION note below.

GRAND_COVEN = Detachment(
    name="Grand Coven",
    faction="Thousand Sons",
    notes=(
        "Kindred Sorcery (Wahapedia): once-per-battle-each selection of "
        "Imbued Manifestation (+6\" Psychic weapon range) / Psychic "
        "Maelstrom (+1 to wound with Psychic weapons) / Wrath of the "
        "Immaterium (Psychic weapons gain [DEVASTATING WOUNDS]). The army's "
        "core teeth is the Cabal of Sorcerers Rituals pass (handled in the "
        "simulator at start of Shooting phase, real 2D6+optional D6 Psychic "
        "test); the baseline `psychic_mortal_wounds_per_round=2` covers "
        "median-D3 Doombolt damage when the ritual pass produces no MW "
        "payload. Six real stratagems wired (Psychic Dominion, Destined by "
        "Fate, Egotistical Power, Desecration of Worlds, Arcane Focus, "
        "Devastating Sorcery)."
    ),
    # APPROXIMATION: Kindred Sorcery's selectable, once-per-battle Psychic-
    # weapon-keyword buff cannot reduce to a single static Detachment flag.
    # The Cabal of Sorcerers Rituals pass (real Psychic test, real WC values,
    # real D3 / D3+3 Doombolt math) is the actual implementation surface; the
    # `psychic_mortal_wounds_per_round=2` baseline is a fallback for rounds
    # where no Ritual fires successfully. Wahapedia URL above.
    # Real rule: per-Command-phase choose-one (range / wound / DevWounds) on
    # Psychic weapons, once-per-battle each; SwegHammer collapses to a flat
    # 2-MW-per-round payload + the Cabal Rituals pass.
    psychic_mortal_wounds_per_round=2,
    stratagems=GRAND_COVEN_STRATAGEMS,
    preferred_composition="infantry",
)


# ---------------------------------------------------------------------------
# Rubricae Phalanx (Thousand Sons) — All-Is-Dust durability detachment (iter15)
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
# 40k.app entry: https://www.40k.app/factions/thousand-sons/rules/detachment/rubricae-phalanx
#
# Detachment Rule (All Is Dust, verbatim from Wahapedia / 40k.app):
#   "Each time an attack with an unmodified Damage characteristic of 1 is
#    allocated to a RUBRICAE model from your army, add 1 to any armour
#    saving throw made against that attack."
#
# Modelled via the `all_is_dust` flag — gated in `Unit.attack` on the
# defender carrying the RUBRICAE keyword AND the incoming attack having
# per_shot_dmg == 1.0. Replaces the iter-14 always-firing behaviour, which
# applied the buff to RUBRICAE defenders regardless of which TSON
# detachment was selected. Real-meta TSON (May 2026) tournament lists are
# Rubricae Phalanx, not Grand Coven, so this detachment is the new
# DEFAULT_BY_FACTION["Thousand Sons"] target.
#
# Six detachment stratagems (verbatim names + CP costs from 40k.app /
# Goonhammer / Frontline Gaming Rubricae Phalanx breakdowns; WebFetch
# against wahapedia.ru returned ECONNREFUSED at edit time so verbatim
# WHEN/EFFECT blocks are paraphrased, with each citation flagged as such):
#   * Ardent Automata (1 CP) — RUBRICAE unit shoots/charges after Fall Back.
#   * Inexorable Advance (1 CP) — RUBRICAE unit ignores Move modifiers,
#     ranged weapons gain [ASSAULT] until end of turn.
#   * Infernal Fusillade (2 CP) — inferno bolt-pattern weapons on RUBRIC
#     MARINES gain [PSYCHIC] and S5 for the Shooting phase.
#   * Revenge of the Rubricae (1 CP) — opponent's Shooting phase, after a
#     friendly THOUSAND SONS PSYKER model is destroyed, a RUBRICAE unit
#     shoots the destroyer out of sequence.
#   * Implacable Guardians (2 CP) — opponent's Shooting phase, until end
#     of phase a RUBRIC MARINES PSYKER unit gets -1 to incoming Damage
#     for non-PSYKER models.
#   * Unwavering Phalanx (1 CP) — opponent's Charge phase, -1 to Wound
#     rolls against the RUBRICAE unit just charged for the Fight phase.

RUBRICAE_PHALANX = Detachment(
    name="Rubricae Phalanx",
    faction="Thousand Sons",
    notes=(
        "All Is Dust (Wahapedia verbatim): \"Each time an attack with an "
        "unmodified Damage characteristic of 1 is allocated to a RUBRICAE "
        "model from your army, add 1 to any armour saving throw made "
        "against that attack.\" Modelled via the `all_is_dust` flag, gated "
        "in `Unit.attack` on the defender carrying the RUBRICAE unit-keyword "
        "AND the incoming attack having per_shot_dmg == 1.0. iter15 adds "
        "this detachment as the real-meta TSON default (Rubricae Phalanx is "
        "the dominant May 2026 tournament list, displacing Grand Coven which "
        "remains opt-in for psyker-heavy lists). The Cabal of Sorcerers "
        "Ritual pass + the `psychic_mortal_wounds_per_round=0` baseline "
        "(NOT 2 — that lives on Grand Coven only) means TSON's psychic teeth "
        "is reduced when in Rubricae Phalanx; the durability uplift from "
        "All Is Dust + Rites of Coalescence + Daemon invulns offsets the "
        "loss. Six stratagems wired below — names + CP costs cross-checked "
        "against 40k.app + Goonhammer + Frontline Gaming; effect text "
        "paraphrased per CLAUDE.md §10 (WebFetch against wahapedia.ru "
        "returned ECONNREFUSED at edit time)."
    ),
    # Real rule: +1 to armour save vs unmodified D1 attacks on RUBRICAE models.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    all_is_dust=True,
    # Cabal of Sorcerers Ritual fallback baseline — matches Grand Coven's
    # `psychic_mortal_wounds_per_round=2` (median-D3 Doombolt). Cabal of
    # Sorcerers is the TSON army rule (faction-gated, not detachment-
    # gated), so it fires under EITHER detachment; the baseline is a
    # round-end MW payload that compensates when the stochastic 2D6
    # Psychic test in `_run_cabal_rituals` produces no manifested
    # Ritual. Same APPROXIMATION shape as GRAND_COVEN — see citation
    # `RUBRICAE_PHALANX.psychic_mortal_wounds_per_round` for full notes.
    psychic_mortal_wounds_per_round=2,
    stratagems=RUBRICAE_PHALANX_STRATAGEMS,
    preferred_composition="infantry",
)


WAR_HORDE = Detachment(
    name="War Horde",
    faction="Orks",
    notes=(
        "Get Stuck In (BSData v10.6.0 verbatim): \"Melee weapons equipped "
        "by ORKS models from your army have the [SUSTAINED HITS 1] "
        "ability.\" Army-wide passive — every Ork melee weapon picks up "
        "[SUSTAINED HITS 1] regardless of leader / aura / character-led "
        "state. Simulator implementation: a new flag "
        "`melee_sustained_hits_army_wide` read by `Unit.attack` when "
        "`mode == 'melee'` AND attacker is Orks; the per-weapon "
        "`sustained_hits` is incremented by 1 for the duration of the "
        "attack resolution, so a crit-to-hit generates one extra normal "
        "hit. Stacks additively with any weapon that already carries the "
        "ability (e.g. Flash Gitz Snazzguns) — matching the codex "
        "compounding (a SUSTAINED HITS 1 weapon with this detachment "
        "would become SUSTAINED HITS 2). Six real stratagems wired below "
        "from https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde "
        "per the iter-1 Cluster B diagnostic — Insane Bravery, Power Of "
        "The WAAAGH!, Mob Up, Big Krumpin', Tellyporta, Da Biggest Boss. "
        "Each is flagged APPROXIMATION where the simulator's transient_* "
        "plumbing can't capture the literal codex effect (see per-entry "
        "citations in data/rule_citations.d/stratagems.json)."
    ),
    melee_sustained_hits_army_wide=True,
    stratagems=WAR_HORDE_STRATAGEMS,
    preferred_composition="infantry",
)


BERZERKER_WARBAND = Detachment(
    name="Berzerker Warband",
    faction="World Eaters",
    notes=(
        "Blood Tithe frenzy: lossy as army-wide +1 to hit. Real rule spends "
        "Blood Tithe points on a roster of escalating effects."
    ),
    plus_one_to_hit=True,
    preferred_composition="infantry",
)

DAEMONIC_INCURSION = Detachment(
    name="Daemonic Incursion",
    faction="Chaos Daemons",
    notes=(
        "Shadow of Chaos: lossy as army-wide +1 to hit. Real rule grants "
        "Battle-shock immunity and bespoke god-specific buffs in friendly zones."
    ),
    plus_one_to_hit=True,
    preferred_composition="balanced",
)

FINAL_DAY = Detachment(
    name="Final Day",
    faction="Genestealer Cults",
    notes=(
        "Day of Reckoning: lossy as army-wide re-roll hit 1s. Real rule "
        "rotates between Ambush / Onslaught / Annihilation stages."
    ),
    reroll_hit_ones=True,
    preferred_composition="infantry",
)

# APPROXIMATION: "Oathband" is a generic stub; closest codex match is Hearthband.
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
# Real rule: codex Votann detachments are Needgaard Oathband, Persecution Prospect,
# Delve Assault Shift, Brandfast Oathband, Hearthfyre Arsenal, Hearthband, Mercenary Oathband.
OATHBAND = Detachment(
    name="Oathband",
    faction="Leagues of Votann",
    notes=(
        "Voidsmen Oaths: previously approximated as army-wide re-roll hit 1s "
        "because the real Eye of the Ancestors / Judgement Tokens rule was "
        "not modelled. Removed once `simulator.judgement_tokens` (Battle's "
        "per-army token store + Unit.attack re-roll buffs at 1+ / 3+ "
        "thresholds) landed — keeping the blanket re-roll on top of the real "
        "mechanic would double-stack the buff. Six real Oathband detachment "
        "stratagems wired (iter-9 fix, Wahapedia: Warrior Pride, Wrath of "
        "the Ancestors, Glory of the Hearth, Ironkin Sequence, Ancestral "
        "Sentence, Void-Armoured Resilience). Replaces the iter-0 zero-"
        "stratagem state where Votann fired Core only. iter-8 anti-DG "
        "audit (docs/AUTO_LOOP_ITER8_ANTI_DG_AUDIT.md fix #2) identified "
        "this set as the top fix for Votann-vs-DG (~+8pt over real meta)."
    ),
    stratagems=OATHBAND_STRATAGEMS,
    preferred_composition="balanced",
)


# ---------------------------------------------------------------------------
# Second detachments per major faction (#126). Each is keyword-gated so the
# buff only fires on the units the codex actually empowers — not army-wide.
# ---------------------------------------------------------------------------

IRONSTORM_SPEARHEAD = Detachment(
    name="Ironstorm Spearhead",
    faction="Adeptus Astartes",
    notes=(
        "Armoured Superiority: friendly VEHICLE units re-roll Hit rolls of 1. "
        "Lossy approximation of the canonical 'Armour of Contempt'-style "
        "vehicle-themed buffs in the launch-day Ironstorm Spearhead index; "
        "the codex replacement carries a similar VEHICLE-keyword reroll "
        "spine. Gate: attacker has the VEHICLE keyword."
    ),
    # APPROXIMATION: offensive vehicle hit-reroll stands in for a defensive AP debuff.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Ironstorm-Spearhead
    # Real rule: Armour of Contempt — -1 AP on Marine models (defensive), not vehicle hit rerolls (offensive).
    vehicles_reroll_hit_ones=True,
    preferred_composition="vehicle",
)

CANOPTEK_COURT = Detachment(
    name="Canoptek Court",
    faction="Necrons",
    notes=(
        "Canoptek-led command: friendly CANOPTEK units gain +1 to Wound "
        "rolls. Lossy approximation of the Canoptek Court detachment's "
        "Cryptek-led repair / acceleration buffs; we collapse the bundle "
        "into a flat +1 to wound on the Canoptek chassis. Gate: attacker "
        "profile name starts with 'Canoptek'."
    ),
    # APPROXIMATION: always-on +1 to wound stands in for a once-per-battle full wound reroll.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Canoptek-Court
    # Real rule: Hyper-Logical Strategy — once-per-battle full reroll, not always-on +1 to wound.
    canoptek_plus_one_to_wound=True,
    preferred_composition="balanced",
)

# SAIM_HANN_WILD_HOST (Aeldari) and PLAGUE_MARINES_ONSLAUGHT (Death Guard)
# were deleted per the 2026-05-15 fabrication audit (commit fa9a957).
# Neither detachment exists in the 10e codices. Real Aeldari detachments
# include Warhost, Windrider Host, Spirit Conclave, Guardian Battlehost,
# Ghosts of the Webway, Devoted of Ynnead, Seer Council, Aspect Host,
# Armoured Warhost, Serpent's Brood, Eldritch Raiders, Corsair Coterie.
# Real DG detachments are listed at PLAGUE_COMPANY's removal note above.
# Real detachment replacements land per-faction.


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DETACHMENTS: Dict[str, Detachment] = {
    "gladius_task_force":      GLADIUS_TASK_FORCE,
    "awakened_dynasty":        AWAKENED_DYNASTY,
    "invasion_fleet":          INVASION_FLEET,
    "noble_lance":             NOBLE_LANCE,
    "hallowed_martyrs":        HALLOWED_MARTYRS,
    "shield_host":             SHIELD_HOST,
    "skitarii_hunter_cohort":  SKITARII_HUNTER_COHORT,
    "inquisition_task_force":  INQUISITION_TASK_FORCE,
    "combined_regiment":       COMBINED_REGIMENT,
    "teleport_strike_force":   TELEPORT_STRIKE_FORCE,
    "warhost":                 WARHOST,
    "skysplinter_assault":     SKYSPLINTER_ASSAULT,
    "montka":                  MONTKA,
    "pactbound_zealots":       PACTBOUND_ZEALOTS,
    "berzerker_warband":       BERZERKER_WARBAND,
    "daemonic_incursion":      DAEMONIC_INCURSION,
    "final_day":               FINAL_DAY,
    "oathband":                OATHBAND,
    # Second detachments per major faction (#126).
    "ironstorm_spearhead":     IRONSTORM_SPEARHEAD,
    "canoptek_court":          CANOPTEK_COURT,
    # Death Guard real-codex detachment (#195). Wired with full 6-stratagem
    # set and Worldblight rule (sticky-control APPROXIMATION).
    "virulent_vectorium":      VIRULENT_VECTORIUM,
    # Thousand Sons real detachment (#193).
    "grand_coven":             GRAND_COVEN,
    # Thousand Sons Rubricae Phalanx detachment (iter15). Real-meta default
    # for May 2026 — Grand Coven retained as opt-in for psyker-heavy lists.
    "rubricae_phalanx":        RUBRICAE_PHALANX,
    # Orks real-codex detachment (War Horde, iter-1 Cluster B B1 fix). Wired
    # with full 6-stratagem set and the Get Stuck In army-wide [SUSTAINED
    # HITS 1] melee passive.
    "war_horde":               WAR_HORDE,
    # Deleted per fabrication audit fa9a957: waaagh_tribe, plague_company,
    # cult_of_magic, saim_hann_wild_host, plague_marines_onslaught. Real
    # codex detachment replacements land in per-faction follow-up commits.
}


# Bind enhancement tuples onto each Detachment whose key has a wired entry
# in `enhancements_for_detachment`. Uses dataclasses.replace because
# `Detachment` is frozen — this produces a new Detachment instance and
# replaces the registry entry in-place. Detachments with no wired
# enhancements keep the default empty tuple.
import dataclasses as _dc
for _key, _det in list(DETACHMENTS.items()):
    _enh = enhancements_for_detachment(_key)
    if _enh:
        DETACHMENTS[_key] = _dc.replace(_det, enhancements=_enh)
# Clean up the loop variables so `dir(detachments)` doesn't expose a stray
# `_det` Detachment instance that the rule auditor would otherwise scan for
# citations. The trailing underscore-prefixed names from the for-loop survive
# scope otherwise (CPython doesn't garbage-collect loop locals in module
# bodies), and the audit picked up the last-iteration Detachment as a
# spurious `_det.<field>` citation requirement.
del _key, _det, _enh, _dc
# Re-bind the module-level constants so downstream `from .detachments import
# GLADIUS_TASK_FORCE` callers see the patched-with-enhancements instance.
GLADIUS_TASK_FORCE = DETACHMENTS["gladius_task_force"]
AWAKENED_DYNASTY   = DETACHMENTS["awakened_dynasty"]
MONTKA             = DETACHMENTS["montka"]
VIRULENT_VECTORIUM = DETACHMENTS["virulent_vectorium"]
GRAND_COVEN        = DETACHMENTS["grand_coven"]
RUBRICAE_PHALANX   = DETACHMENTS["rubricae_phalanx"]
WAR_HORDE          = DETACHMENTS["war_horde"]
SHIELD_HOST        = DETACHMENTS["shield_host"]
OATHBAND           = DETACHMENTS["oathband"]
COMBINED_REGIMENT  = DETACHMENTS["combined_regiment"]
# Codex-correct alias — the detachment was renamed from "Combined Regiment"
# (SwegHammer launch label) to "Combined Arms" (Wahapedia codex name) in
# iter-14. The legacy COMBINED_REGIMENT module symbol + "combined_regiment"
# registry key are preserved so downstream test/import paths don't break.
COMBINED_ARMS      = DETACHMENTS["combined_regiment"]
# CULT_OF_MAGIC and PLAGUE_COMPANY re-bindings removed per fabrication
# audit (commit fa9a957); the detachments themselves are gone.

# Default detachment per faction (used when Army.detachment is None and a
# faction is known). Picks a sensible competitive default; user can override.
DEFAULT_BY_FACTION: Dict[str, str] = {
    "Adeptus Astartes":         "gladius_task_force",
    "Ultramarines":             "gladius_task_force",
    "Blood Angels":             "gladius_task_force",
    "Dark Angels":              "gladius_task_force",
    "Black Templars":           "gladius_task_force",
    "Space Wolves":             "gladius_task_force",
    "Salamanders":              "gladius_task_force",
    "Imperial Fists":           "gladius_task_force",
    "Iron Hands":               "gladius_task_force",
    "Raven Guard":              "gladius_task_force",
    "White Scars":              "gladius_task_force",
    "Deathwatch":               "gladius_task_force",
    "Necrons":                  "awakened_dynasty",
    "Tyranids":                 "invasion_fleet",
    # Orks: real codex detachment "War Horde" wired in iter-1 Cluster B B1.
    "Orks":                     "war_horde",
    "Imperial Knights":         "noble_lance",
    "Chaos Knights":            "noble_lance",
    "Adepta Sororitas":         "hallowed_martyrs",
    "Adeptus Custodes":         "shield_host",
    "Adeptus Mechanicus":       "skitarii_hunter_cohort",
    "Agents of the Imperium":   "inquisition_task_force",
    "Imperial Agents":          "inquisition_task_force",
    "Astra Militarum":          "combined_regiment",
    "Grey Knights":             "teleport_strike_force",
    "Aeldari":                  "warhost",
    "Aeldari (Craftworlds)":    "warhost",
    "Ynnari":                   "warhost",
    "Drukhari":                 "skysplinter_assault",
    "T'au Empire":              "montka",
    "Tau Empire":               "montka",
    "Chaos Space Marines":      "pactbound_zealots",
    "Heretic Astartes":         "pactbound_zealots",
    # Death Guard: real codex detachment "Virulent Vectorium" wired in #195.
    # Thousand Sons: iter15 promotes Rubricae Phalanx (All Is Dust durability
    # spine, real-meta May 2026 default) over Grand Coven (psyker-heavy
    # opt-in, still in the registry + FACTION_DETACHMENTS for variety picks).
    # See `RUBRICAE_PHALANX` notes for the All-Is-Dust rule + 6 stratagems.
    "Death Guard":              "virulent_vectorium",
    "Thousand Sons":            "rubricae_phalanx",
    "World Eaters":             "berzerker_warband",
    "Chaos Daemons":            "daemonic_incursion",
    "Genestealer Cults":        "final_day",
    "Leagues of Votann":        "oathband",
}


def default_detachment_for_faction(faction: str) -> Optional[Detachment]:
    """Return the canonical detachment for a faction, or None if unmapped."""
    key = DEFAULT_BY_FACTION.get(faction)
    return DETACHMENTS.get(key) if key else None


# ---------------------------------------------------------------------------
# Composition-driven detachment selection (Phase: army-builder picker)
# ---------------------------------------------------------------------------

# All detachments registered for a faction. For now most factions only have
# one entry — the catalogue expands in #104. Tuples preserve insertion order
# so the picker is deterministic given a seeded RNG.
FACTION_DETACHMENTS: Dict[str, Tuple[str, ...]] = {
    # Marines chapters now carry BOTH Gladius Task Force (balanced) and
    # Ironstorm Spearhead (vehicle-heavy) per #126. Picker selects by army
    # composition: vehicle-dominant rosters favour Ironstorm.
    "Adeptus Astartes":         ("gladius_task_force", "ironstorm_spearhead"),
    "Ultramarines":             ("gladius_task_force", "ironstorm_spearhead"),
    "Blood Angels":             ("gladius_task_force", "ironstorm_spearhead"),
    "Dark Angels":              ("gladius_task_force", "ironstorm_spearhead"),
    "Black Templars":           ("gladius_task_force", "ironstorm_spearhead"),
    "Space Wolves":             ("gladius_task_force", "ironstorm_spearhead"),
    "Salamanders":              ("gladius_task_force", "ironstorm_spearhead"),
    "Imperial Fists":           ("gladius_task_force", "ironstorm_spearhead"),
    "Iron Hands":               ("gladius_task_force", "ironstorm_spearhead"),
    "Raven Guard":              ("gladius_task_force", "ironstorm_spearhead"),
    "White Scars":              ("gladius_task_force", "ironstorm_spearhead"),
    "Deathwatch":               ("gladius_task_force", "ironstorm_spearhead"),
    # Necrons: Awakened Dynasty (balanced character-led) vs Canoptek Court
    # (boosts Canoptek chassis). Picker tilts toward Canoptek when the
    # army leans on its Canoptek units.
    "Necrons":                  ("awakened_dynasty", "canoptek_court"),
    "Tyranids":                 ("invasion_fleet",),
    # Orks: War Horde wired in iter-1 Cluster B B1 (real codex detachment).
    # Other 10e Ork detachments (Green Tide, Bully Boyz, Kult of Speed,
    # Dread Mob, Da Big Hunt, Taktikal Brigade, More Dakka!, Freebooter
    # Krew, Speedwaaagh!, Blitz Brigade) remain UNIMPLEMENTED — they land
    # in per-detachment follow-up tasks.
    "Orks":                     ("war_horde",),
    "Imperial Knights":         ("noble_lance",),
    "Chaos Knights":            ("noble_lance",),
    "Adepta Sororitas":         ("hallowed_martyrs",),
    "Adeptus Custodes":         ("shield_host",),
    "Adeptus Mechanicus":       ("skitarii_hunter_cohort",),
    "Agents of the Imperium":   ("inquisition_task_force",),
    "Imperial Agents":          ("inquisition_task_force",),
    "Astra Militarum":          ("combined_regiment",),
    "Grey Knights":             ("teleport_strike_force",),
    # Aeldari: Warhost only (renamed from "battle_host" in #197 to match
    # the codex name). saim_hann_wild_host was deleted per fabrication
    # audit fa9a957 (closest real: Windrider Host).
    "Aeldari":                  ("warhost",),
    "Aeldari (Craftworlds)":    ("warhost",),
    "Ynnari":                   ("warhost",),
    "Drukhari":                 ("skysplinter_assault",),
    "T'au Empire":              ("montka",),
    "Tau Empire":               ("montka",),
    "Chaos Space Marines":      ("pactbound_zealots",),
    "Heretic Astartes":         ("pactbound_zealots",),
    # Death Guard: real codex detachment "Virulent Vectorium" wired in #195.
    # Thousand Sons: Rubricae Phalanx (real-meta May 2026 default, durability
    # spine) PLUS Grand Coven (psyker-heavy opt-in). The picker scores both
    # against the army composition; INFANTRY-dominant lists with RUBRICAE
    # squads naturally tilt toward Rubricae Phalanx.
    "Death Guard":              ("virulent_vectorium",),
    "Thousand Sons":            ("rubricae_phalanx", "grand_coven"),
    "World Eaters":             ("berzerker_warband",),
    "Chaos Daemons":            ("daemonic_incursion",),
    "Genestealer Cults":        ("final_day",),
    "Leagues of Votann":        ("oathband",),
}


def _army_composition_signature(units) -> Dict[str, float]:
    """
    Compute the fraction of total army points spent on each composition tag.

    Returns a dict with keys:
      - vehicle_fraction: VEHICLE units
      - infantry_fraction: INFANTRY units that aren't also VEHICLE
      - monster_fraction: MONSTER units
      - character_fraction: CHARACTER units

    Buckets are not mutually exclusive (a CHARACTER may also be INFANTRY) —
    each fraction is computed independently against total spent points. An
    empty army returns all zeros.

    `units` may be a list of `Unit` instances (with `.profile`) or a list of
    `UnitProfile` instances directly — both are supported so the picker can
    be called during army construction.
    """
    def _profile(u):
        return u.profile if hasattr(u, "profile") else u

    def _kw(u) -> set:
        return set(_profile(u).unit_keywords or ())

    def _pts(u) -> float:
        return float(_profile(u).points_cost)

    total = sum(_pts(u) for u in units)
    if total <= 0:
        return {
            "vehicle_fraction": 0.0,
            "infantry_fraction": 0.0,
            "monster_fraction": 0.0,
            "character_fraction": 0.0,
        }

    vehicle_pts = sum(_pts(u) for u in units if "VEHICLE" in _kw(u))
    infantry_pts = sum(
        _pts(u) for u in units
        if "INFANTRY" in _kw(u) and "VEHICLE" not in _kw(u)
    )
    monster_pts = sum(_pts(u) for u in units if "MONSTER" in _kw(u))
    character_pts = sum(_pts(u) for u in units if "CHARACTER" in _kw(u))

    return {
        "vehicle_fraction": vehicle_pts / total,
        "infantry_fraction": infantry_pts / total,
        "monster_fraction": monster_pts / total,
        "character_fraction": character_pts / total,
    }


def _dominant_composition(composition: Dict[str, float]) -> str:
    """
    Return the composition tag with the largest fraction, or "balanced" if
    no single bucket dominates (max fraction < 0.4). CHARACTER is excluded
    from the dominance check — characters ride alongside other unit types
    and shouldn't outweigh the army's actual chassis mix.
    """
    chassis = {
        "vehicle":  composition.get("vehicle_fraction", 0.0),
        "infantry": composition.get("infantry_fraction", 0.0),
        "monster":  composition.get("monster_fraction", 0.0),
    }
    best = max(chassis, key=chassis.get)
    if chassis[best] < 0.4:
        return "balanced"
    return best


# Aspect Warrior / Bike datasheet names — used by the Saim-Hann picker
# affinity (and by `effective_move` to gate the +1" Movement buff). Matched
# against `UnitProfile.name` exactly.
ASPECT_WARRIOR_OR_BIKE_NAMES: Tuple[str, ...] = (
    "Howling Banshees",
    "Striking Scorpions",
    "Fire Dragons",
    "Dark Reapers",
    "Swooping Hawks",
    "Warp Spiders",
    "Shining Spears",
    "Windriders",
    "Shroud Runners",
)


def _keyword_affinity_score(det: Detachment, units) -> float:
    """Bonus score for detachments whose gate matches a sizable chunk of the
    army's points. Returns 0 when the detachment has no keyword gate; up to
    +20 when >=30% of points fit the gate (i.e. the detachment's buff would
    fire on a meaningful slice of the army).

    Each gate is checked against the actual unit list via the same predicates
    `effective_buffs` / `effective_move` use at runtime, so the picker and
    the simulator agree on what counts as a "Canoptek" / "Plague Marines"
    / Aspect-or-Bike unit.
    """
    def _profile(u):
        return u.profile if hasattr(u, "profile") else u
    def _pts(u) -> float:
        return float(_profile(u).points_cost)
    def _kw(u) -> set:
        return set(_profile(u).unit_keywords or ())
    def _name(u) -> str:
        return _profile(u).name or ""

    total = sum(_pts(u) for u in units)
    if total <= 0:
        return 0.0

    if det.canoptek_plus_one_to_wound:
        matched = sum(_pts(u) for u in units if _name(u).startswith("Canoptek"))
    elif det.plague_marines_plus_one_to_wound:
        matched = sum(_pts(u) for u in units if _name(u) == "Plague Marines")
    elif det.aspect_warrior_or_bike_plus_one_move:
        matched = sum(
            _pts(u) for u in units if _name(u) in ASPECT_WARRIOR_OR_BIKE_NAMES
        )
    elif det.vehicles_reroll_hit_ones:
        # VEHICLE already drives `preferred_composition="vehicle"`, but the
        # keyword affinity adds an extra nudge so Ironstorm dominates when
        # the army is genuinely tank-heavy rather than relying on the
        # chassis-dominant heuristic alone.
        matched = sum(_pts(u) for u in units if "VEHICLE" in _kw(u))
    elif det.all_is_dust:
        # Rubricae Phalanx (iter16): the All Is Dust buff fires on the
        # RUBRICAE unit-keyword (Rubric Marines, Scarab Occult Terminators).
        # Without this affinity, Grand Coven (Rubricae Phalanx's only
        # competitor in FACTION_DETACHMENTS["Thousand Sons"]) wins the
        # coin-flip ~50% even though the army is RUBRICAE-heavy. Push
        # Rubricae Phalanx to the front when the army's RUBRICAE points
        # share is non-trivial.
        matched = sum(_pts(u) for u in units if "RUBRICAE" in _kw(u))
    else:
        return 0.0

    fraction = matched / total
    if fraction >= 0.3:
        return 20.0
    if fraction >= 0.15:
        return 10.0
    return 0.0


def _score_detachment_for_army(
    det: Detachment,
    composition: Dict[str, float],
    units=None,
) -> float:
    """
    Score a detachment against an army composition. +10 if the detachment's
    `preferred_composition` matches the dominant chassis tag; 0 otherwise.
    An untagged ("") detachment is treated as "balanced".

    If `units` is provided, ADD a keyword-affinity bonus for the four #126
    second detachments whose buff fires only on specific datasheet keywords
    (Canoptek / Plague Marines / Aspect-or-Bike / VEHICLE) — see
    `_keyword_affinity_score`. The two-stage score lets the chassis tag
    drive coarse picks (which composition is dominant) while the keyword
    affinity layers in finer disambiguation (a Necron army that is 40%
    Canoptek points tilts firmly to Canoptek Court, not Awakened Dynasty).
    """
    dominant = _dominant_composition(composition)
    pref = det.preferred_composition or "balanced"
    score = 10.0 if pref == dominant else 0.0
    if units is not None:
        score += _keyword_affinity_score(det, units)
    return score


def effective_move(unit) -> float:
    """Movement allowance for `unit` after detachment passives.

    Reads `unit.profile.move` and adds any detachment-side movement bonus
    that gates on the attacker. Currently only Saim-Hann Wild Host
    (`aspect_warrior_or_bike_plus_one_move`) — Aspect Warriors and Bike
    chassis units gain +1" Movement.

    Falls back cleanly when the unit has no army_ref / no detachment, so
    catalogue and unit-test code paths that construct bare Units still
    work. Cited as `SAIM_HANN_WILD_HOST.aspect_warrior_or_bike_plus_one_move`.
    """
    base = float(getattr(unit.profile, "move", 6.0) or 6.0)
    army = getattr(unit, "army_ref", None)
    if army is None:
        return base
    try:
        det = army.resolve_detachment()
    except Exception:
        det = None
    if det is None:
        return base
    if getattr(det, "aspect_warrior_or_bike_plus_one_move", False):
        name = getattr(unit.profile, "name", "") or ""
        if name in ASPECT_WARRIOR_OR_BIKE_NAMES:
            return base + 1.0
    return base


def pick_detachment_for_army(
    faction: str,
    units,
    rng: Optional[random.Random] = None,
) -> Optional[Detachment]:
    """
    Pick a detachment that fits the army's composition.

    - If the faction has zero registered detachments, falls back to the
      `DEFAULT_BY_FACTION` resolver and returns whatever that gives (may be
      None for unmapped factions).
    - If exactly one detachment is registered, returns it deterministically.
    - Otherwise scores each candidate against the composition and picks
      weighted-randomly so the top-scoring detachment dominates (~60%) but
      lower-scoring variants still appear occasionally for variety.

    `units` accepts the same forms as `_army_composition_signature`.
    """
    if rng is None:
        rng = random.Random()

    keys = FACTION_DETACHMENTS.get(faction, ())
    if not keys:
        return default_detachment_for_faction(faction)

    if len(keys) == 1:
        return DETACHMENTS[keys[0]]

    candidates = [DETACHMENTS[k] for k in keys if k in DETACHMENTS]
    if not candidates:
        return default_detachment_for_faction(faction)
    if len(candidates) == 1:
        return candidates[0]

    composition = _army_composition_signature(units)
    scores = [
        _score_detachment_for_army(d, composition, units=units)
        for d in candidates
    ]

    # Weight: best-scoring detachment gets a soft majority, not a landslide.
    # With +10 for a match and 0 otherwise, exp(s / 25) yields a ~60/40 split
    # between matching vs non-matching in the N=2 case
    # (exp(0.4) / (exp(0.4) + 1) ≈ 0.598). Variants still surface so the
    # picker doesn't collapse to a deterministic best.
    import math
    weights = [math.exp(s / 25.0) for s in scores]
    return rng.choices(candidates, weights=weights, k=1)[0]
