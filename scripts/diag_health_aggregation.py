"""Per-squad vs per-model health aggregation audit (GitHub issue 61).

SwegHammer fields one `Unit` per physical model (`army.py:_add_squad_per_model`,
the documented "Level of Control" design — see the ground-truth correction in
`docs/DECISION_LEDGER.md`, 2026-06-21). Each per-model `Unit` reads its wounds
from `UnitProfile.health`, which is a SINGLE aggregate value shared by every
model in the squad (`code/units.py:_loadout_entry_to_weapon_fields` only
overrides WEAPON fields per model slot — health/toughness/save/oc/leadership
are never varied per slot). Issue 61 asks whether BSData's parsed `health`
field is ever a SQUAD TOTAL (or otherwise mis-scoped) rather than a genuine
per-model value, which would silently multiply a unit's fielded durability.

This script audits `data/bsdata/parsed.json` for the concrete mechanism found
during the investigation, rather than guessing at thresholds:

CLASS A — "single-model unit miscounted as an N-model squad"
    `code/bsdata/mapper.py:extract_squad_size` sums every
    `selectionEntryGroup` with a `selections` min/max constraint under a unit
    entry, on the assumption that each such group is a squad-composition
    slot (correct for e.g. Devastator body (4,9) + Sergeant (1,1) -> (5,10)).
    That assumption breaks for a genuinely SINGLE-MODEL unit whose wargear is
    offered as two or more independent MANDATORY choice groups (e.g. "pick a
    ranged weapon" + "pick a melee weapon", each shaped identically to a
    model-count group in the XML) -- the groups get summed as if they were
    bodies, inflating `min_models`/`max_models` for a unit that is really one
    model. Every model in the resulting "squad" then gets the full aggregate
    `health` (and the unit's total cost is divided by the phantom model
    count for `points_per_model`), so the sim fields N copies of a full-hp
    model for the points of one.

    Detectable independently of `extract_squad_size` itself: the mapper's
    per-model LOADOUT walk (`_build_model_loadouts` / `gather_squad_loadout`)
    counts real weapon-bearing model slots by a different path. When that
    walk finds only ONE real model's worth of gear (`model_loadouts` has a
    single entry with `count == 1.0`) while `max_models > 1`, the two signals
    disagree and the squad-size side is almost always the bug. Confirmed by
    hand against the raw BSData XML and Wahapedia for every unit in the
    CLASS_A_CONFIRMED table below (see the module docstring in each override
    for the specific weapon-choice-group shape) — this is the SAME defect
    class already fixed for `imperial_knights_library_canis_rex` via
    `SWEG_IK_CANIS_SINGLE` in `code/bsdata/loader.py` (there BSData folds a
    second named model into the loadout instead of summing weapon-choice
    groups, but the downstream effect — shared `health` across a phantom
    multi-model unit — is identical).

CLASS B — "heterogeneous multi-model combo unit" (INFORMATIONAL ONLY)
    Character-plus-retinue datasheets (Ghazghkull Thraka + Makari, Marneus
    Calgar + Victrix Honour Guard, Fabius Bile + Surgeon Acolyte, ...) DO
    carry a correct `min_models`/`max_models` and a `model_loadouts` list
    whose per-entry counts correctly sum to it. But every model still
    inherits the SAME `health` (the one profile `_consume_profile` picked as
    `unit_profile`, usually the named lead) because health is never varied
    per loadout slot. When the retinue's real wounds differ from the lead's,
    this broadcasts the lead's (usually higher) durability onto the weaker
    escort models. Class B is flagged for visibility only: fixing it needs a
    per-unit rules read (is the escort really present from deployment, or a
    special-case replacement model like Sir Hekhtur?) and a code change to
    carry health per loadout slot, not a `data/overrides.json` field edit —
    out of scope for this pass. Do not auto-remediate Class B here.

Run (static analysis only, no simulation, no evaluate_vs_meta):
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_health_aggregation
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_health_aggregation --class b
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
PARSED_PATH = REPO_ROOT / "data" / "bsdata" / "parsed.json"

# Units confirmed (raw BSData XML read + Wahapedia unit-composition /
# Wounds cross-check, see the audit report) as CLASS A: real unit
# composition is "1 model" per Wahapedia, but `extract_squad_size` summed
# independent mandatory wargear-choice groups into a phantom body count.
# Wahapedia URLs are the citation required by CLAUDE.md rule 10.
CLASS_A_CONFIRMED: Dict[str, Dict[str, Any]] = {
    "death_guard_great_unclean_one": {
        "wahapedia": "https://wahapedia.ru/wh40k10ed/factions/death-guard/Great-Unclean-One",
        "real_models": 1,
        "real_wounds": 20,
        "mechanism": (
            "Two independent mandatory weapon-choice selectionEntryGroups "
            "('Flail / Bileblade', 'Bilesword / Bell') each read as a "
            "(1,1) model-count group and get summed -> (2,2)."
        ),
        "note": (
            "Sibling entry chaos_daemons_library_great_unclean_one (same "
            "unit via the shared Chaos Daemons Library catalogue) parses "
            "correctly as (1,1) -- proof the BUG is in this codex's local "
            "XML shape, not the unit itself. Reachable by "
            "code/army_builder.py:_random_fill for any Death Guard army "
            "(profile.faction == 'Death Guard' matches the fill-pool "
            "filter) -- Death Guard is the standing #1 gated over-pole."
        ),
    },
    "space_wolves_wulfen_dreadnought": {
        "wahapedia": "https://wahapedia.ru/wh40k10ed/factions/space-marines/Wulfen-Dreadnought-1",
        "real_models": 1,
        "real_wounds": 8,
        "mechanism": (
            "Single 'Wargear' selectionEntryGroup with min=2,max=2 "
            "(pick 2 of the two weapon-arm loadout options) reads as a "
            "(2,2) model-count group."
        ),
        "note": "Mainline Space Wolves unit (not Legends).",
    },
    "chaos_space_marines_decimator_legends": {
        "wahapedia": "https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/Decimator",
        "real_models": 1,
        "real_wounds": 12,
        "mechanism": "Same weapon-choice-group-summing shape as the Wulfen Dreadnought.",
        "note": "Legends -- excluded from matched play, near-zero fielded frequency.",
    },
    "aeldari_craftworlds_hornet_legends": {
        "wahapedia": "https://wahapedia.ru/wh40k10ed/factions/aeldari/Hornet",
        "real_models": 1,
        "real_wounds": 8,
        "mechanism": "Same weapon-choice-group-summing shape.",
        "note": "Legends -- excluded from matched play, near-zero fielded frequency.",
    },
    "t_au_empire_longstrike_legends": {
        "wahapedia": "https://wahapedia.ru/wh40k10ed/factions/t-au-empire/Longstrike",
        "real_models": 1,
        "real_wounds": 14,
        "mechanism": "Same weapon-choice-group-summing shape.",
        "note": "Legends -- excluded from matched play, near-zero fielded frequency.",
    },
}

# Additional CLASS A hits found by the scan but not yet spot-verified /
# overridden this pass (fortification "Legends" units -- essentially zero
# fielded frequency in a matched-play-derived meta; left for a future pass).
CLASS_A_UNVERIFIED_LOW_PRIORITY = (
    "space_wolves_wolf_guard_pack_leader_in_terminator_armour_legends",
    "unaligned_forces_firestorm_redoubt_legends",
    "unaligned_forces_fortress_of_redemption_legends",
    "unaligned_forces_macro_cannon_aquila_strongpoint_legends",
    "unaligned_forces_vortex_missile_strongpoint_legends",
    "unaligned_forces_imperial_fortress_walls_legends",
    "dark_angels_deathwing_strikemaster_legends",
)

# Already remediated by a targeted fix in code/bsdata/loader.py before this
# audit ran (SWEG_IK_CANIS_SINGLE) -- listed so the scan doesn't re-flag it
# as an open finding.
KNOWN_FIXED = ("imperial_knights_library_canis_rex",)


def _load_units() -> List[Dict[str, Any]]:
    with open(PARSED_PATH, encoding="utf-8") as f:
        return json.load(f)["units"]


def _loadout_total(u: Dict[str, Any]) -> float:
    return sum(x.get("count", 0) for x in (u.get("model_loadouts") or []))


def scan_class_a(units: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    """Return (key, unit) pairs whose model_loadouts (a single real model's
    worth of gear) disagree with extract_squad_size's max_models > 1."""
    hits = []
    for u in units:
        maxm = u.get("max_models", 1)
        if maxm <= 1 or maxm > 4:
            # Cap at 4: genuine large squads with an under-populated
            # model_loadouts list (a separate, unrelated mapper gap) also
            # show total != max_models but are not "one model split into N"
            # -- e.g. a 10-model Cadian squad with only 1 loadout entry.
            # Capping keeps this scan's precision high; it is a
            # known limitation, not a claim that no >4 case exists.
            continue
        total = _loadout_total(u)
        if u.get("model_loadouts") and abs(total - 1.0) < 0.01:
            hits.append((u["key"], u))
    return hits


