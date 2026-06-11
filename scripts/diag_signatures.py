"""Game-shape signature diagnostic for SwegHammer.

Computes the behavioural signatures that have real-world competitive-meta
reference values, enabling a direct sim-vs-reality comparison.

Reference values live in docs/REAL_META_SIGNATURES.md.

Usage (smoke test, tiny matrix):
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_signatures

Usage (calibration-grade run):
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_signatures --pairs 30 --seeds 5

Arguments:
    --pairs  Number of faction matchups to sample (default: 2 for smoke test).
             The script picks the first N from a fixed list that covers a spread
             of archetypes (horde, elite, titanic, hybrid).
    --seeds  Number of random seeds per matchup (default: 2 for smoke test).

Signatures reported (see docs/REAL_META_SIGNATURES.md for reference values):
    1. Mean primary victory points per player per game        (real ≈ 29)
    2. Going-first win rate                                   (real ≈ 49–52%)
    3. Mean secondary victory points per player per game      (real ≈ 22.7)
    4. Round-1 primary score assertion                        (must be 0)
    5. Per-turn primary cap fraction                          (fraction hitting 15)
    6. Per-round primary trajectory                           (shape 0→5–10→peak→…)
    7. Victory-point margin distribution                      (median, fraction > 50)
    8. Challenger-card trigger rate                           (modelled or not)

PYTHONHASHSEED must be 0 for deterministic results — the script enforces this
via re-exec (same mechanism as evaluate_vs_meta.py).
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Reproducibility: re-exec with PYTHONHASHSEED=0 if not already set.
# ---------------------------------------------------------------------------
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_signatures"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army  # noqa: E402
from code.events import (  # noqa: E402
    EventLog, ObjectiveScored, RoundEnded, RoundStarted, UnitActivated,
)
from code.simulator import Battle  # noqa: E402
from scripts.evaluate_vs_meta import _pick_rotation_map  # noqa: E402

# ---------------------------------------------------------------------------
# Matchup list — representative spread of archetypes.
# Index N is used for smoke (first --pairs entries); full run uses all.
# ---------------------------------------------------------------------------
MATCHUP_POOL: List[Tuple[str, str]] = [
    ("Imperial Knights",   "Tyranids"),           # titanic vs horde
    ("Adeptus Astartes",   "Orks"),               # elite vs horde
    ("Aeldari",            "Chaos Space Marines"), # hybrid vs hybrid
    ("Necrons",            "Astra Militarum"),     # elite vs shooty vehicle
    ("T'au Empire",        "World Eaters"),        # ranged vs melee
    ("Adeptus Custodes",   "Chaos Daemons"),       # elite vs swarm
    ("Death Guard",        "Adeptus Mechanicus"),  # durable vs shooty
    ("Thousand Sons",      "Drukhari"),            # sorcerer vs fast
    ("Genestealer Cults",  "Grey Knights"),        # ambush vs elite
    ("Adepta Sororitas",   "Leagues of Votann"),   # mid-tier vs mid-tier
]


# ---------------------------------------------------------------------------
# Per-game data containers
# ---------------------------------------------------------------------------

class _GameRecord:
    """Collects all signature data for a single battle."""

    def __init__(self) -> None:
        self.a_name: Optional[str] = None
        self.b_name: Optional[str] = None
        self.winner: Optional[str] = None
        # Who went first (army name), inferred from the first UnitActivated
        # event after RoundStarted(round_num=1).
        self.first_player: Optional[str] = None
        # Per-round combined VP delta: index 0 = round 1, etc.
        self.a_round_vp: List[int] = []   # a's total-VP gain per round
        self.b_round_vp: List[int] = []
        # Per-round primary VP, summed from ObjectiveScored events emitted
        # within each round's scoring window.  Primary is the only thing that
        # ObjectiveScored tracks — secondary is inferred as (total - primary).
        self.a_round_primary: List[int] = []
        self.b_round_primary: List[int] = []
        # Un-capped running VP totals from the final RoundEnded event.
        # (BattleResult.a_vp is the same un-capped self._a_vp value; caps only
        # apply inside _decide_winner for winner determination and are not
        # written back to BattleResult.)
        self.a_uncapped_total: int = 0
        self.b_uncapped_total: int = 0


def _parse_event_log(log: EventLog, result) -> _GameRecord:
    """Walk the event log and populate a _GameRecord from it."""
    rec = _GameRecord()
    rec.a_name = result.a_name
    rec.b_name = result.b_name
    rec.winner = result.winner

    current_round: int = 0
    # Accumulate ObjectiveScored VP within the current round window.
    _a_primary_this_round: int = 0
    _b_primary_this_round: int = 0
    _prev_a_total: int = 0
    _prev_b_total: int = 0
    _round1_first_activation_seen: bool = False
    # Running un-capped totals from the last RoundEnded seen.
    _last_a_total: int = 0
    _last_b_total: int = 0

    # The ObjectiveScored events can fire BEFORE the RoundStarted event when
    # SWEG_ENTERSCORE=1 (they fire at the top of a round for the previous
    # round's control state), OR AFTER all combat events when scoring at
    # end-of-round.  In both modes, the RoundEnded event fires last and
    # carries the cumulative totals, so we flush primary accumulators there.

    for ev in log.events:
        name = type(ev).__name__

        if name == "BattleStarted":
            rec.a_name = ev.army_a_name
            rec.b_name = ev.army_b_name

        elif name == "RoundStarted":
            current_round = ev.round_num
            _a_primary_this_round = 0
            _b_primary_this_round = 0
            _round1_first_activation_seen = (current_round != 1)

        elif name == "UnitActivated":
            # Capture the first-player from the first activation in round 1.
            if current_round == 1 and not _round1_first_activation_seen:
                rec.first_player = ev.army_name
                _round1_first_activation_seen = True

        elif name == "ObjectiveScored":
            if ev.army_name == rec.a_name and ev.vp_awarded:
                _a_primary_this_round += ev.vp_awarded
            elif ev.army_name == rec.b_name and ev.vp_awarded:
                _b_primary_this_round += ev.vp_awarded

        elif name == "RoundEnded":
            # Total-VP delta for this round (un-capped self._a_vp which is
            # per-round-15-capped for primary but not game-total-capped).
            a_delta = ev.a_vp_total - _prev_a_total
            b_delta = ev.b_vp_total - _prev_b_total
            rec.a_round_vp.append(a_delta)
            rec.b_round_vp.append(b_delta)
            # ObjectiveScored events are emitted BEFORE the per-round primary
            # cap (15 for Take and Hold, 12 for Purge, etc.) is applied to
            # self._a_vp, so summing them can OVER-count primary relative to
            # what was actually credited.  Clamp to the round delta: primary
            # cannot exceed the total delta (secondary is always ≥ 0).
            a_prim_capped = min(_a_primary_this_round, a_delta)
            b_prim_capped = min(_b_primary_this_round, b_delta)
            rec.a_round_primary.append(a_prim_capped)
            rec.b_round_primary.append(b_prim_capped)
            _prev_a_total = ev.a_vp_total
            _prev_b_total = ev.b_vp_total
            _last_a_total = ev.a_vp_total
            _last_b_total = ev.b_vp_total

    rec.a_uncapped_total = _last_a_total
    rec.b_uncapped_total = _last_b_total
    return rec


# ---------------------------------------------------------------------------
# Signature computation
# ---------------------------------------------------------------------------

def _compute_signatures(records: List[_GameRecord]) -> dict:
    """Aggregate all game records into the signature table."""
    n_games = len(records)
    if n_games == 0:
        raise ValueError("No game records to analyse.")

    # Flatten per-player observations.
    # Each game contributes 2 player-games (one per side).
    all_primary: List[int] = []        # final primary per player-game
    all_secondary: List[int] = []      # final secondary per player-game
    all_final_vp: List[int] = []       # final total VP per player-game
    going_first_wins: int = 0
    going_first_total: int = 0

    # Per-round primary: slot [r] = list of primary VP (one per player-game
    # contributing a round-r value).  Up to 5 rounds.
    per_round_primary: List[List[int]] = [[] for _ in range(5)]
    # Count player-rounds hitting the 15 primary cap.
    cap15_hits: int = 0
    cap15_total: int = 0   # player-rounds in rounds 2-5 (round 1 is always 0)

    margin_list: List[int] = []
    round1_primary_ok: bool = True   # assertion: all round-1 primary values == 0

    for rec in records:
        # --- Final VP decomposition -----------------------------------
        # rec.a_uncapped_total = self._a_vp at battle end = primary + secondary
        # (both un-capped).  ObjectiveScored events sum to primary VP.
        # Secondary = un-capped total − primary.
        # We then apply the same caps _decide_winner uses for display:
        #   primary capped at 50, secondary capped at 40.
        a_total_primary_raw = sum(rec.a_round_primary)
        b_total_primary_raw = sum(rec.b_round_primary)
        a_secondary_raw = max(0, rec.a_uncapped_total - a_total_primary_raw)
        b_secondary_raw = max(0, rec.b_uncapped_total - b_total_primary_raw)
        # Apply the same caps as _decide_winner (SWEG_PRIMARY_CAP_50 default ON,
        # secondary cap always 40).
        a_total_primary = min(a_total_primary_raw, 50)
        b_total_primary = min(b_total_primary_raw, 50)
        a_secondary = min(a_secondary_raw, 40)
        b_secondary = min(b_secondary_raw, 40)

        all_primary.extend([a_total_primary, b_total_primary])
        all_secondary.extend([a_secondary, b_secondary])
        all_final_vp.extend([a_total_primary + a_secondary, b_total_primary + b_secondary])

        # --- Going-first win rate ------------------------------------
        if rec.first_player and rec.winner and rec.winner != "Draw":
            going_first_total += 1
            if rec.first_player == rec.winner:
                going_first_wins += 1

        # --- Per-round primary trajectory + cap fraction --------------
        for rnd_idx, (a_prim, b_prim) in enumerate(
            zip(rec.a_round_primary, rec.b_round_primary)
        ):
            per_round_primary[rnd_idx].extend([a_prim, b_prim])
            if rnd_idx == 0:
                # Round 1 must always be 0 (primary opens in round 2).
                if a_prim != 0 or b_prim != 0:
                    round1_primary_ok = False
            else:
                # Rounds 2-5: count player-rounds hitting the 15-pt cap.
                cap15_total += 2
                if a_prim >= 15:
                    cap15_hits += 1
                if b_prim >= 15:
                    cap15_hits += 1

        # --- Victory-point margin (capped VP, matching _decide_winner) ----
        if rec.winner:
            margin_list.append(abs(
                (a_total_primary + a_secondary) - (b_total_primary + b_secondary)
            ))

    # Aggregate per-round means.
    round_means = []
    for slot in per_round_primary:
        if slot:
            round_means.append(statistics.mean(slot))
        else:
            round_means.append(None)

    return {
        "n_games": n_games,
        "mean_primary_per_player": statistics.mean(all_primary) if all_primary else None,
        "mean_secondary_per_player": statistics.mean(all_secondary) if all_secondary else None,
        "going_first_win_rate": (
            going_first_wins / going_first_total if going_first_total else None
        ),
        "going_first_sample_size": going_first_total,
        "round1_primary_zero_assert": round1_primary_ok,
        "cap15_fraction": (
            cap15_hits / cap15_total if cap15_total else None
        ),
        "per_round_primary_means": round_means,   # index 0 = round 1, …, index 4 = round 5
        "vp_margin_median": statistics.median(margin_list) if margin_list else None,
        "vp_margin_fraction_over_50": (
            sum(1 for m in margin_list if m > 50) / len(margin_list)
            if margin_list else None
        ),
        "vp_margin_sample_size": len(margin_list),
    }


# ---------------------------------------------------------------------------
# Pretty-print
# ---------------------------------------------------------------------------

_REAL = {
    "mean_primary":             "≈ 29 (Pariah Nexus / Chapter Approved 2025-26)",
    "going_first_win_rate":     "≈ 49–52% (Chapter Approved 2025-26); more-or-less better to go second",
    "mean_secondary":           "≈ 22.7 (Pariah Nexus)",
    "round1_primary_zero":      "0 by rule (primary opens round 2)",
    "cap15_fraction":           "rare early; rises rounds 3–4",
    "round_trajectory":         "0 → 5–10 (rounds 2–3) → peak 10–15 (rounds 3–4) → attrition-constrained round 5",
    "margin_median":            "no published mean; typical competitive range 10–30",
    "margin_over_50":           "blowout threshold; no published fraction",
    "challenger_cards":         "available when trailing by ≥ 6 VP at start of a battle round; max 12 VP",
}


def _print_table(sigs: dict) -> None:
    print()
    print("=" * 72)
    print("  GAME-SHAPE SIGNATURE TABLE")
    print(f"  N = {sigs['n_games']} games (each contributes 2 player-games)")
    print("=" * 72)

    def _fmt(val, fmt=".1f"):
        if val is None:
            return "N/A"
        if isinstance(val, float):
            return f"{val:{fmt}}"
        return str(val)

    def _pct(val):
        if val is None:
            return "N/A"
        return f"{val * 100:.1f}%"

    print()
    print("# 1  Mean primary victory points per player per game")
    print(f"     Sim:  {_fmt(sigs['mean_primary_per_player'])}")
    print(f"     Real: {_REAL['mean_primary']}")

    print()
    print("# 2  Going-first win rate")
    if sigs["going_first_sample_size"] == 0:
        print("     Sim:  NOT MEASURABLE — going-first is not recorded in the event")
        print("           stream or BattleResult (first_player derived from first")
        print("           UnitActivated in round 1; if no UnitActivated fires in r1,")
        print("           this will be None)")
    else:
        print(f"     Sim:  {_pct(sigs['going_first_win_rate'])}  "
              f"(n = {sigs['going_first_sample_size']} decisive games)")
    print(f"     Real: {_REAL['going_first_win_rate']}")

    print()
    print("# 3  Mean secondary victory points per player per game")
    print(f"     Sim:  {_fmt(sigs['mean_secondary_per_player'])}")
    print(f"     Real: {_REAL['mean_secondary']}")

    print()
    print("# 4  Round-1 primary score assertion (must be 0)")
    ok = sigs["round1_primary_zero_assert"]
    print(f"     Sim:  {'PASS — all round-1 primary values are 0' if ok else 'FAIL — non-zero round-1 primary detected'}")
    print(f"     Real: {_REAL['round1_primary_zero']}")

    print()
    print("# 5  Fraction of player-rounds (rounds 2–5) hitting the 15-point primary cap")
    print(f"     Sim:  {_pct(sigs['cap15_fraction'])}")
    print(f"     Real: {_REAL['cap15_fraction']}")

    print()
    print("# 6  Per-round primary trajectory (mean primary per player per round)")
    means = sigs["per_round_primary_means"]
    for i, m in enumerate(means):
        rnd = i + 1
        val = _fmt(m) if m is not None else "—"
        print(f"     Round {rnd}: {val}")
    print(f"     Real shape: {_REAL['round_trajectory']}")

    print()
    print("# 7  Victory-point margin distribution (winner VP − loser VP)")
    print(f"     Sim median margin:        {_fmt(sigs['vp_margin_median'])}")
    print(f"     Sim fraction margin > 50: {_pct(sigs['vp_margin_fraction_over_50'])}  "
          f"(n = {sigs['vp_margin_sample_size']} decisive games)")
    print(f"     Real: {_REAL['margin_median']}")

    print()
    print("# 8  Challenger-card trigger rate")
    print("     Sim:  NOT MODELLED — the sim has no challenger-card mechanic.")
    print("           The Chapter Approved 2025-26 challenger-card rule (available")
    print("           to a player trailing by >= 6 VP at the start of a battle round,")
    print("           max 12 VP total) is not implemented in code/simulator.py.")
    print(f"     Real: {_REAL['challenger_cards']}")

    print()
    print("=" * 72)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute game-shape signatures and compare to real-meta references.",
    )
    parser.add_argument(
        "--pairs",
        type=int,
        default=2,
        help="Number of faction matchups to sample (default: 2 for smoke test).",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=2,
        help="Number of random seeds per matchup (default: 2 for smoke test).",
    )
    args = parser.parse_args()

    matchups = MATCHUP_POOL[: args.pairs]
    seeds = list(range(args.seeds))

    n_total = len(matchups) * len(seeds)
    print(f"Running {n_total} battles ({len(matchups)} matchups × {args.seeds} seeds) …")
    print("(PYTHONHASHSEED=0, PYTHONIOENCODING=utf-8)")
    print()

    records: List[_GameRecord] = []
    for a_fac, b_fac in matchups:
        for seed in seeds:
            rng_a = random.Random(seed)
            rng_b = random.Random(seed + 10_000)
            a_army = build_faction_random_army("A", a_fac, 2000, rng=rng_a, use_archetype=True)
            b_army = build_faction_random_army("B", b_fac, 2000, rng=rng_b, use_archetype=True)
            log = EventLog()
            map_ = _pick_rotation_map(seed)
            result = Battle(a_army, b_army, subscribers=[log], map_=map_).run()
            rec = _parse_event_log(log, result)
            records.append(rec)
            winner_label = result.winner if result.winner else "Draw"
            # Show capped VP (primary cap 50, secondary cap 40) — the actual
            # scored totals used by _decide_winner.  result.a_vp / b_vp are the
            # un-capped running sums and can exceed 90.
            a_prim_cap = min(sum(rec.a_round_primary), 50)
            b_prim_cap = min(sum(rec.b_round_primary), 50)
            a_sec_cap = min(max(0, rec.a_uncapped_total - sum(rec.a_round_primary)), 40)
            b_sec_cap = min(max(0, rec.b_uncapped_total - sum(rec.b_round_primary)), 40)
            print(
                f"  {a_fac} vs {b_fac}  seed={seed}"
                f"  A={a_prim_cap + a_sec_cap} (p{a_prim_cap}+s{a_sec_cap})"
                f"  B={b_prim_cap + b_sec_cap} (p{b_prim_cap}+s{b_sec_cap})"
                f"  winner={winner_label}  first={rec.first_player}"
            )

    sigs = _compute_signatures(records)
    _print_table(sigs)

    print()
    print("Full-run command (calibration-grade, N≈150 games):")
    print(
        "  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8"
        " python -m scripts.diag_signatures --pairs 10 --seeds 15"
    )
    print()
    print("Measurability summary:")
    print("  MEASURABLE from current event stream:")
    print("    #1 mean primary VP per player per game")
    print("    #2 going-first win rate  (inferred from first UnitActivated in round 1)")
    print("    #3 mean secondary VP per player per game  (BattleResult total − event-derived primary)")
    print("    #4 round-1 primary zero assertion")
    print("    #5 per-round primary cap fraction")
    print("    #6 per-round primary trajectory")
    print("    #7 victory-point margin distribution")
    print("  NOT MEASURABLE — missing from event stream or sim:")
    print("    #8 challenger-card trigger rate  (mechanic not implemented in the sim)")


if __name__ == "__main__":
    main()
