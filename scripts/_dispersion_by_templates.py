"""Do factions that field more than one list produce less extreme matchups?

scripts/_matchup_dispersion shows the simulator's symmetrized matchups have a
standard deviation of about 13 points, roughly twice what tournament data
shows, and that only about half of pairings land inside a realistic 40-60 band.
The leading structural explanation is that 21 of the 22 factions field exactly
ONE archetype list, while a real faction's win rate averages over hundreds of
different lists. One list has one fixed set of good and bad matchups and no way
to regress toward the middle.

That explanation makes a prediction that can be checked without running
anything new. `build_archetype_army` picks uniformly at random among a
faction's templates per army built (code/archetypes.py), and Chaos Daemons is
the only faction with more than one. So Chaos Daemons should show visibly
LOWER matchup dispersion than the single-list factions - a natural experiment
already present in the standing anchor.

If it does not, the single-list hypothesis is wrong or too weak to matter, and
the over-dispersion has to be explained by the deterministic policy instead.
Either answer is worth having before anyone builds a list-population system.

Run: PYTHONHASHSEED=0 python -m scripts._dispersion_by_templates
     DB_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import json
import math
import os
from collections import Counter, defaultdict

from code.archetypes import ARCHETYPES
from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_TARGET

LOG = os.environ.get("DB_LOG", "data/_anchor_sc69a_n80_log.json")


def _load_games(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["games"] if isinstance(d, dict) else d


def _template_count(fac: str) -> int:
    """Templates the builder can actually choose between for this faction.

    The Chaos Daemons "Scintillating Legion" entry is filtered out at build
    time when SWEG_DAEMONS_BELAKOR is off, so read the same environment
    variable the builder reads rather than trusting the dict length.
    """
    tmpl = ARCHETYPES.get(fac, {})
    keys = list(tmpl.keys())
    if (fac == "Chaos Daemons" and "Scintillating Legion" in keys
            and os.environ.get("SWEG_DAEMONS_BELAKOR", "1") == "0"):
        keys = [k for k in keys if k != "Scintillating Legion"]
    return len(keys)


def main() -> None:
    try:
        games = _load_games(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    wins = defaultdict(Counter)
    played = Counter()
    for g in games:
        fa, fb, _i, win = g[0], g[1], g[2], g[3]
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1

    def sym(a, b):
        n_ab, n_ba = played.get((a, b), 0), played.get((b, a), 0)
        if not n_ab or not n_ba:
            return None
        ab = wins[(a, b)].get("A", 0) / n_ab * 100.0
        ba = 100.0 - wins[(b, a)].get("A", 0) / n_ba * 100.0
        return 0.5 * (ab + ba)

    rows = []
    for fac in FACTIONS:
        vals = [v for b in FACTIONS if b != fac
                for v in (sym(fac, b),) if v is not None]
        if len(vals) < 3:
            continue
        m = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
        extreme = 100.0 * sum(1 for v in vals if v >= 70 or v <= 30) / len(vals)
        real = TOURNAMENT_TARGET.get(fac)
        rows.append((sd, fac, _template_count(fac), m, extreme,
                     (m - real) if real is not None else float("nan")))

    rows.sort()
    print(f"=== matchup dispersion per faction ({LOG}) ===")
    print(f"{'faction':<24}{'lists':>6}{'mean':>7}{'matchup sd':>12}"
          f"{'>=70/30':>9}{'resid':>8}")
    for sd, fac, ntmpl, m, extreme, resid in rows:
        mark = "   <-- multiple lists" if ntmpl > 1 else ""
        print(f"{fac:<24}{ntmpl:>6}{m:>7.1f}{sd:>12.1f}"
              f"{extreme:>8.0f}%{resid:>+8.1f}{mark}")

    multi = [r for r in rows if r[2] > 1]
    single = [r for r in rows if r[2] == 1]
    print()
    if multi and single:
        ms = sum(r[0] for r in multi) / len(multi)
        ss = sum(r[0] for r in single) / len(single)
        me = sum(r[4] for r in multi) / len(multi)
        se = sum(r[4] for r in single) / len(single)
        print(f"  mean matchup standard deviation")
        print(f"    factions with multiple lists ({len(multi):>2}) {ms:>6.1f} points, "
              f"{me:.0f}% extreme matchups")
        print(f"    factions with one list       ({len(single):>2}) {ss:>6.1f} points, "
              f"{se:.0f}% extreme matchups")
        print()
        if ms < ss - 1.0:
            print("  The multi-list faction disperses LESS, as the hypothesis predicts.")
            print("  With one faction in the group this is suggestive, not proof - but")
            print("  it is the cheap check clearing the way for a list-population test.")
        else:
            print("  The multi-list faction does NOT disperse less. The single-list")
            print("  hypothesis fails its own prediction; look to the deterministic")
            print("  policy for the over-dispersion instead.")
    else:
        print("  no multi-list faction present to compare against")


if __name__ == "__main__":
    main()
