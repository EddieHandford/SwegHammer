"""READ-ONLY analysis of the secondary-economy replay captures.

Reads data/_sec_audit_anchor.json (broad, real faction mix) and/or
data/_sec_audit_replay.json (deep, stratified) and prints:
  * aggregate secondary VP/player, by track and faction class
  * per-card empirical scoring table (held / scored / achieve rate / mean VP),
    split FIXED vs TACTICAL
  * dead-card clog: fraction of held-card-rounds that scored zero, and the
    distribution of consecutive zero-rounds a card sat in hand
  * cleanse / sabotage action assignment vs realised VP
  * command-point spend census by category
  * deck cards never drawn per game

Run: python -m scripts._sec_audit_analyze [anchor|replay|both]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, Counter

POOL = [
    "no_prisoners", "engage_on_all_fronts", "behind_enemy_lines", "cleanse",
    "sabotage", "secure_no_mans_land", "defend_stronghold", "extend_battle_lines",
    "storm_hostile_objective", "area_denial", "bring_it_down", "assassination",
]


def load(path):
    try:
        return json.load(open(path))["games"]
    except FileNotFoundError:
        return None


def analyse(games, label):
    print("=" * 78)
    print(f"  {label}  (n_games={len(games)})")
    print("=" * 78)

    # --- aggregate secondary VP -------------------------------------------
    secs = [g["sec_a"] for g in games] + [g["sec_b"] for g in games]
    prims = [g["prim_a"] for g in games] + [g["prim_b"] for g in games]
    print(f"\nMean secondary VP / player / game : {sum(secs)/len(secs):6.2f}")
    print(f"Mean primary   VP / player / game : {sum(prims)/len(prims):6.2f}")

    # by track
    track_sec = defaultdict(list)
    for g in games:
        track_sec[g["track_a"]].append(g["sec_a"])
        track_sec[g["track_b"]].append(g["sec_b"])
    print("\nSecondary VP by chosen track:")
    for tk, vals in sorted(track_sec.items()):
        print(f"  {tk:9s}: mean {sum(vals)/len(vals):5.2f}  (n_players={len(vals)})")

    # by faction class (focus games only, if labelled)
    if any("class" in g for g in games):
        cls_sec = defaultdict(list)
        for g in games:
            if "class" not in g:
                continue
            foc = g["focus"]
            side = "a" if g["a_fac"] == foc else "b"
            cls_sec[g["class"]].append(g[f"sec_{side}"])
        print("\nSecondary VP by focus-faction class:")
        for cls, vals in sorted(cls_sec.items()):
            print(f"  {cls:9s}: mean {sum(vals)/len(vals):5.2f}  (n={len(vals)})")

    # --- track choice frequency -------------------------------------------
    tc = Counter()
    for g in games:
        tc[g["track_a"]] += 1
        tc[g["track_b"]] += 1
    tot = sum(tc.values())
    print("\nTrack choice frequency (all players):")
    for tk, n in tc.most_common():
        print(f"  {tk:9s}: {n:5d}  ({100*n/tot:4.1f}%)")

    # --- per-card empirical table -----------------------------------------
    # For each (track, card): scored events, count>0, sum VP.
    held = defaultdict(int)      # (track,card) -> times scored (i.e. present in a scoring pass)
    scored_pos = defaultdict(int)
    vp_sum = defaultdict(int)
    for g in games:
        for (rnd, army, card, vp, track) in g["cards"]:
            held[(track, card)] += 1
            if vp > 0:
                scored_pos[(track, card)] += 1
            vp_sum[(track, card)] += vp

    for track in ("TACTICAL", "FIXED"):
        rows = [(c, held[(track, c)], scored_pos[(track, c)], vp_sum[(track, c)])
                for c in POOL if held[(track, c)] > 0]
        if not rows:
            continue
        print(f"\nPer-card empirical table  [{track} track]")
        print(f"  {'card':24s} {'held-passes':>11s} {'scored>0':>9s} "
              f"{'ach%':>6s} {'VP/held':>8s} {'VP/score':>9s}")
        for c, h, sp, vs in sorted(rows, key=lambda r: -r[3]):
            ach = 100 * sp / h if h else 0
            vph = vs / h if h else 0
            vps = vs / sp if sp else 0
            print(f"  {c:24s} {h:11d} {sp:9d} {ach:6.1f} {vph:8.2f} {vps:9.2f}")

    # --- dead-card clog (TACTICAL hands) ----------------------------------
    # From hand_entry per game+army: track consecutive rounds a card stayed
    # in hand while scoring 0 (need per-round scored set).
    zero_rounds = 0
    total_hand_card_rounds = 0
    clog_runs = []   # length of maximal consecutive zero-score holds
    for g in games:
        # build per (army,round) scored VP per card
        scored = defaultdict(int)   # (army,round,card)->vp
        for (rnd, army, card, vp, track) in g["cards"]:
            scored[(army, rnd, card)] += vp
        # walk hand_entry chronologically per army
        by_army = defaultdict(list)  # army -> [(round, hand)]
        for (rnd, army, hand) in g["hand_entry"]:
            by_army[army].append((rnd, hand))
        for army, seq in by_army.items():
            seq.sort()
            run = defaultdict(int)   # card -> current consecutive zero-run
            for (rnd, hand) in seq:
                present = set(hand)
                for card in present:
                    total_hand_card_rounds += 1
                    vp = scored.get((army, rnd, card), 0)
                    if vp <= 0:
                        zero_rounds += 1
                        run[card] += 1
                    else:
                        if run[card] > 0:
                            clog_runs.append(run[card])
                        run[card] = 0
                # cards that left the hand: flush their run
                for card in list(run.keys()):
                    if card not in present:
                        if run[card] > 0:
                            clog_runs.append(run[card])
                        del run[card]
            for card, r in run.items():
                if r > 0:
                    clog_runs.append(r)
    if total_hand_card_rounds:
        print(f"\nTactical hand ossification:")
        print(f"  held-card-rounds that scored 0 : {zero_rounds}/{total_hand_card_rounds} "
              f"({100*zero_rounds/total_hand_card_rounds:.1f}%)")
        if clog_runs:
            cc = Counter(clog_runs)
            print(f"  consecutive zero-score holds distribution (run length: count):")
            for length in sorted(cc):
                print(f"     {length} round(s): {cc[length]}")
            print(f"  holds that never scored for 3+ straight rounds: "
                  f"{sum(v for k,v in cc.items() if k>=3)}")

    # --- cleanse / sabotage assignment vs realised ------------------------
    assign_tot = defaultdict(int)
    for g in games:
        for k, v in g["assign"].items():
            action = k.split("|")[1]
            assign_tot[action] += v
    cleanse_vp = sum(vp for g in games for (_, _, c, vp, _) in g["cards"] if c == "cleanse")
    sabotage_vp = sum(vp for g in games for (_, _, c, vp, _) in g["cards"] if c == "sabotage")
    cleanse_scored = sum(1 for g in games for (_, _, c, vp, _) in g["cards"] if c == "cleanse" and vp > 0)
    sabotage_scored = sum(1 for g in games for (_, _, c, vp, _) in g["cards"] if c == "sabotage" and vp > 0)
    print(f"\nAction conversion:")
    print(f"  cleanse : {assign_tot['cleanse']} unit-actions assigned, "
          f"scored on {cleanse_scored} held-passes, total {cleanse_vp} VP")
    print(f"  sabotage: {assign_tot['sabotage']} unit-actions assigned, "
          f"scored on {sabotage_scored} held-passes, total {sabotage_vp} VP")

    # --- CP census --------------------------------------------------------
    cp_cat = defaultdict(int)
    for g in games:
        for k, v in g["cp_spend"].items():
            cat = k.split("|")[1]
            base = cat.split(":")[0]
            cp_cat[base] += v
    cp_total = sum(cp_cat.values())
    ngame = len(games)
    print(f"\nCommand-point spend census (total {cp_total} CP over {ngame} games, "
          f"{cp_total/ngame:.1f} CP/game across both armies):")
    for cat, v in sorted(cp_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat:16s}: {v:6d}  ({v/ngame:5.2f}/game, {100*v/cp_total:4.1f}%)")

    # --- undrawn deck cards -----------------------------------------------
    never_drawn = Counter()
    tac_players = 0
    for g in games:
        for side in ("a", "b"):
            if g[f"track_{side}"] != "TACTICAL":
                continue
            tac_players += 1
            # cards ever held this game (from cards passes for this army)
            army = g[f"{side}_fac"] if False else None
            # identify army name: chosen list is pool; use hand_entry names
        # Simpler: per game, cards that ended still in the deck AND never appeared in any hand
        for side in ("a", "b"):
            if g[f"track_{side}"] != "TACTICAL":
                continue
            deck_left = set(g[f"deck_left_{side}"])
            # name of this army
            # find army name via open_hand keys is 'A'/'B'
            aname = "A" if side == "a" else "B"
            drawn = set()
            for (rnd, army, hand) in g["hand_entry"]:
                if army in ("A", "B") and army == aname:
                    drawn |= set(hand)
            # Note: army names in capture are the Army.name (e.g. 'A'/'B')
            for c in deck_left:
                if c not in drawn:
                    never_drawn[c] += 1
    if tac_players:
        print(f"\nDeck cards left undrawn at game end (per TACTICAL player, "
              f"n_tac_players={tac_players}):")
        for c, n in never_drawn.most_common():
            print(f"  {c:24s}: {n:4d}  ({100*n/tac_players:4.1f}% of tac players)")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("anchor", "both"):
        g = load("data/_sec_audit_anchor.json")
        if g:
            analyse(g, "ANCHOR-WIDE SAMPLE (real faction mix)")
    if which in ("replay", "both"):
        g = load("data/_sec_audit_replay.json")
        if g:
            analyse(g, "STRATIFIED SAMPLE (by faction class)")


if __name__ == "__main__":
    main()
