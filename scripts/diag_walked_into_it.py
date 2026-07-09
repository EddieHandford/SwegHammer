"""Walked-into-it instrument — the falsifier for the threat-projection layer.

READ-ONLY. Measures, per faction and per game, how often a unit ENDS one of its
activations in a cell whose realized next-turn incoming damage was lethal — the
"walked into it" rate the threat layer (docs/THREAT_LAYER_PROPOSAL.md) exists to
reduce. Requires NO simulator changes and NO gate: it subscribes to the ordinary
event stream and reads the live army objects at turn boundaries.

Method (realized, not predicted — so the number stays an honest falsifier rather
than a re-reading of the layer's own prediction):
  * The vanilla 10e turn order is I-go-you-go; a turn boundary is detected when
    the activating army changes (UnitActivated.army_name).
  * At the END of army X's turn, snapshot every alive X unit's remaining wounds
    and the cell it finished in.
  * During the opponent's very next turn, X's units may be shot / charged. At the
    end of that opponent turn, a snapshotted unit that lost ALL its remaining
    wounds (i.e. was destroyed — damage in the health model is capped at the
    wound pool, so "incoming exceeds remaining wounds" is realized as death in
    the cell it stopped in) is counted as a walked-into-it event.
Also reports a softer exposure gauge: the mean fraction of remaining wounds each
end-of-turn unit lost on the opponent's next turn (near-lethal cells included).

Usage:
  python -m scripts.diag_walked_into_it                       # default faction set
  python -m scripts.diag_walked_into_it --factions "World Eaters,Chaos Daemons,T'au Empire"
  python -m scripts.diag_walked_into_it --seeds 3,4,5 --points 2000
The threat-layer gates (SWEG_THREAT_CHARGE etc.) may be set in the environment to
measure the rate WITH the layer on; unset (the default) it reports the baseline.
"""
from __future__ import annotations

import argparse
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.maps import STOCK_MAPS, PARIAH_NEXUS_2K_ROTATION
from code.simulator import Battle

# Default opponents faced by each measured faction — a fixed varied slate so the
# baseline is comparable across the measured factions (each sees the same mix).
DEFAULT_FACTIONS = ("World Eaters", "Chaos Daemons", "T'au Empire")
OPPONENT_SLATE = ("Astra Militarum", "Adeptus Astartes", "Necrons")


class WalkedIntoItObserver:
    """Event subscriber that tallies walked-into-it events per faction.

    Holds the live Battle so it can read `current_health` directly at each turn
    boundary; the event stream is used only to detect boundaries (army switches).
    """

    def __init__(self, battle: Battle) -> None:
        self.battle = battle
        self.current_army = None
        # army_name -> {uid: (remaining_wounds_at_turn_end, faction)}
        self.snapshots: dict = {}
        self.walked: dict = defaultdict(int)          # faction -> lethal-cell count
        self.ended: dict = defaultdict(int)           # faction -> end-of-turn positionings
        self.exposure_sum: dict = defaultdict(float)  # faction -> sum of lost-wound fractions

    def _live_units(self) -> dict:
        out = {}
        for u in list(self.battle.a.units) + list(self.battle.b.units):
            out[u.uid] = u
        return out

    def on_event(self, ev) -> None:
        if type(ev).__name__ != "UnitActivated":
            return
        army = ev.army_name
        if self.current_army is not None and army != self.current_army:
            self._turn_boundary(prev=self.current_army, nxt=army)
        self.current_army = army

    def _turn_boundary(self, prev: str, nxt: str) -> None:
        units = self._live_units()
        # Finalise `nxt`'s snapshot: its units sat exposed through `prev`'s
        # just-ended turn. Measure the damage they took.
        snap = self.snapshots.get(nxt)
        if snap:
            for uid, (h0, fac) in snap.items():
                if h0 <= 1e-9:
                    continue
                u = units.get(uid)
                cur = u.current_health if u is not None else 0.0
                dmg = max(0.0, h0 - cur)
                self.ended[fac] += 1
                self.exposure_sum[fac] += min(1.0, dmg / h0)
                if dmg >= h0 - 1e-9:      # lost every remaining wound -> lethal cell
                    self.walked[fac] += 1
        # Snapshot `prev`: it just finished its turn and will be exposed during
        # `nxt`'s upcoming turn.
        prev_army = self.battle.a if self.battle.a.name == prev else self.battle.b
        self.snapshots[prev] = {
            u.uid: (u.current_health, u.profile.faction)
            for u in prev_army.alive_units
        }


def _run(fac_a: str, fac_b: str, seed: int, points: float,
         obs_accumulator: "WalkedIntoItObserver | None" = None) -> WalkedIntoItObserver:
    a = build_faction_random_army("A", fac_a, points,
                                  rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", fac_b, points,
                                  rng=random.Random(seed + 10000), use_archetype=True)
    map_key = PARIAH_NEXUS_2K_ROTATION[seed % len(PARIAH_NEXUS_2K_ROTATION)]
    battle = Battle(a, b, map_=STOCK_MAPS[map_key])
    obs = WalkedIntoItObserver(battle)
    battle.subscribers.append(obs)
    battle.run()
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

    # faction -> aggregated counters across every game it appeared in
    agg_walked = defaultdict(int)
    agg_ended = defaultdict(int)
    agg_expo = defaultdict(float)
    games = defaultdict(int)

    for fac in factions:
        for i, opp in enumerate(OPPONENT_SLATE):
            for seed in seeds:
                # both army orders so the rate is not deployment-zone biased
                for a_fac, b_fac in ((fac, opp), (opp, fac)):
                    obs = _run(a_fac, b_fac, seed + 100 * i, args.points)
                    for f in (a_fac, b_fac):
                        if f != fac:
                            continue
                        agg_walked[fac] += obs.walked[f]
                        agg_ended[fac] += obs.ended[f]
                        agg_expo[fac] += obs.exposure_sum[f]
                    games[fac] += 1

    print(f"factions: {factions}")
    print(f"opponents: {list(OPPONENT_SLATE)}   seeds: {seeds}   points: {args.points:.0f}")
    print(f"(both army orders; {sum(games.values())} games total)\n")
    hdr = (f"  {'faction':18s} {'games':>5s} {'walked/game':>12s} "
           f"{'end-turns/game':>15s} {'walked-rate':>12s} {'exposure':>9s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for fac in factions:
        g = max(1, games[fac])
        e = max(1, agg_ended[fac])
        print(f"  {fac:18s} {games[fac]:5d} "
              f"{agg_walked[fac] / g:12.2f} "
              f"{agg_ended[fac] / g:15.2f} "
              f"{agg_walked[fac] / e:12.3f} "
              f"{agg_expo[fac] / e:9.3f}")
    print("\nReading: 'walked/game' = units per game that ended an activation and were")
    print("dead by the end of the opponent's next turn (the realized falsifier). ")
    print("'walked-rate' = that as a fraction of all end-of-turn positionings; ")
    print("'exposure' = mean fraction of remaining wounds lost on the next enemy turn.")
    print("The threat layer must REDUCE walked/game and walked-rate.")


if __name__ == "__main__":
    main()
