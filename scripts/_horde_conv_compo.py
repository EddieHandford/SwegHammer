"""READ-ONLY: sample the archetype army composition for the hordes and the elite
comparison, to read the character / monster-vehicle / horde-body / chaff counts
that drive the opponent's Fixed-pool anti-horde pick and the horde's own action
economy. Builds a few seeds per faction exactly as the eval does and reports
means. Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._horde_conv_compo
"""
from __future__ import annotations
import os, random, sys
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._horde_conv_compo"], env=os.environ).returncode)
from code.army_builder import build_faction_random_army
from code.secondaries import (_is_character, _is_monster_or_vehicle, _is_horde_unit,
                              _choose_secondary_track, _own_chaff_count)

FACS = ["Orks", "Genestealer Cults", "Adepta Sororitas", "Adeptus Custodes", "Death Guard"]

for fac in FACS:
    chars = mv = horde = chaff = units = models = 0
    tac = 0
    N = 8
    for s in range(N):
        random.seed(s)
        a = build_faction_random_army("A", fac, 2000, rng=random.Random(s), use_archetype=True)
        if not a.units:
            continue
        # per-army: count distinct-ish; units here are per-model Unit instances
        c = sum(1 for u in a.units if _is_character(u))
        m = sum(1 for u in a.units if _is_monster_or_vehicle(u))
        h = sum(1 for u in a.units if _is_horde_unit(u))
        chars += c; mv += m; horde += h
        units += len(a.units)
        chaff += _own_chaff_count(a)
        if _choose_secondary_track(a) == "TACTICAL":
            tac += 1
    print(f"{fac:20s} per-army means over {N}: chars={chars/N:.1f} MV={mv/N:.1f} "
          f"horde-bodies={horde/N:.1f} chaff={chaff/N:.1f} unit-instances={units/N:.0f} "
          f"TACTICAL={tac}/{N}")
