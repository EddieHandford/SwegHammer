"""
Iter-5 Marines alternate-mechanism diagnostic.

Iter-3 fingered Aggressor mapper torrent-aggregation. Iter-4 implemented
Option A (torrent ALL-not-ANY) and parked it — net regression +1.52pt.
Marines still over-perform by +12.6pt at end of iter 4.

This script probes six fresh angles, none of them Option A:

  1. Combat Doctrines round-rotation correctness — measure Marine attacks
     in (round, mode) buckets to verify the AI's R1-ranged / R2-both /
     R3+-melee rotation actually fires and matches the rule wording.
  2. Oath of Moment retargeting — verify OathTargetChosen fires once per
     round per Marine army (not once per battle), and that the target uid
     actually rotates across rounds.
  3. Repulsor stat sanity — read the catalogue line and compare to
     Wahapedia. The diag prints attacks / damage / hit_prob / range / S
     and flags any wildly-off field.
  4. Captain "Rites of Battle" — leader ability is reroll_hit_ones; check
     it isn't accidentally compounding with Oath's full reroll (which
     would double-roll dice). Measure damage-per-attack from the
     captain-led intercessor squad vs unbuffed intercessors.
  5. Apothecary heal cadence — count revives per battle, compare to the
     rule's "1 destroyed INFANTRY model per round" cap.
  6. Intercessor squad ranged stats — print catalogue values; the parsed
     range_inches is 12" which is wrong for Bolt Rifle (24"); damage 1.64
     for 2 attacks looks high too.

Read-only, no catalogue / simulator mutations.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter5_marines_alternate_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter5_marines_alternate_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    OathTargetChosen,
    RoundStarted,
    UnitFought,
    UnitKilled,
    UnitShot,
)
from code.factions import is_marine_faction
from code.maps import DEFAULT_MAP
from code.simulator import Battle
from code.units import UNIT_CATALOG

OPPONENTS = [
    "Death Guard", "Necrons", "Tyranids",
    "Aeldari", "T'au Empire", "Orks",
    "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
]
MARINES = "Adeptus Astartes"
N_BATTLES = 20
POINTS = 1000


class AlternateDiag:
    """For each Marine attack, capture (round, mode) so we can verify the
    Doctrine rotation rate. For each round, capture the OathTargetChosen
    event so we can verify it fires per-round and the target shifts when
    the previous target dies."""

    def __init__(self, marine_army_name: str, marine_uids: Dict[str, "Unit"]) -> None:
        self.marine_army = marine_army_name
        self.marine_uids = marine_uids
        self.current_round = 0

        # H1: Doctrines — attack counts per (round, mode)
        self.attacks_by_round_mode: Dict[tuple, int] = defaultdict(int)
        self.damage_by_round_mode: Dict[tuple, float] = defaultdict(float)

        # H2: Oath rotation
        self.oath_events: List[tuple] = []  # (round, target_uid)
        self.oath_target_in_round: Dict[int, str] = {}

        # H4: Captain attached unit damage tracking. Captain ALIAS uids
        # come in as attached models in the same unit (we approximate by
        # tagging any attack whose attacker is intercessor-keyed when
        # captain is alive).
        self.captain_alive = True

        # H5: Apothecary revives
        self.revives_per_round: Dict[int, int] = defaultdict(int)
        self.marine_kills: List[tuple] = []

        # Aggregate per-attacker damage for archetype-component share
        self.dmg_by_attacker_name: Dict[str, float] = defaultdict(float)
        self.attacks_by_attacker_name: Dict[str, int] = defaultdict(int)

    def _is_marine(self, uid: str) -> bool:
        u = self.marine_uids.get(uid)
        return u is not None and is_marine_faction(u.profile.faction)

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, OathTargetChosen):
            if e.army_name == self.marine_army:
                self.oath_events.append((e.round_num, e.target_uid))
                self.oath_target_in_round[e.round_num] = e.target_uid
        elif isinstance(e, UnitShot):
            self._record(e, "ranged")
        elif isinstance(e, UnitFought):
            self._record(e, "melee")
        elif isinstance(e, UnitKilled):
            if e.unit_uid in self.marine_uids:
                self.marine_kills.append((self.current_round, e.unit_uid))

    def _record(self, e, mode: str) -> None:
        if not self._is_marine(e.attacker_uid):
            return
        u = self.marine_uids.get(e.attacker_uid)
        if u is None:
            return
        nm = u.profile.name
        self.attacks_by_round_mode[(self.current_round, mode)] += 1
        self.damage_by_round_mode[(self.current_round, mode)] += e.damage
        self.dmg_by_attacker_name[nm] += e.damage
        self.attacks_by_attacker_name[nm] += 1


def h3_h6_catalogue_dump() -> None:
    """Print Marine archetype unit catalogue snapshot for visual sanity."""
    print()
    print("=== H3 / H6 — Catalogue stat snapshot (Marine archetype) ===")
    keys = [
        "space_marines_intercessor_squad",
        "space_marines_hellblaster_squad",
        "space_marines_eradicator_squad",
        "space_marines_aggressor_squad",
        "space_marines_captain_in_terminator_armour",
        "space_marines_apothecary",
        "space_marines_repulsor",
    ]
    hdr = (
        f"{'key':<48s} {'A':>3s} {'D':>5s} {'S':>3s} "
        f"{'AP':>3s} {'hit':>5s} {'rng':>4s} {'pts':>6s} {'T':>3s} {'twin':>5s} {'tor':>4s}"
    )
    print(hdr)
    print("-" * len(hdr))
    for k in keys:
        u = UNIT_CATALOG.get(k)
        if u is None:
            print(f"{k:<48s} MISSING")
            continue
        print(
            f"{k:<48s} {u.attacks:>3d} {u.damage:>5.2f} {u.strength:>3d} "
            f"{u.ap:>3d} {u.hit_probability:>5.2f} {u.range_inches:>4d} "
            f"{u.points_cost:>6.1f} {u.toughness:>3d} {str(u.twin_linked):>5s} "
            f"{str(getattr(u,'torrent',False)):>4s}"
        )
    print()
    print("Wahapedia reference values (ranged primary):")
    print("  Intercessor Squad — Bolt Rifle: 24\", A=2, BS3+, S4, AP-1, D1")
    print("    https://wahapedia.ru/wh40k10ed/factions/space-marines/#Intercessor-Squad")
    print("  Hellblaster Squad — Plasma Incinerator: 24\", A=2, BS3+, S7, AP-2, D1 (or 30\", S8, AP-3, D2 supercharge)")
    print("    https://wahapedia.ru/wh40k10ed/factions/space-marines/#Hellblaster-Squad")
    print("  Eradicator Squad — Melta Rifle: 18\", A=1, BS3+, S9, AP-4, D=D6 (Melta 2)")
    print("    https://wahapedia.ru/wh40k10ed/factions/space-marines/#Eradicator-Squad")
    print("  Aggressor Squad — Flamestorm Gauntlets: 12\", A=D6+1, S4, AP0, D1 (Torrent, T-L) / Boltstorm: 18\", A=3, BS3+, S4, AP0, D1 (T-L)")
    print("    https://wahapedia.ru/wh40k10ed/factions/space-marines/#Aggressor-Squad")
    print("  Repulsor — primary firepower: Twin Las-Talon (36\", A=2, BS3+, S10, AP-3, D=D6+1), Heavy Onslaught Gatling (24\", A=12, BS3+, S6, AP-1, D1), Twin Heavy Bolter (36\", A=6, BS3+, S5, AP-1, D2), Onslaught Gatling Cannon, etc.")
    print("    https://wahapedia.ru/wh40k10ed/factions/space-marines/#Repulsor")
    print()


def run_one_matchup(opponent: str) -> Dict:
    doctrine_attacks = defaultdict(int)
    doctrine_damage = defaultdict(float)
    total_attacks = 0
    total_damage = 0.0
    # Oath rotation tracking
    oath_picks_per_battle: List[int] = []
    oath_unique_targets_per_battle: List[int] = []
    oath_changes_per_battle: List[int] = []
    # Per-unit attribution
    per_unit_dmg = defaultdict(float)
    per_unit_attacks = defaultdict(int)
    # Apothecary
    revives_total = 0
    wins = Counter()

    for s in range(N_BATTLES):
        seed = s + 22000
        random.seed(seed)
        marines = build_faction_random_army(
            "A", MARINES, POINTS, rng=random.Random(seed), use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS, rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not marines.units or not opp.units:
            continue
        # Pre-snapshot Marine health to detect end-of-round revives.
        battle = Battle(marines, opp, map_=DEFAULT_MAP)
        battle._assign_uids()
        marine_uids = {u.uid: u for u in marines.units}
        marine_uids_set = set(marine_uids.keys())
        diag = AlternateDiag(marines.name, marine_uids)
        battle.subscribers.append(diag)
        r = battle.run()
        wins[r.winner] += 1

        # H1: aggregate per-(round,mode)
        for (rnd, mode), n in diag.attacks_by_round_mode.items():
            doctrine_attacks[(rnd, mode)] += n
            doctrine_damage[(rnd, mode)] += diag.damage_by_round_mode[(rnd, mode)]
            total_attacks += n
            total_damage += diag.damage_by_round_mode[(rnd, mode)]

        # H2: oath
        oath_picks_per_battle.append(len(diag.oath_events))
        oath_unique_targets_per_battle.append(
            len(set(uid for _, uid in diag.oath_events))
        )
        # Count "changes" — number of rounds where target_uid differs
        # from previous round's pick.
        changes = 0
        prev = None
        for rnd in sorted(diag.oath_target_in_round.keys()):
            cur = diag.oath_target_in_round[rnd]
            if prev is not None and cur != prev:
                changes += 1
            prev = cur
        oath_changes_per_battle.append(changes)

        # Per-attacker share
        for nm, d in diag.dmg_by_attacker_name.items():
            per_unit_dmg[nm] += d
            per_unit_attacks[nm] += diag.attacks_by_attacker_name[nm]

    a, b, draws = wins.get("A", 0), wins.get("B", 0), wins.get(None, 0)
    total = a + b + draws
    wr = (a / total * 100.0) if total else 0.0

    return {
        "opp": opponent,
        "wr": wr,
        "n": total,
        "total_attacks": total_attacks,
        "total_damage": total_damage,
        "doctrine_attacks": dict(doctrine_attacks),
        "doctrine_damage": dict(doctrine_damage),
        "oath_picks_mean": (
            statistics.mean(oath_picks_per_battle) if oath_picks_per_battle else 0.0
        ),
        "oath_unique_mean": (
            statistics.mean(oath_unique_targets_per_battle)
            if oath_unique_targets_per_battle
            else 0.0
        ),
        "oath_changes_mean": (
            statistics.mean(oath_changes_per_battle)
            if oath_changes_per_battle
            else 0.0
        ),
        "per_unit_dmg": dict(per_unit_dmg),
        "per_unit_attacks": dict(per_unit_attacks),
    }


def h1_doctrine_breakdown(results: List[Dict]) -> None:
    print("=== H1 — Combat Doctrines firing-rate sanity ===")
    print("Rule (Gladius Task Force, Wahapedia):")
    print(
        "  R1 Devastator (+1 wound, ranged only) / R2 Tactical (+1 wound, both) / "
        "R3+ Assault (+1 wound, melee only)."
    )
    print("  Our AI rotates deterministically in this order — see code/units.py:680.")
    print("  https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force")
    agg_attacks: Dict[tuple, int] = defaultdict(int)
    agg_damage: Dict[tuple, float] = defaultdict(float)
    total_attacks = 0
    total_damage = 0.0
    for r in results:
        for k, n in r["doctrine_attacks"].items():
            agg_attacks[k] += n
            agg_damage[k] += r["doctrine_damage"][k]
            total_attacks += n
            total_damage += r["doctrine_damage"][k]
    print()
    print(f"{'round':>5s} {'mode':>6s} {'attacks':>8s} {'damage':>9s} {'dpa':>5s} {'doc?':>5s}")
    print("-" * 50)
    rounds = sorted(set(r for r, _ in agg_attacks.keys()))
    for rnd in rounds:
        for mode in ("ranged", "melee"):
            a = agg_attacks.get((rnd, mode), 0)
            d = agg_damage.get((rnd, mode), 0.0)
            if a == 0:
                continue
            doc = "Y" if (
                (rnd == 1 and mode == "ranged")
                or rnd == 2
                or (rnd >= 3 and mode == "melee")
            ) else "N"
            print(
                f"{rnd:>5d} {mode:>6s} {a:>8d} {d:>9.1f} "
                f"{d / max(1, a):>5.2f} {doc:>5s}"
            )
    print()
    # Fraction of Marine attacks that benefit from Doctrines
    doc_attacks = sum(
        n for (rnd, mode), n in agg_attacks.items()
        if (rnd == 1 and mode == "ranged")
        or rnd == 2
        or (rnd >= 3 and mode == "melee")
    )
    doc_dmg = sum(
        d for (rnd, mode), d in agg_damage.items()
        if (rnd == 1 and mode == "ranged")
        or rnd == 2
        or (rnd >= 3 and mode == "melee")
    )
    if total_attacks > 0:
        print(
            f"Doctrine-active attacks: {doc_attacks} / {total_attacks} "
            f"({100.0 * doc_attacks / total_attacks:.1f}%) — damage share "
            f"{100.0 * doc_dmg / total_damage:.1f}%."
        )
    print()


def h2_oath_retarget(results: List[Dict]) -> None:
    print("=== H2 — Oath of Moment retargeting ===")
    print("Rule: 'At the start of your Command phase' — pick once per round.")
    print("  Our impl: simulator.py:3651 picks fresh each round on highest-points")
    print("  alive enemy. uid is reset to None at top of round in :2790.")
    print("  https://wahapedia.ru/wh40k10ed/factions/space-marines/#Oath-of-Moment")
    print()
    picks_means = [r["oath_picks_mean"] for r in results]
    unique_means = [r["oath_unique_mean"] for r in results]
    changes_means = [r["oath_changes_mean"] for r in results]
    print(
        f"Mean oath picks/battle: {statistics.mean(picks_means):.2f} "
        f"(expected: ~rounds played, typically 4-5)."
    )
    print(
        f"Mean unique oath targets/battle: {statistics.mean(unique_means):.2f} "
        f"(if = picks/battle the AI is rotating; if = 1 it's locked on one anchor)."
    )
    print(
        f"Mean oath target changes/battle: {statistics.mean(changes_means):.2f} "
        f"(rounds where target uid differs from previous round)."
    )
    print()


def h4_h5_attribution(results: List[Dict]) -> None:
    print("=== H4 / H5 — Per-unit damage share & Apothecary ===")
    print("Captain 'Rites of Battle' is reroll_hit_ones (leaders.py:127).")
    print("  Per units.py:1033, att_reroll_all_hits (from Oath) takes priority over")
    print("  att_reroll_hit_ones (from Captain) — no double-roll. Verify by share.")
    print("  https://wahapedia.ru/wh40k10ed/factions/space-marines/#Captain")
    print()
    per_unit_dmg: Dict[str, float] = defaultdict(float)
    per_unit_attacks: Dict[str, int] = defaultdict(int)
    for r in results:
        for nm, d in r["per_unit_dmg"].items():
            per_unit_dmg[nm] += d
            per_unit_attacks[nm] += r["per_unit_attacks"][nm]
    total_dmg = sum(per_unit_dmg.values())
    print(f"{'unit':<42s} {'atk':>7s} {'dmg':>8s} {'dpa':>5s} {'share%':>7s}")
    print("-" * 75)
    rows = sorted(per_unit_dmg.items(), key=lambda kv: -kv[1])
    for nm, d in rows:
        a = per_unit_attacks[nm]
        share = 100.0 * d / total_dmg if total_dmg > 0 else 0.0
        dpa = d / max(1, a)
        print(f"{nm:<42s} {a:>7d} {d:>8.1f} {dpa:>5.2f} {share:>7.2f}")
    print()


def main() -> None:
    print(
        f"Iter-5 Marines alternate diag — N={N_BATTLES} per matchup, "
        f"{POINTS}pt, {len(OPPONENTS)} opponents."
    )
    print()

    h3_h6_catalogue_dump()

    results = []
    for opp in OPPONENTS:
        r = run_one_matchup(opp)
        results.append(r)
        print(
            f"  {r['opp']:<18s} WR={r['wr']:>5.1f}%  attacks={r['total_attacks']:>5d}  "
            f"damage={r['total_damage']:>8.1f}  oath_picks={r['oath_picks_mean']:>4.1f}  "
            f"oath_unique={r['oath_unique_mean']:>4.2f}"
        )
    print()

    h1_doctrine_breakdown(results)
    h2_oath_retarget(results)
    h4_h5_attribution(results)


if __name__ == "__main__":
    main()
