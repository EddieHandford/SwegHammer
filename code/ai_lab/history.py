"""Persistence for AI Lab runs: the lineage CSV and per-run JSON snapshots.

Two artefacts, following the repo's existing conventions:

  * docs/ai_lab_lineage.csv — one row per PROMOTED epoch, the permanent
    "strain lineage" record (shape mirrors docs/mae_progress.csv: flat rows
    via csv.DictWriter, loaded by the dashboard).
  * data/ai_lab_runs/<run_id>.json — full per-generation detail for one run
    (shape mirrors the data/*.json snapshots: built_at ISO timestamp + a
    params block + row lists).
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from .ga import GenerationStats, PromotionRecord
from .genome import DuelGenome

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LINEAGE_CSV_PATH = os.path.join(_REPO_ROOT, "docs", "ai_lab_lineage.csv")
RUNS_DIR = os.path.join(_REPO_ROOT, "data", "ai_lab_runs")

LINEAGE_FIELDS = (
    "epoch", "when", "parent_epoch", "champion_genome_json",
    "confirmation_win_rate", "confirmation_n", "confirmation_wilson_lower",
    "generations_to_promote", "label",
)


def append_lineage_row(record: PromotionRecord, label: str = "",
                       csv_path: str = LINEAGE_CSV_PATH) -> None:
    """Append one promoted-epoch row, creating the file + header on first use."""
    row = {
        "epoch": record.epoch,
        "when": datetime.now().isoformat(timespec="seconds"),
        "parent_epoch": record.epoch - 1 if record.epoch > 0 else "",
        "champion_genome_json": json.dumps(record.champion.as_dict(),
                                           sort_keys=True),
        "confirmation_win_rate": f"{record.confirmation.win_rate:.4f}",
        "confirmation_n": record.confirmation.n,
        "confirmation_wilson_lower": f"{record.wilson_lower:.4f}",
        "generations_to_promote": record.generations_to_promote,
        "label": label,
    }
    is_new = not os.path.exists(csv_path)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LINEAGE_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def read_lineage(csv_path: str = LINEAGE_CSV_PATH) -> List[Dict[str, str]]:
    """All lineage rows, oldest first. Missing file = no lineage yet = []."""
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class RunRecorder:
    """Collects an evolve_lineage event stream into one JSON snapshot.

    Feed every (kind, payload) event to on_event(); call save() at the end
    (or periodically — save() rewrites the whole snapshot each time, so a
    long run can checkpoint safely).
    """

    def __init__(self, params: Dict, run_id: Optional[str] = None):
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self.params = dict(params)
        self._epochs: List[Dict] = []

    def _epoch_bucket(self, epoch: int, baseline: DuelGenome) -> Dict:
        while len(self._epochs) <= epoch:
            self._epochs.append({
                "epoch": len(self._epochs),
                "baseline_genome": baseline.as_dict(),
                "generations": [],
                "promoted": None,
            })
        return self._epochs[epoch]

    def on_event(self, kind: str, payload, baseline: DuelGenome) -> None:
        if kind == "generation":
            stats: GenerationStats = payload
            bucket = self._epoch_bucket(stats.epoch, baseline)
            bucket["generations"].append({
                "generation": stats.generation,
                "best_fitness": stats.best.fitness,
                "best_win_rate": stats.best.win_rate,
                "best_mean_margin": stats.best.mean_margin,
                "mean_fitness": stats.mean_fitness,
                "mean_win_rate": stats.mean_win_rate,
                "best_genome": stats.best_genome.as_dict(),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
        elif kind == "promotion":
            record: PromotionRecord = payload
            bucket = self._epoch_bucket(record.epoch, baseline)
            bucket["promoted"] = {
                "champion_genome": record.champion.as_dict(),
                "confirmation_win_rate": record.confirmation.win_rate,
                "confirmation_n": record.confirmation.n,
                "confirmation_wilson_lower": record.wilson_lower,
                "generations_to_promote": record.generations_to_promote,
            }
        # "confirmation" and "epoch_exhausted" carry no extra snapshot state.

    def save(self, runs_dir: str = RUNS_DIR) -> str:
        os.makedirs(runs_dir, exist_ok=True)
        path = os.path.join(runs_dir, f"{self.run_id}.json")
        snapshot = {
            "run_id": self.run_id,
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "params": self.params,
            "epochs": self._epochs,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=1, sort_keys=True)
        return path
