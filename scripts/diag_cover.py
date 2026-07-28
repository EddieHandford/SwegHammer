"""Cover-deniability measurement (#88) — is the melee over-pole partly a cover
asymmetry the sim cannot deny?

Cover in the sim is ranged-only (+1 save) and positional/angle-independent
(`cover_at(target.position)`), and the movement AI hugs cover. So a defender
standing in terrain is taxing every shot fired at it, and NO amount of shooter
outpositioning can strip that cover — there is no angle/line-of-fire model. If
the melee over-pole (Death Guard / World Eaters / Emperor's Children / Chaos
Daemons) advance through cover, their bodies enjoy this undeniable +1 while their
own melee bypasses cover entirely — a structural one-way tax.

This instrument quantifies it. With SWEG_COVER_INSTR on, every ranged shooting
activation records, by ATTACKER faction and by DEFENDER faction:
  * shots         — shooting activations that reached a valid target
  * cover%        — share of those whose target stood in terrain cover
  * out / cover%out — shooting OUTPUT (attacks×hit×dmg) and the share landing
                    into cover (the actual +1-save tax weight)
  * L/H/R         — terrain split of covered shots (light / heavy / ruin)

Read:
  * by DEFENDER — do the melee over-pole get shot into cover MORE than the shooty
    factions (Astra Militarum / T'au) do? If their cover%out is markedly higher,
    the over-pole partly rides an undeniable cover tax → angle-dependent-cover
    build is justified.
  * by ATTACKER — are Astra Militarum / T'au firing a high share of output into
    cover (taxed shooters)? Uniform/low everywhere → the lead dies, cover is a
    faithful symmetric tax and no build is warranted.

Serial run (NOT ProcessPoolExecutor) so COVER_STATS aggregates in-process.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_cover

RESULT (2026-06-15, lead REFUTED — instrument reverted, tree kept clean).
Cover is a real but SYMMETRIC ~46% tax, not the asymmetry the lead needed:
  by DEFENDER cov%out — over-pole mean 46.5% (DG 53.3 / WE 43.7 / EC 48.0 /
  Daemons 41.0) vs field mean 46.1% (AM 42.1 / T'au 49.4 / Orks 50.8 /
  Custodes 45.8 / Knights 42.3). The melee over-pole are NOT shot into cover
  more than anyone else — WE and Daemons sit BELOW the field; shooty Orks and
  T'au sit ABOVE it; under-pole AM sits dead-centre.
  by ATTACKER cov%out — AM 51.0 is modestly high but T'au (the other gunline)
  is 43.9, below field: if a cover-tax-on-shooters drove the under-pole both
  would be high together; they split.
An angle-dependent-cover + shooter-outpositioning build would strip cover from
all huggers and lift all shooters roughly uniformly, so by closed-matrix logic
it does NOT move the relative win rates the gated MAE measures. Lead dead.
To re-run, re-add the SWEG_COVER_INSTR block + COVER_STATS global (reverted).
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_cover"], os.environ)

import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import code.simulator as sim
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + ["Astra Militarum", "T'au Empire", "Orks",
                     "Adeptus Custodes", "Imperial Knights"]
SEEDS = [0, 1, 2]


def _play(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary).run()


def _row(fac: str, d: dict) -> str:
    shots = d["shots"] or 1
    out = d["out"] or 1.0
    cov = 100.0 * d["cover_shots"] / shots
    covo = 100.0 * d["cover_out"] / out
    return (f"{fac:<20}{d['shots']:>7}{cov:>8.1f}{out:>10.0f}{covo:>9.1f}"
            f"{d['light']:>6}{d['heavy']:>6}{d['ruin']:>6}")


def main() -> None:
    os.environ["SWEG_COVER_INSTR"] = "1"
    sim.COVER_STATS.clear()
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _play(a_fac, b_fac, s)
    os.environ["SWEG_COVER_INSTR"] = "0"

    hdr = (f"{'faction':<20}{'shots':>7}{'cover%':>8}{'out':>10}{'cov%out':>9}"
           f"{'L':>6}{'H':>6}{'R':>6}")
    for title, key in (("BY DEFENDER (who gets shot into cover)", "def"),
                       ("BY ATTACKER (whose shots land into cover)", "att")):
        print(f"\n{title}\n")
        print(hdr)
        print("-" * len(hdr))
        bucket = sim.COVER_STATS.get(key, {})
        for fac in PANEL:
            d = bucket.get(fac)
            if not d:
                continue
            tag = "  OVER" if fac in OVER_POLE else (
                "  UNDER" if fac == "Astra Militarum" else "")
            print(_row(fac, d) + tag)
    print("\ncov%out = share of shooting OUTPUT (attacks×hit×dmg) landing into a "
          "covered target = the +1-save tax weight. High & over-pole-skewed on the "
          "DEFENDER side = undeniable cover asymmetry; uniform = faithful symmetric tax.")


if __name__ == "__main__":
    main()
