"""
Curated per-faction tournament archetype templates.

Motivation
----------
`build_faction_random_army` picks units uniformly from a faction's full pool.
That biases lists toward whatever happens to be cheap-and-numerous in the
catalogue — for shooty factions like T'au and Aeldari, the resulting lists
end up disproportionately shooty relative to real tournament play. The
`evaluate_vs_meta` calibration showed T'au at ~+14 pts and Aeldari at ~+14
pts above real win-rate (~54.5% / 44.4%), and the most likely cause was the
random pool bias.

These archetypes are hand-picked from May 2026 tournament meta lists
(Warp Friends weekly aggregate, Goonhammer top-table writeups). Each
ARCHETYPES[faction][name] is a `{catalog_key: count}` dict that, when
instantiated by `build_archetype_army`, scales to fit a points budget.

References
----------
Lists below are simplified-but-representative versions of competitive lists
that recurred in May 2026 events. They are not GW-published "boxed
detachments" — they're empirical observations of what wins at 2k.

Design rules
------------
* Each archetype is a `{unit_catalog_key: count}` mapping.
* All keys MUST exist in `code.units.UNIT_CATALOG`. The `test_archetypes`
  suite enforces this and the catalogue-spot-check above was run when this
  file was authored.
* Counts are "ideal at 2000 pts" — `build_archetype_army` scales them down
  proportionally to fit smaller budgets.
* One archetype per major faction is enough for v1; multi-archetype factions
  can pick randomly.
"""

from __future__ import annotations

import random
from typing import Dict, Optional

from .army import Army
from .army_builder import is_epic_hero
from .detachments import pick_detachment_for_army
from .units import UNIT_CATALOG, UnitProfile


# ---------------------------------------------------------------------------
# Archetype templates.
#
# Numbers are calibrated to add up roughly to ~2000 pts of SwegHammer points
# in the current catalogue — the builder scales down for smaller budgets.
# ---------------------------------------------------------------------------

