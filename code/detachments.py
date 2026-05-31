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
    SUBTERRANEAN_ASSAULT_STRATAGEMS,
    WAR_HORDE_STRATAGEMS,
    SHIELD_HOST_STRATAGEMS,
    OATHBAND_STRATAGEMS,
    GLADIUS_STRATAGEMS,
    COMBINED_ARMS_STRATAGEMS,
    # ST-2 wave 3 — one stratagem per under-performing faction
    BERZERKER_WARBAND_STRATAGEMS,
    DAEMONIC_INCURSION_STRATAGEMS,
    TELEPORT_STRIKE_FORCE_STRATAGEMS,
    FINAL_DAY_STRATAGEMS,
    PACTBOUND_ZEALOTS_STRATAGEMS,
    # DAEMONS-STRATAGEMS-V1 (wave 53) — per-god Daemons detachment sets
    BLOOD_LEGION_STRATAGEMS,
    PLAGUE_LEGION_STRATAGEMS,
    LEGION_OF_EXCESS_STRATAGEMS,
    SCINTILLATING_LEGION_STRATAGEMS,
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
    # LC1-A generalised the gate so any faction-detachment pairing can set
    # the flag. Currently only WAR_HORDE (Orks) sets it. CUSTODES-AURIC-
    # CHAMPIONS (claude/sim-calibration-6): AURIC_CHAMPIONS previously set
    # this flag as a fabrication; removed — the real rule is 'Assemblage of
    # Might' (CHARACTER-only + single designated enemy target per round),
    # which is not faithfully proxied by an army-wide SUSTAINED HITS 1 flag.
    melee_sustained_hits_army_wide: bool = False

    # Necrons Awakened Dynasty Command Protocols rotation (AD-PR, branch
    # claude/sim-calibration-4). The detachment's real rule rotates one of
    # six Command Protocols per battle round (player picks at the start of
    # each Command phase). Three protocols map onto clean simulator hooks
    # and are alternated by round parity to approximate the rotation:
    #   * `necrons_melee_ap_plus_one_army_wide` — Protocol of the Hungry
    #     Void: "NECRONS melee weapons gain the [LETHAL HITS] ability and
    #     improve their Armour Penetration by 1." We wire the AP+1 leg
    #     only (the Lethal Hits leg is dropped to keep the buff bounded;
    #     direction-correct). Fires on EVEN battle rounds (2, 4). Gate:
    #     mode == "melee" AND attacker faction == "Necrons" AND the
    #     detachment carries this flag AND current battle round is even.
    #   * `necrons_ranged_sustained_hits_army_wide` — Protocol of the
    #     Vengeful Stars: "NECRONS ranged weapons gain the [SUSTAINED HITS
    #     1] ability." Fires on ODD battle rounds (1, 3, 5). Gate:
    #     mode != "melee" AND attacker faction == "Necrons" AND the
    #     detachment carries this flag AND current battle round is odd.
    #   * `bonus_to_hit_when_led` (above) — Protocol of the Conquering
    #     Tyrant: always-on representation of the +1-to-hit-when-led leg.
    # Rounds 0/no battle ref treated as inactive so detachment-flag tests
    # without a battle round set see no buff (matches the SHIELD_HOST
    # alternation gate). Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/necrons/#Command-Protocols
    necrons_melee_ap_plus_one_army_wide: bool = False
    necrons_ranged_sustained_hits_army_wide: bool = False

    # NECRONS-CLOSE (claude/sim-calibration-6): Command Protocols third slot —
    # Protocol of the Eternal Conquerors (defensive). Real Wahapedia text:
    # "Until the start of your next Command phase, the first failed armour
    # saving throw made for each NECRONS unit from your army in each phase
    # is automatically passed." Closest clean simulator hook: army-wide +1
    # to the armour save, gated by the save-modifier ±1 cap so it composes
    # with no other defensive +1-save sources stacked. Round-gated to ROUND
    # 3 ONLY — odd-round Vengeful Stars and even-round Hungry Void already
    # cover rounds 1-2-4-5, so Eternal Conquerors adds a single round of
    # additional defensive uplift (over-model bounded to one round). The
    # save-cap clamp (see code/units.py save_buff_sources) means this
    # composes with at most one other +1-save source as a single net +1
    # rather than stacking to +2. Gate: defender faction == "Necrons" AND
    # detachment carries `necrons_army_wide_plus_one_save_command_protocol`
    # AND current battle round == 3. Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/necrons/#Command-Protocols
    necrons_army_wide_plus_one_save_command_protocol: bool = False

    # Adeptus Custodes Shield Host detachment rule (Martial Ka'tah /
    # Martial Mastery). The three real codex bullets are:
    #   * Kaptaris Ka'tah — +1 to invulnerable saving throws vs ranged.
    #   * Rendax Ka'tah   — improve AP of melee weapons by 1.
    #   * Dacatarai Ka'tah — Sustained Hits ranged/melee bonus.
    # The detachment rule picks ONE bullet per round.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    #
    # CUSTODES-KATAH-V1 (claude/sim-calibration-6): `melee_crit_on_5_plus_hits`
    # was a fabricated melee-crit stance with no codex counterpart. It fired
    # on EVEN rounds (2, 4) and inflated melee output spuriously. Removed by
    # setting the flag to False (dataclass default; retained as explicit field
    # for auditability). Only `melee_ap_plus_one` (Rendax Ka'tah, ODD rounds
    # 1/3/5) remains active. Kaptaris and Dacatarai are deferred (tighten
    # direction: Custodes overshooting, not undershooting).
    #
    # Simulator gate (read in Unit.attack):
    #   * melee_ap_plus_one — when True AND mode=="melee" AND
    #     attacker.faction == "Adeptus Custodes" AND battle round is ODD,
    #     the melee AP is improved by 1 (e.g. AP-1 -> AP-2). Cited as
    #     `SHIELD_HOST.melee_ap_plus_one`.
    #   * melee_crit_on_5_plus_hits — retained as a field (default False)
    #     but no longer set True on any detachment. The Unit.attack block
    #     that reads it is a no-op for all current detachments; retained
    #     in case a future faction needs it with a real codex citation.
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
    # that don't appear as datasheet keywords in BSData v10.6.0. AM-DIAG-2
    # narrowed REGIMENT to BATTLELINE-keyword (the three core Cadian /
    # Catachan / Krieg troop squads). AM-DIAG-3 (2026-05-24) narrowed
    # SQUADRON to an explicit name allowlist of the codex SQUADRON
    # datasheets (Leman Russ family, Rogal Dorn family, Hellhound,
    # Armoured / Scout / Commander Sentinels — see
    # `code/units.py::_AM_BORN_SOLDIERS_SQUADRON_NAMES`); the previous
    # "any VEHICLE-keyword AM attacker" proxy over-granted LETHAL HITS
    # on transports (Chimera, Taurox), flyers (Valkyrie, Vendetta),
    # HEAVY artillery (Basilisk, Manticore, Wyvern), super-heavies
    # (Baneblade family), Knights, and VEHICLE CHARACTERS — none of
    # which carry the codex SQUADRON keyword.
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

    # Imperial Knights Valourstrike Lance — Bold Gallantry detachment rule
    # (BSData v10.6.0, Imperium - Imperial Knights - Library.cat.gz verbatim):
    # "Each time an ^^Imperial Knights^^ unit from your army Advances, until
    # the end of the turn, ranged weapons equipped by ^^Imperial Knights^^
    # models from your army have the [ASSAULT] ability."
    # When this flag is True AND the attacker is Imperial Knights AND the
    # attacker Advance in the current round (`attacker.uid in
    # battle._advanced_this_round`), `_do_shoot` skips the Advance-lockout
    # that would otherwise block the unit from shooting, mirroring the
    # [ASSAULT] keyword grant on all IK ranged weapons. Army-wide (any IK
    # unit that Advances benefits, not just the unit that triggered it).
    # Cited as `VALOURSTRIKE_LANCE.bold_gallantry`.
    bold_gallantry: bool = False

    # Imperial Knights Valourstrike Lance — Bondsman abilities.
    # BSData v10.6.0 (Imperium - Imperial Knights - Library.cat.gz) verbatim:
    # "In your Command phase, one or more models from your army with a Bondsman
    # ability can use that ability. For each one that does, select one friendly
    # ^^Armiger^^ model within 12" of that model … Until the start of your next
    # Command phase, that ^^Armiger^^ model is affected by that Bondsman ability."
    # When True the simulator's command-phase hook
    # (`Battle._apply_bondsman_abilities`) iterates alive TITANIC+CHARACTER IK
    # models, picks the closest alive non-TITANIC IK unit (the Armiger) within
    # 12", and applies the matching transient buff for that knight sub-type.
    # The six canonical Bondsman buffs (Paladin = Lethal Hits + Lance; Warden =
    # Sustained Hits 1 + Ignores Cover; Crusader = +1 to hit ranged; Gallant =
    # reroll charge + reroll melee hits; Errant = reroll advance + Assault;
    # Preceptor = reroll wounds vs quarry) are collapsed to one:
    # Paladin's Duty → transient_lethal_hits + transient_lance_this_turn.
    # The others have no clean transient hook (charge-reroll, melee-hit-
    # reroll, advance-reroll, quarry-gate wound-reroll) and are deferred.
    # APPROXIMATION: (1) Paladin's Duty is applied uniformly to every
    # TITANIC+CHARACTER knight as the strongest representable buff; (2) the
    # codex "within 12\"" range gate is dropped because SwegHammer's grid-free
    # deployment spreads Armigers further apart than real tables allow — in
    # real play Armigers are always within 12" of their bonded lord. Follows
    # the same alive-in-army pattern as Beacons of Rage.
    # Cited as `VALOURSTRIKE_LANCE.bondsman_enabled`.
    bondsman_enabled: bool = False

    # Chaos Knights Iconoclast Fiefdom — Dreaded Masters / Dread Tyrants Aura.
    # BSData v10.6.0 (Chaos - Chaos Knights Library.cat.gz) verbatim (from
    # the Iconoclast Fiefdom sub-detachment):
    # "Dread Tyrants (Aura): While a friendly DAMNED unit is within 9\" of this
    # unit, each time a model in that unit makes an attack, re-roll a Hit roll
    # of 1 and re-roll a Wound roll of 1."
    # The DAMNED keyword is carried by War Dog-class units when they belong to
    # the Iconoclast Fiefdom detachment. The BSData mapper does not yet capture
    # DAMNED as a unit keyword (it is detachment-conditional, applied only to
    # War Dog units in an Iconoclast Fiefdom army). SwegHammer gates the aura
    # by name-prefix ("War Dog") as an APPROXIMATION — strictly correct for
    # the real rule since DAMNED is only granted to War Dog units in this
    # detachment, and non-War Dog CK units already carry CHARACTER/TITANIC and
    # are the AURA SOURCE not the receiver. The aura source is any TITANIC CK
    # unit. When this flag is True AND the attacker is "Chaos Knights" faction
    # AND the attacker's name starts with "War Dog" AND at least one alive
    # friendly TITANIC CK unit is within 9", then reroll_hit_ones and
    # reroll_wound_ones are both set True for that attack. Gate lives in
    # `code/units.py:Unit.attack`. Cited as
    # `ICONOCLAST_FIEFDOM.dread_tyrants_aura`.
    dread_tyrants_aura: bool = False

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
        "transient_undying_legions_pulse for the extra reanimation pulse). "
        "AD-PR (claude/sim-calibration-4): the detachment-rule rotation "
        "of Command Protocols is now modelled by alternating two new "
        "always-on flags by battle-round parity — Hungry Void (melee "
        "AP+1, `necrons_melee_ap_plus_one_army_wide`) on EVEN rounds and "
        "Vengeful Stars (ranged SUSTAINED HITS 1, "
        "`necrons_ranged_sustained_hits_army_wide`) on ODD rounds. The "
        "always-on Conquering Tyrant +1-to-hit-when-led leg "
        "(`bonus_to_hit_when_led`) is retained — strictly speaking the "
        "real codex picks only ONE protocol per round, so this is an "
        "APPROXIMATION (slight over-model) but the led-only gate keeps "
        "the over-coverage bounded to character-led squads. "
        "NECRONS-CLOSE (claude/sim-calibration-6): wires the fourth "
        "Command Protocol — Protocol of the Eternal Conquerors (defensive, "
        "first failed armour save auto-passed per phase) — as army-wide "
        "+1 to the armour save (`necrons_army_wide_plus_one_save_command_protocol`) "
        "gated to ROUND 3 ONLY. Single-round defensive uplift; clamped to "
        "+1 by the existing save-modifier cap so it composes safely with "
        "any other +1-save source as a single net +1 rather than stacking."
    ),
    reanimate_per_round=1,
    bonus_to_hit_when_led=True,
    necrons_melee_ap_plus_one_army_wide=True,
    necrons_ranged_sustained_hits_army_wide=True,
    necrons_army_wide_plus_one_save_command_protocol=True,
    stratagems=AWAKENED_DYNASTY_STRATAGEMS,
    preferred_composition="balanced",
)

