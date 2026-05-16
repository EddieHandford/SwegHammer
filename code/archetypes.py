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
        "Awakened Dynasty": {
            "necrons_necron_warriors": 2,
            "necrons_immortals": 2,
            "necrons_lychguard": 1,
            "necrons_overlord": 1,
            "necrons_canoptek_doomstalker": 2,
            "necrons_canoptek_scarab_swarms": 1,
        },
    },
    "Aeldari": {
        "Battle Host": {
            "aeldari_craftworlds_dire_avengers": 1,
            "aeldari_craftworlds_guardian_defenders": 1,
            "aeldari_craftworlds_rangers": 1,
            "aeldari_craftworlds_fire_dragons": 1,
            "aeldari_craftworlds_wraithguard": 1,
            "aeldari_craftworlds_farseer": 1,
            "aeldari_craftworlds_autarch": 1,
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
        # Kauyon-style battlesuit-heavy list. The May 2026 real meta T'au lists
        # (Warp Friends weekly, Goonhammer top tables) revolve around Crisis
        # suits + Riptide + Broadsides + occasional Stormsurge — markerlight
        # infantry and Pathfinders are support, not the spine. The previous
        # template seeded only Strike/Breacher/Pathfinder + one Crisis, which
        # made calibrated T'au lists shoot like a Fire Warrior army (~ -4.9pt
        # under-perform). Task #174.
        #
        # Multi-copy entries here are deliberate: with the post-G5 anchor-first
        # sort (-template_count, -squad_cost), Crisis Fireknife (c=3) and
        # Sunforge (c=2) seed before single-copy entries, ensuring the army
        # spine is battlesuit-dominated even at the 30%-of-budget seed slice.
        "Kauyon": {
            "t_au_empire_crisis_fireknife_battlesuits": 3,
            "t_au_empire_crisis_sunforge_battlesuits": 2,
            "t_au_empire_broadside_battlesuits": 2,
            "t_au_empire_riptide_battlesuit": 1,
            "t_au_empire_stormsurge": 1,
            "t_au_empire_ghostkeel_battlesuit": 1,
            "t_au_empire_stealth_battlesuits": 1,
            "t_au_empire_commander_in_enforcer_battlesuit": 1,
            "t_au_empire_pathfinder_team": 1,
            "t_au_empire_strike_team": 1,
            "t_au_empire_devilfish": 1,
        },
    },
    "Death Guard": {
        "Plague Company": {
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
        "Cult of Magic": {
            "thousand_sons_rubric_marines": 2,
            "thousand_sons_scarab_occult_terminators": 1,
            "thousand_sons_tzaangors": 1,
            "thousand_sons_exalted_sorcerer": 1,
            "thousand_sons_infernal_master": 1,
            "thousand_sons_helbrute": 1,
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


def _instantiate_template(
    template: Dict[str, int],
    points_budget: float,
    rng: random.Random,
) -> Dict[str, int]:
    """
    Scale template counts so the resulting army's template-seeded portion
    fits inside `SEED_FRACTION * points_budget`. The remaining headroom is
    filled by `_random_fill` with same-faction picks at army-build time.

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

    seed_budget = points_budget * SEED_FRACTION

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
    """
    pool = [UNIT_CATALOG[k] for k in UNIT_CATALOG if UNIT_CATALOG[k].faction == faction]
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

    counts = _instantiate_template(template, points_budget, rng)

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