ARCHETYPES: Dict[str, Dict[str, Dict[str, int]]] = {
    "Adeptus Astartes": {
        "Gladius Strike Force": {
            "space_marines_intercessor_squad": 1,
            "space_marines_hellblaster_squad": 1,
            "space_marines_eradicator_squad": 1,
            "space_marines_aggressor_squad": 1,
            "space_marines_captain_in_terminator_armour": 1,
            "space_marines_apothecary": 1,
            "space_marines_repulsor": 1,
        },
    },
    "Necrons": {
        # iter16 — archetype trim. The previous template intent was right
        # (Overlord + 2 Warriors + 2 Immortals + 1 Lychguard + 2 Doomstalker
        # + 1 Scarab), but the post-template `_random_fill` was stacking
        # multiple MONSTER wreckers (e.g. C'tan Nightbringer 340pt +
        # Transcendent C'tan 325pt + Silent King 400pt, or Seraptek 540pt +
        # Tesseract Vault 425pt) into the same army, driving Necron archetype
        # WR to 91% vs real 53.2% (+37.8pt apex outlier in the tourney-
        # archetype eval baseline). Real-meta May 2026 Awakened Dynasty
        # tournament lists (Goonhammer "Necrons Detachment Focus — Awakened
        # Dynasty"; Frontline Gaming GT lists) seat the army on a SINGLE
        # C'tan wrecker (Nightbringer most often, occasionally Deceiver) +
        # 1x Doomstalker + 2-3x Warriors / Immortals BATTLELINE + Lychguard
        # bodyguard brick + 1x Lokhust Heavy Destroyers — never two MONSTERS
        # in the same list at 2000pt.
        #
        # Fix shape:
        #   * Add C'tan Nightbringer at count=1 to the template so the real-
        #     meta wrecker is seeded by design (340pt, single EPIC HERO).
        #     The (-template_count, -squad_cost) walk puts it after the
        #     count=2 BATTLELINE pair but before single-copy support, so it
        #     reliably lands in the seed at 1500pt+ budgets.
        #   * Drop Doomstalker count from 2 -> 1. Real tournament lists run
        #     one Doomstalker as a fire-support sniper; multiple is rare.
        #     A single template count lets random_fill add at most 1 more
        #     (per the iter2 BATTLELINE / iter16 MONSTER cap) for an upper
        #     bound of 2 Doomstalkers when the budget allows.
        #   * Add Lokhust Heavy Destroyers at count=1. Anti-tank fire option
        #     that featured in May 2026 GT top tables; without it the army
        #     leans on Doomstalker / Doomsday Ark for ranged AT, which the
        #     simulator under-models (BS3+ S20 D6 vs S14 D6 + sticky).
        #   * Reanimation Protocols wound-by-wound fix (commit a3798e3,
        #     iter14) is verified upstream — the +37.8pt outlier survives
        #     RP fix because the list COMPOSITION (multi-wrecker stack via
        #     random_fill, not RP over-firing) is the dominant driver.
        #
        # The MONSTER-keyword cap on `_random_fill` (added in iter16) ALSO
        # bounds across-name MONSTER stacking — Transcendent C'tan / Silent
        # King / Tesseract Vault / Seraptek can each be picked at most once
        # by random_fill, and only if the template doesn't already seed a
        # MONSTER with that exact profile name. Combined with the EPIC HERO
        # 1-per-army cap (iter10), this guarantees at most:
        #     1 template-seeded C'tan Nightbringer (EPIC HERO MONSTER) +
        #     N random_fill MONSTERs where N is bounded by the per-profile
        #     `template_count = 0` -> 0 fill rule for unseeded profiles.
        #
        # References:
        #   - https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        #   - https://www.goonhammer.com/the-goonhammer-tournament-cycle-2026-meta/
        #     (May 2026 Necron WR aggregate 53.2% across 4 events)
        #   - https://frontlinegaming.org/2026/05/ (Necron Awakened Dynasty
        #     RTT lists, Apr-May 2026, all 1-C'tan compositions)
        # iter16 tighter trim — Warriors and Immortals dropped to count=1
        # each (was 2). Real-meta May 2026 Awakened Dynasty tournament
        # lists (Goonhammer; Frontline; Stat Check) typically field ONE
        # 20-model Warriors brick plus 1-2 5-model Immortals squads, not
        # multiple Warriors squads of each. The BATTLELINE cap in
        # _random_fill binds at `max(1, template_count)` extra fill
        # picks, so count=1 caps Warriors and Immortals at 2 squads each
        # (template seed + 1 random_fill squad) instead of the previous
        # 4-squad ceiling that drove sim WR to 95% via Warrior OC spam
        # plus additional Immortal anti-infantry shooting.
        "Awakened Dynasty": {
            "necrons_necron_warriors": 1,
            "necrons_immortals": 1,
            "necrons_lychguard": 1,
            "necrons_overlord": 1,
            "necrons_c_tan_shard_of_the_nightbringer": 1,
            "necrons_canoptek_doomstalker": 1,
            "necrons_lokhust_heavy_destroyers": 1,
            "necrons_canoptek_scarab_swarms": 1,
        },
    },
    "Aeldari": {
        # Ynnari triumvirate Battle Host — May 2026 real-meta Aeldari lists
        # mandate the Yvraine + Yncarne EPIC HERO pairing as the Warlord
        # spine. The previous template seeded Farseer + Autarch only, which
        # under-evaluated the army by ~4pt vs real WR. Wraithguard is the
        # durable shooting brick that the Ynnari list builds around; Spirit-
        # seer is the cheap CHARACTER that escorts them.
        #
        # Template-count rationale: Yvraine + Yncarne are set to count=3 so
        # the (-template_count, -squad_cost) anchor sort puts them at the
        # very top of the seed walk, ahead of the count=2 Wraithguard tier.
        # _instantiate_template only seeds 1 copy per entry regardless of
        # count, so the inflated count is purely a sorting hint — it
        # guarantees the EPIC HERO pair lands before the 240pt Wraithguard
        # squad eats the 450pt seed slice at 1500pt budgets. (Yvraine/
        # Yncarne are also EPIC HERO so the 1-per-army cap is naturally
        # respected.)
        #
        # Reference: https://wahapedia.ru/wh40k10ed/factions/aeldari/
        "Battle Host": {
            "aeldari_ynnari_yvraine": 3,
            "aeldari_ynnari_the_yncarne": 3,
            "aeldari_craftworlds_spiritseer": 1,
            "aeldari_craftworlds_farseer": 1,
            "aeldari_craftworlds_wraithguard": 2,
            "aeldari_craftworlds_dire_avengers": 1,
            "aeldari_craftworlds_fire_dragons": 1,
            "aeldari_craftworlds_rangers": 1,
            "aeldari_craftworlds_wave_serpent": 1,
            "aeldari_craftworlds_falcon": 1,
        },
    },
    "Tyranids": {
        "Invasion Fleet": {
            "tyranids_termagants": 1,
            "tyranids_hormagaunts": 1,
            "tyranids_hive_tyrant": 1,
            "tyranids_zoanthropes": 1,
            "tyranids_exocrine": 1,
            "tyranids_carnifexes": 2,
            "tyranids_gargoyles": 1,
        },
    },
    "Orks": {
        "Waaagh!": {
            "orks_boyz": 2,
            "orks_meganobz": 1,
            "orks_warboss_in_mega_armour": 1,
            "orks_killa_kans": 1,
            "orks_tankbustas": 1,
            "orks_nobz": 1,
            "orks_deffkoptas": 1,
        },
    },
    "T'au Empire": {
        # iter16 — Renamed from "Kauyon" to "Mont'ka" to match the real-meta
        # detachment name (T'au's `DEFAULT_BY_FACTION['T'au Empire'] = 'montka'`
        # in code/detachments.py); the previous label was a misnomer (Kauyon
        # and Mont'ka are the two halves of the canonical "patient ambush /
        # killing blow" T'au doctrine pair — Mont'ka is the rounds-1-3
        # aggressive-firepower detachment SwegHammer actually fields).
        #
        # The May 2026 real meta T'au Mont'ka lists revolve around Riptide /
        # Triptide + Hammerhead Gunships + Broadsides + Crisis suits +
        # Strike-Team / Pathfinder Markerlight infantry. Sources:
        #   - Goonhammer "Competitive Innovations in 10th: Mont'ka Mash"
        #     parts 1-3 (https://www.goonhammer.com/competitive-innovations-
        #     in-10th-montka-mash-pt-1/): "the Mont'ka list brings back the
        #     Ion Hammerhead. These, coupled with Riptides, give you a lot of
        #     anti-marine body shooting"; Chase Campbell 3rd with Hammerhead+
        #     Riptide; Max Persson with Triptide; Jan-Hagen Rath Breacherfish/
        #     Triptide; Maksim Kravchenko Commander Farsight + Enforcer +
        #     Twin Lance + Broadsides.
        #   - Goonhammer "Competitive Innovations: T'au Take Over pt.2".
        #   - Frontline Gaming T'au tournament reports (Mont'ka archetype).
        #
        # iter16 brief diagnosed: sim 33.4% vs real 54.5% (-21.1pt). The
        # previous "Kauyon" template seeded Crisis-heavy + Riptide(c=1) but
        # MISSED THREE THINGS:
        #   (a) Riptide should be the headline anchor. Real Mont'ka builds
        #       run 2-3 Riptides ("Triptide"). Bumped to count=3 so the
        #       (-count,-cost) sort puts it at the very top of the seed walk
        #       and a Riptide always seeds at the 600pt slice (200pt fits).
        #   (b) Hammerhead Gunship was absent. Real meta May 2026 universally
        #       pairs Riptides with Ion / Railhead Hammerheads. count=2 so
        #       Hammerhead seeds at 145pt before lower-priority c=1 anchors.
        #   (c) Markerlight infantry seeding was rare. Pathfinder + Strike
        #       Team only seeded sometimes because they were c=1 at the tail
        #       of the walk; with the iter3 wiring of MONTKA.lethal_hits_on_
        #       guided, the chain DOES NOT FIRE without an alive MARKERLIGHT
        #       carrier in the army. Empirical N=10 seed sampling showed 5/10
        #       seeds with ZERO MARKERLIGHT units. Bumped Pathfinder Team and
        #       Strike Team to count=2 so both seed reliably (Strike Team is
        #       also the army's primary BATTLELINE chassis for OC).
        #
        # Companion overrides (data/overrides.json) for iter16 add the
        # MARKERLIGHT unit keyword to Strike Team, Breacher Team, and Sky Ray
        # Gunship — real 10e datasheets carry MARKERLIGHT on the unit keyword
        # line, but BSData encodes Markerlight on the weapon row only. Without
        # those overrides Strike-Team-anchored markerlight saturation would
        # still fail. Source: Wahapedia datasheet keyword lines.
        "Mont'ka": {
            "t_au_empire_riptide_battlesuit": 3,
            "t_au_empire_hammerhead_gunship": 2,
            "t_au_empire_crisis_fireknife_battlesuits": 2,
            "t_au_empire_crisis_sunforge_battlesuits": 2,
            "t_au_empire_broadside_battlesuits": 2,
            "t_au_empire_pathfinder_team": 2,
            "t_au_empire_strike_team": 2,
            "t_au_empire_commander_in_enforcer_battlesuit": 1,
            "t_au_empire_stormsurge": 1,
            "t_au_empire_ghostkeel_battlesuit": 1,
            "t_au_empire_stealth_battlesuits": 1,
            "t_au_empire_devilfish": 1,
        },
    },
    "Death Guard": {
        # iter13 — Renamed from "Plague Company" to match the real-meta
        # Virulent Vectorium detachment used by ~80% of competitive DG lists
        # in May 2026 events. Real meta lists almost universally pivot on
        # Mortarion as the EPIC HERO centerpiece + 1-2 Foetid Bloat-Drones
        # for fast cleave (Goonhammer DG meta writeups; Warp Friends weekly
        # aggregate). Adding them here shifts the archetype away from a
        # sticky-camping Plague-Marines-only list toward the real
        # centerpiece-stomping profile that the published WR (48%) reflects.
        "Virulent Vectorium": {
            "death_guard_mortarion": 1,
            "death_guard_foetid_bloat_drone": 2,
            "death_guard_plague_marines": 2,
            "death_guard_poxwalkers": 1,
            "death_guard_deathshroud_terminators": 1,
            "death_guard_plagueburst_crawler": 2,
            "death_guard_typhus": 1,
            "death_guard_foul_blightspawn": 1,
        },
    },
    "Adeptus Custodes": {
        "Shield Host": {
            "adeptus_custodes_custodian_guard": 2,
            "adeptus_custodes_allarus_custodians": 1,
            "adeptus_custodes_vertus_praetors": 1,
            "adeptus_custodes_shield_captain": 1,
            "adeptus_custodes_caladius_grav_tank": 1,
            "adeptus_custodes_prosecutors": 1,
        },
    },
    "Thousand Sons": {
        # iter16 — TSON archetype at iter15 was 35.5% sim vs 54.6% real
        # (-19.1pt). Investigation showed the template shape (Ahriman c=1
        # + Rubric c=2 + Scarab c=2 + Exalted Sorcerer + Infernal Master +
        # Tzaangors) is fine; the bug was upstream in detachment selection:
        # FACTION_DETACHMENTS["Thousand Sons"] holds both Rubricae Phalanx
        # AND Grand Coven, both `preferred_composition="infantry"`, so the
        # picker was a coin-flip and TSON armies got the wrong detachment
        # half the time, losing the All Is Dust durability buff.
        #
        # Fix lives in `code/detachments.py::_keyword_affinity_score` — a
        # new RUBRICAE-keyword affinity tilts the picker ~70/30 toward
        # Rubricae Phalanx when the army carries RUBRICAE-keyword units
        # (Rubric Marines, Scarab Occult Terminators). The template here
        # is unchanged from iter15 modulo this comment block.
        #
        # Experiments tried and rejected:
        #   - Seeding Ahriman explicitly (count=4 sort hint + SEED_FRACTION
        #     override 0.5): TSON 35.5% → 29.4%, regression of -6pt.
        #     Ahriman is a single-model EPIC HERO that gets focus-fired
        #     and contributes less per-pt than Exalted Sorcerer at this
        #     budget.
        #   - Seeding Scarab Occult Terminators (SEED_FRACTION=0.75 so
        #     396pt squad fits): TSON 35.5% → 28.6%, regression of -6.9pt.
        #     Scarab Occult chassis costs more pts than it contributes
        #     in damage-per-round under the current combat model at
        #     1000pt eval (real-meta TSON runs at 2000pt where Scarab
        #     Occult fits naturally; the 1000pt eval is hostile).
        #
        # Magnus the Red intentionally NOT in the template: 435pt would
        # crowd out the rest of the army at 1000pt. Real-meta Magnus
        # lists need 1500pt+ budget shape. Random_fill picks him up
        # organically at 2000pt evals.
        #
        # References (May 2026):
        #   - Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
        #   - 40k.app: https://www.40k.app/factions/thousand-sons/rules/detachment/rubricae-phalanx
        #   - Goonhammer "Detachment Focus: Rubricae Phalanx"
        #   - Frontline Gaming "Codex Focus: Thousand Sons"
        "Rubricae Phalanx": {
            "thousand_sons_ahriman": 1,
            "thousand_sons_rubric_marines": 2,
            "thousand_sons_scarab_occult_terminators": 2,
            "thousand_sons_exalted_sorcerer": 1,
            "thousand_sons_infernal_master": 1,
            "thousand_sons_tzaangors": 1,
        },
    },
    "Leagues of Votann": {
        "Oathband": {
            "leagues_of_votann_hearthkyn_warriors": 2,
            "leagues_of_votann_einhyr_hearthguard": 1,
            "leagues_of_votann_hernkyn_pioneers": 1,
            "leagues_of_votann_cthonian_beserks": 1,
            "leagues_of_votann_br_khyr_iron_master": 1,
            "leagues_of_votann_sagitaur": 1,
        },
    },
    "Drukhari": {
        # Skysplinter Assault — the flagship Drukhari detachment in 10e May
        # 2026 meta. Doctrine is mounted-everything: every infantry block
        # embarks in a Raider or Venom, deep-strike support from Mandrakes
        # and Scourges, anti-tank from Ravager triples, melee killtile from
        # Incubi + Lelith. Archon is the standard CHARACTER anchor; Lelith
        # joins as the EPIC HERO option that leads a Wyches/Incubi bomb.
        # Multi-copy entries (Raider=4, Kabalites=2, Wyches=2, Incubi=2,
        # Venom=2) are deliberate — these are the spine of the archetype
        # and the (-template_count, -squad_cost) sort guarantees they seed
        # before single-copy support like the Cronos / Ravager.
        #
        # Reference: https://wahapedia.ru/wh40k10ed/factions/drukhari/
        "Skysplinter Assault": {
            "aeldari_drukhari_archon": 1,
            "aeldari_drukhari_lelith_hesperax": 1,
            "aeldari_drukhari_kabalite_warriors": 2,
            "aeldari_drukhari_wyches": 2,
            "aeldari_drukhari_incubi": 2,
            "aeldari_drukhari_mandrakes": 1,
            "aeldari_drukhari_reavers": 1,
            "aeldari_drukhari_scourges_with_shardcarbines": 1,
            "aeldari_drukhari_raider": 4,
            "aeldari_drukhari_venom": 2,
            "aeldari_drukhari_ravager": 1,
            "aeldari_drukhari_cronos": 1,
        },
    },
}


