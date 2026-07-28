"""Follow-up diagnostic: what distinguishes the four melee OVER-POLE factions
from in-band Adeptus Astartes (same Fight-phase per-model footprint, correctly
rated)? And does the over-pole face the melee COUNTERPLAY a real opponent would?

`scripts/diag_melee_activation.py` ruled out per-model Fight-phase activation as
the over-pole cause. This measures the next layer, per faction (no uid map — all
attribution is from the unit object in hand or a whole-army health snapshot):

  * melee damage DEALT per 1000 pts  (offensive output)
  * total damage TAKEN per 1000 pts  (durability + attrition the opponent lands)
  * melee exchange ratio = dealt / taken  (how lopsided the melee trade is)
  * COUNTERPLAY the faction's melee FACES, per game:
      - overwatch_against : times the opponent fired Fire Overwatch at this
        faction's chargers (`_fire_overwatch`, SWEG_OVERWATCH default-on)
      - fallback_against  : times an enemy model chose FALL_BACK to disengage
        from this faction's melee (`pick_move_intent` -> "FALL_BACK")

Read: if the over-pole factions deal similar melee to Adeptus Astartes but TAKE
much less / trade far more lopsidedly, the discriminator is durability, not
output. If they ALSO face much less fall-back / overwatch counterplay than the
field, the over-pole is partly missing/under-fired melee counterplay — a faithful
AI lever, not a representation wall.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_melee_counterplay
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_melee_counterplay"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
import code.simulator as sim
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + [
    "Astra Militarum", "Imperial Knights", "Adeptus Custodes",
    "Adeptus Astartes", "T'au Empire",
]
SEEDS = [0, 1]

STATS: dict = defaultdict(lambda: {
    "games": 0, "melee_dealt": 0.0, "dmg_taken": 0.0,
    "overwatch_against": 0, "fallback_against": 0,
    "points_sum": 0.0, "models_sum": 0,
})
_CUR: dict = {"fac": None}          # faction of the model currently in _do_fight
_PAIR: dict = {"a": None, "b": None}  # the two factions in the current battle

_orig_do_fight = sim.Battle._do_fight
_orig_overwatch = sim.Battle._fire_overwatch
_orig_pmi = sim.pick_move_intent


def _wrap_do_fight(self, attacker, attacker_army, defender_army):
    _CUR["fac"] = (attacker.profile.faction or "?") or "?"
    _orig_do_fight(self, attacker, attacker_army, defender_army)


def _wrap_overwatch(self, defending_army, enemy_unit):
    fac = (enemy_unit.profile.faction or "?") or "?"
    STATS[fac]["overwatch_against"] += 1
    _orig_overwatch(self, defending_army, enemy_unit)


def _wrap_pmi(unit, friendly, enemy, *a, **k):
    res = _orig_pmi(unit, friendly, enemy, *a, **k)
    if res and res[1] == "FALL_BACK":
        f = (unit.profile.faction or "?") or "?"
        threat = _PAIR["b"] if f == _PAIR["a"] else _PAIR["a"]
        if threat:
            STATS[threat]["fallback_against"] += 1
    return res


class _Counter:
    def on_event(self, event) -> None:
        if type(event).__name__ == "UnitFought":
            f = _CUR["fac"]
            if f:
                STATS[f]["melee_dealt"] += event.damage


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    _PAIR["a"], _PAIR["b"] = a_fac, b_fac
    a_start = sum(u.profile.health for u in a.units)
    b_start = sum(u.profile.health for u in b.units)
    for army, fac in ((a, a_fac), (b, b_fac)):
        st = STATS[fac]
        st["games"] += 1
        st["models_sum"] += len(army.units)
        st["points_sum"] += sum(u.profile.points_cost for u in army.units)
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary, subscribers=[_Counter()]).run()
    STATS[a_fac]["dmg_taken"] += a_start - sum(max(0.0, u.current_health) for u in a.units)
    STATS[b_fac]["dmg_taken"] += b_start - sum(max(0.0, u.current_health) for u in b.units)


def main() -> None:
    sim.Battle._do_fight = _wrap_do_fight
    sim.Battle._fire_overwatch = _wrap_overwatch
    sim.pick_move_intent = _wrap_pmi
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
                n += 1
    sim.Battle._do_fight = _orig_do_fight
    sim.Battle._fire_overwatch = _orig_overwatch
    sim.pick_move_intent = _orig_pmi

    print(f"\nMelee discriminator + counterplay diagnostic — {n} battles\n")
    hdr = (f"{'faction':<20}{'mlDealt/1k':>11}{'dmgTaken/1k':>12}{'exch':>7}"
           f"{'ovw/g':>7}{'fallbk/g':>9}{'models':>8}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        k = (st["points_sum"] / g / 1000.0) or 1.0
        dealt = st["melee_dealt"] / g / k
        taken = st["dmg_taken"] / g / k
        exch = (st["melee_dealt"] / st["dmg_taken"]) if st["dmg_taken"] else 0.0
        tag = "  <-- OVER-POLE" if fac in OVER_POLE else ""
        print(f"{fac:<20}{dealt:>11.1f}{taken:>12.1f}{exch:>7.2f}"
              f"{st['overwatch_against'] / g:>7.2f}{st['fallback_against'] / g:>9.2f}"
              f"{st['models_sum'] / g:>8.1f}{tag}")
    print("\nmlDealt/1k = melee damage dealt per 1000 pts; dmgTaken/1k = total "
          "damage absorbed per 1000 pts; exch = melee dealt / total taken; ovw/g = "
          "opponent Fire Overwatch firings at this faction's chargers per game; "
          "fallbk/g = enemy FALL_BACK disengages from this faction's melee per game. "
          "Compare OVER-POLE to Adeptus Astartes (in-band, same melee footprint).")


if __name__ == "__main__":
    main()
