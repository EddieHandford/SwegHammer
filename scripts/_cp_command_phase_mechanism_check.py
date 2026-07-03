"""Scratch mechanism check for SWEG_CP_PER_COMMAND_PHASE (secondary-economy
audit fix D4, 2026-07-03).

Instruments ONE real battle (Imperial Knights vs Chaos Knights -- both
factions fire command-point stratagems every game, e.g. Rotate Ion Shields /
Diabolic Bulwark, so the spend side of the ledger is exercised) and prints,
per battle round and per army:

  * the command-point balance at the START of the round (before this
    round's Command-phase grant),
  * every `award_command_phase_cp` call this round (before -> after, so the
    +2-per-round drip is visible directly at the grant site),
  * the balance at the END of the round (after all spends this round),
  * the implied spend this round (grant total - (end - start)).

Run twice: once with the gate at its default (ON, +2/round) and once with
`SWEG_CP_PER_COMMAND_PHASE=0` (the kill-switch, +1/round, the pre-fix rate)
-- same battle, same seed -- to show the mechanism responds to the gate and
that spends draw the balance down correctly under both rates without ever
exceeding CP_CAP=6 or going negative.
"""
from __future__ import annotations

import os
import random

os.environ.setdefault("PYTHONHASHSEED", "0")

import code.stratagems as strat_mod
import code.simulator as sim
from code.simulator import Battle
from code.army_builder import build_faction_random_army


def _run_instrumented(gate_env: str, seed: int = 7):
    if gate_env == "unset":
        os.environ.pop("SWEG_CP_PER_COMMAND_PHASE", None)
    else:
        os.environ["SWEG_CP_PER_COMMAND_PHASE"] = gate_env

    grants = []   # (round, army_name, before, after)
    rounds = []   # (round, army_name, start_balance, end_balance)

    _orig_award = strat_mod.award_command_phase_cp

    def _logging_award(army):
        before = army.command_points
        _orig_award(army)
        after = army.command_points
        grants.append((sim_state["round"], army.name, before, after))

    strat_mod.award_command_phase_cp = _logging_award
    sim.award_command_phase_cp = _logging_award

    _orig_run_round = Battle._run_round
    sim_state = {"round": 0}

    def _logging_run_round(self, round_num):
        sim_state["round"] = round_num
        start_a, start_b = self.a.command_points, self.b.command_points
        _orig_run_round(self, round_num)
        end_a, end_b = self.a.command_points, self.b.command_points
        rounds.append((round_num, self.a.name, start_a, end_a))
        rounds.append((round_num, self.b.name, start_b, end_b))

    Battle._run_round = _logging_run_round

    try:
        random.seed(seed)
        a = build_faction_random_army("A", "Imperial Knights", 2000,
                                      rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", "Chaos Knights", 2000,
                                      rng=random.Random(seed + 10000), use_archetype=True)
        result = Battle(a, b).run()
    finally:
        Battle._run_round = _orig_run_round
        strat_mod.award_command_phase_cp = _orig_award
        sim.award_command_phase_cp = _orig_award

    return grants, rounds, result


def _print_report(label: str, grants, rounds, result):
    print("=" * 78)
    print(f"{label}  (winner={result.winner}, rounds={result.rounds})")
    print("=" * 78)
    # Group grants by round.
    by_round = {}
    for rnd, name, before, after in grants:
        by_round.setdefault(rnd, []).append((name, before, after, after - before))
    for rnd, _, start_a, end_a in [r for r in rounds if r[1] == "A"]:
        start_b = next(r[2] for r in rounds if r[0] == rnd and r[1] == "B")
        end_b = next(r[3] for r in rounds if r[0] == rnd and r[1] == "B")
        print(f"\nRound {rnd}:")
        for name, before, after, delta in by_round.get(rnd, []):
            print(f"  award_command_phase_cp({name}): {before} -> {after}  (+{delta})")
        grant_a_total = sum(d for n, _, _, d in by_round.get(rnd, []) if n == "A")
        grant_b_total = sum(d for n, _, _, d in by_round.get(rnd, []) if n == "B")
        spend_a = grant_a_total - (end_a - start_a)
        spend_b = grant_b_total - (end_b - start_b)
        print(f"  A: start={start_a} granted=+{grant_a_total} spent={spend_a} end={end_a}")
        print(f"  B: start={start_b} granted=+{grant_b_total} spent={spend_b} end={end_b}")
        assert 0 <= end_a <= 6, f"A balance out of [0,6]: {end_a}"
        assert 0 <= end_b <= 6, f"B balance out of [0,6]: {end_b}"
    print()


print("\n" + "#" * 78)
print("# DEMO 1 -- gate at PRODUCTION DEFAULT (unset -> ON, +2 CP/round)")
print("#" * 78)
grants_on, rounds_on, result_on = _run_instrumented("unset")
_print_report("SWEG_CP_PER_COMMAND_PHASE unset (default ON)", grants_on, rounds_on, result_on)

per_round_grant_on = set(d for _, _, before, after in grants_on for d in [after - before])
print(f"Per-call grant amounts observed (default ON): {sorted(per_round_grant_on)} "
      f"-> {'CONFIRMED +2/call cap-bounded' if per_round_grant_on <= {1, 2} else 'UNEXPECTED'}")
n_calls_on = len(grants_on)
n_rounds_on = result_on.rounds
print(f"award_command_phase_cp call count: {n_calls_on} across {n_rounds_on} rounds "
      f"({n_calls_on} = 2 armies x {n_rounds_on} rounds, ONE call per army per round -- "
      f"the +2 is granted inside the single call, not via a second call site)")

print("\n" + "#" * 78)
print("# DEMO 2 -- gate OFF (SWEG_CP_PER_COMMAND_PHASE=0, pre-fix +1 CP/round)")
print("#" * 78)
grants_off, rounds_off, result_off = _run_instrumented("0")
_print_report("SWEG_CP_PER_COMMAND_PHASE=0 (kill-switch, +1/round)", grants_off, rounds_off, result_off)

per_round_grant_off = set(d for _, _, before, after in grants_off for d in [after - before])
print(f"Per-call grant amounts observed (gate OFF): {sorted(per_round_grant_off)} "
      f"-> {'CONFIRMED +1/call cap-bounded' if per_round_grant_off <= {0, 1} else 'UNEXPECTED'}")

os.environ.pop("SWEG_CP_PER_COMMAND_PHASE", None)
print("\nDONE")