def has_archetype(faction: str) -> bool:
    """True if `faction` has at least one curated archetype template."""
    return faction in ARCHETYPES and bool(ARCHETYPES[faction])


def _squad_cost(key: str) -> float:
    """SwegHammer cost of one min-sized squad of profile `key`."""
    profile = UNIT_CATALOG[key]
    return profile.points_cost * max(1, profile.min_models)


# Fraction of the budget that the curated template seeds. The rest is left
# free for `_random_fill` to top up with same-faction picks, which keeps
# the post-archetype calibration close to the random-list baseline (the
# random builder was empirically near-balanced on most factions before this
# patch — the bias was in pool composition, not total point spend).
SEED_FRACTION: float = 0.3

# Per-faction SEED_FRACTION override. Some factions' archetype anchor units
# are expensive enough that the default 0.3 slice (300pt of 1000pt eval
# budget) cannot fit even ONE flagship squad, leaving the army to be filled
# by off-flavour random_fill picks. Raise the slice for those factions only.
#
# Currently empty: iter16 experimented with a 0.5 / 0.75 slice for Thousand
# Sons (to seed Ahriman + Scarab Occult Terminators) but both regressed sim
# WR vs iter15's 0.3 default (35.5% → 28.6% at 0.75). The Scarab Occult
# chassis costs more pts than it contributes in damage-per-round under the
# current combat model at 1000pt eval. iter16's actual TSON win is the
# RUBRICAE-keyword detachment picker affinity (code/detachments.py).
SEED_FRACTION_BY_FACTION: Dict[str, float] = {}