INVASION_FLEET = Detachment(
    name="Invasion Fleet",
    faction="Tyranids",
    notes=(
        "TYRANIDS-DIAG-8 (2026-05-26): the previous proxy `enemy_ld_penalty=1` was "
        "a fabrication — it mis-attributed Shadow in the Warp (the Tyranids ARMY RULE, "
        "modelled separately as `simulator.shadow_in_the_warp`) to the Invasion Fleet "
        "DETACHMENT rule. The real Invasion Fleet detachment rule is 'Hyper-adaptations' "
        "(Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet): "
        "at the start of battle round 1 the Tyranids player selects ONE of: "
        "(A) Swarming Instincts — friendly Tyranids attacks targeting INFANTRY or SWARM "
        "units gain [SUSTAINED HITS 1]; "
        "(B) Hyper-aggression — friendly Tyranids attacks targeting MONSTER or VEHICLE "
        "units gain [LETHAL HITS]; "
        "(C) Hive Predators — friendly Tyranids Critical Hits against CHARACTER units "
        "gain [PRECISION]. "
        "None of these three variants map cleanly to an existing per-detachment transient "
        "flag: SUSTAINED HITS 1 is keyword-gated-on-TARGET (SwegHammer has no per-attack "
        "target-keyword gate outside of ANTI_X); LETHAL HITS vs MONSTER/VEHICLE is "
        "similarly target-gated; PRECISION is a wound-allocation override with no "
        "current simulator hook. All three are NO-OP for now, catalogued here for a "
        "follow-up wiring pass. Shadow in the Warp continues to be modelled army-wide "
        "via `simulator.shadow_in_the_warp`."
    ),
    # FABRICATION REMOVED (TYRANIDS-DIAG-8): enemy_ld_penalty=1 was a proxy for Shadow
    # in the Warp (the army rule), not the real Invasion Fleet detachment rule
    # (Hyper-adaptations). Both were firing simultaneously when Invasion Fleet was
    # selected, double-counting the Shadow in the Warp effect. Real Hyper-adaptations
    # variants are no-op pending target-keyword-gated flag infrastructure.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet
    preferred_composition="balanced",
)

