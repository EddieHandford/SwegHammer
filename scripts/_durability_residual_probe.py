"""Does the simulator's residual track how DURABLE a faction's army is?

Two independent results point the same way and neither was predicted by the
thing it was measuring:

  Death Guard   residual +11.4, and five real battle reports have them 0-5
                while the simulator has them at 63.5 percent
  Votann        a KNOWN-GOOD 6-0 tournament list, faithfully transcribed
                (docs/TYRANID_LIST_FIDELITY.md sibling case, task #34), moves
                the faction from 61.4 to 77.3 against a real 48.0

Both armies are built on the most durable chassis their faction owns - Death
Guard on Toughness-inflated infantry with Feel No Pain, Votann on three
Toughness-12, sixteen-wound, Save-2+ Hekaton Land Fortresses. If the simulator
systematically over-rewards durability, that is ONE defect wearing two faces,
and it is worth far more than either list.

This tests it without running a battle. For each faction it builds the
archetype army the evaluation actually fields, computes how many attacks a
reference attacker needs to remove the whole army (normalised per point), and
lines that up against the faction's measured residual from the standing anchor.
A positive correlation means durable armies over-perform.

The offence index is computed the same way and reported alongside, because the
honest alternative explanation is that these armies are simply strong on both
axes and durability is riding along.

Run: PYTHONHASHSEED=0 python -m scripts._durability_residual_probe
     DR_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import math
import os
import random

from code.army_builder import build_faction_random_army
from code.units import wound_probability
from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_TARGET
from scripts._residual_table import _sim_rates

LOG = os.environ.get("DR_LOG", "data/_anchor_sc69a_n80_log.json")
SEEDS = [int(s) for s in os.environ.get("DR_SEEDS", "0,1,2").split(",")]

# Reference attackers, spanning what a real army actually shoots with. The
# LIGHT profile is the one that matters most for the hypothesis: a Toughness-12
# Save-2+ chassis is close to immune to it, so an army built on such chassis
# gains disproportionately if the simulator lets durability convert into wins.
REFS = (
    ("light",  4, 0,  1.0),
    ("medium", 8, -2, 2.0),
    ("heavy",  12, -3, 4.0),
)
HIT_P = 0.5


def _fail_save(save: int, invuln: int, ap: int) -> float:
    """Probability an unsaved wound gets through, best of armour and invulnerable."""
    after_ap = max(2, save - ap)          # armour penetration is stored negative
    best = min(after_ap, invuln if invuln else 7)
    if best > 6:
        return 1.0
    return 1.0 - (7 - best) / 6.0


def _fnp_through(fnp) -> float:
    """Fraction of damage that survives a Feel No Pain roll (7 or None = none)."""
    if not fnp or fnp > 6:
        return 1.0
    return 1.0 - (7 - fnp) / 6.0


def _attacks_to_remove(p, s: int, ap: int, dmg: float) -> float:
    """Expected reference attacks needed to remove ONE model of this profile.

    Excess damage on a destroyed model is lost (10e core, and the simulator
    implements it - code/units.py `simulator.damage_allocation_spillover`), so
    a model with W wounds needs ceil(W / D) unsaved wounds regardless of how
    far D overshoots. That ceiling is exactly what makes a sixteen-wound
    chassis expensive to shift with light guns, so it must not be smoothed away.
    """
    w = float(getattr(p, "health", 1) or 1)
    inv = getattr(p, "invuln_save_ranged", None) or getattr(p, "invuln_save", 7) or 7
    through = _fail_save(int(getattr(p, "save", 7) or 7), int(inv), ap)
    wp = wound_probability(s, int(getattr(p, "toughness", 4) or 4))
    eff_dmg = dmg * _fnp_through(getattr(p, "fnp", 7))
    if eff_dmg <= 0 or wp <= 0 or through <= 0:
        return 1e6
    unsaved_needed = math.ceil(w / eff_dmg) if eff_dmg < w else 1
    return unsaved_needed / (HIT_P * wp * through)


def _offence(p, t: int, sv: int) -> float:
    """Damage per round this profile puts into a reference target."""
    out = 0.0
    for atk, hp, s, ap, d in (
        (getattr(p, "attacks", 0), getattr(p, "hit_probability", 0),
         getattr(p, "strength", 0), getattr(p, "ap", 0),
         getattr(p, "weapon_damage_per_shot", 0)),
        (getattr(p, "melee_attacks", 0), getattr(p, "melee_hit_probability", 0),
         getattr(p, "melee_strength", 0), getattr(p, "melee_ap", 0),
         getattr(p, "melee_damage_per_shot", 0)),
    ):
        if not atk or not hp:
            continue
        out = max(out, atk * hp * wound_probability(int(s or 0), t)
                  * _fail_save(sv, 7, int(ap or 0)) * float(d or 1.0))
    return out


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


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
        dur = {name: 0.0 for name, _, _, _ in REFS}
        off = 0.0
        pts = 0.0
        for seed in SEEDS:
            army = build_faction_random_army("A", fac, 2000,
                                             rng=random.Random(seed),
                                             use_archetype=True)
            for u in army.units:
                p = u.profile
                pts += float(getattr(p, "points_cost", 0) or 0)
                for name, s, ap, d in REFS:
                    dur[name] += _attacks_to_remove(p, s, ap, d)
                off += _offence(p, 8, 3)
        pts = max(pts, 1e-9)
        rows.append((
            sim[fac] - real, fac, sim[fac], real,
            {k: v / pts * 100.0 for k, v in dur.items()},
            off / pts * 100.0,
        ))

    rows.sort(reverse=True)
    print(f"=== durability versus residual (log: {LOG}, seeds {SEEDS}) ===")
    print("durability = reference attacks needed to remove the army, per 100 points")
    print("offence    = damage per round into Toughness 8 / Save 3+, per 100 points")
    print()
    print(f"{'faction':<24}{'sim':>6}{'real':>6}{'resid':>7}"
          f"{'dur.light':>10}{'dur.med':>9}{'dur.heavy':>10}{'offence':>9}")
    for resid, fac, s, r, dur, off in rows:
        print(f"{fac:<24}{s:>6.1f}{r:>6.1f}{resid:>+7.1f}"
              f"{dur['light']:>10.1f}{dur['medium']:>9.1f}"
              f"{dur['heavy']:>10.1f}{off:>9.2f}")

    resids = [r[0] for r in rows]
    print()
    print("  Pearson correlation of residual against:")
    for name, _, _, _ in REFS:
        print(f"    durability ({name:<6}) {_pearson([r[4][name] for r in rows], resids):>+7.3f}")
    print(f"    offence             {_pearson([r[5] for r in rows], resids):>+7.3f}")
    print()
    print("  A positive durability correlation means the simulator pays armies")
    print("  for being hard to remove at a rate reality does not. A flat or")
    print("  negative one kills the hypothesis and the Votann result is local.")


if __name__ == "__main__":
    main()
