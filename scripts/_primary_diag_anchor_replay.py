"""Read-only diagnostic (primary victory-point over-score investigation).

`scripts.diag_signatures` reports a sim mean primary victory-point-per-player-
per-game of 35.0 against the real ~29 (Pariah Nexus / Chapter Approved
2025-26) reference. But `diag_signatures.Battle(...)` calls never pass a
`primary_mission` argument and never set `SWEG_PRIMARY_MISSION`, so every
game it runs falls through `Battle.__init__`'s default chain straight to
"take_and_hold" -- the single most holder-friendly primary mission. The
production/gated evaluation (`scripts.evaluate_vs_meta`, and therefore the
standing anchor used for the headline mean-absolute-error metric) instead
draws a game-by-game primary mission from the real Chapter Approved 2025-26
ten-card deck via `_pick_primary_mission` (default-on, `SWEG_PRIMARY_DECK`
unset or "1"). This script asks: how much of the 35-vs-29 gap is an artifact
of `diag_signatures` measuring the wrong (single-mission) configuration,
versus a genuine over-score under the production mission mix the anchor
actually uses?

Method: replay a stratified subset of the standing anchor
(data/_anchor_sc53a_n80_log.json) -- Death Guard cells (the top durable
over-pole) and Orks cells (a ground-down horde under-pole), first 15 seeds
per opponent, mirroring the audit-D stratification pattern
(`scripts/_dura_audit_d_quick.py`) -- using the EXACT evaluate_vs_meta
reconstruction (`_pick_rotation_map` + `_pick_primary_mission` keyed off the
same `pair_seed`), and separately replay the identical seeds forced to
"take_and_hold" for every game. Compare the two using the SAME signature
machinery as `scripts.diag_signatures` (`_parse_event_log` /
`_compute_signatures`), then break the production-mix run down by mission
type.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._primary_diag_anchor_replay
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._primary_diag_anchor_replay"] + sys.argv[1:],
        env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission
from scripts.diag_signatures import _parse_event_log, _compute_signatures, _GameRecord

ANCHOR = "data/_anchor_sc53a_n80_log.json"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}
SEEDS_PER_OPPONENT = 15


def load_stratified(path: str, faction: str, seeds_per_opp: int = SEEDS_PER_OPPONENT):
    d = json.load(open(path, encoding="utf-8"))
    by_opp: Dict[str, list] = defaultdict(list)
    for a_fac, b_fac, s, w in d["games"]:
        if faction in (a_fac, b_fac):
            opp = b_fac if a_fac == faction else a_fac
            if len(by_opp[opp]) < seeds_per_opp:
                by_opp[opp].append((a_fac, b_fac, s, w))
    out = []
    for lst in by_opp.values():
        out.extend(lst)
    return out


def replay_one(a_fac: str, b_fac: str, s: int, force_take_and_hold: bool = False):
    """Mirrors scripts.evaluate_vs_meta._run_battle_job's exact reconstruction."""
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None, None, None
    battle_map = _pick_rotation_map(s)
    mission = "take_and_hold" if force_take_and_hold else _pick_primary_mission(pair_seed)
    log = EventLog()
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=mission, subscribers=[log])
    result = battle.run()
    return result, log, (mission or "take_and_hold")


def run_subset(games, force_take_and_hold: bool):
    records: List[_GameRecord] = []
    mission_counts: Dict[str, int] = defaultdict(int)
    mission_records: Dict[str, List[_GameRecord]] = defaultdict(list)
    for a_fac, b_fac, s, _w in games:
        result, log, mission = replay_one(a_fac, b_fac, s, force_take_and_hold=force_take_and_hold)
        if result is None:
            continue
        rec = _parse_event_log(log, result)
        records.append(rec)
        mission_counts[mission] += 1
        mission_records[mission].append(rec)
    return records, mission_counts, mission_records


def _fmt_sigs(label: str, sigs: dict) -> str:
    means = sigs["per_round_primary_means"]
    trajectory = ", ".join(
        f"r{i+1}={m:.1f}" if m is not None else f"r{i+1}=-" for i, m in enumerate(means)
    )
    return (
        f"{label}: n_games={sigs['n_games']}  mean_primary={sigs['mean_primary_per_player']:.1f}"
        f"  mean_secondary={sigs['mean_secondary_per_player']:.1f}"
        f"  cap15_fraction={sigs['cap15_fraction']*100:.1f}%"
        f"  trajectory: {trajectory}"
    )


def main():
    print("=" * 78)
    print("PRIMARY OVER-SCORE DIAGNOSTIC — anchor-seeded replay under the")
    print("production mission-deck mix vs forced take-and-hold-only")
    print("=" * 78)

    for faction_label in ("Death Guard", "Orks"):
        print(f"\n--- {faction_label} cells (stratified: first {SEEDS_PER_OPPONENT} seeds/opponent) ---")
        games = load_stratified(ANCHOR, faction_label)
        print(f"Loaded {len(games)} games.")

        print("\n[A] Forced take_and_hold every game (mirrors diag_signatures.py's default):")
        recs_th, _mc_th, _mr_th = run_subset(games, force_take_and_hold=True)
        sigs_th = _compute_signatures(recs_th)
        print("  " + _fmt_sigs("take-and-hold-only", sigs_th))

        print("\n[B] Production mission-deck mix (exact evaluate_vs_meta / anchor reconstruction):")
        recs_mix, mission_counts, mission_records = run_subset(games, force_take_and_hold=False)
        sigs_mix = _compute_signatures(recs_mix)
        print("  " + _fmt_sigs("production-mix", sigs_mix))

        print(f"\n  Delta (mix - take_and_hold_only) mean primary: "
              f"{sigs_mix['mean_primary_per_player'] - sigs_th['mean_primary_per_player']:+.2f}")

        print("\n  Mission draw counts in this subset (of games actually played):")
        for m, c in sorted(mission_counts.items(), key=lambda kv: -kv[1]):
            print(f"    {m:20s} {c:4d} games")

        print("\n  Per-mission primary VP mean (within the production-mix run):")
        for m, recs in sorted(mission_records.items(), key=lambda kv: -len(kv[1])):
            if len(recs) < 2:
                continue
            s = _compute_signatures(recs)
            print(f"    {m:20s} n={s['n_games']:4d}  mean_primary={s['mean_primary_per_player']:.1f}"
                  f"  mean_secondary={s['mean_secondary_per_player']:.1f}")

    print("\n" + "=" * 78)
    print("Reference: real mean primary VP per player per game ~= 29 "
          "(Pariah Nexus / Chapter Approved 2025-26, docs/REAL_META_SIGNATURES.md).")
    print("scripts.diag_signatures --pairs 10 --seeds 15 (all-take-and-hold, mixed")
    print("factions) measured 35.0.")


if __name__ == "__main__":
    main()
