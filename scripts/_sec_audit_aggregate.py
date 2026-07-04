"""READ-ONLY lean anchor-wide aggregate: replay a spread of anchor games and
report the secondary-VP-per-player distribution over the REAL faction mix,
split by chosen track and by whether the sim's replayed winner matches the
anchor. No heavy per-card capture — just the accounting totals.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._sec_audit_aggregate [N]
"""
from __future__ import annotations
import json, os, random, sys
from collections import defaultdict

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._sec_audit_aggregate"] + sys.argv[1:], env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}


def replay(a_fac, b_fac, s):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    bm = _pick_rotation_map(s)
    pr = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=bm, rules=None, primary_mission=pr)
    res = battle.run()
    return (battle._a_secondary_vp, battle._b_secondary_vp,
            getattr(a, "secondary_track", None) or "FIXED",
            getattr(b, "secondary_track", None) or "FIXED",
            res.winner if res else None, _w(a_fac, b_fac, s))


def _w(a, b, s):
    return None


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    d = json.load(open("data/_anchor_sc51a_n80_log.json"))
    rows = d["games"]
    step = max(1, len(rows) // n)
    picks = rows[::step][:n]
    sec_all = []
    by_track = defaultdict(list)
    by_fac = defaultdict(list)
    print(f"Lean anchor aggregate over {len(picks)} games...", flush=True)
    done = 0
    for (a_fac, b_fac, s, _win) in picks:
        r = replay(a_fac, b_fac, s)
        if r is None:
            continue
        sa, sb, ta, tb, _w2, _ = r
        sec_all += [sa, sb]
        by_track[ta].append(sa); by_track[tb].append(sb)
        by_fac[a_fac].append(sa); by_fac[b_fac].append(sb)
        done += 1
        if done % 50 == 0:
            print(f"  {done}/{len(picks)}  running mean sec={sum(sec_all)/len(sec_all):.2f}", flush=True)
    print(f"\nANCHOR-WIDE mean secondary VP/player/game: {sum(sec_all)/len(sec_all):.2f} (n={len(sec_all)})")
    print("By track:")
    for tk, v in sorted(by_track.items()):
        print(f"  {tk:9s}: {sum(v)/len(v):5.2f}  (n={len(v)}, {100*len(v)/len(sec_all):.0f}% of players)")
    print("By faction (mean secondary VP/player):")
    for f, v in sorted(by_fac.items(), key=lambda x: sum(x[1])/len(x[1])):
        print(f"  {f:22s}: {sum(v)/len(v):5.2f}  (n={len(v)})")


if __name__ == "__main__":
    main()
