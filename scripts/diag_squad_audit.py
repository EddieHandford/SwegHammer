"""Squad-composition audit (structural re-model plan, Step 1 — no simulator run).

For each faction, build the production archetype army and report the squad-size
distribution: how many models end up in lone one-model squads versus coherent
multi-model squads. This is the binding self-veto for the SWEG_FILL_SQUADS
candidate — if horde fill is already coherent (the fill loop already calls
add_squad(chosen, size)), the lever is inert and the substrate re-base is a no-op.

Read-only: builds armies only, runs no battle. Run with PYTHONHASHSEED=0.
"""
import random
from code.army_builder import build_faction_random_army

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]

# Hordes/body-armies the plan says should be coherent multi-model squads.
HORDES = {"Astra Militarum", "Chaos Daemons", "Necrons", "Tyranids", "Orks",
          "Genestealer Cults"}

print(f"{'Faction':22s} {'models':>6} {'squads':>6} {'lone1':>5} {'multi':>5} "
      f"{'maxsz':>5} {'%modelsInLone':>13}")
print("-" * 74)
horde_lone_pcts = []
for fac in FACTIONS:
    try:
        army = build_faction_random_army(
            "A", fac, 2000, rng=random.Random(42), use_archetype=True)
    except Exception as e:  # noqa: BLE001
        print(f"{fac:22s} ERROR: {e}")
        continue
    groups = army.squads()  # OrderedDict[key, List[Unit]]
    sizes = [len(members) for members in groups.values()]
    n_models = sum(sizes)
    n_squads = len(sizes)
    lone = sum(1 for s in sizes if s == 1)
    multi = sum(1 for s in sizes if s > 1)
    models_in_lone = sum(s for s in sizes if s == 1)
    pct = 100.0 * models_in_lone / max(n_models, 1)
    if fac in HORDES:
        horde_lone_pcts.append(pct)
    print(f"{fac:22s} {n_models:6d} {n_squads:6d} {lone:5d} {multi:5d} "
          f"{(max(sizes) if sizes else 0):5d} {pct:12.0f}%")

print("-" * 74)
if horde_lone_pcts:
    avg = sum(horde_lone_pcts) / len(horde_lone_pcts)
    print(f"Horde factions: mean %models-in-lone-squads = {avg:.0f}%")
    print("VERDICT: SWEG_FILL_SQUADS is "
          + ("INERT (horde fill already coherent — substrate re-base is a no-op)"
             if avg < 25 else
             "LIVE (horde fill is largely lone-model — substrate gap confirmed)"))
