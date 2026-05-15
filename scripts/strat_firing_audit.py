"""
Stratagem-firing diagnostic (SwegHammer task #169).

For each of the 10 standard factions, run 10 seeded battles against every other
faction (10 matchups, 1 battle each per seed × 10 seeds = 100 battles total per
faction-pair-grid traversal). Subscribe an EventLog to each battle and harvest
StratagemFired events. From those plus the army's residual CP at battle end,
compute per-faction CP utilisation and per-stratagem firing rates.

Diagnostic only — does NOT mutate the simulator or strategy layer.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.strat_firing_audit

Writes `docs/STRATAGEM_FIRING_AUDIT.md` with two tables and a per-faction
commentary block flagging the three worst CP-utilisation factions and the five
lowest firing-rate stratagems.
"""
from __future__ import annotations

import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Lock hash randomisation off so set / dict iteration order is reproducible.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.strat_firing_audit"]
               + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army
from code.events import EventLog, StratagemFired
from code.maps import DEFAULT_MAP
from code.simulator import Battle


FACTIONS: List[str] = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
    "Tyranids",
    "Orks",
    "T'au Empire",
    "Death Guard",
    "Adeptus Custodes",
    "Thousand Sons",
    "Leagues of Votann",
]

SEEDS_PER_MATCHUP = 10   # 10 seeded battles per (a, b) pair


def run_audit() -> Tuple[
    Dict[str, int],                       # cp_spent_total[faction]
    Dict[str, int],                       # cp_remaining_total[faction]
    Dict[str, int],                       # battles_played[faction]
    Dict[str, int],                       # strat_fire_count[faction]
    Dict[Tuple[str, str], int],           # firings[(faction, stratagem)]
    Dict[Tuple[str, str], int],           # eligible_games[(faction, stratagem)]
    Dict[Tuple[str, str], int],           # games_with_at_least_one_fire[(faction, strat)]
]:
    """Drive the matrix and return raw counters."""
    cp_spent_total: Dict[str, int] = defaultdict(int)
    cp_remaining_total: Dict[str, int] = defaultdict(int)
    battles_played: Dict[str, int] = defaultdict(int)
    strat_fire_count: Dict[str, int] = defaultdict(int)
    firings: Dict[Tuple[str, str], int] = defaultdict(int)
    games_with_fire: Dict[Tuple[str, str], int] = defaultdict(int)
    # eligible_games[(faction, stratagem)] = number of games where that faction
    # had the chance to fire that stratagem (i.e. simply the number of battles
    # the faction played) — needed for "% of games this stratagem fired".
    eligible_games: Dict[Tuple[str, str], int] = defaultdict(int)
    # Track which stratagems each faction can ever fire, populated from each
    # battle's first event sweep so we don't have to introspect detachments.
    seen_strats_per_faction: Dict[str, set] = defaultdict(set)

    fac_idx = {f: i for i, f in enumerate(FACTIONS)}

    for a_fac in FACTIONS:
        for b_fac in FACTIONS:
            if a_fac == b_fac:
                continue
            for s in range(SEEDS_PER_MATCHUP):
                ai, bi = fac_idx[a_fac], fac_idx[b_fac]
                pair_seed = (ai * 1000 + bi) * 100 + s
                random.seed(pair_seed)
                a = build_faction_random_army(
                    "A", a_fac, 1000, rng=random.Random(s))
                b = build_faction_random_army(
                    "B", b_fac, 1000, rng=random.Random(s + 10000))
                if not a.units or not b.units:
                    continue

                log = EventLog()
                Battle(a, b, map_=DEFAULT_MAP, subscribers=[log]).run()

                battles_played[a_fac] += 1
                battles_played[b_fac] += 1
                # End-of-battle residual CP (a proxy for "CP we never spent").
                cp_remaining_total[a_fac] += a.command_points
                cp_remaining_total[b_fac] += b.command_points

                # Map each side's Battle-internal name ("A" / "B") to the
                # faction so we can aggregate events by faction.
                name_to_fac = {a.name: a_fac, b.name: b_fac}

                game_strats: Dict[str, set] = {a_fac: set(), b_fac: set()}
                for ev in log.events:
                    if not isinstance(ev, StratagemFired):
                        continue
                    fac = name_to_fac.get(ev.army_name)
                    if fac is None:
                        continue
                    cp_spent_total[fac] += ev.cp_cost
                    strat_fire_count[fac] += 1
                    firings[(fac, ev.stratagem_name)] += 1
                    game_strats[fac].add(ev.stratagem_name)
                    seen_strats_per_faction[fac].add(ev.stratagem_name)
                # Per-game presence: count this game as "fired at least once"
                # for every stratagem that fired during it.
                for game_fac, strats in game_strats.items():
                    for s_name in strats:
                        games_with_fire[(game_fac, s_name)] += 1

    # Now compute eligible_games per (faction, stratagem). A stratagem is
    # "eligible" for a faction in every game the faction played, regardless
    # of whether it fired — the firing rate is firings / battles_played.
    for fac in FACTIONS:
        for strat in seen_strats_per_faction[fac]:
            eligible_games[(fac, strat)] = battles_played[fac]

    return (cp_spent_total, cp_remaining_total, battles_played,
            strat_fire_count, firings, eligible_games, games_with_fire)


