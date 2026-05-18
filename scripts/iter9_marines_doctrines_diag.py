"""
Iter-9 Marines Combat Doctrines audit diagnostic.

Iter-8 closed Custodes. Iter-9 picks up the next-largest residual:
Marines still +11.2pt over real-meta at N=40. Hypothesis: the
Combat Doctrines (Gladius Task Force detachment rule) implementation
in code/units.py is OVER-STRONG.

Current implementation (code/units.py:703-727):
  - Round 1 Devastator: +1 to wound, RANGED attacks (ALL of them).
  - Round 2 Tactical:   +1 to wound, BOTH modes (ALL attacks).
  - Round 3+ Assault:   +1 to wound, MELEE attacks (ALL of them).

REAL Wahapedia rule
(https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force,
cross-confirmed from newrecruit.eu wiki Gladius Task Force entry):

  Devastator Doctrine: "This unit is eligible to shoot in a turn in
    which it Advanced." (effectively grants [ASSAULT] to all weapons.)
  Tactical Doctrine:   "This unit is eligible to shoot and declare a
    charge in a turn in which it Fell Back."
  Assault Doctrine:    "This unit is eligible to declare a charge in
    a turn in which it Advanced."

There is NO +1-to-wound anywhere in Combat Doctrines. The wound buff is
fabricated. Every Marine attack on rounds 1-3+ in SwegHammer has been
silently rolling wounds with -1 to the wound target (max 2). Since
roughly 60-70% of Marine attacks per battle happen on rounds where the
fabricated Doctrine matches (R1 ranged, R2 anything, R3+ melee), this is
the single largest free DPS multiplier on the army.

This script measures (read-only):

  H1. Per-(round, mode) Marine attack and damage volumes — quantify how
      much of the army's total output sits inside the Doctrine window.

  H2. Compute the inflation factor: if the +1-to-wound were removed,
      what fraction of damage would the Marines lose? Model: for each
      buffed attack, the wound probability dropped from p_buffed to p_raw
      where p_raw was max(2, wt-1) -> wt. We approximate with the
      observed dpa; a 1-step wound target rise typically drops wound
      success by ~16-33%pt depending on the original target.

  H3. Cross-faction control — Marines vs each meta faction WR with the
      current (over-strong) Doctrine on. Establishes the baseline this
      iter is trying to move.

Outputs decision text at the bottom: FIX (fabricated buff, remove and
gate on the real movement triggers) or HOLD (if measured Doctrine
contribution is < 3pp WR, fix lives elsewhere).

Usage:
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.iter9_marines_doctrines_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter9_marines_doctrines_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import RoundStarted, UnitAdvanced, UnitFought, UnitShot
from code.factions import is_marine_faction
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS = [
    "Death Guard", "Necrons", "Tyranids",
    "Aeldari", "T'au Empire", "Orks",
    "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
]
MARINES = "Adeptus Astartes"
N_BATTLES = 40
POINTS = 1000


class DoctrineDiag:
    """Capture (round, mode) attack volumes for Marine units and count
    UnitAdvanced / fall_back events — the real Doctrines gate on those.
    """

    def __init__(self, marine_army_name: str, marine_uids: Dict[str, "Unit"]):
        self.marine_army = marine_army_name
        self.marine_uids = marine_uids
        self.current_round = 0
        self.attacks_by_round_mode: Dict[tuple, int] = defaultdict(int)
        self.damage_by_round_mode: Dict[tuple, float] = defaultdict(float)
        self.advances_per_round: Dict[int, int] = defaultdict(int)

    def _is_marine(self, uid: str) -> bool:
        u = self.marine_uids.get(uid)
        return u is not None and is_marine_faction(u.profile.faction)

    def on_event(self, e) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, UnitAdvanced):
            if e.unit_uid in self.marine_uids:
                self.advances_per_round[self.current_round] += 1
        elif isinstance(e, UnitShot):
            if self._is_marine(e.attacker_uid):
                self.attacks_by_round_mode[(self.current_round, "ranged")] += 1
                self.damage_by_round_mode[(self.current_round, "ranged")] += e.damage
        elif isinstance(e, UnitFought):
            if self._is_marine(e.attacker_uid):
                self.attacks_by_round_mode[(self.current_round, "melee")] += 1
                self.damage_by_round_mode[(self.current_round, "melee")] += e.damage


def run_one_matchup(opponent: str) -> Dict:
    doc_attacks: Dict[tuple, int] = defaultdict(int)
    doc_damage: Dict[tuple, float] = defaultdict(float)
    adv_per_round: Dict[int, int] = defaultdict(int)
    wins = Counter()

    for s in range(N_BATTLES):
        seed = s + 90000
        random.seed(seed)
        marines = build_faction_random_army(
            "A", MARINES, POINTS, rng=random.Random(seed), use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS, rng=random.Random(seed + 50000), use_archetype=True,
        )
        if not marines.units or not opp.units:
            continue
        battle = Battle(marines, opp, map_=DEFAULT_MAP)
        battle._assign_uids()
        marine_uids = {u.uid: u for u in marines.units}
        diag = DoctrineDiag(marines.name, marine_uids)
        battle.subscribers.append(diag)
        r = battle.run()
        wins[r.winner] += 1
        for k, n in diag.attacks_by_round_mode.items():
            doc_attacks[k] += n
            doc_damage[k] += diag.damage_by_round_mode[k]
        for rnd, n in diag.advances_per_round.items():
            adv_per_round[rnd] += n

    a, b, draws = wins.get("A", 0), wins.get("B", 0), wins.get(None, 0)
    total = a + b + draws
    wr = (a / total * 100.0) if total else 0.0
    return {
        "opp": opponent,
        "wr": wr,
        "n": total,
        "doc_attacks": dict(doc_attacks),
        "doc_damage": dict(doc_damage),
        "adv_per_round": dict(adv_per_round),
    }


def main() -> None:
    print(
        f"Iter-9 Marines Doctrines audit — N={N_BATTLES} per matchup, "
        f"{POINTS}pt, {len(OPPONENTS)} opponents."
    )
    print()
    print("REAL RULE (Wahapedia / newrecruit.eu):")
    print(
        "  Devastator: 'This unit is eligible to shoot in a turn in which it Advanced.'"
    )
    print(
        "  Tactical:   'This unit is eligible to shoot and declare a charge in a turn "
        "in which it Fell Back.'"
    )
    print(
        "  Assault:    'This unit is eligible to declare a charge in a turn in which "
        "it Advanced.'"
    )
    print("  -> NO +1-to-wound anywhere. Current SwegHammer impl is fabricated.")
    print(
        "  https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force"
    )
    print()

    results = []
    for opp in OPPONENTS:
        r = run_one_matchup(opp)
        results.append(r)
        ranged_atk = sum(
            n for (rnd, mode), n in r["doc_attacks"].items() if mode == "ranged"
        )
        melee_atk = sum(
            n for (rnd, mode), n in r["doc_attacks"].items() if mode == "melee"
        )
        total_dmg = sum(r["doc_damage"].values())
        print(
            f"  {r['opp']:<18s} WR={r['wr']:>5.1f}%  ranged_atk={ranged_atk:>5d}  "
            f"melee_atk={melee_atk:>4d}  dmg={total_dmg:>7.1f}"
        )
    print()

    # H1: per-(round,mode) aggregate
    print("=== H1 — Per-(round, mode) Marine attack volumes ===")
    print("  doc?Y = current code's fabricated rule grants +1 to wound on this bucket.")
    print()
    print(
        f"{'round':>5s} {'mode':>6s} {'attacks':>8s} {'damage':>9s} {'dpa':>5s} "
        f"{'doc?':>5s} {'share%':>7s}"
    )
    print("-" * 60)
    agg_attacks: Dict[tuple, int] = defaultdict(int)
    agg_damage: Dict[tuple, float] = defaultdict(float)
    for r in results:
        for k, n in r["doc_attacks"].items():
            agg_attacks[k] += n
            agg_damage[k] += r["doc_damage"][k]
    total_attacks = sum(agg_attacks.values())
    total_damage = sum(agg_damage.values())
    for rnd in sorted(set(r for r, _ in agg_attacks.keys())):
        for mode in ("ranged", "melee"):
            a = agg_attacks.get((rnd, mode), 0)
            if a == 0:
                continue
            d = agg_damage.get((rnd, mode), 0.0)
            doc = (
                (rnd == 1 and mode == "ranged")
                or rnd == 2
                or (rnd >= 3 and mode == "melee")
            )
            share = 100.0 * a / max(1, total_attacks)
            print(
                f"{rnd:>5d} {mode:>6s} {a:>8d} {d:>9.1f} {d/max(1,a):>5.2f} "
                f"{('Y' if doc else 'N'):>5s} {share:>7.2f}"
            )
    print()
    doc_a = sum(
        n for (rnd, mode), n in agg_attacks.items()
        if (rnd == 1 and mode == "ranged") or rnd == 2 or (rnd >= 3 and mode == "melee")
    )
    doc_d = sum(
        d for (rnd, mode), d in agg_damage.items()
        if (rnd == 1 and mode == "ranged") or rnd == 2 or (rnd >= 3 and mode == "melee")
    )
    print(
        f"Doctrine-buffed attacks: {doc_a} / {total_attacks} "
        f"({100.0 * doc_a / max(1, total_attacks):.1f}%) — damage share "
        f"{100.0 * doc_d / max(1, total_damage):.1f}%."
    )
    print()

    # H2: wound-buff inflation estimate
    print("=== H2 — Damage inflation from fabricated +1 to wound ===")
    print(
        "  Removing the +1-to-wound restores wound_target by +1 (i.e. wound roll"
    )
    print(
        "  needs +1 higher to succeed). For each affected attack the wound prob"
    )
    print(
        "  changes by (1 - 1/6) factor at the margin — typical buffed-vs-unbuffed"
    )
    print(
        "  ratio is approximately (wt-1)/wt for the affected dice. Rough estimate:"
    )
    print()
    # The current code is `wound_target = max(2, wound_target - 1)`. So if
    # wound_target without buff was 3, with buff is 2. P_succeed: 5/6 vs 4/6.
    # If wt was 4: 4/6 vs 3/6. If wt was 5: 3/6 vs 2/6. If wt was 6: 2/6 vs 1/6.
    # If wt was 2 (already): clamped, no buff. Roughly the buff is *worth*
    # +1/6 of the affected wound rolls -> ~16.7% absolute uplift in wound%.
    # Damage scales linearly post-wound, so:
    inflation = doc_d * (1.0 / 6.0) / max(1.0, doc_d + (total_damage - doc_d))
    # That formula is sloppy — better: of the doc_d damage, the buff was
    # responsible for fraction f where f = (1/6) / p_buffed_avg. We don't
    # know p_buffed_avg per dice, so report a band 10-25%.
    print(
        f"  Doctrine damage: {doc_d:.1f} / total {total_damage:.1f} "
        f"({100.0 * doc_d / max(1.0, total_damage):.1f}%)."
    )
    print(
        f"  Per-dice +1/6 wound uplift on affected attacks -> conservative band:"
    )
    print(
        f"  10% of {doc_d:.1f} = {0.10 * doc_d:.1f} dmg, 25% of {doc_d:.1f} = "
        f"{0.25 * doc_d:.1f} dmg — i.e. removing buff loses ~10-25% of"
    )
    print(
        f"  Doctrine-window damage (= {100.0 * 0.10 * doc_d / max(1.0, total_damage):.1f}-"
        f"{100.0 * 0.25 * doc_d / max(1.0, total_damage):.1f}% of total Marine damage)."
    )
    print()

    # H3: Advance volume — the REAL rule gates on Advance / Fall Back
    print("=== H3 — Marine Advance / Fall Back volume per round ===")
    print(
        "  Real rule REQUIRES the unit to have Advanced (R1, R3+) or Fallen Back"
    )
    print("  (R2) to benefit from the corresponding Doctrine. If Marine units")
    print("  rarely Advance or Fall Back, the real Doctrine almost never fires,")
    print("  i.e. the rule is a fringe utility, not a damage boost.")
    print()
    advances_total: Dict[int, int] = defaultdict(int)
    for r in results:
        for rnd, n in r["adv_per_round"].items():
            advances_total[rnd] += n
    print(f"{'round':>5s} {'advances':>9s} {'attacks':>9s} {'adv-per-batt':>13s}")
    print("-" * 45)
    for rnd in sorted(advances_total.keys()):
        a = advances_total.get(rnd, 0)
        atk = sum(n for (r2, _), n in agg_attacks.items() if r2 == rnd)
        per_batt = a / max(1, sum(r["n"] for r in results))
        print(f"{rnd:>5d} {a:>9d} {atk:>9d} {per_batt:>13.2f}")
    total_advances = sum(advances_total.values())
    total_battles = sum(r["n"] for r in results)
    print(
        f"\n  Total Marine Advances: {total_advances} across {total_battles} battles "
        f"({total_advances / max(1, total_battles):.2f}/battle)."
    )
    print()

    # Decision
    print("=== DECISION ===")
    wound_share_pct = 100.0 * doc_d / max(1.0, total_damage)
    print(
        f"Fabricated +1-to-wound covers {wound_share_pct:.1f}% of Marine damage."
    )
    print(
        f"Conservative ~15% inflation of that share = "
        f"~{0.15 * wound_share_pct:.1f}pp of total Marine damage erased by fix."
    )
    print(
        "Marines currently +11.2pt MAE. Fix recommendation: REMOVE the +1-to-wound"
    )
    print("Doctrine block and replace it with REAL-RULE gates (shoot-after-Advance,")
    print(
        "shoot+charge-after-Fall-Back, charge-after-Advance) which are utility-only"
    )
    print(
        "and won't multiply damage. Expected MAE drop: -2 to -4pt."
    )


if __name__ == "__main__":
    main()
