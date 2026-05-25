"""
Tournament-list validation for the data-driven points equation.

Loads scraped Goonhammer tournament lists from ``data/tournament_lists/``,
fuzzy-matches each unit name against ``UNIT_CATALOG``, sums the equation's
predicted price for the list, and compares the resulting "equation cost
overrun" to the player's actual win record. This is the first independent,
list-level real-world check the equation gets — the rest of the calibration
loop only compares the equation against itself or against per-faction
tournament aggregates.

Public API
----------
load_tournament_lists(dir_path)  -> list[ListRecord]
match_units(list_record, catalog) -> MatchResult
score_list(match_result, fit, features_df, mults) -> ListScore
fit_winrate_model(scores)        -> WinrateFit
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from .equation_data_fit import FitResult, predict as eqfit_predict
from .units import UNIT_CATALOG, UnitProfile


TOURNAMENT_LISTS_DIR = Path(__file__).parent.parent / "data" / "tournament_lists"

# Tournament write-ups label factions slightly differently from BSData. Map
# the tournament-side label to the matching UNIT_CATALOG faction set so unit
# matching can scope its search. A tournament faction may legitimately span
# several catalogue factions (e.g. a "Space Marines" list pulls from
# "Adeptus Astartes" plus chapter sub-factions).
FACTION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "Space Marines":            ("Adeptus Astartes", "Ultramarines", "Imperial Fists",
                                 "Iron Hands", "Raven Guard", "Salamanders",
                                 "White Scars"),
    "Space Marines (Astartes)": ("Adeptus Astartes", "Ultramarines", "Imperial Fists",
                                 "Iron Hands", "Raven Guard", "Salamanders",
                                 "White Scars"),
    "Black Templars":           ("Black Templars", "Adeptus Astartes"),
    "Blood Angels":             ("Blood Angels", "Adeptus Astartes"),
    "Dark Angels":              ("Dark Angels", "Adeptus Astartes"),
    "Deathwatch":               ("Deathwatch", "Adeptus Astartes"),
    "Space Wolves":             ("Space Wolves", "Adeptus Astartes"),
    "Imperial Fists":           ("Imperial Fists", "Adeptus Astartes"),
    "Iron Hands":               ("Iron Hands", "Adeptus Astartes"),
    "Raven Guard":              ("Raven Guard", "Adeptus Astartes"),
    "Salamanders":              ("Salamanders", "Adeptus Astartes"),
    "Ultramarines":             ("Ultramarines", "Adeptus Astartes"),
    "White Scars":              ("White Scars", "Adeptus Astartes"),
    "Genestealer Cult":         ("Genestealer Cults",),
    "Genestealer Cults":        ("Genestealer Cults",),
    "Aeldari":                  ("Aeldari",),
    "Drukhari":                 ("Drukhari", "Aeldari"),
    "Ynnari":                   ("Ynnari", "Aeldari", "Drukhari"),
}


@dataclass
class TournamentUnit:
    """A single unit entry as it appears in a tournament list."""
    name: str
    model_count: int
    points: int


@dataclass
class ListRecord:
    """One player's army from one tournament round-robin."""
    source_file: str
    event_name: str
    event_date: Optional[str]
    event_size: Optional[int]
    player: str
    placement: Optional[int]
    wins: Optional[int]
    losses: Optional[int]
    draws: Optional[int]
    faction: str
    detachment: Optional[str]
    total_points: Optional[int]
    units: List[TournamentUnit]

    @property
    def actual_winrate(self) -> Optional[float]:
        """Wins divided by (wins + losses); None if record absent."""
        if self.wins is None or self.losses is None:
            return None
        games = self.wins + self.losses
        if games <= 0:
            return None
        return float(self.wins) / float(games)

    @property
    def placement_percentile(self) -> Optional[float]:
        """1.0 for first place, 0.0 for last; None if either field missing."""
        if self.placement is None or not self.event_size or self.event_size <= 1:
            return None
        return float(1.0 - (self.placement - 1) / (self.event_size - 1))


