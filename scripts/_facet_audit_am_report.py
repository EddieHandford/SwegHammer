"""Aggregation + report printer for data/_facet_audit_am_raw.pkl (produced by
scripts/_facet_audit_am.py). Read-only; rebuilds rosters (NO Battle.run(), so
this adds zero simulated battles to the budget) only to recover each side's
total wounds capacity for the facet-5 wounds->points conversion.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._facet_audit_am_report
"""
from __future__ import annotations

import pickle
import random
from collections import defaultdict
from statistics import mean

from code.army_builder import build_faction_random_army

FOCUS = "Astra Militarum"
REF_FACTIONS = ["Genestealer Cults", "T'au Empire", "Necrons",
                "Adeptus Astartes", "Death Guard"]

with open("data/_facet_audit_am_raw.pkl", "rb") as fh:
    RESULTS = pickle.load(fh)

_WOUNDS_CACHE: dict = {}


def _wounds_capacity(a_fac, b_fac, seed):
    key = (a_fac, b_fac, seed)
    if key in _WOUNDS_CACHE:
        return _WOUNDS_CACHE[key]
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    aw = sum(u.profile.health for u in a.units)
    bw = sum(u.profile.health for u in b.units)
    _WOUNDS_CACHE[key] = (aw, bw)
    return aw, bw


def side_games(fac):
    """Yield (side, r) for every battle where `fac` played, side in {A,B}."""
    for r in RESULTS:
        if r["a_fac"] == fac:
            yield "A", r
        elif r["b_fac"] == fac:
            yield "B", r


def opp_of(side, r):
    return r["b_fac"] if side == "A" else r["a_fac"]


# ---------------------------------------------------------------------------
print("=" * 100)
print("FACET 1 — SITTING ON OBJECTIVES: fraction of army's OC on ANY marker / on")
print("markers it CONTROLS, per round 1-5 (mean over games)")
print("=" * 100)


def facet1_rows(fac):
    any_by_r = defaultdict(list)
    ctrl_by_r = defaultdict(list)
    per_opp_r5 = defaultdict(list)
    for side, r in side_games(fac):
        start = r["a_oc_start"] if side == "A" else r["b_oc_start"]
        if start <= 0:
            continue
        oc_any = r["oc_any"][side]
        oc_ctrl = r["oc_ctrl"][side]
        for rnd in range(1, 6):
            any_by_r[rnd].append(oc_any.get(rnd, 0) / start)
            ctrl_by_r[rnd].append(oc_ctrl.get(rnd, 0) / start)
        per_opp_r5[opp_of(side, r)].append(oc_ctrl.get(5, 0) / start)
    return any_by_r, ctrl_by_r, per_opp_r5


am_any, am_ctrl, am_opp_r5 = facet1_rows(FOCUS)
print(f"{'round':>6} {'AM any%':>9} {'AM ctrl%':>9} {'refs any%':>10} {'refs ctrl%':>11}")
ref_any_all, ref_ctrl_all = defaultdict(list), defaultdict(list)
for ref in REF_FACTIONS:
    a_any, a_ctrl, _ = facet1_rows(ref)
    for rnd in range(1, 6):
        ref_any_all[rnd].extend(a_any[rnd])
        ref_ctrl_all[rnd].extend(a_ctrl[rnd])
for rnd in range(1, 6):
    print(f"{rnd:>6} {100*mean(am_any[rnd]):>8.1f}% {100*mean(am_ctrl[rnd]):>8.1f}% "
          f"{100*mean(ref_any_all[rnd]):>9.1f}% {100*mean(ref_ctrl_all[rnd]):>10.1f}%")
opp_means = sorted(((mean(v), k) for k, v in am_opp_r5.items() if v), reverse=True)
print("AM round-5 controlled-OC%% extremes: best =", opp_means[0], " worst =", opp_means[-1])

# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("FACET 2 — DENYING ENEMY VP: opponent's VP vs AM vs opponent's VP vs REFERENCES")
print("=" * 100)
AM_OPPONENTS = sorted({(r["b_fac"] if r["a_fac"] == FOCUS else r["a_fac"])
                       for r in RESULTS if FOCUS in (r["a_fac"], r["b_fac"]) and r["_tag"] == "AM"})


def opp_stats_vs(fac_playing_defense, tag):
    prim, sec, kill, pos, obj, tot, n = [], [], [], [], [], [], 0
    for r in RESULTS:
        if r["_tag"] != tag:
            continue
        if r["b_fac"] == fac_playing_defense:
            side = "B"
        elif tag == "REF" and r["a_fac"] == fac_playing_defense:
            # only used when fac itself is a REF and we want its OWN offence,
            # not relevant here (defense-side only) — skip.
            continue
        else:
            continue
        prim.append(r["b_primary"]); sec.append(r["b_sec"])
        kill.append(r["b_kill_vp"]); pos.append(r["b_pos_vp"]); obj.append(r["b_obj_vp"])
        tot.append(r["b_vp_total"]); n += 1
    return prim, sec, kill, pos, obj, tot, n