SUBTERRANEAN_ASSAULT = Detachment(
    name="Subterranean Assault",
    faction="Tyranids",
    notes=(
        "iter16 fix — May-2026 real-meta Tyranids default detachment, after "
        "Ron Eilyahoo won GW Open Maastricht 2026 with a Subterranean Assault "
        "list and Frontline / Stat-Check / Goonhammer all promoted it to "
        "tier-1 alongside Invasion Fleet and Vanguard Onslaught. "
        "Detachment rule (Goonhammer: "
        "https://www.goonhammer.com/detachment-focus-subterranean-assault/): "
        "'Tyranids units gain reroll Hit rolls of 1 in both shooting and "
        "combat. Trygons and Mawlocs gain the Burrower keyword, letting them "
        "place Tunnel Markers on arrival from reserves which subsequent "
        "friendly Tyranids units can deploy from.' Modelled as army-wide "
        "`reroll_hit_ones=True` — fires for every Tyranid attacker, ranged "
        "or melee. The Burrower / Tunnel Marker mechanic is NOT modelled "
        "(SwegHammer has no in-battle reserve teleport hook); it lives in "
        "the four catalogued-but-no-op stratagems (Tunnel Network, "
        "Replenishing Swarms, Swarming Assault, Enfilading Emergence) as a "
        "placeholder for follow-up wiring. Replaces the previous Tyranids "
        "default Invasion Fleet (-1 enemy Ld approximation of Shadow in the "
        "Warp, which is already handled in simulator.shadow_in_the_warp); "
        "Invasion Fleet stays in the registry as a variant pick."
    ),
    # APPROXIMATION: army-wide reroll Hit rolls of 1 fires both ranged and melee.
    # The Burrower keyword + Tunnel Marker reserve-teleport half is NOT modelled.
    # Source: https://www.goonhammer.com/detachment-focus-subterranean-assault/
    reroll_hit_ones=True,
    stratagems=SUBTERRANEAN_ASSAULT_STRATAGEMS,
    # iter16: preferred_composition="monster" tilts the detachment picker
    # toward Subterranean Assault. Empirically the Subterranean Assault
    # archetype produces monster-dominant armies in ~70% of seeds (Hive
    # Tyrant 195pt + Trygon 140pt + Tervigon 160pt + Carnifex 461pt seed +
    # random_fill MONSTER picks like Exocrine / Tyrannofex / Norn dominate
    # the cost share). Invasion Fleet stays at "balanced" so it surfaces
    # for the residual ~30% infantry-leaning Tyranid builds (chaff-swarm
    # MSU). Real-meta justification: Subterranean Assault is the May-2026
    # tournament default (Maastricht 2026 GT win, Goonhammer focus)
    # specifically *because* it pairs with Trygons / Mawlocs / Carnifexes
    # — it IS the monster-anchor detachment.
    preferred_composition="monster",
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
        "SC5-11 (2026-05-21): the codex Bold Gallantry rule grants the "
        "[ASSAULT] keyword to Imperial Knights ranged weapons in a turn "
        "where the unit Advanced — it is NOT a +1-to-wound rule. The "
        "previous proxy `plus_one_to_wound=True` (army-wide, always-on) "
        "was a fabrication that bore no resemblance to the cited rule "
        "text and biased Imperial Knights sim WR upward by ~5-15pt. "
        "Removed. The detachment is still registered and its vehicle "
        "composition preference is retained — list-build shape still "
        "applies. A faithful Bold Gallantry implementation needs an "
        "Advance-gated ASSAULT grant on the unit's ranged weapons; "
        "follow-up wiring lands separately."
    ),
    preferred_composition="vehicle",
)

VALOURSTRIKE_LANCE = Detachment(
    name="Valourstrike Lance",
    faction="Imperial Knights",
    notes=(
        "IK-KNIGHTS-V1 (2026-05-31): real codex detachment for Imperial "
        "Knights. The Valourstrike Lance detachment rule is Bold Gallantry "
        "(BSData v10.6.0, Imperium - Imperial Knights - Library.cat.gz verbatim): "
        "'Each time an IMPERIAL KNIGHTS unit from your army Advances, until "
        "the end of the turn, ranged weapons equipped by IMPERIAL KNIGHTS "
        "models from your army have the [ASSAULT] ability.' Implemented via "
        "`bold_gallantry=True`: `_do_shoot` skips the Advance-lockout for any "
        "IK attacker in a round where at least one IK unit in the army "
        "Advanced (`uid in _advanced_this_round`). This is an APPROXIMATION — "
        "the real rule triggers on ANY IK unit Advancing and grants [ASSAULT] "
        "army-wide; SwegHammer gates it on the individual attacker's own uid "
        "being in _advanced_this_round (per-unit rather than army-wide), which "
        "is strictly correct because every unit that Advanced is in the set. "
        "PLUS Bondsman abilities (`bondsman_enabled=True`): in each Command "
        "phase, each alive TITANIC+CHARACTER IK unit (Questoris/Cerastus "
        "frame) selects one non-TITANIC IK unit (Armiger) within 12\" and "
        "applies its Bondsman buff. SwegHammer uses the strongest cleanly "
        "representable buff (Paladin's Duty: Lethal Hits on all weapons + "
        "Lance on melee weapons) as a uniform proxy for all Questoris knights. "
        "Wahapedia URL is unreachable from agent worktrees (DNS fails — see "
        "project memory project-wahapedia-dns.md); rule text from BSData cache "
        "as the canonical fallback per CLAUDE.md rule 6."
    ),
    bold_gallantry=True,
    bondsman_enabled=True,
    preferred_composition="vehicle",
)

ICONOCLAST_FIEFDOM = Detachment(
    name="Iconoclast Fiefdom",
    faction="Chaos Knights",
    notes=(
        "IK-KNIGHTS-V1 (2026-05-31): real codex detachment for Chaos Knights "
        "(sub-detachment: Iconoclast Fiefdom, selected via Traitoris Lance "
        "main detachment rule). The Iconoclast Fiefdom detachment rule is "
        "Dreaded Masters (BSData v10.6.0, Chaos - Chaos Knights Library.cat.gz "
        "verbatim): 'TITANIC CHAOS KNIGHTS units from your army have the "
        "following abilities: Dread Tyrants (Aura): While a friendly DAMNED "
        "unit is within 9\" of this unit, each time a model in that unit makes "
        "an attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1.' "
        "The DAMNED keyword is held by War Dog units in an Iconoclast Fiefdom "
        "army (the BSData mapper does not yet capture it as a static keyword). "
        "Implemented via `dread_tyrants_aura=True`: `Unit.attack` gates on "
        "attacker faction=='Chaos Knights' AND attacker name startswith 'War Dog' "
        "AND at least one alive friendly TITANIC CK unit is within 9\". "
        "APPROXIMATION: uses 'War Dog' name-prefix as a proxy for the DAMNED "
        "keyword, strictly correct for the real rule since DAMNED is only "
        "granted to War Dog units in this detachment. "
        "Wahapedia URL is unreachable from agent worktrees; rule text from "
        "BSData cache per CLAUDE.md rule 6."
    ),
    dread_tyrants_aura=True,
    preferred_composition="vehicle",
)

HALLOWED_MARTYRS = Detachment(
    name="Hallowed Martyrs",
    faction="Adepta Sororitas",
    notes=(
        "SC5-4 (2026-05-21): real 'Blood of Martyrs' rule grants +1 Hit only "
        "when the attacking unit is Below Starting Strength and +1 Wound only "
        "when Below Half-strength — a damage-gated trigger the simulator does "
        "not track per-unit. The previous proxy `plus_one_to_wound=True` "
        "(army-wide, always-on) was a strict over-buff driving Adepta "
        "Sororitas to +18.9pt overperformance in the SC5-3 baseline, so it "
        "was removed. The detachment is still registered and its infantry "
        "composition preference is retained — list-build shape still applies."
    ),
    preferred_composition="infantry",
)

BRINGERS_OF_FLAME = Detachment(
    name="Bringers of Flame",
    faction="Adepta Sororitas",
    notes=(
        "DET-VARIETY-1 (2026-05-22): real codex Bringers of Flame detachment "
        "(Adepta Sororitas) registered as a variant pick alongside Hallowed "
        "Martyrs so the FACTION_DETACHMENTS picker has more than one option "
        "to roll for Sororitas. The codex detachment rule 'Fervent Purgation' "
        "(BSData verbatim, v10.6.0): \"Ranged weapons equipped by ADEPTA "
        "SORORITAS models from your army have the [ASSAULT] ability, and "
        "each time an attack made with such a weapon targets a unit within "
        "6\\\", add 1 to the Strength characteristic of that attack.\" The "
        "rule has TWO legs: an army-wide [ASSAULT] grant on ranged weapons "
        "(no existing Detachment flag — the closest equivalent is "
        "MONTKA.army_wide_assault_rounds_1_3 which is round-gated to 1-3 "
        "and faction-gated to T'au, so re-using it would be fabrication), "
        "and a range-gated S+1 within 6\" buff (no existing flag — would "
        "need bespoke wiring with a per-target range check in Unit.attack). "
        "Neither leg maps to an existing transient flag without fabrication; "
        "per the project rule 'DO NOT FABRICATE proxy flags' the detachment "
        "ships NO-FLAG + composition-preference only. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/#Bringers-of-Flame. "
        "The detachment dilutes the average Sororitas WR via random "
        "detachment-roll (was always-Hallowed-Martyrs, now 50/50 random)."
    ),
    preferred_composition="infantry",
)

