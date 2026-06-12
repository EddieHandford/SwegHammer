"""
Iter-15 Marines OC audit — count auto-fielded squads and OC distribution
across all 10 factions at N=30 random_fill armies, 1000pt.

Tests the hypothesis from iter-14 that Marines auto-field too many cheap
2-OC squads (Intercessor, Tactical, Assault Intercessor, Heavy Intercessor
— all 2 OC, 14-20 pts/model, BATTLELINE) which flood objectives and produce
the +10.9pt over-perform vs real meta.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter15_marines_oc_audit
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter
from typing import Dict, List

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter15_marines_oc_audit"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG


FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes",
    "Thousand Sons", "Leagues of Votann",
]
N_ARMIES = 30
POINTS = 1000


def main() -> None:
    print(f"Iter-15 Marines OC audit — N={N_ARMIES} per faction, {POINTS}pt budget")
    print()
    fac_label = "faction"
    print(
        f"{fac_label:25s} "
        f"{'units':>7s} {'OC_tot':>7s} {'OC>=2':>7s} "
        f"{'BLsqd':>6s} {'BLmdl':>6s} {'pts':>7s}"
    )
    print("-" * 75)
    # Track per-faction OC details
    summary: Dict[str, Dict[str, float]] = {}
    bl_breakdowns: Dict[str, Counter] = {}
    for fac in FACTIONS:
        models = []
        oc_tots = []
        oc_high_models = []
        bl_squad_groups = []
        bl_models = []
        pts = []
        bl_name_counter: Counter = Counter()
        for s in range(N_ARMIES):
            a = build_faction_random_army(
                "A", fac, POINTS,
                rng=random.Random(s + 1000),
                use_archetype=True,
            )
            models.append(len(a.units))
            oc_tots.append(sum(getattr(u.profile, "oc", 1) or 1 for u in a.units))
            oc_high_models.append(sum(
                1 for u in a.units
                if (getattr(u.profile, "oc", 1) or 1) >= 2
            ))
            # Count distinct BL squads (a squad = consecutive units of same
            # profile in army.units). Simpler: count BL model instances.
            bl_units = [
                u for u in a.units
                if "BATTLELINE" in (u.profile.unit_keywords or ())
            ]
            bl_models.append(len(bl_units))
            # Count distinct BL profile names in army
            bl_profile_names = set(u.profile.name for u in bl_units)
            bl_squad_groups.append(len(bl_profile_names))
            for u in bl_units:
                bl_name_counter[u.profile.name] += 1
            pts.append(a.total_points)
        summary[fac] = {
            "units": statistics.mean(models),
            "OC_tot": statistics.mean(oc_tots),
            "OC>=2": statistics.mean(oc_high_models),
            "BLsqd": statistics.mean(bl_squad_groups),
            "BLmdl": statistics.mean(bl_models),
            "pts": statistics.mean(pts),
        }
        bl_breakdowns[fac] = bl_name_counter
        s_ = summary[fac]
        print(
            f"{fac:25s} "
            f"{s_['units']:>7.1f} {s_['OC_tot']:>7.1f} {s_['OC>=2']:>7.1f} "
            f"{s_['BLsqd']:>6.1f} {s_['BLmdl']:>6.1f} {s_['pts']:>7.1f}"
        )
    print()
    print("=== BL per-profile breakdown (models per army across N=30) ===")
    for fac in FACTIONS:
        ctr = bl_breakdowns[fac]
        if not ctr:
            print(f"  {fac:25s} (no BL profiles seeded)")
            continue
        parts = ", ".join(
            f"{name}={count/N_ARMIES:.1f}" for name, count in ctr.most_common(5)
        )
        print(f"  {fac:25s} {parts}")

    print()
    print("=== INTERPRETATION ===")
    marines_tot = summary["Adeptus Astartes"]["OC_tot"]
    others_tot = statistics.mean(
        summary[f]["OC_tot"] for f in FACTIONS if f != "Adeptus Astartes"
    )
    marines_bl_models = summary["Adeptus Astartes"]["BLmdl"]
    others_bl_models = statistics.mean(
        summary[f]["BLmdl"] for f in FACTIONS if f != "Adeptus Astartes"
    )
    print(
        f"Marines OC total mean: {marines_tot:.1f}; "
        f"other-factions mean: {others_tot:.1f} "
        f"(delta {marines_tot - others_tot:+.1f}; positive = Marines field MORE OC)"
    )
    print(
        f"Marines BL model count mean: {marines_bl_models:.1f}; "
        f"other-factions mean: {others_bl_models:.1f} "
        f"(delta {marines_bl_models - others_bl_models:+.1f}; positive = Marines field MORE BL)"
    )


if __name__ == "__main__":
    main()