def _instantiate_template(
    template: Dict[str, int],
    points_budget: float,
    rng: random.Random,
    faction: Optional[str] = None,
) -> Dict[str, int]:
    """
    Scale template counts so the resulting army's template-seeded portion
    fits inside `SEED_FRACTION * points_budget`. The remaining headroom is
    filled by `_random_fill` with same-faction picks at army-build time.

    `faction` (optional) selects a per-faction SEED_FRACTION override from
    `SEED_FRACTION_BY_FACTION` — used for factions whose anchor units are
    too expensive for the default 0.3 slice. Currently empty (no overrides
    in production) — see SEED_FRACTION_BY_FACTION for iter16 experiment
    notes.

    Why a partial seed:
      A 100% template-seeded army produced ~24-pt MAE in eval-vs-meta
      because some faction catalogues have lopsided costs (Aeldari Aspect
      Warriors are very expensive, Tyranid Termagants are very cheap) and a
      tournament-list template doesn't compensate. Seeding 60% of the
      budget with the curated template (so the army's CHARACTER + flavour
      units are present) and filling the rest randomly keeps the overall
      cost-per-model close to the random baseline while still biasing list
      composition.
    """
    if not template or points_budget <= 0:
        return {}

    seed_fraction = SEED_FRACTION_BY_FACTION.get(faction or "", SEED_FRACTION)
    seed_budget = points_budget * seed_fraction

    # Walk the template in (-template_count, -squad_cost) order so that
    # archetype-defining units land first:
    #   * Multi-copy entries (e.g. Rubric Marines @ count=2) outrank
    #     single-copy entries — they're the spine of the archetype.
    #   * Within the same template count, instantiate the more expensive
    #     squad first so flagship anchors (Wraithguard, Falcon, Scarab
    #     Occult Terminators) are seeded before chaff that could otherwise
    #     soak the budget cheaply.
    #
    # Previously this walked cheapest-first, which meant a 1000pt seed
    # (SEED_FRACTION*1000 = 300pt) exhausted on Tzaangors (70pt) +
    # Sorcerer (80pt) + Infernal Master (95pt) and never reached the
    # Rubric Marine entry. See task #170.
    #
    # We instantiate exactly one squad per template entry here — extra
    # copies past 1 are left to `_random_fill`, which keeps the seeded
    # slice tight and lets the random topup handle distribution.
    def sort_key(key: str):
        return (-template.get(key, 0), -_squad_cost(key))

    scaled: Dict[str, int] = {}
    running = 0.0
    for key in sorted(template, key=sort_key):
        cost = _squad_cost(key)
        if running + cost <= seed_budget:
            scaled[key] = 1
            running += cost
        # else: skip — too expensive at this budget. Cheaper subsequent
        # entries may still fit, so keep walking rather than break.

    # iter #11 — CHARACTER-anchor guarantee. The (-count, -cost) walk above
    # can exhaust the seed budget on a multi-copy BATTLELINE entry at low
    # budgets (e.g. TSON Rubric Marines @ count=2 takes 240pt of a 300pt
    # seed at 1000pt), leaving no headroom for the army's CHARACTER /
    # PSYKER anchor. Real tournament archetypes are built around their
    # character spine; if none seeded, force the cheapest template
    # CHARACTER in even if it overflows `seed_budget` slightly. The
    # overflow is bounded by `1.5 * seed_budget` so we don't blow past the
    # random_fill headroom at small budgets. Faction-neutral — any
    # template entry with the CHARACTER keyword qualifies.
    def _has_character(key: str) -> bool:
        profile = UNIT_CATALOG.get(key)
        if profile is None:
            return False
        return "CHARACTER" in (profile.unit_keywords or ())

    any_char_seeded = any(_has_character(k) for k in scaled)
    if not any_char_seeded:
        char_keys = [k for k in template if _has_character(k)]
        if char_keys:
            # Cheapest CHARACTER first so the overflow is minimal.
            cheapest_char = min(char_keys, key=_squad_cost)
            cost = _squad_cost(cheapest_char)
            if running + cost <= seed_budget * 1.5:
                scaled[cheapest_char] = 1
                running += cost

    return scaled