@dataclass
class MatchResult:
    """Outcome of matching a tournament list's units against UNIT_CATALOG."""
    list_record: ListRecord
    # (catalog_key, tournament_model_count, tournament_points_paid)
    matched_units: List[Tuple[str, int, int]] = field(default_factory=list)
    # (tournament_name, tournament_points_paid)
    unmatched: List[Tuple[str, int]] = field(default_factory=list)

    @property
    def coverage_points(self) -> int:
        return sum(p for _, _, p in self.matched_units)

    @property
    def total_points(self) -> int:
        return self.coverage_points + sum(p for _, p in self.unmatched)

    @property
    def coverage_ratio(self) -> float:
        total = self.total_points
        if total <= 0:
            return 0.0
        return self.coverage_points / total


@dataclass
class ListScore:
    """Equation-vs-reality summary for one list."""
    match: MatchResult
    predicted_total: float       # sum of equation price × model count × faction multiplier
    gw_total: int                # sum of tournament-paid points across MATCHED units only
    overrun_ratio: float         # predicted_total / gw_total (1.0 = equation agrees with GW)
    overrun_per_2000: float      # (predicted_total - gw_total) scaled to a full 2000-pt army

    # Per-unit detail used by the treemap visualisation.
    # Each entry: (catalog_key, models_fielded, gw_points_paid, predicted_per_model_x_mult)
    per_unit: List[Tuple[str, int, int, float]] = field(default_factory=list)

    @property
    def actual_winrate(self) -> Optional[float]:
        return self.match.list_record.actual_winrate

    @property
    def placement_percentile(self) -> Optional[float]:
        return self.match.list_record.placement_percentile


@dataclass
class WinrateFit:
    """OLS fit of actual_winrate against overrun_ratio."""
    intercept: float
    slope: float
    r_squared: float
    n: int


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_tournament_lists(
    dir_path: Path = TOURNAMENT_LISTS_DIR,
) -> List[ListRecord]:
    """Flatten every ``*.json`` under ``dir_path`` into one ListRecord per list.

    Lists flagged ``partial: True`` are dropped — their unit rosters are
    truncated mid-extraction and would skew the regression. Lists missing a
    faction are dropped (cannot match units without a faction scope).
    """
    if not dir_path.exists():
        raise FileNotFoundError(
            f"Tournament list directory not found: {dir_path}. "
            "Expected scraped Goonhammer JSON dumps to live here."
        )

    out: List[ListRecord] = []
    for json_path in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            raise ValueError(f"Could not parse tournament list file {json_path}: {e}")

        for event_block in data.get("events", []):
            event = event_block.get("event") or {}
            event_name = event.get("name") or ""
            event_date = event.get("date")
            event_size = event.get("size_players")

            for lst in event_block.get("lists", []):
                if lst.get("partial"):
                    continue
                faction = lst.get("faction")
                if not faction:
                    continue
                record = lst.get("record") or {}
                units = []
                for u in lst.get("units", []):
                    name = u.get("name")
                    if not name:
                        continue
                    units.append(TournamentUnit(
                        name=name,
                        model_count=int(u.get("model_count") or 1),
                        points=int(u.get("points") or 0),
                    ))
                if not units:
                    continue
                out.append(ListRecord(
                    source_file=json_path.name,
                    event_name=event_name,
                    event_date=event_date,
                    event_size=event_size,
                    player=lst.get("player") or "",
                    placement=lst.get("placement"),
                    wins=record.get("wins"),
                    losses=record.get("losses"),
                    draws=record.get("draws"),
                    faction=faction,
                    detachment=lst.get("detachment"),
                    total_points=lst.get("total_points"),
                    units=units,
                ))
    return out


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

def _faction_scope(tournament_faction: str) -> Tuple[str, ...]:
    """Catalogue factions to search when matching units from this tournament faction."""
    return FACTION_ALIASES.get(tournament_faction, (tournament_faction,))


def _normalise(s: str) -> str:
    """Lowercase, strip, collapse non-alphanumerics for fuzzy comparison."""
    return "".join(c.lower() if c.isalnum() else " " for c in s).strip()


def _build_faction_index(
    catalog: Dict[str, UnitProfile],
) -> Dict[str, List[Tuple[str, str, str]]]:
    """Group catalogue entries by faction: faction -> [(key, name, normalised_name), ...]."""
    index: Dict[str, List[Tuple[str, str, str]]] = {}
    for key, profile in catalog.items():
        fac = profile.faction or "Unknown"
        index.setdefault(fac, []).append((key, profile.name, _normalise(profile.name)))
    return index


