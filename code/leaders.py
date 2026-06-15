"""
Leader abilities — proximity-gated aura buffs from attached CHARACTER units.

10e attached leaders sit inside a friendly squad and project an aura: nearby
friendlies get to-hit / to-wound buffs, re-rolls, an invuln, Feel No Pain, or
mid-battle healing. This module is the MVP version of that: a small registry
of well-known characters keyed by substring match on the profile name, plus a
single helper `effective_buffs(attacker)` that merges:

    detachment passives (Army.resolve_detachment())
        +
    every alive friendly leader whose aura covers the attacker

into one buff dict the simulator can consume.

Wiring:
  - `Unit.attack` calls `effective_buffs(attacker)` to compose flags from the
    detachment and any in-range leader auras (re-roll 1s, +1 to hit / wound,
    extra invuln, FNP, +1 attack).
  - `Battle._run_round` runs `apply_round_end_healing(army)` so leaders with
    `heal_per_round > 0` patch up a nearby wounded friendly each round end.
  - `Battle._run_round` also runs `apply_round_end_revival(army)` so leaders
    with `revive_destroyed_per_round > 0` (Apothecary Narthecium) return a
    destroyed INFANTRY model from the led unit to play each round end.

The registry is intentionally small. Substring matching against `profile.name`
catches the obvious variants ("Captain in Terminator Armour" matches "Captain"),
which is enough to demonstrate the mechanic. Bespoke per-character abilities
(Lethal Hits aura, Oath of Moment, mortal-wound bombs etc.) are deferred.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .army import Army
    from .units import Unit


# ---------------------------------------------------------------------------
# LeaderAbility — same modifier shape as Detachment, plus aura range + heal
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LeaderAbility:
    """
    Aura buff granted by an attached CHARACTER to nearby friendlies.

    Modifier flags use the same convention as `Detachment`:
      * boolean fields: True = active
      * `extra_invuln`, `fnp`: 7 = none, lower number = better (10e d6 target)

    `aura_range` is in inches. `0` means army-wide (no proximity gating).

    `host_keys` carries DOUBLE DUTY:

      1. List-building hint for the calibrator's host picker: when this
         leader is seeded into a list, the picker walks `host_keys` in
         preference order and attaches the leader to the first UNIT_CATALOG
         key present in the army.

      2. Runtime gate for `effective_buffs`: the per-leader aura merge in
         `effective_buffs` only fires when the attacker's UNIT_CATALOG key
         is in `host_keys`. This implements the "While this model is
         leading a unit..." codex wording — the buff applies to the
         attached bodyguard squad, NOT to every friendly within aura range.

    Empty `host_keys = ()` is the explicit ARMY-WIDE convention:

      * Used for MONSTER / non-attachment auras whose codex wording reads
        "While a friendly <FACTION> unit is within X" of this model..."
        rather than "While this model is leading a unit..." — e.g. the
        Hive Tyrant's Onslaught, the Avatar of Khaine's Bloody-Handed.
        These leaders broadcast their aura to every friendly in range
        with no led-unit requirement.
      * `effective_buffs` reads an empty tuple as "skip the host gate" and
        merges the aura buff onto whichever attacker is in range.

    Iter 22 — the per-leader merge in `effective_buffs` was widened to
    consult `host_keys` because a host_keys-less merge applied every
    leader's aura army-wide (Typhus FNP firing on all Death Guard within
    6", Lieutenant +1-to-wound on every Marine within 6", etc.). Same
    structural bug affected every faction's character auras.
    """
    name: str
    aura_range: float                       # inches; 0 = army-wide
    # Offensive modifiers (apply to ATTACKER when it's in range of this leader)
    reroll_hit_ones: bool = False
    # TSON-AURA-V2 (iter60): shooting-phase-only variant of reroll_hit_ones.
    # Used for Psychic-leader abilities whose codex text says "each time a
    # Psychic Attack is made" or "until the end of the [Shooting] phase" —
    # the codex explicitly restricts the re-roll to the Shooting phase.
    # In units.py the flag is consumed with a `mode != "melee"` guard
    # (matching the existing transient_reroll_hits_shooting gate pattern),
    # so melee attacks from the same led unit receive no re-roll.
    # Affects: Ahriman "Master of the Rubricae (Psychic)" (Shooting/Psychic
    # only), Infernal Master "Malefic Maelstrom (Psychic)" (weapons in unit
    # gain [SUSTAINED HITS 1] — codex doesn't gate by phase but the proxy
    # is directionally correct for ranged-heavy Rubric Marines), Sorcerer
    # in Terminator Armour "Marked by Fate (Psychic)" (explicitly "Until
    # the end of the [Shooting] phase").
    reroll_hit_ones_shooting_only: bool = False
    reroll_wound_ones: bool = False
    plus_one_to_hit: bool = False
    plus_one_to_hit_melee_only: bool = False  # +1 to hit in melee attacks only (e.g. Warboss "Might is Right")
    plus_one_to_wound: bool = False
    plus_one_to_wound_melee_only: bool = False  # +1 to wound in melee attacks only (e.g. Dark Apostle "Dark Zealotry")
    plus_one_attack: int = 0                # +N extra attacks per weapon (Cadre Fireblade etc.)
    # Greater Daemon locus auras (LEADERABILITY-SCHEMA, claude/sim-calibration-6).
    # Each maps to a per-stat uplift on the led / in-aura attacker's attack
    # resolution. None of these were expressible before — adding them unlocks
    # Lord of Change (Locus of Change, +1 Strength on ranged), Great Unclean One
    # (Locus of Virulence, +1 Toughness on the led unit), and Keeper of Secrets
    # (Locus of Slaanesh, +1 AP on melee). All three are cited verbatim in
    # data/rule_citations.d/leaders.json. The Daemons archetype was the
    # immediate driver — Greater Daemons sit at ~300-400pts each in tournament
    # lists and going un-wired contributed to Daemons' -22pt gated under-perf
    # at N=5. The fields are generic, so they can be reused by future leaders
    # whose codex grants the same direction (e.g. any "+1 Strength to ranged
    # in 6"" locus / etc.).
    plus_one_strength_ranged: bool = False  # attacker's ranged S += 1 when led/in-aura
    plus_one_toughness: bool = False         # target's T += 1 when led/in-aura
    plus_one_ap_melee: bool = False          # attacker's melee AP improves by 1 (more negative)
    # DAEMONS-DIAG-7: Skulltaker "Lord of Decapitations" — melee weapons
    # equipped by the led unit gain [DEVASTATING WOUNDS]. Melee-only gate
    # enforced at the attack-resolution site in code/units.py. BSData v10.6.0
    # Chaos - Chaos Daemons Library.cat.gz, Skulltaker profile, Lord of
    # Decapitations ability: "While this model is leading a unit, melee
    # weapons equipped by models in that unit have the [DEVASTATING WOUNDS]
    # ability." The field is generic so future leaders with the same grant
    # (if any are added) can reuse it without schema changes.
    grants_devastating_wounds_melee: bool = False  # led unit's melee attacks gain [DEVASTATING WOUNDS]
    # DAEMONS-DIAG-9: Daemon Prince of Chaos "Prince of Darkness" (Aura) —
    # "While a friendly LEGIONES DAEMONICA unit is within 6\" of this model,
    # models in that unit have the Stealth ability." (Wahapedia verbatim).
    # Stealth imposes -1 on ranged Hit rolls targeting the unit (10e core rule,
    # "each time a ranged attack is made against it, subtract 1 from that
    # attack's Hit roll"). This is a DEFENDER-side buff: it fires via
    # tgt_buffs["grants_stealth_aura"] in the attack-resolution loop in
    # code/units.py, at the same location as the static target.profile.stealth
    # check (line ~2024). The field is generic so future leaders whose codex
    # grants a Stealth aura can reuse it without schema changes.
    grants_stealth_aura: bool = False           # nearby LEGIONES DAEMONICA gain Stealth (ranged -1 to hit)
    # DAEMONS-LOCUS-V1 follow-up — [SUSTAINED HITS N] aura granted by the
    # leader to the led unit's attacks. Integer fields so multiple sources
    # stack additively, matching the per-weapon / detachment / transient
    # SUSTAINED HITS stacking convention already in code/units.py.
    #   - sustained_hits_ranged: Locus of Change (Tzeentch Changecaster, BSData
    #     "ranged weapons equipped by models in that unit have the [SUSTAINED
    #     HITS 1] ability"). Replaces the prior reroll_hit_ones proxy.
    #   - sustained_hits_melee: Locus of Putrescence (Nurgle Spoilpox Scrivener
    #     on Plaguebearers melee) and Locus of Slaanesh (Slaanesh Tormentbringer
    #     on Slaanesh units melee). Schema-ready for these leaders to be added
    #     to the registry without a follow-up dataclass change.
    sustained_hits_ranged: int = 0
    sustained_hits_melee: int = 0
    # Galvanic Field (AdMech Manipulus): led unit's ranged weapons gain [LETHAL HITS]
    lethal_hits_ranged: bool = False
    extra_invuln: int = 7                   # 7 = none
    fnp: int = 7                            # 7 = none
    # End-of-round healing: restore N HP to the nearest wounded friendly in
    # aura range (or to the leader itself if none are wounded).
    heal_per_round: int = 0
    # End-of-round revive: return N destroyed friendly INFANTRY models from
    # nearby units (within aura_range) to play at full HP. Apothecary
    # Narthecium per the 10e Space Marines codex.
    revive_destroyed_per_round: int = 0
    # Command Point economy modifiers — these fire only when the bearer is
    # this army's Warlord. The simulator picks the Warlord at battle start
    # (first alive CHARACTER unit with any non-zero CP field set).
    #
    # `cp_discount_per_round`: extra CP awarded at the start of every Command
    # phase (capped at 6 by the universal CP_CAP). Roboute Guilliman's
    # "Author of the Codex" army-rule slot per the Ultramarines 10e codex.
    cp_discount_per_round: int = 0
    # `cp_refund_per_battle`: one-time-per-battle refund pool. When > 0, the
    # next stratagem spend by this army is refunded 1 CP and the pool
    # decrements. Models Belisarius Cawl's "Master of the Forge" once-per-
    # battle bonus CP and Trazyn the Infinite's "Surreptitious Acquisition"
    # CP-stealing trickery (10e Necrons codex).
    cp_refund_per_battle: int = 0
    # `first_stratagem_free_per_round`: the first stratagem fired each round
    # by this army costs 0 CP. Models Lord of Contagion's "Lord of the
    # Death Guard" Warlord trait when fielded as Warlord.
    first_stratagem_free_per_round: bool = False
    # Adepta Sororitas — Miraculous Intervention (Saint Celestine). The FIRST
    # time this CHARACTER model is destroyed during the battle, roll one D6 at
    # the end of the phase; on a 2+, set the model back up with full wounds.
    # Tracked via Army.self_revive_used_uids so the once-per-battle guard fires
    # on the model's uid, not on the unit name.
    # Gated SWEG_SOROR_ABILITIES (default-ON since wave 232).
    # BSData v10.6.0 (Imperium - Adepta Sororitas.cat.gz, ability id
    # eee9-b689-1a73-742b, typeName Abilities). Cited as
    # `simulator.celestine_miraculous_intervention`.
    self_revive_on_2plus: bool = False
    # Aeldari Ynnari — Ethereal Form (The Yncarne). Each time THIS model
    # destroys an enemy unit it regains up to D3 lost wounds (roll 1D3, cap at
    # starting wounds). The trigger fires on the KILLER being the Yncarne, NOT
    # on any enemy unit dying anywhere. Implemented via
    # `maybe_apply_yncarne_heal` called from each kill site in simulator.py
    # (shooting, melee, Tank Shock, Counter-Offensive), mirroring the Celestine
    # pattern. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/The-Yncarne
    # Cited as `LeaderAbility.Ethereal Form`.
    heal_d3_on_kill: bool = False
    # Legal bodyguard hosts for the calibrator. Preference order; the
    # picker chooses the first key present in UNIT_CATALOG.
    host_keys: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Registry — substring-keyed lookup by profile name
# ---------------------------------------------------------------------------
# Order matters: longer / more specific keys come FIRST so that
# "Captain in Terminator Armour" matches "Captain" cleanly but doesn't
# accidentally collide with a hypothetical future "Captain-General".

# Host preferences below are 10e legal-attachment guidelines. The calibrator
# walks the tuple and picks the first entry that exists in UNIT_CATALOG.
_MARINE_HOSTS = (
    "space_marines_assault_intercessor_squad",
    "space_marines_tactical_squad",
)
# Necron noble characters (Overlord, Chronomancer, Technomancer) lead three
# bodyguard units per the 10e codex Overlord datasheet: NECRON WARRIORS,
# IMMORTALS, and LYCHGUARD. Iter 20: Lychguard added (was missing — caused
# Lychguard squads to be excluded from the Command-Protocols +1-to-hit gate
# even when an Overlord was attached). Wahapedia:
# https://wahapedia.ru/wh40k10ed/factions/necrons/Overlord — "LEADER: This
# model can be attached to the following units: NECRON WARRIORS, IMMORTALS,
# LYCHGUARD."
_NECRON_HOSTS = (
    "necrons_necron_warriors",
    "necrons_immortals",
    "necrons_lychguard",
)
_AELDARI_GUARDIAN_HOSTS = (
    "aeldari_craftworlds_guardian_defenders",
    "aeldari_craftworlds_storm_guardians",
)
_TAU_FIRE_HOSTS = ("t_au_empire_strike_team", "t_au_empire_breacher_team")

# Khorne Legiones Daemonica units — units that benefit from Bloodthirster's
# "Daemon Lord of Khorne" aura and Skarbrand's "Rage Embodied" aura. Both
# auras read "While a friendly KHORNE Legiones Daemonica unit is within 6"".
# This is NOT a led-unit gate (the Greater Daemons do not formally attach via
# Leader): host_keys here gates the buff to attacker units carrying the
# Khorne keyword, applied at proximity per the aura wording. Same structural
# pattern as Magnus / Avatar (empty host_keys for army-wide MONSTER auras),
# but narrowed to mono-mark units because the Daemonic Incursion archetype
# is multi-god — broadcasting Khorne to Plaguebearers / Pink Horrors /
# Daemonettes would be a fabrication (CLAUDE.md §10).
# Roster per Wahapedia https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/
# filtered to BSData v10.6.0 catalogue keys (no Legends entries).
_KHORNE_DAEMON_HOSTS = (
    "chaos_daemons_library_bloodletters",
    "chaos_daemons_library_bloodcrushers",
    "chaos_daemons_library_flesh_hounds",
    "chaos_daemons_library_skull_cannon",
    "chaos_daemons_library_khorne_soul_grinder",
    "chaos_daemons_library_skullmaster",
    "chaos_daemons_library_skulltaker",
    "chaos_daemons_library_karanak",
    "chaos_daemons_library_bloodmaster",
    "chaos_daemons_library_rendmaster_on_blood_throne",
)

# LEADERABILITY-SCHEMA — Tzeentch / Nurgle / Slaanesh Legiones Daemonica
# rosters. Same derivation pattern as _KHORNE_DAEMON_HOSTS above: the
# Greater Daemon's "Daemon Lord of <god>" aura reads "While a friendly
# <GOD> Legiones Daemonica unit is within 6"" — host_keys gates the
# buff to the catalogue keys carrying that god's keyword, applied at
# proximity. Roster filtered to BSData v10.6.0 (no Legends entries) per
# Wahapedia https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/.
# Skull Altar and Feculent Gnarlmaw are terrain pieces (no unit profile
# to buff); Be'lakor is UNDIVIDED (not tagged TZEENTCH/NURGLE/SLAANESH);
# Daemon Prince of Chaos has a player-chosen god at list-building but the
# BSData entry is undivided so it stays out of all three rosters. Syll'esske
# is dual-keyword SLAANESH/KHORNE per the codex but lists SLAANESH for
# Locus targeting — included in the Slaanesh roster only.
_TZEENTCH_DAEMON_HOSTS = (
    "chaos_daemons_library_pink_horrors",
    "chaos_daemons_library_blue_horrors",
    "chaos_daemons_library_flamers",
    "chaos_daemons_library_screamers",
    "chaos_daemons_library_burning_chariot",
    "chaos_daemons_library_tzeentch_soul_grinder",
    "chaos_daemons_library_kairos_fateweaver",
    "chaos_daemons_library_changecaster",
    "chaos_daemons_library_fluxmaster",
    "chaos_daemons_library_fateskimmer",
    "chaos_daemons_library_exalted_flamer",
    "chaos_daemons_library_the_blue_scribes",
    "chaos_daemons_library_the_changeling",
)
_NURGLE_DAEMON_HOSTS = (
    "chaos_daemons_library_plaguebearers",
    "chaos_daemons_library_nurglings",
    "chaos_daemons_library_plague_drones",
    "chaos_daemons_library_beasts_of_nurgle",
    "chaos_daemons_library_nurgle_soul_grinder",
    "chaos_daemons_library_rotigus",
    "chaos_daemons_library_horticulous_slimux",
    "chaos_daemons_library_epidemius",
    "chaos_daemons_library_poxbringer",
    "chaos_daemons_library_sloppity_bilepiper",
    "chaos_daemons_library_spoilpox_scrivener",
)
_SLAANESH_DAEMON_HOSTS = (
    "chaos_daemons_library_daemonettes",
    "chaos_daemons_library_seekers",
    "chaos_daemons_library_fiends",
    "chaos_daemons_library_hellflayers",
    "chaos_daemons_library_slaanesh_soul_grinder",
    "chaos_daemons_library_shalaxi_helbane",
    "chaos_daemons_library_syll_esske",
    "chaos_daemons_library_contorted_epitome",
    "chaos_daemons_library_infernal_enrapturess",
    "chaos_daemons_library_the_masque_of_slaanesh",
    "chaos_daemons_library_tormentbringer",
    "chaos_daemons_library_tranceweaver",
)

# DAEMONS-DIAG-9: ALL LEGIONES DAEMONICA units from BSData v10.6.0
# chaos_daemons_library catalogue. The Daemon Prince of Chaos "Prince of
# Darkness" aura reads "While a friendly LEGIONES DAEMONICA unit is within 6\"
# of this model, models in that unit have the Stealth ability." — it covers
# EVERY Daemon unit carrying the LEGIONES DAEMONICA faction keyword, regardless
# of god alignment or unit type. Legends entries (_legends suffix) are excluded
# because the auto-loop eval never seeds them. The Daemon Prince itself carries
# LEGIONES DAEMONICA and so benefits from its own aura per the codex text
# ("friendly" does NOT exclude the caster's own unit per Wahapedia core-rules
# FAQ). Union of all four god-rosters (Khorne/Nurgle/Tzeentch/Slaanesh) plus
# UNDIVIDED units (Be'lakor, Daemon Princes, Soul Grinders where not already
# included).
_LEGIONES_DAEMONICA_HOSTS: Tuple[str, ...] = (
    # Khorne
    *_KHORNE_DAEMON_HOSTS,
    # Nurgle (Rotigus already in _NURGLE_DAEMON_HOSTS)
    *_NURGLE_DAEMON_HOSTS,
    # Tzeentch
    *_TZEENTCH_DAEMON_HOSTS,
    # Slaanesh
    *_SLAANESH_DAEMON_HOSTS,
    # Undivided / multi-god units (not already in the god-rosters above)
    "chaos_daemons_library_be_lakor",
    "chaos_daemons_library_daemon_prince_of_chaos",
    "chaos_daemons_library_daemon_prince_of_chaos_with_wings",
)

# T'au "Coordinated Fire Plan" (Commander in Battlesuit / Coldstar) fidelity
# gate (wave 212). The real 10e rule (cited verbatim in the LeaderAbility
# .Coordinated Fire Plan citation) grants the LED unit a Move characteristic of
# 12" and the [ASSAULT] ability on its ranged weapons — there is NO Hit-roll
# bonus, and the buff is led-unit-scoped. The prior implementation proxied this
# as `plus_one_to_hit=True` with no host_keys, which the LeaderAbility docstring
# defines as ARMY-WIDE — so it fabricated an army-wide +1 to Hit that over-
# credited every T'au unit's shooting. The faithful default removes that
# fabricated buff (the [ASSAULT] / Move 12" mobility effects are left unmodelled,
# as the simulator does not model Movement-characteristic bonuses). Set
# `SWEG_TAU_CMD=0` to revert to the prior fabricated +1-to-hit proxy for the A/B.
_TAU_CMD_FIX = os.environ.get("SWEG_TAU_CMD", "1") != "0"

# Chaos Space Marines leader host-routing fidelity gate (wave 213). The CSM
# Dark Apostle and Sorcerer had host_keys pointing at units absent from (or
# marginal in) the army — Traitor Guardsmen (not fielded) and a single Cultist
# Mob — so their auras fired on chaff or nothing, never on the Legionaries /
# Chosen core that does the fighting. BSData v10.6.0 (Chaos - Chaos Space
# Marines.cat.gz, "This model can be attached to the following units:") confirms
# the Dark Apostle leads ACCURSED CULTISTS / CHOSEN / CULTIST MOB / LEGIONARIES
# and the Sorcerer leads CHOSEN / LEGIONARIES. The faithful default routes them
# to the core combat squads (their existing effect proxies are unchanged — the
# Dark Apostle's reroll-1s and the Sorcerer's Feel No Pain proxy still approximate
# the real +1-to-Wound-melee and -1-to-Hit-defensive abilities respectively).
# The Chaos Lord is deliberately NOT touched here: its current +1-to-Wound aura
# is a fabrication (the real "Chance for Glory" is a once-per-battle SELF buff,
# not a unit aura), and it currently fires on nothing — routing it would inject
# the fabrication onto the core squad. It is handled in a separate wave.
# Set SWEG_CSM_LEADERS=0 to revert to the prior (mis-routed) host_keys for the A/B.
_CSM_LEADER_FIX = os.environ.get("SWEG_CSM_LEADERS", "1") != "0"
_CSM_APOSTLE_HOSTS = (
    ("chaos_space_marines_legionaries", "chaos_space_marines_chosen",
     "chaos_space_marines_cultist_mob")
    if _CSM_LEADER_FIX else
    ("chaos_space_marines_cultist_mob",)
)
_CSM_SORCERER_HOSTS = (
    ("chaos_space_marines_legionaries", "chaos_space_marines_chosen")
    if _CSM_LEADER_FIX else
    ("chaos_space_marines_traitor_guardsmen_squad", "chaos_space_marines_cultist_mob")
)

_REGISTRY: Tuple[Tuple[str, LeaderAbility], ...] = (
    # ORDER NOTE — iter21: substring matching is greedy first-match, so
    # cross-faction CHARACTERs whose names CONTAIN "Captain" (Custodes
    # Shield-Captain, Grey Knights Brother-Captain) MUST appear BEFORE
    # the generic Marines "Captain" entry. Pre-iter21 this was masked
    # because all three entries carried `reroll_hit_ones=True`, so the
    # bug was invisible — Shield-Captain matched "Captain" first and
    # got the same buff. Dropping Captain's reroll proxy surfaces the
    # collision (Shield-Captain / Brother-Captain falling through to
    # Captain's now-empty entry). The fix: pin the longer keys to the
    # top of the registry. Test:
    #   tests/test_leaders.py::ExpandedRegistryTests::test_each_new_leader_resolves
    # Adeptus Custodes Shield-Captain — BSData v10.6.0 (`Imperium - Adeptus
    # Custodes.cat.gz`). The Shield-Captain has two datasheet abilities:
    #   "Master of the Stances": Once per battle, when this model's unit is
    #   selected to fight, it can use this ability. If it does, until that
    #   fight is resolved, both Ka'tah Stances are active for that unit,
    #   instead of only one.
    #   "Leader: Custodian Guard, Custodian Wardens."
    # Additionally the Wahapedia citation lists "Strategic Mastery": once per
    # battle round, reduce the CP cost of one Stratagem targeting this unit
    # by 1 — a CP-economy effect the simulator does not model.
    # "Stoic Vigil" is NOT a real codex ability name; it was an invented
    # label used when `reroll_hit_ones=True` was placed as a flavour proxy.
    # CUSTODES-AUDIT (claude/sim-calibration-6): removed `reroll_hit_ones=True`.
    # The prior proxy was self-flagged in the rule citation as an
    # "upper-bound flavour proxy" and was contributing to Custodes
    # over-performance (sim 59.4% vs real 52.1%). Neither "Master of the
    # Stances" nor "Strategic Mastery" translates to a per-attack hit-reroll
    # aura. The entry is retained (host_keys intact) so lookup_ability
    # resolves cleanly per CLAUDE.md §13 and so proximity / is_actually_led
    # gates continue to work. Same fabrication-removal standard as SC5-3
    # (Trajann Valoris Captain-General), iter21 (Captain / Autarch / Avatar).
    # Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/Shield-Captain
    ("Shield-Captain",     LeaderAbility(name="Master of the Stances",      aura_range=6.0,
                                          host_keys=("adeptus_custodes_custodian_guard",
                                                     "adeptus_custodes_custodian_guard_with_adrasite_and_pyrithite_spears",
                                                     "adeptus_custodes_custodian_wardens"))),
    ("Brother-Captain",    LeaderAbility(name="First to the Fray",          aura_range=6.0, reroll_hit_ones=True,
                                          host_keys=("grey_knights_strike_squad",))),
    # Space Marine HQ — named characters first so they win the substring
    # match before the generic "Captain" entry below.
    #
    # iter21 fabrication audit — Marines leader aura proxies removed:
    #   * Guilliman: dropped `reroll_hit_ones=True` proxy. The "Author of
    #     the Codex" codex ability is a CP gain (+1 CP per Command phase
    #     when Guilliman is Warlord) — there is NO hit-re-roll component
    #     in the real datasheet. `cp_discount_per_round=1` is the faithful
    #     codex mechanic and is preserved.
    #   * Captain: dropped `reroll_hit_ones=True` proxy. "Rites of Battle"
    #     is a once-per-round 1 CP discount on a Stratagem — a CP-econ
    #     effect with no aura damage buff. SwegHammer doesn't model
    #     Stratagem-targeted CP discounts (only the warlord +1/round and
    #     once-per-battle refunds), so the entry is kept structurally
    #     (host_keys still resolves Captain as a valid Marines leader for
    #     proximity / `is_actually_led` gates) but contributes no
    #     offensive aura. Strictly weaker than the prior fabrication.
    #   * Chaplain: dropped `reroll_wound_ones=True` proxy. The Chaplain's
    #     "Spiritual Leader" ability is a once-per-battle Battle-shock
    #     removal on a friendly ADEPTUS ASTARTES unit — a defensive
    #     morale recovery, not an offensive buff. The simulator does model
    #     Battle-shock, but the once-per-battle target-restricted nature
    #     of this ability is not auto-applicable as an aura.
    #   * Librarian: kept `fnp=5` (introduced in iter15). Codex grants
    #     "Feel No Pain 4+ vs PSYCHIC attacks + 4+ invuln from Mental
    #     Fortress" — both halves are DEFENSIVE; fnp=5 is the
    #     direction-correct strictly-weaker proxy. NO change in iter21.
    #   * Apothecary: kept `revive_destroyed_per_round=1` (faithful match
    #     to the codex Narthecium rule). NO change in iter21.
    ("Roboute Guilliman", LeaderAbility(name="Author of the Codex",         aura_range=6.0,
                                          cp_discount_per_round=1,
                                          host_keys=_MARINE_HOSTS)),
    ("Captain",            LeaderAbility(name="Rites of Battle",            aura_range=6.0, host_keys=_MARINE_HOSTS)),
    ("Chaplain",           LeaderAbility(name="Spiritual Leader",           aura_range=6.0, host_keys=_MARINE_HOSTS)),
    ("Apothecary",         LeaderAbility(name="Narthecium",                 aura_range=3.0, revive_destroyed_per_round=1, host_keys=_MARINE_HOSTS)),
    ("Librarian",          LeaderAbility(name="Mental Fortress",             aura_range=6.0, fnp=5,                 host_keys=_MARINE_HOSTS)),
    # Adepta Sororitas
    # SORORITAS-DIAG (2026-05-23): Canoness aura removed. Prior implementation
    # claimed "Beacon of Faith" granting reroll-hit-1s in aura range, citing
    # Wahapedia for the Canoness "Sacred Command" ability — but the cited rule
    # text reads: "Once per battle round, one unit from your army with this
    # ability can use it when its unit is targeted with a Stratagem. If it
    # does, reduce the CP cost of that use of that Stratagem by 1CP."  The
    # Sacred Command rule is a Stratagem CP discount, NOT a hit re-roll. The
    # prior aura was a fabricated offensive proxy (the citation itself read
    # "invented label for a reroll-1s offensive proxy"). Project rule 10
    # (cite every rule, do not invent) and rule 13 (no silent overbuffs)
    # require the proxy be removed rather than relabelled. The CP-discount
    # mechanic is not modelled in the simulator; the Canoness ships with NO
    # offensive aura until a faithful implementation lands. Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/#Canoness
    #
    # SWEG_SOROR_ABILITIES-gated entries (default-ON since wave 232 — gate is in
    # effective_buffs via _soror_gate_on, same pattern as SWEG_CSM_ABILITIES).
    #
    # Saint Celestine — "Miraculous Intervention" (once-per-battle self-revive
    # on 2+). BSData v10.6.0 Imperium - Adepta Sororitas.cat.gz, ability id
    # eee9-b689-1a73-742b: "The first time this unit's Celestine model is
    # destroyed, roll one D6 at the end of the phase. On a 2+, set that
    # Celestine model back up on the battlefield, as close as possible to where
    # it was destroyed and not within Engagement Range of any enemy units, with
    # its full wounds remaining."
    # The LeaderAbility.self_revive_on_2plus flag signals the simulator-side
    # `_maybe_apply_celestine_revival` hook. Celestine attaches to Seraphim
    # Squad or Zephyrim Squad per the BSData Leader profile (SWEG-checked via
    # UNIT_CATALOG keys below). Gated SWEG_SOROR_ABILITIES. Cited as
    # `simulator.celestine_miraculous_intervention` +
    # `LeaderAbility.Miraculous Intervention`.
    ("Saint Celestine",    LeaderAbility(name="Miraculous Intervention",     aura_range=6.0,
                                          self_revive_on_2plus=True,
                                          host_keys=("adepta_sororitas_seraphim_squad",
                                                     "adepta_sororitas_zephyrim_squad",))),
    # Morvenn Vahl — "Abbess Sanctorum". BSData v10.6.0 Imperium - Adepta
    # Sororitas.cat.gz, ability id 5e86-cb68-9205-16c4: "While this model is
    # leading a unit, each time a model in that unit makes an attack, you can
    # re-roll the Hit roll and you can re-roll the Wound roll."
    # APPROXIMATION: the codex grants full re-roll of any hit/wound failure;
    # SwegHammer's reroll_hit_ones + reroll_wound_ones re-roll only natural 1s
    # (the simulator has no full-reroll leader field distinct from reroll-1s).
    # Direction-correct; strictly weaker than the codex. Attaches to Paragon
    # Warsuits per BSData Leader profile. Gated SWEG_SOROR_ABILITIES. Cited as
    # `LeaderAbility.Abbess Sanctorum`.
    ("Morvenn Vahl",       LeaderAbility(name="Abbess Sanctorum",            aura_range=6.0,
                                          reroll_hit_ones=True,
                                          reroll_wound_ones=True,
                                          host_keys=("adepta_sororitas_paragon_warsuits",))),
    # Necrons — named characters first so they win the substring match
    # before the generic "Overlord" entry below.
    #
    # wave 235 fabrication removals (four entries):
    #
    # 1. Trazyn the Infinite `plus_one_to_hit` — REMOVED. The real datasheet
    #    abilities are "Leader" / "Ancient Collector" (sticky objective:
    #    "While this model is leading a unit, that unit counts as having at
    #    least 5 models for the purposes of controlling objective markers.")
    #    and "Surrogate Hosts" (resurrection: "Once per battle, if this
    #    model is destroyed, roll one D6 at the end of the phase. On a 2+,
    #    set this model back up anywhere on the battlefield that is not
    #    within Engagement Range of any enemy models, with half its starting
    #    wounds remaining."). Neither grants a to-hit aura. The
    #    `cp_refund_per_battle=1` field models the Warlord-gated
    #    "Surreptitious Acquisition" CP-steal ability (separately cited as
    #    LeaderAbility.Surreptitious Acquisition and faithfully retained).
    #    UNMODELLED REAL RULES: Ancient Collector (sticky objective count),
    #    Surrogate Hosts (once-per-battle 2+ self-revive to half wounds) —
    #    neither has a LeaderAbility flag equivalent; parking-lot until
    #    objective-counting and per-character resurrection hooks land.
    #    BSData v10.6.0 Necrons.cat.gz, Trazyn the Infinite profile, typeName
    #    "Abilities": ids for Ancient Collector and Surrogate Hosts confirmed.
    #
    # 2. Overlord `plus_one_to_hit` — REMOVED. The real "My Will Be Done" is
    #    "Once per battle round, one unit from your army with this ability
    #    can use it when its unit is targeted with a Stratagem. If it does,
    #    reduce the CP cost of that use of that Stratagem by 1CP." This is a
    #    Stratagem CP-discount ability (same pattern as Space Marine Captain
    #    "Rites of Battle" dropped in iter21, Autarch "Path of Command"
    #    dropped in iter21, and Adeptus Custodes Shield-Captain "Strategic
    #    Mastery" dropped in the custodes audit) — NOT a hit-roll aura.
    #    UNMODELLED REAL RULE: My Will Be Done (once-per-round Stratagem
    #    CP discount) — no per-character Stratagem-CP-discount hook exists.
    #    BSData v10.6.0 Necrons.cat.gz, Overlord profile: ability text
    #    confirmed verbatim via STRUCTURAL_DEBT_REVIEW.md orchestrator
    #    cross-verification.
    #
    # 3. Chronomancer `fnp=5` — REMOVED. The real "Chronometron" is:
    #    "In your Shooting phase, after this model's unit has shot, if it
    #    is not within Engagement Range of any enemy units, that unit can
    #    make a Normal move of up to 5\" as if it were your Movement phase.
    #    If it does, until the end of the turn, that unit is not eligible to
    #    declare a charge." This is a post-Shooting-phase movement ability,
    #    not a feel no pain save. UNMODELLED REAL RULE: Chronometron (post-
    #    shoot 5\" Normal move conditional on not being in Engagement Range)
    #    — the simulator has no post-shooting-phase movement hook for led
    #    units. Parking-lot until a Movement-phase trigger layer lands.
    #    BSData v10.6.0 Necrons.cat.gz, Chronomancer profile: ability text
    #    confirmed verbatim via STRUCTURAL_DEBT_REVIEW.md orchestrator
    #    cross-verification.
    #
    # 4. Plasmancer `fnp=5` — REMOVED. The real "Harbinger of Destruction"
    #    is: "While this model is leading a unit, each time a model in that
    #    unit makes a ranged attack, a successful unmodified Hit roll of 5+
    #    scores a Critical Hit." This is a ranged crit-hit-threshold lowering
    #    ability (5+ instead of the canonical 6), not a feel no pain save.
    #    FAITHFUL REBUILD ASSESSMENT: the existing `melee_crit_threshold`
    #    variable in code/units.py (set up around line 3523) lowers the crit
    #    threshold for melee only; the ranged crit path (line 3816) is
    #    hard-coded to `unmodified_roll == 6` with no variable or leader-aura
    #    hook. Wiring a ranged crit-on-5+ from a leader aura would require
    #    (a) a new `ranged_crit_threshold_aura: int = 6` field on
    #    LeaderAbility and (b) a new read of `att_buffs.get(...)` in the
    #    ranged crit branch of code/units.py — NEW MACHINERY. Per the wave 235
    #    briefing: removal only when new machinery is needed. UNMODELLED REAL
    #    RULE: Harbinger of Destruction (ranged crit-hit threshold lowered to
    #    5+ on the led unit) — parking-lot until a ranged-crit-threshold
    #    leader-aura field is added. BSData v10.6.0 Necrons.cat.gz, Plasmancer
    #    profile: "While this model is leading a unit, each time a model in
    #    that unit makes a ranged attack, a successful unmodified Hit roll of
    #    5+ scores a Critical Hit." Confirmed verbatim via STRUCTURAL_DEBT_REVIEW.md
    #    orchestrator cross-verification.
    ("Trazyn the Infinite", LeaderAbility(name="Surreptitious Acquisition", aura_range=6.0,
                                          cp_refund_per_battle=1,
                                          host_keys=_NECRON_HOSTS)),
    ("Overlord",           LeaderAbility(name="My Will Be Done",            aura_range=6.0, host_keys=_NECRON_HOSTS)),
    ("Chronomancer",       LeaderAbility(name="Chronometron",               aura_range=6.0, host_keys=_NECRON_HOSTS)),
    ("Plasmancer",         LeaderAbility(name="Harbinger of Destruction",   aura_range=6.0, host_keys=("necrons_immortals", "necrons_necron_warriors"))),
    ("Technomancer",       LeaderAbility(name="Canoptek Cloak",             aura_range=6.0, fnp=5,                 host_keys=_NECRON_HOSTS)),
    # Orks — "Might is Right" (Warboss, Warboss In Mega Armour). Real rule:
    # "While this model is leading a unit, each time a model in that unit makes
    # a melee attack, add 1 to the Hit roll." (Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/orks/Warboss )
    # Melee-only: use `plus_one_to_hit_melee_only` so the buff does NOT fire
    # in the Shooting phase. Prior implementation used `plus_one_to_hit=True`
    # which applied to all attack modes — an over-buff vs the codex text.
    # Cited as `WARBOSS.plus_one_to_hit_melee_only`. host_keys cover both
    # Warboss (Boyz / Nobz) and Warboss In Mega Armour (Meganobz).
    ("Warboss",            LeaderAbility(name="Might is Right",             aura_range=6.0, plus_one_to_hit_melee_only=True, host_keys=("orks_boyz", "orks_nobz", "orks_meganobz"))),
    # Tyranids — Hive Tyrant is a Monster with NO formal Leader/Bodyguard
    # attachment in 10e. The codex Onslaught aura reads "While a friendly
    # TYRANIDS unit is within 6" of this model, ranged weapons equipped by
    # models in that unit have the [ASSAULT] and [LETHAL HITS] abilities."
    # — broadcast aura with no led-unit gate. Use the iter22 empty-tuple
    # convention.
    #
    # TYRANIDS-DIAG-7 (2026-05-26): dropped `reroll_wound_ones=True` proxy.
    # The prior proxy was wrong in two ways:
    #   1. The real Onslaught rule grants [LETHAL HITS] on RANGED weapons
    #      only. `reroll_wound_ones` fires on both ranged AND melee attacks
    #      inside `effective_buffs` — over-buff on every melee attack.
    #   2. Re-roll wound 1s is the wrong mechanic: the real effect is
    #      [LETHAL HITS] (natural 6 to hit = auto-wound on ranged) + [ASSAULT]
    #      (shoot after Advancing). The `transient_lethal_hits` flag exists
    #      in the simulator but the `LeaderAbility` schema has no ranged-only
    #      lethal-hits field. Wiring it army-wide would re-introduce the
    #      ranged+melee over-buff in a different form.
    # Ship NO-FLAG + composition-only (same pattern as Avatar of Khaine /
    # Autarch / Custodes Blade Champion). Will return as
    # `lethal_hits_ranged=True` once the LeaderAbility schema gains a
    # ranged-only lethal-hits slot.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/Hive-Tyrant
    ("Hive Tyrant",        LeaderAbility(name="Synaptic Imperative",        aura_range=6.0)),
    # Aeldari
    # Yvraine (Ynnari EPIC HERO) — Herald of Ynnead grants Aeldari-friendly
    # re-roll of Wound rolls of 1 vs a fight-phase-marked target (we proxy
    # as an always-on reroll-wound-1s aura); Word of the Phoenix (Psychic)
    # revives D3+1 destroyed Bodyguard models in the led unit each Command
    # phase on a 2+ — wired via revive_destroyed_per_round=2 (median D3+1=3
    # models per fire, ~83% fire rate on 2+ → effective ~2.5/round; we
    # round down to 2 to stay conservative). Leader-attaches to Asuryani or
    # Ynnari Aeldari battleline; we list Guardian Defenders as the closest
    # in-catalogue host. EPIC HERO so the 1-per-army cap applies. Cited as
    # LeaderAbility."Word of the Phoenix" in data/rule_citations.d/leaders.json.
    # iter17 — revive_destroyed_per_round dropped from 2 -> 1 after the
    # archetype eval showed Aeldari at sim 55.6% vs real 44.4% (+11.2pt
    # over). The codex Word of the Phoenix returns D3+1 (median 3) on a
    # 2+ — effective ~2.5 models/round in the codex; iter15 modelled this
    # as 2 to stay conservative. The simulator's apply_round_end_revival
    # fires unconditionally each round whether or not a Bodyguard model
    # actually died — the codex would no-op on a round where Yvraine's
    # unit took zero casualties. Scaling to 1/round better matches an
    # "average 1 model dies per round on the Yvraine-led unit * D3+1
    # median heal * 2+ success rate" expectation. Yvraine remains in the
    # leader registry but is NOT in the Aeldari archetype template — she
    # gets picked up if an explicit caller seeds her, or if she lands via
    # build_faction_random_army when faction == "Ynnari".
    ("Yvraine",            LeaderAbility(name="Word of the Phoenix",        aura_range=6.0, reroll_wound_ones=True, revive_destroyed_per_round=1,
                                          host_keys=_AELDARI_GUARDIAN_HOSTS)),
    # The Yncarne (Ynnari EPIC HERO, MONSTER) — Ethereal Form (Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/aeldari/The-Yncarne):
    # "Each time this model destroys an enemy unit it regains up to D3
    # lost wounds."
    # Trigger: THIS model (the Yncarne) is the killer. NOT battlefield-wide.
    # Effect: roll 1D3, restore that many lost wounds capped at starting wounds.
    # Implemented via `maybe_apply_yncarne_heal` called from each kill site in
    # simulator.py (shooting, melee, Tank Shock, Counter-Offensive), mirroring
    # the Celestine Miraculous Intervention pattern. `heal_d3_on_kill=True`
    # signals the hook; `heal_per_round` is NOT set (the old unconditional
    # round-end drip was an approximation removed here).
    #
    # History of approximations now retired:
    #   iter15: heal_per_round=2 (D3 median proxy, round-end unconditional).
    #   iter17: Yvraine dropped from archetype; heal_per_round left at 2.
    #   iter21: plus_one_to_hit=True dropped (no codex basis).
    #   AELDARI-DIAG-3 (2026-05-24): heal_per_round cut from 2 to 1.
    #   wave 241 (this commit): heal_per_round removed; heal_d3_on_kill=True
    #     wires the faithful on-kill D3 heal.
    #
    # Inevitable Death (reactive teleport on Aeldari unit death) is NOT
    # modelled — the simulator has no reactive-relocation hook.
    # Yncarne is a Monster — no formal leader attachment (host_keys empty).
    # Cited as LeaderAbility."Ethereal Form".
    ("The Yncarne",        LeaderAbility(name="Ethereal Form",              aura_range=6.0, heal_d3_on_kill=True)),
    # Farseer — Branching Fates (Psychic) is a once-per-phase set-one-roll-
    # to-6 ability (Wahapedia: "While this model is leading a unit, once per
    # phase, you can change the result of one Hit roll, one Wound roll or one
    # Damage roll made for a model in that unit (excluding SUPPORT WEAPON
    # models) to an unmodified 6." BSData v10.6.0, Aeldari - Aeldari
    # Library.cat.gz, ability id 1db8-859e-c4c7-d8b2). The simulator has no
    # once-per-phase set-roll-to-6 leader hook — the prior reroll_wound_ones=True
    # flag was a loose stand-in with no codex support for an always-on aura.
    # wave 236 drops the proxy (same standard as Autarch iter21 / Avatar iter21
    # / Necron Overlord iter20). Registry entry retained (host_keys kept for
    # is_actually_led gating). Will return as a once-per-phase set-to-6
    # modifier once the leader-hook layer gains that capability.
    ("Farseer",            LeaderAbility(name="Runes of Fate",              aura_range=6.0,                          host_keys=_AELDARI_GUARDIAN_HOSTS)),
    # Autarch — Path of Command is a once-per-round Stratagem CP-discount
    # ability, IDENTICAL in pattern to Necron Overlord "My Will Be Done"
    # (which iter20 audited and dropped the +1-to-hit proxy from). iter21
    # drops Autarch's +1-to-hit aura on the same grounds: the codex rule
    # is a CP-economy effect with no permanent aura buff; the simulator
    # does not model per-character Stratagem CP discounts. Entry kept in
    # the registry (with host_keys retained for is_actually_led gating
    # purposes), but no offensive flag — matches the iter20 fab-removal
    # standard.
    ("Autarch",            LeaderAbility(name="Path of Command",            aura_range=6.0,                          host_keys=_AELDARI_GUARDIAN_HOSTS)),
    # Avatar of Khaine — Bloody-Handed is "+1 to Advance and Charge rolls"
    # for nearby AELDARI: a MOVEMENT-phase buff. The reroll_hit_ones aura
    # was a known wrong-buff-type stand-in (citation explicitly admitted
    # "Known limitation: wrong buff TYPE — direction-correct but
    # mechanically unrelated"). iter21 fab audit drops the reroll proxy
    # rather than continue routing a movement rule through the hit-roll
    # layer. Entry kept (Monster, no host_keys); will return as a charge-
    # roll modifier once the charge resolver gains a leader-buff hook.
    ("Avatar of Khaine",   LeaderAbility(name="Avatar's Fury",              aura_range=6.0)),  # Monster, no formal host
    # T'au Empire
    ("Ethereal",           LeaderAbility(name="Failure Is Not an Option",   aura_range=6.0, fnp=5,                  host_keys=_TAU_FIRE_HOSTS)),
    # Battlesuit Commander (Coldstar / Crisis / Enforcer); leads CRISIS Battlesuits,
    # no INFANTRY host. Faithful default = no offensive buff (real rule is [ASSAULT]
    # + Move 12" to the led unit, both unmodelled); SWEG_TAU_CMD=0 reverts to the
    # prior fabricated army-wide +1-to-hit proxy. See _TAU_CMD_FIX above.
    ("Commander in",       LeaderAbility(name="Coordinated Fire Plan",      aura_range=6.0)
                           if _TAU_CMD_FIX else
                           LeaderAbility(name="Coordinated Fire Plan",      aura_range=6.0, plus_one_to_hit=True)),
    ("Cadre Fireblade",    LeaderAbility(name="Volley Fire",                aura_range=6.0, plus_one_attack=1,      host_keys=_TAU_FIRE_HOSTS)),
    # Thousand Sons — character LeaderAbility entries (iter21 fix).
    # TSON characters were previously unwired: Ahriman / Infernal Master
    # / Exalted Sorcerer / Magnus all returned None from lookup_ability,
    # so the led Rubric Marines / Scarab Occult Terminators squads
    # received NO aura buff. Wahapedia datasheets for each are linked in
    # data/rule_citations.d/leaders.json. Listed BEFORE the generic
    # CSM "Sorcerer" entry so unique TSON keys win the substring match.
    # "Exalted Sorcerer" and "Infernal Master" are unique to TSON.
    # "Ahriman" is also unique.
    #
    # Sources:
    #   - Ahriman: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/#Ahriman
    #     Real ability: "Master of the Rubricae (Psychic)" — while this model
    #     leads a Rubric Marines or Scarab Occult Terminators unit, each time a
    #     Psychic Attack made by a model in that unit targets an enemy unit, you
    #     can re-roll the Hit roll. This is an OFFENSIVE hit-reroll (Psychic
    #     weapons only), not a defensive invuln. TSON-DIAG-3 fix: the previous
    #     proxy (extra_invuln=4) was a fabrication — it applied a 4++ invuln
    #     save to Ahriman's led unit, which is Arcane Shield (Exalted Sorcerer
    #     only). Ahriman's real contribution is offensive (hit re-rolls), not
    #     defensive. Removing extra_invuln=4 and replacing with reroll_hit_ones
    #     correctly models his offensive buff direction (approximation: the
    #     re-roll applies to all hit rolls, not just Psychic Attacks, due to
    #     SwegHammer not tagging weapons as Psychic vs non-Psychic).
    #   - Exalted Sorcerer / Sorcerer: Arcane Shield (Psychic) grants the
    #     led unit a 4+ invulnerable save. Modelled as extra_invuln=4.
    #   - Infernal Master: Malefic Maelstrom (Psychic) grants the led
    #     unit [SUSTAINED HITS 1]. Modelled as sustained_hits proxy via
    #     reroll_hit_ones_shooting_only (an offensive Shooting-phase buff).
    #     TSON-AURA-V2 (iter60): narrowed from reroll_hit_ones (all phases)
    #     to reroll_hit_ones_shooting_only for both Ahriman and Infernal Master.
    #     Ahriman's codex rule is explicitly "Psychic Attack" and "targets an
    #     enemy unit" — Psychic Attacks are ranged-only in 10e; melee Rubric
    #     Marine attacks carry no Psychic keyword. Infernal Master's Malefic
    #     Maelstrom grant is weapons-wide, but the proxy direction (re-roll
    #     1s) is most defensible on Shooting where Rubric Marines deal the
    #     bulk of their damage. Narrowing to Shooting removes the melee-leak
    #     that inflated TSON sim win-rates beyond the Warp Friends target.
    ("Ahriman",            LeaderAbility(name="Arch-Sorcerer of Tzeentch",  aura_range=6.0, reroll_hit_ones_shooting_only=True,
                                          host_keys=("thousand_sons_rubric_marines",
                                                     "thousand_sons_tzaangor_enlightened"))),
    ("Exalted Sorcerer",   LeaderAbility(name="Arcane Shield",              aura_range=6.0, extra_invuln=4,
                                          host_keys=("thousand_sons_rubric_marines",))),
    ("Infernal Master",    LeaderAbility(name="Malefic Maelstrom",          aura_range=6.0, reroll_hit_ones_shooting_only=True,
                                          host_keys=("thousand_sons_rubric_marines",))),
    # Magnus the Red — EPIC HERO MONSTER PSYKER, NOT a CHARACTER leader-
    # attachment. Magnus does not formally lead a unit and does not confer
    # an aura buff to nearby Thousand Sons units (per Wahapedia datasheet
    # https://wahapedia.ru/wh40k10ed/factions/thousand-sons/#Magnus-the-Red).
    # His self-conferred rules are already wired elsewhere:
    #   - Impossible Form (-1 to incoming Damage): code/simulator.py:4063-4066
    #   - Lord of the Planet of the Sorcerers (2 Rituals/turn +2 to Psychic
    #     test): code/simulator.py:3142-3148
    # This registry entry exists ONLY so `lookup_ability("Magnus the Red")`
    # returns a non-None LeaderAbility per CLAUDE.md §13 (no silent
    # defaults). No buff flags, no host_keys — empty host_keys=() follows
    # the iter22 "army-wide / no host gate" convention used for Monster
    # leaders like Avatar of Khaine (line 308 above) that don't formally
    # attach. iter21's commit comment had claimed Magnus was added but
    # he was in fact skipped from the registry tuple; iter24 closes that
    # silent-default gap. If a future codex revision confers an aura buff
    # to nearby PSYKERs, encode it here and add the matching
    # LeaderAbility.Magnus the Red citation.
    ("Magnus the Red",     LeaderAbility(name="Magnus the Red",              aura_range=0.0,                          host_keys=())),
    # Sorcerer in Terminator Armour — TSON variant. Leader-attaches to
    # Scarab Occult Terminators (per BSData v10.6.0 Leader infoLink).
    # Datasheet ability "Marked by Fate (Psychic)" grants +1 to Hit on
    # the Sorcerer's chosen target unit each Shooting phase — quoted
    # Wahapedia: "At the start of your Shooting phase, select one enemy
    # unit that is visible to this PSYKER model. Until the end of the
    # phase, each time a model in this unit makes an attack that targets
    # that enemy unit, add 1 to the Hit roll."
    #
    # TSON-KOS-MESMERISING (wave-44): the prior proxy was
    # `plus_one_to_hit=True`, which fires army-wide AND in BOTH the
    # Shooting and Fight phases. That is a strict over-buff in three
    # dimensions vs codex:
    #   1. codex is shooting-only; +1-to-hit fires in melee too,
    #   2. codex is per-Shooting-phase one-target; +1-to-hit applies to
    #      every shooting target every round,
    #   3. codex is per-chosen-unit; +1-to-hit applies to every enemy.
    # Combined this is ~2x the codex magnitude on the Scarab Occult
    # Terminators (the host unit) — a marquee elite squad whose entire
    # role rests on its shooting + melee weight of attacks. The current
    # +1-to-hit proxy is a leading contributor to the +12-pt TSON sim
    # over-shoot vs the Warp Friends real meta (sim 71.5%, real 54.6%
    # at wave-43 baseline).
    #
    # Wave-44 fix: replace plus_one_to_hit with reroll_hit_ones — the
    # same proxy convention used for Ahriman's Master of the Rubricae
    # (Psychic) hit-reroll (TSON-DIAG-3) and Infernal Master's Malefic
    # Maelstrom [SUSTAINED HITS 1] proxy. Magnitude drops from a full
    # +1-to-hit modifier (~+1/3 to +1/2 of all hit rolls) to a single
    # 1-rerolled hit-roll-of-1 (~+1/6 of all hit rolls), strictly
    # narrower than the codex single-target per-phase +1-to-hit, but the
    # smallest credible shrinkage given the absence of per-target
    # hit-modifier plumbing. Listed BEFORE the generic CSM "Sorcerer"
    # entry so this longer key wins lookup. Wahapedia source:
    # https://wahapedia.ru/wh40k10ed/factions/thousand-sons/Sorcerer-In-Terminator-Armour
    # TSON-AURA-V2 (iter60): narrowed from reroll_hit_ones (all phases) to
    # reroll_hit_ones_shooting_only. The codex explicitly says "Until the
    # end of the [Shooting] phase" — melee attacks by Scarab Occult
    # Terminators must receive no re-roll from this ability. The prior
    # all-phases flag incorrectly boosted melee hit rolls on a unit that
    # does significant melee damage with Force Staves and Inferno combi-bolters.
    ("Sorcerer in Terminator Armour", LeaderAbility(name="Marked by Fate",   aura_range=6.0, reroll_hit_ones_shooting_only=True,
                                          host_keys=("thousand_sons_scarab_occult_terminators",))),
    # Chaos Space Marines (legacy "Chaos Space Marines squad" not in 10e BSData;
    # use the closest battleline that is, otherwise let the heuristic decide.)
    ("Sorcerer",           LeaderAbility(name="Prescience",                 aura_range=6.0, fnp=5,
                                          host_keys=_CSM_SORCERER_HOSTS)),
    # Dark Apostle: the real 10e ability is "Dark Zealotry" — "+1 to the Wound
    # roll" on melee attacks while a Dark Apostle model is leading the unit.
    # BSData v10.6.0 (Chaos - Chaos Space Marines.cat.gz, ability id
    # da55-1d58-dee4-d42): "While this unit is leading a unit and contains a
    # DARK APOSTLE model, each time a model in that unit makes a melee attack,
    # add 1 to the Wound roll."
    # Both the proxy (reroll_hit_ones) and the faithful field
    # (plus_one_to_wound_melee_only) are always present. The gate
    # SWEG_CSM_ABILITIES controls which fires at the consumption sites:
    #   OFF (default): reroll_hit_ones fires in effective_buffs (the prior proxy);
    #     plus_one_to_wound_melee_only is suppressed in units.py (already gated).
    #   ON: plus_one_to_wound_melee_only fires in units.py; reroll_hit_ones is
    #     suppressed in effective_buffs via the _csm_gate_suppress block below.
    # Cited as `simulator.dark_apostle_dark_zealotry`.
    ("Dark Apostle",       LeaderAbility(name="Dark Zealotry",              aura_range=6.0,
                                          reroll_hit_ones=True,
                                          plus_one_to_wound_melee_only=True,
                                          host_keys=_CSM_APOSTLE_HOSTS)),
    # Master of Possession — PSYKER CHARACTER, leads CHOSEN / LEGIONARIES /
    # POSSESSED (BSData v10.6.0, Chaos - Chaos Space Marines.cat.gz, profile id
    # 287f-7d48-59cf-dc1e, Leader ability id 638e-667a-a1c5-1135).
    # Datasheet abilities:
    #   "Daemonkin (Psychic)": "While this model is leading a unit, add 1 to
    #   Advance and Charge rolls made for that unit." — a Movement-phase roll
    #   modifier. The simulator has no Advance/Charge roll leader-aura hook;
    #   parking-lot until a charge-roll modifier is added to LeaderAbility.
    #   "Sacrificial Dagger": "Once per phase, when this model is selected to
    #   shoot or fight, it can use this ability. If it does, this model's unit
    #   suffers 1 mortal wound and, until the end of the phase, each time this
    #   model makes a Psychic Attack, add 1 to the Hit roll and add 1 to the
    #   Wound roll." — a self-activation once-per-phase mortal-wound trade
    #   (affects only the Master of Possession's own Psychic Attacks, not the
    #   whole led unit). The simulator has no once-per-phase self-activation
    #   leader hook; parking-lot.
    # No currently-expressible led-unit aura flags. Entry exists so
    # lookup_ability("Master of Possession") returns non-None per CLAUDE.md §13.
    # Cited as LeaderAbility.Daemonkin (Psychic).
    # BSData sole source per project memory (wahapedia.ru DNS may fail in agents).
    ("Master of Possession", LeaderAbility(name="Daemonkin (Psychic)",          aura_range=6.0,
                                          host_keys=("chaos_space_marines_chosen",
                                                     "chaos_space_marines_legionaries",
                                                     "chaos_space_marines_possessed"))),
    # Warpsmith — INFANTRY CHARACTER, leads CHOSEN / HAVOCS / LEGIONARIES
    # (BSData v10.6.0, Chaos - Chaos Space Marines.cat.gz, profile id
    # 440-a22a-eac1-b107, Leader ability id b5da-4ab-cfb5-4e4c).
    # Datasheet abilities:
    #   "Warpsmith" (Lone Operative): "While this model is within 3\" of one or
    #   more friendly HERETIC ASTARTES VEHICLE units, this model has the Lone
    #   Operative ability." — a self-defence ability on the Warpsmith; does not
    #   affect the led unit.
    #   "Master of Mechanisms": "In your Command phase, select one friendly
    #   HERETIC ASTARTES VEHICLE model within 3\" of this model. That VEHICLE
    #   model regains up to D3 lost wounds and, until the start of your next
    #   Command phase, each time that VEHICLE makes an attack, add 1 to the Hit
    #   roll." — a Command-phase heal + Hit buff on a VEHICLE model, not a
    #   led-unit aura. The simulator has no per-leader Command-phase vehicle
    #   repair hook; parking-lot.
    #   "Enrage Machine Spirits": "At the end of your Movement phase, select one
    #   enemy VEHICLE unit within 12\" of this model. That unit must take a
    #   Battle-shock test." — an enemy debuff applied in the Movement phase.
    #   The simulator does not model per-leader Battle-shock triggers; parking-lot.
    # No currently-expressible led-unit aura flags. Entry exists so
    # lookup_ability("Warpsmith") returns non-None per CLAUDE.md §13.
    # Cited as LeaderAbility.Master of Mechanisms.
    # BSData sole source per project memory (wahapedia.ru DNS may fail in agents).
    ("Warpsmith",            LeaderAbility(name="Master of Mechanisms",          aura_range=6.0,
                                          host_keys=("chaos_space_marines_chosen",
                                                     "chaos_space_marines_havocs",
                                                     "chaos_space_marines_legionaries"))),
    # Dark Commune — INFANTRY CHARACTER UNIT (contains a Cult Demagogue model),
    # leads ACCURSED CULTISTS / CULTIST MOB (BSData v10.6.0, Chaos - Chaos Space
    # Marines.cat.gz, profile id 1780-25b8-ce0b-898d, Leader ability id
    # 98b1-c4d2-400d-f8c7).
    # Datasheet abilities:
    #   "Faithful Flock": "While this unit is leading a unit and contains a CULT
    #   DEMAGOGUE model, models in that unit have a 5+ invulnerable save."
    #   The Dark Commune always contains a Cult Demagogue (the Cult Demagogue
    #   is one of its constituent models per the unit datasheet), so the
    #   condition "contains a CULT DEMAGOGUE model" is always true while the
    #   Dark Commune is intact. Modelled as extra_invuln=5.
    #   "Dark Ritual": "Once per battle, in your Command phase, if this unit
    #   contains a CULT DEMAGOGUE model, it can use this ability. If it does,
    #   until the end of the turn, this unit can declare a charge in a turn in
    #   which it Advanced and each time a model in this unit makes an attack,
    #   add 1 to the Hit roll and add 1 to the Wound roll." — a once-per-battle
    #   self-activation on the Dark Commune's own attacks, not a persistent led-
    #   unit aura. Parking-lot until a once-per-battle Command-phase trigger hook
    #   lands in the leader layer.
    # Cited as LeaderAbility.Faithful Flock.
    # BSData sole source per project memory (wahapedia.ru DNS may fail in agents).
    ("Dark Commune",         LeaderAbility(name="Faithful Flock",                aura_range=6.0,
                                          extra_invuln=5,
                                          host_keys=("chaos_space_marines_accursed_cultists",
                                                     "chaos_space_marines_cultist_mob"))),
    # Chaos Lord — Lord of Chaos is a once-per-battle-round Stratagem
    # command-point-discount ability (Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/Chaos-Lord;
    # BSData v10.6.0, Chaos - Chaos Space Marines.cat.gz, ability id
    # 73e9-284e-fd62-4056: "Once per battle round, one unit from your army
    # with this ability can use it when its unit is targeted with a Stratagem.
    # If it does, reduce the CP cost of that use of that Stratagem by 1CP.").
    # There is NO offensive aura component — plus_one_to_wound=True was a
    # flavour proxy with no codex support (two-source fabrication verified,
    # docs/STRUCTURAL_DEBT_REVIEW.md surface 2 line 104). wave 236 drops the
    # proxy on the same standard as Autarch "Path of Command" (iter21) and
    # Shield-Captain "Master of the Stances" (CUSTODES-AUDIT). Entry retained
    # with corrected host_keys (BSData Leader text: "CHOSEN / LEGIONARIES").
    # Note: this flag fires on near-dormant units (prior host was
    # chaos_space_marines_traitor_guardsmen_squad, absent from archetype
    # lists), so the metric impact is near-neutral — this is a fidelity
    # correction, not a metric knob. Will return as a Stratagem CP-discount
    # once per-character command-point-reduction hooks are added.
    ("Chaos Lord",         LeaderAbility(name="Lord of Hosts",              aura_range=6.0,
                                          host_keys=("chaos_space_marines_legionaries",
                                                     "chaos_space_marines_chosen"))),
    # Abaddon the Despoiler: the Warmaster ability "Paragon of Hatred" (Aura)
    # is the competitively dominant pick. BSData v10.6.0 (Chaos - Chaos Space
    # Marines.cat.gz, ability id 8b8a-6967-9f60-3de0, typeName "Warmaster"):
    # "While a friendly HERETIC ASTARTES unit (excluding DAMNED units) is within
    # 6\" of this model, each time a model in that unit makes an attack, you can
    # re-roll the Hit roll."
    # This is an army-wide broadcast aura (host_keys=() = no attachment gate):
    # the codex text reads "While a friendly ... unit is within 6\"", NOT "While
    # this model is leading a unit". Effect is GATED in effective_buffs via
    # _csm_gate_suppress: fires only when SWEG_CSM_ABILITIES=1.
    # Cited as `simulator.abaddon_paragon_of_hatred`.
    ("Abaddon the Despoiler",
                           LeaderAbility(name="Paragon of Hatred",          aura_range=6.0,
                                          reroll_hit_ones=True,
                                          host_keys=())),
    # Chaos Daemons heralds (MR-CHAOS-DAEMONS-LOCUS, claude/sim-calibration-6).
    # The four single-god Heralds were previously absent from this registry,
    # which meant every Bloodletters / Plaguebearers / Pink Horrors / Daemonettes
    # battleline squad in the Daemonic Incursion archetype seed fought without
    # its god's locus aura. Each entry's quoted_text is verbatim from the
    # BSData v10.6.0 datasheet (Chaos - Chaos Daemons Library.cat.gz). Citations:
    # data/rule_citations.d/leaders.json (LeaderAbility.Bloodmaster's Locus / ...).
    # Source (Wahapedia, fallback per CLAUDE.md §6):
    #   https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/
    ("Bloodmaster",        LeaderAbility(name="Bloodmaster's Locus",        aura_range=6.0, plus_one_to_wound=True,
                                          host_keys=("chaos_daemons_library_bloodletters",))),
    # Poxbringer — codex ability is "successful unmodified Hit roll of 5+
    # scores a Critical Hit" on the led Plaguebearers. SwegHammer does not
    # currently expose a per-unit-led 5+-crit-hit flag (crit-on-5+ is a weapon
    # ability tracked on profile, not a leader-grantable aura). The
    # Plaguebearers' melee profile already carries [LETHAL HITS] on a 6, so
    # the codex rule effectively expands lethals from 1/6 -> 2/6 of hits. The
    # closest aura-flag proxy is `plus_one_to_wound=True` for the melee swarm
    # (loose but direction-correct: more wounds get through). This proxy is
    # called out as "(approximation)" in the citation. Plus the Feculent
    # Despair aura is a -1 enemy battle-shock test which we don't currently
    # gate per-leader, so it is skipped.
    ("Poxbringer",         LeaderAbility(name="Poxbringer's Locus",         aura_range=6.0, plus_one_to_wound=True,
                                          host_keys=("chaos_daemons_library_plaguebearers",))),
    # Changecaster — codex ability grants [SUSTAINED HITS 1] to ranged weapons
    # on the led unit. BSData v10.6.0 Chaos - Chaos Daemons Library.cat.gz:
    # "While this model is leading a unit, ranged weapons equipped by models
    # in that unit have the [SUSTAINED HITS 1] ability." Leader attachment:
    # "PINK HORRORS, BLUE HORRORS" (both are separate UNIT_CATALOG keys —
    # chaos_daemons_library_pink_horrors and chaos_daemons_library_blue_horrors,
    # confirmed via UNIT_CATALOG inspection). DAEMONS-LOCUS-V1 added Blue
    # Horrors to host_keys (prior entry's claim that they didn't surface as a
    # separate catalog key was factually wrong). LEADERABILITY-SUSTAINED-HITS
    # (this wave): the prior `reroll_hit_ones=True` proxy is replaced with the
    # rule-correct `sustained_hits_ranged=1` field now that the LeaderAbility
    # schema carries it. Same direction (+1/6 hits per shot) but exact codex
    # fidelity; the SUSTAINED HITS extra-hit accumulator in Unit.attack also
    # composes correctly with detachment / stratagem / per-weapon
    # SUSTAINED HITS sources whereas the reroll_hit_ones proxy did not.
    ("Changecaster",       LeaderAbility(name="Changecaster's Locus",       aura_range=6.0,
                                          sustained_hits_ranged=1,
                                          host_keys=("chaos_daemons_library_pink_horrors",
                                                     "chaos_daemons_library_blue_horrors",))),
    # Contorted Epitome — Swallow Energy (Psychic) grants the led Daemonettes
    # FNP 4+ vs mortal wounds and Psychic Attacks. SwegHammer does not tag
    # attacks as PSYCHIC, so FNP 4 is applied army-wide (per the iter15
    # Librarian pattern: defensive proxy, strictly stronger than the codex's
    # restricted-trigger 4+ FNP). Horrible Fascination is a once-per-game
    # opponent-Shooting-phase ritual with no aura-flag plumbing; skipped.
    ("Contorted Epitome",  LeaderAbility(name="Swallow Energy",             aura_range=6.0, fnp=4,
                                          host_keys=("chaos_daemons_library_daemonettes",))),
    # Spoilpox Scrivener — "Keep Counting!" grants melee [SUSTAINED HITS 1]
    # to the led Plaguebearers. BSData v10.6.0 Chaos - Chaos Daemons
    # Library.cat.gz verbatim: "While this model is leading a unit, melee
    # weapons equipped by models in that unit have the [SUSTAINED HITS 1]
    # ability." Leader attachment: PLAGUE BEARERS. Schema field
    # `sustained_hits_melee` added in wave-50 commit `25af977`
    # (LEADERABILITY-SUSTAINED-HITS) precisely so this leader could be
    # added without a follow-up dataclass change. Second BSData ability
    # "Meet Your Quota!" (+1 OC to the led unit) is parking-lot: no
    # `oc_bonus_led_unit` field exists in LeaderAbility yet.
    ("Spoilpox Scrivener", LeaderAbility(name="Keep Counting!",             aura_range=6.0,
                                          sustained_hits_melee=1,
                                          host_keys=("chaos_daemons_library_plaguebearers",))),
    # Tormentbringer — Aura (NOT led-unit gated) grants melee [SUSTAINED
    # HITS 1] to any friendly SLAANESH LEGIONES DAEMONICA within 6". BSData
    # v10.6.0: "While a friendly Slaanesh Legions Daemonica unit is within
    # 6\" of this model, melee weapons in that unit have the [SUSTAINED
    # HITS 1] ability." `host_keys` is the full _SLAANESH_DAEMON_HOSTS
    # tuple — this is an army-aura within the Slaanesh sub-faction, NOT
    # a Leader/Bodyguard buff. Empty `host_keys=()` would broadcast to
    # ALL friendlies (including non-Slaanesh allies via Daemons of Chaos
    # detachment composition), which is wrong. Tormentbringer's other
    # ability "Hysterical Frenzy" (destroyed model fights after) requires
    # a fight-phase-trigger flag that doesn't exist; parking-lot.
    ("Tormentbringer",     LeaderAbility(name="Tormentbringer (Aura)",      aura_range=6.0,
                                          sustained_hits_melee=1,
                                          host_keys=_SLAANESH_DAEMON_HOSTS)),
    # Chaos Daemons Greater Daemons — per-god aura carriers. Bloodthirster
    # and Skarbrand (DAEMONS-DIAG-3, claude/sim-calibration-6) wire Khorne;
    # LEADERABILITY-SCHEMA (this iteration) extends to the three remaining
    # gods (Lord of Change / Great Unclean One / Keeper of Secrets) now that
    # LeaderAbility carries `plus_one_strength_ranged`, `plus_one_toughness`,
    # and `plus_one_ap_melee`. Each Greater Daemon broadcasts a 6" aura to
    # friendly <god> Legiones Daemonica units; host_keys narrows the buff
    # to that god's catalogue roster. Citations verbatim from BSData v10.6.0
    # Chaos - Chaos Daemons Library.cat.gz in
    # data/rule_citations.d/leaders.json. Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Bloodthirster
    # https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Skarbrand
    # https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Lord-of-Change
    # https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Great-Unclean-One
    # https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Keeper-of-Secrets
    ("Bloodthirster",      LeaderAbility(name="Daemon Lord of Khorne",      aura_range=6.0, plus_one_to_hit_melee_only=True,
                                          host_keys=_KHORNE_DAEMON_HOSTS)),
    ("Skarbrand",          LeaderAbility(name="Rage Embodied",              aura_range=6.0, plus_one_attack=1,
                                          host_keys=_KHORNE_DAEMON_HOSTS)),
    # Skulltaker — "Lord of Decapitations" grants [DEVASTATING WOUNDS] to
    # melee weapons equipped by the led unit. BSData v10.6.0 Chaos - Chaos
    # Daemons Library.cat.gz, Lord of Decapitations ability: "While this
    # model is leading a unit, melee weapons equipped by models in that unit
    # have the [DEVASTATING WOUNDS] ability." Host: BLOODLETTERS only (BSData
    # Leader profile: "This model can be attached to the following unit:
    # BLOODLETTERS"). Modelled as `grants_devastating_wounds_melee=True`; the
    # melee-only gate is enforced in the attack-resolution loop in
    # code/units.py (fires only when mode == "melee").
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Skulltaker
    ("Skulltaker",         LeaderAbility(name="Lord of Decapitations",       aura_range=6.0,
                                          grants_devastating_wounds_melee=True,
                                          host_keys=("chaos_daemons_library_bloodletters",))),
    # Daemon Prince of Chaos — "Prince of Darkness" (Aura). Verbatim from
    # Wahapedia (https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/Daemon-Prince-of-Chaos):
    # "While a friendly LEGIONES DAEMONICA unit is within 6\" of this model,
    # models in that unit have the Stealth ability."
    # 10e Stealth rule (core rules, Wahapedia): "each time a ranged attack is
    # made against it, subtract 1 from that attack's Hit roll."
    # This is a DEFENDER-side buff: when the enemy targets a Daemon unit within
    # 6\" of a friendly Daemon Prince, the attacker's Hit roll takes -1 in the
    # Shooting phase. Modelled as grants_stealth_aura=True; the -1 modifier is
    # applied in code/units.py at the hit-roll computation (defender side, mode
    # != "melee" gate, reads tgt_buffs["grants_stealth_aura"]). Melee is
    # unaffected — Stealth is a ranged defence per the 10e core rules.
    # host_keys = _LEGIONES_DAEMONICA_HOSTS (all Legiones Daemonica units in
    # BSData v10.6.0; see DAEMONS-DIAG-9 comment above _REGISTRY). Empty
    # host_keys would broadcast to ALL friendly units including non-Daemon
    # allies — the codex wording restricts to LEGIONES DAEMONICA, so
    # non-empty host_keys is the correct gate. Daemon Prince is a MONSTER;
    # no formal Leader/Bodyguard attachment. The DAEMONS archetype seeds it
    # in all four Daemonic Incursion lists (Khorne Murderhost, Tzeentch
    # Manifestation, Nurgle Pestilence, Slaanesh Excess), so the aura fires
    # on every Daemon archetype eval run.
    # Cited as LeaderAbility.Prince of Darkness in
    # data/rule_citations.d/leaders.json.
    ("Daemon Prince of Chaos", LeaderAbility(name="Prince of Darkness",      aura_range=6.0,
                                          grants_stealth_aura=True,
                                          host_keys=_LEGIONES_DAEMONICA_HOSTS)),
    # Only the GENERIC Greater Daemon datasheets (Lord of Change, Great
    # Unclean One, Keeper of Secrets) carry the "Daemon Lord of <god>" Locus
    # aura per BSData v10.6.0 cache. The named variants (Kairos Fateweaver,
    # Rotigus, Shalaxi Helbane) are separate datasheets with their own
    # bespoke datasheet abilities (Kairos: CP-stealing stratagem-cost gate,
    # Rotigus: damage uplift on a chosen target + enemy debuff aura,
    # Shalaxi: Monster-hunter melee uplift) and explicitly DO NOT inherit
    # the Locus aura. They are intentionally not wired here per CLAUDE.md
    # §10 "cite every rule, don't invent". Skarbrand is the only named
    # variant that broadcasts a Locus-equivalent — its "Rage Embodied"
    # aura is wired above with the codex-correct +1 Attacks effect, not
    # the Khorne Locus +1-to-hit (those are two separate auras on the
    # same datasheet per BSData and Wahapedia).
    ("Lord of Change",     LeaderAbility(name="Daemon Lord of Tzeentch",    aura_range=6.0, plus_one_strength_ranged=True,
                                          host_keys=_TZEENTCH_DAEMON_HOSTS)),
    ("Great Unclean One",  LeaderAbility(name="Daemon Lord of Nurgle",      aura_range=6.0, plus_one_toughness=True,
                                          host_keys=_NURGLE_DAEMON_HOSTS)),
    ("Keeper of Secrets",  LeaderAbility(name="Daemon Lord of Slaanesh",    aura_range=6.0, plus_one_ap_melee=True,
                                          host_keys=_SLAANESH_DAEMON_HOSTS)),
    # Adeptus Custodes — Shield-Captain pinned to the registry head above
    # to prevent substring-collision with the generic Marines "Captain"
    # entry. Trajann Valoris and Blade Champion live in this per-faction
    # block. Per Wahapedia / BSData v10.6.0, Trajann Valoris and Blade
    # Champion each list Custodian Guard and Custodian Wardens as their
    # only legal Leader hosts — Allarus / Sagittarum / Vertus Praetors are
    # NOT in any Custodes CHARACTER's Leader text (verify via BSData cache
    # `Imperium - Adeptus Custodes.cat.gz`). iter24: Trajann's host_keys
    # widened from Guard-only to (Guard + Wardens), and Blade Champion
    # added as a new structural entry (was returning None from
    # lookup_ability per CLAUDE.md §13 fail-loud rule). The Blade Champion
    # carries no offensive aura field today — its codex abilities are
    # Martial Inspiration (once-per-battle advance + charge in same turn)
    # and Swift Onslaught (re-roll Charge rolls while leading). Neither
    # is currently expressible through the LeaderAbility aura schema; the
    # entry exists so lookup_ability resolves cleanly and so the host-key
    # gate on Resolute Will (Wardens) and similar future buffs can verify
    # "the led unit has a CHARACTER attached". Same iter21 fab-removal
    # standard as Captain / Autarch / Avatar of Khaine.
    # Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/Trajann-Valoris
    # Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/Blade-Champion
    # SC5-3 (claude/sim-calibration-5): drop fabricated `plus_one_to_hit=True`
    # on Trajann's Auric Sage. BSData cache (`Imperium - Adeptus Custodes.cat.gz`,
    # profile "Captain-General") verbatim text: "While this model is leading a
    # unit, each time a model in that unit makes an attack, you can ignore any
    # or all modifiers to that attack's Ballistic Skill or Weapon Skill
    # characteristics and/or all modifiers to the Hit roll." This is a
    # modifier-CANCELLATION ability (negates -1-to-hit auras / Heavy penalties /
    # battle-shock penalties), not a flat +1-to-hit uplift. SwegHammer does not
    # model hit-modifier penalties on the attack side either, so the correct
    # net effect of Captain-General in this sim is approximately zero offensive
    # contribution. The prior `plus_one_to_hit=True` was self-flagged in the
    # leaders.json citation as an "upper-bound flavour proxy" and was stacking
    # on top of BS2+ Custodes (already 5/6 to hit) — a strictly-stronger-than-
    # codex over-modelling that was contributing to the +31pt Custodes outlier
    # vs the May 2026 Warp Friends meta. The entry is retained (with no
    # offensive aura field) so lookup_ability resolves cleanly per CLAUDE.md
    # §13 (fail-loud-on-missing-data) and so host-key gates that require "the
    # led unit has a CHARACTER attached" continue to verify. Same iter21
    # fabrication-removal standard as Blade Champion (line below), Captain,
    # Autarch, Avatar of Khaine. Stage 1 calibration: matches sim to codex.
    ("Trajann Valoris",    LeaderAbility(name="Auric Sage",                 aura_range=6.0,
                                          host_keys=("adeptus_custodes_custodian_guard",
                                                     "adeptus_custodes_custodian_guard_with_adrasite_and_pyrithite_spears",
                                                     "adeptus_custodes_custodian_wardens"))),
    ("Blade Champion",     LeaderAbility(name="Swift Onslaught",            aura_range=6.0,
                                          host_keys=("adeptus_custodes_custodian_guard",
                                                     "adeptus_custodes_custodian_guard_with_adrasite_and_pyrithite_spears",
                                                     "adeptus_custodes_custodian_wardens"))),
    # Adeptus Mechanicus
    # Belisarius Cawl — entry must precede the generic Tech-Priest match so
    # the longer name wins the substring lookup. SUPREME COMMANDER (must be
    # Warlord). Real ability: "Canticles of the Omnissiah" — pick ONE aura per
    # Command phase: (a) Invocation of Machine Vengeance: select ONE enemy unit
    # as Machine Vengeance target, re-roll Hit rolls for friendly AdMech attacks
    # against THAT unit only; (b) Mantra of Discipline: +1 OC + battle-shock
    # bonus; (c) Shroudpsalm: Stealth aura. The offensive Invocation is target-
    # restricted to ONE designated enemy unit per round — the simulator has no
    # per-target designation system, so wiring it as an unconditional aura on
    # host_keys units would over-apply (firing against ALL targets, not one).
    # ADMECH-DIAG-5 (2026-05-26): dropped prior reroll_hit_ones=True proxy.
    # The prior citation incorrectly described Cawl's ability as only a CP gain,
    # missing the Canticles entirely. Correct BSData text: see
    # data/rule_citations.d/cp_discount_hq.json#LeaderAbility.Master of the Forge.
    # cp_refund_per_battle=1 models the Warlord-gated once-per-battle CP gain
    # (also part of Cawl's datasheet, separate from Canticles). Registry entry
    # retained so lookup_ability resolves cleanly per CLAUDE.md §13.
    ("Belisarius Cawl",    LeaderAbility(name="Master of the Forge",        aura_range=6.0,
                                          cp_refund_per_battle=1,
                                          host_keys=("adeptus_mechanicus_skitarii_vanguard",
                                                     "adeptus_mechanicus_skitarii_rangers"))),
    # Tech-Priest Dominus: "Lord of the Machine Cult" (BSData v10.6.0 verbatim):
    # "While this model is leading a unit, models in that unit have the Feel No
    # Pain 5+ ability. If that unit has the ELECTRO-PRIESTS keyword, models in
    # that unit have the Feel No Pain 4+ ability instead."
    # ADMECH-DIAG-3 (2026-05-26): removed fabricated reroll_hit_ones + heal_per_round
    # (no offensive aura in the codex ability; the prior heal_per_round=1 was an
    # unanchored proxy for the Dominus's vehicle-repair flavour). Replaced with
    # fnp=5 matching the verbatim BSData / Wahapedia ability. The ELECTRO-PRIESTS
    # Feel No Pain 4+ branch is not implemented (LeaderAbility has no keyword-conditional
    # fnp field); fnp=5 is the floor for non-ELECTRO-PRIESTS hosts.
    # Full BSData Leader text: Corpuscarii Electro-Priests, Fulgurite Electro-Priests,
    # Kataphron Breachers, Kataphron Destroyers, Skitarii Rangers, Skitarii Vanguard.
    # ADMECH-DIAG-4 (2026-05-26): APPROXIMATION — Kataphron Breachers and Destroyers
    # removed from host_keys for calibration. The SwegHammer proximity-broadcast model
    # (any eligible unit within aura_range receives the buff) does not model the 10e
    # one-attachment-per-unit rule. With the full 6-unit list, both Belisarius Cawl
    # (host_keys: Rangers, Vanguard) and the Dominus broadcast to overlapping units
    # simultaneously: Rangers + Vanguard get Feel No Pain 5+ from Dominus AND
    # reroll_hit_ones from Cawl at the same time, while Kataphron Breachers and
    # Destroyers (native Feel No Pain 7 — no base feel no pain) also receive Feel No
    # Pain 5+ from the Dominus despite not being formally attached in the game. The
    # Kataphron units have no native feel no pain and the grant to them is the largest
    # source of over-application (high-toughness 3-wound models with feel no pain 5+
    # are significantly more durable than the tournament baseline). Electro-Priests
    # (Corpuscarii, Fulgurite) retain their entries because they have native feel no
    # pain 5+ from their own BSData infoLinks; the min-merge means the Dominus aura
    # is redundant for them and their presence causes no additional over-application.
    # ADMECH-DIAG-6 (2026-05-26): APPROXIMATION — Skitarii Rangers and Skitarii
    # Vanguard also removed from host_keys. The archetype list carries 2x Rangers
    # and 2x Vanguard alongside one Dominus. The proximity-broadcast model fires
    # Feel No Pain 5+ on all four units simultaneously, but the real 10e rule grants
    # it only to the one unit the Dominus is formally attached to. Four concurrent
    # Feel No Pain 5+ grants on 1-wound Toughness-3 BATTLELINE squads (~33% damage
    # reduction each) inflated AdMech effective durability well beyond tournament
    # baseline. The prior neuter (Electro-Priests only) made the aura a no-op
    # because those units already have native Feel No Pain 5+.
    # WAVE-147 (2026-06-03): re-pointed to a SINGLE-occurrence host that models
    # the real one-attachment FNP 5+ faithfully without over-applying. Kataphron
    # Breachers appear exactly 1x in the Skitarii Hunter Cohort archetype
    # (code/archetypes.py), so the proximity broadcast reaches exactly one unit —
    # the same single-attachment approximation the ADMECH-DIAG-6 note above
    # flagged as the future fix ("a single ... unit can be re-added" once
    # one-attachment is approximated). Kataphron Breachers have no native Feel No
    # Pain, so this grant is now live (a real FNP 5+ on one durable unit), not a
    # no-op — direction-correct and matched to the codex one-attachment rule.
    # Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/#Tech-Priest-Dominus
    # Cited as LeaderAbility.Master of the Machine.
    ("Tech-Priest Dominus", LeaderAbility(name="Master of the Machine",    aura_range=6.0, fnp=5,
                                          host_keys=("adeptus_mechanicus_kataphron_breachers",))),
    # Tech-Priest Manipulus: "Galvanic Field" (BSData v10.6.0 / Wahapedia verbatim):
    # "While this model is leading a unit, weapons equipped by models in that unit
    # have the [Lethal Hits] ability." The Manipulus's Leader list includes
    # Kataphron Destroyers. The SwegHammer proximity-broadcast model applies the
    # aura to every host_keys unit in range, so to model the real one-attachment
    # faithfully the host is a SINGLE-occurrence unit in the Skitarii Hunter
    # Cohort archetype — Kataphron Destroyers appear exactly 1x there, so the
    # broadcast reaches exactly one unit and does not over-apply (same approach
    # as the Dominus note above, which re-points its FNP aura to the 1x Kataphron
    # Breachers). lethal_hits_ranged is consumed in code/units.py attack() on the
    # ranged side (mode != "melee" guard) — [Lethal Hits] mirrors the ranged
    # p.lethal_hits profile field here.
    # Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/#Tech-Priest-Manipulus
    # Cited as LeaderAbility.Galvanic Field.
    ("Tech-Priest Manipulus", LeaderAbility(name="Galvanic Field", aura_range=6.0,
                                            lethal_hits_ranged=True,
                                            host_keys=("adeptus_mechanicus_kataphron_destroyers",))),
    # Death Guard
    # Lord of Contagion: per Wahapedia datasheet
    # (https://wahapedia.ru/wh40k10ed/factions/death-guard/#Lord-of-Contagion)
    # the Leader Bodyguard list is restricted to Blightlord Terminators and
    # Deathshroud Terminators only — NOT Plague Marines. Iter24-D1 fix.
    ("Lord of Contagion",  LeaderAbility(name="Plague-Ridden Champion",     aura_range=6.0, plus_one_to_wound=True,
                                          first_stratagem_free_per_round=True,
                                          host_keys=("death_guard_blightlord_terminators",
                                                     "death_guard_deathshroud_terminators"))),
    ("Typhus",             LeaderAbility(name="The Destroyer Hive",         aura_range=6.0, fnp=5,
                                          host_keys=("death_guard_plague_marines",))),
    # Grey Knights — Brother-Captain pinned to the registry head above to
    # prevent substring-collision with the generic Marines "Captain"
    # entry; only Grand Master remains in the per-faction block here.
    ("Grand Master",       LeaderAbility(name="Tactical Acumen",            aura_range=6.0, plus_one_to_wound=True,
                                          host_keys=("grey_knights_brotherhood_terminator_squad",
                                                     "grey_knights_strike_squad"))),
    # Drukhari (10e: folded into Aeldari faction)
    # DRK-DIAG-3 (2026-05-23): both Drukhari leader auras were strict
    # fabrications, per their own rule_citations entries. Archon's
    # `plus_one_to_hit=True` was wired as a proxy for "Hatred Eternal",
    # which is actually a per-Pain-token Empower mechanic granting full
    # Hit re-rolls only when the unit is Empowered — the sim doesn't
    # model Pain tokens, so the always-on +1-to-hit aura was a stronger-
    # than-real proxy with no gate. Succubus's `reroll_hit_ones=True`
    # was wired as a proxy for "Storm of Blades", which grants
    # [SUSTAINED HITS 1] to melee weapons — a weapon-keyword grant, not
    # a Hit-roll re-roll aura. Both proxies were always-on, ungated, and
    # contributed to Drukhari's +20.5pt gated overshoot. Dropped to NO-FLAG
    # + host_keys-only, matching the SC5-1 Skysplinter pattern. Restore
    # narrowly when (a) Pain-token economy lands and (b) SUSTAINED HITS is
    # modelled. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/
    ("Archon",             LeaderAbility(name="Overlord of Commorragh",     aura_range=6.0,
                                          host_keys=("aeldari_drukhari_kabalite_warriors",))),
    ("Succubus",           LeaderAbility(name="Precision Blows",            aura_range=6.0,
                                          host_keys=("aeldari_drukhari_wyches",))),
    # Genestealer Cults
    # PATRIARCH — "Might From Beyond": while leading a unit, melee weapons
    # equipped by models in that unit have the [DEVASTATING WOUNDS] ability.
    # BSData v10.6.0 Genestealer Cults.cat.gz, Patriarch profile, Might From
    # Beyond ability: "While this model is leading a unit, melee weapons
    # equipped by models in that unit have the [DEVASTATING WOUNDS] ability."
    # Host: PURESTRAIN GENESTEALERS only (BSData Leader profile: "This model
    # can be attached to the following units: PURESTRAIN GENESTEALERS").
    # Catalogue key verified: genestealer_cults_purestrain_genestealers.
    # Pattern identical to Skulltaker's "Lord of Decapitations" (same BSData
    # verbatim text, same grants_devastating_wounds_melee field). The field is
    # already wired in code/units.py (melee-only gate, fires only when
    # mode == "melee"). No Wahapedia fallback needed — BSData confirms the text.
    ("Patriarch",          LeaderAbility(name="Might From Beyond",         aura_range=6.0,
                                          grants_devastating_wounds_melee=True,
                                          host_keys=("genestealer_cults_purestrain_genestealers",))),
    # PRIMUS — "Cult Demagogue": while leading a unit, each time a model in
    # that unit makes an attack, add 1 to the Hit roll. BSData v10.6.0
    # Genestealer Cults.cat.gz, Primus profile, Cult Demagogue ability:
    # "While this model is leading a unit, each time a model in that unit
    # makes an attack, you can add 1 to the Hit roll." Corrected from the
    # prior `reroll_hit_ones` approximation (the prior name "Meticulous
    # Uprising" was a fabrication — the codex ability is named "Cult
    # Demagogue"). The codex grants a full unconditional +1-to-Hit on every
    # attack — strictly stronger than re-rolling 1s; `plus_one_to_hit=True`
    # is the accurate modelling. Hosts: Acolyte Hybrids (both loadout
    # variants), Hybrid Metamorphs, and Neophyte Hybrids — BSData Leader
    # profile: "This model can be attached to the following units: ACOLYTE
    # HYBRIDS, HYBRID METAMORPHS, NEOPHYTE HYBRIDS."
    ("Primus",             LeaderAbility(name="Cult Demagogue",            aura_range=6.0,
                                          plus_one_to_hit=True,
                                          host_keys=("genestealer_cults_neophyte_hybrids",
                                                     "genestealer_cults_acolyte_hybrids_with_autopistols",
                                                     "genestealer_cults_acolyte_hybrids_with_hand_flamers",
                                                     "genestealer_cults_hybrid_metamorphs"))),
    # Leagues of Votann
    # VOTANN-JUDGEMENT-TOKENS-V1 (2026-05-28): downgraded the Kâhl aura from
    # `plus_one_to_hit=True` to `reroll_hit_ones=True` on the led Hearthkyn
    # squad. The codex rule is Kindred Hero: weapons in the led unit gain
    # [LETHAL HITS] (Critical Hits — natural 6s on Hit — auto-wound). The
    # simulator does not model the LETHAL HITS keyword, so a proxy is
    # required. The previous `plus_one_to_hit` proxy was a roughly 2× over-
    # buff: on a BS4+ shooter LETHAL HITS adds ~17% wounds (1/6 of hits
    # auto-wound vs the baseline 50% wound roll), whereas +1 to Hit adds
    # ~33% wounds (BS4+ → BS3+ raises hit probability from 0.5 to 0.667).
    # `reroll_hit_ones` is a closer numerical match (~+17% hits = ~+17%
    # wounds on a 4+ wound roll) and is strictly weaker than the codex
    # LETHAL HITS in melee against high-T targets (where 6s already wound
    # naturally), erring on the under-buff side per the SC5 audit standard.
    # The Kâhl-led Hearthkyn brick is the spine of the modal Votann list
    # (see code/archetypes.py "Oathband" template), so this single-leader
    # change feeds through the most-played unit. Cited as
    # `LeaderAbility.Warrior-Forged Leadership`.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/K-hl
    ("Kâhl",               LeaderAbility(name="Warrior-Forged Leadership",  aura_range=6.0, reroll_hit_ones=True,
                                          host_keys=("leagues_of_votann_hearthkyn_warriors",))),
)

# ---------------------------------------------------------------------------
# Astra Militarum officer leader-attachment registry entries
# (gated SWEG_OFFICER_FOLLOW, default-on since the wave-244 adoption;
# SWEG_OFFICER_FOLLOW=0 is the kill-switch)
#
# Four officers whose Leader datasheets specify legal bodyguard hosts. These
# entries serve a STRUCTURAL purpose only under the current schema: the
# LeaderAbility fields carry no offensive/defensive aura (the real codex
# abilities are Order-economy and unit-buff mechanics that do not map onto
# existing LeaderAbility flag fields), so the simulator's `effective_buffs`
# merge will see them as zero-contribution — the actual tactical benefit
# comes entirely from the Half-B stay-near piloting hook (pick_move_intent,
# code/strategy.py) which keeps officers inside their 6" Order-issuance band.
#
# When the gate is on (the default) these entries append to _REGISTRY,
# making `lookup_ability` resolve each officer name and enabling the
# host_keys gate in `is_actually_led`. SWEG_OFFICER_FOLLOW=0 leaves
# _REGISTRY unchanged, behaviour byte-identical to the pre-wave-244 arm.
#
# BSData verbatim attach targets (Library cat.gz, cross-checked):
#   Cadian Castellan  (id 2b49-4d03-aaf5-3532): Cadian Shock Troops, Kasrkin
#   Cadian Command Squad (id 4d28-f2a7-67c1-eb2e): Cadian Shock Troops
#   Ursula Creed       (id b6b2-9971-ec0c-349e): Cadian Shock Troops, Kasrkin
#   Lord Solar Leontus (id a9d-55c1-3d24-fa25):
#       Attilan Rough Riders, Cadian Shock Troops, Catachan Jungle Fighters,
#       Death Korps of Krieg, Death Riders, Kasrkin, Krieg Combat Engineers
#       (all seven host keys confirmed present in data/bsdata/parsed.json —
#       rule 13 key-verification performed before listing)
#
# Cited as LeaderAbility.<Officer>.leader_attachment in
# data/rule_citations.d/astra_militarum.json.
# ---------------------------------------------------------------------------

_AM_OFFICER_FOLLOW_GATE: bool = os.environ.get("SWEG_OFFICER_FOLLOW", "1") == "1"

# Wave-245 adopted (default-on, kill-switch retained): extend Lord Solar's
# stay-near coverage to include the five SQUADRON artillery/tank catalog keys
# so the officer-follow hook can pull him toward unordered SQUADRON vehicles
# when infantry hosts are already covered.  Screened wash-keep on fidelity
# (paired N=40 vs the sc10a anchor: gated 6.77 to 6.75, Astra Militarum
# +0.68 with 157 flipped games — orders now reach artillery, churn without
# net direction).  SWEG_SOLAR_SQUADRON=0 restores the pre-wave-245 arm.
_AM_SOLAR_SQUADRON_GATE: bool = os.environ.get("SWEG_SOLAR_SQUADRON", "1") == "1"

# Lord Solar Leontus has three Orders per round targeting REGIMENT, SQUADRON,
# and TITANIC units (code/orders.py OFFICER_ORDER_PROFILES).  His seven codex
# infantry attach-targets are the base host_keys.  When SWEG_SOLAR_SQUADRON=1
# the five SQUADRON vehicle catalog keys are appended so the officer-follow
# hook also pulls him toward unordered artillery/tanks sitting beyond his 6"
# aura — preventing his SQUADRON Orders from wasting every round.
# Catalog keys confirmed present in data/bsdata/parsed.json (rule 13 check).
_LORD_SOLAR_SQUADRON_KEYS: Tuple[str, ...] = (
    "astra_militarum_leman_russ_battle_tank",
    "astra_militarum_leman_russ_demolisher",
    "astra_militarum_rogal_dorn_battle_tank",
    "astra_militarum_basilisk",
    "astra_militarum_manticore",
)
_LORD_SOLAR_HOST_KEYS: Tuple[str, ...] = (
    "astra_militarum_attilan_rough_riders",
    "astra_militarum_cadian_shock_troops",
    "astra_militarum_catachan_jungle_fighters",
    "astra_militarum_death_korps_of_krieg",
    "astra_militarum_death_riders",
    "astra_militarum_kasrkin",
    "astra_militarum_krieg_combat_engineers",
) + (_LORD_SOLAR_SQUADRON_KEYS if _AM_SOLAR_SQUADRON_GATE else ())

# These entries fold into the unconditional _REGISTRY when the gate itself is
# removed at a future wave. Until then they are appended only when the gate is
# on (the default), keeping SWEG_OFFICER_FOLLOW=0 as a working kill-switch.
_AM_OFFICER_REGISTRY_ENTRIES: Tuple[Tuple[str, LeaderAbility], ...] = (
    # Cadian Castellan — "Senior Officer" ability (BSData id 2b49-4d03-aaf5-3532).
    # BSData verbatim (Imperium - Astra Militarum - Library.cat.gz, Abilities
    # profile id a7f5-adb8-d1c9-2a2d): "While this model is leading a unit,
    # ranged weapons equipped by models in that unit have the [SUSTAINED HITS 1]
    # ability"
    # The grant is wired via sustained_hits_ranged=1 (gate SWEG_CASTELLAN_SH,
    # default ON since wave 247; "0" is the kill-switch). Killed (=0) is
    # byte-identical to the pre-wave-247 arm: the field default is 0, and the
    # application site in code/units.py (~line 3682) guards with
    # `if _aura_sh_r > 0`, so a 0 value produces no effect. Import-time
    # evaluation is safe: evaluation processes set SWEG_CASTELLAN_SH before
    # spawning the worker, and no battle is in flight at module load.
    # Cited as LeaderAbility.Cadian Castellan.leader_attachment and
    # LeaderAbility.Senior Officer in data/rule_citations.d/astra_militarum.json.
    ("Cadian Castellan",     LeaderAbility(name="Senior Officer",              aura_range=6.0,
                                            host_keys=("astra_militarum_cadian_shock_troops",
                                                       "astra_militarum_kasrkin"),
                                            sustained_hits_ranged=(1 if os.environ.get("SWEG_CASTELLAN_SH", "1") != "0" else 0))),
    # Cadian Command Squad — "Cadia Stands!" ability (BSData id 4d28-f2a7-67c1-eb2e).
    # BSData verbatim Leader text: "This model can be attached to the following
    # unit: Cadian Shock Troops". The Cadia Stands! ability grants Benefit of
    # Cover against ranged attacks while on a controlled objective — a defensive
    # once-per-attack gate with no existing LeaderAbility proxy. Structural only.
    # Cited as LeaderAbility.Cadian Command Squad.leader_attachment.
    ("Cadian Command Squad",  LeaderAbility(name="Cadia Stands!",              aura_range=6.0,
                                            host_keys=("astra_militarum_cadian_shock_troops",))),
    # Ursula Creed — "Lord Castellan" ability (BSData id b6b2-9971-ec0c-349e).
    # BSData verbatim: "While this model is leading a unit, that unit can be
    # affected by up to two different Orders at the same time." The double-Order
    # exception is gated by SWEG_CREED_TWO_ORDERS (default off, wave 248).
    # When the gate is on, the Order dispatcher (code/orders.py) allows the
    # squad Creed is leading to receive a second, different Order per round.
    # Cited as SWEG_CREED_TWO_ORDERS.lord_castellan_two_orders in
    # data/rule_citations.json.
    ("Ursula Creed",          LeaderAbility(name="Lord Castellan",             aura_range=6.0,
                                            host_keys=("astra_militarum_cadian_shock_troops",
                                                       "astra_militarum_kasrkin"))),
    # Lord Solar Leontus — "The Lord Solar" / CP-drip ability (BSData id a9d-55c1-3d24-fa25).
    # BSData verbatim: "At the start of your Command phase, if this model is on
    # the battlefield, you gain 1 CP." Modelled as cp_discount_per_round=1 which
    # is the closest existing LeaderAbility field for a per-round CP gain.
    # MOUNTED keyword (Move 12") — routes through pick_move_intent exactly like
    # other officers; no MOUNTED-specific movement gate exists in the hook, so
    # Leontus is subject to the same officer-follow pull as INFANTRY officers.
    # host_keys: seven BSData infantry attach-targets; when SWEG_SOLAR_SQUADRON=1
    # also includes the five SQUADRON vehicle keys defined in
    # _LORD_SOLAR_SQUADRON_KEYS above (wave-245 screen gate).
    # Cited as LeaderAbility.Lord Solar Leontus.leader_attachment.
    ("Lord Solar Leontus",    LeaderAbility(name="The Lord Solar",             aura_range=6.0,
                                            cp_discount_per_round=1,
                                            host_keys=_LORD_SOLAR_HOST_KEYS)),
)

if _AM_OFFICER_FOLLOW_GATE:
    _REGISTRY = _REGISTRY + _AM_OFFICER_REGISTRY_ENTRIES


def warlord_ability(army: "Army") -> Optional[LeaderAbility]:
    """Return the LeaderAbility of this army's Warlord, if any.

    Warlord is defined here as the first alive CHARACTER unit (in iteration
    order on `army.units`) whose LeaderAbility carries any CP-economy field
    (`cp_discount_per_round`, `cp_refund_per_battle`, or
    `first_stratagem_free_per_round`). This narrow definition is sufficient
    for the simulator's CP-econ gates: a non-Warlord-having army returns
    None and never accrues a discount.

    A character that loses its alive status mid-battle does NOT cause the
    discount to retroactively disappear from the army's accumulated CP —
    the latches in `Army.cp_refund_remaining` /
    `Army._warlord_first_strat_free_enabled` are set at battle start once.
    """
    for u in army.units:
        if not u.is_alive:
            continue
        kw = set(u.profile.unit_keywords or ())
        if "CHARACTER" not in kw:
            continue
        ability = lookup_ability(u.profile.name)
        if ability is None:
            continue
        if (
            ability.cp_discount_per_round > 0
            or ability.cp_refund_per_battle > 0
            or ability.first_stratagem_free_per_round
        ):
            return ability
    return None


@functools.lru_cache(maxsize=2048)
def lookup_ability(profile_name: str) -> Optional[LeaderAbility]:
    """
    Find a LeaderAbility by substring match against the unit's profile name.

    "Captain in Terminator Armour" -> matches "Captain" -> Rites of Battle.
    Returns None if no entry matches.

    Cached because the registry is static and the call sits on the per-attack
    hot path (every `effective_buffs` invocation scans the attacker's army
    for in-range leaders and asks this function about each one).
    """
    if not profile_name:
        return None
    for key, ability in _REGISTRY:
        if key in profile_name:
            return ability
    return None


# ---------------------------------------------------------------------------
# Aura application — merge detachment + in-range leader flags
# ---------------------------------------------------------------------------

# Default buff dict: all flags off / neutral. Same shape Unit.attack consumes.
_NEUTRAL_BUFFS: Dict[str, object] = {
    "reroll_hit_ones": False,
    # TSON-AURA-V2: shooting-phase-only re-roll 1s (Ahriman / Infernal Master /
    # Sorcerer in Terminator Armour). Consumed in units.py with mode != "melee" gate.
    "reroll_hit_ones_shooting_only": False,
    "reroll_wound_ones": False,
    "plus_one_to_hit": False,
    "plus_one_to_hit_melee_only": False,
    "plus_one_to_wound": False,
    "plus_one_to_wound_melee_only": False,
    "plus_one_attack": 0,
    "plus_one_save": False,
    "extra_invuln": 7,
    "fnp": 7,
    # LEADERABILITY-SCHEMA: three new Greater Daemon locus fields (see
    # LeaderAbility dataclass docstring for derivation). Defaults False so
    # the buff dict matches every existing call site that consumes it via
    # bracket access — the consumers in code/units.py only branch on True.
    "plus_one_strength_ranged": False,
    "plus_one_toughness": False,
    "plus_one_ap_melee": False,
    # DAEMONS-DIAG-7: Skulltaker "Lord of Decapitations" — led unit's melee
    # attacks gain [DEVASTATING WOUNDS]. Default False; only True when Skulltaker
    # is alive and leading Bloodletters.
    "grants_devastating_wounds_melee": False,
    # DAEMONS-DIAG-9: Daemon Prince "Prince of Darkness" — LEGIONES DAEMONICA
    # units within 6\" gain the Stealth ability (-1 to ranged Hit rolls targeting
    # them). Default False; only True when a Daemon Prince of Chaos is alive and
    # in-range of the target unit.
    "grants_stealth_aura": False,
    # DAEMONS-LOCUS-V1 follow-up — Locus-granted [SUSTAINED HITS N]. See
    # LeaderAbility for derivation. Integer because multiple aura sources
    # stack additively, matching the existing per-weapon / detachment /
    # transient SUSTAINED HITS stacking convention in code/units.py.
    "sustained_hits_ranged": 0,
    "sustained_hits_melee": 0,
    # Galvanic Field (AdMech Manipulus) — led unit's ranged weapons gain
    # [LETHAL HITS]. Default False; only True when a Tech-Priest Manipulus is
    # alive and leading the single host_keys-gated unit (Kataphron Destroyers).
    "lethal_hits_ranged": False,
}


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def _merge_bool(target: Dict[str, object], source: object, key: str) -> None:
    """OR-merge a boolean flag: any source granting it wins."""
    if getattr(source, key, False):
        target[key] = True


def _merge_min(target: Dict[str, object], source: object, key: str, default_off: int = 7) -> None:
    """Take the better (lower) of the two values, treating `default_off` as off."""
    s_val = getattr(source, key, default_off)
    if s_val < target[key]:
        target[key] = s_val


def _merge_add(target: Dict[str, object], source: object, key: str) -> None:
    """Additive int merge — used for plus_one_attack stacking."""
    s_val = getattr(source, key, 0)
    if s_val:
        target[key] = target[key] + s_val


def in_range_leaders(attacker: "Unit") -> List["Unit"]:
    """
    Return alive friendly CHARACTER units whose aura covers `attacker`.

    A leader covers the attacker if:
      * its aura_range is 0 (army-wide), OR
      * the distance from leader to attacker is <= aura_range.

    Leaders without a registered ability are skipped.
    """
    army = getattr(attacker, "army_ref", None)
    if army is None:
        return []
    covered: List["Unit"] = []
    for u in army.alive_units:
        if u is attacker:
            continue
        ability = lookup_ability(u.profile.name)
        if ability is None:
            continue
        if ability.aura_range <= 0:
            covered.append(u)
        else:
            if _distance(u.position, attacker.position) <= ability.aura_range:
                covered.append(u)
    return covered


# Reverse map: UnitProfile.name -> tuple of all matching catalog keys.
# Used by `is_actually_led` and the iter22 `effective_buffs` host-gate to
# translate an attacker's profile name back to UNIT_CATALOG keys that
# `LeaderAbility.host_keys` is declared against.
#
# Why a TUPLE not a single key: profile names are not unique across
# factions. "Plague Marines" lives in both `death_guard_plague_marines`
# and `chaos_space_marines_plague_marines`. A previous single-key cache
# silently dropped one of the two — which caused iter22's host gate to
# fail-closed when a Death Guard Lord of Contagion's host_keys listed
# `death_guard_plague_marines` but the reverse lookup happened to land
# on the CSM key. Returning ALL keys and letting the gate test set
# intersection eliminates the false negative.
#
# Built lazily on first use so importing `code.leaders` doesn't force
# `code.units` to load.
_NAME_TO_KEYS_CACHE: Dict[str, Tuple[str, ...]] = {}


def _name_to_catalog_keys(name: str) -> Tuple[str, ...]:
    """Reverse lookup: UnitProfile.name -> ALL matching UNIT_CATALOG keys.

    Returns an empty tuple if the name isn't present in UNIT_CATALOG.
    Names are NOT unique across factions ("Plague Marines" appears in
    both Death Guard and Chaos Space Marines), so callers must treat
    the result as a set and test set membership / intersection against
    a leader's host_keys.
    """
    global _NAME_TO_KEYS_CACHE
    if not _NAME_TO_KEYS_CACHE:
        from .units import UNIT_CATALOG
        from collections import defaultdict
        builder: Dict[str, list] = defaultdict(list)
        for k, p in UNIT_CATALOG.items():
            builder[p.name].append(k)
        _NAME_TO_KEYS_CACHE = {n: tuple(ks) for n, ks in builder.items()}
    return _NAME_TO_KEYS_CACHE.get(name, ())


def _name_to_catalog_key(name: str) -> Optional[str]:
    """Backwards-compatible single-key lookup.

    Returns the FIRST matching UNIT_CATALOG key for `name`, or None if no
    catalog entry shares the name. Retained for the existing
    `is_actually_led` caller (the gate is now an `any(... in host_keys)`
    check using the full keys tuple — see below — but this single-key
    helper is kept for any other call site that hasn't migrated).
    """
    keys = _name_to_catalog_keys(name)
    return keys[0] if keys else None


# Legacy alias retained for any debug/test code reading the old cache
# directly. New code should use _NAME_TO_KEYS_CACHE.
_NAME_TO_KEY_CACHE: Dict[str, str] = {}


def is_actually_led(attacker: "Unit") -> bool:
    """Tighter "leading" gate for the Awakened Dynasty Command Protocols
    rule (and other "while a CHARACTER is leading this unit" effects).

    The 10e Leader rule says a CHARACTER "leads" a unit only when it is
    formally attached to that unit at list-building (a one-CHARACTER-per-
    bodyguard relationship, moves coherently, dies with the unit). The
    SwegHammer simulator doesn't carry an explicit attachment registry,
    so we approximate "leading" with TWO co-incident conditions:

      1. proximity — at least one alive friendly CHARACTER is within the
         leader's own aura_range of `attacker` (i.e. `in_range_leaders`),
         AND
      2. legal host — that CHARACTER's `LeaderAbility.host_keys` includes
         `attacker`'s UNIT_CATALOG key. This rules out impossible
         attachments: a Necron Overlord cannot lead a C'tan Shard, a
         Lokhust Heavy Destroyer, a Doomstalker, or any non-INFANTRY
         BATTLELINE unit, so those attackers must NEVER receive the
         Command Protocols +1-to-hit even with a friendly Overlord
         standing 6" away.

    Returns False if either gate fails — including when the attacker
    has no catalog key (CHARACTERs themselves, hand-rolled profiles,
    or anything not in UNIT_CATALOG).

    Cited as `AWAKENED_DYNASTY.bonus_to_hit_when_led` and used by
    `effective_buffs` to gate the detachment-level +1-to-hit grant.
    """
    candidates = in_range_leaders(attacker)
    if not candidates:
        return False
    # Use the full set of catalog keys matching this profile name (Plague
    # Marines exists in both Death Guard and Chaos Space Marines, etc.).
    attacker_keys = _name_to_catalog_keys(attacker.profile.name)
    if not attacker_keys:
        return False
    for leader in candidates:
        ability = lookup_ability(leader.profile.name)
        if ability is None:
            continue
        if any(k in ability.host_keys for k in attacker_keys):
            return True
    return False


# Per-activation cache for effective_buffs. Keyed on unit.uid. Cleared by
# bump_buffs_generation() which the simulator calls at the start of each unit
# activation. Within a single pick_move_intent / target-scoring loop nothing
# moves, so every repeated call for the same unit returns instantly.
_buffs_cache: Dict[str, Any] = {}


def bump_buffs_generation() -> None:
    """Clear the effective_buffs cache. Call at the start of each unit activation."""
    _buffs_cache.clear()


def _arrived_via_deep_strike_this_round(attacker) -> bool:
    """True if *attacker* arrived from reserves this battle round — the proxy
    for the Grey Knights Fury of Titan 'set up via Deep Strike, until end of
    turn' window. Reads the Battle's `_fresh_arrivals` set via the unit's army
    back-reference; returns False outside a running Battle (catalogue / unit
    tests), keeping the fidelity gate inert there. `_fresh_arrivals` is reset
    each round, so membership means 'arrived this round' = 'until end of turn'."""
    army = getattr(attacker, "army_ref", None)
    battle = getattr(army, "_battle_ref", None) if army is not None else None
    fresh = getattr(battle, "_fresh_arrivals", None) if battle is not None else None
    if not fresh:
        return False
    return getattr(attacker, "uid", None) in fresh


def effective_buffs(attacker: "Unit") -> Dict[str, object]:
    """
    Merge the attacker's detachment passives with every in-range friendly
    leader's aura flags. Returns a buff dict with the same field names as
    `Detachment`. Booleans OR together; `extra_invuln` / `fnp` take the min.

    Detachment carries all the boolean attack flags + plus_one_attack +
    plus_one_save + extra_invuln. Leader auras add the offensive booleans,
    extra_invuln, and FNP (which detachments don't currently expose).

    Iter 22 host_keys gating (faction-neutral structural fix):
      Per-leader aura merge consults `LeaderAbility.host_keys`. The 10e
      Leader rule says a CHARACTER aura applies to "this model's unit"
      (the attached bodyguard squad), NOT to every friendly within aura
      range. The per-leader merge therefore filters by host_keys:

        * `host_keys == ()` (empty tuple)
            Army-wide / broadcast aura — apply to any attacker in range.
            Used for MONSTER auras with no formal attachment whose codex
            wording is "While a friendly <FACTION> unit is within X"...":
              - Hive Tyrant (Onslaught — 6" Tyranids aura)
              - Avatar of Khaine (Bloody-Handed — 6" Aeldari aura; no
                offensive flags after iter21 fab audit, but the empty
                tuple is structurally correct)
              - The Yncarne (Ethereal Form is self-heal-on-kill, applied
                via apply_round_end_healing — no offensive aura)

        * `host_keys != ()` (non-empty)
            Bodyguard-gated aura — apply ONLY when
            `_name_to_catalog_key(attacker.profile.name)` is in
            `host_keys`. Implements the "While this model is leading a
            unit..." codex wording. Pre-iter22 this gate was missing,
            so e.g. Typhus's Destroyer Hive FNP fired on EVERY Death
            Guard unit within 6" instead of just the Plague Marines he
            was attached to — and the same bug affected every faction's
            leader auras (Necron Overlord, Marine Lieutenant, Aeldari
            Spiritseer, etc.).

      Existing detachment-side gates (`is_actually_led` for
      Awakened-Dynasty Command Protocols) already apply host_keys
      filtering correctly — only the per-leader merge below was missing
      it.

      Attackers with no UNIT_CATALOG key (hand-rolled test profiles,
      synthetic names) cannot satisfy a non-empty host_keys check, so
      their non-broadcast aura merges are skipped. This is deliberate:
      if you can't be a legal bodyguard, you don't receive the led-unit
      aura. Empty-tuple broadcast auras still apply to such attackers.
    """
    uid = getattr(attacker, "uid", None) or None  # treat "" as uncacheable
    if uid is not None and uid in _buffs_cache:
        return _buffs_cache[uid]

    buffs = dict(_NEUTRAL_BUFFS)

    army = getattr(attacker, "army_ref", None)
    if army is not None:
        try:
            det = army.resolve_detachment()
        except Exception:
            det = None
        if det is not None:
            # Grey Knights Fury of Titan deep-strike gate (SWEG_GK_FURY_FAITHFUL,
            # default OFF). The codex grants the re-roll-1s-to-hit-and-wound only
            # to a unit that arrived via Deep Strike this turn; the detachment
            # otherwise models it army-wide always-on (documented approximation).
            # When the gate is set and the detachment flags
            # `reroll_ones_requires_deep_strike`, merge the two rerolls ONLY for
            # an attacker that arrived from reserves this round. OFF path (gate
            # unset) runs the unconditional merge → byte-identical; the gate is
            # also inert for any detachment that does not set the flag.
            _ds_gated = (
                __import__("os").environ.get("SWEG_GK_FURY_FAITHFUL") == "1"
                and getattr(det, "reroll_ones_requires_deep_strike", False)
                and not _arrived_via_deep_strike_this_round(attacker)
            )
            if not _ds_gated:
                _merge_bool(buffs, det, "reroll_hit_ones")
                _merge_bool(buffs, det, "reroll_wound_ones")
            _merge_bool(buffs, det, "plus_one_to_hit")
            _merge_bool(buffs, det, "plus_one_to_wound")
            _merge_bool(buffs, det, "plus_one_save")
            _merge_add(buffs, det, "plus_one_attack")
            _merge_min(buffs, det, "extra_invuln")
            _merge_min(buffs, det, "fnp")
            # Conditional offensive trigger: detachment-led +1-to-hit aura
            # (Awakened Dynasty Command Protocols). Wahapedia verbatim:
            # "While a NECRONS CHARACTER model is leading this unit, each
            # time a model in this unit makes an attack, add 1 to the Hit
            # roll." 10e "leading" is the formal Leader/Bodyguard attachment,
            # not just proximity — so use `is_actually_led`, which requires
            # an in-range CHARACTER whose host_keys list the attacker. This
            # correctly excludes attackers that cannot be led at all
            # (C'tan Shards, Lokhust Heavy Destroyers, Doomstalkers, Wraiths,
            # Tomb Blades, etc.) — they retain their base hit roll regardless
            # of how many Overlords stand 6" away. Fix iter 20: previously
            # gated on `in_range_leaders(attacker)`, which over-fired the +1
            # on every Necron unit within 6" of any CHARACTER. iter 19's
            # parked salvage of this same change was reverted because of
            # cumulative cross-faction noise; iter 20 re-applies it together
            # with the Lychguard host_keys fix so Lychguard squads correctly
            # receive the buff while non-leadable wreckers (C'tan, Lokhust HD,
            # Doomstalker, Wraiths, Tomb Blades) correctly do not. Cited as
            # `AWAKENED_DYNASTY.bonus_to_hit_when_led`.
            if getattr(det, "bonus_to_hit_when_led", False) \
                    and is_actually_led(attacker):
                buffs["plus_one_to_hit"] = True

            # Keyword-gated second-detachment buffs (#126). Each fires only
            # when the attacker's datasheet matches the detachment's gate.
            attacker_kw = set(getattr(attacker.profile, "unit_keywords", ()) or ())
            attacker_name = getattr(attacker.profile, "name", "") or ""
            # Ironstorm Spearhead — VEHICLE units re-roll Hit rolls of 1.
            if (
                getattr(det, "vehicles_reroll_hit_ones", False)
                and "VEHICLE" in attacker_kw
            ):
                buffs["reroll_hit_ones"] = True
            # Canoptek Court — CANOPTEK units get +1 to wound. Datasheet
            # detection via name-prefix matches all four BSData entries
            # (Reanimator, Spyders, Scarab Swarms, Wraiths).
            if (
                getattr(det, "canoptek_plus_one_to_wound", False)
                and attacker_name.startswith("Canoptek")
            ):
                buffs["plus_one_to_wound"] = True
            # Plague Marines Onslaught — Plague Marines get +1 to wound.
            if (
                getattr(det, "plague_marines_plus_one_to_wound", False)
                and attacker_name == "Plague Marines"
            ):
                buffs["plus_one_to_wound"] = True
            # NB: Saim-Hann Wild Host's +1" Movement is a phase-side buff,
            # not an attack-side modifier; it's applied via the
            # `effective_move` helper, not here.

    # iter22 — resolve the attacker's full set of catalog keys once for
    # host-gate use across the per-leader merge below. Empty tuple when
    # the attacker is a synthetic / hand-rolled profile (test fixtures,
    # scratch profiles), or when its name doesn't appear in UNIT_CATALOG.
    # Returns multiple keys when the same name spans factions (Plague
    # Marines: Death Guard + CSM), so the gate uses set intersection.
    attacker_keys_for_host_gate = _name_to_catalog_keys(
        getattr(attacker.profile, "name", "") or ""
    )

    # Compute in_range_leaders once — reused for both leader-aura merge and
    # enhancement-carrier scan below.
    nearby_leaders = in_range_leaders(attacker)

    for leader in nearby_leaders:
        ability = lookup_ability(leader.profile.name)
        if ability is None:
            continue
        # Host-gate: see docstring's "Iter 22 host_keys gating" block.
        # Empty host_keys = army-wide broadcast aura (apply unconditionally).
        # Non-empty host_keys = bodyguard-gated; apply ONLY when ANY of
        # the attacker's UNIT_CATALOG keys is in host_keys (set
        # intersection). Attackers with no catalog keys fail any
        # non-empty gate.
        if ability.host_keys:
            if not any(k in ability.host_keys for k in attacker_keys_for_host_gate):
                continue
        # SWEG_CSM_ABILITIES gate for CSM-specific leader abilities.
        # Checked once per leader in the loop; avoids repeated os.environ lookups
        # by reading from a local already established before the loop is entered.
        # (For performance, this is cheap — the env is rarely changed mid-run.)
        _csm_gate_on = __import__("os").environ.get("SWEG_CSM_ABILITIES", "1") != "0"
        # Dark Apostle: gate-ON suppresses the old reroll_hit_ones proxy (because
        # plus_one_to_wound_melee_only fires in its place); gate-OFF keeps the proxy.
        # Abaddon: the Paragon of Hatred aura is default-off; gate-ON enables it.
        _ability_name = getattr(ability, "name", "")
        _dark_apostle_on = _csm_gate_on and _ability_name == "Dark Zealotry"
        _abaddon_off = not _csm_gate_on and _ability_name == "Paragon of Hatred"
        if _abaddon_off:
            # Abaddon's aura is default-off; skip all fields for this leader.
            continue
        # SWEG_SOROR_ABILITIES gate for Sororitas-specific leader abilities.
        # Gate-OFF (default): Miraculous Intervention and Abbess Sanctorum auras
        # are suppressed entirely — their leader entries are default-off, so if
        # the gate is OFF we skip the whole leader. Gate-ON: aura fields merge
        # normally (no proxy suppression needed, the fields are the faithful rule).
        _soror_gate_on = __import__("os").environ.get("SWEG_SOROR_ABILITIES", "1") != "0"
        _soror_off = (not _soror_gate_on) and (_ability_name in (
            "Miraculous Intervention", "Abbess Sanctorum",
        ))
        if _soror_off:
            # Sororitas gate explicitly disabled (default-ON since wave 232);
            # skip all fields for this leader.
            continue
        # Dark Apostle gate-ON: suppress the legacy reroll_hit_ones proxy because
        # plus_one_to_wound_melee_only (gated in units.py) fires in its place.
        if not _dark_apostle_on:
            _merge_bool(buffs, ability, "reroll_hit_ones")
        # TSON-AURA-V2: shooting-only re-roll 1s grant. See LeaderAbility
        # dataclass comment and units.py consumption site for gate detail.
        _merge_bool(buffs, ability, "reroll_hit_ones_shooting_only")
        _merge_bool(buffs, ability, "reroll_wound_ones")
        _merge_bool(buffs, ability, "plus_one_to_hit")
        _merge_bool(buffs, ability, "plus_one_to_hit_melee_only")
        _merge_bool(buffs, ability, "plus_one_to_wound")
        _merge_bool(buffs, ability, "plus_one_to_wound_melee_only")
        _merge_add(buffs, ability, "plus_one_attack")
        _merge_min(buffs, ability, "extra_invuln")
        _merge_min(buffs, ability, "fnp")
        # LEADERABILITY-SCHEMA: Greater Daemon locus fields. Booleans OR
        # together — multiple loci of the same type don't stack numerically
        # in 10e (you either get +1 S / +1 T / +1 AP from a locus or you
        # don't). The simulator's modifier cap on hit/wound rolls already
        # handles +1-to-hit / +1-to-wound at the delta level; for these
        # stat-level uplifts the boolean OR is the right shape because
        # codex wording is "improve by 1", not "modifier +1" subject to a
        # cap. Strength and AP uplifts apply at the attacker side; the
        # toughness uplift applies at the defender side (and so reads
        # tgt_buffs, not att_buffs, in code/units.py).
        _merge_bool(buffs, ability, "plus_one_strength_ranged")
        _merge_bool(buffs, ability, "plus_one_toughness")
        _merge_bool(buffs, ability, "plus_one_ap_melee")
        _merge_bool(buffs, ability, "grants_devastating_wounds_melee")
        # DAEMONS-DIAG-9: Daemon Prince "Prince of Darkness" stealth aura.
        # Defender-side buff — callers reading tgt_buffs will see this True
        # when a friendly Daemon Prince of Chaos is within 6\" of the target.
        _merge_bool(buffs, ability, "grants_stealth_aura")
        # DAEMONS-LOCUS-V1 follow-up — SUSTAINED HITS aura magnitudes.
        # Additive: multiple Locus carriers within range stack their grants
        # (rare in practice — most armies field at most one Locus-bearing
        # Herald per god).
        _merge_add(buffs, ability, "sustained_hits_ranged")
        _merge_add(buffs, ability, "sustained_hits_melee")
        # Galvanic Field (AdMech Manipulus) — led unit's ranged weapons gain
        # [LETHAL HITS]. Boolean OR (the grant is binary, not stacking).
        _merge_bool(buffs, ability, "lethal_hits_ranged")

    # 10e Enhancements (Warlord upgrades). Each in-range friendly CHARACTER
    # may carry one Enhancement; if it does, OR-merge the aura modifier
    # flags onto the same buff dict. Enhancement fields are namespaced
    # with `_aura` to keep them visually distinct from the LeaderAbility
    # equivalents, but they merge into the same neutral-buffs keys.
    # We also include `attacker.enhancement` itself: a CHARACTER carrying
    # an Enhancement is its own bearer, so its unit benefits even without
    # a separate friendly CHARACTER nearby.
    enh_carriers: List["Unit"] = []
    army = getattr(attacker, "army_ref", None)
    if army is not None:
        # Bearer is the attacker itself, when applicable.
        if getattr(attacker, "enhancement", None) is not None:
            enh_carriers.append(attacker)
        # Plus every other in-range friendly CHARACTER carrying an
        # Enhancement; reuse nearby_leaders — no second scan needed.
        for leader in nearby_leaders:
            if leader is attacker:
                continue
            if getattr(leader, "enhancement", None) is not None:
                enh_carriers.append(leader)
    for carrier in enh_carriers:
        enh = carrier.enhancement
        if enh is None:
            continue
        if getattr(enh, "plus_one_to_hit_aura", False):
            buffs["plus_one_to_hit"] = True
        if getattr(enh, "plus_one_to_wound_aura", False):
            buffs["plus_one_to_wound"] = True
        if getattr(enh, "reroll_hit_ones_aura", False):
            buffs["reroll_hit_ones"] = True
        if getattr(enh, "reroll_wound_ones_aura", False):
            buffs["reroll_wound_ones"] = True
        extra_atk = int(getattr(enh, "extra_attacks_melee", 0) or 0)
        if extra_atk:
            buffs["plus_one_attack"] = int(buffs["plus_one_attack"]) + extra_atk
        if getattr(enh, "fnp_to_5", False):
            cur_fnp = int(buffs["fnp"])
            if cur_fnp > 5:
                buffs["fnp"] = 5

    if uid is not None:
        _buffs_cache[uid] = buffs
    return buffs



# ---------------------------------------------------------------------------
# Round-end healing
# ---------------------------------------------------------------------------

def apply_round_end_healing(army: "Army") -> None:
    """
    End-of-round leader heal: every alive leader with heal_per_round > 0
    restores HP. Priority:
      1. nearest WOUNDED friendly within aura_range (lowest current_health
         first, ties broken by distance);
      2. else the leader itself if it's wounded;
      3. else no-op.

    Cap at the recipient's max health.
    """
    for leader in army.alive_units:
        ability = lookup_ability(leader.profile.name)
        if ability is None or ability.heal_per_round <= 0:
            continue

        # Build candidate list: wounded friendlies in aura
        candidates: List["Unit"] = []
        for u in army.alive_units:
            if u is leader:
                continue
            if u.current_health >= u.profile.health:
                continue   # already at full HP
            if ability.aura_range > 0:
                if _distance(leader.position, u.position) > ability.aura_range:
                    continue
            candidates.append(u)

        recipient: Optional["Unit"] = None
        if candidates:
            # Pick the most-wounded; tie-break by proximity to the leader
            candidates.sort(
                key=lambda u: (
                    u.current_health,
                    _distance(leader.position, u.position),
                )
            )
            recipient = candidates[0]
        elif leader.current_health < leader.profile.health:
            recipient = leader

        if recipient is None:
            continue
        recipient.current_health = min(
            recipient.profile.health,
            recipient.current_health + ability.heal_per_round,
        )


# ---------------------------------------------------------------------------
# Round-end model revival (Apothecary Narthecium)
# ---------------------------------------------------------------------------

def apply_round_end_revival(army: "Army") -> None:
    """
    End-of-round revival: every alive leader with revive_destroyed_per_round > 0
    returns N destroyed friendly INFANTRY models to play. Models the 10e
    Apothecary's Narthecium ability:

        "While this model is leading a unit, in your Command phase, you can
         return 1 destroyed model (excluding CHARACTER models) to that unit."

    SwegHammer models multi-model squads as N separate single-model Units
    sharing a profile name, so "return 1 destroyed model" maps to "find a
    dead Unit of an in-aura profile and reset its current_health to max".

    Selection priority for the resurrection target:
      1. dead non-CHARACTER unit whose live peers (same profile.name) are
         within aura_range of the leader — prefer profile shared with the
         most live peers (proxy for the led unit);
      2. else any dead non-CHARACTER unit (within aura_range fallback);
      3. else no-op.

    The revived model reappears at the position of a living peer if available,
    otherwise next to the leader.
    """
    for leader in army.alive_units:
        ability = lookup_ability(leader.profile.name)
        if ability is None or ability.revive_destroyed_per_round <= 0:
            continue

        # Inventory dead vs live non-character INFANTRY by profile name. We
        # only consider profiles whose live peers (if any) are within aura
        # range of the leader, otherwise the led-unit constraint is meaningless.
        dead_by_profile: Dict[str, List["Unit"]] = {}
        alive_by_profile: Dict[str, List["Unit"]] = {}
        for u in army.units:
            if u is leader:
                continue
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" in kw:
                continue
            if "INFANTRY" not in kw:
                continue
            bucket = (alive_by_profile if u.is_alive else dead_by_profile)
            bucket.setdefault(u.profile.name, []).append(u)

        if not dead_by_profile:
            continue

        # Score profiles by number of live peers within aura range (ties
        # broken by total live peer count). A profile with no live peers
        # still qualifies as a fallback, but ranks below profiles with
        # at least one in-aura peer.
        def _profile_priority(profile_name: str) -> Tuple[int, int]:
            peers = alive_by_profile.get(profile_name, [])
            if ability.aura_range > 0:
                in_aura = sum(
                    1 for p in peers
                    if _distance(leader.position, p.position) <= ability.aura_range
                )
            else:
                in_aura = len(peers)
            return (in_aura, len(peers))

        candidate_profiles = sorted(
            dead_by_profile.keys(),
            key=_profile_priority,
            reverse=True,
        )

        revives_remaining = ability.revive_destroyed_per_round
        for profile_name in candidate_profiles:
            if revives_remaining <= 0:
                break
            pool = dead_by_profile[profile_name]
            live_peers = alive_by_profile.get(profile_name, [])
            anchor_pos: Tuple[float, float] = (
                live_peers[0].position if live_peers else leader.position
            )
            while pool and revives_remaining > 0:
                revived = pool.pop(0)
                revived.current_health = revived.profile.health
                revived.position = anchor_pos
                revives_remaining -= 1


def maybe_apply_celestine_revival(
    army: "Army",
    destroyed_unit: "Unit",
    rng,
) -> bool:
    """Saint Celestine — Miraculous Intervention (gated SWEG_SOROR_ABILITIES).

    Called from the simulator's destroy-unit hooks whenever a unit in `army`
    is killed. If the destroyed unit IS the Celestine model AND the gate is ON
    AND the once-per-battle guard has not fired yet, roll 1D6; on 2+ restore
    the model to full wounds in place.

    Returns True iff a revival occurred (so the caller can emit an event or
    log if needed). Returns False in all other cases (gate off, wrong unit,
    already used, roll failed).

    BSData v10.6.0 Imperium - Adepta Sororitas.cat.gz, ability id
    eee9-b689-1a73-742b (Miraculous Intervention):
    "The first time this unit's Celestine model is destroyed, roll one D6 at
    the end of the phase. On a 2+, set that Celestine model back up on the
    battlefield, as close as possible to where it was destroyed and not within
    Engagement Range of any enemy units, with its full wounds remaining."

    Cited as `simulator.celestine_miraculous_intervention`.
    """
    # Gate OFF by default.
    if __import__("os").environ.get("SWEG_SOROR_ABILITIES", "1") == "0":
        return False

    ability = lookup_ability(destroyed_unit.profile.name)
    if ability is None or not ability.self_revive_on_2plus:
        return False

    uid = destroyed_unit.uid
    used = getattr(army, "self_revive_used_uids", None)
    if used is None:
        # Army was created before this field existed (e.g. in isolated tests);
        # initialise lazily — fail-loud discipline does not apply to optional
        # runtime-created state that didn't exist in earlier builds.
        army.self_revive_used_uids = set()
        used = army.self_revive_used_uids

    if uid in used:
        # Already revived this unit once this battle; codex says "first time".
        return False

    used.add(uid)

    # Roll D6: on 2+ revive at full wounds in current position (approximate —
    # exact "as close as possible to where it was destroyed" maps to current
    # position in the simulator's grid).
    roll = rng.randint(1, 6)
    if roll >= 2:
        destroyed_unit.current_health = destroyed_unit.profile.health
        return True
    return False


def maybe_apply_yncarne_heal(
    killer: "Unit",
    killer_army: "Army",
    rng,
) -> int:
    """The Yncarne — Ethereal Form on-kill D3 wound regain.

    Called from each kill site in simulator.py (shooting, melee, Tank Shock,
    Counter-Offensive) when an enemy unit is destroyed. If the KILLER is The
    Yncarne and it carries heal_d3_on_kill=True, roll 1D3 and restore that
    many lost wounds to the Yncarne itself, capped at its starting wounds.

    Rule text (Wahapedia https://wahapedia.ru/wh40k10ed/factions/aeldari/The-Yncarne):
    "Ethereal Form: Each time this model destroys an enemy unit it regains up
    to D3 lost wounds."

    Trigger: the killer unit IS The Yncarne (the unit that dealt the killing
    blow). This is NOT battlefield-wide — only kills made by the Yncarne count.

    Returns the number of wounds actually restored (0 if not applicable or
    already at full wounds).

    Cited as `LeaderAbility.Ethereal Form`.
    """
    ability = lookup_ability(killer.profile.name)
    if ability is None or not ability.heal_d3_on_kill:
        return 0

    # No heal when already at full wounds.
    if killer.current_health >= killer.profile.health:
        return 0

    heal = rng.randint(1, 3)
    healed = min(heal, killer.profile.health - killer.current_health)
    killer.current_health += healed
    return healed
