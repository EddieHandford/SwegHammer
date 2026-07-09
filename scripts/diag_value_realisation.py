"""Value-realisation instrument — the falsifier for the value field (Layer A).

READ-ONLY. Measures, per faction and per game, the fraction of a faction's
END-of-round marker control that its ROUND-START value-ranked destinations
predicted. This is the behavioural falsifier docs/LAYERS_RESEARCH.md §A(f)
demands: the value field must RAISE value-realisation (units end up controlling
the markers their value ranking pointed them at), independently of whether the
headline mean absolute error moves. Requires NO simulator changes: it subscribes
to the ordinary event stream and reads the live army objects at round boundaries,
and it computes its predictions with the SAME value-field ranking the
SWEG_VALUE_MOVE consumer uses (strategy.value_top_marker_index).

Method (predict at round start, check against realised end-round control):
  * The battle-round counter (battle._current_round) advances at the top of each
    round, before any movement. A round boundary is detected when it changes on a
    UnitActivated event.
  * At the FIRST activation of round R (positions are still round-start), snapshot
    each alive unit's top value-ranked objective marker — the faction's PREDICTED
    marker set for round R.
  * When the round advances to R+1 (or the battle ends), the board is as it ended
    round R (nobody has moved in R+1 yet), so battle._objective_controllers()
    gives the REALISED control for round R. For each faction:
        realisation_R = |predicted_R  intersect  realised_R| / |realised_R|
    (rounds where the faction controls no marker are skipped — nothing to realise).

Run it once with the gate UNSET (baseline: does the value ranking predict where
legacy movement ends up controlling?) and once with SWEG_VALUE_MOVE=1 (the layer
routing movement by that same ranking). The layer must raise the realisation rate.

Usage:
  python -m scripts.diag_value_realisation                       # default faction set, baseline
  SWEG_VALUE_MOVE=1 python -m scripts.diag_value_realisation      # with the layer on
  python -m scripts.diag_value_realisation --factions "Astra Militarum,Death Guard,Orks"
  python -m scripts.diag_value_realisation --seeds 3,4,5 --points 2000
"""
from __future__ import annotations

import argparse
import os
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.maps import STOCK_MAPS, PARIAH_NEXUS_2K_ROTATION
from code.simulator import Battle
from code.strategy import value_top_marker_index

# Default measured factions — the two dominant error poles plus a mobile army —
# and a fixed varied opponent slate so the baseline is comparable across them.
DEFAULT_FACTIONS = ("Astra Militarum", "Death Guard", "Orks")
OPPONENT_SLATE = ("Adeptus Astartes", "Necrons", "T'au Empire")


class ValueRealisationObserver:
    """Event subscriber that tallies value-realisation per faction.

    Holds the live Battle so it can read positions / control directly at each
    round boundary; the event stream is used only to detect boundaries (the
    battle-round counter advancing).
    """

    def __init__(self, battle: Battle) -> None:
        self.battle = battle
        self.cur_round = 0
        # faction -> summed realisation ratio, and count of contributing rounds
        self.realised_sum: dict = defaultdict(float)
        self.rounds_counted: dict = defaultdict(int)
        # pending predictions for the round in progress: faction -> set(obj_idx)
        self._predicted: dict = {}

    def _army_faction(self, army) -> str:
        return (army.units[0].profile.faction if army.units else "?") or "?"

    def _predict_round(self) -> None:
        """Snapshot each alive unit's top value-ranked marker (round-start
        positions) into the per-faction predicted set."""
        self._predicted = {}
        for army, enemy in ((self.battle.a, self.battle.b),
                            (self.battle.b, self.battle.a)):
            fac = self._army_faction(army)
            pred = self._predicted.setdefault(fac, set())
            for u in army.alive_units:
                idx = value_top_marker_index(u, army, enemy, self.battle.map)
                if idx is not None:
                    pred.add(idx)

    def _finalise_round(self) -> None:
        """The board is as it ended the just-finished round: compare each
        faction's realised control against its round-start predictions."""
        if not self._predicted:
            return
        controllers = self.battle._objective_controllers()   # {idx: 'a'/'b'/None}
        fac_a = self._army_faction(self.battle.a)
        fac_b = self._army_faction(self.battle.b)
        realised: dict = defaultdict(set)
        for idx, who in controllers.items():
            if who == "a":
                realised[fac_a].add(idx)
            elif who == "b":
                realised[fac_b].add(idx)
        for fac, pred in self._predicted.items():
            got = realised.get(fac, set())
            if not got:
                continue      # controlled nothing this round — nothing to realise
            self.realised_sum[fac] += len(pred & got) / len(got)
            self.rounds_counted[fac] += 1

    def on_event(self, ev) -> None:
        if type(ev).__name__ != "UnitActivated":
            return
        r = self.battle._current_round
        if r != self.cur_round:
            # Round boundary: finalise the round that just ended, then predict
            # the new one from its round-start positions.
            if self.cur_round >= 1:
                self._finalise_round()
            self.cur_round = r
            self._predict_round()

    def close(self) -> None:
        """Finalise the last round at battle end (final board = its end state)."""
        if self.cur_round >= 1:
            self._finalise_round()


