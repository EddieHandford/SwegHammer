"""
Iter-15 Marines kill-efficiency diag — measures damage output per pt
across all 10 factions in mirror-style 1000pt random_fill battles.

Hypothesis: Marines win on objectives because they kill MORE opponents
per pt of their army, not because they have more OC. If true, the residual
+10.9pt over-perform vs real meta is unit-balance (points are too cheap
for kill output), not list-shape or AI gap → MC bisection territory.

Records, per faction, average damage dealt and damage taken per army
across N=30 battles. Computes (damage_dealt / total_pts) — the "lethality
density" of the faction.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter15_marines_kill_efficiency
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter15_marines_kill_efficiency"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import UnitFought, UnitShot, UnitKilled
from code.maps import DEFAULT_MAP
from code.simulator import Battle


FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes",
    "Thousand Sons", "Leagues of Votann",
]
N_BATTLES = 20  # smaller N to keep runtime reasonable
POINTS = 1000


class KillDiag:
    def __init__(self, a_uids: set, b_uids: set) -> None:
        self.a_uids = a_uids
        self.b_uids = b_uids
        self.a_damage_out = 0.0  # damage A dealt to B
        self.b_damage_out = 0.0  # damage B dealt to A
        self.a_kills = 0
        self.b_kills = 0

    def on_event(self, e) -> None:
        if isinstance(e, (UnitShot, UnitFought)):
            if e.attacker_uid in self.a_uids and e.target_uid in self.b_uids:
                self.a_damage_out += e.damage
            elif e.attacker_uid in self.b_uids and e.target_uid in self.a_uids:
                self.b_damage_out += e.damage
        elif isinstance(e, UnitKilled):
            # Killed unit was in which army?
            if e.unit_uid in self.b_uids:
                self.a_kills += 1
            elif e.unit_uid in self.a_uids:
                self.b_kills += 1


def main() -> None:
    print(f"Iter-15 kill-efficiency — N={N_BATTLES} mirror battles, {POINTS}pt budget")
    print()
    print(
        f"{'fac_A':25s} {'avg_pts':>8s} "
        f"{'dmg_out':>8s} {'kills':>6s} "
        f"{'dmg_in':>8s} {'killed':>7s} "
        f"{'dmg/pt':>7s}"
    )
    print("-" * 75)
    summary = {}
    for fac in FACTIONS:
        # Each faction vs random opponent rotation (not self-mirror)
        dmg_outs = []
        dmg_ins = []
        kills_outs = []
        kills_ins = []
        pts_used = []
        opp_rotation = [f for f in FACTIONS if f != fac]
        for s in range(N_BATTLES):
            seed = s + 9000
            opp = opp_rotation[s % len(opp_rotation)]
            a = build_faction_random_army(
                "A", fac, POINTS,
                rng=random.Random(seed),
                use_archetype=True,
            )
            b = build_faction_random_army(
                "B", opp, POINTS,
                rng=random.Random(seed + 50000),
                use_archetype=True,
            )
            if not a.units or not b.units:
                continue
            battle = Battle(a, b, map_=DEFAULT_MAP)
            battle._assign_uids()
            a_uids = {u.uid for u in a.units}
            b_uids = {u.uid for u in b.units}
            diag = KillDiag(a_uids, b_uids)
            battle.subscribers.append(diag)
            battle.run()
            dmg_outs.append(diag.a_damage_out)
            dmg_ins.append(diag.b_damage_out)
            kills_outs.append(diag.a_kills)
            kills_ins.append(diag.b_kills)
            pts_used.append(a.total_points)
        if not dmg_outs:
            continue
        avg_pts = statistics.mean(pts_used)
        avg_dmg_out = statistics.mean(dmg_outs)
        avg_dmg_in = statistics.mean(dmg_ins)
        avg_kills = statistics.mean(kills_outs)
        avg_killed = statistics.mean(kills_ins)
        dmg_per_pt = avg_dmg_out / max(avg_pts, 1.0)
        summary[fac] = {
            "pts": avg_pts,
            "dmg_out": avg_dmg_out,
            "kills": avg_kills,
            "dmg_in": avg_dmg_in,
            "killed": avg_killed,
            "dmg_per_pt": dmg_per_pt,
        }
        print(
            f"{fac:25s} {avg_pts:>8.1f} "
            f"{avg_dmg_out:>8.1f} {avg_kills:>6.1f} "
            f"{avg_dmg_in:>8.1f} {avg_killed:>7.1f} "
            f"{dmg_per_pt:>7.4f}"
        )

    print()
    print("=== INTERPRETATION ===")
    marines = summary.get("Adeptus Astartes", {})
    if not marines:
        return
    others_dmg_per_pt = statistics.mean(
        s["dmg_per_pt"] for f, s in summary.items() if f != "Adeptus Astartes"
    )
    others_kills = statistics.mean(
        s["kills"] for f, s in summary.items() if f != "Adeptus Astartes"
    )
    others_dmg_out = statistics.mean(
        s["dmg_out"] for f, s in summary.items() if f != "Adeptus Astartes"
    )
    print(
        f"Marines: dmg_out={marines['dmg_out']:.1f}, kills={marines['kills']:.1f}, "
        f"dmg/pt={marines['dmg_per_pt']:.4f}"
    )
    print(
        f"Others avg: dmg_out={others_dmg_out:.1f}, kills={others_kills:.1f}, "
        f"dmg/pt={others_dmg_per_pt:.4f}"
    )
    print(
        f"Marines vs others delta: dmg_out {marines['dmg_out']-others_dmg_out:+.1f}, "
        f"kills {marines['kills']-others_kills:+.1f}, "
        f"dmg/pt {marines['dmg_per_pt']-others_dmg_per_pt:+.4f}"
    )
    if marines['dmg_per_pt'] > others_dmg_per_pt * 1.1:
        print(
            "FLAG: Marines damage-per-pt > 1.1x avg → unit-balance issue "
            "(Marines are too cheap for their kill efficiency). "
            "FLAG FOR MC BISECTION."
        )
    elif marines['dmg_per_pt'] < others_dmg_per_pt * 0.9:
        print(
            "Marines damage-per-pt < 0.9x avg → Marines under-killing. "
            "Win must come from elsewhere (durability, OC, mobility)."
        )
    else:
        print(
            "Marines damage-per-pt within 10% of avg — not the dominant factor."
        )


if __name__ == "__main__":
    main()
