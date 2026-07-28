"""Does a reported paired delta reconcile with its own flip count?

The Cull the Horde pick-awareness screen reported Aeldari at -6.38 with 74
flips. Aeldari play 3,360 games in a full matrix, so a 6.38-point swing needs
roughly 214 net result changes. Seventy-four cannot produce it, and a headline
number that fails its own arithmetic must be checked before anything is built on
it.

Two explanations are possible and they have very different consequences:

  the flip count and the delta are computed over DIFFERENT denominators - for
  instance flips over army-A cells only while the delta is field-weighted, in
  which case both numbers are right and only my reading was wrong;

  or one of them is wrong.

This recomputes each faction's win rate from both game logs directly, in both
the army-A field-weighted frame the evaluation uses and the raw both-sides
frame, and counts result changes per faction. No reliance on paired_delta's own
accounting.

Run: PYTHONHASHSEED=0 python -m scripts._verify_paired_delta
     VD_OFF=data/_anchor_sc69a_n80_log.json VD_ON=data/_scr_cullpick_full_log.json
"""
from __future__ import annotations
import collections
import json
import os

from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_GAMES

OFF = os.environ.get("VD_OFF", "data/_anchor_sc69a_n80_log.json")
ON = os.environ.get("VD_ON", "data/_scr_cullpick_full_log.json")
WATCH = [f.strip() for f in os.environ.get(
    "VD_WATCH", "Aeldari,Chaos Knights,Grey Knights,Adeptus Custodes").split(",")]


def _load(path):
    d = json.load(open(path, encoding="utf-8"))
    games = d["games"] if isinstance(d, dict) else d
    # key on (a, b, index) so the two logs align game for game
    return {(g[0], g[1], g[2]): g[3] for g in games}


def _rates(res):
    wins = collections.defaultdict(collections.Counter)
    played = collections.Counter()
    for (fa, fb, _i), win in res.items():
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1
    pair = {k: wins[k].get("A", 0) / played[k] * 100.0 for k in played}

    a_frame, both = {}, {}
    for fac in FACTIONS:
        num = den = 0.0
        bn = bd = 0.0
        for b in FACTIONS:
            if b == fac:
                continue
            ab, ba = pair.get((fac, b)), pair.get((b, fac))
            w = TOURNAMENT_GAMES[b]
            if ab is not None:
                num += ab * w
                den += w
                bn += ab * w
                bd += w
            if ba is not None:
                bn += (100.0 - ba) * w
                bd += w
        if den:
            a_frame[fac] = num / den
        if bd:
            both[fac] = bn / bd
    return a_frame, both


def main() -> None:
    try:
        off, on = _load(OFF), _load(ON)
    except Exception as exc:
        print(f"could not read logs: {exc}")
        return

    shared = set(off) & set(on)
    print(f"=== paired delta reconciliation ===")
    print(f"  off {OFF}\n  on  {ON}")
    print(f"  {len(off)} / {len(on)} games, {len(shared)} keyed in both\n")

    changed = collections.Counter()
    involved = collections.Counter()
    for k in shared:
        fa, fb, _i = k
        involved[fa] += 1
        involved[fb] += 1
        if off[k] != on[k]:
            changed[fa] += 1
            changed[fb] += 1

    a_off, b_off = _rates(off)
    a_on, b_on = _rates(on)

    print(f"{'faction':<24}{'A-frame off':>12}{'A-frame on':>12}{'delta':>8}"
          f"{'both off':>10}{'both on':>9}{'delta':>8}{'changed':>9}{'games':>7}")
    for fac in FACTIONS:
        if WATCH and fac not in WATCH:
            continue
        ao, an = a_off.get(fac, 0.0), a_on.get(fac, 0.0)
        bo, bn = b_off.get(fac, 0.0), b_on.get(fac, 0.0)
        print(f"{fac:<24}{ao:>12.2f}{an:>12.2f}{an - ao:>+8.2f}"
              f"{bo:>10.2f}{bn:>9.2f}{bn - bo:>+8.2f}"
              f"{changed[fac]:>9}{involved[fac]:>7}")

    print()
    print("  'changed' counts every game this faction played whose winner")
    print("  differs between the two logs, counting both slots. If a reported")
    print("  delta needs more result changes than this, the delta and the flip")
    print("  count are being taken over different denominators - or one is")
    print("  wrong. A swing of D points over N games needs about N*D/100")
    print("  net changes, and net is always at most the raw count.")


if __name__ == "__main__":
    main()
