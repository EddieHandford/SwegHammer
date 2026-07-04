"""Scratch stratagem fire-rate check for the D4 command-point fix
(secondary-economy audit, 2026-07-03).

Answers the probe question directly: with the corrected +2 CP/round rate,
does Smokescreen fire now (it never fired once in the durability-wave
command-point census at the old +1/round rate), and how often do the ion
shield stratagems (Rotate Ion Shields / Diabolic Bulwark) fire? Compares
gate ON (default, +2/round) against gate OFF (SWEG_CP_PER_COMMAND_PHASE=0,
the pre-fix +1/round) over the same batch of seeded games for two scopes:
Imperial Knights (vs a rotation of opponents) and Death Guard (vs a
rotation of opponents).

Detects a stratagem "fire" generically by watching the defending army's
command_points drop by exactly the stratagem's CP cost inside the
relevant method (no source changes needed — pure instrumentation).
"""
from __future__ import annotations

import os
import random
from collections import defaultdict

os.environ.setdefault("PYTHONHASHSEED", "0")

import code.simulator as sim
from code.simulator import Battle
from code.army_builder import build_faction_random_army

OPPONENTS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes", "Astra Militarum",
    "Chaos Space Marines", "World Eaters", "Adepta Sororitas",
]


def _count_fires(scope_faction: str, n_games: int, gate_env: str):
    if gate_env == "unset":
        os.environ.pop("SWEG_CP_PER_COMMAND_PHASE", None)
    else:
        os.environ["SWEG_CP_PER_COMMAND_PHASE"] = gate_env

    counts = defaultdict(int)  # event name -> fire count
    games_run = 0

    _orig_smoke = Battle._maybe_smokescreen
    _orig_ion = Battle._maybe_ion_shield_stratagem

    def _wrap_smoke(self, defending_army, shoot_target, attacker):
        before = defending_army.command_points
        _orig_smoke(self, defending_army, shoot_target, attacker)
        if defending_army.command_points < before:
            counts["smokescreen"] += 1

    def _wrap_ion(self, defending_army, shoot_target, attacker, *, faction,
                  cp_cost, env_var, used_flag):
        before = defending_army.command_points
        _orig_ion(self, defending_army, shoot_target, attacker,
                  faction=faction, cp_cost=cp_cost, env_var=env_var,
                  used_flag=used_flag)
        if defending_army.command_points < before:
            counts[f"ion_shield[{faction}]"] += 1

    Battle._maybe_smokescreen = _wrap_smoke
    Battle._maybe_ion_shield_stratagem = _wrap_ion

    try:
        for i in range(n_games):
            opp = OPPONENTS[i % len(OPPONENTS)]
            seed = 1000 + i
            a = build_faction_random_army("A", scope_faction, 2000,
                                          rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000,
                                          rng=random.Random(seed + 50000), use_archetype=True)
            if not a.units or not b.units:
                continue
            Battle(a, b).run()
            games_run += 1
    finally:
        Battle._maybe_smokescreen = _orig_smoke
        Battle._maybe_ion_shield_stratagem = _orig_ion

    return games_run, dict(counts)


for scope in ("Imperial Knights", "Death Guard"):
    print("=" * 78)
    print(f"SCOPE: {scope}  (N=20 games per gate state, rotating opponents)")
    print("=" * 78)
    for label, gate in (("gate OFF (pre-fix +1/round)", "0"),
                        ("gate ON  (default, +2/round)", "unset")):
        games, counts = _count_fires(scope, 20, gate)
        print(f"  {label}: games={games}  fires={counts if counts else '{}'}")
    print()

os.environ.pop("SWEG_CP_PER_COMMAND_PHASE", None)
print("DONE")
