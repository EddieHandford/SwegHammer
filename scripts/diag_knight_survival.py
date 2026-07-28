"""Imperial Knight un-removability instrument (#72, the over-pole lever).

Wave 187 reframed the Knight over-rate: it is not a primary-scoring artifact (the
Knight dominates whatever the scoring rewards; all-Purge → IK 91.6% sim). The real
signal is that the sim's Knight WINS THE COMBAT decisively and is essentially never
removed — real Knights are ~47% because opponents FOCUS-FIRE them down. Watchdog
steer: instrument whether the sim AI concentrates fire on the durable Knight or
spreads it (min-HP / chaff targeting), and how long a Knight survives.

This read-only probe wraps Battle._do_shoot and, for Imperial-Knights armies,
records — per battle round — the damage dealt TO the army's big Knight bricks
(TITANIC, or VEHICLE/MONSTER with >=18 wounds) versus the rest of the army, and
whether/when each brick dies. Reports per opponent + overall: the Knight bricks'
survival rate, average death round, and the fraction of the opponent's damage that
lands ON the bricks (concentration). If bricks rarely die and damage is spread thin
(low concentration), the AI-focus-fire gap is the over-pole driver. Run with
PYTHONHASHSEED=0.
"""
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

KNIGHTS = "Imperial Knights"
OPPONENTS = ["Astra Militarum", "Adeptus Mechanicus", "Aeldari", "Drukhari",
             "Adeptus Astartes", "Necrons", "Tyranids", "World Eaters"]
SEEDS = [1, 2, 3, 4, 5]


def _is_brick(u) -> bool:
    kw = u.profile.unit_keywords or ()
    return "TITANIC" in kw or (
        ("VEHICLE" in kw or "MONSTER" in kw) and (u.profile.health or 0) >= 18
    )


def run_pair(knight_side, opp_fac, seed, agg):
    a_fac = KNIGHTS if knight_side == "A" else opp_fac
    b_fac = opp_fac if knight_side == "A" else KNIGHTS
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    knight_army = a if knight_side == "A" else b
    bricks = {u.uid for u in knight_army.units if _is_brick(u)}
    if not bricks:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    real = battle._do_shoot
    d = agg[opp_fac]

    def wrapped(attacker, attacker_army, defender_army):
        before = {u.uid: u.current_health for u in defender_army.units}
        res = real(attacker, attacker_army, defender_army)
        if defender_army is knight_army:
            for u in defender_army.units:
                lost = before.get(u.uid, u.current_health) - u.current_health
                if lost <= 0:
                    continue
                if u.uid in bricks:
                    d["dmg_to_bricks"] += lost
                else:
                    d["dmg_to_rest"] += lost
        return res

    battle._do_shoot = wrapped
    battle.run()
    # Brick survival from END STATE (catches all death causes incl. melee): a
    # brick is alive iff it is still present with positive health.
    alive_now = {u.uid for u in knight_army.units if u.current_health > 0}
    for uid in bricks:
        d["bricks_total"] += 1
        if uid not in alive_now:
            d["bricks_killed"] += 1
    d["games"] += 1


if __name__ == "__main__":
    agg = defaultdict(lambda: defaultdict(float))
    for opp in OPPONENTS:
        for s in SEEDS:
            run_pair("A", opp, s, agg)
            run_pair("B", opp, s + 100, agg)

    print(f"{'vs Opponent':<20} {'bricks':>7} {'killed%(end)':>12} "
          f"{'shootDmg-on-brick%':>19}")
    print("-" * 62)
    tot = defaultdict(float)
    for opp in OPPONENTS:
        d = agg[opp]
        nb = d["bricks_total"] or 1
        killed_pct = 100 * d["bricks_killed"] / nb
        dmg_total = d["dmg_to_bricks"] + d["dmg_to_rest"]
        conc = 100 * d["dmg_to_bricks"] / (dmg_total or 1)
        print(f"{opp:<20} {int(d['bricks_total']):>7} {killed_pct:>11.0f}% "
              f"{conc:>18.0f}%")
        for k in ("bricks_total", "bricks_killed", "dmg_to_bricks", "dmg_to_rest"):
            tot[k] += d[k]
    print("-" * 62)
    nb = tot["bricks_total"] or 1
    dt = tot["dmg_to_bricks"] + tot["dmg_to_rest"]
    print(f"{'ALL':<20} {int(tot['bricks_total']):>7} "
          f"{100*tot['bricks_killed']/nb:>11.0f}% {100*tot['dmg_to_bricks']/(dt or 1):>18.0f}%")
    print()
    print("killed%(end) = fraction of Knight bricks dead at END of game (all causes, incl.")
    print("melee). shootDmg-on-brick% = share of the opponent's SHOOTING damage to the")
    print("Knight army that landed ON the bricks (low = the AI SPREADS shooting across the")
    print("smaller Armigers/chaff instead of massing it on the durable Knight — the focus-")
    print("fire gap). The IK focus-fire levers (SWEG_FOCUS / SWEG_FOCUSFIRE) are gated.")
