"""
Anti-tank weapon-picker bias diagnostic.

The BSData mapper picks ONE weapon per choice group using
expected_damage_through_baseline(), which scores damage against a baseline
Marine (Toughness 4-ish, 3+ save, no wound roll). Multi-shot
anti-infantry options outscore single-shot anti-tank options whose high
Strength / Armour Penetration / Damage is wasted on a Marine. This causes
durable shooty vehicles to fire weaker weapons in the sim than they would
on the table.

This script walks the same choice groups the mapper walks, replays both
the EV-vs-Marine score and a new EV-vs-heavy-tank score for every
candidate, and measures how much anti-tank output the picker leaves on
the table.

Factions analysed:
  Under-shooters (expected victims of the bias):
    Astra Militarum, Adeptus Mechanicus
  Comparison set (to confirm the bias is systemic — opponents are also
  under-armed against heavy targets, so Knights are under-threatened):
    Imperial Knights, World Eaters, Aeldari, Drukhari, Adeptus Astartes

Usage:
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_antitank_pick
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Ensure the project root is on the path when called as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code.bsdata.mapper import (
    WeaponStats,
    _gather_group_candidates,
    _is_crusade_only_entry,
    _resolve_weapon_target,
    _weapons_from_inline_entry,
    extract_ranged_weapon,
    extract_melee_weapon,
    extract_unit_stat_line,
    is_unit_profile,
    map_unit,
)
from code.bsdata.parser import (
    Registry,
    iter_unit_entries,
    load_registry,
    profile_characteristics,
)
from code.factions import faction_of

# ---------------------------------------------------------------------------
# Target factions
# ---------------------------------------------------------------------------

UNDER_SHOOTER_FACTIONS = {"Astra Militarum", "Adeptus Mechanicus"}
COMPARISON_FACTIONS = {
    "Imperial Knights",
    "World Eaters",
    "Aeldari",
    "Drukhari",
    "Adeptus Astartes",
}
ALL_TARGET_FACTIONS = UNDER_SHOOTER_FACTIONS | COMPARISON_FACTIONS

# ---------------------------------------------------------------------------
# Heavy tank target parameters
# The representative heavy vehicle: Toughness 11, Save 2+, many wounds.
# This covers Predator Annihilator (T11), Land Raiders (T12), Rogal Dorn
# (T12), Imperial Knights (T10+), etc.
# ---------------------------------------------------------------------------

TANK_TOUGHNESS = 11
TANK_SAVE = 2      # 2+ save before armour penetration modifier
TANK_WOUNDS = 16   # not used in EV calc, but representative


def wound_probability(strength: int, toughness: int) -> float:
    """Probability of wounding given Strength vs Toughness.

    10th Edition wound table:
      S >= 2*T  -> wounds on 2+  (5/6)
      S >  T    -> wounds on 3+  (4/6)
      S == T    -> wounds on 4+  (3/6)
      S <  T    -> wounds on 5+  (2/6)
      S*2 <= T  -> wounds on 6+  (1/6)

    (The "S >= 2*T" check is evaluated first, then "S*2 <= T" last.)
    """
    if strength <= 0:
        return 1 / 6
    if strength >= 2 * toughness:
        return 5 / 6
    if strength > toughness:
        return 4 / 6
    if strength == toughness:
        return 3 / 6
    if 2 * strength <= toughness:
        return 1 / 6
    return 2 / 6  # S < T (and not S*2 <= T)


def ev_vs_tank(w: WeaponStats) -> float:
    """Expected damage per activation against the heavy tank target.

    Unlike expected_damage_through_baseline, this includes:
      - the wound roll (Strength vs Toughness 11)
      - the save roll after armour penetration (2+ save modified by AP)
    The hit probability and damage are taken directly from WeaponStats.
    """
    if w.attacks <= 0 or w.hit_prob <= 0:
        return 0.0
    p_wound = wound_probability(w.strength, TANK_TOUGHNESS)
    # Save roll: TANK_SAVE minus the weapon's AP (AP is negative in 10e
    # BSData, so subtracting a negative raises the save target).
    # effective_save = TANK_SAVE - ap  (e.g. AP=-3 -> effective 2-(-3)=5 -> 5+)
    effective_save_target = TANK_SAVE - w.ap
    # Clamp: save cannot be better than 2+ (auto-fail on 1 always, so max
    # probability = 5/6) or worse than 6+ (always fails on 1, prob=1/6).
    if effective_save_target <= 2:
        p_save = 5 / 6  # 2+ save
    elif effective_save_target >= 7:
        p_save = 0.0    # save auto-fails
    else:
        p_save = (7 - effective_save_target) / 6.0
    p_unsaved = 1.0 - p_save
    base = w.attacks * w.hit_prob * p_wound * p_unsaved * w.damage
    # Apply the same ability boosts as expected_damage_through_baseline for
    # fair comparison, since the mapper uses them in the pick decision.
    if w.lethal_hits:
        base *= 1.15
    if w.sustained_hits:
        base *= 1.0 + 0.17 * w.sustained_hits
    if w.twin_linked:
        base *= 1.30
    if w.devastating_wounds:
        base *= 1.10
    return base


# ---------------------------------------------------------------------------
# Walk choice groups for a single unit entry
#
# We replicate _collect_weapons_for_model's selectionEntryGroup loop because
# that's the code path the mapper uses to pick within each group. The outer
# gather_wargear / _walk path also sees choice groups but ultimately resolves
# them the same way via the same _gather_group_candidates primitive.
#
# For each group, we:
#   1. Collect all ranged candidates (same as the mapper does).
#   2. Identify the mapper's pick: max by EV-vs-Marine.
#   3. Identify the best anti-tank alternative: highest EV-vs-tank among the
#      candidates NOT picked, OR the highest-Strength candidate overall.
#   4. Record the gap (dropped EV-vs-tank minus picked EV-vs-tank) when the
#      gap is positive (i.e. the mapper left a better anti-tank option behind).
# ---------------------------------------------------------------------------

def is_antitank(w: WeaponStats) -> bool:
    """A weapon is anti-tank if Strength >= 9 (wounds T10+ on 4+, T8 on 3+)."""
    return w.strength >= 9


ChoiceGroupResult = Tuple[
    str,       # unit name
    str,       # faction
    str,       # picked weapon name
    float,     # picked EV-vs-Marine
    float,     # picked EV-vs-tank
    str,       # dropped weapon name
    float,     # dropped EV-vs-Marine
    float,     # dropped EV-vs-tank
    float,     # gap = dropped_ev_tank - picked_ev_tank (positive = bias)
]


def analyse_unit_entry(
    codex: str,
    entry,
    reg: Registry,
    faction: str,
) -> List[ChoiceGroupResult]:
    """Return one ChoiceGroupResult per choice group that exhibits the bias."""
    unit_name = entry.get("name") or "?"
    results: List[ChoiceGroupResult] = []

    # Walk selectionEntryGroups directly on the unit entry (single-model path)
    # AND on any inner model entries (multi-model path).
    def _check_groups_on(node) -> None:
        for grp in node.findall("./selectionEntryGroups/selectionEntryGroup"):
            if _is_crusade_only_entry(grp):
                continue
            candidates_ranged, _ = _gather_group_candidates(grp, reg)
            if len(candidates_ranged) < 2:
                # Only one candidate — no choice, no bias possible.
                continue
            # Mapper's pick: highest EV-vs-Marine
            picked = max(
                candidates_ranged,
                key=lambda w: w.expected_damage_through_baseline(),
            )
            # Best candidate by EV-vs-tank (may equal picked)
            best_by_tank = max(candidates_ranged, key=ev_vs_tank)
            # Also find the highest-Strength candidate for the "anti-tank"
            # definition (separate from the EV-vs-tank winner).
            best_by_strength = max(candidates_ranged, key=lambda w: w.strength)

            # We care about cases where the dropped weapon is BETTER for tanks.
            # Evaluate against both the best-by-tank and best-by-strength
            # candidates, taking the one that maximises the anti-tank gap.
            dropped_candidates = [
                w for w in candidates_ranged
                if w is not picked
            ]
            if not dropped_candidates:
                continue
            # Among dropped candidates, pick the one with highest EV-vs-tank.
            best_dropped = max(dropped_candidates, key=ev_vs_tank)
            gap = ev_vs_tank(best_dropped) - ev_vs_tank(picked)
            if gap <= 0.0:
                # Picked weapon is already at least as good vs tanks.
                continue
            # Also require that the dropped weapon is higher-Strength than
            # picked (confirming it's genuinely anti-tank-flavoured), OR that
            # the gap is substantial (> 0.05 per activation).
            if best_dropped.strength <= picked.strength and gap < 0.05:
                continue
            results.append((
                unit_name,
                faction,
                picked.name,
                picked.expected_damage_through_baseline(),
                ev_vs_tank(picked),
                best_dropped.name,
                best_dropped.expected_damage_through_baseline(),
                ev_vs_tank(best_dropped),
                gap,
            ))

        # Recurse into inner model entries.
        for me in node.findall(
            "./selectionEntries/selectionEntry"
        ):
            if me.get("type") == "model":
                _check_groups_on(me)

    _check_groups_on(entry)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading registry…")
    reg = load_registry()
    print("Registry loaded. Walking unit entries…\n")

    # Collect all results by faction.
    faction_results: Dict[str, List[ChoiceGroupResult]] = defaultdict(list)
    total_entries = 0

    for codex, entry in iter_unit_entries(reg):
        faction = faction_of(codex)
        if faction not in ALL_TARGET_FACTIONS:
            continue
        total_entries += 1
        rows = analyse_unit_entry(codex, entry, reg, faction)
        faction_results[faction].extend(rows)

    print(f"Scanned {total_entries} unit entries across {len(ALL_TARGET_FACTIONS)} factions.\n")

    # ---------------------------------------------------------------------------
    # Table 1: Per-faction summary
    # ---------------------------------------------------------------------------
    print("=" * 78)
    print("TABLE 1 — Per-faction anti-tank output left on the table")
    print("  'choice groups biased' = groups where mapper picked a weaker anti-tank option")
    print("  'total EV-vs-tank lost' = sum of (dropped EV-vs-tank - picked EV-vs-tank) over")
    print("  all such groups; larger = more anti-tank output suppressed by the picker")
    print("=" * 78)

    faction_order = sorted(
        ALL_TARGET_FACTIONS,
        key=lambda f: -sum(r[8] for r in faction_results.get(f, []))
    )

    header = f"{'Faction':<26} {'Biased groups':>14} {'Total EV lost':>14} {'Units affected':>15}"
    print(header)
    print("-" * len(header))
    for faction in faction_order:
        rows = faction_results.get(faction, [])
        n_groups = len(rows)
        total_ev_lost = sum(r[8] for r in rows)
        units_affected = len({r[0] for r in rows})
        marker = " <<< UNDER-SHOOTER" if faction in UNDER_SHOOTER_FACTIONS else ""
        print(
            f"{faction:<26} {n_groups:>14} {total_ev_lost:>14.2f} {units_affected:>15}{marker}"
        )
    print()

    # ---------------------------------------------------------------------------
    # Table 2: Worst individual cases (top 10 by gap size)
    # ---------------------------------------------------------------------------
    all_rows: List[ChoiceGroupResult] = []
    for rows in faction_results.values():
        all_rows.extend(rows)
    all_rows.sort(key=lambda r: -r[8])  # descending by gap

    print("=" * 78)
    print("TABLE 2 — Top 10 worst individual cases (largest anti-tank EV loss per group)")
    print("  EV = expected damage per activation;  'Marine EV' = what the picker optimises")
    print("  'Tank EV' = expected damage vs Toughness 11 / 2+ save heavy vehicle")
    print("=" * 78)

    col1 = 28  # unit name
    col2 = 26  # weapon name
    col3 = 9   # marine ev
    col4 = 9   # tank ev
    col5 = 8   # gap

    hdr = (
        f"{'Unit':<{col1}} {'Weapon':<{col2}} "
        f"{'MrEV':>{col3}} {'TkEV':>{col4}} "
        f"{'Gap':>{col5}}"
    )
    print(hdr)
    print("-" * len(hdr))

    shown = 0
    for r in all_rows:
        if shown >= 10:
            break
        unit_name, faction, picked_name, picked_mr, picked_tk, dropped_name, dropped_mr, dropped_tk, gap = r
        # First line: picked weapon
        print(
            f"{'[' + faction + '] ' + unit_name:<{col1}} "
            f"{'PICKED: ' + picked_name:<{col2}} "
            f"{picked_mr:>{col3}.2f} {picked_tk:>{col4}.2f} {'':>{col5}}"
        )
        # Second line: dropped (better anti-tank) weapon
        blank = " " * col1
        print(
            f"{blank} "
            f"{'DROPPED: ' + dropped_name:<{col2}} "
            f"{dropped_mr:>{col3}.2f} {dropped_tk:>{col4}.2f} {gap:>{col5}.2f}"
        )
        shown += 1
        if shown < 10 and shown < len(all_rows):
            print()

    print()
    print(
        "Note: EV-vs-Marine uses expected_damage_through_baseline() (no wound roll, 3+ save).")
    print(
        "      EV-vs-Tank uses Strength vs Toughness 11 wound table + 2+ save - armour penetration modifier."
    )


if __name__ == "__main__":
    main()
