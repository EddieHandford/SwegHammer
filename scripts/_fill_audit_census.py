"""
_fill_audit_census.py  (READ-ONLY durability audit; scratch)

Horizontal, structural cut on the archetype build mechanism:
does build_archetype_army's seed + random-fill produce a
durability-per-point that CORRELATES with each faction's sc52a
over/under-pole?

For all 22 eval factions:
  * sample N archetype builds at 2000 pts via the EXACT anchor build path
    (build_archetype_army, all env gates at their production defaults),
  * split each army into SEED units and FILL units (wrapper on _random_fill
    records len(army.units) at the seed/fill boundary),
  * compute a durability-per-point vector, seed and fill separated.

Also computes the full 22-faction sc52a over/under-pole from the standing
anchor game log + the live Warp Friends real win rates, and correlates the
pole against each durability metric.

No tracked files are modified. Output: scratch JSON + printed tables.
"""
from __future__ import annotations

import json
import os
import random
import statistics
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("PYTHONHASHSEED", "0")

import code.archetypes as A
from code.archetypes import build_archetype_army, has_archetype, ARCHETYPES
from code.units import UNIT_CATALOG

ROOT = Path(__file__).resolve().parent.parent

FACTIONS: List[str] = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes", "Thousand Sons",
    "Leagues of Votann", "Chaos Space Marines", "World Eaters",
    "Emperor's Children", "Chaos Daemons", "Astra Militarum",
    "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights", "Drukhari",
    "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]

N_SAMPLES = 45
BUDGET = 2000.0

# ---------------------------------------------------------------------------
# Poles from the standing anchor game log + live Warp Friends real win rates.
# ---------------------------------------------------------------------------

def compute_poles():
    log = json.load(open(ROOT / "data" / "_anchor_sc52a_n80_log.json"))
    wins: Dict[str, int] = {f: 0 for f in FACTIONS}
    played: Dict[str, int] = {f: 0 for f in FACTIONS}
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
    poles = {}
    sim_wr = {}
    for f in FACTIONS:
        sw = 100.0 * wins[f] / played[f] if played[f] else float("nan")
        sim_wr[f] = sw
        poles[f] = sw - float(real[f]["win_rate"])
    return poles, sim_wr


# ---------------------------------------------------------------------------
# Durability metrics over a list of per-model Units.
# ---------------------------------------------------------------------------

def durable_brick(u) -> bool:
    p = u.profile
    return (p.toughness or 0) >= 10 or (p.health or 0) >= 15


def metrics(units) -> Dict[str, float]:
    pts = sum(u.profile.points_cost for u in units)
    w = sum(u.profile.health for u in units)
    if pts <= 0:
        return dict(points=0.0, wounds=0.0, wpp=0.0, wt_T=0.0,
                    inv_cov=0.0, fnp_cov=0.0, brick_share=0.0, models=len(units))
    wt_T = sum(u.profile.health * u.profile.toughness for u in units) / w if w else 0.0
    inv_w = sum(u.profile.health for u in units if (u.profile.invuln_save or 7) < 7)
    fnp_w = sum(u.profile.health for u in units if (u.profile.fnp or 7) < 7)
    brick_pts = sum(u.profile.points_cost for u in units if durable_brick(u))
    return dict(
        points=pts, wounds=w, wpp=w / pts, wt_T=wt_T,
        inv_cov=inv_w / w if w else 0.0,
        fnp_cov=fnp_w / w if w else 0.0,
        brick_share=brick_pts / pts,
        models=len(units),
    )


# ---------------------------------------------------------------------------
# Seed/fill-split build (uses the real build_archetype_army).
# ---------------------------------------------------------------------------

_seed_boundary = {"n": None}
_orig_fill = A._random_fill

def _wrapped_fill(army, faction, remaining_budget, rng, template=None):
    _seed_boundary["n"] = len(army.units)
    return _orig_fill(army, faction, remaining_budget, rng, template=template)

A._random_fill = _wrapped_fill


def sample_faction(faction: str, n: int):
    rows = []
    for i in range(n):
        _seed_boundary["n"] = None
        rng = random.Random(1000 + i)
        army = build_archetype_army(faction, faction, BUDGET, rng=rng)
        units = army.units
        n_seed = _seed_boundary["n"]
        if n_seed is None:
            n_seed = len(units)  # fill never ran (seed filled the budget)
        seed_units = units[:n_seed]
        fill_units = units[n_seed:]
        rows.append({
            "full": metrics(units),
            "seed": metrics(seed_units),
            "fill": metrics(fill_units),
            "arch": army.detachment.name if getattr(army, "detachment", None) else "",
        })
    return rows


def agg(rows, part, key):
    vals = [r[part][key] for r in rows if r[part]["points"] > 0]
    return statistics.mean(vals) if vals else 0.0


def main():
    poles, sim_wr = compute_poles()
    result = {}
    print("Sampling %d builds x %d factions at %dpt ...\n" % (N_SAMPLES, len(FACTIONS), BUDGET))
    for f in FACTIONS:
        if not has_archetype(f):
            print("  (no archetype) ", f)
            continue
        rows = sample_faction(f, N_SAMPLES)
        full_pts = agg(rows, "full", "points")
        seed_pts = agg(rows, "seed", "points")
        fill_pts = agg(rows, "fill", "points")
        result[f] = {
            "pole": poles[f],
            "sim_wr": sim_wr[f],
            "full": {k: agg(rows, "full", k) for k in
                     ("wpp", "wt_T", "inv_cov", "fnp_cov", "brick_share", "wounds", "points", "models")},
            "seed": {k: agg(rows, "seed", k) for k in
                     ("wpp", "wt_T", "inv_cov", "fnp_cov", "brick_share", "wounds", "points", "models")},
            "fill": {k: agg(rows, "fill", k) for k in
                     ("wpp", "wt_T", "inv_cov", "fnp_cov", "brick_share", "wounds", "points", "models")},
            "seed_pts_frac": seed_pts / full_pts if full_pts else 0.0,
            "fill_pts_frac": fill_pts / full_pts if full_pts else 0.0,
            "archs": sorted({r["arch"] for r in rows}),
        }
        print("  done %-22s pole=%+6.1f  wpp=%.4f  brick=%.2f  seedfrac=%.2f" % (
            f, poles[f], result[f]["full"]["wpp"],
            result[f]["full"]["brick_share"], result[f]["seed_pts_frac"]))

    out = ROOT / "scripts" / "_fill_audit_census_out.json"
    json.dump(result, open(out, "w"), indent=2)
    print("\nWrote", out)


if __name__ == "__main__":
    main()
