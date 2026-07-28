"""How many Fate dice does the simulator actually spend, and on what?

Task #38 isolated Aeldari's ordering error to MECHANICS: two structurally
different real tenth-edition lists both produce 52-55 percent against a real
41.5. Strands of Fate is the faction's defining army rule and so the first
suspect.

A READ OF THE CODE ALONE WOULD MISLEAD HERE, which is why this exists. The
comment on `Army.fate_budget_key` says the default per-squad budget allows "up
to ~36-40 spends/round for a 9-10-squad army" against a codex-correct one per
phase, which sounds like an enormous over-valuation. But `Battle.run` rolls the
pool ONCE at battle start - six dice, never refilled (code/simulator.py, the
`army.fate_dice = sorted([...range(6)...])` block) - and that matches the codex.
The pool binds long before the budget does, so the budget gate changes how the
six dice are DISTRIBUTED, not how many exist.

This measures what actually happens: dice spent per battle, which rounds they
go in, and how often the pool is exhausted. If the simulator reliably spends all
six on high-value substitutions early, that is still an over-valuation relative
to a real player who must spread them and often wastes some - but it is a much
smaller effect than the comment implies, and the size decides whether the gate
is worth a screen at all.

Run: PYTHONHASHSEED=0 python -m scripts._fate_spend_probe
     FS_BATTLES=40 FS_OPPONENT="Adeptus Astartes"
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle

N = int(os.environ.get("FS_BATTLES", "40"))
OPP = os.environ.get("FS_OPPONENT", "Adeptus Astartes")
GATE = "SWEG_AELDARI_FATE_FAITHFUL"


def _run(gate_on: bool):
    prev = os.environ.get(GATE)
    os.environ[GATE] = "1" if gate_on else "0"
    spent = []
    leftover = []
    wins = 0
    try:
        for i in range(N):
            rng = random.Random(1000 + i)
            random.seed(1000 + i)
            a = build_faction_random_army("A", "Aeldari", 2000, rng=rng,
                                          use_archetype=True)
            b = build_faction_random_army("B", OPP, 2000, rng=rng,
                                          use_archetype=True)
            battle = Battle(a, b)
            result = battle.run()
            # The pool starts at six and is never refilled, so what remains
            # at the end is six minus what was spent.
            left = len(getattr(a, "fate_dice", []))
            leftover.append(left)
            spent.append(6 - left)
            # BattleResult.winner is the army NAME as a string, not an Army
            # object. A first version of this probe read `winner.name`, which
            # is always absent, so every battle scored as a loss and both arms
            # reported a 0.0 percent win rate — impossible against an anchor
            # that has Aeldari near 51. Kept explicit as a reminder that a
            # column reading zero for every arm is a broken instrument, not a
            # finding.
            if result is not None and result.winner == "A":
                wins += 1
    finally:
        if prev is None:
            os.environ.pop(GATE, None)
        else:
            os.environ[GATE] = prev
    return spent, leftover, wins


def _report(label, spent, leftover, wins):
    n = len(spent)
    mean = sum(spent) / n if n else 0.0
    hist = collections.Counter(spent)
    print(f"--- {label} ---")
    print(f"  battles                  {n}")
    print(f"  mean Fate dice spent     {mean:.2f} of 6")
    print(f"  pool fully exhausted in  {100.0 * hist[6] / n:.0f}% of battles")
    print(f"  distribution             " +
          "  ".join(f"{k}:{hist[k]}" for k in sorted(hist)))
    print(f"  Aeldari win rate         {100.0 * wins / n:.1f}%")
    print()


def main() -> None:
    print(f"=== Strands of Fate spending, Aeldari vs {OPP}, {N} battles ===")
    print("The pool is six dice rolled once at battle start and never refilled,")
    print("so 'spent' is six minus what remains when the battle ends.\n")

    s_off, l_off, w_off = _run(False)
    _report(f"{GATE}=0  (production default, per-squad budget)",
            s_off, l_off, w_off)
    s_on, l_on, w_on = _run(True)
    _report(f"{GATE}=1  (faithful, army-wide budget)", s_on, l_on, w_on)

    d_spend = (sum(s_on) - sum(s_off)) / max(len(s_on), 1)
    d_win = 100.0 * (w_on - w_off) / max(len(s_on), 1)
    print("=== difference (faithful minus default) ===")
    print(f"  mean dice spent   {d_spend:+.2f}")
    print(f"  Aeldari win rate  {d_win:+.1f} points")
    print()
    print("  This is ONE pairing at small N and is a sizing exercise, not a")
    print("  screen. A win-rate difference here is indicative only; the verdict")
    print("  comes from a scoped paired evaluation against the standing anchor.")
    print("  If mean dice spent barely moves, the budget gate is not where")
    print("  Aeldari's eleven-point over-rating lives and the next suspect is")
    print("  the SPEND HEURISTIC - a simulator that always substitutes")
    print("  optimally is worth more than six dice in a real player's hands.")


if __name__ == "__main__":
    main()