AURIC_CHAMPIONS = Detachment(
    name="Auric Champions",
    faction="Adeptus Custodes",
    notes=(
        "CUSTODES-AURIC-CHAMPIONS (claude/sim-calibration-6): prior "
        "implementation carried `melee_sustained_hits_army_wide=True`, "
        "citing 'Trail of Glory' — a fabrication. The real Auric Champions "
        "detachment rule is 'Assemblage of Might' (Wahapedia verbatim): "
        "\"At the start of your Command phase, select one unit from your "
        "opponent's army. Until the start of your next Command phase, each "
        "time a model in an ADEPTUS CUSTODES CHARACTER unit from your army "
        "makes an attack that targets that enemy unit, add 1 to the Wound "
        "roll.\" The real rule has two axes the Detachment schema cannot "
        "faithfully proxy: (1) it requires designating a single enemy unit "
        "at the start of the Command phase — the sim has no 'pick one target "
        "for a round-long debuff' mechanic; (2) the buff applies only to "
        "ADEPTUS CUSTODES CHARACTER unit models, not all Custodes units. "
        "The closest available flag (`plus_one_to_wound`) would apply to "
        "all Custodes units against all enemies — wrong scope and wrong "
        "target. A no-op is more rules-correct than a fabrication. "
        "Custodes OVER-shoots the tournament target (~+5 gated), so "
        "removing the fabricated buff is MAE-positive. "
        "Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Auric-Champions."
    ),
    # melee_sustained_hits_army_wide intentionally NOT set — see notes above.
    # The real 'Assemblage of Might' cannot be proxied by any existing
    # Detachment flag without fabrication (CHARACTER-only + single designated
    # target). No-op ships until a bespoke flag is added.
    stratagems=SHIELD_HOST_STRATAGEMS,  # share stratagems for now —
    # real Auric Champions has its own 6-stratagem pool that we'd need
    # to wire individually. Per-stratagem differences are smaller and follow-up.
    preferred_composition="infantry",
)

SHIELD_HOST = Detachment(
    name="Shield Host",
    faction="Adeptus Custodes",
    notes=(
        "Martial Ka'tah / Martial Mastery (Wahapedia verbatim): \"At the "
        "start of the battle round, you can select one of the bullet "
        "points below. If you do, until the start of the next battle "
        "round, that bullet point's effects apply.\" The three real codex "
        "bullets are: Kaptaris Ka'tah (+1 to invulnerable saving throws "
        "against ranged attacks, defensive); Rendax Ka'tah (improve the "
        "Armour Penetration of melee weapons by 1, offensive melee); "
        "Dacatarai Ka'tah (melee weapons with the Sustained Hits ability "
        "have that ability improved by 1, offensive melee/ranged). "
        "Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host. "
        "CUSTODES-KATAH-V1 fix (claude/sim-calibration-6): the prior "
        "implementation wired a fabricated 'Crit-on-5+ melee' bullet "
        "(`melee_crit_on_5_plus_hits=True`) that has no codex counterpart. "
        "That bullet fired on EVEN rounds (2, 4) and inflated Custodes "
        "melee output by adding a spurious Critical Hit mechanic not "
        "present in any of the three real stances. Root cause: when "
        "the alternating-round model was introduced in C1 "
        "(claude/sim-calibration-4), a fabricated second bullet was "
        "introduced rather than mapping to the real codex stances. "
        "Fix: `melee_crit_on_5_plus_hits` set to False on SHIELD_HOST; "
        "only the Rendax AP+1 bullet (`melee_ap_plus_one`, ODD rounds 1/3/5) "
        "remains active. Kaptaris (+1 invuln ranged) and Dacatarai "
        "(Sustained Hits ranged) are not implemented as the Custodes "
        "overshooting direction requires tightening, not expansion. "
        "Six real detachment stratagems wired (iter-8 fix): "
        "Arcane Genetic Alchemy, Unwavering Sentinels, Multipotentiality, "
        "Vigilance Eternal, Archaeotech Munitions, Avenge the Fallen."
    ),
    # Real rule: Martial Ka'tah / Martial Mastery — player picks ONE of three
    # bullets per battle round (Kaptaris defensive, Rendax melee AP+1,
    # Dacatarai Sustained Hits). Only the Rendax AP+1 bullet is wired here
    # because Custodes is overshooting and the direction is tighten.
    # CUSTODES-KATAH-V1: melee_crit_on_5_plus_hits was a fabricated stance
    # with no codex counterpart — removed (set False, which is the dataclass
    # default; explicit here for auditability).
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    melee_crit_on_5_plus_hits=False,
    melee_ap_plus_one=True,
    stratagems=SHIELD_HOST_STRATAGEMS,
    preferred_composition="infantry",
)

SKITARII_HUNTER_COHORT = Detachment(
    name="Skitarii Hunter Cohort",
    faction="Adeptus Mechanicus",
    notes=(
        "SC5-4 (2026-05-21): the codex 'Stealth Optimisation' detachment rule "
        "is a purely defensive grant (Stealth + cover for Sicarians at >12\") — "
        "no offensive reroll exists. The previous proxy `reroll_hit_ones=True` "
        "was a stand-in for the launch-index Conqueror Doctrina Imperatives "
        "(an army-rule rotation, not a detachment rule) and was driving "
        "Adeptus Mechanicus to +20.7pt overperformance in the SC5-3 baseline. "
        "Removed. The detachment is still registered and its infantry "
        "composition preference is retained — list-build shape still applies."
    ),
    preferred_composition="infantry",
)

COHORT_CYBERNETICA = Detachment(
    name="Cohort Cybernetica",
    faction="Adeptus Mechanicus",
    notes=(
        "DET-VARIETY-1 (2026-05-22): real codex Cohort Cybernetica detachment "
        "(Adeptus Mechanicus) registered as a variant pick alongside Skitarii "
        "Hunter Cohort so the FACTION_DETACHMENTS picker has more than one "
        "option to roll for Adeptus Mechanicus. The codex detachment rule "
        "'Cyber-Psalm Programming' (BSData verbatim, v10.6.0): \"Add 2\\\" to "
        "the Move characteristic of models in LEGIO CYBERNETICA units from "
        "your army. In addition, unless that unit is Battle-shocked, add 1 "
        "to the Objective Control characteristic of models in that unit.\" "
        "Both legs are keyword-gated to LEGIO CYBERNETICA (Kastelan Robots, "
        "Cybernetica Datasmith) — a narrow slice of the AdMech roster. "
        "Neither leg maps to an existing Detachment flag without fabrication: "
        "the +2\" Move would need a unit-keyword-gated Move buff (no current "
        "schema slot — `aspect_warrior_or_bike_plus_one_move` is faction- "
        "and keyword-gated to Aeldari Aspect Warriors / bikes, re-using it "
        "for AdMech LEGIO CYBERNETICA would be fabrication), and the +1 OC "
        "leg has no schema entry at all (OC is not a current Detachment-flag "
        "axis). Per the project rule 'DO NOT FABRICATE proxy flags' the "
        "detachment ships NO-FLAG + composition-preference only. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/#Cohort-Cybernetica. "
        "The detachment dilutes the average AdMech WR via random "
        "detachment-roll (was always-Skitarii-Hunter-Cohort)."
    ),
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
        "v10.6.0; AM-DIAG-2 narrowed REGIMENT to BATTLELINE-keyword (the "
        "three core Cadian / Catachan / Krieg troop squads); AM-DIAG-3 "
        "narrowed SQUADRON to an explicit name allowlist of the codex "
        "SQUADRON datasheets (Leman Russ family, Rogal Dorn family, "
        "Hellhound, Armoured / Scout / Commander Sentinels — see "
        "`code/units.py::_AM_BORN_SOLDIERS_SQUADRON_NAMES`) instead of "
        "any VEHICLE-keyword AM unit (which over-fired LETHAL HITS on "
        "transports, flyers, HEAVY artillery, super-heavies, Knights, "
        "and VEHICLE CHARACTERS). "
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
        "Fury of Titan (Wahapedia): 'Each time a unit from your army is "
        "set up using the Deep Strike ability, until the end of the turn, "
        "each time a model in that unit makes an attack, re-roll a Hit "
        "roll of 1 and re-roll a Wound roll of 1.' Approximation: the "
        "deep-strike-turn gate is dropped (modelled as army-wide always-on "
        "re-roll hit 1s + wound 1s). Prior to SC5-6 only the wound-1 half "
        "was wired; the hit-1 half is restored here to match the quoted "
        "rule text. Real rule also includes bespoke psychic / teleport "
        "redeploy mechanics that the simulator does not yet model. "
        "Source: https://wahapedia.ru/wh40k10ed/factions/grey-knights/#Fury-of-Titan"
    ),
    reroll_hit_ones=True,
    reroll_wound_ones=True,
    stratagems=TELEPORT_STRIKE_FORCE_STRATAGEMS,
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
        "Rain of Cruelty (real 10e rule). Each time a DRUKHARI unit "
        "disembarks from a TRANSPORT, until the end of the turn its "
        "ranged weapons gain [IGNORES COVER] and its melee weapons "
        "gain [LANCE]. DRK-SKYSPLINTER-DISEMBARK (wave 45, 2026-05-28): "
        "the per-weapon LANCE wound-roll bonus and per-target "
        "ignores-cover modifier are now wired through transient "
        "per-unit flags (`transient_lance_this_turn`, "
        "`transient_ignores_cover_this_turn`) set in "
        "`simulator._disembark` when the disembarking unit is "
        "Drukhari AND the army's detachment is Skysplinter Assault, "
        "and cleared at the next round-start by the standard "
        "transient-flag reset (matching the 'until the end of the "
        "turn' wording). LANCE composes via OR with `profile.lance` "
        "at the existing lance eligibility gate in Unit.attack "
        "(still gated on `is_charging` because LANCE itself only "
        "fires on the charge turn). IGNORES COVER composes via OR "
        "with `profile.ignores_cover` at the ranged ignore_cover "
        "gate (melee already always ignores cover). EMBARK-V1 "
        "(2026-05-28) wired the embark / disembark cycle (see "
        "simulator._embark / _disembark / "
        "_destroyed_transport_disembark and the matching "
        "embarked-passenger gates in _do_move / _do_shoot / "
        "_do_charge / _do_fight). The previous proxy granted "
        "army-wide reroll_wound_ones=True; that was a strict "
        "over-buff (always-on, every wound roll, every unit, no "
        "disembark gate) and drove the +39.5pt Drukhari "
        "overperformance in the May 2026 calibration. Removed "
        "(SC5-1, 2026-05-20). "
        "Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/#Skysplinter-Assault"
    ),
    preferred_composition="vehicle",
)

