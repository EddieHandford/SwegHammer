"""READ-ONLY scratch diagnostic for Durability Audit E (melee damage math into
durable platforms). NOT part of the production codebase; not imported by
anything else. No source files are modified — this instruments the live
Unit.attack call via sys.settrace, capturing the fully-resolved hit_target /
wound_target / save_target / invuln right after they are computed (line 3571
of code/units.py, immediately after `save_target = effective_save`), for every
melee attack call made by a World Eaters attacker against a Chaos Knights or
Imperial Knights target during 2-3 replayed anchor games.

Mirrors scripts._ec_crater_replay's exact battle-construction recipe (which
itself mirrors scripts.evaluate_vs_meta._run_battle_job):
  random.seed(pair_seed)
  a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
  b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
  battle_map = _pick_rotation_map(s)
  primary = _pick_primary_mission(pair_seed)
  Battle(a, b, map_=battle_map, rules=None, primary_mission=primary).run()
where pair_seed = (ai*1000 + bi) * 100 + s, ai/bi = FACTIONS.index(a_fac/b_fac).

Run: PYTHONIOENCODING=utf-8 python -m scripts._dura_audit_e_melee_replay
"""
from __future__ import annotations

import json
import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._dura_audit_e_melee_replay"] + sys.argv[1:],
        env=os.environ,
    ).returncode)

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.units import Unit
import code.units as units_mod
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

WE = "World Eaters"
KNIGHT_FACTIONS = {"Chaos Knights", "Imperial Knights"}

# Line inside Unit.attack (code/units.py) that reads `for _ in range(n_attacks):`
# -- by the time this line is about to execute, every once-per-attack local
# (hit_target, wound_target, save_target, invuln, ap, n_attacks,
# effective_lethal_hits, effective_sustained_hits, _effective_twin_linked) has
# already been resolved, and the per-shot loop (which also computes per-shot-
# only locals like anti_crit_threshold and effective_dw) has not started yet.
ATTACK_CODE = Unit.attack.__code__
TARGET_LINE = 4492  # the `for _ in range(n_attacks):` line

captured = []  # list of dict snapshots


def _local_tracer(frame, event, arg):
    if event == "line" and frame.f_lineno == TARGET_LINE:
        lv = frame.f_locals
        try:
            self_u = lv["self"]
            target_u = lv["target"]
            mode = lv["mode"]
            if mode != "melee":
                return None
            if (self_u.profile.faction or "") != WE:
                return None
            if (target_u.profile.faction or "") not in KNIGHT_FACTIONS:
                return None
            captured.append({
                "attacker_name": self_u.profile.name,
                "attacker_faction": self_u.profile.faction,
                "target_name": target_u.profile.name,
                "target_faction": target_u.profile.faction,
                "strength": lv["p"].melee_strength,
                "toughness": target_u.profile.toughness,
                "ap": lv["ap"],
                "weapon": lv["p"].melee_weapon,
                "attacks_char": lv["p"].melee_attacks,
                "damage_per_shot": lv["p"].melee_damage_per_shot,
                "base_save": target_u.profile.save,
                "invuln_melee": target_u.profile.invuln_save_melee,
                "hit_target": lv["hit_target"],
                "wound_target": lv["wound_target"],
                "save_target": lv["save_target"],
                "target_wounds_before": target_u.current_health,
                "lethal_hits": lv.get("effective_lethal_hits"),
                "sustained_hits": lv.get("effective_sustained_hits"),
                "devastating_wounds": bool(lv["p"].melee_devastating_wounds),
                "twin_linked": lv.get("_effective_twin_linked"),
                "n_attacks": lv.get("n_attacks"),
            })
        except Exception as exc:  # pragma: no cover - diagnostic robustness
            captured.append({"error": repr(exc)})
        return None  # stop line-tracing this frame; let it run to completion
    return _local_tracer


def _global_tracer(frame, event, arg):
    if event == "call" and frame.f_code is ATTACK_CODE:
        return _local_tracer
    return None


def wound_probability_chart(strength: int, toughness: int) -> str:
    """Independent hand-transcription of the printed 10e Strength-vs-Toughness
    Wound chart (Wahapedia core rules, Wound Roll section), used as the
    external oracle the captured `wound_target` values are checked against.
    """
    if strength >= 2 * toughness:
        return "2+"
    if 2 * strength <= toughness:
        return "6+"
    if strength > toughness:
        return "3+"
    if strength == toughness:
        return "4+"
    return "5+"


def replay_one(a_fac: str, b_fac: str, s: int):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=primary)
    sys.settrace(_global_tracer)
    try:
        result = battle.run()
    finally:
        sys.settrace(None)
    return result


def main():
    anchor_path = "data/_anchor_sc50a_n80_log.json"
    with open(anchor_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    games = [
        (a, b, s, w) for a, b, s, w in data["games"]
        if WE in (a, b) and (KNIGHT_FACTIONS & {a, b})
    ]
    print(f"Found {len(games)} World Eaters vs Knights games in the anchor.")

    n_games_to_replay = 3
    replayed = 0
    for a_fac, b_fac, s, recorded_winner in games:
        if replayed >= n_games_to_replay:
            break
        print(f"\n=== Replaying {a_fac} vs {b_fac} seed={s} (recorded winner={recorded_winner}) ===")
        result = replay_one(a_fac, b_fac, s)
        if result is None:
            print("  (empty army, skipped)")
            continue
        print(f"  Replayed winner: {result.winner}  rounds={result.rounds}")
        replayed += 1

    print(f"\nTotal World-Eaters-attacker-vs-Knight-target melee sequences captured: {len(captured)}")
    out_path = "data/_dura_audit_e_melee_sequences.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(captured, fh, indent=2)
    print(f"Wrote {out_path}")

    # Hand-verification pass: cross-check every captured wound_target against
    # the independent chart oracle.
    print("\n--- Hand-verification against the printed Strength-vs-Toughness chart ---")
    mismatches = 0
    for i, c in enumerate(captured):
        if "error" in c:
            print(f"  [{i}] ERROR capturing frame: {c['error']}")
            continue
        expected = wound_probability_chart(c["strength"], c["toughness"])
        expected_n = int(expected[0])
        actual_n = c["wound_target"]
        ok = "OK" if expected_n == actual_n else "MISMATCH"
        if expected_n != actual_n:
            mismatches += 1
        print(
            f"  [{i}] {c['attacker_name']} ({c['weapon']}, S{c['strength']}) vs "
            f"{c['target_name']} (T{c['toughness']}, Sv{c['base_save']}+/inv "
            f"{c['invuln_melee']}+, AP{c['ap']}) -> hit {c['hit_target']}+, "
            f"wound {c['wound_target']}+ (chart says {expected}), "
            f"save {c['save_target']}+ -- {ok}"
        )
    print(f"\n{len(captured) - mismatches}/{len(captured)} wound targets matched the printed chart "
          f"({mismatches} mismatches).")


if __name__ == "__main__":
    main()
