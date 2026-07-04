"""READ-ONLY instrumentation for the durability fidelity wave, audit C
("points-out" side): replay a handful of anchored Imperial Knights games and
log, per battle round, the Knights army's shooting activations taken and the
victory points scored by/against it. Purely descriptive -- no evaluation
sweep, no statistic changed, nothing written back to tracked files.

Mirrors scripts._ec_crater_replay's exact reconstruction of an anchored game
(same pair_seed formula, same army-build call, same map/mission draw), reusing
scripts.evaluate_vs_meta's FACTIONS / _pick_rotation_map / _pick_primary_mission
so the replay is a byte-identical reconstruction of what evaluate_vs_meta.py
actually ran to produce the standing anchor.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dura_audit_c_uptime_replay
Reads: data/_anchor_sc50a_n80_log.json (copied from the repository root anchor)
Writes: nothing tracked -- prints a per-round report to stdout only.
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
        [sys.executable, "-m", "scripts._dura_audit_c_uptime_replay"] + sys.argv[1:],
        env=os.environ,
    ).returncode)

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitShot, UnitFought, UnitKilled,
    ObjectiveScored, BattleEnded, EventLog,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

ANCHOR_PATH = "data/_anchor_sc50a_n80_log.json"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

# The "Knights cell" -- one fixed matchup pairing (Adeptus Astartes vs
# Imperial Knights) replayed across four consecutive per-pair seeds, exactly
# as evaluate_vs_meta.py itself schedules a cell (pair_seed = (ai*1000+bi)*100+s).
CELL_A_FAC = "Adeptus Astartes"
CELL_B_FAC = "Imperial Knights"
CELL_SEEDS = [0, 1, 2, 3]


def load_anchor_winner(path: str, a_fac: str, b_fac: str, s: int):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    for ga, gb, gs, winner in data["games"]:
        if ga == a_fac and gb == b_fac and gs == s:
            return winner
    return "NOT-IN-ANCHOR"


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


def instrument_uptime(a_fac, b_fac, s, recorded_winner, result, log, battle):
    """Per-round: Knights units alive at round start, units that took a
    shooting activation (>=1 UnitShot as attacker) that round, Knights units
    killed that round, and VP scored by/against the Knights side that round
    (both raw uncapped and Pariah-Nexus-capped standing)."""
    if battle is None:
        print(f"  [{a_fac} vs {b_fac} s={s}] EMPTY ARMY -- skipped")
        return

    knights_side = "A" if a_fac == "Imperial Knights" else "B"

    ev = log.events
    uid_info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                uid_info[u.uid] = {"name": u.name, "army": u.army, "keywords": u.unit_keywords}

    knights_uids = {uid for uid, i in uid_info.items() if i["army"] == knights_side}
    alive = set(knights_uids)  # shrinks as UnitKilled events arrive

    cur_round = 0
    per_round = {}  # round_num -> dict of tallies

    def bucket(rnd):
        return per_round.setdefault(rnd, {
            "alive_at_round_start": None,
            "activated_uids": set(),
            "killed_uids": set(),
            "a_vp_total": None, "b_vp_total": None,
            "a_vp_capped": None, "b_vp_capped": None,
        })

    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
            bucket(cur_round)["alive_at_round_start"] = len(alive & knights_uids)
        elif isinstance(e, UnitShot):
            if e.attacker_uid in knights_uids:
                bucket(cur_round)["activated_uids"].add(e.attacker_uid)
        elif isinstance(e, UnitKilled):
            if e.unit_uid in knights_uids and e.unit_uid in alive:
                alive.discard(e.unit_uid)
                bucket(cur_round)["killed_uids"].add(e.unit_uid)
        elif isinstance(e, RoundEnded):
            b = bucket(e.round_num)
            b["a_vp_total"], b["b_vp_total"] = e.a_vp_total, e.b_vp_total
            b["a_vp_capped"], b["b_vp_capped"] = e.a_vp_capped, e.b_vp_capped

    print(f"\n=== {a_fac} vs {b_fac}  seed={s}  (Knights = side {knights_side}) ===")
    print(f"  Recorded anchor winner: {recorded_winner}   Replayed winner: "
          f"{result.winner if result else None}   "
          f"(match={ (result.winner if result else None) == recorded_winner })")
    print(f"  Knights units at battle start: {len(knights_uids)}")
    prev_knights_vp = 0
    prev_other_vp = 0
    for rnd in sorted(per_round):
        b = per_round[rnd]
        alive_start = b["alive_at_round_start"]
        activated = len(b["activated_uids"])
        killed = len(b["killed_uids"])
        knights_vp_total = b["a_vp_total"] if knights_side == "A" else b["b_vp_total"]
        other_vp_total = b["b_vp_total"] if knights_side == "A" else b["a_vp_total"]
        knights_vp_capped = b["a_vp_capped"] if knights_side == "A" else b["b_vp_capped"]
        other_vp_capped = b["b_vp_capped"] if knights_side == "A" else b["a_vp_capped"]
        knights_vp_delta = (knights_vp_total or 0) - prev_knights_vp
        other_vp_delta = (other_vp_total or 0) - prev_other_vp
        prev_knights_vp = knights_vp_total or prev_knights_vp
        prev_other_vp = other_vp_total or prev_other_vp
        activation_rate = f"{activated}/{alive_start}" if alive_start else "0/0"
        print(f"  Round {rnd}: Knights alive-at-start={alive_start:>2}  "
              f"shooting-activations={activation_rate:>5}  killed-this-round={killed}  "
              f"VP-this-round Knights=+{knights_vp_delta:<3} opponent=+{other_vp_delta:<3}  "
              f"running-total Knights={knights_vp_total}(capped {knights_vp_capped})  "
              f"opponent={other_vp_total}(capped {other_vp_capped})")

    knights_survivors = (result.a_survivors if knights_side == "A" else result.b_survivors) if result else None
    other_survivors = (result.b_survivors if knights_side == "A" else result.a_survivors) if result else None
    print(f"  Final survivors: Knights={knights_survivors}  opponent={other_survivors}  "
          f"rounds played={result.rounds if result else None}")


def main():
    print(f"Uptime instrumentation -- Knights cell: {CELL_A_FAC} vs {CELL_B_FAC}, "
          f"seeds {CELL_SEEDS}")
    print("(Read-only replay of the standing anchor; no statistics are changed.)")
    for s in CELL_SEEDS:
        recorded_winner = load_anchor_winner(ANCHOR_PATH, CELL_A_FAC, CELL_B_FAC, s)
        result, log, a, b, battle = replay_one(CELL_A_FAC, CELL_B_FAC, s)
        instrument_uptime(CELL_A_FAC, CELL_B_FAC, s, recorded_winner, result, log, battle)


if __name__ == "__main__":
    main()
