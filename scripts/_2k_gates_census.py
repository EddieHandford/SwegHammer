"""Read-only census for the three 2026-07-08 template feasibility gates
(SWEG_AM_2K, SWEG_EC_LIST3, SWEG_ORKS_LIST2). No evaluation sweep — archetype-
build sampling only, mirroring scripts/_compaudit_under_census.py.

Run gate-ON:
  SWEG_AM_2K=1 PYTHONHASHSEED=0 python -m scripts._2k_gates_census am
  SWEG_EC_LIST3=1 PYTHONHASHSEED=0 python -m scripts._2k_gates_census ec
  SWEG_ORKS_LIST2=1 PYTHONHASHSEED=0 python -m scripts._2k_gates_census orks
Run gate-OFF (no env var set) with the same faction arg to get the baseline.
"""
from __future__ import annotations

import collections
import random
import sys

from code.army_builder import build_faction_random_army, is_epic_hero

N = 20
BUDGET = 2000.0

FACTION_BY_ARG = {
    "am": "Astra Militarum",
    "ec": "Emperor's Children",
    "orks": "Orks",
}

# The named entries each gate is meant to make reliably realize (for the
# "realization per entry" report the build brief asks for).
WATCH_BY_ARG = {
    "am": [
        "astra_militarum_lord_solar_leontus",
        "astra_militarum_ursula_creed",
        "astra_militarum_cadian_castellan",
        "astra_militarum_cadian_command_squad",
        "astra_militarum_cadian_shock_troops",
        "astra_militarum_tempestus_scions",
        "astra_militarum_chimera",
        "astra_militarum_kasrkin",
        "astra_militarum_death_korps_of_krieg",
        "astra_militarum_cadian_heavy_weapons_squad",
        "astra_militarum_attilan_rough_riders",
        "astra_militarum_leman_russ_battle_tank",
        "astra_militarum_leman_russ_demolisher",
        "astra_militarum_rogal_dorn_battle_tank",
        "astra_militarum_basilisk",
        "astra_militarum_manticore",
    ],
    "ec": [
        "emperor_s_children_daemon_prince_of_slaanesh_with_wings",
        "emperor_s_children_lord_exultant",
        "emperor_s_children_infractors",
        "emperor_s_children_defiler",
        "emperor_s_children_maulerfiend",
        "emperor_s_children_tormentors",
        "emperor_s_children_noise_marines",
        "emperor_s_children_flawless_blades",
        "emperor_s_children_chaos_rhino",
        "emperor_s_children_chaos_spawn",
        "emperor_s_children_lucius_the_eternal",
    ],
    "orks": [
        "orks_ghazghkull_thraka",
        "orks_boss_snikrot",
        "orks_kommandos",
        "orks_zodgrod_wortsnagga",
        "orks_trukk",
        "orks_battlewagon",
        "orks_stormboyz",
        "orks_beast_snagga_boyz",
    ],
}


def census(arg: str):
    faction = FACTION_BY_ARG[arg]
    watch = WATCH_BY_ARG[arg]
    appears = collections.Counter()
    copies_total = collections.Counter()
    det_counter = collections.Counter()
    point_totals = []

    for s in range(N):
        army = build_faction_random_army(
            "A", faction, BUDGET, rng=random.Random(s), use_archetype=True
        )
        det = getattr(army, "detachment", None)
        det_counter[getattr(det, "name", None) if det is not None else "NONE"] += 1
        point_totals.append(army.total_points)

        sq_map = collections.defaultdict(list)
        for u in army.units:
            sid = getattr(u, "squad_id", None)
            key = (sid, u.profile.name) if sid is not None else (id(u), u.profile.name)
            sq_map[key].append(u)
        squads_by_key = collections.Counter()
        for (sid, pname), members in sq_map.items():
            squads_by_key[pname] += 1

        for key in watch:
            # match by catalogue key -> profile name lookup at call time
            from code.units import UNIT_CATALOG
            if key not in UNIT_CATALOG:
                continue
            pname = UNIT_CATALOG[key].name
            n = squads_by_key.get(pname, 0)
            if n > 0:
                appears[key] += 1
            copies_total[key] += n

    print(f"FACTION: {faction}  N={N} @ {int(BUDGET)}pts")
    print("Detachment:")
    for name, c in det_counter.most_common():
        print(f"    {c:2d}/{N}  {name}")
    print(f"Avg total points: {sum(point_totals)/len(point_totals):.1f}")
    print("Watch-list realization (builds present / N, mean copies):")
    for key in watch:
        a = appears.get(key, 0)
        mean_copies = copies_total.get(key, 0) / N
        print(f"    {a:2d}/{N}  mean={mean_copies:.2f}  {key}")


if __name__ == "__main__":
    census(sys.argv[1])