def format_utilisation_table(
    cp_spent: Dict[str, int],
    cp_remaining: Dict[str, int],
    battles: Dict[str, int],
    strat_fires: Dict[str, int],
) -> Tuple[str, List[Tuple[str, float]]]:
    """Return (markdown table, sorted (faction, utilisation) list)."""
    lines = [
        "| Faction | Battles | CP spent | CP unspent | Total flow | Util % | Strats/game |",
        "|---------|--------:|---------:|-----------:|-----------:|-------:|------------:|",
    ]
    util_pairs: List[Tuple[str, float]] = []
    for fac in FACTIONS:
        spent = cp_spent[fac]
        unspent = cp_remaining[fac]
        n = battles[fac]
        flow = spent + unspent
        util = (100.0 * spent / flow) if flow > 0 else 0.0
        spg = (strat_fires[fac] / n) if n > 0 else 0.0
        util_pairs.append((fac, util))
        lines.append(
            f"| {fac} | {n} | {spent} | {unspent} | {flow} | "
            f"{util:5.1f} | {spg:6.2f} |"
        )
    return "\n".join(lines), util_pairs


def format_stratagem_table(
    firings: Dict[Tuple[str, str], int],
    eligible_games: Dict[Tuple[str, str], int],
    games_with_fire: Dict[Tuple[str, str], int],
) -> Tuple[str, List[Tuple[str, str, float, float]]]:
    """Return (markdown table, sorted list of
    (faction, strat, rate_per_game%, games_fired%) entries)."""
    rows: List[Tuple[str, str, int, int, int, float, float]] = []
    for (fac, strat), fires in firings.items():
        games = eligible_games.get((fac, strat), 0)
        if games <= 0:
            continue
        rate = 100.0 * fires / games
        gwf = games_with_fire.get((fac, strat), 0)
        game_pct = 100.0 * gwf / games
        rows.append((fac, strat, fires, gwf, games, rate, game_pct))
    rows.sort(key=lambda r: (r[0], -r[5]))

    lines = [
        "| Faction | Stratagem | Fires | Games-fired | Games | Fires/game % | Games-fired % |",
        "|---------|-----------|------:|------------:|------:|-------------:|--------------:|",
    ]
    for fac, strat, fires, gwf, games, rate, game_pct in rows:
        lines.append(
            f"| {fac} | {strat} | {fires} | {gwf} | {games} | "
            f"{rate:6.1f} | {game_pct:5.1f} |"
        )
    sorted_out = [(fac, strat, rate, game_pct)
                  for (fac, strat, _, _, _, rate, game_pct) in rows]
    return "\n".join(lines), sorted_out


