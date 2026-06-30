"""Firepower + piloting audit for one faction (under-pole diagnosis).

Generalises the wave-260+ manual artillery check: runs N archetype battles for a
faction against a strong aggressor and instruments every shot and every unit's
end-state, to surface the concrete, addressable artificial-intelligence and
firing failures that aggregate win rates hide — dormant weapons (a unit that
fields a gun but never fires it), firing collapse (a gunline swamped in melee
after round two), and units that die without contributing.

Usage:
    PYTHONHASHSEED=0 python -m scripts.diag_firepower_audit --faction "Drukhari"
    PYTHONHASHSEED=0 python -m scripts.diag_firepower_audit --faction "T'au Empire" --vs "Death Guard" --battles 16

Registered in docs/ANALYSIS_TOOLBOX.md. Pure single-process (no worker pool), so
it never hits the evaluate_vs_meta re-launch path.
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict

import code.units as U
from code.army_builder import build_faction_random_army
from code.simulator import Battle, RulesConfig
from code.maps import PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS


# ---- instrumentation state (module-level; reset per run) --------------------
_CUR_ROUND = [0]
_SHOTS = []  # (unit_id, unit_name, has_los, dmg, round)


def _has_ranged(profile) -> bool:
    """A unit can shoot if its primary ranged profile has range and attacks, or
    any model-loadout entry carries a ranged weapon."""
    if (getattr(profile, "range_inches", 0) or 0) > 0 and (getattr(profile, "attacks", 0) or 0) > 0:
        return True
    try:
        for m in U._unflatten_model_loadouts(profile.model_loadouts or ()):
            if m.get("ranged"):
                return True
    except Exception:
        pass
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--faction", required=True)
    p.add_argument("--vs", default="World Eaters",
                   help="aggressor opponent (default World Eaters, a melee over-pole)")
    p.add_argument("--battles", type=int, default=12)
    args = p.parse_args()

    orig_attack = U.Unit.attack
    orig_round = Battle._run_round

    def attack_patched(self, target, distance=0.0, mode="ranged", is_charging=False,
                       has_los=True, overwatch=False, alloc_next_fn=None):
        dmg = orig_attack(self, target, distance, mode, is_charging, has_los,
                          overwatch, alloc_next_fn)
        if mode != "melee":
            _SHOTS.append((id(self), self.profile.name, bool(has_los),
                           float(dmg), _CUR_ROUND[0]))
        return dmg

    def round_patched(self, round_num):
        _CUR_ROUND[0] = round_num
        return orig_round(self, round_num)

    U.Unit.attack = attack_patched
    Battle._run_round = round_patched

    # per-faction aggregates
    fielded_ranged = 0          # ranged-capable units fielded (sum over battles)
    fired_ranged = 0            # of those, ever fired
    dormant_names = defaultdict(int)   # ranged unit that NEVER fired -> count
    shots_by_round = defaultdict(int)
    blind_by_unit = defaultdict(lambda: [0, 0.0])
    dmg_by_unit = defaultdict(lambda: [0, 0.0])  # name -> [shots, dmg]
    fielded_units = 0
    died = 0
    alive_end = 0
    dormant_survived = 0   # ranged unit that NEVER fired but was ALIVE at end -> pilot forfeit
    dormant_died = 0       # ranged unit that NEVER fired and DIED -> swamped / killed first

    for b in range(args.battles):
        _SHOTS.clear()
        _CUR_ROUND[0] = 0
        s = b
        random.seed(s)
        a = build_faction_random_army("A", args.faction, 2000, rng=random.Random(s),
                                      use_archetype=True)
        opp = build_faction_random_army("B", args.vs, 2000, rng=random.Random(s + 10000),
                                        use_archetype=True)
        if not a.units or not opp.units:
            continue
        battle_map = STOCK_MAPS[PARIAH_NEXUS_2K_ROTATION[s % len(PARIAH_NEXUS_2K_ROTATION)]]
        # snapshot faction A roster BEFORE the battle
        roster = {id(u): u.profile.name for u in a.units}
        roster_ranged = {id(u): u.profile.name for u in a.units if _has_ranged(u.profile)}
        Battle(a, opp, map_=battle_map, rules=RulesConfig.vanilla_10e()).run()

        # which A units fired (ranged)? _SHOTS holds shots from BOTH armies, keyed
        # by object id; restrict to this battle's A roster.
        fired_ids = {k for (k, nm, los, dmg, rnd) in _SHOTS if k in roster}
        alive_ids_snap = {id(u) for u in a.alive_units}
        for uid, nm in roster_ranged.items():
            fielded_ranged += 1
            if uid in fired_ids:
                fired_ranged += 1
            else:
                dormant_names[nm] += 1
                if uid in alive_ids_snap:
                    dormant_survived += 1   # alive at end yet never fired = pilot forfeit
                else:
                    dormant_died += 1
        for (k, nm, los, dmg, rnd) in _SHOTS:
            if k not in roster:
                continue
            shots_by_round[rnd] += 1
            dmg_by_unit[nm][0] += 1
            dmg_by_unit[nm][1] += dmg
            if not los:
                blind_by_unit[nm][0] += 1
                blind_by_unit[nm][1] += dmg
        fielded_units += len(roster)
        # end-state: A units alive vs dead
        alive_ids = {id(u) for u in a.alive_units}
        alive_end += len(alive_ids)
        died += len(roster) - len(alive_ids & set(roster))

    U.Unit.attack = orig_attack
    Battle._run_round = orig_round

    n = args.battles
    print(f"\n=== FIREPOWER + PILOTING AUDIT — {args.faction} vs {args.vs} (N={n}) ===")
    cov = (100.0 * fired_ranged / fielded_ranged) if fielded_ranged else 0.0
    print(f"ranged-capable units fielded: {fielded_ranged/n:.1f}/game | "
          f"ever fired: {cov:.0f}%  (the rest are DORMANT)")
    dtot = dormant_survived + dormant_died
    if dtot:
        print(f"  of the dormant guns: {100.0*dormant_survived/dtot:.0f}% SURVIVED but never fired "
              f"(pilot forfeit) | {100.0*dormant_died/dtot:.0f}% died first (swamped)")
    print(f"units fielded: {fielded_units/n:.1f}/game | alive at end: {alive_end/n:.1f} | "
          f"died: {died/n:.1f}")
    tot_shots = sum(shots_by_round.values())
    print(f"ranged shots/game: {tot_shots/n:.1f}")
    print("  by round: " + "  ".join(
        f"R{r}={shots_by_round.get(r,0)/n:.1f}" for r in range(1, 6)))
    print("\nDORMANT ranged units (fielded with a gun, NEVER fired) — top offenders:")
    for nm, c in sorted(dormant_names.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {nm[:34]:36} dormant in {c}/{n} battles")
    if not dormant_names:
        print("  (none — every ranged unit fired at least once)")
    print("\nBlind / indirect shots (artillery bombarding without line of sight):")
    if blind_by_unit:
        for nm, (c, d) in sorted(blind_by_unit.items(), key=lambda kv: -kv[1][0])[:8]:
            print(f"  {nm[:34]:36} blind shots={c/n:.1f}/game  dmg={d/n:.1f}")
    else:
        print("  (no indirect fire fielded)")
    print("\nLowest-output ranged units (fired, but little damage — possible mis-pilot/over-matched):")
    low = sorted(((nm, v[0], v[1]) for nm, v in dmg_by_unit.items()), key=lambda x: x[2]/max(1, x[1]))
    for nm, c, d in low[:8]:
        print(f"  {nm[:34]:36} {c/n:.1f} shots/game  {d/max(1,c):.2f} dmg/shot")


if __name__ == "__main__":
    main()
