"""
Robust launcher for the calibration evaluation.

Use `python -m scripts.run_eval --battles 80 --use-archetype [--log-games out.json]`
instead of `python -m scripts.evaluate_vs_meta ...`.

This wrapper presets PYTHONHASHSEED=0 and PYTHONIOENCODING=utf-8 in-process
before importing evaluate_vs_meta, so the os.execvpe re-exec (which caused
empty-output and exit-code-127 flakes under background redirects) is never
triggered. All command-line flags pass straight through to evaluate_vs_meta's
argument parser.
"""
import os
import sys

# Set the environment variables BEFORE importing evaluate_vs_meta so that
# the re-exec branch at lines 28-30 is never taken.
os.environ["PYTHONHASHSEED"] = "0"
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Replace sys.argv[0] to keep argparse happy, then call the main function.
# This ensures all flags (--battles, --use-archetype, --workers, --log-games,
# --seed-start, --out, --equation-prices, --swegpoints, --sweghammer) are
# passed through without modification.
sys.argv[0] = "evaluate_vs_meta"
from scripts import evaluate_vs_meta

# MUST be guarded: evaluate_vs_meta uses a ProcessPoolExecutor, and on Windows
# (spawn start method) each worker re-imports this __main__ module. Without the
# guard, every worker would re-run main() -> recursive process spawning ->
# BrokenProcessPool. The guard makes the re-import inert in workers (they import
# scripts.evaluate_vs_meta directly to unpickle _run_battle_job).
if __name__ == "__main__":
    evaluate_vs_meta.main()
