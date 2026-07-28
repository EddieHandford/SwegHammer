"""Does the residual track how HARD an army is to pilot, rather than how strong it is?

The project's goal is a simulator that fields the best list available and pilots
it as well as a tournament player would. If the artificial intelligence pilots
some kinds of army well and others badly, the per-faction residual measures the
simulator's competence at that army's style, not the army's strength - and
chasing 22 separate poles is treating 22 symptoms of one defect.

Sorting the sc69a residuals by eye, the over-performers are almost all shooting
armies and the under-performers almost all melee armies. Every melee piloting
bug found this campaign fits: the advance-suppression family protects forfeited
shooting but never the forfeited charge, Fall Back eligibility asks a
capability question of a role label, melee-only units advance and lose the
charge. This tests the pattern instead of trusting the eye.

Four candidate axes, each computed from the army the evaluation actually fields:

  melee share    fraction of the army's damage output that is melee
  melee-only     fraction of models whose roles.combat_profile is MELEE_ONLY
  mobility       points-weighted mean movement allowance, in inches
  model count    models fielded - a proxy for how many decisions a turn costs

A strong negative correlation on the melee axes means the simulator
under-performs exactly where melee matters, which is a piloting-competence
defect and not 22 faction problems.

Run: PYTHONHASHSEED=0 python -m scripts._piloting_axis_probe
     PA_LOG=data/_anchor_sc69a_n80_log.json PA_SEEDS=0,1,2
"""
from __future__ import annotations
import math
import os
import random

from code.army_builder import build_faction_random_army
from code.roles import combat_profile
from code.units import wound_probability
from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_TARGET
from scripts._residual_table import _sim_rates

LOG = os.environ.get("PA_LOG", "data/_anchor_sc69a_n80_log.json")
SEEDS = [int(s) for s in os.environ.get("PA_SEEDS", "0,1,2").split(",")]

# A mid-table reference defender: Toughness 6, Save 3+. Both damage estimates
# are taken against the SAME target so the melee share is a like-for-like
# comparison rather than an artefact of two different yardsticks.
REF_T = int(os.environ.get("PA_REF_T", "6"))
REF_SV = int(os.environ.get("PA_REF_SV", "3"))


def _dpa(attacks, hit_p, s, ap, dmg) -> float:
    if not attacks or not hit_p:
        return 0.0
    after = max(2, REF_SV - (ap or 0))
    through = 1.0 - (7 - after) / 6.0 if after <= 6 else 1.0
    return (attacks * hit_p * wound_probability(int(s or 0), REF_T)
            * through * float(dmg or 1.0))


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def _spearman(xs, ys) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r
    return _pearson(rank(xs), rank(ys))


def main() -> None:
    try:
        sim = _sim_rates(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    rows = []
    for fac in FACTIONS:
        real = TOURNAMENT_TARGET.get(fac)
        if real is None or fac not in sim:
            continue
        m_dmg = r_dmg = 0.0
        melee_only = models = 0
        move_pts = pts = 0.0
        for seed in SEEDS:
            army = build_faction_random_army("A", fac, 2000,
                                             rng=random.Random(seed),
                                             use_archetype=True)
            for u in army.units:
                p = u.profile
                m_dmg += _dpa(p.melee_attacks, p.melee_hit_probability,
                              p.melee_strength, p.melee_ap,
                              p.melee_damage_per_shot)
                r_dmg += _dpa(p.attacks, p.hit_probability, p.strength,
                              p.ap, p.weapon_damage_per_shot)
                models += 1
                if combat_profile(p) == "MELEE_ONLY":
                    melee_only += 1
                cost = float(getattr(p, "points_cost", 0) or 0)
                move_pts += float(getattr(p, "move", 6.0) or 6.0) * cost
                pts += cost
        total = m_dmg + r_dmg
        rows.append({
            "fac": fac,
            "resid": sim[fac] - real,
            "melee_share": m_dmg / total if total else 0.0,
            "melee_only": melee_only / models if models else 0.0,
            "mobility": move_pts / pts if pts else 0.0,
            "models": models / len(SEEDS),
        })

    rows.sort(key=lambda r: -r["resid"])
    print(f"=== piloting axes against residual ({LOG}, seeds {SEEDS}) ===")
    print(f"{'faction':<24}{'resid':>8}{'melee share':>13}{'melee-only':>12}"
          f"{'mobility':>10}{'models':>8}")
    for r in rows:
        print(f"{r['fac']:<24}{r['resid']:>+8.1f}{r['melee_share']:>13.2f}"
              f"{r['melee_only']:>12.2f}{r['mobility']:>10.1f}{r['models']:>8.0f}")

    resid = [r["resid"] for r in rows]
    print()
    print(f"  {'axis':<16}{'Pearson':>10}{'Spearman':>10}")
    for axis in ("melee_share", "melee_only", "mobility", "models"):
        print(f"  {axis:<16}{_pearson([r[axis] for r in rows], resid):>+10.3f}"
              f"{_spearman([r[axis] for r in rows], resid):>+10.3f}")
    print()
    print("  With 22 factions a correlation near 0.42 is significant at the five")
    print("  percent level, and one near 0.25 is not distinguishable from noise.")
    print("  Read these as a direction to investigate, never as a verdict.")

    # Split the table so the claim can be checked as a group difference too,
    # which does not depend on the relationship being linear.
    melee = [r for r in rows if r["melee_share"] >= 0.5]
    shoot = [r for r in rows if r["melee_share"] < 0.5]
    if melee and shoot:
        mm = sum(r["resid"] for r in melee) / len(melee)
        ss = sum(r["resid"] for r in shoot) / len(shoot)
        print()
        print(f"  melee-majority armies  ({len(melee):>2})  mean residual {mm:>+6.2f}")
        print(f"  shooting-majority      ({len(shoot):>2})  mean residual {ss:>+6.2f}")
        print(f"  gap {mm - ss:>+.2f} points")


if __name__ == "__main__":
    main()