def _run(fac_a: str, fac_b: str, seed: int, points: float) -> ValueRealisationObserver:
    a = build_faction_random_army("A", fac_a, points,
                                  rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", fac_b, points,
                                  rng=random.Random(seed + 10000), use_archetype=True)
    map_key = PARIAH_NEXUS_2K_ROTATION[seed % len(PARIAH_NEXUS_2K_ROTATION)]
    battle = Battle(a, b, map_=STOCK_MAPS[map_key])
    obs = ValueRealisationObserver(battle)
    battle.subscribers.append(obs)
    battle.run()
    obs.close()
    return obs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--factions", default=",".join(DEFAULT_FACTIONS),
                    help="comma-separated factions to measure")
    ap.add_argument("--seeds", default="3,4,5",
                    help="comma-separated integer seeds")
    ap.add_argument("--points", type=float, default=2000.0)
    args = ap.parse_args()

    factions = [f.strip() for f in args.factions.split(",") if f.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    agg_sum = defaultdict(float)
    agg_rounds = defaultdict(int)
    games = defaultdict(int)

    for fac in factions:
        for i, opp in enumerate(OPPONENT_SLATE):
            for seed in seeds:
                # both army orders so the rate is not deployment-zone biased
                for a_fac, b_fac in ((fac, opp), (opp, fac)):
                    obs = _run(a_fac, b_fac, seed + 100 * i, args.points)
                    if fac in obs.realised_sum or fac in obs.rounds_counted:
                        agg_sum[fac] += obs.realised_sum.get(fac, 0.0)
                        agg_rounds[fac] += obs.rounds_counted.get(fac, 0)
                    games[fac] += 1

    gate = "ON (SWEG_VALUE_MOVE=1)" if os.environ.get("SWEG_VALUE_MOVE") == "1" else "OFF (baseline)"
    print(f"factions: {factions}")
    print(f"opponents: {list(OPPONENT_SLATE)}   seeds: {seeds}   points: {args.points:.0f}")
    print(f"value-move gate: {gate}")
    print(f"(both army orders; {sum(games.values())} games total)\n")
    hdr = (f"  {'faction':18s} {'games':>5s} {'scored-rounds':>13s} "
           f"{'value-realisation':>18s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for fac in factions:
        rr = max(1, agg_rounds[fac])
        print(f"  {fac:18s} {games[fac]:5d} "
              f"{agg_rounds[fac]:13d} "
              f"{agg_sum[fac] / rr:18.3f}")
    print("\nReading: 'value-realisation' = mean over scored rounds of")
    print("(markers the faction both PREDICTED at round start AND controlled at round end)")
    print("/ (markers it controlled at round end). The value field must RAISE this rate")
    print("gate-on vs baseline; if it does not, the layer is fidelity-only, not a realiser.")


if __name__ == "__main__":
    main()
