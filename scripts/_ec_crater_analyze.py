"""Read-only diagnostic: aggregate the per-game data written by
scripts._ec_crater_replay (data/_ec_crater_games.json) into the loss-mechanism
breakdown for the Astra Militarum vs Emperor's Children crater.

Run: PYTHONIOENCODING=utf-8 python -m scripts._ec_crater_analyze
"""
from __future__ import annotations

import json
import statistics
from collections import Counter


def main():
    with open("data/_ec_crater_games.json", "r", encoding="utf-8") as fh:
        data = json.load(fh)
    games = data["games"]
    print(f"n_games={data['n_games']} matched={data['matched']} mismatches={data['mismatches']}\n")

    am_wins = [g for g in games if g.get("match") and (
        (g["a_fac"] == "Astra Militarum" and g["recorded_winner"] == "A")
        or (g["b_fac"] == "Astra Militarum" and g["recorded_winner"] == "B")
    )]
    am_losses = [g for g in games if g.get("match") and (
        (g["a_fac"] == "Astra Militarum" and g["recorded_winner"] == "B")
        or (g["b_fac"] == "Astra Militarum" and g["recorded_winner"] == "A")
    )]
    draws = [g for g in games if g.get("match") and g["recorded_winner"] is None]
    print(f"Astra Militarum record: {len(am_wins)} wins / {len(am_losses)} losses / {len(draws)} draws "
          f"(win rate {100*len(am_wins)/len(games):.1f}%)\n")

    # -------------------------------------------------------------
    # Margin distribution: capped VP margin, primary vs secondary split
    # -------------------------------------------------------------
    margins = []
    primary_margins = []
    secondary_margins = []
    wipes = 0          # AM ends with 0 survivors
    ec_wipes = 0        # EC ends with 0 survivors (AM still lost on VP!)
    scoring_losses = 0  # neither side wiped, decided on VP
    for g in am_losses:
        margin = g["ec_capped"] - g["am_capped"]
        margins.append(margin)
        primary_margins.append(g["ec_primary"] - g["am_primary"])
        secondary_margins.append(g["ec_secondary"] - g["am_secondary"])
        if g["am_survivors"] == 0:
            wipes += 1
        if g["ec_survivors"] == 0:
            ec_wipes += 1
        if g["am_survivors"] > 0 and g["ec_survivors"] > 0:
            scoring_losses += 1

    print("=== MARGIN / SCORE BREAKDOWN (Astra Militarum losses) ===")
    print(f"  mean capped VP margin (Emperor's Children - Astra Militarum): {statistics.mean(margins):.2f}")
    print(f"  median margin: {statistics.median(margins):.2f}  "
          f"min={min(margins)} max={max(margins)}")
    print(f"  mean primary-VP margin:   {statistics.mean(primary_margins):.2f}")
    print(f"  mean secondary-VP margin: {statistics.mean(secondary_margins):.2f}")
    print(f"  Astra Militarum tabled to zero survivors: {wipes}/{len(am_losses)}")
    print(f"  Emperor's Children tabled to zero survivors (but still won on VP): {ec_wipes}/{len(am_losses)}")
    print(f"  Neither side wiped (pure scoring loss): {scoring_losses}/{len(am_losses)}")
    print()

    # -------------------------------------------------------------
    # Contrast: the 29 Astra Militarum wins -- what does the margin/board
    # look like when Astra Militarum DOES win this matchup?
    # -------------------------------------------------------------
    if am_wins:
        win_margins = [g["am_capped"] - g["ec_capped"] for g in am_wins]
        print("=== CONTRAST: THE 29 ASTRA MILITARUM WINS ===")
        print(f"  mean capped VP margin (Astra Militarum - Emperor's Children): "
              f"{statistics.mean(win_margins):.2f}  (median {statistics.median(win_margins):.2f})")
        win_am_surv_rate = statistics.mean(g["am_survivors"]/g["am_start"] for g in am_wins)
        win_ec_surv_rate = statistics.mean(g["ec_survivors"]/g["ec_start"] for g in am_wins)
        print(f"  mean Astra Militarum survivor fraction: {win_am_surv_rate:.2f}")
        print(f"  mean Emperor's Children survivor fraction: {win_ec_surv_rate:.2f}\n")

    # -------------------------------------------------------------
    # Round reached
    # -------------------------------------------------------------
    rounds = [g["rounds"] for g in am_losses]
    print(f"Rounds played in losses: mean={statistics.mean(rounds):.2f} "
          f"(distribution: {Counter(rounds)})\n")

    # -------------------------------------------------------------
    # Casualties by round
    # -------------------------------------------------------------
    deaths_by_round_total = Counter()
    for g in am_losses:
        for rnd, n in g["am_deaths_by_round"].items():
            deaths_by_round_total[int(rnd)] += n
    print("=== ASTRA MILITARUM CASUALTIES BY ROUND (summed across all losses) ===")
    for rnd in sorted(deaths_by_round_total):
        print(f"  round {rnd}: {deaths_by_round_total[rnd]} units killed")
    total_am_start = sum(g["am_start"] for g in am_losses)
    total_am_surv = sum(g["am_survivors"] for g in am_losses)
    total_ec_start = sum(g["ec_start"] for g in am_losses)
    total_ec_surv = sum(g["ec_survivors"] for g in am_losses)
    print(f"  total Astra Militarum starting units across losses: {total_am_start}")
    print(f"  total Astra Militarum survivors at game end:         {total_am_surv}")
    print(f"  overall Astra Militarum attrition rate: {100*(1 - total_am_surv/total_am_start):.1f}%")
    print(f"  total Emperor's Children starting units across losses: {total_ec_start}")
    print(f"  total Emperor's Children survivors at game end:         {total_ec_surv}")
    print(f"  overall Emperor's Children attrition rate: {100*(1 - total_ec_surv/total_ec_start):.1f}%")
    print(f"  mean absolute am_capped: {statistics.mean(g['am_capped'] for g in am_losses):.2f}")
    print(f"  mean absolute ec_capped: {statistics.mean(g['ec_capped'] for g in am_losses):.2f}\n")

    # -------------------------------------------------------------
    # Kill source attribution (which Emperor's Children unit killed the most
    # Astra Militarum units, across all losses)
    # -------------------------------------------------------------
    kill_totals = Counter()
    for g in am_losses:
        for name, n in g["kill_source_counts"].items():
            kill_totals[name] += n
    print("=== KILL SOURCE ATTRIBUTION (Emperor's Children unit -> Astra Militarum kills, all losses) ===")
    for name, n in kill_totals.most_common(20):
        print(f"  {name:35s} {n:4d} kills")
    print(f"  TOTAL attributed kills: {sum(kill_totals.values())}  "
          f"(vs {total_am_start - total_am_surv} total Astra Militarum deaths)\n")

    # -------------------------------------------------------------
    # Damage dealt: Emperor's Children unit -> Astra Militarum, and
    # Astra Militarum unit -> Emperor's Children (does Astra Militarum's
    # shooting ever meaningfully engage the Emperor's Children bricks?)
    # -------------------------------------------------------------
    ec_damage_totals = Counter()
    am_damage_totals = Counter()
    for g in am_losses:
        for name, dmg in g["ec_damage_by_unit"].items():
            ec_damage_totals[name] += dmg
        for name, dmg in g["am_damage_by_unit"].items():
            am_damage_totals[name] += dmg
    print("=== DAMAGE DEALT: Emperor's Children unit -> Astra Militarum (all losses, summed) ===")
    for name, dmg in ec_damage_totals.most_common(20):
        print(f"  {name:35s} {dmg:8.1f} damage")
    print(f"  TOTAL Emperor's Children damage dealt: {sum(ec_damage_totals.values()):.1f}\n")

    print("=== DAMAGE DEALT: Astra Militarum unit -> Emperor's Children (all losses, summed) ===")
    for name, dmg in am_damage_totals.most_common(30):
        print(f"  {name:35s} {dmg:8.1f} damage")
    print(f"  TOTAL Astra Militarum damage dealt: {sum(am_damage_totals.values()):.1f}\n")

    # Specifically: damage against the named Lord Exultant / Defiler / Noise
    # Marines pillar the task brief names.
    pillar_names = ["Lord Exultant", "Defiler", "Noise Marines"]
    print("=== ASTRA MILITARUM DAMAGE AGAINST THE NAMED EMPEROR'S CHILDREN PILLAR ===")
    for pn in pillar_names:
        # Damage dealt BY Astra Militarum units TO this pillar isn't broken out
        # per-target in am_damage_by_unit (that dict is keyed by attacker, not
        # target) -- see the ec side's own totals for how much this pillar
        # ABSORBED as a proxy for "was it engaged at all" via its damage-dealt
        # ranking (attacker-name key on EC damage tells us EC's own output, not
        # what it received). Cross-checked instead against kill counts below.
        n_kills = kill_totals.get(pn, 0)
        print(f"  {pn:20s} credited with {n_kills} Astra Militarum kills across {len(am_losses)} losses")
    print()

    # -------------------------------------------------------------
    # Objective control at rounds 2-4
    # -------------------------------------------------------------
    print("=== OBJECTIVE HOLDER AT ROUNDS 2-4 (fraction of losses where Emperor's Children holds more objectives) ===")
    for rnd in (2, 3, 4):
        am_more, ec_more, tied, n_games_with_round = 0, 0, 0, 0
        for g in am_losses:
            am_side = g["am_side"]
            ec_side = g["ec_side"]
            holders = g["obj_holder_by_round"].get(str(rnd)) or g["obj_holder_by_round"].get(rnd)
            if not holders:
                continue
            n_games_with_round += 1
            am_count = sum(1 for _, army in holders if army == am_side)
            ec_count = sum(1 for _, army in holders if army == ec_side)
            if am_count > ec_count:
                am_more += 1
            elif ec_count > am_count:
                ec_more += 1
            else:
                tied += 1
        if n_games_with_round:
            print(f"  round {rnd} ({n_games_with_round} games reached): "
                  f"Astra Militarum ahead on objectives {am_more}, "
                  f"Emperor's Children ahead {ec_more}, tied {tied}")
    print()

    # -------------------------------------------------------------
    # Sample list of the worst / most representative losses for deep-dive.
    # -------------------------------------------------------------
    print("=== CANDIDATE GAMES FOR DEEP-DIVE (sorted by margin, then by round) ===")
    sorted_losses = sorted(am_losses, key=lambda g: (g["ec_capped"] - g["am_capped"]))
    for g in sorted_losses[:8]:
        print(f"  a_fac={g['a_fac']:20s} b_fac={g['b_fac']:20s} seed={g['s']:3d}  "
              f"am_side={g['am_side']} rounds={g['rounds']} "
              f"am_surv={g['am_survivors']}/{g['am_start']} ec_surv={g['ec_survivors']}/{g['ec_start']} "
              f"am_capped={g['am_capped']} ec_capped={g['ec_capped']}")


if __name__ == "__main__":
    main()
