"""Round-robin tournament helpers: lookup table I/O and Bradley-Terry scoring."""

from __future__ import annotations

import json
import itertools
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RESULTS_PATH = Path(__file__).parent.parent / "data" / "tournament_results.json"

# ---------------------------------------------------------------------------
# Lookup table I/O
# ---------------------------------------------------------------------------

def _pair_key(a: str, b: str) -> str:
    """Canonical key: lexicographically smaller unit always first."""
    return f"{a}|{b}" if a <= b else f"{b}|{a}"


def load_results() -> Dict:
    if not RESULTS_PATH.exists():
        return {}
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_results(results: Dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def record_matchup(
    results: Dict,
    key_a: str,
    key_b: str,
    wins_a: int,
    wins_b: int,
    draws: int,
    n_sims: int,
) -> None:
    """Upsert one matchup into the results dict (in-place)."""
    pk = _pair_key(key_a, key_b)
    canonical_a = min(key_a, key_b)
    canonical_b = max(key_a, key_b)
    # If key_a is the canonical first, wins_a/wins_b are already in canonical order.
    if key_a != canonical_a:
        wins_a, wins_b = wins_b, wins_a
    results[pk] = {
        "unit_a": canonical_a,
        "unit_b": canonical_b,
        "n_sims": n_sims,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "draws": draws,
    }


def get_win_rate(results: Dict, key_a: str, key_b: str) -> Optional[float]:
    """Win rate of key_a against key_b. Returns None if matchup not recorded."""
    pk = _pair_key(key_a, key_b)
    if pk not in results:
        return None
    row = results[pk]
    canonical_a = min(key_a, key_b)
    total = row["wins_a"] + row["wins_b"] + row["draws"]
    if total == 0:
        return None
    wins = row["wins_a"] if key_a == canonical_a else row["wins_b"]
    return wins / total


def faction_keys_in_results(results: Dict) -> Dict[str, List[str]]:
    """Return {faction: [unit_keys]} for every unit that appears in results."""
    from .units import UNIT_CATALOG
    seen: Dict[str, set] = {}
    for row in results.values():
        for side in ("unit_a", "unit_b"):
            k = row[side]
            if k in UNIT_CATALOG:
                faction = UNIT_CATALOG[k].faction
                seen.setdefault(faction, set()).add(k)
    return {f: sorted(ks) for f, ks in sorted(seen.items())}


def missing_pairs(results: Dict, keys: List[str]) -> List[Tuple[str, str]]:
    """All (a, b) combinations from keys that are not yet in results."""
    return [
        (a, b)
        for a, b in itertools.combinations(sorted(keys), 2)
        if _pair_key(a, b) not in results
    ]


# ---------------------------------------------------------------------------
# Bradley-Terry solver
# ---------------------------------------------------------------------------

def bradley_terry(keys: List[str], results: Dict, iterations: int = 500) -> Dict[str, float]:
    """
    Fit Bradley-Terry strength scores for a set of units.

    Returns {unit_key: score} normalised so scores sum to 1.
    Units with no recorded matchups get score 0.
    """
    n = len(keys)
    idx = {k: i for i, k in enumerate(keys)}
    scores = [1.0] * n

    for _ in range(iterations):
        new_scores = [0.0] * n
        for i, ki in enumerate(keys):
            for j, kj in enumerate(keys):
                if i == j:
                    continue
                pk = _pair_key(ki, kj)
                if pk not in results:
                    continue
                row = results[pk]
                canonical_a = min(ki, kj)
                wins_i = row["wins_a"] if ki == canonical_a else row["wins_b"]
                wins_j = row["wins_b"] if ki == canonical_a else row["wins_a"]
                denom = scores[i] + scores[j]
                if denom > 0:
                    new_scores[i] += wins_i / denom

        total = sum(new_scores)
        if total == 0:
            break
        scores = [s / total for s in new_scores]

    return {k: scores[idx[k]] for k in keys}


def derive_points(
    keys: List[str],
    bt_scores: Dict[str, float],
    anchor_key: str,
    anchor_cost: float,
) -> Dict[str, float]:
    """
    Scale Bradley-Terry scores into points values using one anchor unit.

    anchor_key must be in keys and have a known GW cost (anchor_cost).
    """
    anchor_score = bt_scores.get(anchor_key, 0.0)
    if anchor_score == 0:
        return {k: 0.0 for k in keys}
    scale = anchor_cost / anchor_score
    return {k: bt_scores[k] * scale for k in keys}


# ---------------------------------------------------------------------------
# Matrix builder (for heatmap)
# ---------------------------------------------------------------------------

def win_rate_matrix(
    keys: List[str], results: Dict
) -> Tuple[List[List[Optional[float]]], List[str]]:
    """
    Build an N×N matrix where matrix[i][j] = win rate of keys[i] vs keys[j].

    Diagonal is None. Unrecorded matchups are also None.
    Returns (matrix, keys) — same key order used for both axes.
    """
    n = len(keys)
    matrix = [[None] * n for _ in range(n)]
    for i, ki in enumerate(keys):
        for j, kj in enumerate(keys):
            if i == j:
                continue
            matrix[i][j] = get_win_rate(results, ki, kj)
    return matrix, keys
