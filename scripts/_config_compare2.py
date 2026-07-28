"""Per-faction comparison across every measured configuration, both-sides frame.

Extends `scripts/_config_compare.py` to take the decomposition arms as they land,
so the redistribution can be attributed to specific gates rather than guessed at.
The guessing has already failed once: weapon range was predicted to carry the
whole Adeptus Astartes inflation and removing it recovered 0.08 of 0.45, with
Astartes still +5.03.

Read-only. Run: python -m scripts._config_compare2
"""
from __future__ import annotations
import collections
import json
import os

CONFIGS = [
    ("sc67a", "data/_anchor_sc67a_n80_log.json"),
    ("4gate", "data/_scr_ampkg2_log.json"),
    ("sc68a", "data/_anchor_sc68a_n80_log.json"),
    ("norange", "data/_scr_norange_log.json"),
    ("noscore", "data/_scr_noscoring_log.json"),
    ("cand1", "data/_scr_amonly_log.json"),
    ("cand2", "data/_scr_cand2_log.json"),
]


def rates(path):
    games = json.load(open(path))["games"]
    w, n = collections.Counter(), collections.Counter()
    for fa, fb, _s, win in games:
        n[fa] += 1
        w[fa] += (win == "A")
        n[fb] += 1
        w[fb] += (win == "B")
    return {f: 100.0 * w[f] / n[f] for f in n}


def main() -> None:
    real = {k: v["win_rate"] for k, v in
            json.load(open("data/warpfriends_rolling.json"))["factions"].items()}
    cols = [(name, rates(p)) for name, p in CONFIGS if os.path.exists(p)]
    print("win rate by configuration (both-sides frame)\n")
    print(f"{'faction':<22}{'real':>7}" + "".join(f"{n:>9}" for n, _ in cols))
    for f in sorted(real):
        print(f"{f:<22}{real[f]:>7.1f}" + "".join(f"{r[f]:>9.1f}" for _n, r in cols))
    print()
    print("absolute error by configuration\n")
    print(f"{'faction':<22}" + "".join(f"{n:>9}" for n, _ in cols))
    tot = [0.0] * len(cols)
    for f in sorted(real, key=lambda f: -abs(cols[-1][1][f] - real[f])):
        errs = [abs(r[f] - real[f]) for _n, r in cols]
        for i, e in enumerate(errs):
            tot[i] += e
        print(f"{f:<22}" + "".join(f"{e:>9.1f}" for e in errs))
    print(f"{'-' * 22}" + "".join(f"{'-' * 9}" for _ in cols))
    print(f"{'MEAN':<22}" + "".join(f"{t / len(real):>9.2f}" for t in tot))


if __name__ == "__main__":
    main()
