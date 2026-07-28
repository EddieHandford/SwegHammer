"""Scratch: for AM vs Astartes across seeds, decompose the loss into PRIMARY vs
SECONDARY VP, and count AM's futile melee (charges that whiff for <=1 dmg) + AM
unit deaths. Disambiguates: is AM's loss a primary (can't-hold) or secondary
(assassination/kill-bleed) problem? Read-only. Not committed."""
from __future__ import annotations
import random
import sys

from code.army_builder import build_faction_random_army
from code.events import (
    RoundEnded, BattleStarted, UnitCharged, UnitFought, UnitKilled, EventLog,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
B_FAC = "Adeptus Astartes"
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
seeds = [int(x) for x in sys.argv[1:]] or [5, 10, 7, 13, 9, 15, 8, 11]

print(f"# {A_FAC} (A) vs {B_FAC} (B): primary/secondary decomposition")
print(f"{'seed':>4} {'win':>3} {'Apri':>4} {'Bpri':>4} {'Asec':>4} {'Bsec':>4} "
      f"{'pri_d':>5} {'sec_d':>5} | {'Achg':>4} {'Awhiff':>6} {'Adead':>5} {'Bdead':>5}")
agg = {"pri_d": 0, "sec_d": 0, "Achg": 0, "Awhiff": 0, "Adead": 0, "Bdead": 0, "n": 0}
for seed in seeds:
    pair_seed = (_fac_idx[A_FAC] * 1000 + _fac_idx[B_FAC]) * 100 + seed
    random.seed(pair_seed)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    primary = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, subscribers=[log], map_=map_, primary_mission=primary)
    battle.run()
    ev = log.events
    res = [e for e in ev if isinstance(e, RoundEnded)]
    if not res:
        continue
    last = res[-1]
    ac, bc = last.a_vp_capped, last.b_vp_capped
    asec = getattr(battle, "_a_secondary_vp", 0)
    bsec = getattr(battle, "_b_secondary_vp", 0)
    achal = getattr(battle, "_a_challenger_vp", 0)
    bchal = getattr(battle, "_b_challenger_vp", 0)
    # capped primary ~ capped total minus capped secondary (approx; challenger small)
    apri = ac - min(asec, 40) - achal
    bpri = bc - min(bsec, 40) - bchal
    win = "A" if ac > bc else ("B" if bc > ac else "=")

    army = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                army[u.uid] = u.army
    achg = sum(1 for e in ev if isinstance(e, UnitCharged)
               and army.get(e.unit_uid) == "A" and e.succeeded)
    # AM melee swings that dealt <=1 damage (whiffed against durable Marines)
    awhiff = sum(1 for e in ev if isinstance(e, UnitFought)
                 and army.get(e.attacker_uid) == "A" and e.damage <= 1)
    adead = sum(1 for e in ev if isinstance(e, UnitKilled) and army.get(e.unit_uid) == "A")
    bdead = sum(1 for e in ev if isinstance(e, UnitKilled) and army.get(e.unit_uid) == "B")

    print(f"{seed:>4} {win:>3} {apri:>4} {bpri:>4} {asec:>4} {bsec:>4} "
          f"{apri-bpri:>+5} {asec-bsec:>+5} | {achg:>4} {awhiff:>6} {adead:>5} {bdead:>5}")
    agg["pri_d"] += apri - bpri; agg["sec_d"] += asec - bsec
    agg["Achg"] += achg; agg["Awhiff"] += awhiff
    agg["Adead"] += adead; agg["Bdead"] += bdead; agg["n"] += 1

n = max(agg["n"], 1)
print(f"\n# MEANS over {n} games: primary_diff {agg['pri_d']/n:+.1f}  "
      f"secondary_diff {agg['sec_d']/n:+.1f}  AM_charges {agg['Achg']/n:.1f}  "
      f"AM_whiff_swings {agg['Awhiff']/n:.1f}  AM_dead {agg['Adead']/n:.1f}  "
      f"Astartes_dead {agg['Bdead']/n:.1f}")
