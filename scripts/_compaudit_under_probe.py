"""
Read-only lever-validation probes for the under-pole audit. NOT a code change:
the Ork probe monkeypatches an in-memory copy of the template to confirm the
proposed one-line fix seeds as expected; nothing is written to source.

  PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._compaudit_under_probe
"""
from __future__ import annotations

import collections
import os
import random

# Probe 1 — Astra Militarum Grizzled Company detachment flip. The gate is read
# at import time in code.detachments, so set it BEFORE importing anything.
os.environ["SWEG_AM_GRIZZLED"] = "1"

from code.army_builder import build_faction_random_army, is_epic_hero  # noqa: E402
from code.units import UNIT_CATALOG  # noqa: E402
from code import archetypes  # noqa: E402

N = 20
BUDGET = 2000.0


def probe_am_grizzled():
    det = collections.Counter()
    for s in range(N):
        army = build_faction_random_army(
            "A", "Astra Militarum", BUDGET, rng=random.Random(s), use_archetype=True
        )
        d = getattr(army, "detachment", None)
        det[getattr(d, "name", "NONE")] += 1
    print("PROBE 1 — Astra Militarum with SWEG_AM_GRIZZLED=1:")
    for name, c in det.most_common():
        print(f"    {c:2d}/{N}  {name}")
    print()


def probe_orks_ghazghkull():
    # Monkeypatch an in-memory copy of the Waaagh! template with Ghazghkull.
    orig = archetypes.ARCHETYPES["Orks"]["Waaagh!"]
    patched = dict(orig)
    patched["orks_ghazghkull_thraka"] = 1
    archetypes.ARCHETYPES["Orks"]["Waaagh!"] = patched
    try:
        ghaz_builds = 0
        bodies = []
        wounds = []
        for s in range(N):
            army = build_faction_random_army(
                "A", "Orks", BUDGET, rng=random.Random(s), use_archetype=True
            )
            names = {u.profile.name for u in army.units}
            if "Ghazghkull Thraka" in names:
                ghaz_builds += 1
            bodies.append(len(army.units))
            w = 0.0
            for u in army.units:
                w += float(getattr(u.profile, "health", 1) or 1)
            wounds.append(w)
        print("PROBE 2 — Orks with Ghazghkull added to the Waaagh! template "
              "(in-memory only):")
        print(f"    Ghazghkull fielded in {ghaz_builds}/{N} builds")
        print(f"    Avg body {sum(bodies)/len(bodies):.1f}, "
              f"avg wounds {sum(wounds)/len(wounds):.1f}")
        print()
    finally:
        archetypes.ARCHETYPES["Orks"]["Waaagh!"] = orig


if __name__ == "__main__":
    probe_am_grizzled()
    probe_orks_ghazghkull()
