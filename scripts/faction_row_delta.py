#!/usr/bin/env python3
"""Per-matchup (per-cell) win-rate delta for one faction's row.

The paired_delta report gives per-FACTION aggregate deltas. Per-faction AI
strategy work needs the stronger Principle-1 gate: when a faction's own strategy
is enabled, EVERY one of its matchups (that faction vs each opponent) must be
>= 0 -- any single matchup that dips is the signal that the strategy mis-plays
that pairing and needs refinement (never ship a per-faction lever that lowers the
faction anywhere).

This reads two --log-games JSON logs (OFF anchor, ON arm), picks one faction, and
prints its win rate vs each opponent in both arms with the delta, flagging any
opponent where the faction dropped. The faction's win rate in a pairing pools both
table positions (faction-as-A wins + faction-as-B wins) over the matched seeds.

Usage:
  python -m scripts.faction_row_delta OFF.json ON.json "Astra Militarum"
  python -m scripts.faction_row_delta OFF.json ON.json "Astra Militarum" --threshold 0.0
"""
import json
import sys
from collections import defaultdict


def _load(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    games = {}
    for a, b, s, w in d["games"]:
        games[(a, b, int(s))] = w
    return games


def _row(games, faction):
    """faction -> {opponent: (faction_wins, n)} pooling both table positions."""
    wins = defaultdict(int)
    n = defaultdict(int)
    for (a, b, _s), w in games.items():
        if a == faction:
            n[b] += 1
            if w == "A":
                wins[b] += 1
        elif b == faction:
            n[a] += 1
            if w == "B":
                wins[a] += 1
    return wins, n


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        raise SystemExit(2)
    off_path, on_path, faction = sys.argv[1], sys.argv[2], sys.argv[3]
    threshold = 0.0
    if "--threshold" in sys.argv:
        threshold = float(sys.argv[sys.argv.index("--threshold") + 1])

    off, on = _load(off_path), _load(on_path)
    # Pair only on matched games (handles OFF N=80 vs ON N=40, etc.).
    keys = off.keys() & on.keys()
    off = {k: off[k] for k in keys}
    on = {k: on[k] for k in keys}

    off_w, off_n = _row(off, faction)
    on_w, on_n = _row(on, faction)
    opponents = sorted(set(off_n) | set(on_n))

    print(f"\nPER-MATCHUP ROW for {faction}  (matched games: {len(keys)})")
    print(f"OFF={off_path}\nON ={on_path}\n")
    print(f"{'Opponent':28s} {'OFF%':>6s} {'ON%':>6s} {'delta':>7s} {'n':>5s}  flag")
    print("-" * 62)
    tot_off_w = tot_on_w = tot_n = 0
    dips = []
    for opp in opponents:
        no = off_n.get(opp, 0)
        nn = on_n.get(opp, 0)
        if no == 0 or nn == 0:
            continue
        off_wr = off_w.get(opp, 0) / no * 100.0
        on_wr = on_w.get(opp, 0) / nn * 100.0
        d = on_wr - off_wr
        tot_off_w += off_w.get(opp, 0)
        tot_on_w += on_w.get(opp, 0)
        tot_n += no  # no == nn on matched seeds
        flag = ""
        if d < -threshold - 1e-9:
            flag = "  <-- DIP (refine this matchup)"
            dips.append((opp, d))
        print(f"{opp:28s} {off_wr:6.1f} {on_wr:6.1f} {d:+7.2f} {no:5d}{flag}")
    print("-" * 62)
    agg_off = tot_off_w / tot_n * 100.0 if tot_n else 0.0
    agg_on = tot_on_w / tot_n * 100.0 if tot_n else 0.0
    print(f"{'AGGREGATE (unweighted row)':28s} {agg_off:6.1f} {agg_on:6.1f} "
          f"{agg_on - agg_off:+7.2f} {tot_n:5d}")
    if dips:
        print(f"\nONLY-IMPROVES GATE: FAILED — {len(dips)} matchup(s) dipped: "
              + ", ".join(f"{o} ({d:+.2f})" for o, d in dips))
    else:
        print(f"\nONLY-IMPROVES GATE: PASSED — no matchup below "
              f"{-threshold:+.2f} (every {faction} pairing >= threshold).")


if __name__ == "__main__":
    main()
