"""
3-profile mix weapon-picker sanity check.

Tests whether replacing the Marine-only expected-damage scorer with a
3-profile AVERAGE (chaff + elite-infantry + heavy-armour) — as a fallback for
units with no canonical loadout — correctly identifies:

  (A) The anti-tank weapon for a dedicated gunboat (Drukhari Ravager: Dark
      Lance vs Disintegrator Cannon).
  (B) The anti-elite/plasma weapon for a unit offering a plasma or high-AP
      option alongside a bolter-class option (e.g. Space Marine Devastator /
      Intercessors with plasma incinerator, or similar).
  (C) That a transport's incidental weapon stays the low-value pick and the
      transport does not get "over-armed" by the new scorer.

For each unit of interest we print per-weapon EV vs each target and which
weapon each scorer picks.  We also include the worst-bias cases flagged by
diag_antitank_pick so the fix can be checked against the original problem.

Usage:
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_mix_sanity
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code.bsdata.mapper import (
    WeaponStats,
    _gather_group_candidates,
    _is_crusade_only_entry,
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

# Reuse wound_probability and ev_vs_tank from the existing diagnostic.
from scripts.diag_antitank_pick import wound_probability, ev_vs_tank

# ---------------------------------------------------------------------------
# Three target profiles
# ---------------------------------------------------------------------------

# Profile 1 — chaff: Guardsman / Ork Boy
CHAFF_T = 3
CHAFF_SAVE = 5  # 5+ armour save

# Profile 2 — elite infantry: Terminator-class (ignore invulnerable saves for
# simplicity)
ELITE_T = 5
ELITE_SAVE = 2  # 2+ armour save (Terminators wear Tactical Dreadnought armour)

# Profile 3 — heavy armour: already implemented in diag_antitank_pick as
# Toughness 11 / 2+ save — reuse ev_vs_tank directly.

# EV-vs-Marine reproduced inline so this module is self-contained as well.


def _save_prob(save_target: int, ap: int) -> float:
    """Probability of making a save roll given the base save target and weapon AP.

    AP in 10e is a negative integer (e.g. -3 means AP -3).
    effective save = save_target - ap  (subtracting a negative raises the target).
    Clamped: saves cannot be better than 2+ (5/6 chance of succeeding) and cannot
    be forced to auto-fail here (min 1/6 is only if target > 6, giving 0.0).
    """
    effective = save_target - ap  # ap <= 0, so this raises the number
    if effective <= 2:
        return 5 / 6  # 2+ save: fail only on 1
    if effective >= 7:
        return 0.0    # impossible save
    return (7 - effective) / 6.0


def _apply_ability_boosts(base: float, w: WeaponStats) -> float:
    """Multiply in the same ability boosts used by expected_damage_through_baseline."""
    if w.lethal_hits:
        base *= 1.15
    if w.sustained_hits:
        base *= 1.0 + 0.17 * w.sustained_hits
    if w.twin_linked:
        base *= 1.30
    if w.devastating_wounds:
        base *= 1.10
    return base


def ev_vs_chaff(w: WeaponStats) -> float:
    """Expected damage per activation against chaff (Toughness 3 / 5+ save)."""
    if w.attacks <= 0 or w.hit_prob <= 0:
        return 0.0
    p_wound = wound_probability(w.strength, CHAFF_T)
    p_save = _save_prob(CHAFF_SAVE, w.ap)
    base = w.attacks * w.hit_prob * p_wound * (1.0 - p_save) * w.damage
    return _apply_ability_boosts(base, w)


def ev_vs_elite(w: WeaponStats) -> float:
    """Expected damage per activation against elite infantry (Toughness 5 / 2+ save)."""
    if w.attacks <= 0 or w.hit_prob <= 0:
        return 0.0
    p_wound = wound_probability(w.strength, ELITE_T)
    p_save = _save_prob(ELITE_SAVE, w.ap)
    base = w.attacks * w.hit_prob * p_wound * (1.0 - p_save) * w.damage
    return _apply_ability_boosts(base, w)


def ev_vs_marine(w: WeaponStats) -> float:
    """Expected damage per activation against a baseline Marine (Toughness 4 / 3+ save).

    Reproduces expected_damage_through_baseline() locally so we can compare it in
    the table without having to import the private BASELINE_SAVE constant."""
    return w.expected_damage_through_baseline()


def mix_average(w: WeaponStats) -> float:
    """3-profile flat-average mix: (chaff + elite + tank) / 3."""
    return (ev_vs_chaff(w) + ev_vs_elite(w) + ev_vs_tank(w)) / 3.0


def mix_max(w: WeaponStats) -> float:
    """3-profile maximum mix: max(chaff, elite, tank)."""
    return max(ev_vs_chaff(w), ev_vs_elite(w), ev_vs_tank(w))


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

COL_WEAPON = 34
COL_SCORE = 9

SCORE_LABELS = ["MrineEV", "ChaffEV", "EliteEV", " TankEV", "MixAvg", " MixMax"]


def _score_row(w: WeaponStats) -> Tuple[float, ...]:
    return (
        ev_vs_marine(w),
        ev_vs_chaff(w),
        ev_vs_elite(w),
        ev_vs_tank(w),
        mix_average(w),
        mix_max(w),
    )


def _pick_name(candidates: List[WeaponStats], key_fn) -> str:
    if not candidates:
        return "(none)"
    return max(candidates, key=key_fn).name


def print_group(
    unit_label: str,
    candidates: List[WeaponStats],
    note: str = "",
) -> None:
    """Print a formatted comparison table for one choice group and summarise picks."""
    if not candidates:
        print(f"  [SKIP] {unit_label}: no candidates found")
        return

    sep = "-" * (COL_WEAPON + 1 + COL_SCORE * len(SCORE_LABELS) + len(SCORE_LABELS) - 1)
    header = f"{'Weapon':<{COL_WEAPON}}" + "".join(f" {lbl:>{COL_SCORE}}" for lbl in SCORE_LABELS)

    print(f"\n{'='*len(sep)}")
    print(f"Unit: {unit_label}{('  [' + note + ']') if note else ''}")
    print(sep)
    print(header)
    print(sep)

    for w in candidates:
        scores = _score_row(w)
        row = f"{w.name:<{COL_WEAPON}}" + "".join(f" {s:>{COL_SCORE}.3f}" for s in scores)
        print(row)

    print(sep)

    # Per-scorer pick
    scorers = [
        ("Marine-EV", ev_vs_marine),
        ("MixAverage", mix_average),
        ("MixMax", mix_max),
    ]
    picks_line_parts = []
    for scorer_name, fn in scorers:
        best = max(candidates, key=fn)
        picks_line_parts.append(f"{scorer_name}={best.name!r}")
    print("PICKS: " + "   |   ".join(picks_line_parts))


# ---------------------------------------------------------------------------
# Unit finder — locate a named unit entry in the registry
# ---------------------------------------------------------------------------

def find_unit_choice_groups(
    reg: Registry,
    unit_name_fragment: str,
    faction: Optional[str] = None,
) -> List[Tuple[str, str, List[WeaponStats]]]:
    """Return (unit_name, faction, candidates) tuples for every choice group under
    units whose name contains unit_name_fragment (case-insensitive).  If faction
    is given, restricts to that faction."""
    results = []
    needle = unit_name_fragment.lower()
    for codex, entry in iter_unit_entries(reg):
        f = faction_of(codex)
        if faction and f != faction:
            continue
        name = entry.get("name") or ""
        if needle not in name.lower():
            continue

        def _walk(node, unit_name_resolved: str) -> None:
            for grp in node.findall("./selectionEntryGroups/selectionEntryGroup"):
                if _is_crusade_only_entry(grp):
                    continue
                cand_r, _ = _gather_group_candidates(grp, reg)
                if len(cand_r) >= 2:
                    results.append((unit_name_resolved, f, cand_r))
            for me in node.findall("./selectionEntries/selectionEntry"):
                if me.get("type") == "model":
                    _walk(me, unit_name_resolved)

        _walk(entry, name)

    return results


# ---------------------------------------------------------------------------
# Hard-coded spotlight cases
# ---------------------------------------------------------------------------

# These are units mentioned explicitly in the task brief.
# We handle them via find_unit_choice_groups to pick up the real BSData entries.

SPOTLIGHT_UNITS: List[Tuple[str, Optional[str], str]] = [
    # (name fragment, faction or None, role description)
    ("Ravager",          "Drukhari",             "GUNBOAT: dedicated anti-tank vehicle (Dark Lance vs Disintegrator)"),
    ("Raider",           "Drukhari",             "TRANSPORT: incidental weapon (expect low EV across the board)"),
    ("Devastator",       "Adeptus Astartes",     "ANTI-ELITE: plasma / heavy weapon vs bolter choice"),
    ("Hellblaster",      "Adeptus Astartes",     "ANTI-ELITE: plasma incinerator specialist"),
    ("Leman Russ",       "Astra Militarum",      "GUNBOAT: main battle tank with battle cannon choice"),
    ("Punisher",         "Astra Militarum",      "ANTI-HORDE: Punisher Gatling Cannon vs battle cannon"),
    ("Predator",         "Adeptus Astartes",     "GUNBOAT: Predator Annihilator autocannon vs lascannon"),
    ("Hammerhead",       "T'au Empire",           "GUNBOAT: Railgun vs Ion Cannon"),
    ("Crisis",           "T'au Empire",           "ANTI-ELITE/TANK: burst cannon vs plasma rifle vs missile pod"),
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading registry…")
    reg = load_registry()
    print("Registry loaded.\n")

    print("=" * 80)
    print("SECTION 1 — Spotlight units (gunboats, transports, anti-elite platforms)")
    print("=" * 80)

    seen_labels: set = set()

    for name_frag, faction, role in SPOTLIGHT_UNITS:
        groups = find_unit_choice_groups(reg, name_frag, faction)
        if not groups:
            print(f"\n[MISSING] '{name_frag}' (faction={faction}) — no choice groups found in registry")
            continue
        # De-duplicate by first-weapon-name set to avoid printing the same group twice
        # when multiple model entries share the same weapons.
        printed_fingerprints: set = set()
        for unit_name, f, candidates in groups:
            fp = frozenset(w.name for w in candidates)
            if fp in printed_fingerprints:
                continue
            printed_fingerprints.add(fp)
            label = f"[{f}] {unit_name}"
            print_group(label, candidates, note=role)

    # ---------------------------------------------------------------------------
    # Section 2: Worst-bias cases from diag_antitank_pick (anti-tank EV lost).
    # We re-derive them here so we can show all 6 scores side-by-side.
    # ---------------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("SECTION 2 — Worst anti-tank bias cases (from diag_antitank_pick factions)")
    print("These are the cases the fix is supposed to CORRECT.")
    print("=" * 80)

    BIAS_FACTIONS = {
        "Astra Militarum",
        "Adeptus Mechanicus",
        "Imperial Knights",
        "World Eaters",
        "Aeldari",
        "Drukhari",
        "Adeptus Astartes",
    }

    # Collect all choice groups from bias factions with anti-tank bias.
    BiasRow = Tuple[str, str, List[WeaponStats], float, str, str]
    bias_rows: List[BiasRow] = []

    for codex, entry in iter_unit_entries(reg):
        f = faction_of(codex)
        if f not in BIAS_FACTIONS:
            continue
        unit_name = entry.get("name") or "?"

        def _walk_bias(node) -> None:
            for grp in node.findall("./selectionEntryGroups/selectionEntryGroup"):
                if _is_crusade_only_entry(grp):
                    continue
                cand_r, _ = _gather_group_candidates(grp, reg)
                if len(cand_r) < 2:
                    continue
                picked = max(cand_r, key=ev_vs_marine)
                dropped_candidates = [w for w in cand_r if w is not picked]
                if not dropped_candidates:
                    continue
                best_dropped = max(dropped_candidates, key=ev_vs_tank)
                gap = ev_vs_tank(best_dropped) - ev_vs_tank(picked)
                if gap > 0.1:
                    bias_rows.append((unit_name, f, cand_r, gap, picked.name, best_dropped.name))
            for me in node.findall("./selectionEntries/selectionEntry"):
                if me.get("type") == "model":
                    _walk_bias(me)

        _walk_bias(entry)

    # Sort by gap descending, keep top 10.
    bias_rows.sort(key=lambda r: -r[3])
    shown = 0
    printed_fps: set = set()

    for unit_name, f, candidates, gap, picked_name, dropped_name in bias_rows:
        if shown >= 10:
            break
        fp = frozenset(w.name for w in candidates)
        if fp in printed_fps:
            continue
        printed_fps.add(fp)
        note = f"Marine picks {picked_name!r}; anti-tank winner is {dropped_name!r}; gap={gap:.3f}"
        print_group(f"[{f}] {unit_name}", candidates, note=note)
        shown += 1

    # ---------------------------------------------------------------------------
    # Section 3: Overall verdict summary
    # ---------------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("SECTION 3 — Aggregate verdict across ALL bias cases")
    print("=" * 80)

    # Count how often each scorer agrees with ev_vs_tank's top pick.
    total = 0
    marine_agree = 0
    avg_agree = 0
    mx_agree = 0
    avg_better_than_marine = 0
    mx_better_than_marine = 0

    for codex, entry in iter_unit_entries(reg):
        f = faction_of(codex)
        if f not in BIAS_FACTIONS:
            continue

        def _tally(node) -> None:
            nonlocal total, marine_agree, avg_agree, mx_agree
            nonlocal avg_better_than_marine, mx_better_than_marine
            for grp in node.findall("./selectionEntryGroups/selectionEntryGroup"):
                if _is_crusade_only_entry(grp):
                    continue
                cand_r, _ = _gather_group_candidates(grp, reg)
                if len(cand_r) < 2:
                    continue
                # Only consider groups where the anti-tank winner differs from Marine.
                tank_best = max(cand_r, key=ev_vs_tank)
                marine_best = max(cand_r, key=ev_vs_marine)
                if tank_best is marine_best:
                    # No disagreement — skip from totals
                    continue
                total += 1
                avg_best = max(cand_r, key=mix_average)
                mx_best = max(cand_r, key=mix_max)
                if marine_best is tank_best:
                    marine_agree += 1
                if avg_best is tank_best:
                    avg_agree += 1
                if mx_best is tank_best:
                    mx_agree += 1
                # Also track improvement: each scorer vs Marine pick on tank EV.
                marine_tank_ev = ev_vs_tank(marine_best)
                avg_tank_ev = ev_vs_tank(avg_best)
                mx_tank_ev = ev_vs_tank(mx_best)
                if avg_tank_ev > marine_tank_ev:
                    avg_better_than_marine += 1
                if mx_tank_ev > marine_tank_ev:
                    mx_better_than_marine += 1
            for me in node.findall("./selectionEntries/selectionEntry"):
                if me.get("type") == "model":
                    _tally(me)

        _tally(entry)

    if total == 0:
        print("No disagreeing choice groups found — nothing to tally.")
    else:
        print(f"Total choice groups where anti-tank best != Marine best: {total}")
        print(f"  Marine    agrees with anti-tank winner: {marine_agree}/{total} = {100*marine_agree/total:.1f}%  (baseline: 0% by construction)")
        print(f"  MixAverage agrees with anti-tank winner: {avg_agree}/{total} = {100*avg_agree/total:.1f}%")
        print(f"  MixMax     agrees with anti-tank winner: {mx_agree}/{total} = {100*mx_agree/total:.1f}%")
        print()
        print(f"Groups where each scorer's pick is better (higher tank EV) than Marine's pick:")
        print(f"  MixAverage better than Marine: {avg_better_than_marine}/{total} = {100*avg_better_than_marine/total:.1f}%")
        print(f"  MixMax     better than Marine: {mx_better_than_marine}/{total} = {100*mx_better_than_marine/total:.1f}%")

    print()
    print("Legend:")
    print("  MrineEV = EV vs Toughness 4 / 3+ save Marine (current mapper scorer)")
    print("  ChaffEV = EV vs Toughness 3 / 5+ save (Guardsman / Ork Boy)")
    print("  EliteEV = EV vs Toughness 5 / 2+ save (Terminator-class; no invuln)")
    print("   TankEV = EV vs Toughness 11 / 2+ save (heavy vehicle)")
    print("   MixAvg = flat average of ChaffEV + EliteEV + TankEV")
    print("   MixMax = max of ChaffEV, EliteEV, TankEV")


if __name__ == "__main__":
    main()
