"""Check evaluate_vs_meta.report_diagnostics against the standalone probes.

The diagnostics block was written twice: once as a standalone instrument
(scripts/_skill_vs_null.py, scripts/_matchup_dispersion.py) and once wired into
evaluate_vs_meta. Two implementations of the same quantity is only useful if
they are actually compared, so this reconstructs the evaluation's inputs from
the standing anchor game log and asserts the wired-in version reproduces the
standalone figures.

Expected from the sc69a anchor, measured 2026-07-27:
    Spearman                +0.282
    Pearson                 +0.249
    spread ratio             1.75
    skill against the null  -3.33
    matchup standard deviation 13.4 over 231 pairings

Run: PYTHONHASHSEED=0 python -m scripts._verify_diagnostics
     VD_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import json
import os
from collections import Counter, defaultdict

from scripts.evaluate_vs_meta import (
    FACTIONS, TOURNAMENT_GAMES, report_diagnostics,
)

LOG = os.environ.get("VD_LOG", "data/_anchor_sc69a_n80_log.json")
EXPECTED = {
    "spearman": 0.282, "pearson": 0.249, "spread_ratio": 1.75,
    "skill_vs_null": -3.333, "matchup_sd": 13.4,
}
TOL = {"spearman": 0.01, "pearson": 0.01, "spread_ratio": 0.02,
       "skill_vs_null": 0.02, "matchup_sd": 0.1}


def main() -> None:
    d = json.load(open(LOG, encoding="utf-8"))
    games = d["games"] if isinstance(d, dict) else d

    wins = defaultdict(Counter)
    played = Counter()
    for g in games:
        fa, fb, _i, win = g[0], g[1], g[2], g[3]
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1

    # Rebuild exactly what run_matrix hands to report / report_diagnostics.
    pair_wr = {k: wins[k].get("A", 0) / played[k] * 100.0 for k in played}
    sim = {}
    for fac in FACTIONS:
        num = den = 0.0
        for b in FACTIONS:
            if b == fac or (fac, b) not in pair_wr:
                continue
            w = TOURNAMENT_GAMES[b]
            num += pair_wr[(fac, b)] * w
            den += w
        if den:
            sim[fac] = num / den

    out = report_diagnostics(sim, pair_wr, scoped=False,
                             n_battles=d.get("n") if isinstance(d, dict) else 80)

    print()
    print("=== verification against the standalone probes ===")
    bad = 0
    for k, want in EXPECTED.items():
        got = out.get(k)
        if got is None:
            print(f"  {k:<16} MISSING from the diagnostics output")
            bad += 1
            continue
        ok = abs(got - want) <= TOL[k]
        print(f"  {k:<16} wired {got:+8.3f}  standalone {want:+8.3f}  "
              f"{'ok' if ok else 'MISMATCH'}")
        bad += 0 if ok else 1

    print()
    if bad:
        print(f"  {bad} value(s) disagree — one of the two implementations is wrong.")
        raise SystemExit(1)
    print("  All values agree. The wired-in diagnostics reproduce the standalone")
    print("  instruments from a separate code path.")

    # The scoped guard must refuse rather than print a meaningless correlation.
    print()
    print("=== scoped guard ===")
    scoped_out = report_diagnostics(sim, pair_wr, scoped=True)
    if scoped_out != {}:
        print("  MISMATCH — a scoped run must return nothing, got "
              f"{sorted(scoped_out)}")
        raise SystemExit(1)
    print("  Scoped run correctly refuses to report. ")


if __name__ == "__main__":
    main()
