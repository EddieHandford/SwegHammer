"""READ-ONLY horde secondary-conversion replay.

Reconstructs the Orks / Genestealer Cults (and, on request, a comparison elite
like Adepta Sororitas) games recorded in the standing anchor
data/_anchor_sc52a_n80_log.json, exactly as scripts._ec_crater_replay /
scripts._sec_audit_replay build them (the canonical construction), verifies the
replayed winner reproduces the anchor's recorded winner (the mandatory gate),
and captures the full per-game secondary economy:

  * every card scored by EITHER army (round, army, card, vp, track) -> lets the
    analysis attribute opponent secondary VP to horde-specific cards
    (cull_the_horde / bring_it_down / marked_for_death) vs generic cards.
  * the held Tactical hand at each round's scoring (held-but-whiffed).
  * cleanse / sabotage / establish_locus / recover_assets ASSIGNMENT counts and,
    at score time, how many assigned units survived to COMPLETE and the VP the
    action realised (assign -> complete -> score funnel).
  * the voluntary-discard "cannot pay" verdicts per card per round, and the
    New Orders structural-dead discards -> the shedding-heuristic audit.
  * opening hand + deck, deck left undrawn, final primary/secondary split.

Reads env GATE STATE at runtime (the gates are os.environ.get each call), so run
this script twice: once with committed defaults (sc52a, all six fixes on) and
once with the five kill-switches off (== sc51a, the pre-fix substrate) to obtain
the before/after per-game comparison the channel split needs.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._horde_conv_replay \
        <comma-factions> <out.json> [max_games]

Nothing here mutates tracked files.
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._horde_conv_replay"]
                            + sys.argv[1:], env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

ANCHOR = "data/_anchor_sc52a_n80_log.json"

GATE_VARS = ["SWEG_TAC_SHEDDING", "SWEG_ACTIONS_HAND_GATED", "SWEG_TACDECK_FULL",
             "SWEG_FIXED_POOL_FULL", "SWEG_CP_PER_COMMAND_PHASE"]

CUR = {}


def _reset_capture():
    CUR.clear()
    CUR["cards"] = []          # (round, army_name, card, vp, track)
    CUR["hand_entry"] = []     # (round, army_name, tuple(hand))
    CUR["open_hand"] = {}      # army_name -> (hand, deck)
    CUR["assign"] = defaultdict(int)     # (army_name, action) -> units flagged
    # action funnel at score time: (army_name, card) -> [assigned_alive, completed, vp, calls]
    CUR["action_funnel"] = defaultdict(lambda: [0, 0, 0, 0])
    CUR["cannot_pay"] = []     # (round, army_name, card, verdict_bool)
    CUR["new_orders"] = []     # (round, army_name, card_discarded)


def _install_patches():
    if getattr(Battle, "_horde_conv_patched", False):
        return
    Battle._horde_conv_patched = True

    orig_score_one = Battle._score_one_card
    orig_score_hand = Battle._score_tactical_hand
    orig_init_deck = Battle._init_tactical_deck
    orig_assign_cleanse = Battle._assign_cleanse_actions
    orig_assign_sabotage = Battle._assign_sabotage_actions
    orig_cannot_pay = Battle._tac_discard_card_cannot_pay
    orig_new_orders = Battle._apply_new_orders
    orig_score_cleanse = Battle._score_cleanse
    orig_score_sabotage = Battle._score_sabotage
    orig_score_locus = Battle._score_establish_locus
    orig_score_recover = Battle._score_recover_assets

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

    def cannot_pay(self, card_key, army, other_army, own_is_army_a, round_num):
        v = orig_cannot_pay(self, card_key, army, other_army, own_is_army_a, round_num)
        CUR["cannot_pay"].append((round_num, army.name, card_key, bool(v)))
        return v

    def new_orders(self, army, other, own_is_a, round_num):
        hand_before = list(getattr(army, "tactical_hand", ()) or ())
        orig_new_orders(self, army, other, own_is_a, round_num)
        hand_after = list(getattr(army, "tactical_hand", ()) or ())
        for c in hand_before:
            if c not in hand_after:
                CUR["new_orders"].append((round_num, army.name, c))

    def _funnel(self, army, card, score_fn, *a, **k):
        # count units with this action still alive at score time (completed the
        # movement->end-of-turn survival), and the VP realised.
        act = card if card in ("cleanse", "sabotage") else None
        vp = score_fn(self, army, *a, **k)
        rec = CUR["action_funnel"][(army.name, card)]
        rec[3] += 1
        rec[2] += vp
        if act is not None:
            alive_with = sum(1 for u in army.alive_units
                             if getattr(u, "action_this_round", None) == act)
            rec[0] += alive_with
            try:
                completed = sum(1 for u in army.alive_units
                                if getattr(u, "action_this_round", None) == act
                                and self._action_completes(u, a[0] if a else None))
            except Exception:
                completed = alive_with
            rec[1] += completed
        return vp

    def score_cleanse(self, army, opponent, own_is_army_a, chosen_override=None):
        return _funnel(self, army, "cleanse", orig_score_cleanse, opponent,
                       own_is_army_a=own_is_army_a, chosen_override=chosen_override)

    def score_sabotage(self, army, own_is_army_a, chosen_override=None, opponent=None):
        vp = orig_score_sabotage(self, army, own_is_army_a=own_is_army_a,
                                 chosen_override=chosen_override, opponent=opponent)
        rec = CUR["action_funnel"][(army.name, "sabotage")]
        rec[3] += 1
        rec[2] += vp
        alive_with = sum(1 for u in army.alive_units
                         if getattr(u, "action_this_round", None) == "sabotage")
        rec[0] += alive_with
        try:
            completed = sum(1 for u in army.alive_units
                            if getattr(u, "action_this_round", None) == "sabotage"
                            and self._action_completes(u, opponent))
        except Exception:
            completed = alive_with
        rec[1] += completed
        return vp

    def score_locus(self, army, opponent, own_is_army_a, chosen_override=None):
        vp = orig_score_locus(self, army, opponent, own_is_army_a=own_is_army_a,
                              chosen_override=chosen_override)
        rec = CUR["action_funnel"][(army.name, "establish_locus")]
        rec[3] += 1
        rec[2] += vp
        return vp

    def score_recover(self, army, opponent, own_is_army_a, chosen_override=None):
        vp = orig_score_recover(self, army, opponent, own_is_army_a=own_is_army_a,
                                chosen_override=chosen_override)
        rec = CUR["action_funnel"][(army.name, "recover_assets")]
        rec[3] += 1
        rec[2] += vp
        return vp

    Battle._score_one_card = score_one
    Battle._score_tactical_hand = score_hand
    Battle._init_tactical_deck = init_deck
    Battle._assign_cleanse_actions = assign_cleanse
    Battle._assign_sabotage_actions = assign_sabotage
    Battle._tac_discard_card_cannot_pay = cannot_pay
    Battle._apply_new_orders = new_orders
    Battle._score_cleanse = score_cleanse
    Battle._score_sabotage = score_sabotage
    Battle._score_establish_locus = score_locus
    Battle._score_recover_assets = score_recover


def _worker(job):
    _install_patches()
    a_fac, b_fac, s, w = job
    return replay_one(a_fac, b_fac, s, w)


def replay_one(a_fac, b_fac, s, recorded_winner):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return {"a_fac": a_fac, "b_fac": b_fac, "s": s,
                "recorded_winner": recorded_winner, "winner": None,
                "match": recorded_winner is None, "empty": True}
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    _reset_capture()
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=primary)
    result = battle.run()
    return _summarise(a_fac, b_fac, s, recorded_winner, a, b, battle, result)


def _summarise(a_fac, b_fac, s, recorded_winner, a, b, battle, result):
    winner = result.winner if result else None
    sec_a = battle._a_secondary_vp
    sec_b = battle._b_secondary_vp
    chal_a = getattr(battle, "_a_challenger_vp", 0)
    chal_b = getattr(battle, "_b_challenger_vp", 0)
    prim_a = battle._a_vp - sec_a - chal_a
    prim_b = battle._b_vp - sec_b - chal_b
    a_cap, b_cap = battle._capped_vp_pair()
    return {
        "a_fac": a_fac, "b_fac": b_fac, "s": s,
        "recorded_winner": recorded_winner, "winner": winner,
        "match": winner == recorded_winner,
        "rounds": result.rounds if result else None,
        "track_a": getattr(a, "secondary_track", None) or "FIXED",
        "track_b": getattr(b, "secondary_track", None) or "FIXED",
        "sec_a": sec_a, "sec_b": sec_b,
        "prim_a": prim_a, "prim_b": prim_b,
        "chal_a": chal_a, "chal_b": chal_b,
        "cap_a": a_cap, "cap_b": b_cap,
        "name_a": a.name, "name_b": b.name,
        "cards": CUR["cards"],
        "hand_entry": [(r, n, list(h)) for (r, n, h) in CUR["hand_entry"]],
        "open_hand": {k: [list(v[0]), list(v[1])] for k, v in CUR["open_hand"].items()},
        "deck_left_a": list(getattr(a, "tactical_deck", ()) or ()),
        "deck_left_b": list(getattr(b, "tactical_deck", ()) or ()),
        "hand_left_a": list(getattr(a, "tactical_hand", ()) or ()),
        "hand_left_b": list(getattr(b, "tactical_hand", ()) or ()),
        "assign": {f"{k[0]}|{k[1]}": v for k, v in CUR["assign"].items()},
        "action_funnel": {f"{k[0]}|{k[1]}": list(v)
                          for k, v in CUR["action_funnel"].items()},
        "cannot_pay": CUR["cannot_pay"],
        "new_orders": CUR["new_orders"],
    }


def main():
    if len(sys.argv) < 3:
        print("usage: _horde_conv_replay <comma-factions> <out.json> [max_games]")
        sys.exit(2)
    focus = set(sys.argv[1].split(","))
    out_path = sys.argv[2]
    max_games = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    workers = int(os.environ.get("SWEG_WORKERS", "0")) or max(1, int((os.cpu_count() or 2) * 0.85))

    d = json.load(open(ANCHOR))
    rows = [g for g in d["games"] if g[0] in focus or g[1] in focus]
    if max_games:
        # even stride so a capped run still spreads across seeds/opponents
        step = max(1, len(rows) // max_games)
        rows = rows[::step][:max_games]
    print(f"Focus {sorted(focus)}: {len(rows)} anchor games to replay on {workers} workers.")
    print("Gate state: " + ", ".join(f"{v}={os.environ.get(v,'(default-on)')}"
                                      for v in GATE_VARS))
    sys.stdout.flush()

    out = []
    matched = 0
    mismatches = []
    if workers <= 1:
        _install_patches()
        results_iter = map(_worker, rows)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        results_iter = executor.map(_worker, rows, chunksize=4)
    for i, summ in enumerate(results_iter):
        out.append(summ)
        if summ.get("match"):
            matched += 1
        elif not summ.get("empty"):
            mismatches.append(summ)
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(rows)} done ({matched} matched)")
            sys.stdout.flush()

    print(f"\nREPRODUCTION: {matched}/{len(rows)} winners matched "
          f"({len(mismatches)} mismatches).")
    for m in mismatches[:15]:
        print(f"  MISMATCH {m['a_fac']} vs {m['b_fac']} s={m['s']}: "
              f"rec={m['recorded_winner']} replay={m['winner']}")

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"n": len(out), "matched": matched,
                   "mismatches": len(mismatches),
                   "gates": {v: os.environ.get(v, "1") for v in GATE_VARS},
                   "games": out}, fh)
    print(f"Wrote {out_path} ({len(out)} games)")


if __name__ == "__main__":
    main()