# Module-level cache so we don't rebuild the index for every list.
_FACTION_INDEX_CACHE: Dict[int, Dict[str, List[Tuple[str, str, str]]]] = {}


def _faction_index_for(
    catalog: Dict[str, UnitProfile],
) -> Dict[str, List[Tuple[str, str, str]]]:
    cache_key = id(catalog)
    cached = _FACTION_INDEX_CACHE.get(cache_key)
    if cached is None:
        cached = _build_faction_index(catalog)
        _FACTION_INDEX_CACHE[cache_key] = cached
    return cached


def _best_match(
    unit_name: str,
    candidates: List[Tuple[str, str, str]],
    cutoff: float = 0.78,
) -> Optional[str]:
    """Return the best catalogue key for unit_name, or None below cutoff."""
    if not candidates:
        return None
    target_norm = _normalise(unit_name)
    if not target_norm:
        return None
    # Exact normalised match first — cheap and avoids difflib's slight noise.
    for key, _name, norm in candidates:
        if norm == target_norm:
            return key
    # difflib best ratio.
    best_key = None
    best_ratio = cutoff
    for key, _name, norm in candidates:
        ratio = difflib.SequenceMatcher(None, target_norm, norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_key = key
    return best_key


def match_units(
    list_record: ListRecord,
    catalog: Optional[Dict[str, UnitProfile]] = None,
) -> MatchResult:
    """Map every unit in ``list_record`` to a UNIT_CATALOG key (or unmatched)."""
    if catalog is None:
        catalog = UNIT_CATALOG
    index = _faction_index_for(catalog)
    scope_factions = _faction_scope(list_record.faction)
    candidates: List[Tuple[str, str, str]] = []
    for fac in scope_factions:
        candidates.extend(index.get(fac, []))

    result = MatchResult(list_record=list_record)
    for unit in list_record.units:
        key = _best_match(unit.name, candidates)
        if key is None:
            result.unmatched.append((unit.name, unit.points))
        else:
            result.matched_units.append((key, unit.model_count, unit.points))
    return result


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def score_list(
    match: MatchResult,
    fit: FitResult,
    features_df: pd.DataFrame,
    faction_multipliers: Dict[str, float],
    specs=None,
) -> Optional[ListScore]:
    """Score one list. Returns None if zero units matched (no signal)."""
    if not match.matched_units:
        return None

    # Build a key -> row index lookup once per scoring call.
    key_to_idx = {k: i for i, k in enumerate(features_df["key"].to_numpy())}

    # Predict prices for every catalogue unit once; pick out the rows we need.
    predicted = eqfit_predict(features_df, fit, specs)
    factions = features_df["faction"].to_numpy()

    predicted_total = 0.0
    gw_total = 0
    per_unit: List[Tuple[str, int, int, float]] = []
    for key, model_count, gw_points in match.matched_units:
        idx = key_to_idx.get(key)
        if idx is None:
            continue
        per_model = float(predicted[idx])
        mult = float(faction_multipliers.get(factions[idx], 1.0))
        per_model_adj = per_model * mult
        unit_predicted = per_model_adj * float(model_count)
        predicted_total += unit_predicted
        gw_total += gw_points
        per_unit.append((key, model_count, gw_points, per_model_adj))

    if gw_total <= 0:
        return None

    overrun_ratio = predicted_total / gw_total

    # Extrapolate matched-only totals to a full 2000-pt army so partial-
    # coverage lists are comparable to fully matched ones.
    cov = match.coverage_ratio
    full_predicted = predicted_total / cov if cov > 0 else predicted_total
    full_gw = match.total_points if match.total_points > 0 else 2000
    overrun_per_2000 = (full_predicted - full_gw) * (2000.0 / max(1, full_gw))

    return ListScore(
        match=match,
        predicted_total=predicted_total,
        gw_total=gw_total,
        overrun_ratio=overrun_ratio,
        overrun_per_2000=overrun_per_2000,
        per_unit=per_unit,
    )


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

def fit_winrate_model(
    scores: Iterable[ListScore],
    target: str = "winrate",
) -> Optional[WinrateFit]:
    """OLS fit of actual_winrate (or placement_percentile) against overrun_ratio."""
    xs: List[float] = []
    ys: List[float] = []
    for s in scores:
        if target == "winrate":
            y = s.actual_winrate
        elif target == "placement":
            y = s.placement_percentile
        else:
            raise ValueError(f"Unknown target {target!r}; expected 'winrate' or 'placement'.")
        if y is None:
            continue
        xs.append(s.overrun_ratio)
        ys.append(y)

    if len(xs) < 3:
        return None

    x_arr = np.array(xs, dtype=float)
    y_arr = np.array(ys, dtype=float)
    slope, intercept = np.polyfit(x_arr, y_arr, 1)
    y_pred = slope * x_arr + intercept
    ss_res = float(np.sum((y_arr - y_pred) ** 2))
    y_mean = float(np.mean(y_arr))
    ss_tot = float(np.sum((y_arr - y_mean) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return WinrateFit(intercept=float(intercept), slope=float(slope),
                      r_squared=float(r2), n=len(xs))


# ---------------------------------------------------------------------------
# Aggregation helpers used by the Streamlit view
# ---------------------------------------------------------------------------

def aggregate_unit_appearances(
    scores: Iterable[ListScore],
    features_df: pd.DataFrame,
) -> pd.DataFrame:
    """Roll up per-unit usage across the dataset for the treemap.

    Returns a DataFrame with one row per catalogue key actually fielded:
    key, name, faction, total_models, total_gw_points, appearances,
    gw_points_per_model, predicted_points_per_model, overrun_ratio.
    """
    name_lookup = dict(zip(features_df["key"], features_df["name"]))
    fac_lookup = dict(zip(features_df["key"], features_df["faction"]))
    gw_lookup = dict(zip(features_df["key"], features_df["gw_points_per_model"]))

    agg: Dict[str, Dict] = {}
    for score in scores:
        for key, models, gw_pts, predicted_per_model in score.per_unit:
            row = agg.setdefault(key, {
                "key": key,
                "name": name_lookup.get(key, key),
                "faction": fac_lookup.get(key, "Unknown"),
                "total_models": 0,
                "total_gw_points": 0,
                "appearances": 0,
                "predicted_points_per_model": predicted_per_model,
                "gw_points_per_model": float(gw_lookup.get(key, 0.0)),
            })
            row["total_models"] += models
            row["total_gw_points"] += gw_pts
            row["appearances"] += 1

    df = pd.DataFrame(agg.values())
    if df.empty:
        return df
    df["overrun_ratio"] = np.where(
        df["gw_points_per_model"] > 0,
        df["predicted_points_per_model"] / df["gw_points_per_model"],
        np.nan,
    )
    return df.sort_values("total_gw_points", ascending=False).reset_index(drop=True)


def aggregate_by_faction(
    scores: Iterable[ListScore],
) -> pd.DataFrame:
    """One row per faction with list count, mean overrun, mean actual winrate."""
    rows: Dict[str, Dict] = {}
    for s in scores:
        fac = s.match.list_record.faction
        row = rows.setdefault(fac, {
            "faction": fac,
            "lists": 0,
            "overrun_sum": 0.0,
            "winrate_sum": 0.0,
            "winrate_n": 0,
            "placement_sum": 0.0,
            "placement_n": 0,
        })
        row["lists"] += 1
        row["overrun_sum"] += s.overrun_ratio
        wr = s.actual_winrate
        if wr is not None:
            row["winrate_sum"] += wr
            row["winrate_n"] += 1
        pp = s.placement_percentile
        if pp is not None:
            row["placement_sum"] += pp
            row["placement_n"] += 1

    out = []
    for fac, r in rows.items():
        out.append({
            "faction": fac,
            "lists": r["lists"],
            "mean_overrun_ratio": r["overrun_sum"] / r["lists"],
            "mean_actual_winrate": (r["winrate_sum"] / r["winrate_n"]) if r["winrate_n"] else None,
            "winrate_n": r["winrate_n"],
            "mean_placement_percentile": (r["placement_sum"] / r["placement_n"]) if r["placement_n"] else None,
        })
    df = pd.DataFrame(out)
    if not df.empty:
        df = df.sort_values("lists", ascending=False).reset_index(drop=True)
    return df
