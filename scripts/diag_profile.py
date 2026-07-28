"""Consolidated faction profile — why do two body-heavy 'shooty hordes' land on
opposite poles? Astra Militarum (-19.9 under) vs Orks (+3.70 over), with the
melee over-pole and references for context.

Single run, per faction:
  * win%                     within-panel
  * prim/1k                  primary objective VP per 1000 pts (scoring outcome)
  * melee/1k                 melee damage dealt per 1000 pts (UnitFought via the
                             current-attacker faction; Orks fight, Guardsmen don't)
  * dmgTaken/1k              total damage absorbed per 1000 pts (low = tanky)
  * present/g                objective markers it had OC on at scoring
  * bodyT / bodyW            mean toughness / wounds of its BODY units (ranged
                             DPA < 1.5) — the STRUCTURAL durability of the cheap
                             objective-holders (Ork Boyz T5 vs Guardsmen T3)
  * surv%                    models alive at game end
  * models                   mean army size

Hypothesis: Orks over-rate because its horde bodies are durable + can fight, so
they HOLD contested markers; Astra Militarum under-rates because its bodies are
fragile shooting-only and die on contested markers.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_profile
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_profile"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import code.simulator as sim
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

PANEL = ["Aeldari", "Adeptus Astartes", "Death Guard", "World Eaters",
         "Astra Militarum", "Orks", "T'au Empire", "Adeptus Custodes"]
HILITE = {"Aeldari"}
SEEDS = [0, 1, 2]

STATS: dict = defaultdict(lambda: {
    "games": 0, "wins": 0, "melee": 0.0, "taken": 0.0, "prim": 0,
    "present": 0, "bodyT": 0.0, "bodyW": 0.0, "bodyn": 0,
    "points": 0.0, "models": 0, "start_hp": 0.0, "surv": 0,
})
_CUR: dict = {"fac": None}
_PAIR: dict = {"A": None, "B": None}
_orig_do_fight = sim.Battle._do_fight


def _wrap_do_fight(self, attacker, attacker_army, defender_army):
    _CUR["fac"] = (attacker.profile.faction or "?") or "?"
    _orig_do_fight(self, attacker, attacker_army, defender_army)


def _rdpa(p) -> float:
    return (getattr(p, "attacks", 0) or 0) * (getattr(p, "hit_probability", 0) or 0) \
        * (getattr(p, "per_shot_damage", 0.0) or 0.0)


class _Sub:
    def on_event(self, e) -> None:
        n = type(e).__name__
        if n == "UnitFought":
            f = _CUR["fac"]
            if f:
                STATS[f]["melee"] += e.damage
        elif n == "ObjectiveScored":
            if _PAIR["A"] and e.a_oc > 0:
                STATS[_PAIR["A"]]["present"] += 1
            if _PAIR["B"] and e.b_oc > 0:
                STATS[_PAIR["B"]]["present"] += 1
            if e.army_name in ("A", "B") and e.vp_awarded:
                STATS[_PAIR[e.army_name]]["prim"] += e.vp_awarded


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    _PAIR["A"], _PAIR["B"] = a_fac, b_fac
    starts = {}
    for letter, fac, army in (("A", a_fac, a), ("B", b_fac, b)):
        st = STATS[fac]
        st["games"] += 1
        st["models"] += len(army.units)
        st["points"] += sum(u.profile.points_cost for u in army.units)
        hp = sum(u.profile.health for u in army.units)
        st["start_hp"] += hp
        starts[letter] = hp
        for u in army.units:
            if _rdpa(u.profile) < 1.5:
                st["bodyT"] += (u.profile.toughness or 0)
                st["bodyW"] += (u.profile.health or 0)
                st["bodyn"] += 1
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    w = Battle(a, b, map_=battle_map, primary_mission=primary, subscribers=[_Sub()]).run().winner
    for letter, fac, army in (("A", a_fac, a), ("B", b_fac, b)):
        st = STATS[fac]
        if w == letter:
            st["wins"] += 1
        end_hp = sum(max(0.0, u.current_health) for u in army.units)
        st["taken"] += starts[letter] - end_hp
        st["surv"] += sum(1 for u in army.units if u.is_alive)


def main() -> None:
    sim.Battle._do_fight = _wrap_do_fight
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
    sim.Battle._do_fight = _orig_do_fight

    print("\nConsolidated faction profile — Astra Militarum vs Orks (both shooty hordes)\n")
    hdr = (f"{'faction':<20}{'win%':>6}{'prim/1k':>8}{'melee/1k':>9}{'taken/1k':>9}"
           f"{'pres/g':>7}{'bodyT':>6}{'bodyW':>6}{'surv%':>7}{'models':>7}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        k = (st["points"] / g / 1000.0) or 1.0
        bn = st["bodyn"] or 1
        tag = "  <==" if fac in HILITE else ""
        print(f"{fac:<20}{100.0 * st['wins'] / g:>6.1f}{st['prim'] / g / k:>8.1f}"
              f"{st['melee'] / g / k:>9.1f}{st['taken'] / g / k:>9.1f}"
              f"{st['present'] / g:>7.1f}{st['bodyT'] / bn:>6.1f}{st['bodyW'] / bn:>6.1f}"
              f"{100.0 * st['surv'] / (st['models'] or 1):>7.1f}{st['models'] / g:>7.1f}{tag}")
    print("\nbodyT/bodyW = mean toughness/wounds of body units (ranged DPA < 1.5). "
          "Compare Astra Militarum vs Orks: same horde shape, but does Orks hold "
          "(durable bodies + melee) where Astra Militarum dies?")


if __name__ == "__main__":
    main()
