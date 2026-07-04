"""READ-ONLY analysis of the horde secondary-conversion replays.

Consumes the JSON written by scripts._horde_conv_replay for a focus horde
(Orks / Genestealer Cults) under the committed sc52a defaults (ON) and under the
five secondary-economy kill-switches (OFF == sc51a), plus an elite comparison
(Adepta Sororitas, ON), and reports:

  1. reproduction gate (ON winners vs the sc52a anchor);
  2. the focus faction's cell win-rate ON vs OFF (must reproduce the crater);
  3. the winner-flip census (win->loss / loss->win between sc51a and sc52a);
  4. the secondary decomposition and the two-channel split
     (opponent-armed-against-me vs I-cannot-convert), with numbers;
  5. action-conversion funnels (assign -> complete -> score) for the horde vs
     the elite;
  6. the shedding-heuristic audit (which cards the voluntary-discard/New Orders
     path flags dead, and whether it costs the horde its own scoring).

Run: python -m scripts._horde_conv_analyze <focus_faction> <on.json> <off.json> [elite.json]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

HORDE_TARGET_CARDS = ("cull_the_horde", "bring_it_down", "marked_for_death",
                      "no_prisoners", "assassination", "overwhelming_force")
ACTION_CARDS = ("cleanse", "sabotage", "establish_locus", "recover_assets")


def load(path):
    with open(path) as fh:
        return json.load(fh)


def focus_side(g, focus):
    if g["a_fac"] == focus:
        return "A"
    if g["b_fac"] == focus:
        return "B"
    return None


def focus_won(g, focus):
    side = focus_side(g, focus)
    return g["winner"] == side


def sec_of(g, side):
    return g["sec_a"] if side == "A" else g["sec_b"]


def prim_of(g, side):
    return g["prim_a"] if side == "A" else g["prim_b"]


def opp_side(side):
    return "B" if side == "A" else "A"


def card_vp_by_army(g):
    """(army_side, card) -> total vp scored across the game."""
    out = defaultdict(float)
    for (rnd, army, card, vp, track) in g["cards"]:
        out[(army, card)] += vp
    return out


def key_by_seed(games, focus):
    d = {}
    for g in games:
        if g.get("empty"):
            continue
        if focus_side(g, focus) is None:
            continue
        d[(g["a_fac"], g["b_fac"], g["s"])] = g
    return d


def winrate(games, focus):
    n = w = 0
    for g in games:
        if g.get("empty") or focus_side(g, focus) is None:
            continue
        n += 1
        if focus_won(g, focus):
            w += 1
    return w, n, (100.0 * w / n if n else 0.0)


def official_winrate(games, focus):
    """Reproduce scripts.evaluate_vs_meta's per-faction number: the focus faction
    as SIDE A ONLY, per-opponent win-rate, field-weighted by each opponent's
    tournament prevalence (TOURNAMENT_GAMES). This is the convention the reported
    sc51a/sc52a win-rates and the -3.78/-3.94 crater use."""
    with open("data/warpfriends_rolling.json") as fh:
        _wf = json.load(fh)["factions"]
    TOURNAMENT_GAMES = {f: int(v["total_games"]) for f, v in _wf.items()}
    pair = {}   # opp -> [winsA, total]
    for g in games:
        if g.get("empty"):
            continue
        if g["a_fac"] != focus:
            continue  # focus must be side A (eval convention)
        opp = g["b_fac"]
        rec = pair.setdefault(opp, [0, 0])
        rec[1] += 1
        if g["winner"] == "A":
            rec[0] += 1
    num = den = 0.0
    for opp, (wa, tot) in pair.items():
        if tot == 0:
            continue
        wpct = 100.0 * wa / tot
        wgt = TOURNAMENT_GAMES[opp]
        num += wpct * wgt
        den += wgt
    return (num / den if den else 0.0), pair


def report(focus, on, off, elite=None):
    print("=" * 78)
    print(f"HORDE SECONDARY-CONVERSION ANALYSIS — focus = {focus}")
    print("=" * 78)

    on_games = on["games"]
    off_games = off["games"] if off else None

    # 1. reproduction gate
    print("\n[1] REPRODUCTION GATE (ON defaults vs sc52a anchor)")
    print(f"    matched {on['matched']}/{on['n']}  mismatches={on['mismatches']}")

    # 2. win-rate ON vs OFF
    ow, on_n, on_wr = winrate(on_games, focus)
    on_off_wr, _ = official_winrate(on_games, focus)
    print(f"\n[2] {focus} CELL WIN-RATE")
    print(f"    ON  (sc52a): pooled(both sides) {ow}/{on_n} = {on_wr:.2f}%  |  "
          f"OFFICIAL(as-A, field-weighted) = {on_off_wr:.2f}%")
    if off_games:
        fw, off_n, off_wr = winrate(off_games, focus)
        off_off_wr, _ = official_winrate(off_games, focus)
        print(f"    OFF (sc51a): pooled(both sides) {fw}/{off_n} = {off_wr:.2f}%  |  "
              f"OFFICIAL(as-A, field-weighted) = {off_off_wr:.2f}%")
        print(f"    CRATER pooled (ON-OFF): {on_wr-off_wr:+.2f} pts  |  "
              f"OFFICIAL (ON-OFF): {on_off_wr-off_off_wr:+.2f} pts")

    on_by = key_by_seed(on_games, focus)
    off_by = key_by_seed(off_games, focus) if off_games else {}

    # 3. flip census
    flips_wl = []   # win in OFF, loss in ON  (the crater games)
    flips_lw = []   # loss in OFF, win in ON
    common = 0
    for k, g_on in on_by.items():
        g_off = off_by.get(k)
        if g_off is None:
            continue
        common += 1
        won_on = focus_won(g_on, focus)
        won_off = focus_won(g_off, focus)
        if won_off and not won_on:
            flips_wl.append(k)
        elif won_on and not won_off:
            flips_lw.append(k)
    if off_games:
        print(f"\n[3] WINNER-FLIP CENSUS (paired seeds, n={common})")
        print(f"    OFF-win -> ON-loss (crater losses): {len(flips_wl)}")
        print(f"    OFF-loss -> ON-win (fix helped):    {len(flips_lw)}")
        print(f"    net swing: {len(flips_lw)-len(flips_wl):+d} games "
              f"({100.0*(len(flips_lw)-len(flips_wl))/common:+.2f} pts of the cell)")

    # 4. secondary decomposition + two-channel split
    def agg_secondary(games_by):
        n = 0
        h_sec = o_sec = h_prim = o_prim = 0.0
        opp_card = defaultdict(float)
        own_card = defaultdict(float)
        opp_cull_by_track = defaultdict(float)
        for k, g in games_by.items():
            side = focus_side(g, focus)
            osd = opp_side(side)
            n += 1
            h_sec += sec_of(g, side)
            o_sec += sec_of(g, osd)
            h_prim += prim_of(g, side)
            o_prim += prim_of(g, osd)
            cvp = card_vp_by_army(g)
            for (army, card), vp in cvp.items():
                if army == osd:
                    opp_card[card] += vp
                    if card == "cull_the_horde":
                        opp_cull_by_track[g["track_b" if osd == "B" else "track_a"]] += vp
                elif army == side:
                    own_card[card] += vp
        return n, h_sec, o_sec, h_prim, o_prim, opp_card, own_card, opp_cull_by_track

    print(f"\n[4] SECONDARY DECOMPOSITION (per game, focus vs opponent)")
    non, nh_sec, no_sec, nh_prim, no_prim, on_opp_card, on_own_card, on_cull_tr = agg_secondary(on_by)
    print(f"    ON : horde_sec={nh_sec/non:.2f}  opp_sec={no_sec/non:.2f}  "
          f"horde_prim={nh_prim/non:.2f}  opp_prim={no_prim/non:.2f}  (n={non})")
    if off_by:
        # restrict to common seeds for a clean paired delta
        com = {k: off_by[k] for k in on_by if k in off_by}
        fon = {k: on_by[k] for k in on_by if k in off_by}
        n2, fh_sec, fo_sec, fh_prim, fo_prim, off_opp_card, off_own_card, off_cull_tr = agg_secondary(com)
        _, ph_sec, po_sec, ph_prim, po_prim, pon_opp_card, pon_own_card, pon_cull_tr = agg_secondary(fon)
        print(f"    OFF: horde_sec={fh_sec/n2:.2f}  opp_sec={fo_sec/n2:.2f}  "
              f"horde_prim={fh_prim/n2:.2f}  opp_prim={fo_prim/n2:.2f}  (n={n2})")
        d_h = (ph_sec - fh_sec) / n2
        d_o = (po_sec - fo_sec) / n2
        print(f"    Δ horde_sec (ON-OFF): {d_h:+.2f}/game")
        print(f"    Δ opp_sec   (ON-OFF): {d_o:+.2f}/game")
        print(f"    NET secondary swing for horde (Δh - Δo): {d_h - d_o:+.2f}/game")
        print(f"      >>> CHANNEL A 'opponent armed against me' = opp_sec rose {d_o:+.2f}/game")
        print(f"      >>> CHANNEL B 'I cannot convert' = horde_sec moved only {d_h:+.2f}/game")

        # opponent card deltas (what the deck handed the opponent)
        print(f"\n    OPPONENT secondary VP/game by card (ON vs OFF, Δ):")
        allcards = sorted(set(pon_opp_card) | set(off_opp_card),
                          key=lambda c: -(pon_opp_card.get(c, 0) - off_opp_card.get(c, 0)))
        for c in allcards:
            on_v = pon_opp_card.get(c, 0) / n2
            off_v = off_opp_card.get(c, 0) / n2
            if abs(on_v) < 0.01 and abs(off_v) < 0.01:
                continue
            tag = "  <== HORDE-TARGET" if c in HORDE_TARGET_CARDS else ""
            print(f"      {c:24s} ON {on_v:5.2f}  OFF {off_v:5.2f}  Δ {on_v-off_v:+5.2f}{tag}")
        print(f"    opp cull_the_horde by opp-track (ON): {dict(on_cull_tr)}")

        print(f"\n    FOCUS-OWN secondary VP/game by card (ON vs OFF, Δ):")
        allown = sorted(set(pon_own_card) | set(off_own_card),
                        key=lambda c: -(pon_own_card.get(c, 0) - off_own_card.get(c, 0)))
        for c in allown:
            on_v = pon_own_card.get(c, 0) / n2
            off_v = off_own_card.get(c, 0) / n2
            if abs(on_v) < 0.01 and abs(off_v) < 0.01:
                continue
            tag = "  (action)" if c in ACTION_CARDS else ""
            print(f"      {c:24s} ON {on_v:5.2f}  OFF {off_v:5.2f}  Δ {on_v-off_v:+5.2f}{tag}")

        # split on the crater (win->loss) games specifically
        if flips_wl:
            nfl = len(flips_wl)
            dh = do = 0.0
            cull_gain = 0.0
            for k in flips_wl:
                g_on, g_off = on_by[k], off_by[k]
                side = focus_side(g_on, focus)
                osd = opp_side(side)
                dh += sec_of(g_on, side) - sec_of(g_off, side)
                do += sec_of(g_on, osd) - sec_of(g_off, osd)
                cvp_on = card_vp_by_army(g_on)
                cvp_off = card_vp_by_army(g_off)
                cull_gain += cvp_on.get((osd, "cull_the_horde"), 0) - cvp_off.get((osd, "cull_the_horde"), 0)
            print(f"\n    ON THE {nfl} CRATER (win->loss) GAMES:")
            print(f"      Δ horde_sec {dh/nfl:+.2f}/game   Δ opp_sec {do/nfl:+.2f}/game")
            print(f"      of which opp cull_the_horde gain: {cull_gain/nfl:+.2f}/game")

    # 5. action conversion funnels
    def agg_funnel(games, who):
        tot = defaultdict(lambda: [0, 0, 0, 0])  # assigned, completed, vp, calls
        assign = defaultdict(int)
        for g in games:
            if g.get("empty"):
                continue
            if who is not None and focus_side(g, who) is None:
                continue
            side = focus_side(g, who) if who else None
            name = g["name_a"] if side == "A" else g["name_b"] if side == "B" else None
            for key, rec in g["action_funnel"].items():
                army, card = key.split("|", 1)
                if name is not None and army != name:
                    continue
                t = tot[card]
                t[0] += rec[0]; t[1] += rec[1]; t[2] += rec[2]; t[3] += rec[3]
            for key, v in g["assign"].items():
                army, card = key.split("|", 1)
                if name is not None and army != name:
                    continue
                assign[card] += v
        return tot, assign

    print(f"\n[5] ACTION CONVERSION FUNNEL — {focus} (ON)")
    ftot, fassign = agg_funnel(on_games, focus)
    _print_funnel(ftot, fassign)
    if elite:
        el_fac = elite.get("focus_faction") or _detect_focus(elite)
        print(f"\n    ELITE COMPARISON — {el_fac} (ON)")
        etot, eassign = agg_funnel(elite["games"], el_fac)
        _print_funnel(etot, eassign)

    # 6. shedding-heuristic audit
    print(f"\n[6] SHEDDING-HEURISTIC AUDIT — {focus} (ON)")
    cp_true = defaultdict(int)
    cp_all = defaultdict(int)
    no_disc = defaultdict(int)
    for g in on_games:
        if g.get("empty"):
            continue
        side = focus_side(g, focus)
        name = g["name_a"] if side == "A" else g["name_b"]
        for (rnd, army, card, verdict) in g["cannot_pay"]:
            if army != name:
                continue
            cp_all[card] += 1
            if verdict:
                cp_true[card] += 1
        for (rnd, army, card) in g["new_orders"]:
            if army == name:
                no_disc[card] += 1
    print("    voluntary-discard 'cannot_pay' verdicts (card: TRUE/total probes):")
    for c in sorted(cp_all, key=lambda c: -cp_true[c]):
        if cp_true[c] == 0:
            continue
        print(f"      {c:24s} flagged-dead {cp_true[c]:5d} / {cp_all[c]:5d} probes"
              f"{'  (action)' if c in ACTION_CARDS else ''}")
    print("    New Orders structural-dead discards (card: count):")
    for c in sorted(no_disc, key=lambda c: -no_disc[c]):
        print(f"      {c:24s} {no_disc[c]}")


def _print_funnel(tot, assign):
    print(f"      {'card':20s} {'assign(mv)':>10s} {'alive@score':>11s} "
          f"{'completed':>10s} {'VP':>8s} {'VP/assign':>9s}")
    for c in ("cleanse", "sabotage", "establish_locus", "recover_assets"):
        rec = tot.get(c, [0, 0, 0, 0])
        a = assign.get(c, 0)
        vp = rec[2]
        conv = (vp / a) if a else 0.0
        print(f"      {c:20s} {a:10d} {rec[0]:11d} {rec[1]:10d} {vp:8.0f} {conv:9.3f}")


def _detect_focus(blob):
    # infer the single faction all games share
    facs = set()
    for g in blob["games"][:50]:
        facs.add(g["a_fac"]); facs.add(g["b_fac"])
    # the focus is the one present in ALL games
    from collections import Counter
    c = Counter()
    for g in blob["games"]:
        c[g["a_fac"]] += 1; c[g["b_fac"]] += 1
    return c.most_common(1)[0][0]


def main():
    focus = sys.argv[1]
    on = load(sys.argv[2])
    off = load(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    elite = load(sys.argv[4]) if len(sys.argv) > 4 else None
    report(focus, on, off, elite)


if __name__ == "__main__":
    main()
