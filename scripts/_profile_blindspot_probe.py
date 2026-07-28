"""How many units does the advance-suppression filter mis-classify?

The shared gunline-hold filter reads ranged damage per activation and range from
each unit's PRIMARY weapon profile only. Task #49 found this live: the Emperor's
Children Defiler was documented as "NOT held ... despite it being the observed
stand-out misplay", because its primary profile is a short-range torrent while
its real firepower is a 48-inch battle cannon on a SECONDARY profile.

That blind spot is not Emperor's Children specific. The filter is shared by
EIGHT entry points on the same block, and SIX of them are default-on - Astra
Militarum, Chaos Knights, Leagues of Votann, Thousand Sons, Adepta Sororitas and
Adeptus Astartes - so whatever it mis-classifies is mis-classified in production
right now.

This measures it across the whole catalogue. For each unit it computes the
filter verdict from the primary profile, then from the BEST of the primary and
every extra ranged profile, and reports where the two disagree:

  MISSED    not held on the primary, held on a better profile. The Defiler
            shape: a real fire platform the filter cannot see, free to Advance
            and waste its shooting.
  SPURIOUS  held on the primary but not on any better profile. Would mean the
            primary overstates the unit, which the mapper makes unlikely.

Extra profiles are PARTIAL overrides of the primary, so each is merged onto the
primary's values rather than read standalone - a swap carrying only `attacks`
and `range_inches` still inherits the primary's damage and hit probability.

IT READS BUILT ARMIES, NOT UNIT_CATALOG, AND THAT DISTINCTION IS THE WHOLE
POINT. A first version of this probe walked UNIT_CATALOG and produced a
confidently wrong answer: it read the Emperor's Children Defiler as 12.00 damage
at 12 inches (failing the range test), while scripts/_ec_hold_membership - which
builds an army - reads the same unit as 12.01 at 48 inches and HELD. The gate
reads `attacker.profile` at runtime, which is the FIELDED profile after
per-model loadout promotion (SWEG_PERMODEL, default-on), not the raw catalogue
entry. Measuring the catalogue answers a question nobody asked.

Run: PYTHONHASHSEED=0 python -m scripts._profile_blindspot_probe
     PB_VERBOSE=1  list every missed unit, not just the summary
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import FACTIONS

RDPA_MIN = 2.0
RANGE_MIN = 18.0
VERBOSE = os.environ.get("PB_VERBOSE") == "1"

# The six factions whose entry point on the shared block is DEFAULT-ON, so a
# mis-classification is live in production for them today.
LIVE = {
    "Astra Militarum", "Chaos Knights", "Leagues of Votann",
    "Thousand Sons", "Adepta Sororitas", "Adeptus Astartes",
}


def _rdpa(attacks, hit_p, dmg) -> float:
    return float(attacks or 0) * float(hit_p or 0.0) * float(dmg or 0.0)


def _held(rdpa: float, rng: float, assault: bool) -> bool:
    return rdpa >= RDPA_MIN and rng >= RANGE_MIN and not assault


def _fielded_profiles():
    """Every distinct profile the archetype builder actually fields, per faction.

    Keyed by (faction, profile name) so a unit fielded by several factions -
    the Defiler, for instance - is judged once per faction, which is how the
    faction-scoped gates see it.
    """
    seen = {}
    seeds = [int(s) for s in os.environ.get("PB_SEEDS", "0,1,2,3").split(",")]
    for fac in FACTIONS:
        for s in seeds:
            try:
                army = build_faction_random_army("A", fac, 2000,
                                                 rng=random.Random(s),
                                                 use_archetype=True)
            except Exception:
                continue
            for u in army.units:
                seen.setdefault((fac, u.profile.name), u.profile)
    return seen


def main() -> None:
    missed = []
    spurious = []
    with_extras = 0
    total = 0

    for (fac_key, _name), p in _fielded_profiles().items():
        total += 1
        assault = bool(getattr(p, "assault", False))
        prim_rdpa = _rdpa(p.attacks, p.hit_probability, p.weapon_damage_per_shot)
        prim_rng = float(getattr(p, "range_inches", 0) or 0)
        prim_held = _held(prim_rdpa, prim_rng, assault)

        extras = getattr(p, "extra_ranged_profiles", None) or ()
        if extras:
            with_extras += 1

        best_rdpa, best_rng, best_name = prim_rdpa, prim_rng, "primary"
        for entry in extras:
            try:
                swap = dict(entry)
            except (TypeError, ValueError):
                continue
            # A swap is a PARTIAL override — inherit anything it omits.
            a = swap.get("attacks", p.attacks)
            h = swap.get("hit_probability", p.hit_probability)
            d = swap.get("weapon_damage_per_shot", p.weapon_damage_per_shot)
            r = float(swap.get("range_inches", prim_rng) or 0)
            rd = _rdpa(a, h, d)
            # "Best" = the profile that most makes this look like a fire
            # platform, since that is what the filter is trying to detect.
            if _held(rd, r, assault) and not _held(best_rdpa, best_rng, assault):
                best_rdpa, best_rng, best_name = rd, r, swap.get("weapon_name", "extra")
            elif rd > best_rdpa and r >= RANGE_MIN:
                best_rdpa, best_rng, best_name = rd, r, swap.get("weapon_name", "extra")

        best_held = _held(best_rdpa, best_rng, assault)
        fac = fac_key
        if best_held and not prim_held:
            missed.append((fac, p.name, prim_rdpa, prim_rng, best_rdpa,
                           best_rng, best_name, len(extras)))
        elif prim_held and not best_held:
            spurious.append((fac, p.name, prim_rdpa, prim_rng))

    print(f"=== advance-suppression filter blind spot ===")
    print(f"    {total} catalogue units, {with_extras} carry extra ranged profiles")
    print(f"    filter: ranged damage per activation >= {RDPA_MIN} "
          f"AND range >= {RANGE_MIN}in, not ASSAULT\n")
    print(f"  MISSED   (fire platform the filter cannot see): {len(missed)}")
    print(f"  SPURIOUS (held on primary, not on any better):  {len(spurious)}\n")

    by_fac = collections.Counter(f for f, *_ in missed)
    live_missed = sum(n for f, n in by_fac.items() if f in LIVE)
    print(f"  MISSED by faction — the six marked LIVE have a default-on gate,")
    print(f"  so these are mis-piloted in production today:")
    for fac, n in by_fac.most_common():
        mark = "   <-- LIVE" if fac in LIVE else ""
        print(f"    {fac:<26}{n:>4}{mark}")
    print()
    print(f"  {live_missed} of {len(missed)} missed units are in a faction whose")
    print(f"  gate is default-on.")

    if VERBOSE and missed:
        print()
        print("  --- missed units ---")
        for fac, name, pr, prg, br, brg, bn, ne in sorted(missed)[:60]:
            print(f"    {fac:<24}{name[:30]:<32} primary {pr:>6.2f}/{prg:>3.0f}in"
                  f"  ->  best {br:>6.2f}/{brg:>3.0f}in  ({ne} extra)")

    if spurious:
        print()
        print("  --- spurious (held on primary only) ---")
        for fac, name, pr, prg in spurious[:20]:
            print(f"    {fac:<24}{name[:30]:<32} {pr:>6.2f}/{prg:>3.0f}in")

    print()
    print("  A MISSED unit is free to Advance onto an objective and forfeit a")
    print("  shooting phase the filter was built to protect. The gate cannot")
    print("  see it, so the mis-pilot the whole family exists to fix survives")
    print("  for exactly the units with the most complicated gun racks.")


if __name__ == "__main__":
    main()
