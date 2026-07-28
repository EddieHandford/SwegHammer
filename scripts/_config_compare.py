"""Compare the three measured configurations against the real-meta target.

  sc67a  — the old standing anchor (none of this session's gates)
  4gate  — the Astra Militarum package alone (data/_scr_ampkg2_log.json)
  sc68a  — all seventeen faithful gates (data/_anchor_sc68a_n80_log.json)

The point is to see WHICH factions the thirteen non-package gates move and in
which direction, because the headline gated mean absolute error hides a large
redistribution: Death Guard improves by 4.5 while several other factions worsen
by 3-4 each.

Read-only. Run: python -m scripts._config_compare
"""
from __future__ import annotations
import collections
import json


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
    cfg = [
        ("sc67a", rates("data/_anchor_sc67a_n80_log.json")),
        ("4gate", rates("data/_scr_ampkg2_log.json")),
        ("sc68a", rates("data/_anchor_sc68a_n80_log.json")),
    ]
    print(f"{'faction':<22}{'real':>7}" + "".join(f"{n:>9}" for n, _ in cfg)
          + f"{'|err 67a':>9}{'err 4g':>8}{'err 68a':>9}")
    tot = [0.0, 0.0, 0.0]
    rows = []
    for f in real:
        errs = [abs(r[f] - real[f]) for _n, r in cfg]
        for i, e in enumerate(errs):
            tot[i] += e
        rows.append((errs[2] - errs[0], f, [r[f] for _n, r in cfg], errs))
    for delta, f, vals, errs in sorted(rows, key=lambda x: -x[0]):
        mark = "  <-- worse" if delta > 2 else ("  <-- BETTER" if delta < -2 else "")
        print(f"{f:<22}{real[f]:>7.1f}" + "".join(f"{v:>9.1f}" for v in vals)
              + f"{errs[0]:>9.1f}{errs[1]:>8.1f}{errs[2]:>9.1f}{mark}")
    print()
    for i, (name, _r) in enumerate(cfg):
        print(f"  raw mean absolute error, {name}: {tot[i]/len(real):.2f}")


if __name__ == "__main__":
    main()
