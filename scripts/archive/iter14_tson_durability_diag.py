"""iter14 TSON durability diagnostic.

Investigates whether the simulator's TSON defensive rules (All Is Dust /
Rubricae Phalanx +1 save vs D1, Rites of Coalescence -1 to wound on
Scarab Occult Terminators, 5++ on Rubric / 4++ on Scarab Occult, 4++
on Pink Horrors / Blue Horrors / Flamers / Screamers) actually deliver
the durability the codex claims, and reports the iter14-required
headline numbers:

  * Per-attack save resolution trace for a Rubric Marine squad versus a
    representative D1-AP0 bolter attacker.
  * "Rubrics killed per shot" empirical rate vs the analytical rule-math
    ratio (50% wound * 33% fail save * 1 damage = 0.167 wounds/shot
    baseline; the Rubricae Phalanx +1-save-vs-D1 ought to push it down
    to 50% wound * 17% fail save ≈ 0.083 wounds/shot).
  * TSON-vs-Adeptus Astartes and TSON-vs-Necrons win-rate over 30
    random_fill battles each, to expose any residual durability gap.

This script is READ-ONLY (does not touch the catalogue or simulator) and
runs deterministically with PYTHONHASHSEED=0.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter14_tson_durability_diag
"""
from __future__ import annotations

import dataclasses
import os
import random
import statistics
import sys
from typing import List, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter14_tson_durability_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army import Army
from code.army_builder import build_faction_random_army
from code.maps import DEFAULT_MAP
from code.simulator import Battle
from code.units import UNIT_CATALOG, UnitProfile

TSON = "Thousand Sons"
OPPONENTS = ("Adeptus Astartes", "Necrons")
N = 30
POINTS = 1000


def _make_attacker_d1_bolter() -> UnitProfile:
    """A bog-standard S4 AP0 D1 Marine bolter — the worst-case attacker
    for All Is Dust to chew on. Auto-hits via torrent so we isolate the
    wound + save step."""
    return UnitProfile(
        name="Bolter Marine (diag)",
        health=2.0,
        damage=1,
        hit_probability=1.0,
        ap=0,
        save=3,
        strength=4,
        toughness=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        torrent=True,
        melee_attacks=1,
        melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3,
        melee_strength=4,
        melee_ap=0,
    )


def _attack_rate(
    attacker_profile: UnitProfile,
    defender_profile: UnitProfile,
    n_shots: int = 6000,
    seed: int = 42,
) -> float:
    """Mean damage per individual shot resolution."""
    random.seed(seed)
    atk_army = Army("Atk")
    atk_army.add_unit(attacker_profile)
    def_army = Army("Def")
    # Make a beefy defender so a single shot can't wipe the squad and skew the rate
    inflated = dataclasses.replace(defender_profile, health=10_000.0)
    def_army.add_unit(inflated)
    attacker = atk_army.units[0]
    attacker.uid = "atk0"
    defender = def_army.units[0]
    defender.uid = "def0"

    class _FakeBattle:
        _current_round = 1

        def maybe_fire_command_reroll(self, *args, **kwargs):
            return False

    fb = _FakeBattle()
    attacker.army_ref._battle_ref = fb
    defender.army_ref._battle_ref = fb

    total = 0.0
    for _ in range(n_shots):
        total += attacker.attack(defender, distance=6.0, mode="ranged")
    return total / n_shots


def per_attack_save_trace() -> None:
    print(f"=== iter14 - per-attack save resolution trace ===\n")
    print(
        "Scenario: S4 AP0 D1 bolter (auto-hit) versus the canonical TSON "
        "RUBRICAE bricks. Headline is mean wounds-dealt per shot; we want "
        "the figure to match the analytical rule-math ratio for each unit."
    )
    print()
    bolter = _make_attacker_d1_bolter()

    targets: List[Tuple[str, UnitProfile]] = []
    for label, key in (
        ("Rubric Marines (3+/5++, T4, RUBRICAE) - All Is Dust target",
         "thousand_sons_rubric_marines"),
        ("Scarab Occult Terminators (2+/4++, T5, RUBRICAE+PSYKER)",
         "thousand_sons_scarab_occult_terminators"),
        ("Intercessor Squad (3+, T4) - control (no TSON rules)",
         "space_marines_intercessor_squad"),
        ("Pink Horrors (7+/4++, T3, DAEMON) - durability sanity",
         "thousand_sons_pink_horrors"),
        ("Flamers (7+/4++, T4, DAEMON) - durability sanity",
         "thousand_sons_flamers"),
    ):
        prof = UNIT_CATALOG.get(key)
        if prof is None:
            print(f"  [WARN] {key} missing from catalogue, skipping")
            continue
        targets.append((label, prof))

    print(f"{'Defender':70s} {'inv':>4s} {'kw':>20s} {'W/shot':>8s} {'shots/kill':>11s}")
    print("-" * 116)
    for label, prof in targets:
        rate = _attack_rate(bolter, prof, n_shots=6000, seed=0)
        inv = 1.0 / rate if rate > 0 else float("inf")
        kw_short = ",".join(k for k in (prof.unit_keywords or ()) if k in (
            "RUBRICAE", "PSYKER", "DAEMON", "BATTLELINE",
        ))[:20]
        print(f"{label:70s} {prof.invuln_save:>4d} {kw_short:>20s} {rate:8.4f} {inv:11.2f}")
    print()
    print(
        "Reference rule-math (S4 AP0 D1, no detachment buffs assumed):\n"
        "  Rubric 3+/5++ no rule:                      50% wound * 33% fail-save = 0.167 W/shot\n"
        "  Rubric Rubricae-Phalanx AID (+1 save vs D1): 50% wound * 17% fail-save = 0.083 W/shot\n"
        "  Intercessor 3+:                             50% wound * 33% fail-save = 0.167 W/shot\n"
        "  Scarab Occult 2+/4++ + Rites (-1 wound):    33% wound * 17% fail-save = 0.056 W/shot\n"
        "  Pink Horror 7+/4++ no rule:                 50% wound * 50% fail-save = 0.250 W/shot\n"
        "  Pink Horror pre-fix 7+/7++ (no invuln):     50% wound * 100% fail-save = 0.500 W/shot\n"
    )


def matchup_audit() -> None:
    print(f"=== iter14 - TSON win-rate vs Adeptus Astartes & Necrons ({N} battles each) ===\n")
    print(f"{'Opponent':22s} {'TSON WR%':>9s}")
    print("-" * 35)
    wrs: List[float] = []
    for opp in OPPONENTS:
        wins = 0
        for s in range(N):
            tson = build_faction_random_army(
                "A", TSON, POINTS,
                rng=random.Random(s),
                use_archetype=False,
            )
            other = build_faction_random_army(
                "B", opp, POINTS,
                rng=random.Random(s + 10000),
                use_archetype=False,
            )
            if not tson.units or not other.units:
                continue
            battle = Battle(tson, other, map_=DEFAULT_MAP)
            r = battle.run()
            if r.winner == "A":
                wins += 1
        wr = wins / N * 100
        wrs.append(wr)
        print(f"{opp:22s} {wr:9.1f}")
    print(f"\nMean TSON WR vs {len(OPPONENTS)} factions: {statistics.mean(wrs):.1f}%")


def main() -> None:
    per_attack_save_trace()
    matchup_audit()


if __name__ == "__main__":
    main()
