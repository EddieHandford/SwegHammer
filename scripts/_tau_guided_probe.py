"""Is T'au's Guided uptime high enough to matter, and is the buff even live?

T'au Empire is the cleanest mechanics target in the game (task #42): its
template is well sourced and 10 of 12 entries are realised in every army, so the
list layer is ruled out BY MEASUREMENT - yet it sits eleven places mis-ranked,
simulated 48.2 against a real 54.3, the second-strongest faction in reality.

Markerlights into Guided is the faction's defining army rule. `Battle.
_run_markerlight_phase` requires each MARKERLIGHT carrier to pass a Ballistic
Skill hit roll with line of sight at 36 inches; a single hit marks the target,
and friendly T'au attackers firing at a marked unit gain [LETHAL HITS] - but ONLY
if the resolved detachment carries `lethal_hits_on_guided`, which Mont'ka sets.

So there are two independent ways the faction's signature mechanic could be
worth nothing, and they need different fixes:

  DORMANT   the detachment never resolves to one carrying the flag, so the
            buff is never read no matter how many marks land.
  LOW UPTIME  marks land rarely - failed hit rolls, no line of sight, or out of
            range - so few attacks are ever made into a guided target.

This measures both, per round, over real battles. It does NOT theorise about
which is happening; it counts.

Run: PYTHONHASHSEED=0 python -m scripts._tau_guided_probe
     TG_BATTLES=24
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map

N = int(os.environ.get("TG_BATTLES", "24"))
FAC = "T'au Empire"

samples = []          # (guided_count, alive_enemy_count)
detach_flag = collections.Counter()
detach_name = collections.Counter()
marker_units = []

_real = Battle._run_markerlight_phase


def _patched(self, army, opponent):
    _real(self, army, opponent)
    fac = army.units[0].profile.faction if army.units else "?"
    if fac != FAC:
        return
    guided = set(getattr(army, "guided_enemy_uids", None) or ())
    alive = [u for u in opponent.units if u.is_alive]
    # Count DISTINCT enemy squads marked, not model-instances, since the
    # one-Unit-per-model representation would otherwise inflate both sides.
    alive_squads = {getattr(u, "squad_id", -1) if getattr(u, "squad_id", -1) >= 0
                    else id(u) for u in alive}
    guided_squads = {getattr(u, "squad_id", -1) if getattr(u, "squad_id", -1) >= 0
                     else id(u) for u in alive if u.uid in guided}
    samples.append((len(guided_squads), len(alive_squads)))


def main() -> None:
    opponents = [f for f in FACTIONS if f != FAC]
    Battle._run_markerlight_phase = _patched
    try:
        for i in range(N):
            opp = opponents[i % len(opponents)]
            seed = 11000 + i
            random.seed(seed)
            a = build_faction_random_army("A", FAC, 2000,
                                          rng=random.Random(seed),
                                          use_archetype=True)
            b = build_faction_random_army("B", opp, 2000,
                                          rng=random.Random(seed + 1),
                                          use_archetype=True)
            if not a.units or not b.units:
                continue
            # Detachment resolution happens in Battle construction.
            bt = Battle(a, b, map_=_pick_rotation_map(seed))
            det = getattr(a, "detachment", None)
            detach_name[getattr(det, "name", None) or repr(det)[:40]] += 1
            detach_flag[bool(getattr(det, "lethal_hits_on_guided", False))] += 1
            # Count MARKERLIGHT carriers actually fielded.
            n_mark = sum(1 for u in a.units
                         if "MARKERLIGHT" in set(u.profile.unit_keywords or ()))
            marker_units.append(n_mark)
            bt.run()
    finally:
        Battle._run_markerlight_phase = _real

    print(f"=== T'au Guided uptime, {N} battles ===\n")

    print("  DETACHMENT RESOLUTION")
    for name, n in detach_name.most_common():
        print(f"    {str(name)[:44]:<46}{n:>4} battles")
    live = detach_flag[True]
    print(f"    carries lethal_hits_on_guided: {live} of {sum(detach_flag.values())}"
          f" battles")
    if not live:
        print()
        print("    THE BUFF IS DORMANT. No resolved detachment carries the flag,")
        print("    so Unit.attack never reads a Guided mark and every")
        print("    Markerlight hit is wasted regardless of uptime.")

    print()
    if marker_units:
        mm = sum(marker_units) / len(marker_units)
        print(f"  MARKERLIGHT carriers fielded (model instances): mean {mm:.1f},"
              f" min {min(marker_units)}, max {max(marker_units)}")
        if min(marker_units) == 0:
            zero = sum(1 for m in marker_units if m == 0)
            print(f"    {zero} of {len(marker_units)} armies field NONE - the"
                  f" mechanic cannot fire at all in those")

    print()
    if not samples:
        print("  No markerlight phases observed for T'au.")
        return
    tot_g = sum(g for g, _ in samples)
    tot_a = sum(a for _, a in samples)
    zero = sum(1 for g, _ in samples if g == 0)
    print(f"  GUIDED UPTIME over {len(samples)} T'au shooting phases")
    print(f"    enemy squads marked, mean      {tot_g / len(samples):.2f}")
    phases_pct = 100.0 * zero / len(samples)
    print(f"    phases with ZERO marks         {phases_pct:.0f}%")
    print(f"    share of live enemy squads     "
          f"{100.0 * tot_g / max(tot_a, 1):.1f}%")
    print()
    print("  A low share means most T'au shooting is unbuffed. The codex")
    print("  pattern is Pathfinders and Stealth Suits saturating marks, which")
    print("  the module's own docstring calls the practical play pattern the")
    print("  one-hit simplification was meant to approximate.")


if __name__ == "__main__":
    main()
