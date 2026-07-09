"""
Headless AI Lab run: evolve Intercessor duel piloting against a fixed
baseline, promoting champions into a strain lineage.

The AI Lab is an EXPLORATORY sandbox outside the Stage 1 / Stage 2
calibration pipeline — it touches no points files and no tournament data.
See docs/AI_LAB_PLAN.md.

Usage:
    python -m scripts.ai_lab_run                        # small default run
    python -m scripts.ai_lab_run --population 30 --generations-per-epoch 40 \
        --duels-per-genome 20 --epochs 5 --seed 12345
"""
from __future__ import annotations

import argparse
import os
import sys

# Lock Python's hash randomisation off so set()/dict iteration order inside
# the simulator is reproducible — same discipline as scripts/evaluate_vs_meta.
# subprocess re-launch rather than os.exec*: the Windows exec emulation is
# flaky with redirected stdout (see the note in scripts/evaluate_vs_meta.py).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(
        subprocess.run(
            [sys.executable, "-m", "scripts.ai_lab_run"] + sys.argv[1:],
            env=os.environ,
        ).returncode
    )

from code.ai_lab.duel import DEFAULT_PROFILE_KEY, DEFAULT_SQUAD_SIZE  # noqa: E402
from code.ai_lab.ga import (  # noqa: E402
    DEFAULT_CONFIRMATION_N,
    evolve_lineage,
)
from code.ai_lab.genome import NEUTRAL_GENOME  # noqa: E402
from code.ai_lab.history import RunRecorder, append_lineage_row  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="AI Lab: genetic-algorithm duel sandbox (headless)")
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--generations-per-epoch", type=int, default=15)
    parser.add_argument("--duels-per-genome", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=3,
                        help="Maximum promoted epochs before stopping")
    parser.add_argument("--promotion-threshold", type=float, default=0.55)
    parser.add_argument("--confirmation-n", type=int,
                        default=DEFAULT_CONFIRMATION_N,
                        help="Must be large enough that a confirmation win "
                             "rate sitting exactly at --promotion-threshold "
                             "clears the Wilson 95%% lower bound (> 0.5) — "
                             "evolve_lineage refuses to start otherwise. "
                             "See ai_lab.ga.min_confirmation_n_for_threshold.")
    parser.add_argument("--elite-count", type=int, default=2)
    parser.add_argument("--margin-weight", type=float, default=0.2)
    parser.add_argument("--mutation-sigma-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile-key", type=str, default=DEFAULT_PROFILE_KEY)
    parser.add_argument("--squad-size", type=int, default=DEFAULT_SQUAD_SIZE)
    parser.add_argument("--label", type=str, default="",
                        help="Free-text label recorded on lineage rows")
    parser.add_argument("--no-lineage-csv", action="store_true",
                        help="Skip appending to docs/ai_lab_lineage.csv "
                             "(smoke tests)")
    args = parser.parse_args(argv)

    params = {
        "population_size": args.population,
        "generations_per_epoch": args.generations_per_epoch,
        "duels_per_genome": args.duels_per_genome,
        "max_epochs": args.epochs,
        "promotion_threshold": args.promotion_threshold,
        "confirmation_n": args.confirmation_n,
        "elite_count": args.elite_count,
        "margin_weight": args.margin_weight,
        "mutation_sigma_scale": args.mutation_sigma_scale,
        "seed_base": args.seed,
        "profile_key": args.profile_key,
        "squad_size": args.squad_size,
    }
    recorder = RunRecorder(params)
    baseline = NEUTRAL_GENOME
    print(f"[ai_lab] run {recorder.run_id}: population={args.population} "
          f"generations/epoch={args.generations_per_epoch} "
          f"duels/genome={args.duels_per_genome} max epochs={args.epochs}")

    events = evolve_lineage(
        seed_base=args.seed,
        population_size=args.population,
        generations_per_epoch=args.generations_per_epoch,
        duels_per_genome=args.duels_per_genome,
        max_epochs=args.epochs,
        promotion_threshold=args.promotion_threshold,
        confirmation_n=args.confirmation_n,
        elite_count=args.elite_count,
        margin_weight=args.margin_weight,
        mutation_sigma_scale=args.mutation_sigma_scale,
        profile_key=args.profile_key,
        squad_size=args.squad_size,
    )
    try:
        for kind, payload in events:
            recorder.on_event(kind, payload, baseline)
            if kind == "generation":
                print(f"[epoch {payload.epoch} gen {payload.generation:3d}] "
                      f"best wr={payload.best.win_rate:.3f} "
                      f"fit={payload.best.fitness:.3f} "
                      f"mean wr={payload.mean_win_rate:.3f}")
            elif kind == "confirmation":
                print(f"  confirmation n={payload.confirmation.n}: "
                      f"wr={payload.confirmation.win_rate:.3f} "
                      f"wilson_lower={payload.wilson_lower:.3f}")
            elif kind == "promotion":
                baseline = payload.champion
                print(f"  PROMOTED epoch {payload.epoch} champion after "
                      f"{payload.generations_to_promote} generations: "
                      f"{payload.champion.as_dict()}")
                if not args.no_lineage_csv:
                    append_lineage_row(payload, label=args.label)
            elif kind == "epoch_exhausted":
                print(f"[epoch {payload}] exhausted without promotion — "
                      f"lineage ends")
    finally:
        path = recorder.save()
        print(f"[ai_lab] snapshot written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