KABALITE_CARTEL = Detachment(
    name="Kabalite Cartel",
    faction="Drukhari",
    notes=(
        "DET-VARIETY-1 (2026-05-22): real codex Kabalite Cartel detachment "
        "(Drukhari) registered as a variant pick alongside Skysplinter "
        "Assault so the FACTION_DETACHMENTS picker has more than one option "
        "to roll for Drukhari. The codex detachment rule 'Murderous Agenda' "
        "(Wahapedia verbatim): \"At the start of the first battle round, "
        "select one of the following Contracts (you cannot select the same "
        "Contract more than once per battle): Trophy Hunters (target unit "
        "must be a CHARACTER); Sow Fear and Terror (target unit must be "
        "INFANTRY or MOUNTED, excluding CHARACTERS); Show of Strength "
        "(target unit must be a MONSTER or VEHICLE). KABAL and BLADES FOR "
        "HIRE units from your army have the ability stated in that Contract. "
        "If the target unit is destroyed before the end of the battle, you "
        "gain 3 Pain tokens.\" The bespoke Contract / Pain-token / Pain-token-"
        "spend economy has no equivalent flag in the Detachment schema — "
        "Pain tokens are a per-battle-state resource (not a static buff), "
        "Contract targeting requires a per-unit-keyword target picker (no "
        "schema slot), and the per-Contract effects (Trophy Hunters grants "
        "PRECISION; Sow Fear and Terror grants [LETHAL HITS]; Show of "
        "Strength grants +1 AP) would each need separate bespoke wiring. "
        "Per the project rule 'DO NOT FABRICATE proxy flags' the detachment "
        "ships NO-FLAG + composition-preference only. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/drukhari/#Kabalite-Cartel. "
        "Kabal-leaning composition preference set to 'infantry' (Kabalite "
        "Warriors / Trueborn / Incubi / Mandrakes are infantry; Raiders / "
        "Ravagers / Venoms are vehicles — but the detachment's identity "
        "leans on Kabal foot-troop output, contrasting with Skysplinter's "
        "vehicle-disembark identity)."
    ),
    preferred_composition="infantry",
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
        "SC5-11 (2026-05-21): the real Marks of Chaos / Dark Pacts rule "
        "grants Lethal Hits OR Sustained Hits on a unit that successfully "
        "declares a Dark Pact (a Leadership-test gamble), gated by mark "
        "keyword. It is NOT a reroll-wound-1s rule. The previous proxy "
        "`reroll_wound_ones=True` (army-wide, always-on) was a fabrication "
        "biasing Chaos Space Marines sim WR upward. Removed. The "
        "detachment is still registered and its composition preference is "
        "retained — list-build shape still applies. A faithful Dark Pacts "
        "implementation needs a per-unit gamble + Leadership test + "
        "Lethal/Sustained Hits transient flag; follow-up wiring lands "
        "separately."
    ),
    stratagems=PACTBOUND_ZEALOTS_STRATAGEMS,
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
    # TSON-DIAG (claude/sim-calibration-6): zeroed from 2 to 0.
    # Kindred Sorcery's real rule is a once-per-battle-each selection of three
    # Psychic-weapon-keyword buffs (Imbued Manifestation / Psychic Maelstrom /
    # Wrath of the Immaterium); NONE of those grant an unconditional per-round
    # mortal-wound payload to the highest-threat enemy. The Cabal of Sorcerers
    # Rituals pass (`_run_cabal_rituals`) is the actual implementation surface
    # for TSON's psychic teeth — real 2D6 Psychic test, real Doombolt D3 /
    # D3+3 mortals, real cadence (Magnus gets 2 attempts + 2 to test, Ahriman
    # gets +1 to test). The previous `psychic_mortal_wounds_per_round=2`
    # baseline stacked an unconditional 2-MW-per-round payload ON TOP of the
    # stochastic Ritual pass, double-counting Doombolt's already-modelled
    # damage and contributing to TSON's +22pt over-perf at the Warp Friends
    # rolling target. Removing the fabricated baseline lets the rule-accurate
    # Cabal pass be the only source of TSON psychic MW output.
    psychic_mortal_wounds_per_round=0,
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
    # TSON-DIAG (claude/sim-calibration-6): zeroed from 2 to 0, matching the
    # GRAND_COVEN fix in the same commit. The notes block above this
    # Detachment already states "psychic_mortal_wounds_per_round=0 baseline
    # (NOT 2 — that lives on Grand Coven only)" — the code previously
    # contradicted its own comment and set the value to 2 anyway. The real
    # All Is Dust detachment rule (verbatim Wahapedia) grants +1 to armour
    # saves on D1 attacks against RUBRICAE models; it does NOT grant a
    # per-round MW payload to the highest-threat enemy. The Cabal of
    # Sorcerers Rituals pass (`_run_cabal_rituals`) is the rule-accurate
    # source of TSON psychic MW output; the previous baseline double-counted
    # Doombolt and contributed to TSON's +22pt over-perf at the Warp Friends
    # rolling target.
    psychic_mortal_wounds_per_round=0,
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
        "SC5-11 (2026-05-21): the real Relentless Rage rule grants +1 "
        "Attack and +2 Strength to melee weapons on a unit that made a "
        "Charge move — it is NOT a +1-to-hit rule. The previous proxy "
        "`plus_one_to_hit=True` (army-wide, always-on) was a fabrication "
        "biasing World Eaters sim WR upward. Removed. The detachment is "
        "still registered and its infantry composition preference is "
        "retained — list-build shape still applies. A faithful Relentless "
        "Rage implementation needs a charge-turn transient +1A / +2S "
        "buff and Blood Tithe spend tracking; follow-up wiring lands "
        "separately."
    ),
    stratagems=BERZERKER_WARBAND_STRATAGEMS,
    preferred_composition="infantry",
)

DAEMONIC_INCURSION = Detachment(
    name="Daemonic Incursion",
    faction="Chaos Daemons",
    notes=(
        "SC5-11 (2026-05-21): the canonical Warp Rifts rule reduces the "
        "Deep Strike distance for Legiones Daemonica units set up wholly "
        "within Shadow of Chaos or near greater daemons — it has no "
        "offensive reroll or +1-to-hit component. The previous proxy "
        "`plus_one_to_hit=True` (army-wide, always-on) was a fabrication "
        "biasing Chaos Daemons sim WR upward. Removed. The detachment is "
        "still registered and its composition preference is retained — "
        "list-build shape still applies. A faithful Warp Rifts "
        "implementation needs reserve-deployment distance tracking that "
        "the simulator does not yet model; follow-up wiring lands "
        "separately."
    ),
    stratagems=DAEMONIC_INCURSION_STRATAGEMS,
    preferred_composition="balanced",
)

