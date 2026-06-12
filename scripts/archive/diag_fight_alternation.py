"""Fight-phase alternation over-credit diagnostic (OVERSHOOTER_PLAN Phase 2 #2, STEP 1).

The sim's Fight phase resolves ALL of the active army's units, then the defender
fights only in its OWN later turn. Real 10e alternates, so a charged/engaged
defender swings back IN THE SAME phase and can blunt the aggressor. The sim's
"active kills before the defender retaliates" therefore over-credits MELEE
aggressors — they delete defenders whose retaliation is then never dealt.

This read-only probe quantifies the over-credit and, crucially, its DIFFERENTIAL
across factions (the watchdog's bar: it must be LARGER for the melee
over-shooters than for gunlines). For each faction as the ACTIVE attacker it
records, per battle:
  - melee_dmg : total melee damage that faction deals in its fight phases
  - denied    : summed melee output (attacks x hit x dmg) of enemy models this
                faction KILLS in melee during its own fight phase — i.e. the
                retaliation those models never get to deal this round, the direct
                over-credit from the missing alternation.
Melee over-shooters (World Eaters / Tyranids / Drukhari) should show high
melee_dmg AND high denied; gunlines (Astra Militarum / AdMech / T'au / Votann)
should show both near zero (they barely fight melee, so alternation can't help
or hurt them). Run with PYTHONHASHSEED=0.
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


def _melee_dpa(unit):
    p = unit.profile
    return (max(0, int(p.melee_attacks or 0))
            * float(p.melee_hit_probability or 0.0)
            * float(p.melee_damage_per_shot or 0.0))


def run_pair(a_fac, b_fac, seed, agg):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    real_fight = battle._do_fight

    def wrapped(attacker, attacker_army, defender_army):
        fac = attacker.profile.faction or "?"
        # snapshot which enemies are alive before the strike, and the chosen
        # target's pre-strike state, so we can detect a kill + attribute denied
        # retaliation to the attacker's faction.
        before = {e.uid: (e.is_alive, _melee_dpa(e)) for e in defender_army.units}
        hp_before = {e.uid: e.current_health for e in defender_army.units}
        result = real_fight(attacker, attacker_army, defender_army)
        dealt = 0.0
        for e in defender_army.units:
            was_alive, edpa = before.get(e.uid, (False, 0.0))
            if not was_alive:
                continue
            lost = hp_before[e.uid] - e.current_health
            if lost > 0:
                dealt += lost
                if not e.is_alive:           # killed this strike → retaliation denied
                    agg[fac]["denied"] += edpa
        agg[fac]["melee"] += dealt
        return result

    battle._do_fight = wrapped
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
        print(f"  {'Faction':<20} {'meleeDmg/btl':>12} {'denied/btl':>11}")
        for f in facs:
            d = agg[f]
            n = d["battles"] or 1
            print(f"  {f:<20} {d['melee']/n:>12.1f} {d['denied']/n:>11.2f}")

    show("MELEE over-shooters (expect HIGH denied):", MELEE)
    print()
    show("GUNLINES (expect ~0 denied):", GUNLINE)
    print()
    print("denied/btl = enemy melee output (attacks x hit x dmg) this faction KILLS in its")
    print("own fight phase before those models can retaliate — the direct fight-alternation")
    print("over-credit. A clear MELEE>>GUNLINE gap is the differential proof for #2.")
