"""Scratch mechanism check for SWEG_BGNT_RECIPROCAL (audit C reciprocal half).

Three demonstrations:
  1. Direct legality: `_reciprocal_ranged_legal` BLOCKS a shot at an engaged
     non-MONSTER/VEHICLE target and PERMITS a shot at an engaged MONSTER/VEHICLE.
  2. Numeric -1: driving a real Unit.attack many times with the flag off vs on
     shows the reciprocal -1 lowers the hit rate (fewer expected wounds).
  3. In-situ: instrument ONE real World-Eaters archetype battle and count both
     event kinds actually firing (a blocked non-brick shot; a permitted -1 shot
     at an engaged brick).
"""
from __future__ import annotations

import os
import random

os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ["SWEG_BGNT_RECIPROCAL"] = "1"

import code.simulator as sim
from code.simulator import (
    Battle,
    _er_gap_units,
    _reciprocal_ranged_legal,
    _er_engaged_by_other_unit,
)
from code.army_builder import build_faction_random_army


def _kw(u):
    return set(u.profile.unit_keywords or ())


def _first_ranged_unit(army):
    for u in army.units:
        p = u.profile
        if (p.range_inches or 0) >= 12 and (p.attacks or 0) > 0 and not p.pistol:
            return u
    return army.units[0]


# ---------------------------------------------------------------------------
# 1 + 2: synthetic direct legality + numeric -1
# ---------------------------------------------------------------------------
print("=" * 72)
print("DEMO 1/2 — direct legality + numeric -1 (synthetic placement)")
print("=" * 72)

random.seed(0)
we = build_faction_random_army("A", "World Eaters", 2000, rng=random.Random(0),
                               use_archetype=True)
opp = build_faction_random_army("B", "Death Guard", 2000, rng=random.Random(10000),
                                use_archetype=True)

shooter = _first_ranged_unit(we)
pinner = next(u for u in we.units if u is not shooter)

# An enemy INFANTRY (non-MONSTER/VEHICLE) target, and an enemy MONSTER/VEHICLE.
inf_target = next((u for u in opp.units
                   if not ({"MONSTER", "VEHICLE"} & _kw(u))), None)
brick_target = next((u for u in opp.units
                     if {"MONSTER", "VEHICLE"} & _kw(u)), None)

# Place: shooter far away (NOT itself engaged); pinner within 1" of each target
# in turn so the target is engaged by a friendly unit OTHER than the shooter.
shooter.position = (0.0, 0.0)
shooter.squad_id = 111
pinner.squad_id = 222  # different squad, so it counts as an "other unit"


def _probe(target, label):
    target.position = (30.0, 30.0)
    pinner.position = (30.3, 30.0)  # ~0.3" centre gap -> within Engagement Range
    eng_other = _er_engaged_by_other_unit(target, we.alive_units, shooter)
    legal = _reciprocal_ranged_legal(target, we.alive_units, shooter)
    print(f"\n[{label}] target = {target.profile.name}")
    print(f"    keywords: {sorted(_kw(target) & {'INFANTRY','MONSTER','VEHICLE','TITANIC'})}")
    print(f"    within Engagement Range of a friendly OTHER unit? {eng_other}")
    print(f"    _reciprocal_ranged_legal -> {legal}  "
          f"({'PERMITTED' if legal else 'BLOCKED'})")
    return legal


if inf_target is not None:
    legal_inf = _probe(inf_target, "a) engaged INFANTRY")
    assert legal_inf is False, "expected non-brick engaged target to be BLOCKED"
    print("    => (a) confirmed: shot at engaged infantry is BLOCKED")
else:
    print("\n[a] no non-brick target available in this opponent list")

if brick_target is not None:
    legal_brick = _probe(brick_target, "b) engaged MONSTER/VEHICLE")
    assert legal_brick is True, "expected engaged brick to be PERMITTED"
    print("    => (b) confirmed: shot at engaged brick is PERMITTED (carve-out)")

    # Numeric -1: fire the same ranged attacker at the brick many times, flag
    # off vs on, with a common seeded RNG each pass. The reciprocal -1 must
    # lower the empirical hit/damage.
    def _mean_damage(flag: bool, trials: int = 4000) -> float:
        rng = random.Random(2026)
        _orig = sim.random
        sim.random = rng
        try:
            import code.units as units_mod
            _orig_u = units_mod.random
            units_mod.random = rng
            total = 0.0
            for _ in range(trials):
                brick_target.current_health = brick_target.profile.health
                shooter.shooting_at_engaged_brick = flag
                total += shooter.attack(brick_target, distance=18.0, has_los=True)
            units_mod.random = _orig_u
            return total / trials
        finally:
            sim.random = _orig
    shooter.shooting_in_engagement = False
    off = _mean_damage(False)
    on = _mean_damage(True)
    print(f"\n    numeric -1 check ({shooter.profile.name} vs {brick_target.profile.name}):")
    print(f"      mean damage per activation, reciprocal flag OFF : {off:.3f}")
    print(f"      mean damage per activation, reciprocal flag ON  : {on:.3f}")
    print(f"      -> flag ON is {'LOWER' if on < off else 'NOT lower'} "
          f"(the -1 to Hit reduces output)")
else:
    print("\n[b] no MONSTER/VEHICLE target available in this opponent list")


# ---------------------------------------------------------------------------
# 3: in-situ instrumentation of one real battle
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("DEMO 3 — instrument ONE real World Eaters archetype battle")
print("=" * 72)

blocked = []   # (round, attacker, target, keywords)
minus1 = []    # (attacker, target, keywords)

_orig_legal = sim._reciprocal_ranged_legal


def _logging_legal(target, friendly_units, attacker):
    res = _orig_legal(target, friendly_units, attacker)
    if res is False:
        blocked.append((attacker.profile.name, target.profile.name,
                        sorted(_kw(target) & {"INFANTRY", "MONSTER", "VEHICLE", "TITANIC"})))
    return res


sim._reciprocal_ranged_legal = _logging_legal

import code.units as units_mod
_orig_attack = units_mod.Unit.attack


def _logging_attack(self, target, *a, **k):
    if getattr(self, "shooting_at_engaged_brick", False):
        minus1.append((self.profile.name, target.profile.name,
                       sorted(_kw(target) & {"INFANTRY", "MONSTER", "VEHICLE", "TITANIC"})))
    return _orig_attack(self, target, *a, **k)


units_mod.Unit.attack = _logging_attack

found = False
for seed in range(12):
    random.seed(seed)
    a = build_faction_random_army("A", "World Eaters", 2000,
                                  rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", "Death Guard", 2000,
                                  rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        continue
    blocked.clear()
    minus1.clear()
    Battle(a, b).run()
    if blocked and minus1:
        print(f"\nseed {seed}: both events fired in one battle")
        print(f"  (a) blocked non-brick shots: {len(blocked)} — first 3:")
        for row in blocked[:3]:
            print(f"        attacker {row[0]!r} -> target {row[1]!r} kw={row[2]}")
        print(f"  (b) permitted -1 shots at engaged brick: {len(minus1)} — first 3:")
        for row in minus1[:3]:
            print(f"        attacker {row[0]!r} -> target {row[1]!r} kw={row[2]}")
        found = True
        break

units_mod.Unit.attack = _orig_attack
sim._reciprocal_ranged_legal = _orig_legal

if not found:
    print("\n(no single battle showed BOTH events across 12 seeds; "
          f"last-battle counts: blocked={len(blocked)}, minus1={len(minus1)})")
print("\nDONE")
