"""Group-2 #3 battle-shock crumbling diagnostic (OVERSHOOTER_PLAN Phase 2 #3).

Question (watchdog): do below-Half-strength units faithfully crumble (the sim
already zeroes OC + locks stratagems on a failed 2D6-vs-Ld test), and — the
differential — do the MELEE over-shooters crumble MORE or LESS than gunlines? If
the melee aggressors grind down but rarely crumble (e.g. Synapse / Mob Rule
auto-pass, or the size-1-swarm units never reach below-Half), their depleted
units keep their Objective Control and over-hold; that would be the lever. If
crumbling is faction-neutral / already faithful, #3 is null and the Group-2
melee over-shoot needs the big bounding-fidelity track (or accept the floor).

This read-only probe wraps `Battle._run_battleshock_phase` and accumulates, per
faction-as-army across rounds and battles:
  - below_half : squad-rounds where a squad was Below Half-strength (eligible to
                 test)
  - crumbled   : squad-rounds where the squad ended Battle-shocked (failed → OC 0)
Report per faction the per-battle rates and the crumble fraction. Run with
PYTHONHASHSEED=0.
"""
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

MELEE = ["World Eaters", "Tyranids", "Drukhari", "Adepta Sororitas"]
GUNLINE = ["Astra Militarum", "Adeptus Mechanicus", "T'au Empire", "Leagues of Votann"]
OPPONENTS = ["Adeptus Custodes", "Necrons", "Space Marines", "Orks"]
SEEDS = [1, 2, 3]


def _below_half(battle, army):
    """Replicate the sim's per-squad below-Half gate; return the alive squads
    that are currently Below Half-strength."""
    out = []
    for squad_key, members in army.squads().items():
        sid = members[0].squad_id
        start = battle._squad_start_count.get((army.name, sid), 1)
        if start > 1:
            if len(members) < start / 2.0:
                out.append(members)
        else:
            u0 = members[0]
            if u0.current_health < u0.profile.health / 2.0:
                out.append(members)
    return out


def run_pair(a_fac, b_fac, seed, agg):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    real = battle._run_battleshock_phase

    def wrapped(round_num):
        result = real(round_num)
        for army in (battle.a, battle.b):
            fac = army.units[0].profile.faction if army.units else "?"
            bh = _below_half(battle, army)
            agg[fac]["below_half"] += len(bh)
            for members in bh:
                if any(m.uid in battle._battleshocked_this_round for m in members):
                    agg[fac]["crumbled"] += 1
        return result

    battle._run_battleshock_phase = wrapped
    battle.run()
    agg[a_fac]["battles"] += 1
    agg[b_fac]["battles"] += 1


if __name__ == "__main__":
    agg = defaultdict(lambda: defaultdict(float))
    for grp in (MELEE, GUNLINE):
        for f in grp:
            for opp in OPPONENTS:
                for s in SEEDS:
                    run_pair(f, opp, s, agg)
                    run_pair(opp, f, s + 50, agg)

    def show(title, facs):
        print(title)
        print(f"  {'Faction':<20} {'belowHalf/btl':>13} {'crumbled/btl':>12} {'crumble%':>9}")
        for f in facs:
            d = agg[f]
            n = d["battles"] or 1
            bh = d["below_half"] / n
            cr = d["crumbled"] / n
            frac = (100 * d["crumbled"] / d["below_half"]) if d["below_half"] else 0.0
            print(f"  {f:<20} {bh:>13.2f} {cr:>12.2f} {frac:>8.0f}%")

    show("MELEE over-shooters:", MELEE)
    print()
    show("GUNLINES:", GUNLINE)
    print()
    print("belowHalf/btl = squad-rounds a unit was Below Half-strength (eligible to test).")
    print("crumbled/btl  = squad-rounds a Below-Half unit ended Battle-shocked (OC->0).")
    print("If melee over-shooters show LOW belowHalf or LOW crumble% vs gunlines, the sim")
    print("under-crumbles them (a lever). If similar/higher, #3 is null for the over-side.")
