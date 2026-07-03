"""Read-only diagnostic: reconstruct and re-run every Astra Militarum vs
Emperor's Children game recorded in the standing anchor
(data/_anchor_sc48a_n80_log.json), verify the replayed winner matches the
anchor's recorded winner, and dump per-game event logs for the loss cases so
the crater mechanism can be quantified.

Mirrors scripts.evaluate_vs_meta._run_battle_job's exact construction:
  random.seed(pair_seed)
  a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
  b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
  battle_map = _pick_rotation_map(s)
  primary = _pick_primary_mission(pair_seed)
  Battle(a, b, map_=battle_map, rules=None, primary_mission=primary).run()

where pair_seed = (ai*1000 + bi) * 100 + s, ai/bi = FACTIONS.index(a_fac/b_fac).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._ec_crater_replay
Writes: data/_ec_crater_games.json (per-game summary, read by the other
_ec_crater_*.py scratch scripts).
"""
from __future__ import annotations

import json
import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._ec_crater_replay"] + sys.argv[1:], env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitShot, UnitFought, UnitKilled,
    ObjectiveScored, BattleEnded, EventLog,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

AM = "Astra Militarum"
EC = "Emperor's Children"

FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}


def load_anchor_games(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    games = []
    for a_fac, b_fac, s, winner in data["games"]:
        if {a_fac, b_fac} == {AM, EC}:
            games.append((a_fac, b_fac, s, winner))
    return games


def replay_one(a_fac: str, b_fac: str, s: int):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    log = EventLog()
    if not a.units or not b.units:
        return None, log, a, b, None
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=primary,
                     subscribers=[log])
    result = battle.run()
    return result, log, a, b, battle


