"""Causal A/B validation of the deep-strike-alpha hypothesis — ONE-SIDED.

The earlier both-sides toggle confounded "my alpha gone" with "opponent's alpha
gone". This isolates each faction's OWN alpha: per pairing + seed, three arms with
identical CRN army builds —
  arm0: all alpha ON (baseline, SWEG_FORCE_ONBOARD=0)
  armA: only a_fac forced on-board (a's alpha OFF, b normal)
  armB: only b_fac forced on-board (b's alpha OFF, a normal)
For faction F, compare F's win rate at baseline to F's win rate in the arm where
ONLY F lost its alpha (opponents unchanged).

Hypothesis CONFIRMED for F iff F's win rate DROPS sharply when only F's alpha is
removed. A flat/positive delta means F's over-pole is not its deep-strike alpha.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_ds_ab
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_ds_ab"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + [
    "Astra Militarum", "Imperial Knights", "Adeptus Custodes",
    "Adeptus Astartes", "T'au Empire",
]
SEEDS = [0, 1, 2, 3]   # N = 8 opponents x 2 positions x 4 seeds = 64 games / faction

# per faction: games, baseline wins, wins when ONLY this faction's alpha is off
STATS: dict = defaultdict(lambda: {"games": 0, "base_win": 0, "self_off_win": 0})


def _play(a_fac: str, b_fac: str, s: int, force: str) -> str:
    os.environ["SWEG_FORCE_ONBOARD"] = force
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return "skip"
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    return Battle(a, b, map_=battle_map, primary_mission=primary).run().winner


def _run_pair(a_fac: str, b_fac: str, s: int) -> None:
    w0 = _play(a_fac, b_fac, s, "0")        # baseline, all alpha on
    wa = _play(a_fac, b_fac, s, a_fac)      # only a_fac's alpha off
    wb = _play(a_fac, b_fac, s, b_fac)      # only b_fac's alpha off
    if "skip" in (w0, wa, wb):
        return
    sa = STATS[a_fac]
    sa["games"] += 1
    sa["base_win"] += (w0 == "A")
    sa["self_off_win"] += (wa == "A")
    sb = STATS[b_fac]
    sb["games"] += 1
    sb["base_win"] += (w0 == "B")
    sb["self_off_win"] += (wb == "B")


def main() -> None:
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_pair(a_fac, b_fac, s)
                n += 1
    os.environ["SWEG_FORCE_ONBOARD"] = "0"

    print(f"\nDeep-strike-alpha A/B (ONE-SIDED, paired) — {n} pairings x 3 arms\n")
    hdr = (f"{'faction':<20}{'games':>6}{'win% base':>11}{'win% ownDSoff':>15}{'delta':>8}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        base = 100.0 * st["base_win"] / g
        off = 100.0 * st["self_off_win"] / g
        tag = "  <-- OVER-POLE" if fac in OVER_POLE else ""
        print(f"{fac:<20}{st['games']:>6}{base:>11.1f}{off:>15.1f}{off - base:>+8.1f}{tag}")
    print("\nwin% base = all alpha on; win% ownDSoff = only THIS faction's deep-strike "
          "disabled (opponents unchanged); delta = ownDSoff minus base. Hypothesis "
          "CONFIRMED for a faction iff its delta is strongly NEGATIVE (it needs the "
          "alpha to win). ~+-12% CI at N=64.")


if __name__ == "__main__":
    main()