print(f"{'opponent':<20} {'vsAM prim':>9} {'vsREF prim':>10} {'vsAM kill':>9} {'vsREF kill':>10} "
      f"{'vsAM pos':>8} {'vsREF pos':>9} {'vsAM obj':>8} {'vsREF obj':>9} {'n(AM/REF)':>10}")
f2_deltas = []
for opp in AM_OPPONENTS:
    p1, s1, k1, po1, o1, t1, n1 = opp_stats_vs(opp, "AM")
    p2, s2, k2, po2, o2, t2, n2 = opp_stats_vs(opp, "REF")
    if not p1 or not p2:
        continue
    print(f"{opp:<20} {mean(p1):>9.1f} {mean(p2):>10.1f} {mean(k1):>9.1f} {mean(k2):>10.1f} "
          f"{mean(po1):>8.1f} {mean(po2):>9.1f} {mean(o1):>8.1f} {mean(o2):>9.1f} {n1:>4}/{n2:<4}")
    f2_deltas.append((opp, mean(t1) - mean(t2), mean(p1) - mean(p2), mean(k1) - mean(k2)))
f2_deltas.sort(key=lambda x: -x[1])
print("Opponent total-VP delta (vsAM - vsREF), sorted, most-to-least extra VP earned vs AM:")
for opp, dt, dp, dk in f2_deltas:
    print(f"  {opp:<20} totalVPΔ={dt:+6.1f}  primaryΔ={dp:+6.1f}  killVPΔ={dk:+6.1f}")

# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("FACET 3 — ACTIVELY ACHIEVING SECONDARIES: attempt rate (pursue_target /")
print("action_this_round set, share of alive units, mean over rounds) + VP by source")
print("=" * 100)


def facet3(fac):
    pursue_rate, action_rate = [], []
    kill_vp, pos_vp, obj_vp = [], [], []
    action_types = defaultdict(int)
    for side, r in side_games(fac):
        kv = r["a_kill_vp"] if side == "A" else r["b_kill_vp"]
        pv = r["a_pos_vp"] if side == "A" else r["b_pos_vp"]
        ov = r["a_obj_vp"] if side == "A" else r["b_obj_vp"]
        kill_vp.append(kv); pos_vp.append(pv); obj_vp.append(ov)
        for rnd, snap in r["pursue_actions"].items():
            s = snap[side]
            if s["alive"] <= 0:
                continue
            pursue_rate.append(s["pursue"] / s["alive"])
            action_rate.append(sum(s["actions"].values()) / s["alive"])
            for k, v in s["actions"].items():
                action_types[k] += v
    return pursue_rate, action_rate, kill_vp, pos_vp, obj_vp, action_types


am_pr, am_ar, am_kv, am_pv, am_ov, am_at = facet3(FOCUS)
print(f"{'faction':<22} {'pursue%':>8} {'action%':>8} {'killVP':>7} {'posVP':>6} {'objVP':>6}")
print(f"{FOCUS:<22} {100*mean(am_pr):>7.1f}% {100*mean(am_ar):>7.1f}% {mean(am_kv):>7.1f} "
      f"{mean(am_pv):>6.1f} {mean(am_ov):>6.1f}")
ref_pr, ref_ar, ref_kv, ref_pv, ref_ov = [], [], [], [], []
ref_at_all = defaultdict(int)
for ref in REF_FACTIONS:
    p, a, k, po, o, at = facet3(ref)
    ref_pr += p; ref_ar += a; ref_kv += k; ref_pv += po; ref_ov += o
    for kk, vv in at.items():
        ref_at_all[kk] += vv
    print(f"  {ref:<20} {100*mean(p):>7.1f}% {100*mean(a):>7.1f}% {mean(k):>7.1f} "
          f"{mean(po):>6.1f} {mean(o):>6.1f}")
print(f"{'REF MEAN':<22} {100*mean(ref_pr):>7.1f}% {100*mean(ref_ar):>7.1f}% {mean(ref_kv):>7.1f} "
      f"{mean(ref_pv):>6.1f} {mean(ref_ov):>6.1f}")
print("AM action_this_round types:", dict(am_at))
print("REF action_this_round types (summed):", dict(ref_at_all))

# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("FACET 4 — KILLING THE RIGHT THINGS: dealt-damage allocation by target class,")
print("units-finished per 100 damage, overkill share on 1-wound chaff")
print("=" * 100)


