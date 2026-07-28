"""Do Battle Focus tokens accumulate when the codex says they are lost?

Second suspect for Aeldari's mechanics defect (task #38: two structurally
different real lists both produce 52-55 percent against a real 41.5, so the
error is constant across list identity and must live in the rules).

The first suspect, the Strands of Fate per-squad budget
(SWEG_AELDARI_FATE_FAITHFUL), was measured INERT: the faithful gate changes
mean dice spent by -0.15 of six, because the pool is six dice rolled once at
battle start and never refilled, so the pool binds long before the budget does.
See scripts/_fate_spend_probe.py.

This one has a different shape, and a worse one. code/simulator.py quotes
Wahapedia verbatim: "At the end of the battle round, all unspent Battle Focus
tokens are lost". The simulator grants tokens per battle round and, BY DEFAULT,
lets unspent ones CARRY OVER. SWEG_AELDARI_BF_DISCARD zeroes the pool at end of
round as the rule requires - and it is default-off.

An accumulating resource compounds across five rounds in a way a per-round
budget cannot, so this is a better candidate for a systematic uplift than the
Fate budget was. Whether it actually matters depends on whether the simulator
ever banks tokens rather than spending them, which is what this measures: peak
and end-of-battle token holdings with the gate off and on.

Only Star Engines consumes tokens in this simulator (the other five Agile
Manoeuvres are not modelled, per the note in Battle.run), so a large unspent
bank would mean the carry-over is inflating a pool the army has almost no way
to use - in which case the gate is faithful but inert, exactly like the Fate
budget. Measure before proposing.

Run: PYTHONHASHSEED=0 python -m scripts._battle_focus_probe
     BF_BATTLES=40 BF_OPPONENT="Adeptus Astartes"
"""
from __future__ import annotations
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle

N = int(os.environ.get("BF_BATTLES", "40"))
OPP = os.environ.get("BF_OPPONENT", "Adeptus Astartes")
GATE = "SWEG_AELDARI_BF_DISCARD"


def _run(gate_on: bool):
    prev = os.environ.get(GATE)
    os.environ[GATE] = "1" if gate_on else "0"
    end_tokens = []
    wins = 0
    try:
        for i in range(N):
            rng = random.Random(2000 + i)
            random.seed(2000 + i)
            a = build_faction_random_army("A", "Aeldari", 2000, rng=rng,
                                          use_archetype=True)
            b = build_faction_random_army("B", OPP, 2000, rng=rng,
                                          use_archetype=True)
            result = Battle(a, b).run()
            end_tokens.append(float(getattr(a, "battle_focus_tokens", 0) or 0))
            # BattleResult.winner is the army NAME as a string.
            if result is not None and result.winner == "A":
                wins += 1
    finally:
        if prev is None:
            os.environ.pop(GATE, None)
        else:
            os.environ[GATE] = prev
    return end_tokens, wins


def _report(label, toks, wins):
    n = len(toks)
    mean = sum(toks) / n if n else 0.0
    print(f"--- {label} ---")
    print(f"  battles                        {n}")
    print(f"  mean tokens UNSPENT at end     {mean:.2f}")
    print(f"  battles ending with 0 tokens   {100.0 * sum(1 for t in toks if t <= 0) / n:.0f}%")
    print(f"  largest end-of-battle bank     {max(toks) if toks else 0:.0f}")
    print(f"  Aeldari win rate               {100.0 * wins / n:.1f}%")
    print()


def main() -> None:
    print(f"=== Battle Focus tokens, Aeldari vs {OPP}, {N} battles ===")
    print("Codex (quoted in code/simulator.py): 'At the end of the battle round,")
    print("all unspent Battle Focus tokens are lost.' Default lets them carry.\n")

    t_off, w_off = _run(False)
    _report(f"{GATE}=0  (production default, tokens CARRY OVER)", t_off, w_off)
    t_on, w_on = _run(True)
    _report(f"{GATE}=1  (faithful, tokens lost each round)", t_on, w_on)

    d_tok = (sum(t_on) - sum(t_off)) / max(len(t_on), 1)
    d_win = 100.0 * (w_on - w_off) / max(len(t_on), 1)
    print("=== difference (faithful minus default) ===")
    print(f"  mean unspent tokens  {d_tok:+.2f}")
    print(f"  Aeldari win rate     {d_win:+.1f} points")
    print()
    print("  Sizing only, one pairing, small N — at forty battles the standard")
    print("  error on a win-rate difference is roughly eleven points, so treat")
    print("  anything under that as noise. A LARGE unspent bank under the")
    print("  default means the carry-over inflates a resource the army cannot")
    print("  spend, which would make the gate faithful but inert — the same")
    print("  verdict the Fate budget got.")


if __name__ == "__main__":
    main()