def build_commentary(
    util_pairs: List[Tuple[str, float]],
    rate_rows: List[Tuple[str, str, float, float]],
    firings: Dict[Tuple[str, str], int],
    eligible_games: Dict[Tuple[str, str], int],
    games_with_fire: Dict[Tuple[str, str], int],
    cp_spent: Dict[str, int],
    cp_remaining: Dict[str, int],
    battles: Dict[str, int],
) -> str:
    """Per-faction prose + the headline 'top 3 worst utilisation' + 'bottom 5
    firing-rate stratagems' callouts."""
    parts: List[str] = []

    # Headline: bottom-3 utilisation.
    util_sorted = sorted(util_pairs, key=lambda x: x[1])
    bottom3 = util_sorted[:3]
    parts.append("## Headline findings\n")
    parts.append("### Worst three factions by CP utilisation (under-spending)\n")
    for fac, util in bottom3:
        spent = cp_spent[fac]
        unspent = cp_remaining[fac]
        n = battles[fac]
        avg_left = unspent / n if n else 0.0
        parts.append(
            f"- **{fac}** — {util:.1f} % utilisation "
            f"({spent} CP spent vs {unspent} CP unspent across {n} battles; "
            f"~{avg_left:.1f} CP left on the table per game)."
        )
    parts.append("")

    # Headline: lowest games-fired-% stratagems (only those that fired at
    # least once, otherwise the bottom is dominated by zero-fire entries).
    fired_rows = [r for r in rate_rows if r[3] > 0.0]
    fired_rows.sort(key=lambda r: r[3])
    bottom5 = fired_rows[:5]
    parts.append("### Five lowest firing-rate stratagems (that fired at least once)\n")
    parts.append("Ranked by % of games the stratagem fired in.\n")
    for fac, strat, rate, game_pct in bottom5:
        fires = firings[(fac, strat)]
        gwf = games_with_fire[(fac, strat)]
        games = eligible_games[(fac, strat)]
        parts.append(
            f"- **{strat}** ({fac}) — fired in **{game_pct:.1f} %** of games "
            f"({gwf}/{games}), totalling {fires} fires."
        )
    parts.append("")

    # >50% and <10% groupings — by games-fired %.
    high = [(f, s, r, g) for (f, s, r, g) in rate_rows if g > 50.0]
    low = [(f, s, r, g) for (f, s, r, g) in rate_rows if 0.0 < g < 10.0]
    parts.append("### Stratagems firing in **more than 50 %** of games\n")
    if high:
        for fac, strat, rate, game_pct in sorted(high, key=lambda x: -x[3]):
            parts.append(f"- {strat} ({fac}) — {game_pct:.1f} % of games")
    else:
        parts.append("_None — no stratagem clears the 50 % threshold._")
    parts.append("")
    parts.append("### Stratagems firing in **less than 10 %** of games (but at least once)\n")
    if low:
        for fac, strat, rate, game_pct in sorted(low, key=lambda x: x[3]):
            parts.append(f"- {strat} ({fac}) — {game_pct:.1f} % of games")
    else:
        parts.append("_None — every fired stratagem clears 10 %._")
    parts.append("")

    # Per-faction prose.
    parts.append("## Per-faction commentary\n")
    rate_by_fac: Dict[str, List[Tuple[str, float, float]]] = defaultdict(list)
    for fac, strat, rate, game_pct in rate_rows:
        rate_by_fac[fac].append((strat, rate, game_pct))
    for fac in FACTIONS:
        spent = cp_spent[fac]
        unspent = cp_remaining[fac]
        n = battles[fac]
        flow = spent + unspent
        util = (100.0 * spent / flow) if flow > 0 else 0.0
        verdict = ("under 70 % — CP sitting unspent at game end"
                   if util < 70.0 else "healthy")
        parts.append(f"### {fac}")
        parts.append(
            f"Utilisation **{util:.1f} %** ({verdict}); "
            f"average residual {unspent / n if n else 0.0:.2f} CP/game."
        )
        strats = sorted(rate_by_fac[fac], key=lambda x: -x[2])
        if strats:
            top = ", ".join(f"{s} ({g:.0f}% games)" for s, _, g in strats[:3])
            parts.append(f"Top-firing stratagems (by games-fired %): {top}.")
            bot = [(s, g) for s, _, g in strats if 0.0 < g < 10.0]
            if bot:
                names = ", ".join(f"{s} ({g:.0f}%)" for s, g in bot)
                parts.append(f"Under-utilised (<10 % of games): {names}.")
        else:
            parts.append("No stratagems fired in any battle.")
        parts.append("")
    return "\n".join(parts)


def main() -> int:
    print(f"Running {len(FACTIONS)} x {len(FACTIONS) - 1} x {SEEDS_PER_MATCHUP} "
          f"= {len(FACTIONS) * (len(FACTIONS) - 1) * SEEDS_PER_MATCHUP} battles...")
    (cp_spent, cp_remaining, battles, strat_fires,
     firings, eligible_games, games_with_fire) = run_audit()

    util_md, util_pairs = format_utilisation_table(
        cp_spent, cp_remaining, battles, strat_fires)
    strat_md, rate_rows = format_stratagem_table(
        firings, eligible_games, games_with_fire)
    commentary = build_commentary(
        util_pairs, rate_rows, firings, eligible_games, games_with_fire,
        cp_spent, cp_remaining, battles)

    doc = (
        "# Stratagem firing audit\n\n"
        "Diagnostic generated by `scripts/strat_firing_audit.py` "
        f"(SwegHammer task #169). Each of the {len(FACTIONS)} factions "
        f"plays {SEEDS_PER_MATCHUP} seeded battles against every other "
        "faction; we tally `StratagemFired` events per army and combine "
        "with residual CP at battle end to compute utilisation.\n\n"
        "Utilisation % = CP spent / (CP spent + CP unspent at game end). "
        "A faction below 70 % is leaving CP on the table.\n\n"
        "Per-stratagem **rate %** is `fires / games` and can exceed 100 % "
        "for stratagems that legally fire many times per battle (e.g. "
        "Command Re-Roll triggers on every failed wound, so >300 % rate "
        "means ~3 fires per game on average).\n\n"
        "## Per-faction CP utilisation\n\n"
        + util_md + "\n\n"
        "## Per-stratagem firing rate\n\n"
        + strat_md + "\n\n"
        + commentary
    )

    out_path = Path(__file__).resolve().parent.parent / "docs" / "STRATAGEM_FIRING_AUDIT.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    print(f"Wrote {out_path}")

    # Console summary so the diagnostic is useful without opening the file.
    print("\nBottom 3 utilisation:")
    for fac, util in sorted(util_pairs, key=lambda x: x[1])[:3]:
        print(f"  {fac:22s}  {util:5.1f} %")
    print("\nBottom 5 stratagem firing rates (by % of games it fired in):")
    fired_rows = sorted([r for r in rate_rows if r[3] > 0.0], key=lambda r: r[3])
    for fac, strat, rate, game_pct in fired_rows[:5]:
        print(f"  {strat:32s}  {fac:22s}  {game_pct:5.1f} % of games")
    return 0


if __name__ == "__main__":
    sys.exit(main())