def facet4(fac):
    dmg = defaultdict(float)
    tot = 0.0
    kills = 0
    overkill = 0.0
    per_opp = defaultdict(lambda: [0.0, 0])  # opp -> [overkill_frac_sum, n]
    for side, r in side_games(fac):
        dbc = r["dmg_by_class"][side]
        for k, v in dbc.items():
            dmg[k] += v
        tot += r["dmg_total"][side]
        kills += r["kills"][side]
        overkill += r["overkill_chaff"][side]
        if r["dmg_total"][side] > 0:
            per_opp[opp_of(side, r)][0] += r["overkill_chaff"][side] / r["dmg_total"][side]
            per_opp[opp_of(side, r)][1] += 1
    return dmg, tot, kills, overkill, per_opp


am_dmg, am_tot, am_kills, am_overkill, am_per_opp = facet4(FOCUS)
print(f"AM: total dmg={am_tot:.0f}  kills={am_kills}  dmg/kill={am_tot/max(1,am_kills):.1f}  "
      f"overkill-on-chaff={100*am_overkill/max(1,am_tot):.2f}% of total dmg")
for cls in ("chaff", "scoring_infantry", "character", "monster_vehicle"):
    print(f"  {cls:<18} {am_dmg.get(cls,0):>8.0f}  ({100*am_dmg.get(cls,0)/max(1,am_tot):>5.1f}%)")
ref_dmg_all = defaultdict(float); ref_tot_all = 0.0; ref_kills_all = 0; ref_overkill_all = 0.0
for ref in REF_FACTIONS:
    d, t, k, o, _ = facet4(ref)
    for kk, vv in d.items():
        ref_dmg_all[kk] += vv
    ref_tot_all += t; ref_kills_all += k; ref_overkill_all += o
print(f"REF (pooled): total dmg={ref_tot_all:.0f}  kills={ref_kills_all}  "
      f"dmg/kill={ref_tot_all/max(1,ref_kills_all):.1f}  "
      f"overkill-on-chaff={100*ref_overkill_all/max(1,ref_tot_all):.2f}%")
for cls in ("chaff", "scoring_infantry", "character", "monster_vehicle"):
    print(f"  {cls:<18} {ref_dmg_all.get(cls,0):>8.0f}  ({100*ref_dmg_all.get(cls,0)/max(1,ref_tot_all):>5.1f}%)")
opp_ok = sorted(((v[0]/v[1], k) for k, v in am_per_opp.items() if v[1]), reverse=True)
print("AM overkill-on-chaff%% by opponent, extremes: highest =", opp_ok[0] if opp_ok else None,
      " lowest =", opp_ok[-1] if opp_ok else None)

# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("FACET 5 — SURVIVING AS EXPECTED: realized cumulative points-lost vs a stat-")
print("implied expectation (proxy: max(ranged,melee) expected-wounds x roster")
print("points-per-wound, flat per-round rate from PRE-BATTLE rosters)")
print("=" * 100)


def facet5(fac):
    ratio_by_r = defaultdict(list)
    for side, r in side_games(fac):
        aw, bw = _wounds_capacity(r["a_fac"], r["b_fac"], r["seed"])
        my_wounds = aw if side == "A" else bw
        my_pts = r["a_pts_start"] if side == "A" else r["b_pts_start"]
        exp_incoming = r["a_exp_incoming"] if side == "A" else r["b_exp_incoming"]
        if my_wounds <= 0 or exp_incoming <= 0:
            continue
        pts_per_wound = my_pts / my_wounds
        exp_pts_per_round = exp_incoming * pts_per_wound
        cum = r["pts_lost_by_round"][side]
        for rnd in range(1, 6):
            expected = exp_pts_per_round * rnd
            if expected <= 0:
                continue
            ratio_by_r[rnd].append(cum[rnd] / expected)
    return ratio_by_r


am_ratio = facet5(FOCUS)
print(f"{'round':>6} {'AM realized/expected':>22} {'REF mean realized/expected':>28}")
ref_ratio_all = defaultdict(list)
for ref in REF_FACTIONS:
    rr = facet5(ref)
    for rnd in range(1, 6):
        ref_ratio_all[rnd].extend(rr[rnd])
for rnd in range(1, 6):
    print(f"{rnd:>6} {mean(am_ratio[rnd]):>22.2f} {mean(ref_ratio_all[rnd]):>28.2f}")
print("ratio > 1.0 = dying FASTER than the stat-implied expectation (fidelity flag);")
print("ratio ~ 1.0 = dying at the rate its fragility implies (durability economics);")
print("ratio < 1.0 = surviving BETTER than the stat-implied expectation.")
