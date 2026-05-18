"""iter17 TSON archetype diagnostic.

Following iter16 Rubricae Phalanx detachment-picker fix (commit 4837592),
TSON archetype eval was solo +3.1pt but cumulative -28.8pt. This script
probes the archetype seed composition + actual detachment chosen across
seeds, identifies cross-faction regress, and proposes template tweaks.

Hypotheses checked:
  H1) detachment picker now reliably picks Rubricae Phalanx vs Grand Coven.
  H2) Magnus the Red (435pt) doesn't fit at the 1000pt eval budget, so the
      iter15 expectation of Magnus-anchored TSON lists is structurally
      unreachable. Random_fill never picks Magnus because EPIC HERO
      keyword cap (template_count=0 -> 0 fill) excludes him entirely now.
  H3) Cabal of Sorcerers Rituals (Doombolt, Temporal Surge) fire per turn.
  H4) Adding Mutalith Vortex Beast (170pt MONSTER) as template anchor gives
      an Aux MONSTER threat. Pink Horrors / Blue Horrors are already in the
      catalogue and have 4++ invulns — adding them gives a cheap DAEMON
      durability pad.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter17_tson_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter
from typing import Dict, List

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter17_tson_diag"] + sys.argv[1:],
        os.environ,
    )

from code.archetypes import build_archetype_army, ARCHETYPES, _instantiate_template, _squad_cost
from code.army_builder import build_faction_random_army
from code.maps import DEFAULT_MAP
from code.simulator import Battle
from code.units import UNIT_CATALOG

TSON = "Thousand Sons"
POINTS = 1000
N = 30


def seed_composition_audit() -> None:
    """Sample 20 archetype seeds at 1000pt, print detachment + key units."""
    print(f"=== iter17 - Rubricae Phalanx seed composition audit ({POINTS}pt) ===\n")

    template = ARCHETYPES[TSON]['Rubricae Phalanx']
    print(f"Template: {template}\n")
    print("Squad costs:")
    for k in template:
        prof = UNIT_CATALOG[k]
        kw = ",".join(prof.unit_keywords or ())[:35]
        print(f"  {k}: {_squad_cost(k):.1f}pt count={template[k]} kw=({kw})")
    print()

    seeded = _instantiate_template(template, POINTS, random.Random(0), faction=TSON)
    print(f"Static seed at {POINTS}pt budget: {seeded}")
    seeded_pts = sum(_squad_cost(k) for k in seeded)
    print(f"  total seed pts = {seeded_pts:.1f} / {POINTS * 0.3:.0f} target slice\n")

    det_counter: Counter = Counter()
    char_counter: Counter = Counter()
    rubric_counter: Counter = Counter()
    print("Seed   Detachment        Total pts  RUBRICAE squads  Has Ahriman  Has SOT  Has Magnus")
    print("-" * 100)
    for s in range(20):
        rng = random.Random(s + 10000)
        army = build_archetype_army('A', TSON, POINTS, rng=rng)
        det_name = army.detachment.name if army.detachment else "(none)"
        det_counter[det_name] += 1
        names = Counter(u.profile.name for u in army.units)
        rubric_squads = names.get("Rubric Marines", 0) // 4  # min_models=4
        sot_squads = names.get("Scarab Occult Terminators", 0) // 4
        has_ahriman = names.get("Ahriman", 0) > 0
        has_magnus = names.get("Magnus the Red", 0) > 0
        char_counter['Ahriman'] += int(has_ahriman)
        char_counter['Magnus'] += int(has_magnus)
        rubric_counter['rubric_squads'] += rubric_squads
        rubric_counter['sot_squads'] += sot_squads
        print(f"  {s:2d}    {det_name:18s}  {army.total_points:7.1f}  "
              f"     {rubric_squads}/{sot_squads}              "
              f"  {'Y' if has_ahriman else 'N'}            "
              f"  {'Y' if sot_squads > 0 else 'N'}      "
              f"  {'Y' if has_magnus else 'N'}")

    print()
    print(f"Detachment frequency over 20 seeds: {dict(det_counter)}")
    print(f"Character frequency: Ahriman={char_counter['Ahriman']}/20, Magnus={char_counter['Magnus']}/20")
    print(f"Avg Rubric squads/army = {rubric_counter['rubric_squads']/20:.2f}")
    print(f"Avg Scarab Occult squads/army = {rubric_counter['sot_squads']/20:.2f}")
    print()


def cabal_ritual_audit() -> None:
    """Spin a TSON-vs-Necron battle, count Ritual events.

    Cabal Rituals are not emitted as a discrete event — we infer firing
    by counting MW dealt during the Shooting phase. The simplest check
    is to run a battle with the event log enabled and see if PSYKER
    activity registers.
    """
    print("=== iter17 - Cabal of Sorcerers ritual firing audit ===\n")
    random.seed(42)
    a = build_archetype_army('A', TSON, POINTS, rng=random.Random(0))
    b = build_faction_random_army('B', 'Necrons', POINTS,
                                  rng=random.Random(10000), use_archetype=False)
    if not a.units or not b.units:
        print("  Empty army, skipping")
        return

    psyker_count = sum(1 for u in a.units
                       if "PSYKER" in (u.profile.unit_keywords or ()))
    print(f"  TSON army has {psyker_count} PSYKER models")
    print(f"  TSON detachment: {a.detachment.name if a.detachment else '(none)'}")
    if a.detachment:
        print(f"  TSON detachment.all_is_dust = {a.detachment.all_is_dust}")

    battle = Battle(a, b, map_=DEFAULT_MAP)
    res = battle.run()
    print(f"  Result: winner={res.winner} rounds={res.rounds}")

    # Reports nothing more granular without simulator instrumentation,
    # but the fact that the battle completes with a PSYKER-heavy TSON
    # army confirms the Cabal pathway doesn't crash.
    print()


def template_variant_eval(label: str, template_override: Dict[str, int],
                          archetype_opponents: bool = False) -> float:
    """Run a TSON-vs-meta mini eval with `template_override` swapped in.

    If `archetype_opponents=True`, opponents also use archetype lists
    (matches the production evaluate_vs_meta --use-archetype matrix).
    Otherwise opponents are random_fill (legacy probe behaviour).

    Returns the mean WR over Necrons + Marines + T'au opponents at N=30 each.
    """
    # Patch the template in place, run, restore. Patches are scoped to
    # this function and reverted before returning.
    orig = ARCHETYPES[TSON]['Rubricae Phalanx']
    ARCHETYPES[TSON]['Rubricae Phalanx'] = template_override
    try:
        opponents = ["Adeptus Astartes", "Necrons", "T'au Empire"]
        wrs: List[float] = []
        for opp in opponents:
            wins = 0
            for s in range(N):
                rng_a = random.Random(s)
                rng_b = random.Random(s + 10000)
                a = build_archetype_army('A', TSON, POINTS, rng=rng_a)
                b = build_faction_random_army(
                    'B', opp, POINTS, rng=rng_b,
                    use_archetype=archetype_opponents,
                )
                if not a.units or not b.units:
                    continue
                r = Battle(a, b, map_=DEFAULT_MAP).run()
                if r.winner == "A":
                    wins += 1
            wr = wins / N * 100
            wrs.append(wr)
        print(f"  [{label}]  mean WR={statistics.mean(wrs):5.1f}%  per-opp={['%.1f' % w for w in wrs]}")
        return statistics.mean(wrs)
    finally:
        ARCHETYPES[TSON]['Rubricae Phalanx'] = orig


def template_variants(archetype_opponents: bool = False) -> None:
    """Probe alternate templates to find shape that lifts TSON WR.

    If `archetype_opponents=True`, opponents are archetype-shaped lists
    (matches the production evaluate_vs_meta --use-archetype matrix).

    Variants are micro-changes:
      V0: baseline (current iter17 template — includes Mutalith)
      V1: drop SOT (never fits) + add Daemon Prince
      V2: V1 + raise tzaangor count to 2
      V3: V1 + add Heldrake (215pt VEHICLE FLY)
      V4: drop SOT + add Lord of Change (285pt MONSTER EPIC HERO)
      V5: drop SOT + Chaos Predator Annihilator (130pt anti-tank)
    """
    suffix = "archetype opponents" if archetype_opponents else "random_fill opponents"
    print(f"=== iter17 - Template variant probe (N={N}, vs Marines/Necrons/T'au, {suffix}) ===\n")

    baseline = ARCHETYPES[TSON]['Rubricae Phalanx']
    print(f"Baseline (V0): {baseline}\n")

    base_no_sot = {k: v for k, v in baseline.items()
                   if k != 'thousand_sons_scarab_occult_terminators'}

    variants = {
        "V0 current": baseline,
        "V1 -SOT +Daemon Prince": {
            **base_no_sot,
            "thousand_sons_daemon_prince_of_tzeentch": 1,
        },
        "V2 V1 + 2x Tzaangors": {
            **base_no_sot,
            "thousand_sons_daemon_prince_of_tzeentch": 1,
            "thousand_sons_tzaangors": 2,
        },
        "V3 V1 + Heldrake (215pt)": {
            **base_no_sot,
            "thousand_sons_daemon_prince_of_tzeentch": 1,
            "thousand_sons_heldrake": 1,
        },
        "V4 -SOT + Lord of Change (285)": {
            **base_no_sot,
            "thousand_sons_lord_of_change": 1,
        },
        "V5 -SOT + Chaos Predator Annihilator": {
            **base_no_sot,
            "thousand_sons_chaos_predator_annihilator": 1,
        },
        "V6 +Pink Horrors": {
            **baseline,
            "thousand_sons_pink_horrors": 1,
        },
        "V7 -SOT + Forgefiend (130pt VEHICLE)": {
            **base_no_sot,
            "thousand_sons_forgefiend": 1,
        },
        "V8 +Helbrute (110pt)": {
            **base_no_sot,
            "thousand_sons_helbrute": 1,
        },
    }

    for label, tmpl in variants.items():
        template_variant_eval(label, tmpl, archetype_opponents=archetype_opponents)


def main() -> None:
    seed_composition_audit()
    cabal_ritual_audit()
    print("\n--- Variant probe vs random_fill opponents ---\n")
    template_variants(archetype_opponents=False)
    print("\n--- Variant probe vs archetype opponents (production matrix) ---\n")
    template_variants(archetype_opponents=True)


if __name__ == "__main__":
    main()
