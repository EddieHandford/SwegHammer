"""Group-2 melee attacker-count diagnostic (OVERSHOOTER_PLAN Phase 2 #1).

Question (watchdog): when a large unit engages a small one, does the sim let
(effectively) the whole squad swing, or only as many models as can physically
reach base contact? Real 10e bounds melee by base-contact geometry — a 20-model
unit into a 5-model screen lands ~8-10 attackers, the rest do nothing.

The sim already gates `_do_fight` on per-model Engagement Range (1.0"), so a model
only swings if it is within 1.0" of a live enemy. The over-count, if any, is
therefore POSITIONAL: SwegHammer's one-Unit-per-model squads can end up
co-located so every model is simultaneously within Engagement Range of the same
small enemy unit — geometrically impossible on a real table.

This instrument wraps `Battle._do_fight` and, for every melee attack that lands,
records:
  - attacker faction
  - the attacker's squad alive-size
  - how many of that squad's models are within 1.0" of ANY live enemy right now
    (the "would-fight" count — i.e. how many of the squad are engaged at once)
  - the alive-size of the enemy unit being struck (the footprint being engaged)

It then reports, per Group-2 faction, the mean squad size, the mean simultaneously-
engaged count, the mean target footprint, and the attackers-per-defender-model
ratio. A ratio far above a realistic base-contact surround (~2-3 attackers per
defender model for a single rank, more with a second rank) is the over-count
signature. Read-only; no fix. Run with PYTHONHASHSEED=0.
"""
import os
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle, _distance
from scripts.evaluate_vs_meta import _pick_rotation_map

# Group-2 melee over-shooters (per OVERSHOOTER_PLAN) + a couple of opponents that
# field small screens / elite bodies for the large-vs-small case.
GROUP2 = ["World Eaters", "Tyranids", "Drukhari"]
OPPONENTS = ["Imperial Knights", "Adeptus Custodes", "Astra Militarum", "T'au Empire"]
SEEDS = [1, 2, 3, 4, 5]


def _squad_alive(army, squad_id, unit):
    if squad_id is None or squad_id < 0:
        return [unit]
    return [u for u in army.units
            if u.is_alive and getattr(u, "squad_id", -1) == squad_id]


def _unit_alive_size(army, squad_id, unit):
    return len(_squad_alive(army, squad_id, unit))


def run_pair(a_fac, b_fac, seed, rows):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed),
                                  use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000),
                                  use_archetype=True)
    if not a.units or not b.units:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    real_fight = battle._do_fight

    def wrapped(attacker, attacker_army, defender_army):
        before_alive = attacker.is_alive and attacker.profile.melee_attacks > 0
        # snapshot the squad's simultaneously-engaged count BEFORE the fight
        sid = getattr(attacker, "squad_id", -1)
        squad = _squad_alive(attacker_army, sid, attacker)
        enemies = list(defender_army.alive_units)
        in_er = sum(
            1 for m in squad
            if any(_distance(m.position, e.position) <= 1.0 for e in enemies)
        )
        # find the model's own engagement target footprint (the nearest live
        # enemy unit it is within 1.0" of), to size the defender being struck
        tgt_size = 0
        if before_alive and enemies:
            near = [e for e in enemies if _distance(attacker.position, e.position) <= 1.0]
            if near:
                tgt = min(near, key=lambda e: _distance(attacker.position, e.position))
                tsid = getattr(tgt, "squad_id", -1)
                tgt_size = _unit_alive_size(defender_army, tsid, tgt)
        result = real_fight(attacker, attacker_army, defender_army)
        # record only when this model actually had an engagement target (fought)
        if before_alive and tgt_size > 0:
            rows[attacker.profile.faction or "?"].append((len(squad), in_er, tgt_size))
        return result

    battle._do_fight = wrapped
    battle.run()


if __name__ == "__main__":
    rows = defaultdict(list)
    for g in GROUP2:
        for opp in OPPONENTS:
            for s in SEEDS:
                run_pair(g, opp, s, rows)
                run_pair(opp, g, s + 100, rows)   # also g on defence

    print(f"{'Faction':<20} {'fights':>7} {'sqSize':>7} {'engaged':>8} "
          f"{'tgtSize':>8} {'eng/tgt':>8} {'eng/sq':>7}")
    print("-" * 70)
    for fac in sorted(rows):
        data = rows[fac]
        n = len(data)
        if n == 0:
            continue
        msq = sum(r[0] for r in data) / n
        meng = sum(r[1] for r in data) / n
        mtgt = sum(r[2] for r in data) / n
        eng_per_tgt = meng / mtgt if mtgt else 0.0
        eng_per_sq = meng / msq if msq else 0.0
        print(f"{fac:<20} {n:>7} {msq:>7.1f} {meng:>8.1f} {mtgt:>8.1f} "
              f"{eng_per_tgt:>8.2f} {eng_per_sq:>7.2f}")
    print()
    print("eng/tgt = attacker models simultaneously in Engagement Range per LIVE "
          "defender model of the struck unit.")
    print("eng/sq  = fraction of the attacking squad simultaneously engaged "
          "(~1.0 => the whole squad swings at once regardless of footprint).")
