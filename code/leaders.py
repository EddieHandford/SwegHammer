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
    reroll_wound_ones: bool = False
    plus_one_to_hit: bool = False
    plus_one_to_wound: bool = False
    plus_one_attack: int = 0                # +N extra attacks per weapon (Cadre Fireblade etc.)
    # Defensive modifiers (apply to DEFENDER when it's in range of this leader)
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
    # Adeptus Custodes Shield-Captain — per the Wahapedia / BSData v10.6.0
    # Shield-Captain datasheet, the Leader ability lists Custodian Guard
    # and Custodian Wardens as the only legal hosts. The previous
    # host_keys tuple omitted Wardens, which silently blocked Stoic Vigil
    # from firing on a Wardens-led squad — half the Custodes archetype's
    # leader-target population. iter24 fix expands the tuple to both legal
    # hosts (also including the Adrasite/Pyrithite spear variant of
    # Custodian Guard, which BSData groups under the same Leader entry).
    # Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/Shield-Captain
    ("Shield-Captain",     LeaderAbility(name="Stoic Vigil",                aura_range=6.0, reroll_hit_ones=True,
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
    # Necrons — named characters first so they win the substring match
    # before the generic "Overlord" entry below.
    ("Trazyn the Infinite", LeaderAbility(name="Surreptitious Acquisition", aura_range=6.0, plus_one_to_hit=True,
                                          cp_refund_per_battle=1,
                                          host_keys=_NECRON_HOSTS)),
    ("Overlord",           LeaderAbility(name="My Will Be Done",            aura_range=6.0, plus_one_to_hit=True,  host_keys=_NECRON_HOSTS)),
    ("Chronomancer",       LeaderAbility(name="Chronometron",               aura_range=6.0, fnp=5,                 host_keys=_NECRON_HOSTS)),
    ("Plasmancer",         LeaderAbility(name="Harbinger of Destruction",   aura_range=6.0, fnp=5,                 host_keys=("necrons_immortals", "necrons_necron_warriors"))),
    ("Technomancer",       LeaderAbility(name="Canoptek Cloak",             aura_range=6.0, fnp=5,                 host_keys=_NECRON_HOSTS)),
    # Orks
    ("Warboss",            LeaderAbility(name="Might is Right",             aura_range=6.0, plus_one_to_hit=True,   host_keys=("orks_boyz", "orks_nobz"))),
    # Tyranids — Hive Tyrant is a Monster with NO formal Leader/Bodyguard
    # attachment in 10e. The codex Onslaught aura reads "While a friendly
    # TYRANIDS unit is within 6" of this model, ranged weapons equipped by
    # models in that unit have the [ASSAULT] and [LETHAL HITS] abilities."
    # — broadcast aura with no led-unit gate. Use the iter22 empty-tuple
    # convention so `effective_buffs` applies the reroll-wound-1s proxy
    # to ANY friendly Tyranids attacker in 6", not just one bodyguard
    # squad. Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/tyranids/Hive-Tyrant
    ("Hive Tyrant",        LeaderAbility(name="Synaptic Imperative",        aura_range=6.0, reroll_wound_ones=True)),
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
    # The Yncarne (Ynnari EPIC HERO, MONSTER) — Ethereal Form regains D3
    # wounds each time it destroys an enemy unit; we proxy as
    # heal_per_round=2 (D3 median = 2) channelled at round end through
    # apply_round_end_healing, which prefers the most-wounded friendly in
    # aura but falls back to the leader itself — the latter case maps to
    # the codex's self-heal behaviour. Inevitable Death (reactive teleport
    # on Aeldari unit death) is NOT modelled — the simulator has no
    # reactive-relocation hook. Listed AFTER Yvraine so substring lookup
    # on "The Yncarne" doesn't collide with any generic match. Yncarne is
    # a Monster — no formal leader attachment (host_keys empty). Cited as
    # LeaderAbility."Ethereal Form".
    #
    # iter17 note: dropped Yvraine from the Aeldari archetype template
    # (the Word-of-the-Phoenix revive_destroyed_per_round=2 was compounding
    # with Yncarne's heal under the round-end pipeline, pushing Aeldari sim
    # to 55.6% vs real 44.4%). With Yvraine gone, Yncarne's heal_per_round
    # is left at the iter15 value (D3 median = 2).
    #
    # iter21 fab audit: dropped the +1-to-hit aura. The previous citation
    # admitted plus_one_to_hit=True was "a loose threat-mobility proxy for
    # the teleport's tactical upside" with NO basis in either Ethereal Form
    # (a self-heal-on-kill) or Inevitable Death (a reactive teleport).
    # Same pattern iter20 dropped from Necron Overlord and Typhus — proxy
    # flag approximating a rule that does not, in fact, grant an aura buff.
    # The heal_per_round=2 stays (legitimate D3-median proxy of the
    # codex's on-kill regain).
    ("The Yncarne",        LeaderAbility(name="Ethereal Form",              aura_range=6.0, heal_per_round=2)),
    ("Farseer",            LeaderAbility(name="Runes of Fate",              aura_range=6.0, reroll_wound_ones=True, host_keys=_AELDARI_GUARDIAN_HOSTS)),
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
    ("Commander in",       LeaderAbility(name="Coordinated Fire Plan",      aura_range=6.0, plus_one_to_hit=True)),  # Battlesuit, no INFANTRY host
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
    #   - Exalted Sorcerer / Sorcerer: Arcane Shield (Psychic) grants the
    #     led unit a 4+ invulnerable save. Modelled as extra_invuln=4.
    #   - Infernal Master: Malefic Maelstrom (Psychic) grants the led
    #     unit [SUSTAINED HITS 1]. Modelled as sustained_hits proxy via
    #     reroll_hit_ones (an offensive shooting buff in the same scale).
    ("Ahriman",            LeaderAbility(name="Arch-Sorcerer of Tzeentch",  aura_range=6.0, extra_invuln=4,
                                          host_keys=("thousand_sons_rubric_marines",
                                                     "thousand_sons_tzaangor_enlightened"))),
    ("Exalted Sorcerer",   LeaderAbility(name="Arcane Shield",              aura_range=6.0, extra_invuln=4,
                                          host_keys=("thousand_sons_rubric_marines",))),
    ("Infernal Master",    LeaderAbility(name="Malefic Maelstrom",          aura_range=6.0, reroll_hit_ones=True,
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
    # the Sorcerer's chosen target unit each Shooting phase — proxied
    # here as a unit-wide plus_one_to_hit aura on the led Scarab squad
    # (strictly stronger than codex since the codex is per-target per-
    # phase; the aura uplift compensates for our missing target-indexed
    # buff plumbing and lands the Scarab Occult Terminators' real
    # offensive ceiling in vs-meta calibration). Listed AFTER plain
    # "Sorcerer" would lose substring tie — must come BEFORE the generic
    # CSM "Sorcerer" entry so this longer key wins lookup. Wahapedia
    # source: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/Sorcerer-In-Terminator-Armour
    ("Sorcerer in Terminator Armour", LeaderAbility(name="Marked by Fate",   aura_range=6.0, plus_one_to_hit=True,
                                          host_keys=("thousand_sons_scarab_occult_terminators",))),
    # Chaos Space Marines (legacy "Chaos Space Marines squad" not in 10e BSData;
    # use the closest battleline that is, otherwise let the heuristic decide.)
    ("Sorcerer",           LeaderAbility(name="Prescience",                 aura_range=6.0, fnp=5,
                                          host_keys=("chaos_space_marines_traitor_guardsmen_squad",
                                                     "chaos_space_marines_cultist_mob"))),
    ("Dark Apostle",       LeaderAbility(name="Profane Litanies",           aura_range=6.0, reroll_hit_ones=True,
                                          host_keys=("chaos_space_marines_cultist_mob",))),
    ("Chaos Lord",         LeaderAbility(name="Lord of Hosts",              aura_range=6.0, plus_one_to_wound=True,
                                          host_keys=("chaos_space_marines_traitor_guardsmen_squad",))),
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
    # on the led unit (Pink Horrors / Blue Horrors). SwegHammer's LeaderAbility
    # has no `sustained_hits` flag, so this is proxied with `reroll_hit_ones=True`
    # — the same proxy already used for TSON Infernal Master's [SUSTAINED HITS 1]
    # grant (see line ~347 above). Direction-correct: both expand the per-hit-
    # roll value, just via different math (reroll-1s = +1/6 hits, sustained-1 on
    # a 6 = +1/6 hits). Citation flagged "(approximation)".
    ("Changecaster",       LeaderAbility(name="Changecaster's Locus",       aura_range=6.0, reroll_hit_ones=True,
                                          host_keys=("chaos_daemons_library_pink_horrors",))),
    # Contorted Epitome — Swallow Energy (Psychic) grants the led Daemonettes
    # FNP 4+ vs mortal wounds and Psychic Attacks. SwegHammer does not tag
    # attacks as PSYCHIC, so FNP 4 is applied army-wide (per the iter15
    # Librarian pattern: defensive proxy, strictly stronger than the codex's
    # restricted-trigger 4+ FNP). Horrible Fascination is a once-per-game
    # opponent-Shooting-phase ritual with no aura-flag plumbing; skipped.
    ("Contorted Epitome",  LeaderAbility(name="Swallow Energy",             aura_range=6.0, fnp=4,
                                          host_keys=("chaos_daemons_library_daemonettes",))),
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
    # the longer name wins the substring lookup. "Master of the Forge" once-
    # per-battle CP bonus + a baseline reroll-1s offensive aura (codex grants
    # full hit re-rolls on Cawl's unit; reroll-1s is the loose proxy).
    ("Belisarius Cawl",    LeaderAbility(name="Master of the Forge",        aura_range=6.0, reroll_hit_ones=True,
                                          cp_refund_per_battle=1,
                                          host_keys=("adeptus_mechanicus_skitarii_vanguard",
                                                     "adeptus_mechanicus_skitarii_rangers"))),
    ("Tech-Priest Dominus", LeaderAbility(name="Master of the Machine",    aura_range=6.0, reroll_hit_ones=True, heal_per_round=1,
                                          host_keys=("adeptus_mechanicus_skitarii_vanguard",
                                                     "adeptus_mechanicus_skitarii_rangers"))),
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
    ("Archon",             LeaderAbility(name="Overlord of Commorragh",     aura_range=6.0, plus_one_to_hit=True,
                                          host_keys=("aeldari_drukhari_kabalite_warriors",))),
    ("Succubus",           LeaderAbility(name="Precision Blows",            aura_range=6.0, reroll_hit_ones=True,
                                          host_keys=("aeldari_drukhari_wyches",))),
    # Genestealer Cults
    ("Primus",             LeaderAbility(name="Meticulous Uprising",       aura_range=6.0, reroll_hit_ones=True,
                                          host_keys=("genestealer_cults_neophyte_hybrids",
                                                     "genestealer_cults_acolyte_hybrids_with_autopistols"))),
    # Leagues of Votann
    ("Kâhl",               LeaderAbility(name="Warrior-Forged Leadership",  aura_range=6.0, plus_one_to_hit=True,
                                          host_keys=("leagues_of_votann_hearthkyn_warriors",))),
)


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
    "reroll_wound_ones": False,
    "plus_one_to_hit": False,
    "plus_one_to_wound": False,
    "plus_one_attack": 0,
    "plus_one_save": False,
    "extra_invuln": 7,
    "fnp": 7,
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
        _merge_bool(buffs, ability, "reroll_hit_ones")
        _merge_bool(buffs, ability, "reroll_wound_ones")
        _merge_bool(buffs, ability, "plus_one_to_hit")
        _merge_bool(buffs, ability, "plus_one_to_wound")
        _merge_add(buffs, ability, "plus_one_attack")
        _merge_min(buffs, ability, "extra_invuln")
        _merge_min(buffs, ability, "fnp")

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
