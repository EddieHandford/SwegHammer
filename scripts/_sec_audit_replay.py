"""READ-ONLY secondary-economy fidelity audit — per-card instrumented replay.

Reconstructs anchor-seeded games exactly as scripts._ec_crater_replay does
(the canonical construction), then monkeypatches the Battle secondary-scoring
methods to record, per game and per round:
  * each army's secondary TRACK (FIXED / TACTICAL) and chosen cards
  * the opening Tactical hand + full deck order (which cards are drawable)
  * per-round per-card victory points via _score_one_card
  * the Tactical hand composition at each round's scoring (held-but-whiffed)
  * cleanse / sabotage action ASSIGNMENT counts and completions
  * command-point spend by category (stratagem / overwatch / GTG / smokescreen)
  * final secondary VP per side, and the deck cards NEVER drawn

Nothing here mutates tracked files. Output: data/_sec_audit_replay.json.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._sec_audit_replay [N_PER_FACTION]
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._sec_audit_replay"] + sys.argv[1:], env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

# Faction classes for stratification.
CLASSES = {
    "horde":   ["Orks", "Tyranids", "Genestealer Cults"],
    "elite":   ["Adeptus Custodes", "Grey Knights", "World Eaters"],
    "gunline": ["T'au Empire", "Astra Militarum", "Leagues of Votann"],
    "durable": ["Death Guard", "Imperial Knights", "Necrons"],
}

# ---------------------------------------------------------------------------
# Capture buffers (reset per game)
# ---------------------------------------------------------------------------
CUR = {}


def _reset_capture():
    CUR.clear()
    CUR["cards"] = []          # (round, army_name, card, vp, track)
    CUR["hand_entry"] = []     # (round, army_name, tuple(hand))
    CUR["open_hand"] = {}      # army_name -> (hand, deck)
    CUR["assign"] = defaultdict(int)   # (army_name, action) -> count flagged
    CUR["cp_spend"] = defaultdict(int) # (army_name, category) -> cp


def _install_patches():
    """Monkeypatch Battle secondary + CP methods to capture. Idempotent."""
    if getattr(Battle, "_sec_audit_patched", False):
        return
    Battle._sec_audit_patched = True

    orig_score_one = Battle._score_one_card
    orig_score_hand = Battle._score_tactical_hand
    orig_init_deck = Battle._init_tactical_deck
    orig_assign_cleanse = Battle._assign_cleanse_actions
    orig_assign_sabotage = Battle._assign_sabotage_actions
    orig_fire_strat = Battle._fire_stratagem
    orig_fire_ow = Battle._fire_overwatch
    orig_gtg = Battle._maybe_go_to_ground
    orig_smoke = Battle._maybe_smokescreen

    def score_one(self, card_key, scoring_army, other_army, own_is_army_a, round_num):
        vp = orig_score_one(self, card_key, scoring_army, other_army,
                            own_is_army_a, round_num)
        track = getattr(scoring_army, "secondary_track", None) or "FIXED"
        CUR["cards"].append((round_num, scoring_army.name, card_key, vp, track))
        return vp

    def score_hand(self, army, other_army, own_is_army_a, round_num):
        hand = tuple(getattr(army, "tactical_hand", ()) or ())
        CUR["hand_entry"].append((round_num, army.name, hand))
        return orig_score_hand(self, army, other_army, own_is_army_a, round_num)

    def init_deck(self, army):
        orig_init_deck(self, army)
        if getattr(army, "secondary_track", None) == "TACTICAL":
            CUR["open_hand"][army.name] = (
                tuple(getattr(army, "tactical_hand", ()) or ()),
                tuple(getattr(army, "tactical_deck", ()) or ()),
            )

    def assign_cleanse(self, active, other):
        before = sum(1 for u in active.alive_units
                     if getattr(u, "action_this_round", None) == "cleanse")
        orig_assign_cleanse(self, active, other)
        after = sum(1 for u in active.alive_units
                    if getattr(u, "action_this_round", None) == "cleanse")
        CUR["assign"][(active.name, "cleanse")] += max(0, after - before)

    def assign_sabotage(self, active, other):
        before = sum(1 for u in active.alive_units
                     if getattr(u, "action_this_round", None) == "sabotage")
        orig_assign_sabotage(self, active, other)
        after = sum(1 for u in active.alive_units
                    if getattr(u, "action_this_round", None) == "sabotage")
        CUR["assign"][(active.name, "sabotage")] += max(0, after - before)

    def fire_strat(self, army, strat):
        before = army.command_points
        ok = orig_fire_strat(self, army, strat)
        spent = max(0, before - army.command_points)
        if spent:
            CUR["cp_spend"][(army.name, "stratagem:" + getattr(strat, "name", "?"))] += spent
        return ok

    def fire_ow(self, defending_army, enemy_unit):
        before = defending_army.command_points
        r = orig_fire_ow(self, defending_army, enemy_unit)
        spent = max(0, before - defending_army.command_points)
        if spent:
            CUR["cp_spend"][(defending_army.name, "overwatch")] += spent
        return r

    def gtg(self, defending_army, shoot_target, attacker):
        before = defending_army.command_points
        r = orig_gtg(self, defending_army, shoot_target, attacker)
        spent = max(0, before - defending_army.command_points)
        if spent:
            CUR["cp_spend"][(defending_army.name, "go_to_ground")] += spent
        return r

    def smoke(self, defending_army, shoot_target, attacker):
        before = defending_army.command_points
        r = orig_smoke(self, defending_army, shoot_target, attacker)
        spent = max(0, before - defending_army.command_points)
        if spent:
            CUR["cp_spend"][(defending_army.name, "smokescreen")] += spent
        return r

    Battle._score_one_card = score_one
    Battle._score_tactical_hand = score_hand
    Battle._init_tactical_deck = init_deck
    Battle._assign_cleanse_actions = assign_cleanse
    Battle._assign_sabotage_actions = assign_sabotage
    Battle._fire_stratagem = fire_strat
    Battle._fire_overwatch = fire_ow
    Battle._maybe_go_to_ground = gtg
    Battle._maybe_smokescreen = smoke


def replay_one(a_fac, b_fac, s):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    _reset_capture()
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=primary)
    result = battle.run()
    return _summarise(a_fac, b_fac, s, a, b, battle, result)


def _summarise(a_fac, b_fac, s, a, b, battle, result):
    return {
        "a_fac": a_fac, "b_fac": b_fac, "s": s,
        "winner": result.winner if result else None,
        "rounds": result.rounds if result else None,
        "track_a": getattr(a, "secondary_track", None) or "FIXED",
        "track_b": getattr(b, "secondary_track", None) or "FIXED",
        "chosen_a": list(getattr(a, "chosen_secondaries", ()) or ()),
        "chosen_b": list(getattr(b, "chosen_secondaries", ()) or ()),
        "sec_a": battle._a_secondary_vp,
        "sec_b": battle._b_secondary_vp,
        "prim_a": battle._a_vp - battle._a_secondary_vp - getattr(battle, "_a_challenger_vp", 0),
        "prim_b": battle._b_vp - battle._b_secondary_vp - getattr(battle, "_b_challenger_vp", 0),
        "open_hand": {k: [list(v[0]), list(v[1])] for k, v in CUR["open_hand"].items()},
        "deck_left_a": list(getattr(a, "tactical_deck", ()) or ()),
        "deck_left_b": list(getattr(b, "tactical_deck", ()) or ()),
        "hand_left_a": list(getattr(a, "tactical_hand", ()) or ()),
        "hand_left_b": list(getattr(b, "tactical_hand", ()) or ()),
        "cards": CUR["cards"],
        "hand_entry": [(r, n, list(h)) for (r, n, h) in CUR["hand_entry"]],
        "assign": {f"{k[0]}|{k[1]}": v for k, v in CUR["assign"].items()},
        "cp_spend": {f"{k[0]}|{k[1]}": v for k, v in CUR["cp_spend"].items()},
    }


def _anchor_sample(n_games):
    """Sample n_games spread uniformly across the anchor's game list, replay
    them with capture, and report the anchor-wide secondary-VP distribution
    plus a per-card empirical table over the real faction mix."""
    _install_patches()
    d = json.load(open("data/_anchor_sc51a_n80_log.json"))
    rows = d["games"]
    step = max(1, len(rows) // n_games)
    picks = rows[::step][:n_games]
    print(f"Anchor sample: {len(picks)} games (every {step}th of {len(rows)}).")
    out = []
    for i, (a_fac, b_fac, s, _w) in enumerate(picks):
        summ = replay_one(a_fac, b_fac, s)
        if summ is None:
            continue
        out.append(summ)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(picks)} done")
    path = "data/_sec_audit_anchor.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n": len(out), "games": out}, fh)
    secs = [x["sec_a"] for x in out] + [x["sec_b"] for x in out]
    print(f"Wrote {path} ({len(out)} games)")
    print(f"ANCHOR-WIDE mean secondary VP/player: {sum(secs)/len(secs):.2f} "
          f"(n={len(secs)} player-games)")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "anchor":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
        _anchor_sample(n)
        return
    n_per = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    _install_patches()

    opponents = ["Adeptus Astartes", "Aeldari", "Death Guard", "Orks",
                 "T'au Empire", "Necrons"]
    games = []
    seen = set()
    for cls, facs in CLASSES.items():
        for fac in facs:
            picked = 0
            for s in range(0, 40):
                if picked >= n_per:
                    break
                opp = opponents[(s + FAC_IDX[fac]) % len(opponents)]
                if opp == fac:
                    continue
                key = (fac, opp, s)
                if key in seen:
                    continue
                seen.add(key)
                games.append((cls, fac, opp, s))
                picked += 1

    print(f"Replaying {len(games)} stratified games ({n_per}/faction)...")
    out = []
    for i, (cls, fac, opp, s) in enumerate(games):
        summ = replay_one(fac, opp, s)
        if summ is None:
            continue
        summ["class"] = cls
        summ["focus"] = fac
        out.append(summ)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(games)} done")

    path = "data/_sec_audit_replay.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n": len(out), "games": out}, fh)
    print(f"Wrote {path} ({len(out)} games)")


if __name__ == "__main__":
    main()
