"""AUDIT D scratch: replay Death Guard games from the standing anchor
(data/_anchor_sc50a_n80_log.json) and decompose each win/loss into primary
(objective) VP, secondary (scoring) VP, and attrition (survivor counts), to
decide whether Death Guard's over-pole is durability-shaped or scoring-shaped.

Mirrors scripts._ec_crater_replay's exact reconstruction.
Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dura_audit_d_winshape [opp1 opp2 ...]
"""
from __future__ import annotations
import json
import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._dura_audit_d_winshape"] + sys.argv[1:],
        env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitShot,
    UnitFought, UnitKilled, ObjectiveScored, BattleEnded, EventLog,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

DG = "Death Guard"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}


def load_dg_games(path):
    d = json.load(open(path, encoding="utf-8"))
    return [(a, b, s, w) for a, b, s, w in d["games"] if DG in (a, b)]


def replay_one(a_fac, b_fac, s):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    log = EventLog()
    if not a.units or not b.units:
        return None, log, a, b, None
    bm = _pick_rotation_map(s)
    pm = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=bm, rules=None, primary_mission=pm, subscribers=[log])
    res = battle.run()
    return res, log, a, b, battle


def summarise(a_fac, b_fac, s, rec_winner, res, log, battle):
    if battle is None:
        return None
    ev = log.events
    info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                info[u.uid] = {"name": u.name, "army": u.army}
    dg_side = "A" if a_fac == DG else "B"
    opp_side = "B" if dg_side == "A" else "A"
    dg_start = sum(1 for i in info.values() if i["army"] == dg_side)
    opp_start = sum(1 for i in info.values() if i["army"] == opp_side)
    dg_deaths = sum(1 for e in ev if isinstance(e, UnitKilled)
                    and info.get(e.unit_uid, {}).get("army") == dg_side)
    opp_deaths = sum(1 for e in ev if isinstance(e, UnitKilled)
                     and info.get(e.unit_uid, {}).get("army") == opp_side)
    a_primary = battle._a_vp - battle._a_secondary_vp - battle._a_challenger_vp
    b_primary = battle._b_vp - battle._b_secondary_vp - battle._b_challenger_vp
    a_capped, b_capped = battle._capped_vp_pair()

    def pick(a_val, b_val):
        return a_val if dg_side == "A" else b_val

    dg_primary = pick(a_primary, b_primary)
    opp_primary = pick(b_primary, a_primary)
    dg_sec = pick(battle._a_secondary_vp, battle._b_secondary_vp)
    opp_sec = pick(battle._b_secondary_vp, battle._a_secondary_vp)
    dg_capped = pick(a_capped, b_capped)
    opp_capped = pick(b_capped, a_capped)
    dg_surv = pick(res.a_survivors, res.b_survivors)
    opp_surv = pick(res.b_survivors, res.a_survivors)
    return {
        "opp": b_fac if a_fac == DG else a_fac, "s": s,
        "rec": rec_winner, "rep": res.winner, "match": res.winner == rec_winner,
        "dg_side": dg_side, "rounds": res.rounds,
        "dg_start": dg_start, "opp_start": opp_start,
        "dg_deaths": dg_deaths, "opp_deaths": opp_deaths,
        "dg_surv": dg_surv, "opp_surv": opp_surv,
        "dg_primary": dg_primary, "opp_primary": opp_primary,
        "dg_sec": dg_sec, "opp_sec": opp_sec,
        "dg_capped": dg_capped, "opp_capped": opp_capped,
        "dg_win": res.winner == dg_side,
    }


def avg(lst, k):
    return sum(x[k] for x in lst) / len(lst) if lst else 0


