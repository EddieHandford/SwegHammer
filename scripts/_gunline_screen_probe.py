"""Is the deep-strike screen check blind to single-wound gunlines?

`strategy._is_gunline_screened(opponent)` decides whether a Round-2 deep-strike
alpha strike is worthwhile: it collects the opponent's SHOOTY/HEAVY units as
`shooters`, its HORDE/SUPPORT/MELEE/DUAL units as `screeners`, and returns True
only if every shooter has a screen within 9 inches. On `if not shooters: return
False` the caller reads "gunline not screened" and the drop goes in.

`roles.classify` labels a one-wound, save-4-or-worse, low-output unit HORDE
before it can be SHOOTY. So Guardsmen, Termagants, Fire Warriors, Necron
Warriors and Neophyte Hybrids — entire gunlines — are counted as SCREENERS and
never as SHOOTERS. For an army made only of those, `shooters` is empty and the
function reports "unscreened" no matter how densely the army is actually packed.

This counts, per call and per defending faction:
    shooters empty  -> returned False for lack of any recognised shooter
    hidden gunlines -> units the label missed that combat_profile says shoot
    verdict flips   -> what the answer would be if those units counted

Run: PYTHONHASHSEED=0 python -m scripts._gunline_screen_probe
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

N = int(os.environ.get("GS_N", "3"))
PAIRS = [
    # (deep-strike-capable attacker, defender with a single-wound gunline)
    ("Adeptus Astartes", "Astra Militarum"),
    ("Adeptus Astartes", "Tyranids"),
    ("Drukhari", "T'au Empire"),
    ("Genestealer Cults", "Necrons"),
    ("Chaos Daemons", "Astra Militarum"),
    ("Adepta Sororitas", "Tyranids"),
]
_idx = {f: i for i, f in enumerate(FACTIONS)}

C = collections.Counter()
BYFAC = collections.defaultdict(collections.Counter)
_real = STRAT._is_gunline_screened


def _ranged_primary(p) -> bool:
    return (combat_profile(p) in ("RANGED_ONLY", "DUAL")
            and expected_ranged_dpa(p) > expected_melee_dpa(p))


def _hook(opponent):
    res = _real(opponent)
    try:
        if opponent is not None:
            units = opponent.alive_units
            fac = (units[0].profile.faction or "?") if units else "?"
            labelled = [u for u in units if classify(u.profile) in ("SHOOTY", "HEAVY")]
            hidden = [u for u in units
                      if classify(u.profile) not in ("SHOOTY", "HEAVY")
                      and _ranged_primary(u.profile)]
            C["calls"] += 1
            BYFAC[fac]["calls"] += 1
            if not labelled:
                C["no recognised shooter -> returned False"] += 1
                BYFAC[fac]["no recognised shooter"] += 1
                if hidden:
                    C["  ...but the army DID have gunline units"] += 1
                    BYFAC[fac]["hidden gunline present"] += 1
            if hidden:
                C["calls with at least one hidden gunline unit"] += 1
                BYFAC[fac]["hidden units seen"] += len(hidden)
            # Would counting the hidden gunlines flip the verdict?
            if hidden:
                allsh = labelled + hidden
                screeners = [u for u in units
                             if classify(u.profile) in ("HORDE", "SUPPORT", "MELEE", "DUAL")]
                flipped = bool(allsh) and all(
                    any(STRAT._dist(s.position, c.position) <= 9.0
                        for c in screeners if c is not s)
                    for s in allsh)
                if flipped != res:
                    C[f"VERDICT FLIPS {res} -> {flipped}"] += 1
                    BYFAC[fac]["verdict flips"] += 1
    except Exception as exc:
        C[f"probe error: {type(exc).__name__}"] += 1
    return res


def main() -> None:
    # The sole caller is strategy.py:5203, in this same module, and it resolves
    # the name through module globals at call time — so rebinding here is enough.
    STRAT._is_gunline_screened = _hook
    for att, dfn in PAIRS:
        for seed in range(N):
            ps = (_idx[att] * 1000 + _idx[dfn]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (dfn, att) if swap else (att, dfn)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed),
                                          use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000),
                                          use_archetype=True)
            Battle(a, b, map_=_pick_rotation_map(seed),
                   primary_mission=_pick_primary_mission(ps)).run()

    tot = max(1, C["calls"])
    print("=== _is_gunline_screened: does the label hide the gunline? ===")
    print(f"    calls observed: {tot}")
    for k, v in C.most_common():
        if k == "calls":
            continue
        print(f"    {100*v/tot:5.1f}%  ({v:4d})  {k}")
    print()
    print("    by defending faction:")
    for fac, c in sorted(BYFAC.items(), key=lambda kv: -kv[1]["calls"]):
        if not c["calls"]:
            continue
        print(f"      {fac:<22} calls={c['calls']:<5} "
              f"no-shooter={c['no recognised shooter']:<5} "
              f"hidden-present={c['hidden gunline present']:<5} "
              f"flips={c['verdict flips']}")


if __name__ == "__main__":
    main()
