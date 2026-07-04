"""
_compaudit_over_census.py  (READ-ONLY list-composition audit; scratch)

Samples archetype builds for the over-pole factions and reports, per faction:
  * the sc55a field-weighted pole (reconstructed from the standing anchor log
    + live Warp Friends real win rates, the evaluate_vs_meta aggregation),
  * the detachment distribution the picker actually returns,
  * per-unit presence: mean models, mean points, seed-vs-fill split, % of builds
    the unit appears in (the force-seed / phantom detector),
  * army-level durability-per-point (wpp) and total points/models.

No tracked files are modified. All env gates at production defaults (the
sc55a anchor build path). Windows: PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0.
"""
from __future__ import annotations

import json
import os
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("PYTHONHASHSEED", "0")

import code.archetypes as A
from code.archetypes import build_archetype_army, has_archetype
from code.units import UNIT_CATALOG

ROOT = Path(__file__).resolve().parent.parent

ALL_FACTIONS: List[str] = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes", "Thousand Sons",
    "Leagues of Votann", "Chaos Space Marines", "World Eaters",
    "Emperor's Children", "Chaos Daemons", "Astra Militarum",
    "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights", "Drukhari",
    "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]

OVER_POLES = [
    "Imperial Knights", "Chaos Knights", "Aeldari",
    "Adeptus Custodes", "Adeptus Astartes",
]

N_SAMPLES = 25
BUDGET = 2000.0


def compute_poles():
    log = json.load(open(ROOT / "data" / "_anchor_sc55a_n80_log.json"))
    wins: Dict[str, int] = {f: 0 for f in ALL_FACTIONS}
    played: Dict[str, int] = {f: 0 for f in ALL_FACTIONS}
    for a_fac, b_fac, _seed, winner in log["games"]:
        if winner is None:
            continue
        played[a_fac] += 1
        played[b_fac] += 1
        if winner == "A":
            wins[a_fac] += 1
        elif winner == "B":
            wins[b_fac] += 1
    real = json.load(open(ROOT / "data" / "warpfriends_rolling.json"))["factions"]
    poles, sim_wr, real_wr = {}, {}, {}
    for f in ALL_FACTIONS:
        sw = 100.0 * wins[f] / played[f] if played[f] else float("nan")
        sim_wr[f] = sw
        real_wr[f] = float(real[f]["win_rate"])
        poles[f] = sw - real_wr[f]
    return poles, sim_wr, real_wr


# seed/fill boundary wrapper
_seed_boundary = {"n": None}
_orig_fill = A._random_fill


def _wrapped_fill(army, faction, remaining_budget, rng, template=None):
    _seed_boundary["n"] = len(army.units)
    return _orig_fill(army, faction, remaining_budget, rng, template=template)


A._random_fill = _wrapped_fill


def sample_faction(faction: str, n: int):
    per_unit = defaultdict(lambda: {"models": 0.0, "points": 0.0,
                                     "seed_models": 0.0, "fill_models": 0.0,
                                     "builds": 0})
    det_counts = defaultdict(int)
    army_pts, army_models, army_wpp = [], [], []
    for i in range(n):
        _seed_boundary["n"] = None
        rng = random.Random(1000 + i)
        army = build_archetype_army(faction, faction, BUDGET, rng=rng)
        units = army.units
        n_seed = _seed_boundary["n"]
        if n_seed is None:
            n_seed = len(units)
        det = army.detachment.name if getattr(army, "detachment", None) else "(none)"
        det_counts[det] += 1

        # group by profile name
        seen_names = set()
        name_models = defaultdict(float)
        name_points = defaultdict(float)
        name_seedm = defaultdict(float)
        name_fillm = defaultdict(float)
        for idx, u in enumerate(units):
            nm = u.profile.name
            name_models[nm] += 1
            name_points[nm] += u.profile.points_cost
            if idx < n_seed:
                name_seedm[nm] += 1
            else:
                name_fillm[nm] += 1
            seen_names.add(nm)
        for nm in seen_names:
            per_unit[nm]["models"] += name_models[nm]
            per_unit[nm]["points"] += name_points[nm]
            per_unit[nm]["seed_models"] += name_seedm[nm]
            per_unit[nm]["fill_models"] += name_fillm[nm]
            per_unit[nm]["builds"] += 1

        pts = sum(u.profile.points_cost for u in units)
        w = sum(u.profile.health for u in units)
        army_pts.append(pts)
        army_models.append(len(units))
        army_wpp.append(w / pts if pts else 0.0)

    # finalize means (divide by n)
    rows = []
    for nm, d in per_unit.items():
        rows.append({
            "name": nm,
            "models": d["models"] / n,
            "points": d["points"] / n,
            "seed_models": d["seed_models"] / n,
            "fill_models": d["fill_models"] / n,
            "in_pct": 100.0 * d["builds"] / n,
        })
    rows.sort(key=lambda r: -r["points"])
    return {
        "detachments": {k: 100.0 * v / n for k, v in det_counts.items()},
        "units": rows,
        "army_points": statistics.mean(army_pts),
        "army_models": statistics.mean(army_models),
        "army_wpp": statistics.mean(army_wpp),
    }


def main():
    poles, sim_wr, real_wr = compute_poles()
    print("=== sc55a reconstructed poles (field-weighted from anchor log) ===")
    for f in OVER_POLES:
        print("  %-20s sim=%5.1f real=%5.1f pole=%+6.1f" % (
            f, sim_wr[f], real_wr[f], poles[f]))
    print()

    out = {"poles": {f: {"sim": sim_wr[f], "real": real_wr[f], "pole": poles[f]}
                     for f in OVER_POLES}}
    for f in OVER_POLES:
        if not has_archetype(f):
            print("(no archetype)", f)
            continue
        print("=" * 78)
        print("FACTION: %s  pole=%+.1f (sim %.1f vs real %.1f)" % (
            f, poles[f], sim_wr[f], real_wr[f]))
        res = sample_faction(f, N_SAMPLES)
        out[f] = res
        print("  army: %.0f pts, %.1f models, wpp=%.4f" % (
            res["army_points"], res["army_models"], res["army_wpp"]))
        print("  DETACHMENTS: " + ", ".join(
            "%s %.0f%%" % (k, v) for k, v in sorted(
                res["detachments"].items(), key=lambda kv: -kv[1])))
        print("  %-42s %6s %6s %5s %5s %5s" % (
            "unit", "mdl", "pts", "seed", "fill", "in%"))
        for r in res["units"]:
            if r["points"] < 1 and r["in_pct"] < 5:
                continue
            print("  %-42s %6.2f %6.0f %5.2f %5.2f %4.0f" % (
                r["name"][:42], r["models"], r["points"],
                r["seed_models"], r["fill_models"], r["in_pct"]))
        print()

    outpath = ROOT / "scripts" / "_compaudit_over_census_out.json"
    json.dump(out, open(outpath, "w"), indent=2)
    print("Wrote", outpath)


if __name__ == "__main__":
    main()