def _random_fill(
    army: Army,
    faction: str,
    remaining_budget: float,
    rng: random.Random,
    template: Optional[Dict[str, int]] = None,
) -> None:
    """
    Top up `army` with random faction picks until `remaining_budget` is
    exhausted. Mirrors the legacy `build_faction_random_army` per-pick logic
    (size=max_models, cap=remaining/2 per type) so the filler portion is
    statistically equivalent to the pre-archetype baseline.

    BATTLELINE squad cap (task #179):
      For any BATTLELINE-keyword profile P, random_fill is capped at
      `max(1, template_count(P))` additional squad picks, so the total
      squads-of-P in the army (template + random_fill) is bounded at
      `2 * template_count(P)` when P is in the template, else 1.

      Rationale: BATTLELINE profiles are the OC-on-objectives spine of
      the army; the F5 / F5b Marines audit traced a +17pt over-perform to
      `random_fill` stacking Intercessor squads on top of the templated
      seed (deterministic 20+ OC floor). The cap is faction-neutral —
      Necron Warriors (template=2) and Tyranid Termagants (template=1)
      still seed at their archetype's intended density; only profiles
      that aggregate beyond 2x the template intent are throttled. Non-
      BATTLELINE roles (HQ / ELITE / FAST_ATTACK / HEAVY / DEDICATED
      TRANSPORT) use the unchanged per-type point cap.

    MONSTER / TITANIC / EPIC HERO cap (iter16):
      Mirror of the BATTLELINE cap, applied to any profile with the
      MONSTER, TITANIC, or EPIC HERO keyword. For an unseeded wrecker
      profile (not in the template), random_fill picks 0 squads — pre-
      venting multi-wrecker stacking like the iter15 Necron Awakened
      Dynasty list which regularly drafted Transcendent C'tan + Tesseract
      Vault + Seraptek Heavy Construct alongside the template-seeded
      C'tan Nightbringer via fill, driving sim WR to 91% vs real 53.2%.
      The Silent King (VEHICLE + EPIC HERO + CHARACTER, 400pt) is caught
      by the EPIC HERO leg — without it, random_fill would still stack
      Silent King alongside a template-seeded Nightbringer.

      Profiles that ARE in the template (Tyranid Carnifex count=2, Hive
      Tyrant count=1, Exocrine count=1, DG Mortarion count=1, Drukhari
      Lelith count=1) still get `template_count` extra fill picks, so a
      Tyranid Invasion Fleet list can field up to 2*template_count of
      each MONSTER — matching the real-meta "MONSTER spam Tyranids"
      profile that the Invasion Fleet detachment is built around. The
      EPIC HERO leg composes with the existing per-name is_epic_hero
      check (10e core, 1 copy per EH datasheet per army): templated EHs
      can't be re-picked, AND unseeded EHs can't be introduced.

      Faction-neutral by keyword: applies to every codex's MONSTERs and
      EHs (Aeldari Wraithlord/Wraithknight + Yvraine/Yncarne, T'au
      Stormsurge/Riptide + Shadowsun, DG Mortarion/Plagueburst + Typhus,
      Custodes Telemon + Trajann, Marines Redemptor + Calgar) and gates
      by template intent rather than faction-specific allowlists.

    [Legends] / [Crucible] exclusion (iter16):
      Profiles whose display name contains "[Legends]" or "[Crucible]"
      are filtered out of the random_fill pool entirely. These are non-
      tournament profiles per GW's 10e ruleset and shouldn't appear in
      the calibration target (the eval-vs-meta WR data is derived from
      tournament events that exclude Legends datasheets). Template-
      seeded units are unaffected — if a future archetype explicitly
      wants a Legends entry, the template still seeds it, but the random
      fill won't pad with random Legends profiles like the iter15 trace
      that drafted Nemesor Zahndrekh, Anrakyr the Traveller, Tesseract
      Ark, Night Shroud, and Vargard Obyron into the Necron fill pass.

      Faction-neutral by display-name suffix — applies to all 445
      Legends/Crucible profiles across the catalogue.
    """
    pool = [
        UNIT_CATALOG[k] for k in UNIT_CATALOG
        if UNIT_CATALOG[k].faction == faction
        and "[Legends]" not in UNIT_CATALOG[k].name
        and "[Crucible]" not in UNIT_CATALOG[k].name
    ]
    if not pool:
        return

    # Map profile.name -> template count of its catalogue key. We index by
    # display name so the per-pick check (which has the profile in hand)
    # doesn't need to round-trip back to the catalogue key.
    template = template or {}
    template_count_by_name: Dict[str, int] = {}
    for key, count in template.items():
        prof = UNIT_CATALOG.get(key)
        if prof is not None:
            template_count_by_name[prof.name] = count

    spent_by_name: Dict[str, float] = {}
    fill_squads_by_name: Dict[str, int] = {}
    cap = remaining_budget * 0.5

    # 10e core EPIC HERO 1-per-army cap. Seed the tracker with any epic
    # heroes already present in the army from the template seed, so the
    # fill pass cannot duplicate a hero that the archetype already drafted.
    epic_heroes_taken: set = {
        u.profile.name for u in army.units if is_epic_hero(u.profile)
    }

    while remaining_budget > 0:
        affordable = []
        for p in pool:
            if is_epic_hero(p) and p.name in epic_heroes_taken:
                continue
            size = max(1, p.max_models)
            cost = p.points_cost * size
            if cost > remaining_budget:
                continue
            if spent_by_name.get(p.name, 0.0) + cost > cap:
                continue
            # BATTLELINE cap: bound random_fill picks per BATTLELINE profile
            # at max(1, template_count). Profiles outside the template are
            # allowed 1 fill pick (so the random topup can still introduce
            # variety without stacking OC).
            if "BATTLELINE" in (p.unit_keywords or ()):
                bl_cap = max(1, template_count_by_name.get(p.name, 0))
                if fill_squads_by_name.get(p.name, 0) >= bl_cap:
                    continue
            # MONSTER / TITANIC / EPIC HERO cap (iter16): bound random_fill
            # picks per wrecker profile at template_count (no implicit +1 —
            # an unseeded wrecker gets 0 fill picks). This stops the multi-
            # wrecker stacking that drove Necron Awakened Dynasty to sim
            # 91% (Transcendent C'tan + Tesseract Vault + Seraptek + Silent
            # King all picked into the same army's random_fill pass).
            #
            # Including EPIC HERO is intentional: it stops unseeded centre-
            # piece characters from being introduced by random_fill (e.g.
            # The Silent King wasn't in the Necron template but kept landing
            # in fills as a 400pt Vehicle EH wrecker alongside the templated
            # Nightbringer). Profiles that ARE in the template (DG Mortarion
            # count=1, Drukhari Lelith count=1) are still seeded; the
            # existing per-name is_epic_hero check prevents duplicate fills
            # of an already-seeded EH datasheet (10e core rule). The MONSTER
            # cap composes with that: a templated EH won't be re-picked, and
            # an unseeded EH won't be introduced at all.
            #
            # Profiles that ARE in the template (e.g. Tyranid Carnifex
            # count=2 with MONSTER keyword) still get up to `template_count`
            # extra fill picks, so MONSTER-spam Tyranids still build their
            # real-meta shape.
            kw = p.unit_keywords or ()
            if "MONSTER" in kw or "TITANIC" in kw or "EPIC HERO" in kw:
                wrecker_cap = template_count_by_name.get(p.name, 0)
                if fill_squads_by_name.get(p.name, 0) >= wrecker_cap:
                    continue
            affordable.append((p, size, cost))
        if not affordable:
            break
        chosen, size, cost = rng.choice(affordable)
        for _ in range(size):
            army.add_unit(chosen)
        spent_by_name[chosen.name] = spent_by_name.get(chosen.name, 0.0) + cost
        fill_squads_by_name[chosen.name] = fill_squads_by_name.get(chosen.name, 0) + 1
        remaining_budget -= cost
        if is_epic_hero(chosen):
            epic_heroes_taken.add(chosen.name)