# DAEMONS-DIAG-4 (2026-05-23, claude/sim-calibration-6): the four god-aligned
# sub-detachments published in the 10e Chaos Daemons codex (Blood Legion,
# Legion of Excess, Plague Legion, Scintillating Legion) registered alongside
# Daemonic Incursion so the FACTION_DETACHMENTS picker has more than one
# option to roll for Chaos Daemons. Each is composition-only + no-flag
# because none of the four real detachment rules reduces to an existing
# Detachment schema field without fabrication:
#   * Blood Legion's Murdercall is a per-trigger Surge move (no movement
#     hook of that shape in the simulator).
#   * Legion of Excess's Beguiling Aura is a fall-back-then-charge
#     eligibility flag (the simulator does not track Fell Back state).
#   * Plague Legion's Melancholic Miasma expands the Shadow of Chaos to 9"
#     around each Nurgle unit AND forces a per-Command-phase Battle-shock
#     test on a selected enemy (overlaps with simulator.shadow_of_chaos
#     which is already wired army-wide; the per-CP-phase forced test is a
#     Command Phase hook the simulator does not model).
#   * Scintillating Legion's Fates in Flux is a Flux token economy (3
#     re-roll tokens per battle, spendable on Advance/Hit/Wound/Damage/
#     save/Hazardous rolls) — there is no transient token-spend layer in
#     the schema.
# Wahapedia source: https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/
# Same DET-VARIETY-1 pattern as Bringers of Flame / Cohort Cybernetica /
# Kabalite Cartel above — ship the shell with composition preference so
# the random detachment picker no longer always rolls Daemonic Incursion
# and the eval matrix gains variety. No citation block needed because no
# rule-bearing flag is set (audit_rules.py only requires citations on
# detachments that toggle a RULE_BEARING_FIELDS field). When a proper
# movement / fall-back-and-charge / token-spend layer lands in the
# simulator, each detachment's wired flag should be added back here with
# a fresh citation in data/rule_citations.d/detachments.json.

BLOOD_LEGION = Detachment(
    name="Blood Legion",
    faction="Chaos Daemons",
    notes=(
        "DAEMONS-DIAG-4 (2026-05-23): god-aligned variant detachment "
        "(Khorne). Real codex detachment rule 'Murdercall' (Wahapedia "
        "verbatim): \"Each time an enemy unit (excluding AIRCRAFT) ends a "
        "Normal or Advance move within 6\\\" of one or more LEGIONES "
        "DAEMONICA KHORNE units from your army, one of those LEGIONES "
        "DAEMONICA KHORNE units can make a Surge move towards that enemy "
        "unit.\" The Surge move is a transient out-of-phase movement that "
        "the simulator's positional model does not represent (no movement "
        "phase ordering, no per-trigger reactive moves); the rule does "
        "NOT reduce to any existing Detachment flag without fabrication. "
        "Per CLAUDE.md §10 ship NO-FLAG + composition-only. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/. The "
        "infantry composition tilt biases the picker toward Khorne "
        "infantry archetypes (Bloodletters / Bloodcrushers / Flesh "
        "Hounds), which already collect the Bloodthirster / Skarbrand "
        "auras wired in DAEMONS-DIAG-3. "
        "DAEMONS-STRATAGEMS-V1 (wave 53): stratagems upgraded from the "
        "shared DAEMONIC_INCURSION_STRATAGEMS to the dedicated "
        "BLOOD_LEGION_STRATAGEMS set (Blood Begets Skulls + Wrath "
        "Undeniable) drawn from 40k.app."
    ),
    stratagems=BLOOD_LEGION_STRATAGEMS,
    preferred_composition="infantry",
)

LEGION_OF_EXCESS = Detachment(
    name="Legion of Excess",
    faction="Chaos Daemons",
    notes=(
        "DAEMONS-DIAG-4 (2026-05-23): god-aligned variant detachment "
        "(Slaanesh). Real codex detachment rule 'Beguiling Aura' "
        "(Wahapedia verbatim): \"LEGIONES DAEMONICA SLAANESH units from "
        "your army are eligible to declare a charge in a turn in which "
        "they Fell Back.\" The simulator does not track Fall-Back state "
        "(units cannot disengage and re-engage in the same battle round "
        "in the current movement model), so the rule has no place to "
        "fire and does NOT reduce to any existing Detachment flag without "
        "fabrication. Per CLAUDE.md §10 ship NO-FLAG + composition-only. "
        "Wahapedia: https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/. "
        "The infantry composition tilt biases the picker toward Slaanesh "
        "infantry archetypes (Daemonettes / Fiends / Seekers). "
        "DAEMONS-STRATAGEMS-V1 (wave 53): stratagems upgraded from the "
        "shared DAEMONIC_INCURSION_STRATAGEMS to the dedicated "
        "LEGION_OF_EXCESS_STRATAGEMS set (Archagonists) drawn from 40k.app."
    ),
    stratagems=LEGION_OF_EXCESS_STRATAGEMS,
    preferred_composition="infantry",
)

PLAGUE_LEGION = Detachment(
    name="Plague Legion",
    faction="Chaos Daemons",
    notes=(
        "DAEMONS-DIAG-4 (2026-05-23): god-aligned variant detachment "
        "(Nurgle). Real codex detachment rule 'Melancholic Miasma' "
        "(Wahapedia verbatim): \"While an enemy unit is within 9\\\" of "
        "one or more LEGIONES DAEMONICA NURGLE units from your army, "
        "that enemy unit is within your army's Shadow of Chaos. In each "
        "player's Command phase, select one enemy unit within your "
        "army's Shadow of Chaos. That unit must take a Battle-shock "
        "test.\" The first leg (extending Shadow of Chaos to a 9\" aura "
        "around Nurgle units) overlaps with the existing army-wide "
        "approximation in simulator.shadow_of_chaos (cited in "
        "data/rule_citations.d/chaos_daemons.json) which already applies "
        "the Shadow of Chaos -1-Battle-shock + D3-mortal-on-fail effect "
        "across an 18\" central area when any Chaos Daemons unit is "
        "alive — re-wiring it as a per-Nurgle-unit 9\" aura is a follow-"
        "up refinement, not a flag-flip. The second leg (forced Command-"
        "phase Battle-shock test on a selected enemy) has no per-Command-"
        "phase enemy-targeting hook in the schema. Per CLAUDE.md §10 "
        "ship NO-FLAG + composition-only. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/. The "
        "infantry composition tilt biases the picker toward Nurgle "
        "infantry archetypes (Plaguebearers / Nurglings / Plague Drones). "
        "DAEMONS-STRATAGEMS-V1 (wave 53): stratagems upgraded from the "
        "shared DAEMONIC_INCURSION_STRATAGEMS to the dedicated "
        "PLAGUE_LEGION_STRATAGEMS set (Seeping Virulence + Foetid "
        "Resurgence) drawn from 40k.app."
    ),
    stratagems=PLAGUE_LEGION_STRATAGEMS,
    preferred_composition="infantry",
)

SCINTILLATING_LEGION = Detachment(
    name="Scintillating Legion",
    faction="Chaos Daemons",
    notes=(
        "DAEMONS-DIAG-4 (2026-05-23): god-aligned variant detachment "
        "(Tzeentch). Real codex detachment rule 'Fates in Flux' "
        "(Wahapedia verbatim): \"You start the battle with three Flux "
        "tokens. You can spend one Flux token just after an Advance "
        "roll, Hit roll, Wound roll, Damage roll, saving throw or "
        "Hazardous test is made for a LEGIONES DAEMONICA TZEENTCH model "
        "or unit to re-roll that result.\" The token economy is a "
        "per-battle, per-roll-class reroll pool that the simulator does "
        "not model (no transient token-spend layer for any-stat reroll); "
        "the rule does NOT reduce to any existing Detachment flag "
        "without fabrication — a generic reroll_hit_ones / "
        "reroll_wound_ones would be the wrong shape (3 tokens flat, not "
        "an always-on roll-of-1 reroll). Per CLAUDE.md §10 ship NO-FLAG "
        "+ composition-only. Wahapedia: "
        "https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/. The "
        "balanced composition tilt biases the picker toward Tzeentch "
        "lists that mix infantry (Pink Horrors / Flamers) with monster/"
        "elite shooting (Burning Chariot / Lord of Change auras). "
        "DAEMONS-STRATAGEMS-V1 (wave 53): stratagems upgraded from the "
        "shared DAEMONIC_INCURSION_STRATAGEMS to the dedicated "
        "SCINTILLATING_LEGION_STRATAGEMS set (Flickering Reality) drawn "
        "from 40k.app."
    ),
    stratagems=SCINTILLATING_LEGION_STRATAGEMS,
    preferred_composition="balanced",
)

