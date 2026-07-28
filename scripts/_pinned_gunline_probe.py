"""MEASURED: when a gun-carrying unit is pinned in melee, can it ever leave?

The static audit (scripts/_fallback_eligibility_audit.py) says 145 ranged-primary
catalogue units are ineligible for the Fall Back branch in
`strategy.pick_move_intent` — 45 because `roles.classify` labels every
single-wound gunline HORDE before it can be SHOOTY, and 89 because the
eligibility list is ("SHOOTY", "HEAVY") and simply omits ranged-primary DUAL.

A catalogue audit is not a behavioural claim. This one hooks the live decision
and counts, per activation of a ranged-primary unit standing inside enemy
Engagement Range, WHY it did not Fall Back:

    eligible -> FELL BACK            the branch worked
    eligible -> no destination       branch reached, geometry refused
    STRANDED: role not SHOOTY/HEAVY  the classify collision
    STRANDED: _is_melee_class        deliberate (task #7) - melee unit stays

It also records how many consecutive rounds a pinned unit stays pinned, which is
the quantity that decides whether a connected charge is over-rewarded.

Run: PYTHONHASHSEED=0 python -m scripts._pinned_gunline_probe
"""
from __future__ import annotations
import collections
import os
import random

import code.strategy as STRAT
from code.army_builder import build_faction_random_army
from code.roles import classify, combat_profile, expected_melee_dpa, expected_ranged_dpa
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("PG_FACTION", "Tyranids")
N = int(os.environ.get("PG_N", "4"))
OPPS = [f.strip() for f in os.environ.get(
    "PG_OPPS", "Adeptus Astartes,Astra Militarum,T'au Empire,Necrons").split(",")]
_idx = {f: i for i, f in enumerate(FACTIONS)}

C = collections.Counter()
PINNED_RUN = collections.Counter()   # uid -> consecutive pinned activations
RUNS = []                            # completed pinned-run lengths
_real = STRAT.pick_move_intent


def _hook(unit, friendly, enemy, map_, *a, **kw):
    res = _real(unit, friendly, enemy, map_, *a, **kw)
    try:
        p = unit.profile
        prof = combat_profile(p)
        ranged_primary = (prof in ("RANGED_ONLY", "DUAL")
                          and expected_ranged_dpa(p) > expected_melee_dpa(p))
        if ranged_primary:
            pinned = any(
                STRAT._er_gap(unit.position, p, e.position, e.profile,
                              base_edge=True) <= STRAT._ENGAGEMENT_RANGE
                for e in enemy.alive_units)
            if pinned:
                C["pinned activations"] += 1
                PINNED_RUN[unit.uid] += 1
                role = classify(p)
                fb = (res[1] == STRAT._FALL_BACK_INTENT)
                # Attribute in the SHORT-CIRCUIT ORDER the code actually uses:
                #   role in _fall_back_eligible_roles  AND  not _is_melee_class(...)
                # The role test runs FIRST, so a unit excluded by its role label
                # never reaches the melee-class test at all. Bucketing on
                # _is_melee_class first (an earlier version of this probe) blamed
                # the melee-class test for exclusions the ROLE test had already
                # made, and produced a false 40.8 percent attribution.
                _elig = ("SHOOTY", "HEAVY", "DUAL") if (
                    p.faction in STRAT._VOTANN_FALLBACK_FACTIONS) else ("SHOOTY", "HEAVY")
                if role not in _elig:
                    C[f"[1] role test excludes: role={role}"] += 1
                elif STRAT._is_melee_class(STRAT._score_profile(unit)):
                    C["[2] melee-class test excludes (gate can move these)"] += 1
                else:
                    C["[3] reached the branch"] += 1
                # Report the ACTUAL intent in every bucket. An earlier version
                # bucketed on `_is_melee_class` first and reported that label
                # regardless of the returned intent, so it could not see
                # SWEG_FALLBACK_EFFECTIVE_DAMAGE change anything.
                if fb:
                    C["FELL BACK"] += 1
                if STRAT._is_melee_class(p):
                    C["raw-volume melee-class"
                      + (" -> now FELL BACK" if fb else " -> stayed")] += 1
                elif role in ("SHOOTY", "HEAVY"):
                    C["eligible -> FELL BACK" if fb
                      else f"eligible -> no fall back ({res[1]})"] += 1
                else:
                    C[f"STRANDED: role={role}"
                      + (" -> FELL BACK" if fb else "")] += 1
            else:
                if PINNED_RUN.get(unit.uid):
                    RUNS.append(PINNED_RUN.pop(unit.uid))
    except Exception as exc:      # never let the probe change the game
        C[f"probe error: {type(exc).__name__}"] += 1
    return res


def main() -> None:
    STRAT.pick_move_intent = _hook
    import code.simulator as SIM
    SIM.pick_move_intent = _hook
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed),
                                          use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000),
                                          use_archetype=True)
            Battle(a, b, map_=_pick_rotation_map(seed),
                   primary_mission=_pick_primary_mission(ps)).run()
    RUNS.extend(PINNED_RUN.values())

    tot = max(1, C["pinned activations"])
    print(f"=== ranged-primary units pinned in Engagement Range ({FAC} vs "
          f"{len(OPPS)} opponents, {N} seeds each) ===")
    print(f"    pinned activations observed: {tot}")
    print()
    for k, v in C.most_common():
        if k == "pinned activations":
            continue
        print(f"    {100*v/tot:5.1f}%  ({v:4d})  {k}")
    if RUNS:
        RUNS.sort()
        print()
        print(f"    consecutive activations spent pinned: n={len(RUNS)} "
              f"median={RUNS[len(RUNS)//2]} mean={sum(RUNS)/len(RUNS):.2f} "
              f"max={RUNS[-1]}")
        print(f"    pinned for 3+ activations: "
              f"{100*sum(1 for r in RUNS if r >= 3)/len(RUNS):.1f}%")


if __name__ == "__main__":
    main()
