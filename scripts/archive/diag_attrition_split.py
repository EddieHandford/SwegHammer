"""Damage-dealt vs damage-taken split for the out-attrited under-shooters.

Astra Militarum and Adeptus Mechanicus are durable-shooty-vehicle armies
that the simulator under-rates.  A prior diagnostic (scripts/diag_undershooter.py)
confirmed they get heavily out-attrited (~28 % unit-survival vs the opponent's
~61 %).  Cover was refuted as the root cause (scripts/diag_vehicle_cover.py:
durable vehicles are in cover 44-69 % of shots, not never).

This probe asks a sharper question: is the attrition gap driven by
  (a) UNDER-OUTPUT -- the under-shooter's guns deal too little damage, or
  (b) OVER-FRAGILITY -- the under-shooter's units take too much damage / die too
      fast despite being in cover?

Method: snapshot every unit's ``current_health`` at battle start and at battle
end, then compute:
  * damage_taken = sum of (start_health - end_health) over own units (clamped >= 0)
  * damage_dealt = sum of (start_health - end_health) over opponent's units

Both are split into durable-vehicle (VEHICLE keyword + health >= 8) vs rest-of-army,
and normalized per game so the numbers are comparable across different run counts.

Run with PYTHONHASHSEED=0.
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

UNDER = ["Astra Militarum", "Adeptus Mechanicus"]
OPPONENTS = [
    "Imperial Knights", "World Eaters", "Necrons", "T'au Empire",
    "Tyranids", "Adeptus Astartes", "Aeldari",
]
SEEDS = [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_durable_vehicle(u) -> bool:
    """True when the unit is a durable VEHICLE (VEHICLE keyword + >= 8 wounds)."""
    kw = u.profile.unit_keywords or ()
    return "VEHICLE" in kw and (u.profile.health or 0) >= 8


def _snapshot(army) -> Dict[int, float]:
    """Return {object_id: current_health} for all units in army.

    Uses Python object identity (id(u)) rather than u.uid because uids are
    assigned during Battle.run() — before that point every unit has uid == "".
    Object identity is stable for the lifetime of the battle since the same
    Unit instances are reused throughout.
    """
    return {id(u): u.current_health for u in army.units}


def _damage_from_snapshot(army, before: Dict[int, float]) -> tuple[float, float]:
    """Return (durable_vehicle_damage, other_damage) taken by army since snapshot.

    Damage is clamped to >= 0 per unit (heals are ignored; we only count losses).
    """
    dv_dmg = 0.0
    other_dmg = 0.0
    for u in army.units:
        hp_before = before.get(id(u), 0.0)
        loss = max(0.0, hp_before - u.current_health)
        if _is_durable_vehicle(u):
            dv_dmg += loss
        else:
            other_dmg += loss
    return dv_dmg, other_dmg


# ---------------------------------------------------------------------------
# Per-game runner
# ---------------------------------------------------------------------------

def run_pair(
    me_fac: str,
    me_side: str,
    opp_fac: str,
    seed: int,
    agg: dict,
) -> None:
    a_fac = me_fac if me_side == "A" else opp_fac
    b_fac = opp_fac if me_side == "A" else me_fac

    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return

    # Snapshot health at battle start (before any damage is dealt).
    snap_a = _snapshot(a)
    snap_b = _snapshot(b)

    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    battle.run()

    # Identify which army is "me" and which is "opponent".
    me_army = a if me_side == "A" else b
    opp_army = b if me_side == "A" else a
    snap_me = snap_a if me_side == "A" else snap_b
    snap_opp = snap_b if me_side == "A" else snap_a

    # Damage TAKEN by the under-shooter (wounds lost from own units).
    me_dv_taken, me_other_taken = _damage_from_snapshot(me_army, snap_me)

    # Damage DEALT by the under-shooter = wounds lost from opponent's units.
    opp_dv_taken, opp_other_taken = _damage_from_snapshot(opp_army, snap_opp)
    me_dv_dealt = opp_dv_taken        # damage my guns did to their durable vehicles
    me_other_dealt = opp_other_taken  # damage my guns did to the rest of their army

    d = agg[me_fac]
    d["n"] += 1
    d["me_dv_taken"]    += me_dv_taken
    d["me_other_taken"] += me_other_taken
    d["me_dv_dealt"]    += me_dv_dealt
    d["me_other_dealt"] += me_other_dealt

    # Track the opponent's numbers from their own perspective (for comparison row).
    # "opponent_dealt" = what the opponent dealt TO the under-shooter = me_taken.
    d["opp_dv_dealt"]    += me_dv_taken
    d["opp_other_dealt"] += me_other_taken
    d["opp_dv_taken"]    += opp_dv_taken
    d["opp_other_taken"] += opp_other_taken

    # Unit survival counts for context.
    d["me_units_start"]  += len(me_army.units)
    d["me_units_alive"]  += len([u for u in me_army.units if u.is_alive])
    d["opp_units_start"] += len(opp_army.units)
    d["opp_units_alive"] += len([u for u in opp_army.units if u.is_alive])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agg: dict = defaultdict(lambda: defaultdict(float))

    for me in UNDER:
        for opp in OPPONENTS:
            if opp == me:
                continue
            for s in SEEDS:
                run_pair(me, "A", opp, s, agg)
                run_pair(me, "B", opp, s + 100, agg)

    # -----------------------------------------------------------------------
    # Print results
    # -----------------------------------------------------------------------
    print()
    print("=" * 90)
    print("DAMAGE DEALT vs DAMAGE TAKEN — per game averages (wounds)")
    print("Under-shooter factions: Astra Militarum, Adeptus Mechanicus")
    print("=" * 90)

    col_w = 13
    header_row = (
        f"{'Faction':<22}"
        f"{'DEALT-DV':>{col_w}}"
        f"{'DEALT-other':>{col_w}}"
        f"{'DEALT-total':>{col_w}}"
        f"{'TAKEN-DV':>{col_w}}"
        f"{'TAKEN-other':>{col_w}}"
        f"{'TAKEN-total':>{col_w}}"
        f"{'D/T ratio':>{col_w}}"
        f"{'surv%':>7}"
    )
    print(header_row)
    print("-" * 90)

    for me in UNDER:
        d = agg[me]
        n = d["n"] or 1

        dv_dealt    = d["me_dv_dealt"] / n
        oth_dealt   = d["me_other_dealt"] / n
        tot_dealt   = dv_dealt + oth_dealt

        dv_taken    = d["me_dv_taken"] / n
        oth_taken   = d["me_other_taken"] / n
        tot_taken   = dv_taken + oth_taken

        dt_ratio    = tot_dealt / max(0.01, tot_taken)

        surv_pct    = 100.0 * d["me_units_alive"] / max(1.0, d["me_units_start"])

        print(
            f"{me:<22}"
            f"{dv_dealt:{col_w}.1f}"
            f"{oth_dealt:{col_w}.1f}"
            f"{tot_dealt:{col_w}.1f}"
            f"{dv_taken:{col_w}.1f}"
            f"{oth_taken:{col_w}.1f}"
            f"{tot_taken:{col_w}.1f}"
            f"{dt_ratio:{col_w}.2f}"
            f"{surv_pct:>6.0f}%"
        )

    print()
    print("Opponent averages (pooled across all matchups vs the two under-shooters):")
    print("-" * 90)

    # Aggregate the opponent numbers pooled over both factions.
    opp_totals: dict = defaultdict(float)
    for me in UNDER:
        d = agg[me]
        for k in ("opp_dv_dealt", "opp_other_dealt", "opp_dv_taken", "opp_other_taken",
                  "opp_units_start", "opp_units_alive"):
            opp_totals[k] += d[k]
        opp_totals["n"] += d["n"]

    n_opp = opp_totals["n"] or 1
    odv_dealt  = opp_totals["opp_dv_dealt"] / n_opp
    ooth_dealt = opp_totals["opp_other_dealt"] / n_opp
    otot_dealt = odv_dealt + ooth_dealt

    odv_taken  = opp_totals["opp_dv_taken"] / n_opp
    ooth_taken = opp_totals["opp_other_taken"] / n_opp
    otot_taken = odv_taken + ooth_taken

    odt_ratio  = otot_dealt / max(0.01, otot_taken)
    osurv_pct  = 100.0 * opp_totals["opp_units_alive"] / max(1.0, opp_totals["opp_units_start"])

    print(
        f"{'Opponent (pooled)':<22}"
        f"{odv_dealt:{col_w}.1f}"
        f"{ooth_dealt:{col_w}.1f}"
        f"{otot_dealt:{col_w}.1f}"
        f"{odv_taken:{col_w}.1f}"
        f"{ooth_taken:{col_w}.1f}"
        f"{otot_taken:{col_w}.1f}"
        f"{odt_ratio:{col_w}.2f}"
        f"{osurv_pct:>6.0f}%"
    )

    print()
    print("Durable-vehicle contribution breakdown (% of total dealt / taken that is durable vehicles):")
    print("-" * 90)
    for me in UNDER:
        d = agg[me]
        n = d["n"] or 1
        tot_dealt = (d["me_dv_dealt"] + d["me_other_dealt"]) / n
        tot_taken = (d["me_dv_taken"] + d["me_other_taken"]) / n
        dv_dealt_pct = 100.0 * (d["me_dv_dealt"] / n) / max(0.01, tot_dealt)
        dv_taken_pct = 100.0 * (d["me_dv_taken"] / n) / max(0.01, tot_taken)
        print(f"  {me:<22}  durable-vehicle share of DEALT = {dv_dealt_pct:.0f}%   "
              f"durable-vehicle share of TAKEN = {dv_taken_pct:.0f}%")

    print()
    print("COLUMNS")
    print("  DEALT-DV     = avg wounds inflicted on opponent's durable vehicles per game")
    print("  DEALT-other  = avg wounds inflicted on opponent's non-durable-vehicle units per game")
    print("  DEALT-total  = total avg wounds inflicted on opponent per game")
    print("  TAKEN-DV     = avg wounds suffered by faction's own durable vehicles per game")
    print("  TAKEN-other  = avg wounds suffered by faction's own non-durable-vehicle units per game")
    print("  TAKEN-total  = total avg wounds suffered per game")
    print("  D/T ratio    = DEALT-total / TAKEN-total  (>1 = dealt more than taken; <1 = net loss)")
    print("  surv%        = fraction of unit instances alive at battle end")
    print()
    print("INTERPRETATION")
    print("  If DEALT-total is LOW relative to the opponent's DEALT-total => under-output")
    print("    (the under-shooter's guns underperform; not dealing enough damage)")
    print("  If TAKEN-total is HIGH relative to the opponent's TAKEN-total => over-fragility")
    print("    (under-shooter units die too fast, regardless of cover)")
    print("  A D/T ratio < 1 means the faction is taking more damage than it deals.")
    print("  The dominant cause is whichever column explains more of the gap vs the opponent.")