FINAL_DAY = Detachment(
    name="Final Day",
    faction="Genestealer Cults",
    notes=(
        "SC5-11 (2026-05-21): the real Psionic Parasitism rule lets each "
        "friendly Tyranids Synapse unit drain D3+1 mortal wounds from a "
        "nearby Genestealer Cults unit to grant +1 to Hit to a separate "
        "nearby Tyranids unit — a per-unit, per-Synapse trade-off, not "
        "an army-wide reroll-1s buff. The previous proxy "
        "`reroll_hit_ones=True` (army-wide, always-on) was a fabrication "
        "biasing Genestealer Cults sim WR upward. Removed. The detachment "
        "is still registered and its infantry composition preference is "
        "retained — list-build shape still applies. A faithful Psionic "
        "Parasitism implementation needs cross-faction Synapse-to-GSC "
        "trading that the simulator does not yet model; follow-up "
        "wiring lands separately."
    ),
    stratagems=FINAL_DAY_STRATAGEMS,
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
        "VOTANN-DIAG-2 (2026-05-26): the previous six stratagems (Warrior "
        "Pride, Wrath of the Ancestors, Glory of the Hearth, Ironkin "
        "Sequence, Ancestral Sentence at 2CP, Void-Armoured Resilience) "
        "were confirmed absent from the current 10e codex via Wahapedia. "
        "They were fabricated or sourced from a prior edition and were "
        "contributing to Leagues of Votann +6.48pt over-performance. "
        "Replaced with three real Needgaard Oathband stratagems: Huntr's "
        "Mark, Ancestral Sentence, Void Hardened. "
        "VOTANN-AUDIT-V1 (2026-05-29): Huntr's Mark removed — absent from "
        "BSData v10.6.0 (Leagues of Votann.cat.gz), no verifiable Wahapedia "
        "anchor citation per CLAUDE.md s10, and responsible for +7.8pt sim "
        "overshoot in 9-faction N=10 measurement. Two stratagems remain: "
        "Ancestral Sentence (Sustained Hits 1) and Void Hardened (defensive "
        "AP worsening no-op). See data/rule_citations.d/stratagems.json."
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
        "SC5-11 (2026-05-21): the canonical Armour of Contempt rule "
        "worsens the Armour Penetration characteristic of incoming "
        "attacks on Adeptus Astartes models by 1 — a defensive rule, "
        "not an offensive vehicle hit-reroll. The previous proxy "
        "`vehicles_reroll_hit_ones=True` was a direction-wrong "
        "fabrication (offensive buff substituted for a defensive one) "
        "biasing Marine-vehicle sim WR upward. Removed. The detachment "
        "is still registered and its vehicle composition preference is "
        "retained — list-build shape still applies. A faithful Armour "
        "of Contempt implementation needs an -1-to-incoming-AP defensive "
        "modifier on the Marine defender; follow-up wiring lands "
        "separately."
    ),
    preferred_composition="vehicle",
)

PLAGUE_COMPANY = Detachment(
    name="Plague Company",
    faction="Death Guard",
    notes=(
        "SC5-11 (2026-05-21): the previous `melee_sustained_hits_army_wide` "
        "flag was justified by a paraphrased 'Sworn to Nurgle (simplified)' "
        "citation that did not match any verbatim primary source for the "
        "Plague Company detachment rule — the real codex Plague Company "
        "is themed around named plague-company sub-themes (Mortarion's "
        "Anvil, Wraith Creepers, etc.), each granting different buffs to "
        "a narrow unit set, none of which is an army-wide melee SUSTAINED "
        "HITS 1 grant. The proxy was a fabrication biasing Death Guard "
        "sim WR upward (already noted as the +16.4 outlier compensation "
        "in the prior citation, which is itself a sign the buff was "
        "over-fit). Removed. The detachment is still registered and its "
        "infantry composition preference is retained — list-build shape "
        "still applies. A faithful Plague Company implementation needs a "
        "sub-theme selection layer that the simulator does not yet model; "
        "follow-up wiring lands separately. Stratagem set kept as the "
        "Awakened Dynasty placeholder pending a real Plague Company "
        "stratagem pull."
    ),
    stratagems=AWAKENED_DYNASTY_STRATAGEMS,  # placeholder; real PC has
    # its own stratagems. Per-strat differences smaller than rule lever.
    preferred_composition="infantry",
)

ANNIHILATION_LEGION = Detachment(
    name="Annihilation Legion",
    faction="Necrons",
    notes=(
        "Hardened Killers (Wahapedia verbatim): \"Each time a NECRONS "
        "unit from your army makes a ranged attack, you can re-roll a "
        "Wound roll of 1.\" Simulator: wired via the existing army-wide "
        "`reroll_wound_ones` flag (already in use by other detachments). "
        "Lossy by design — the Annihilation Legion detachment text "
        "applies the reroll specifically to RANGED attacks; the existing "
        "schema reroll_wound_ones applies to all attacks (ranged + "
        "melee). Necrons are a ranged-leaning faction so the over-broad "
        "application is small in practice. Real Annihilation Legion "
        "also gives various ranged stratagems and tank-flavour buffs "
        "that aren't wired individually here — the detachment rule "
        "alone is the LC-1 lever to give Necrons a stronger offensive "
        "alternative to Awakened Dynasty (whose lead-required +1-to-hit "
        "is conditional on character attachment that not every Necrons "
        "squad has). Cited as `ANNIHILATION_LEGION.reroll_wound_ones`."
    ),
    reroll_wound_ones=True,
    stratagems=AWAKENED_DYNASTY_STRATAGEMS,  # share for now — real
    # Annihilation Legion has its own stratagems (Galvanic Resurrection,
    # Tachyonic Annihilation, etc.); per-strat differences are smaller
    # than the detachment rule's MAE lever.
    preferred_composition="balanced",
)

