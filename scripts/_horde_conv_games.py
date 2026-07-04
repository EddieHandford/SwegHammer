"""READ-ONLY: print detailed round-by-round narratives for a few representative
horde-LOSS games (optionally restricted to the sc51a-win -> sc52a-loss crater
set when an OFF file is supplied), for the findings write-up.

Run: python -m scripts._horde_conv_games <focus> <on.json> [off.json] [n]
"""
from __future__ import annotations
import json, sys
from collections import defaultdict


def load(p):
    with open(p) as fh:
        return json.load(fh)


def fside(g, f):
    return "A" if g["a_fac"] == f else "B" if g["b_fac"] == f else None


def won(g, f):
    return g["winner"] == fside(g, f)


def key(g):
    return (g["a_fac"], g["b_fac"], g["s"])


def narrate(g, focus):
    side = fside(g, focus)
    osd = "B" if side == "A" else "A"
    opp_fac = g["b_fac"] if side == "A" else g["a_fac"]
    print("-" * 74)
    print(f"{focus} ({side}, {g['track_a'] if side=='A' else g['track_b']}) "
          f"vs {opp_fac} ({g['track_b'] if osd=='B' else g['track_a']})  s={g['s']}  "
          f"rounds={g['rounds']}  winner={g['winner']} "
          f"({'LOSS' if not won(g,focus) else 'WIN'})")
    hs = g["sec_a"] if side == "A" else g["sec_b"]
    os_ = g["sec_a"] if osd == "A" else g["sec_b"]
    hp = g["prim_a"] if side == "A" else g["prim_b"]
    op = g["prim_a"] if osd == "A" else g["prim_b"]
    print(f"  FINAL  {focus}: prim {hp} + sec {hs} (cap {g['cap_a'] if side=='A' else g['cap_b']})   "
          f"{opp_fac}: prim {op} + sec {os_} (cap {g['cap_b'] if osd=='B' else g['cap_a']})")
    oh = g["open_hand"].get(side)
    if oh:
        print(f"  {focus} opening hand: {oh[0]}  deck: {oh[1]}")
    # round-by-round hand + scores for the focus side
    scored = defaultdict(list)   # (round, army) -> [(card, vp)]
    for (rnd, army, card, vp, track) in g["cards"]:
        scored[(rnd, army)].append((card, vp))
    hand_by_round = {}
    for (rnd, army, hand) in g["hand_entry"]:
        if army == side:
            hand_by_round[rnd] = hand
    for rnd in range(1, (g["rounds"] or 5) + 1):
        h = hand_by_round.get(rnd)
        fs = scored.get((rnd, side), [])
        osx = scored.get((rnd, osd), [])
        fs_nz = [(c, v) for c, v in fs if v > 0]
        os_nz = [(c, v) for c, v in osx if v > 0]
        line = f"  R{rnd}:"
        if h is not None:
            line += f" hand={list(h)}"
        line += f"  {focus}+{sum(v for _,v in fs_nz)}={fs_nz}  {opp_fac}+{sum(v for _,v in os_nz)}={os_nz}"
        print(line)
    # actions
    af = {k: v for k, v in g["action_funnel"].items() if k.startswith(("A|", "B|"))}
    name = "A" if side == "A" else "B"
    mine = {k.split("|", 1)[1]: v for k, v in af.items() if k.split("|", 1)[0] == name}
    if mine:
        print(f"  {focus} action funnel (assign@score/completed/VP/calls): {mine}")
    print(f"  {focus} assign(mv): "
          f"{ {k.split('|',1)[1]: v for k,v in g['assign'].items() if k.split('|',1)[0]==name and v} }")


def main():
    focus = sys.argv[1]
    on = load(sys.argv[2])
    off = load(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    on_by = {key(g): g for g in on["games"]
             if not g.get("empty") and fside(g, focus)}
    crater = []
    if off:
        off_by = {key(g): g for g in off["games"]
                  if not g.get("empty") and fside(g, focus)}
        for k, g in on_by.items():
            go = off_by.get(k)
            if go is not None and won(go, focus) and not won(g, focus):
                crater.append(g)
        pool = crater
        print(f"Crater (sc51a-win -> sc52a-loss) games: {len(crater)}. Showing {n} spread.")
    else:
        pool = [g for g in on_by.values() if not won(g, focus)]
        print(f"Loss games: {len(pool)}. Showing {n} spread.")

    if not pool:
        print("none")
        return
    step = max(1, len(pool) // n)
    for g in pool[::step][:n]:
        narrate(g, focus)


if __name__ == "__main__":
    main()
