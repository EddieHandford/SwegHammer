"""Which Markerlight gate loses T'au their Guided uptime?

Guided uptime measures 3.5 percent with 68 percent of T'au shooting phases
producing zero marks (task #42), while the buff is confirmed live - Mont'ka
resolves every battle carrying lethal_hits_on_guided - and carriers are fielded
generously at a mean 17.9 model instances.

`Battle._run_markerlight_phase` loses an attempt at one of five places, and they
imply completely different fixes:

  SQUAD DEDUPLICATION  17.9 model instances collapse to one attempt per codex
                       squad, so the real number of attempts is three or four,
                       not eighteen. If this is the binding constraint the
                       uptime is by design and the modelling choice is the
                       thing to argue about.
  RANGE                no enemy within 36 inches of the carrier.
  LINE OF SIGHT        blocked by terrain.
  TARGETING            Look Out Sir / Lone Operative, or the reciprocal Big
                       Guns Never Tire rule barring a shot at an enemy pinned
                       in melee.
  HIT ROLL             candidates existed, the Ballistic Skill roll failed.

This counts each, per attempt, over real battles. It reuses the simulator's OWN
helpers - `_weapon_range_gap`, `Map.has_line_of_sight`, `can_target_for_ranged`,
`_reciprocal_ranged_legal` - rather than reimplementing the filter, because a
probe that reimplements the thing it measures is how the earlier blind-spot
probe produced a confidently wrong answer.

Run: PYTHONHASHSEED=0 python -m scripts._tau_marker_gates_probe
     TM_BATTLES=24
"""
from __future__ import annotations
import collections
import os
import random

import code.simulator as simmod
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map

N = int(os.environ.get("TM_BATTLES", "24"))
FAC = "T'au Empire"
ML_RANGE = 36.0

stat = collections.Counter()
attempts_per_phase = []

_real = Battle._run_markerlight_phase


def _patched(self, army, opponent):
    fac = army.units[0].profile.faction if army.units else "?"
    if fac != FAC:
        return _real(self, army, opponent)

    from code.army import can_target_for_ranged

    alive = opponent.alive_units
    ml_models = [u for u in army.alive_units
                 if "MARKERLIGHT" in (u.profile.unit_keywords or ())]
    # Reproduce the squad grouping exactly as the phase does.
    groups: dict = collections.defaultdict(list)
    for u in ml_models:
        k = getattr(u, "squad_id", -1)
        groups[k if k >= 0 else u.profile.name].append(u)
    carriers = []
    for _k, g in groups.items():
        size = max(1, g[0].profile.min_models)
        for i in range(max(1, len(g) // size)):
            carriers.append(g[i * size])

    stat["ml_models"] += len(ml_models)
    stat["carriers"] += len(carriers)
    attempts_per_phase.append(len(carriers))

    if alive:
        marked_sim: set = set()
        for mk in carriers:
            stat["attempts"] += 1
            in_range = [e for e in alive
                        if simmod._weapon_range_gap(mk, e) <= ML_RANGE]
            if not in_range:
                stat["fail_range"] += 1
                continue
            with_los = [e for e in in_range
                        if self.map.has_line_of_sight(
                            mk.position, e.position,
                            attacker_keywords=mk.profile.unit_keywords or (),
                            target_keywords=e.profile.unit_keywords or ())]
            if not with_los:
                stat["fail_los"] += 1
                continue
            targetable = [e for e in with_los
                          if can_target_for_ranged(mk, e, alive)]
            if not targetable:
                stat["fail_targeting"] += 1
                continue
            fresh = [e for e in targetable if e.uid not in marked_sim]
            if not fresh:
                stat["fail_already_marked"] += 1
                continue
            stat["reached_hit_roll"] += 1
            marked_sim.add(max(fresh, key=lambda u: u.profile.points_cost).uid)

    return _real(self, army, opponent)


def main() -> None:
    opponents = [f for f in FACTIONS if f != FAC]
    Battle._run_markerlight_phase = _patched
    try:
        for i in range(N):
            seed = 12000 + i
            random.seed(seed)
            a = build_faction_random_army("A", FAC, 2000,
                                          rng=random.Random(seed),
                                          use_archetype=True)
            b = build_faction_random_army("B", opponents[i % len(opponents)],
                                          2000, rng=random.Random(seed + 1),
                                          use_archetype=True)
            if not a.units or not b.units:
                continue
            Battle(a, b, map_=_pick_rotation_map(seed)).run()
    finally:
        Battle._run_markerlight_phase = _real

    att = stat["attempts"]
    if not att:
        print("no Markerlight attempts observed")
        return

    print(f"=== Markerlight gate decomposition, {N} battles ===\n")
    print(f"  Markerlight MODEL instances seen   {stat['ml_models']}")
    print(f"  collapsed to CARRIER attempts      {stat['carriers']}"
          f"   ({stat['ml_models'] / max(stat['carriers'], 1):.1f} models per attempt)")
    if attempts_per_phase:
        print(f"  attempts per shooting phase        "
              f"mean {sum(attempts_per_phase)/len(attempts_per_phase):.2f}, "
              f"max {max(attempts_per_phase)}")
    print()
    print(f"  {'gate':<22}{'lost':>8}{'share':>9}")
    for key, label in (("fail_range", "no enemy in 36 inches"),
                       ("fail_los", "no line of sight"),
                       ("fail_targeting", "Look Out Sir / pinned"),
                       ("fail_already_marked", "all candidates marked"),
                       ("reached_hit_roll", "REACHED the hit roll")):
        n = stat[key]
        print(f"  {label:<22}{n:>8}{100.0 * n / att:>8.1f}%")
    print()
    reached = stat["reached_hit_roll"]
    print(f"  Of {att} attempts, {reached} ({100.0*reached/att:.0f}%) reached a")
    print("  hit roll. The measured 0.42 marks per phase is that figure times")
    print("  the Ballistic Skill pass rate, so whichever gate dominates above is")
    print("  where the faction's army rule is actually being lost.")


if __name__ == "__main__":
    main()