def summarise_game(a_fac, b_fac, s, recorded_winner, result, log, battle):
    """Extract the mechanism data needed for the loss-breakdown analysis."""
    if battle is None:
        return {
            "a_fac": a_fac, "b_fac": b_fac, "s": s, "recorded_winner": recorded_winner,
            "replayed_winner": None, "match": recorded_winner is None,
            "empty_army": True,
        }
    ev = log.events
    info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                info[u.uid] = {"name": u.name, "army": u.army}

    am_side = "A" if a_fac == AM else "B"
    ec_side = "B" if am_side == "A" else "A"

    # Round-by-round AM casualties and who/what killed them; EC unit
    # damage-dealt tally; final round reached; VP progression.
    am_deaths_by_round = {}
    kill_source_counts = {}  # EC unit name -> AM kills credited
    ec_damage_by_unit = {}   # EC unit name -> total damage dealt to AM units
    am_damage_by_unit = {}   # AM unit name -> total damage dealt to EC units
    round_vp = []            # (round_num, a_capped, b_capped, a_raw, b_raw)
    obj_holder_by_round = {} # round_num -> list of (objective_name, holder_army)
    cur_round = 0
    last_shot_on = {}  # target_uid -> (attacker_uid, damage) most recent shot/fight

    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, (UnitShot, UnitFought)):
            last_shot_on[e.target_uid] = (e.attacker_uid, e.damage)
            attacker_info = info.get(e.attacker_uid, {})
            target_info = info.get(e.target_uid, {})
            if attacker_info.get("army") == ec_side and target_info.get("army") == am_side:
                ec_damage_by_unit[attacker_info["name"]] = (
                    ec_damage_by_unit.get(attacker_info["name"], 0.0) + e.damage
                )
            elif attacker_info.get("army") == am_side and target_info.get("army") == ec_side:
                am_damage_by_unit[attacker_info["name"]] = (
                    am_damage_by_unit.get(attacker_info["name"], 0.0) + e.damage
                )
        elif isinstance(e, UnitKilled):
            victim_info = info.get(e.unit_uid, {})
            if victim_info.get("army") == am_side:
                am_deaths_by_round[cur_round] = am_deaths_by_round.get(cur_round, 0) + 1
                src = last_shot_on.get(e.unit_uid)
                if src is not None:
                    src_uid, _dmg = src
                    src_info = info.get(src_uid, {})
                    if src_info.get("army") == ec_side:
                        kill_source_counts[src_info["name"]] = (
                            kill_source_counts.get(src_info["name"], 0) + 1
                        )
        elif isinstance(e, ObjectiveScored):
            obj_holder_by_round.setdefault(cur_round, []).append(
                (e.objective_name, e.army_name)
            )
        elif isinstance(e, RoundEnded):
            round_vp.append((e.round_num, e.a_vp_capped, e.b_vp_capped,
                              e.a_vp_total, e.b_vp_total))

    am_start = sum(1 for i in info.values() if i["army"] == am_side)
    ec_start = sum(1 for i in info.values() if i["army"] == ec_side)

    # Primary / secondary / challenger VP split, read directly off the Battle
    # instance's private accounting after run() (uncapped) plus the capped
    # standing that actually decided the winner (_capped_vp_pair).
    a_primary_raw = battle._a_vp - battle._a_secondary_vp - battle._a_challenger_vp
    b_primary_raw = battle._b_vp - battle._b_secondary_vp - battle._b_challenger_vp
    a_capped, b_capped = battle._capped_vp_pair()
    vp_split = {
        "a_primary_raw": a_primary_raw, "b_primary_raw": b_primary_raw,
        "a_secondary_raw": battle._a_secondary_vp, "b_secondary_raw": battle._b_secondary_vp,
        "a_challenger_raw": battle._a_challenger_vp, "b_challenger_raw": battle._b_challenger_vp,
        "a_capped": a_capped, "b_capped": b_capped,
    }
    am_capped = vp_split["a_capped"] if am_side == "A" else vp_split["b_capped"]
    ec_capped = vp_split["b_capped"] if am_side == "A" else vp_split["a_capped"]
    am_primary = a_primary_raw if am_side == "A" else b_primary_raw
    ec_primary = b_primary_raw if am_side == "A" else a_primary_raw
    am_secondary = battle._a_secondary_vp if am_side == "A" else battle._b_secondary_vp
    ec_secondary = battle._b_secondary_vp if am_side == "A" else battle._a_secondary_vp

    return {
        "a_fac": a_fac, "b_fac": b_fac, "s": s, "recorded_winner": recorded_winner,
        "replayed_winner": result.winner if result else None,
        "match": (result.winner if result else None) == recorded_winner,
        "am_side": am_side, "ec_side": ec_side,
        "am_start": am_start, "ec_start": ec_start,
        "am_survivors": result.a_survivors if am_side == "A" else result.b_survivors,
        "ec_survivors": result.b_survivors if am_side == "A" else result.a_survivors,
        "rounds": result.rounds,
        "am_deaths_by_round": am_deaths_by_round,
        "kill_source_counts": kill_source_counts,
        "ec_damage_by_unit": ec_damage_by_unit,
        "am_damage_by_unit": am_damage_by_unit,
        "round_vp": round_vp,
        "obj_holder_by_round": obj_holder_by_round,
        "final_a_vp": round_vp[-1][1] if round_vp else None,
        "final_b_vp": round_vp[-1][2] if round_vp else None,
        "vp_split": vp_split,
        "am_capped": am_capped, "ec_capped": ec_capped,
        "am_primary": am_primary, "ec_primary": ec_primary,
        "am_secondary": am_secondary, "ec_secondary": ec_secondary,
    }


def main():
    anchor_path = "data/_anchor_sc48a_n80_log.json"
    games = load_anchor_games(anchor_path)
    print(f"Found {len(games)} Astra Militarum vs Emperor's Children games in the anchor.")

    matched = 0
    mismatches = []
    summaries = []
    for a_fac, b_fac, s, recorded_winner in games:
        result, log, a, b, battle = replay_one(a_fac, b_fac, s)
        summ = summarise_game(a_fac, b_fac, s, recorded_winner, result, log, battle)
        summaries.append(summ)
        if summ["match"]:
            matched += 1
        else:
            mismatches.append(summ)

    print(f"\nREPRODUCTION VERIFICATION: {matched}/{len(games)} winners matched.")
    if mismatches:
        print(f"MISMATCHES ({len(mismatches)}):")
        for m in mismatches[:20]:
            print(f"  {m['a_fac']} vs {m['b_fac']} s={m['s']}: "
                  f"recorded={m['recorded_winner']} replayed={m['replayed_winner']}")

    out_path = "data/_ec_crater_games.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({
            "n_games": len(games),
            "matched": matched,
            "mismatches": len(mismatches),
            "games": summaries,
        }, fh, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