CANOPTEK_COURT = Detachment(
    name="Canoptek Court",
    faction="Necrons",
    notes=(
        "SC5-11 (2026-05-21): the canonical Hyper-Logical Strategy rule "
        "grants a once-per-battle full Wound-roll reroll to CANOPTEK "
        "models for one phase — it is NOT an always-on +1-to-wound rule. "
        "The previous proxy `canoptek_plus_one_to_wound=True` (army-wide, "
        "always-on, every Canoptek-prefixed datasheet) was a "
        "magnitude- and frequency-wrong fabrication (a flat +1-wound "
        "over 5 rounds is dramatically stronger than a once-per-battle "
        "single-phase full reroll). Removed. The detachment is still "
        "registered and its balanced composition preference is retained — "
        "list-build shape still applies. A faithful Hyper-Logical "
        "Strategy implementation needs a once-per-battle, single-phase "
        "transient reroll grant that the simulator does not yet model; "
        "follow-up wiring lands separately."
    ),
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
    "subterranean_assault":    SUBTERRANEAN_ASSAULT,
    "noble_lance":             NOBLE_LANCE,
    # IK-KNIGHTS-V1 (2026-05-31): real codex detachments for both Knight factions.
    "valourstrike_lance":      VALOURSTRIKE_LANCE,
    "iconoclast_fiefdom":      ICONOCLAST_FIEFDOM,
    "hallowed_martyrs":        HALLOWED_MARTYRS,
    "shield_host":             SHIELD_HOST,
    "auric_champions":         AURIC_CHAMPIONS,
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
    "annihilation_legion":     ANNIHILATION_LEGION,
    "plague_company":          PLAGUE_COMPANY,
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
    # DET-VARIETY-1 (2026-05-22): alternate detachments for three factions
    # that previously had only one option in FACTION_DETACHMENTS, so the
    # picker always rolled the same detachment. All three ship no-flag +
    # composition-only (real codex rule does not map cleanly to existing
    # Detachment schema flags; per project rule "DO NOT FABRICATE proxy
    # flags" we ship the shell rather than invent a flag). See each
    # detachment's `notes` for the verbatim rule text and the rationale
    # for the no-flag choice.
    "bringers_of_flame":       BRINGERS_OF_FLAME,
    "cohort_cybernetica":      COHORT_CYBERNETICA,
    "kabalite_cartel":         KABALITE_CARTEL,
    # DAEMONS-DIAG-4 (2026-05-23): god-aligned Chaos Daemons sub-detachments
    # alongside Daemonic Incursion. All four ship no-flag + composition-only
    # — see per-detachment notes for the rule text and rationale.
    "blood_legion":            BLOOD_LEGION,
    "legion_of_excess":        LEGION_OF_EXCESS,
    "plague_legion":           PLAGUE_LEGION,
    "scintillating_legion":    SCINTILLATING_LEGION,
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
INVASION_FLEET     = DETACHMENTS["invasion_fleet"]
SUBTERRANEAN_ASSAULT = DETACHMENTS["subterranean_assault"]
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
    # iter16: Tyranids default flipped from "invasion_fleet" (which is
    # a -1 enemy Ld approximation of Shadow in the Warp, redundant with
    # simulator.shadow_in_the_warp) to "subterranean_assault" — the
    # May-2026 real-meta default after Ron Eilyahoo's GW Open Maastricht
    # 2026 win with a Subterranean Assault Trygon/Ravener list (Bell of
    # Lost Souls, Goonhammer detachment focus). Army-wide reroll-hit-1s
    # is the offensive uplift the calibration loop's archetype mode
    # (-9.4pt vs real WR) needs.
    "Tyranids":                 "subterranean_assault",
    # Orks: real codex detachment "War Horde" wired in iter-1 Cluster B B1.
    "Orks":                     "war_horde",
    # IK-KNIGHTS-V1 (2026-05-31): real codex detachments replace the no-op
    # NOBLE_LANCE proxy. Imperial Knights → Valourstrike Lance (Bold Gallantry
    # + Bondsman). Chaos Knights → Iconoclast Fiefdom (Dread Tyrants Aura).
    "Imperial Knights":         "valourstrike_lance",
    "Chaos Knights":            "iconoclast_fiefdom",
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
    "Necrons":                  ("awakened_dynasty", "canoptek_court", "annihilation_legion"),
    # iter16: Tyranids gains Subterranean Assault as the real-meta default
    # (May 2026 Maastricht GT winner — see DEFAULT_BY_FACTION comment).
    # Invasion Fleet is retained as a variant for the picker; both real
    # Tyranid detachments (also Synaptic Nexus, Vanguard Onslaught,
    # Crusher Stampede, Warrior Bioform Onslaught) remain UNIMPLEMENTED
    # — they land in per-detachment follow-ups.
    "Tyranids":                 ("subterranean_assault", "invasion_fleet"),
    # Orks: War Horde wired in iter-1 Cluster B B1 (real codex detachment).
    # Other 10e Ork detachments (Green Tide, Bully Boyz, Kult of Speed,
    # Dread Mob, Da Big Hunt, Taktikal Brigade, More Dakka!, Freebooter
    # Krew, Speedwaaagh!, Blitz Brigade) remain UNIMPLEMENTED — they land
    # in per-detachment follow-up tasks.
    "Orks":                     ("war_horde",),
    # IK-KNIGHTS-V1 (2026-05-31): real codex detachments for both Knight factions.
    # Imperial Knights: Valourstrike Lance is the competitive default (May 2026
    # meta, Goonhammer focus). Noble Lance retained as a no-buff variant so the
    # old baseline is still reachable if needed for regression testing.
    "Imperial Knights":         ("valourstrike_lance", "noble_lance"),
    # Chaos Knights: Iconoclast Fiefdom is the competitive default (Goonhammer,
    # May 2026 meta). Lords of Dread and Houndpack Lance are not yet wired.
    "Chaos Knights":            ("iconoclast_fiefdom",),
    # DET-VARIETY-1 (2026-05-22): add Bringers of Flame as a Sororitas
    # variant pick. Both ship no-flag (Hallowed Martyrs after SC5-4,
    # Bringers of Flame because the codex Fervent Purgation rule does
    # not map onto existing Detachment schema flags); the picker now
    # randomly rolls between them, diluting the always-pick-one
    # convergence that was driving Sororitas overperformance.
    "Adepta Sororitas":         ("hallowed_martyrs", "bringers_of_flame"),
    "Adeptus Custodes":         ("shield_host", "auric_champions"),
    # DET-VARIETY-1 (2026-05-22): add Cohort Cybernetica as an AdMech
    # variant pick. Same no-flag rationale as Bringers of Flame above.
    "Adeptus Mechanicus":       ("skitarii_hunter_cohort", "cohort_cybernetica"),
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
    # DET-VARIETY-1 (2026-05-22): add Kabalite Cartel as a Drukhari
    # variant pick. Same no-flag rationale as Bringers of Flame /
    # Cohort Cybernetica — the bespoke Contract / Pain-token economy
    # does not reduce to a static Detachment flag.
    "Drukhari":                 ("skysplinter_assault", "kabalite_cartel"),
    "T'au Empire":              ("montka",),
    "Tau Empire":               ("montka",),
    "Chaos Space Marines":      ("pactbound_zealots",),
    "Heretic Astartes":         ("pactbound_zealots",),
    # Death Guard: real codex detachment "Virulent Vectorium" wired in #195.
    # Thousand Sons: Rubricae Phalanx only (real-meta May 2026 default,
    # durability spine).
    #
    # Grand Coven removed from auto-pick list iter24 — Kindred Sorcery is
    # NOT implemented (see data/rule_citations.d/thousand_sons.json under
    # GRAND_COVEN.psychic_mortal_wounds_per_round: the once-per-Command-
    # phase, once-per-battle-each selectable buff does not reduce cleanly
    # to a static Detachment flag and is currently a no-op). Grand Coven
    # also disables All Is Dust (it's not on the Grand Coven detachment),
    # so when the picker resolved to Grand Coven (~11/20 of TSON armies
    # in archetype eval), the army lost the +1 save on D1 attacks AND
    # gained no compensating buff. Restore this tuple to
    # ("rubricae_phalanx", "grand_coven") when Kindred Sorcery is wired.
    "Death Guard":              ("virulent_vectorium", "plague_company"),
    "Thousand Sons":            ("rubricae_phalanx",),
    "World Eaters":             ("berzerker_warband",),
    # DAEMONS-DIAG-4 (2026-05-23): four god-aligned variant detachments
    # alongside the generic Daemonic Incursion. All no-flag + composition-only
    # per Wahapedia rule text (see per-detachment notes above). The picker
    # now rolls 5-way randomly instead of always Daemonic Incursion, diluting
    # the always-pick-one convergence the +18.96pt gated under-perf reflects.
    "Chaos Daemons":            ("daemonic_incursion", "blood_legion",
                                 "legion_of_excess", "plague_legion",
                                 "scintillating_legion"),
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

    # SC5-11 (2026-05-21): keyword-affinity gating now reads `det.name`
    # rather than the buff-flag fields, because three of those flags
    # (canoptek_plus_one_to_wound, vehicles_reroll_hit_ones, and the
    # PLAGUE_COMPANY melee-sustained-hits one) were dropped as
    # fabrications in this commit. The list-build shape — picking
    # Canoptek Court for Canoptek-heavy Necron armies, Ironstorm
    # Spearhead for vehicle-heavy Marines, etc. — is preserved by
    # gating on the detachment identity directly.
    det_name = det.name
    if det_name == "Canoptek Court":
        matched = sum(_pts(u) for u in units if _name(u).startswith("Canoptek"))
    elif det.plague_marines_plus_one_to_wound:
        matched = sum(_pts(u) for u in units if _name(u) == "Plague Marines")
    elif det.aspect_warrior_or_bike_plus_one_move:
        matched = sum(
            _pts(u) for u in units if _name(u) in ASPECT_WARRIOR_OR_BIKE_NAMES
        )
    elif det_name == "Ironstorm Spearhead":
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
    # Drukhari Combat Drugs (army rule): Hypex grants +2" Move on WYCH CULT
    # units. The simulator's `_apply_combat_drugs` hook stamps a per-unit
    # float bonus at battle start; default 0.0 on every non-Drukhari unit
    # means this add is safe. Cited as `simulator.combat_drugs`.
    base = base + float(getattr(unit, "combat_drug_move_bonus", 0.0) or 0.0)
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
