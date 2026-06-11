"""
Deterministic motion-proof harness for the code/simulator.py modularization.

WHAT THIS IS FOR
----------------
The simulator is being split from one 13k-line module into a code/sim/ package
by pure code motion (see docs/SIM_MODULARIZATION_PLAN.md). "Pure code motion"
means every extraction must be provably behaviour-identical: zero logic edits,
zero reordering of dictionary or set iteration, zero change to the order in
which random rolls happen. The calibration loop depends on this — its paired
common-random-number evaluations and anchor reuse die if the random number
generator call order shifts even slightly.

This harness produces a single SHA-256 fingerprint of a fixed bundle of
battles. Run it on the unmodified tree to record a baseline hash, then run it
again after every extraction commit. If the hash matches byte-for-byte, the
motion changed nothing observable; if it differs, the motion changed behaviour
and must be fixed before committing.

WHY NOT run.py --cli
--------------------
The command-line demo battle (code/main.demo_verbose_battle) does NOT seed the
global random module before running its battle, so consecutive invocations of
`python run.py --cli` are NOT byte-identical — verified directly. It therefore
cannot serve as a determinism proof. This harness seeds explicitly, exactly the
way scripts/evaluate_vs_meta.py does in its worker (random.seed(pair_seed) then
build both armies off a per-arm random.Random), so its output is reproducible.

DETERMINISM CONTRACT
--------------------
PYTHONHASHSEED must be 0 so the simulator's internal set / dict-of-string
iteration order is reproducible (the same reason evaluate_vs_meta re-execs
itself). This module re-execs itself with PYTHONHASHSEED=0 if it is not already
set, mirroring evaluate_vs_meta. The battles run serially and in-process (no
worker pool) so there is no cross-process ordering to worry about.

USAGE
    PYTHONHASHSEED=0 python scripts/sim_motion_proof.py
    PYTHONHASHSEED=0 python scripts/sim_motion_proof.py --json   # full record to stdout

Run it twice and confirm the printed FINGERPRINT line is identical before
trusting it as a proof tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path

# Running as a loose script (`python scripts/sim_motion_proof.py`) puts the
# scripts/ directory on sys.path[0], not the repo root, so `import code.*`
# fails. Put the repo root (this file's parent's parent) on the path so the
# `code` package resolves regardless of how the harness is launched.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Lock Python's hash randomisation off so set() / dict-of-string iteration
# order is reproducible across runs — without this the simulator's internal
# sets (advance / battleshock / fresh-arrival trackers) shuffle and the record
# drifts between back-to-back invocations. Mirrors the re-exec in
# scripts/evaluate_vs_meta.py exactly.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "scripts/sim_motion_proof.py"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.maps import PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS
from code.simulator import Battle


# Three-plus fixed faction pairings with fixed seeds. Chosen to exercise
# different unit profiles (a shooty Marine line, a horde, an elite-vehicle
# list, a psyker faction, a melee brawl) so the fingerprint is sensitive to a
# wide range of code paths. Each entry is (army_a_faction, army_b_faction, seed).
BATTLES = (
    ("Adeptus Astartes", "Orks", 1),
    ("Necrons", "Tyranids", 2),
    ("Imperial Knights", "Astra Militarum", 3),
    ("Thousand Sons", "Drukhari", 4),
    ("Adeptus Custodes", "World Eaters", 5),
)

POINTS_BUDGET = 2000


def _pick_rotation_map(seed: int):
    """Deterministic map rotation — identical rule to
    scripts/evaluate_vs_meta._pick_rotation_map so the harness exercises the
    same map geometry the calibration loop does."""
    rotation = PARIAH_NEXUS_2K_ROTATION
    key = rotation[seed % len(rotation)]
    return STOCK_MAPS[key]


def _run_one(a_fac: str, b_fac: str, seed: int) -> dict:
    """Build two armies and run one battle, mirroring the construction in
    scripts/evaluate_vs_meta._run_battle_job exactly (same seeding scheme), and
    return a fully deterministic per-battle record.

    The record captures every field of BattleResult that the simulator
    determines, so a behaviour change anywhere in the move / shoot / fight /
    charge / command / battleshock / scoring pipeline perturbs the fingerprint.
    """
    # Seed the GLOBAL random module before army building, then build each army
    # off its own private random.Random — exactly the evaluate_vs_meta pattern.
    pair_seed = seed
    random.seed(pair_seed)
    a = build_faction_random_army(
        "A", a_fac, POINTS_BUDGET, rng=random.Random(seed),
    )
    b = build_faction_random_army(
        "B", b_fac, POINTS_BUDGET, rng=random.Random(seed + 10000),
    )
    battle_map = _pick_rotation_map(seed)
    result = Battle(a, b, map_=battle_map).run()

    # round_history is a list of (a_alive, b_alive) tuples; JSON turns tuples
    # into lists, which is fine — the comparison is on the serialized bytes.
    return {
        "a_faction": a_fac,
        "b_faction": b_fac,
        "seed": seed,
        "a_units_built": len(a.units),
        "b_units_built": len(b.units),
        "winner": result.winner,
        "rounds": result.rounds,
        "a_name": result.a_name,
        "b_name": result.b_name,
        "a_start": result.a_start,
        "b_start": result.b_start,
        "a_survivors": result.a_survivors,
        "b_survivors": result.b_survivors,
        "a_vp": result.a_vp,
        "b_vp": result.b_vp,
        "a_points_remaining": round(result.a_points_remaining, 6),
        "b_points_remaining": round(result.b_points_remaining, 6),
        "round_history": [list(r) for r in (result.round_history or [])],
    }


def build_record() -> dict:
    """Run every battle in BATTLES and assemble the full deterministic record."""
    battles = [_run_one(a, b, s) for (a, b, s) in BATTLES]
    return {
        "schema": "sim_motion_proof/v1",
        "points_budget": POINTS_BUDGET,
        "battles": battles,
    }


def fingerprint(record: dict) -> str:
    """SHA-256 of the canonical JSON serialization (sorted keys, compact
    separators) of the record. Sorted keys make the bytes independent of dict
    insertion order, so the hash isolates real behaviour changes."""
    blob = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full per-battle record as JSON before the fingerprint.",
    )
    args = parser.parse_args()

    record = build_record()
    digest = fingerprint(record)

    if args.json:
        print(json.dumps(record, sort_keys=True, indent=2))

    for b in record["battles"]:
        print(
            f"{b['a_faction']:18s} vs {b['b_faction']:18s} "
            f"seed={b['seed']}  winner={str(b['winner']):4s}  "
            f"rounds={b['rounds']}  a_vp={b['a_vp']:>3}  b_vp={b['b_vp']:>3}  "
            f"survivors {b['a_survivors']}/{b['a_start']} : "
            f"{b['b_survivors']}/{b['b_start']}"
        )
    print(f"FINGERPRINT sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
