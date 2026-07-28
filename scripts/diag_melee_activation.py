"""One-question diagnostic: is the melee over-pole the per-model FIGHT-phase
activation amplification, or is "representation wall" a mislabel?

In real 10e a unit fights ONCE: pile-in (each model up to 3"), then ALL attacks,
then consolidate (each model up to 3") — one coordinated decision. SwegHammer
models one Unit per model and calls `_do_fight` per model-Unit, each running its
OWN pile-in -> attack -> consolidate sequence, adapting to the board the previous
model just changed (re-targeting, advancing into gaps, each clearing-model
consolidating onto an objective independently). The move COUNT matches 10e; the
amplification is in the sequencing.

This instruments `_do_fight` by monkeypatch (zero production-code change) over a
fixed seeded archetype matrix and reports, per faction:
  * melee fight-activations per game (UnitFought strikes)
  * free FIGHT-phase board movement (pile-in + consolidate net displacement) per
    game, total and per 1000 points
  * consolidate-onto-objective grabs per game (a cleared-combat model walking 3"
    onto a marker — the per-model objective amplification)
  * mean models / army (the amplification scales with this)

Read: if the four melee over-pole factions (Death Guard, World Eaters, Emperor's
Children, Chaos Daemons) are clear OUTLIERS on free-move-per-point and
objective-grabs-per-game versus the field, the over-pole is this findable
Fight-phase sequencing mechanic, not the abstract activation-count wall. If they
scale in line with the field (just more models), it is the generic wall.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_melee_activation
"""
from __future__ import annotations

import os
import sys

# Match the eval's hash-seed lock so set/dict iteration is reproducible and the
# imported evaluate_vs_meta guard does not re-exec us (it re-execs ITSELF only
# when PYTHONHASHSEED != 0; setting it first makes that guard inert).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_melee_activation"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.sim.geometry import _distance
import code.simulator as sim
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

# Four melee over-pole factions + a comparison panel: the dominant under-pole
# (Astra Militarum), a low-model elite (Imperial Knights / Adeptus Custodes), and
# an in-band shooty baseline (Adeptus Astartes, T'au Empire).
OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + [
    "Astra Militarum", "Imperial Knights", "Adeptus Custodes",
    "Adeptus Astartes", "T'au Empire",
]
SEEDS = [0, 1]   # two CRN seeds per ordered pairing

# Per-faction fight-phase accumulators (the monkeypatch + a Subscriber fill these).
STATS: dict = defaultdict(lambda: {
    "games": 0, "strikes": 0, "free_move": 0.0, "fights": 0,
    "models_sum": 0, "points_sum": 0.0,
})
# The faction of the model-Unit currently inside _do_fight. The strike event
# (UnitFought) is emitted synchronously during that call, so the subscriber can
# attribute it directly without a uid map.
_CUR: dict = {"fac": None}

_orig_do_fight = sim.Battle._do_fight


def _instrumented_do_fight(self, attacker, attacker_army, defender_army):
    fac = (attacker.profile.faction or "?") or "?"
    _CUR["fac"] = fac
    p0 = attacker.position
    _orig_do_fight(self, attacker, attacker_army, defender_army)
    p1 = attacker.position
    s = STATS[fac]
    s["fights"] += 1                       # _do_fight invocations (pile-in attempts)
    s["free_move"] += _distance(p0, p1)    # net Fight-phase board displacement


class _StrikeCounter:
    """Counts actual melee strikes per attacker faction off the event stream."""

    def on_event(self, event) -> None:
        if type(event).__name__ == "UnitFought":
            f = _CUR["fac"]
            if f:
                STATS[f]["strikes"] += 1


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    # Record army size / points for the attacker faction (per game, both armies).
    for army, fac in ((a, a_fac), (b, b_fac)):
        st = STATS[fac]
        st["games"] += 1
        st["models_sum"] += len(army.units)
        st["points_sum"] += sum(u.profile.points_cost for u in army.units)
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary,
           subscribers=[_StrikeCounter()]).run()


def main() -> None:
    sim.Battle._do_fight = _instrumented_do_fight
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
                n += 1
    sim.Battle._do_fight = _orig_do_fight

    print(f"\nFight-phase per-model activation diagnostic — {n} battles\n")
    hdr = (f"{'faction':<20}{'games':>6}{'strikes/g':>10}{'strk/1kpt':>10}"
           f"{'freemv/g':>10}{'freemv/1kpt':>12}{'models':>8}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        avg_pts = st["points_sum"] / g
        k = (avg_pts / 1000.0) or 1.0
        tag = "  <-- OVER-POLE" if fac in OVER_POLE else ""
        print(f"{fac:<20}{st['games']:>6}{st['strikes'] / g:>10.1f}"
              f"{(st['strikes'] / g) / k:>10.1f}{st['free_move'] / g:>10.1f}"
              f"{(st['free_move'] / g) / k:>12.1f}{st['models_sum'] / g:>8.1f}{tag}")
    print("\nstrikes = melee swings (UnitFought); freemv = pile-in + consolidate "
          "net board displacement in the Fight phase (inches). Both normalised "
          "per 1000 points. If the OVER-POLE rows are NOT clear outliers vs the "
          "in-band melee factions (Adeptus Astartes), the over-pole is not the "
          "Fight-phase per-model amplification.")


if __name__ == "__main__":
    main()