def build_archetype_army(
    name: str,
    faction: str,
    points_budget: float,
    rng: Optional[random.Random] = None,
    in_cover: bool = False,
    archetype_name: Optional[str] = None,
) -> Army:
    """
    Build an army from a curated archetype template for `faction`, then top
    up the remaining budget with random same-faction picks via
    `_random_fill`.

    If `archetype_name` is None, picks one at random from the faction's
    available archetypes. Raises KeyError if the faction has no archetype —
    callers should gate with `has_archetype(faction)` first.

    Squad sizes default to BSData min_models for the template-seeded
    portion (MSU style, since the templates reflect the CHARACTER + flavour
    spine of competitive lists). Random fill uses max_models squads to
    match legacy `build_faction_random_army` behaviour and keep total cost
    near budget.
    """
    if rng is None:
        rng = random.Random()
    if not has_archetype(faction):
        raise KeyError(f"No archetype defined for faction {faction!r}")

    available = ARCHETYPES[faction]
    if archetype_name is None:
        archetype_name = rng.choice(list(available.keys()))
    template = available[archetype_name]

    counts = _instantiate_template(template, points_budget, rng, faction=faction)

    army = Army(name, in_cover=in_cover)
    for key, count in counts.items():
        profile: UnitProfile = UNIT_CATALOG[key]
        squad_size = max(1, profile.min_models)
        for _ in range(count):
            for _ in range(squad_size):
                army.add_unit(profile)

    # Fill the remaining budget with random same-faction picks. Keeps the
    # archetype's flavour seed but lets the total cost converge to the
    # pre-archetype calibration baseline. Passes `template` so the fill
    # path can apply the BATTLELINE squad cap (task #179) — random_fill
    # may add at most `max(1, template_count(P))` extra squads for any
    # BATTLELINE profile P.
    remaining = points_budget - army.total_points
    if remaining > 0:
        _random_fill(army, faction, remaining, rng, template=template)

    if army.units:
        army.detachment = pick_detachment_for_army(faction, army.units, rng)

    return army
