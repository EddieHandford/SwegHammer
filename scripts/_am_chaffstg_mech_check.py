"""Mechanism-check diagnostic for SWEG_AM_CHAFF_STAGING (companion to the
committed scripts/_ec_crater_replay.py family): replay a handful of the
crater's own Astra Militarum versus Emperor's Children LOSS seeds twice
each -- once with SWEG_AM_CHAFF_STAGING unset (reproduces the crater
diagnostic baseline) and once with SWEG_AM_CHAFF_STAGING=1 -- and report
whether the chaff actually stages (per-unit staging-instrumentation names)
and whether the round-3/4 piecemeal death shape changes.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._am_chaffstg_mech_check
"""
from __future__ import annotations

import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._am_chaffstg_mech_check"] + sys.argv[1:], env=os.environ).returncode)

from scripts._ec_crater_replay import (
    AM, EC, load_anchor_games, replay_one, summarise_game,
)

N_LOSS_SEEDS = 6


def main():
    anchor_path = "data/_anchor_sc48a_n80_log.json"
    games = load_anchor_games(anchor_path)
    # `winner` in the anchor log is the SIDE letter ('A'/'B'), not a faction
    # name -- compute the side Astra Militarum occupies in each game and
    # select the games where the recorded winner is the OTHER side.
    loss_games = []
    for a_fac, b_fac, s, winner in games:
        am_side = "A" if a_fac == AM else "B"
        if winner is not None and winner != am_side:
            loss_games.append((a_fac, b_fac, s, winner))
    picked = loss_games[:N_LOSS_SEEDS]
    print(f"Picked {len(picked)} of {len(loss_games)} Astra Militarum losses "
          f"vs Emperor's Children to replay under both arms.\n")

    for a_fac, b_fac, s, recorded_winner in picked:
        print(f"=== seed {s}: {a_fac} (A) vs {b_fac} (B), recorded winner={recorded_winner} ===")
        for label, gate_on in (("OFF (baseline)", False), ("ON (SWEG_AM_CHAFF_STAGING=1)", True)):
            if gate_on:
                os.environ["SWEG_AM_CHAFF_STAGING"] = "1"
            else:
                os.environ.pop("SWEG_AM_CHAFF_STAGING", None)
            os.environ["SWEG_STAGING_INSTR"] = "1"
            result, log, a, b, battle = replay_one(a_fac, b_fac, s)
            summ = summarise_game(a_fac, b_fac, s, recorded_winner, result, log, battle)
            stage_log = getattr(battle, "_staging_log", None) or []
            am_side_prefix = "A" if a_fac == AM else "B"
            am_stage_events = [
                e for e in stage_log if e[1] == AM
            ]
            am_hold = sum(1 for e in am_stage_events if e[5] == "HOLD")
            am_edge = sum(1 for e in am_stage_events if e[5] == "EDGE")
            names = sorted({e[2] for e in am_stage_events})
            print(f"  [{label}] winner={summ['replayed_winner']} "
                  f"am_capped={summ['am_capped']} ec_capped={summ['ec_capped']} "
                  f"am_deaths_by_round={summ['am_deaths_by_round']} "
                  f"staging_events(AM)={len(am_stage_events)} (hold={am_hold}, edge={am_edge}) "
                  f"units staged={names}")
        print()


if __name__ == "__main__":
    main()