def main():
    path = "data/_anchor_sc50a_n80_log.json"
    games = load_dg_games(path)
    want_opps = sys.argv[1:] if len(sys.argv) > 1 else None
    summaries = []
    matched = 0
    total = 0
    detail_opps = want_opps or [
        "Aeldari", "Orks", "Astra Militarum", "Adeptus Custodes", "Imperial Knights"]
    detail = {o: [] for o in detail_opps}
    for a_fac, b_fac, s, w in games:
        res, log, a, b, battle = replay_one(a_fac, b_fac, s)
        sm = summarise(a_fac, b_fac, s, w, res, log, battle)
        if sm is None:
            continue
        total += 1
        if sm["match"]:
            matched += 1
        summaries.append(sm)
        o = sm["opp"]
        if o in detail and len(detail[o]) < 3:
            detail[o].append(sm)
    print(f"REPRODUCTION: {matched}/{total} winners matched ({100*matched/total:.1f}%)")
    wins = [x for x in summaries if x["dg_win"]]
    losses = [x for x in summaries if not x["dg_win"] and x["rep"] is not None]
    print(f"\nDG record (replayed): {len(wins)}W / {len(losses)}L  = "
          f"{100*len(wins)/(len(wins)+len(losses)):.1f}%")
    print("\n=== AGGREGATE over DG WINS (n=%d) ===" % len(wins))
    print(f"  avg DG primary   {avg(wins,'dg_primary'):5.1f}  vs opp primary   "
          f"{avg(wins,'opp_primary'):5.1f}   (margin {avg(wins,'dg_primary')-avg(wins,'opp_primary'):+.1f})")
    print(f"  avg DG secondary {avg(wins,'dg_sec'):5.1f}  vs opp secondary "
          f"{avg(wins,'opp_sec'):5.1f}   (margin {avg(wins,'dg_sec')-avg(wins,'opp_sec'):+.1f})")
    print(f"  avg DG capped    {avg(wins,'dg_capped'):5.1f}  vs opp capped    "
          f"{avg(wins,'opp_capped'):5.1f}   (margin {avg(wins,'dg_capped')-avg(wins,'opp_capped'):+.1f})")
    print(f"  avg DG survivors {avg(wins,'dg_surv'):5.1f}/{avg(wins,'dg_start'):.1f}"
          f"   opp survivors {avg(wins,'opp_surv'):5.1f}/{avg(wins,'opp_start'):.1f}")
    print(f"  avg DG units killed {avg(wins,'dg_deaths'):4.1f}   opp units killed {avg(wins,'opp_deaths'):4.1f}")
    print("\n=== AGGREGATE over DG LOSSES (n=%d) ===" % len(losses))
    print(f"  avg DG primary   {avg(losses,'dg_primary'):5.1f}  vs opp primary   "
          f"{avg(losses,'opp_primary'):5.1f}")
    print(f"  avg DG secondary {avg(losses,'dg_sec'):5.1f}  vs opp secondary "
          f"{avg(losses,'opp_sec'):5.1f}")
    print(f"  avg DG survivors {avg(losses,'dg_surv'):5.1f}/{avg(losses,'dg_start'):.1f}"
          f"   opp survivors {avg(losses,'opp_surv'):5.1f}/{avg(losses,'opp_start'):.1f}")
    all_played = wins + losses
    prim_margin = avg(all_played, 'dg_primary') - avg(all_played, 'opp_primary')
    sec_margin = avg(all_played, 'dg_sec') - avg(all_played, 'opp_sec')
    print("\n=== OVERALL margin decomposition (all replayed DG games n=%d) ===" % len(all_played))
    print(f"  primary   margin {prim_margin:+.2f}")
    print(f"  secondary margin {sec_margin:+.2f}")
    print(f"  capped    margin {avg(all_played,'dg_capped')-avg(all_played,'opp_capped'):+.2f}")
    print(f"  DG survival rate {avg(all_played,'dg_surv')/avg(all_played,'dg_start')*100:.1f}%"
          f"   opp survival rate {avg(all_played,'opp_surv')/avg(all_played,'opp_start')*100:.1f}%")
    print("\n=== DETAIL: sample games by opponent class ===")
    for o in detail_opps:
        for sm in detail[o]:
            print(f"\n-- DG vs {o} s={sm['s']} rounds={sm['rounds']} "
                  f"{'WIN' if sm['dg_win'] else 'LOSS'} (match={sm['match']})")
            print(f"   VP capped: DG {sm['dg_capped']} - {sm['opp_capped']} opp")
            print(f"   primary:   DG {sm['dg_primary']:.0f} - {sm['opp_primary']:.0f} opp | "
                  f"secondary: DG {sm['dg_sec']:.0f} - {sm['opp_sec']:.0f} opp")
            print(f"   attrition: DG survivors {sm['dg_surv']}/{sm['dg_start']} "
                  f"({100*sm['dg_surv']/max(sm['dg_start'],1):.0f}%) | opp survivors "
                  f"{sm['opp_surv']}/{sm['opp_start']} ({100*sm['opp_surv']/max(sm['opp_start'],1):.0f}%)")
    json.dump({"n": len(summaries), "matched": matched, "games": summaries},
              open("data/_dura_audit_d_dg_games.json", "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