def scan_class_b(units: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    """Return (key, unit) pairs whose model_loadouts show >=2 DIFFERENTLY
    NAMED model slots summing correctly to max_models (a genuine multi-model
    combo unit), which still broadcast one shared `health` onto every
    physical model. Informational -- not auto-fixable via overrides.json.

    Gated on the CHARACTER / EPIC HERO keyword: an ordinary squad's
    model_loadouts entries are often differently-NAMED WEAPON-LOADOUT
    variants of the same real model type (e.g. Aquilon Custodians' six
    "Aquilon Custodian (Gauntlet & ...)" entries, or a Command Squad's
    per-member wargear labels) -- same real wounds, no bug, just a naming
    artifact of the per-model loadout distributor. The at-risk shape is
    specifically a NAMED lead CHARACTER bundled with differently-statted
    retinue models (Ghazghkull + Makari, Calgar + Victrix Honour Guard);
    restricting to units carrying CHARACTER/EPIC HERO cuts the raw
    same-name-set signal from ~240 (mostly loadout-label noise) down to the
    genuine combo-unit population."""
    hits = []
    for u in units:
        maxm = u.get("max_models", 1)
        loadouts = u.get("model_loadouts") or []
        if maxm <= 1 or len(loadouts) < 2:
            continue
        total = _loadout_total(u)
        if abs(total - maxm) > 0.5:
            continue
        names = {x.get("name", "") for x in loadouts}
        kws = set(u.get("unit_keywords") or [])
        if len(names) >= 2 and (kws & {"CHARACTER", "EPIC HERO"}):
            hits.append((u["key"], u))
    return hits


def _is_legends(u: Dict[str, Any]) -> bool:
    return "legends" in u["key"] or "[Legends]" in u.get("name", "")


def _archetype_reference_count(key: str) -> int:
    """How many ARCHETYPES[faction][name] template dicts name this key --
    a static proxy for fielded frequency (curated seed usage). Does not
    capture `_random_fill` reach (faction-filtered, seeded by RNG at battle
    time) -- report that separately per-unit in the audit narrative."""
    try:
        from code.archetypes import ARCHETYPES
    except Exception:
        return -1
    count = 0
    for _fac, templates in ARCHETYPES.items():
        for _name, template in templates.items():
            if key in template:
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--class", dest="cls", choices=["a", "b", "all"], default="all",
        help="Which defect class to print (a = health-aggregation bug, "
             "b = informational heterogeneous-combo broadcast, all = both).",
    )
    args = parser.parse_args()

    units = _load_units()
    by_key = {u["key"]: u for u in units}

    if args.cls in ("a", "all"):
        hits = scan_class_a(units)
        print("=== CLASS A: single-model unit miscounted as an N-model squad ===")
        print(f"{'key':55} {'min/max':>8} {'health':>7} {'pts':>6} {'legends':>8} {'archetype_refs':>14}")
        for key, u in sorted(hits, key=lambda kv: (_is_legends(kv[1]), -kv[1].get("health", 0))):
            status = []
            if key in KNOWN_FIXED:
                status.append("ALREADY-FIXED(loader.py)")
            if key in CLASS_A_CONFIRMED:
                status.append("CONFIRMED+OVERRIDE-APPLIED(data/overrides.json)")
            elif key in CLASS_A_UNVERIFIED_LOW_PRIORITY:
                status.append("flagged-not-yet-verified")
            refs = _archetype_reference_count(key)
            print(
                f"{key:55} {u['min_models']}/{u['max_models']:<5} "
                f"{u.get('health', 0):>7.1f} {u.get('points_listed', 0):>6.0f} "
                f"{str(_is_legends(u)):>8} {refs:>14}  {' '.join(status)}"
            )
        print(f"\n{len(hits)} Class A candidates total "
              f"({len(CLASS_A_CONFIRMED)} confirmed + override-proposed, "
              f"{len(KNOWN_FIXED)} already fixed pre-audit, "
              f"{len(hits) - len(CLASS_A_CONFIRMED) - len(KNOWN_FIXED)} flagged for a future pass).")

    if args.cls in ("b", "all"):
        hits_b = scan_class_b(units)
        print("\n=== CLASS B (informational only): heterogeneous multi-model combo units ===")
        print("These broadcast ONE shared health/toughness/save value onto every named")
        print("model slot even though the slots are different named models. Needs a")
        print("per-unit rules read (see imperial_knights_library_canis_rex / Sir Hekhtur")
        print("precedent in code/bsdata/loader.py) before any fix -- NOT auto-remediated.")
        for key, u in sorted(hits_b, key=lambda kv: -kv[1].get("health", 0))[:25]:
            names = [x.get("name") for x in u.get("model_loadouts", [])]
            print(f"{key:55} health={u.get('health'):>5} models={u['max_models']} {names}")
        print(f"\n{len(hits_b)} Class B units found (top 25 shown, sorted by health).")


if __name__ == "__main__":
    main()
