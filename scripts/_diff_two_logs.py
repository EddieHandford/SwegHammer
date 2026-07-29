"""Are two evaluation game logs identical, and if not, where do they differ?

The corrected SWEG_CULL_PICK_AWARE substitution produced numbers identical to
the uncorrected one, to the decimal, across every faction. Either the fix is a
no-op in practice - in which case the mechanism claimed for the first screen's
magnitude is refuted - or the wrong file was read. This settles which.

Run: PYTHONHASHSEED=0 python -m scripts._diff_two_logs
     DL_A=data/_scr_cullpick_full_log.json DL_B=data/_scr_cullpick2_log.json
"""
from __future__ import annotations
import collections
import json
import os

A = os.environ.get("DL_A", "data/_scr_cullpick_full_log.json")
B = os.environ.get("DL_B", "data/_scr_cullpick2_log.json")


def _load(path):
    d = json.load(open(path, encoding="utf-8"))
    games = d["games"] if isinstance(d, dict) else d
    return {(g[0], g[1], g[2]): g[3] for g in games}


def main() -> None:
    try:
        a, b = _load(A), _load(B)
    except Exception as exc:
        print(f"could not read: {exc}")
        return

    print(f"=== {A}\n=== {B}\n")
    print(f"  games   {len(a)} / {len(b)}")
    only_a = set(a) - set(b)
    only_b = set(b) - set(a)
    if only_a or only_b:
        print(f"  keys only in A: {len(only_a)}   only in B: {len(only_b)}")

    shared = set(a) & set(b)
    diff = [k for k in shared if a[k] != b[k]]
    print(f"  shared  {len(shared)}")
    print(f"  DIFFER  {len(diff)}\n")

    if not diff:
        print("  The two runs are BYTE-EQUIVALENT in outcome. The change under")
        print("  test altered no game. Any mechanism claimed to explain the")
        print("  first run's magnitude cannot rest on the code path that was")
        print("  changed, because that path never fired differently.")
        return

    by_fac = collections.Counter()
    for fa, fb, _i in diff:
        by_fac[fa] += 1
        by_fac[fb] += 1
    print("  differing games by faction:")
    for fac, n in by_fac.most_common():
        print(f"    {fac:<26}{n:>6}")


if __name__ == "__main__":
    main()
