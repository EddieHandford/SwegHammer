"""Fill-realism probe (brief method step 3): for factions spanning the poles,
tally what the RANDOM FILL actually selects (unit -> mean point share of the
fill slice) and flag whether the uniform-within-template-pool draw over-selects
the faction's most durable/expensive units, or skews toward cheap chaff.
Compares the fill's point-weighted mean cost-per-model and wounds-per-point to
the seed's. READ-ONLY.
"""
import json
import os
import random
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("PYTHONHASHSEED", "0")

import code.archetypes as A
from code.archetypes import build_archetype_army, _effective_template, ARCHETYPES
from code.units import UNIT_CATALOG

ROOT = Path(__file__).resolve().parent.parent
BUDGET = 2000.0
N = 45

SPAN = [
    ("Death Guard", "durable over-pole +22"),
    ("Imperial Knights", "brick over-pole +18"),
    ("Aeldari", "fragile over-pole +15"),
    ("Astra Militarum", "durable-ish under-pole -12"),
    ("Orks", "horde under-pole -8"),
    ("Adeptus Astartes", "mid -4"),
]

_seed_boundary = {"n": None}
_orig_fill = A._random_fill
def _wrapped(army, faction, rb, rng, template=None):
    _seed_boundary["n"] = len(army.units)
    return _orig_fill(army, faction, rb, rng, template=template)
A._random_fill = _wrapped


def brick(p):
    return (p.toughness or 0) >= 10 or (p.health or 0) >= 15


for fac, tag in SPAN:
    fill_pts = defaultdict(float)
    seed_pts = defaultdict(float)
    tot_fill = tot_seed = 0.0
    fill_brick_pts = seed_brick_pts = 0.0
    for i in range(N):
        _seed_boundary["n"] = None
        rng = random.Random(1000 + i)
        army = build_archetype_army(fac, fac, BUDGET, rng=rng)
        units = army.units
        ns = _seed_boundary["n"] if _seed_boundary["n"] is not None else len(units)
        for u in units[:ns]:
            seed_pts[u.profile.name] += u.profile.points_cost
            tot_seed += u.profile.points_cost
            if brick(u.profile):
                seed_brick_pts += u.profile.points_cost
        for u in units[ns:]:
            fill_pts[u.profile.name] += u.profile.points_cost
            tot_fill += u.profile.points_cost
            if brick(u.profile):
                fill_brick_pts += u.profile.points_cost

    # template pool for this faction (what the fill can draw from under
    # SWEG_FILL_TEMPLATE_POOL=1)
    tpl_names = set()
    for arch, tmpl in ARCHETYPES[fac].items():
        eff = _effective_template(fac, tmpl)
        for k in eff:
            if k in UNIT_CATALOG:
                tpl_names.add(UNIT_CATALOG[k].name)

    print("=" * 72)
    print("%s  (%s)" % (fac, tag))
    print("  seed brick point-share: %.2f   fill brick point-share: %.2f" % (
        seed_brick_pts / tot_seed if tot_seed else 0,
        fill_brick_pts / tot_fill if tot_fill else 0))
    print("  FILL composition (unit : pt-share of fill : T/W/cost-per-model):")
    for name, pts in sorted(fill_pts.items(), key=lambda kv: -kv[1]):
        prof = next((UNIT_CATALOG[k] for k in UNIT_CATALOG
                     if UNIT_CATALOG[k].name == name), None)
        tw = ("T%d W%.0f %gpt" % (prof.toughness, prof.health, prof.points_cost)
              if prof else "?")
        intpl = "" if name in tpl_names else "  [NON-TEMPLATE]"
        print("    %-38s %5.1f%%  %s%s" % (name, 100 * pts / tot_fill, tw, intpl))
