"""Causal A/B for SWEG_SCREEN_AI (#88 screening lever): does a defensive
screening move-AI raise the gunline under-pole (Astra Militarum the dominant
case) and, via the closed pairwise matrix, pull the melee over-pole down?

The substrate already supports screening: SWEG_CHARGE_PATH (default ON) makes a
non-FLY charger DROP any target whose approach passes within Engagement Range of
a non-target enemy. That is the offensive half — a charger respects a screen
that happens to be there. The missing half is defensive: no unit MOVES to create
the block. SWEG_SCREEN_AI adds a "SCREEN" move intent — a cheap INFANTRY body
interposes on the charge lane between a threatening enemy melee unit and a
valuable friendly gun/character.

Per gunline×melee pairing + seed, two arms with IDENTICAL common-random-number
army builds: OFF (production) vs ON (SWEG_SCREEN_AI=1). Measures each faction's
win rate in both arms, and counts how many SCREEN intents actually fire in the ON
arm (per faction) — an inert lever fires zero and the question dies cheaply.

CONFIRMED if the gunlines (esp. Astra Militarum) gain win% AND the melee factions
drop (closed matrix). WASH if the gunlines don't move — then screening, like the
four prior AI levers, cannot beat the off-table durability-in-contest wall, and
the on-table lever family is fully exhausted.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_screen_ab

RESULT (2026-06-15, lever REJECTED — code reverted, OFF byte-identical proven via
sim_motion_proof.py before revert). The lever FIRES actively (Astra Militarum 6.7
SCREEN intents/game, Leagues of Votann 14.1) and is DECISIVELY WRONG-DIRECTION:
every gunline got WORSE — Astra Militarum 25.0 -> 16.7 (-8.3), T'au 45.8 -> 41.7
(-4.2), Votann 39.1 -> 34.8 (-4.3, worst hit despite the most screening) — while
the melee over-pole got BETTER (Death Guard / World Eaters / Emperor's Children
all +8.3, Orks +16.7; Daemons flat, Custodes -8.3 lone exception). `_screen_blocks`
verifies each screen genuinely blocks the charge, so this is a real backfire, not
a bug. MECHANISM = the durability-in-contest wall itself: AM's cheap bodies ARE
its objective-holders, so pulling one back to interpose ~1" in front of a backline
gun CEDES board presence; the melee army charges the fragile screen, kills it, and
takes the abandoned objectives anyway. The sim cannot separate "dedicated screen
chaff" from "objective bodies" (no surplus chaff in the representation), so even
screening loses the objective game. FIFTH on-table AI lever to wash/backfire
(after mass-bodies, mass-tanks, gunline-hold, focus-fire) — the on-table AI lever
family for the melee over-pole / AM under-pole is EXHAUSTED; the residual is the
off-table representation/scoring wall (needs user auth).

HARNESS NOTE: the simulator binds pick_move_intent at import (`from code.strategy
import pick_move_intent`), so the fire counter MUST patch `code.simulator
.pick_move_intent`, NOT `code.strategy.pick_move_intent` — the first run patched
strategy and read fires=0 while the gate was plainly active (win rates moved). To
re-run, re-add the SWEG_SCREEN_AI block in code/strategy.py (reverted).
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_screen_ab"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import code.simulator as sim
import code.strategy as strat
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

GUNLINES = ["Astra Militarum", "T'au Empire", "Leagues of Votann"]
MELEE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons",
         "Orks", "Adeptus Custodes"]
OVER_POLE = {"Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"}
SEEDS = [0, 1, 2, 3]

STATS: dict = defaultdict(lambda: {"games": 0, "win_off": 0, "win_on": 0, "fires": 0})

# Wrap pick_move_intent to count SCREEN intents in the ON arm (per the moving
# unit's faction). Deterministic + side-effect-free wrt the sim (read-only tap).
# NOTE: the simulator binds `pick_move_intent` at import (`from code.strategy
# import pick_move_intent`), so we MUST patch the simulator-module binding —
# patching code.strategy.pick_move_intent alone leaves the sim calling the
# original and the counter reads zero.
_orig_pmi = strat.pick_move_intent
_COUNT = {"on": False}


def _wrapped_pmi(unit, friendly, enemy, map_, **kw):
    res = _orig_pmi(unit, friendly, enemy, map_, **kw)
    if _COUNT["on"] and res[1] == "SCREEN":
        STATS[(unit.profile.faction or "?") or "?"]["fires"] += 1
    return res


def _play(a_fac: str, b_fac: str, s: int, on: bool):
    os.environ["SWEG_SCREEN_AI"] = "1" if on else "0"
    _COUNT["on"] = on
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    return Battle(a, b, map_=battle_map, primary_mission=primary).run().winner


def _run_pair(a_fac: str, b_fac: str, s: int) -> None:
    w0 = _play(a_fac, b_fac, s, False)
    w1 = _play(a_fac, b_fac, s, True)
    if w0 is None or w1 is None:
        return
    for letter, fac in (("A", a_fac), ("B", b_fac)):
        st = STATS[fac]
        st["games"] += 1
        st["win_off"] += (w0 == letter)
        st["win_on"] += (w1 == letter)


def main() -> None:
    sim.pick_move_intent = _wrapped_pmi
    try:
        for a_fac in GUNLINES:
            for b_fac in MELEE:
                for s in SEEDS:
                    _run_pair(a_fac, b_fac, s)
    finally:
        sim.pick_move_intent = _orig_pmi
        os.environ["SWEG_SCREEN_AI"] = "0"

    print("\nSWEG_SCREEN_AI causal A/B (gunline screeners vs melee threats)\n")
    hdr = (f"{'faction':<20}{'role':>9}{'games':>6}{'win%off':>8}{'win%on':>8}"
           f"{'dWin':>7}{'fires/g':>8}")
    print(hdr)
    print("-" * len(hdr))
    for fac in GUNLINES + MELEE:
        st = STATS[fac]
        g = st["games"] or 1
        wo, wn = 100.0 * st["win_off"] / g, 100.0 * st["win_on"] / g
        role = "gunline" if fac in GUNLINES else ("OVER" if fac in OVER_POLE else "melee")
        print(f"{fac:<20}{role:>9}{st['games']:>6}{wo:>8.1f}{wn:>8.1f}"
              f"{wn - wo:>+7.1f}{st['fires'] / g:>8.1f}")
    print("\ndWin = ON minus OFF. CONFIRMED if gunlines (esp. Astra Militarum) "
          "gain and the OVER rows drop. fires/g = SCREEN intents per game (ON "
          "arm); zero everywhere = inert lever, question dies.")


if __name__ == "__main__":
    main()
