"""Threat-field calibration instrument — the substrate falsifier for the
allocation-aware threat field (docs/DECISION_LEDGER.md "ALLOCATION-AWARE
THREAT FIELD" registration).

READ-ONLY. Per unit per enemy turn, compares the threat field's PREDICTED
expected incoming damage against the REALIZED incoming damage, with the same
realized accounting scripts/diag_walked_into_it.py uses:

  * At the boundary where army X's turn ends (detected as a UnitActivated
    army switch — the diag_walked_into_it pattern), snapshot every alive X
    unit: its remaining wounds AND the field's prediction
    _threat_field_at(u, projectors(opponent), u.position, map) — the
    expected wounds the opponent's coming turn projects onto the cell the
    unit stopped in.
  * At the next boundary (the opponent's turn just resolved), realized =
    wounds actually lost, capped at the pool (death caps damage, exactly as
    walked-into-it counts it).
  * Report, per faction: sum(predicted) / sum(realized) — the mean
    predicted-to-realized bias. Two prediction columns: RAW field T, and T
    CAPPED at the unit's remaining wounds (realized is inherently capped by
    death, so the capped column removes the overkill-truncation share of the
    bias and isolates the allocation share).

THE GATE: this tool computes predictions through the live
strategy._threat_field_at, which reads SWEG_THREAT_ALLOC — so running it with
the env unset measures the SUMMED field's bias (the saturation, quantified)
and with SWEG_THREAT_ALLOC=1 the ALLOCATED field's, on IDENTICAL battles (no
decision gate consumes the field on the default path, so the battle
trajectory is byte-identical between the two arms; only the observer's
predictions differ — a clean paired comparison).

Registered falsifier (before any consumer screen): the summed field should
read far above 1 (above 2 expected); the allocated field must land within
[2/3, 3/2] per probe faction.

USAGE
    PYTHONHASHSEED=0 python scripts/diag_threat_calibration.py
    SWEG_THREAT_ALLOC=1 PYTHONHASHSEED=0 python scripts/diag_threat_calibration.py
"""
from __future__ import annotations

import os
import random
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "scripts/diag_threat_calibration.py"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army           # noqa: E402
from code.maps import PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS         # noqa: E402
from code.simulator import Battle                                  # noqa: E402
from code.strategy import _threat_field_at, _threat_projectors     # noqa: E402

# The same eight fixed-seed mixed pairs as scripts/diag_fire_allocation.py.
BATTLES = (
    ("Adeptus Astartes", "Orks", 1),
    ("Necrons", "Tyranids", 2),
    ("Imperial Knights", "Astra Militarum", 3),
    ("Thousand Sons", "Drukhari", 4),
    ("Adeptus Custodes", "World Eaters", 5),
    ("T'au Empire", "Chaos Daemons", 6),
    ("Death Guard", "Aeldari", 7),
    ("Chaos Knights", "Genestealer Cults", 8),
)
POINTS_BUDGET = 2000


class ThreatCalibrationObserver:
    """Snapshot-and-realize at every turn boundary, walked-into-it style,
    with the field prediction recorded at snapshot time."""

    def __init__(self, battle: Battle) -> None:
        self.battle = battle
        self.current_army = None
        # army_name -> {uid: (h0, faction, predicted_raw, predicted_capped)}
        self.snapshots: dict = {}
        # faction -> [n, sum_pred_raw, sum_pred_capped, sum_realized]
        self.tally: dict = defaultdict(lambda: [0, 0.0, 0.0, 0.0])

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
        # Realize `nxt`'s snapshot: its units sat exposed through `prev`'s
        # just-ended turn.
        snap = self.snapshots.get(nxt)
        if snap:
            for uid, (h0, fac, p_raw, p_cap) in snap.items():
                if h0 <= 1e-9:
                    continue
                u = units.get(uid)
                cur = u.current_health if u is not None else 0.0
                realized = min(h0, max(0.0, h0 - cur))
                t = self.tally[fac]
                t[0] += 1
                t[1] += p_raw
                t[2] += p_cap
                t[3] += realized
        # Snapshot `prev`: it just finished its turn; its units now sit
        # exposed through `nxt`'s coming turn. Predict at the stopped cell.
        prev_army = (self.battle.a if self.battle.a.name == prev
                     else self.battle.b)
        opp_army = (self.battle.b if prev_army is self.battle.a
                    else self.battle.a)
        projectors = _threat_projectors(opp_army)
        new_snap = {}
        for u in prev_army.alive_units:
            pred = _threat_field_at(u, projectors, u.position,
                                    self.battle.map)
            new_snap[u.uid] = (u.current_health, u.profile.faction, pred,
                               min(pred, u.current_health))
        self.snapshots[prev] = new_snap


def main() -> int:
    mode = ("ALLOCATED (SWEG_THREAT_ALLOC=1)"
            if os.environ.get("SWEG_THREAT_ALLOC") == "1" else
            "SUMMED (gate unset)")
    tally = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for (fa, fb, seed) in BATTLES:
        random.seed(seed)
        a = build_faction_random_army("A", fa, POINTS_BUDGET,
                                      rng=random.Random(seed),
                                      use_archetype=True)
        b = build_faction_random_army("B", fb, POINTS_BUDGET,
                                      rng=random.Random(seed + 10000),
                                      use_archetype=True)
        map_key = PARIAH_NEXUS_2K_ROTATION[seed % len(PARIAH_NEXUS_2K_ROTATION)]
        battle = Battle(a, b, map_=STOCK_MAPS[map_key])
        obs = ThreatCalibrationObserver(battle)
        battle.subscribers.append(obs)
        battle.run()
        for fac, row in obs.tally.items():
            t = tally[fac]
            for i in range(4):
                t[i] += row[i]

    print("threat-field calibration — %d fixed-seed battles, %d points, "
          "use_archetype=True" % (len(BATTLES), POINTS_BUDGET))
    print("field mode: %s" % mode)
    print("(per unit per enemy turn: field-predicted incoming at the cell the")
    print(" unit stopped in, versus realized wounds lost that enemy turn —")
    print(" the walked-into-it accounting. ratio = sum(pred)/sum(realized);")
    print(" 'capped' clips each prediction at the unit's remaining wounds,")
    print(" removing the overkill-truncation share of the bias)\n")
    hdr = (f"  {'faction':22s} {'unit-turns':>10s} {'pred/real RAW':>14s} "
           f"{'pred/real CAPPED':>17s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for fac in sorted(tally):
        n, p_raw, p_cap, real = tally[fac]
        r_raw = p_raw / real if real > 0 else float("inf")
        r_cap = p_cap / real if real > 0 else float("inf")
        print(f"  {fac:22s} {n:10d} {r_raw:14.2f} {r_cap:17.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
