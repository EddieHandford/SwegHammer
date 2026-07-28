"""Current per-faction residual against the reference win rates, with the
archetype template shape alongside — so the citation audit can be prioritised.

A template that declares more than a 2000-point army is a MENU the builder
samples from; one that fits is a LIST it should field. Both can cite the wrong
army, but only the second can be checked entry-by-entry against a source.

Run: PYTHONHASHSEED=0 python -m scripts._residual_table
"""
from __future__ import annotations
import json
import os

from code.archetypes import ARCHETYPES
from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_TARGET

LOG = os.environ.get("RT_LOG", "data/_anchor_sc68a_n80_log.json")
KEY = os.environ.get("RT_KEY", "warp_friends_may_2026")


def _sim_rates(path):
    """BOTH-SIDES win rate per faction from an evaluate_vs_meta game log.

    Each game is stored as [faction_a, faction_b, index, winner]. Counting a
    faction's wins across BOTH slots gives the both-sides rate — the same frame
    scripts/_config_compare2.py reports, NOT the A-frame that paired_delta uses.
    The two differ by the per-faction positional bias, so they must not be
    compared with each other.
    """
    d = json.load(open(path, encoding="utf-8"))
    games = d["games"] if isinstance(d, dict) else d
    w: dict = {}
    n: dict = {}
    for g in games:
        fa, fb, _idx, win = g[0], g[1], g[2], g[3]
        n[fa] = n.get(fa, 0) + 1
        n[fb] = n.get(fb, 0) + 1
        if win == "A":
            w[fa] = w.get(fa, 0) + 1
        elif win == "B":
            w[fb] = w.get(fb, 0) + 1
    return {f: 100.0 * w.get(f, 0) / n[f] for f in n if n[f]}


def _template_points(fac):
    tmpl = ARCHETYPES.get(fac, {})
    best = 0
    for entries in tmpl.values():
        tot = 0
        for k, v in entries.items():
            p = UNIT_CATALOG.get(k)
            if p:
                tot += p.points_cost * max(1, getattr(p, "min_models", 1) or 1) * v
        best = max(best, tot)
    return best, len(tmpl)


def main() -> None:
    try:
        sim = _sim_rates(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return
    rows = []
    for f in FACTIONS:
        real = TOURNAMENT_TARGET.get(f)
        if real is None or f not in sim:
            continue
        pts, ntmpl = _template_points(f)
        rows.append((abs(sim[f] - real), sim[f], real, f, pts, ntmpl))
    rows.sort(reverse=True)
    print(f"=== residuals against {KEY} (log: {LOG}) ===")
    print(f"{'faction':<24}{'sim':>7}{'real':>7}{'error':>8}   "
          f"{'template pts':>12}  shape")
    for err, s, r, f, pts, ntmpl in rows:
        shape = "MENU" if pts > 2400 else "list"
        if ntmpl > 1:
            shape = f"{ntmpl} templates"
        print(f"{f:<24}{s:>7.1f}{r:>7.1f}{s-r:>+8.1f}   {pts:>12.0f}  {shape}")
    if rows:
        mae = sum(r[0] for r in rows) / len(rows)
        print(f"\n  BOTH-SIDES raw mean absolute error: {mae:.2f} pts over "
              f"{len(rows)} factions")
        print("  (this is the _config_compare2 frame, NOT paired_delta's A-frame — "
              "never compare the two)")


if __name__ == "__main__":
    main()
