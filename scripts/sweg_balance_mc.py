"""
SwegHammer task #131 — C1 Full catalogue sweep retry (Phase 5 replacement).

Phase 5 equilibrium prices regressed eval-vs-meta MAE from 4.55 to 8.32 because
the army builder picks fixed compositions — making units cheaper just buys more
bodies without strategic improvement, so equilibrium maths doesn't map onto sim
win-rate.

This pass uses a different signal: per-faction Monte Carlo win-rate residuals
from the eval-vs-meta script. The four factions with the largest residuals get
their 2-3 most-points-spent tournament-staple units shifted toward the target
direction:

  * Over-strong factions  (sim wr > tournament wr) -> raise unit cost +10%
  * Under-strong factions (sim wr < tournament wr) -> lower unit cost -10%

The shift is capped at 25% per pass so a single bad signal can't blow up a
unit's cost. The Intercessor anchor (the global SwegHammer points reference)
is never touched.

Updates are written to ``data/overrides.json`` as ``points_override`` entries
which feed UnitProfile.points_cost (per-model) via the loader.

Usage:
    python -m scripts.sweg_balance_mc
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from code.units import UNIT_CATALOG

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = REPO_ROOT / "data" / "overrides.json"

# Hard cap on per-pass shift, defends against runaway iterations.
MAX_SHIFT_FRACTION = 0.25
PASS_SHIFT_FRACTION = 0.10

# Global anchor — never modify this unit's points (CLAUDE.md baseline rule).
ANCHOR_UNIT_KEY = "space_marines_intercessor_squad"

# Per-faction targets. Each entry: (direction, [unit_keys]).
# direction = "up" means over-strong (raise cost); "down" means under-strong
# (lower cost). The unit_keys are the 2-3 highest-points-share tournament
# staples per faction, sourced from May 2026 meta lists (Wahapedia / GW
# datasheets) and confirmed present in the SwegHammer catalogue.
FACTION_ADJUSTMENTS: Dict[str, Tuple[str, List[str]]] = {
    # Over-strong on GW-anchored eval (sim WR > real WR): raise per-model cost.
    # NB: never include the Intercessor anchor — gated by the AnchorPreservedTests.
    "Adeptus Astartes": ("up", [
        "space_marines_hellblaster_squad",
        "space_marines_repulsor",
        "space_marines_bladeguard_veteran_squad",
    ]),
    "Death Guard": ("up", [
        "death_guard_plague_marines",
        "death_guard_plagueburst_crawler",
        "death_guard_deathshroud_terminators",
    ]),
    "Adeptus Custodes": ("up", [
        "adeptus_custodes_custodian_guard",
        "adeptus_custodes_caladius_grav_tank",
        "adeptus_custodes_allarus_custodians",
    ]),
    "Aeldari": ("up", [
        "aeldari_craftworlds_wraithguard",
        "aeldari_craftworlds_falcon",
    ]),
    # Under-strong on GW-anchored eval (sim WR < real WR): lower per-model cost.
    # T'au flipped direction post-points-fix: under Lanchester they were over-
    # strong, under GW they're severely under-priced for their performance.
    "T'au Empire": ("down", [
        "t_au_empire_crisis_sunforge_battlesuits",
        "t_au_empire_crisis_fireknife_battlesuits",
        "t_au_empire_riptide_battlesuit",
    ]),
    "Thousand Sons": ("down", [
        "thousand_sons_rubric_marines",
        "thousand_sons_scarab_occult_terminators",
    ]),
    "Leagues of Votann": ("down", [
        "leagues_of_votann_hearthkyn_warriors",
        "leagues_of_votann_sagitaur",
        "leagues_of_votann_hekaton_land_fortress",
    ]),
    # Necrons removed — now ~equilibrium (+3.5pt off, within sample noise).
}


def compute_shift(current: float, direction: str,
                  shift: float = PASS_SHIFT_FRACTION) -> float:
    """Return new points-per-model after applying a single-pass shift.

    direction='up'   -> current * (1 + shift)
    direction='down' -> current * (1 - shift)

    Cap is enforced by the caller against the starting catalogue value.
    """
    if direction == "up":
        return current * (1.0 + shift)
    if direction == "down":
        return current * (1.0 - shift)
    raise ValueError(f"unknown direction: {direction!r}")


def clamp_against_anchor(starting: float, proposed: float,
                         max_shift: float = MAX_SHIFT_FRACTION) -> float:
    """Clamp the proposed cost to be within ``max_shift`` of ``starting``."""
    lo = starting * (1.0 - max_shift)
    hi = starting * (1.0 + max_shift)
    return max(lo, min(hi, proposed))


def load_overrides() -> dict:
    """Return the parsed overrides JSON (full document, not just 'units')."""
    if not OVERRIDES_PATH.exists():
        return {"units": {}}
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def write_overrides(doc: dict) -> None:
    OVERRIDES_PATH.write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8",
    )


def build_updates() -> List[Dict[str, object]]:
    """Compute the per-unit points_override updates for this pass.

    Returns a list of dicts (one per targeted unit) with the fields:
      faction, key, direction, starting_points, proposed_points,
      capped_points, applied_points.

    A unit missing from the catalogue is silently skipped (logged in caller).
    """
    updates: List[Dict[str, object]] = []
    for faction, (direction, keys) in FACTION_ADJUSTMENTS.items():
        for key in keys:
            if key == ANCHOR_UNIT_KEY:
                # Defensive: never adjust the anchor even if mis-listed.
                continue
            profile = UNIT_CATALOG.get(key)
            if profile is None:
                updates.append({
                    "faction": faction, "key": key, "direction": direction,
                    "starting_points": None, "proposed_points": None,
                    "capped_points": None, "applied_points": None,
                    "skipped": True,
                })
                continue
            starting = float(profile.points_cost)
            proposed = compute_shift(starting, direction)
            capped = clamp_against_anchor(starting, proposed)
            updates.append({
                "faction": faction, "key": key, "direction": direction,
                "starting_points": round(starting, 2),
                "proposed_points": round(proposed, 2),
                "capped_points": round(capped, 2),
                "applied_points": round(capped, 2),
                "skipped": False,
            })
    return updates


def apply_updates_to_overrides(updates: List[Dict[str, object]]) -> dict:
    """Merge update entries into overrides.json's ``units`` map.

    The anchor unit is never modified. Updates set the ``points_override``
    field, preserving any other override fields already present.
    """
    doc = load_overrides()
    units = doc.setdefault("units", {})
    for upd in updates:
        if upd.get("skipped"):
            continue
        key = upd["key"]
        if key == ANCHOR_UNIT_KEY:
            continue
        entry = units.setdefault(key, {})
        entry["points_override"] = float(upd["applied_points"])
        note = entry.get("notes", "")
        tag = (
            f"sweg_balance_mc {upd['direction']} {upd['starting_points']} -> "
            f"{upd['applied_points']} pts/model"
        )
        if "sweg_balance_mc" not in note:
            entry["notes"] = (note + " | " if note else "") + tag
        else:
            # Update the existing tag in-place (single line)
            entry["notes"] = " | ".join(
                p for p in note.split(" | ") if "sweg_balance_mc" not in p
            )
            entry["notes"] = (entry["notes"] + " | " if entry["notes"] else "") + tag
    return doc


def main() -> None:
    updates = build_updates()
    print(f"sweg_balance_mc — {len(updates)} target unit(s) across "
          f"{len(FACTION_ADJUSTMENTS)} factions\n")
    print(f"{'Faction':18s}  {'Direction':9s}  {'Unit':56s}  "
          f"{'Start':>6s}  {'Applied':>7s}")
    print("-" * 110)
    for upd in updates:
        if upd.get("skipped"):
            print(f"{upd['faction']:18s}  {upd['direction']:9s}  "
                  f"{upd['key']:56s}  MISSING-FROM-CATALOG")
            continue
        print(f"{upd['faction']:18s}  {upd['direction']:9s}  "
              f"{upd['key']:56s}  "
              f"{upd['starting_points']:>6.2f}  {upd['applied_points']:>7.2f}")
    doc = apply_updates_to_overrides(updates)
    write_overrides(doc)
    print(f"\nWrote {OVERRIDES_PATH}")


if __name__ == "__main__":
    main()
