"""
Iter-14 Marines AI-side audit — task brief: find a FACTION-NEUTRAL AI counter-
tool gap that lets Marines over-perform without naming "Marines" anywhere.

Marines have sat at +10pt vs real meta (sim ~60%, real 48%) for 6+ iterations
even AFTER iter-9 corrected the fabricated +1-to-wound Combat Doctrines.
The Combat Doctrines rebuild is now utility-only. So the residual gap is
either rule-side (Marines have something we missed) OR AI-side (every
faction's AI fails to counter Oath of Moment / Marine leader stacks).

This script measures three AI-side suspects (all faction-neutral hypotheses):

  H-A. Oath-anchor LEADER kill rate: when a Marine character is the warlord
       in a Tactical/Intercessor squad, the picker prioritises the bodyguard
       squad — never the leader. Killing the leader BREAKS the +1-to-hit
       aura. We measure, per matchup, how many Marine CHARACTER units the
       opponent kills per battle (vs how many bodyguard squads).

  H-B. Anti-Marine target spread: when an opponent's shoot picker uses
       min(current_health) as its tiebreaker, the picker pours fire into
       the most-wounded Marine — usually a Tactical squad that's lost two
       models. The Marine player benefits because Oath retargets onto the
       opponent's biggest brick, while the opponent's fire focuses on a
       half-dead squad with 1-2 wounds left. We measure: % of opponent
       shooting damage that goes into Marine squads ALREADY at <33% HP.

  H-C. Charge-target leader bypass: pick_charge_target uses
       _support_target_bonus (1.3x for SUPPORT / aura-leader targets), but
       the CHARACTER hidden inside a led Marine squad is NEVER selectable
       as a charge target — only the bodyguard's uid is. Look Out Sir
       (in army.can_target_for_ranged) shields the character at range, but
       in melee they should be reachable. We measure how many Marine
       CHARACTERS the opponent SUCCESSFULLY charges (UnitCharged +
       UnitFought combined attacker target).

All three are independent of "is the attacker Marines" — they show up as
gaps in the universal target-picker logic. The fix landing-zone is
faction-neutral by construction.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter14_marines_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter14_marines_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    OathTargetChosen, RoundStarted, UnitFought, UnitKilled, UnitShot,
)
from code.factions import is_marine_faction
from code.leaders import lookup_ability
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS: List[str] = [
    "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes",
    "Thousand Sons", "Leagues of Votann",
]
MARINES = "Adeptus Astartes"
N_BATTLES = 20
POINTS = 1000


def _is_character(u) -> bool:
    return "CHARACTER" in (u.profile.unit_keywords or ())


def _has_aura(u) -> bool:
    return lookup_ability(u.profile.name) is not None


class IterDiag:
    """Capture per-battle diagnostic counters."""

    def __init__(self, marines_army_name: str, marine_units, opp_units) -> None:
        self.marines_name = marines_army_name
        self.marine_uids = {u.uid: u for u in marine_units}
        self.opp_uids = {u.uid: u for u in opp_units}
        self.current_round = 0

        # Marines characters with auras + their starting HP at battle start.
        self.marine_leaders = {
            u.uid: u for u in marine_units
            if _is_character(u) and _has_aura(u)
        }
        self.marine_leaders_alive_at_end: Dict[str, bool] = {}

        # H-A counters
        self.opp_shot_into_marine_leader = 0
        self.opp_shot_into_marine_bodyguard = 0
        self.opp_fought_into_marine_leader = 0
        self.opp_fought_into_marine_bodyguard = 0
        self.marine_leaders_killed_by_opp = 0
        self.marine_bodyguards_killed_by_opp = 0

        # H-B counters: opponent shooting damage by target HP bucket.
        # We sample target_hp_after BEFORE damage to bucket; approximate via
        # target_hp_after + damage (= pre-attack HP). Health bucket: <33%,
        # 33-66%, >66% of profile.health.
        self.opp_damage_into_marines_by_bucket: Dict[str, float] = defaultdict(float)
        self.opp_damage_into_marines_total = 0.0

        # H-C counter — Marine characters fought in melee (uid as target).
        self.opp_melee_attacks_into_marine_char = 0

    def on_event(self, e) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, UnitShot):
            self._record_shot(e)
        elif isinstance(e, UnitFought):
            self._record_fought(e)
        elif isinstance(e, UnitKilled):
            self._record_killed(e.unit_uid)

    def _opp_attacker_into_marine(self, attacker_uid, target_uid) -> bool:
        a = self.marine_uids.get(attacker_uid)
        if a is not None:
            return False  # attacker is Marine, skip
        t = self.marine_uids.get(target_uid)
        return t is not None

    def _record_shot(self, e: UnitShot) -> None:
        if not self._opp_attacker_into_marine(e.attacker_uid, e.target_uid):
            return
        target = self.marine_uids[e.target_uid]
        # Bucket by pre-attack HP fraction (target_hp_after + damage = pre).
        pre_hp = e.target_hp_after + e.damage
        max_hp = max(1.0, float(target.profile.health))
        frac = pre_hp / max_hp
        if frac < 0.33:
            bucket = "low"
        elif frac < 0.66:
            bucket = "mid"
        else:
            bucket = "full"
        self.opp_damage_into_marines_by_bucket[bucket] += e.damage
        self.opp_damage_into_marines_total += e.damage
        # H-A — leader vs bodyguard categorisation. Only leaders inside the
        # leaders dict count; bodyguard = any other Marine unit.
        if e.target_uid in self.marine_leaders:
            self.opp_shot_into_marine_leader += 1
        else:
            self.opp_shot_into_marine_bodyguard += 1

    def _record_fought(self, e: UnitFought) -> None:
        if not self._opp_attacker_into_marine(e.attacker_uid, e.target_uid):
            return
        if e.target_uid in self.marine_leaders:
            self.opp_fought_into_marine_leader += 1
            self.opp_melee_attacks_into_marine_char += 1
        else:
            self.opp_fought_into_marine_bodyguard += 1

    def _record_killed(self, killed_uid) -> None:
        if killed_uid in self.marine_leaders:
            self.marine_leaders_killed_by_opp += 1
        elif killed_uid in self.marine_uids:
            self.marine_bodyguards_killed_by_opp += 1


def run_matchup(opponent: str) -> Dict:
    wins = Counter()
    leader_atks_lead: List[int] = []
    bodyguard_atks_lead: List[int] = []
    leaders_killed_per_battle: List[int] = []
    leaders_present_per_battle: List[int] = []
    bucket_damage_pct_low: List[float] = []
    bucket_damage_pct_full: List[float] = []
    melee_into_char_per_battle: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 14000
        random.seed(seed)
        marines = build_faction_random_army(
            "A", MARINES, POINTS, rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS, rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not marines.units or not opp.units:
            continue

        battle = Battle(marines, opp, map_=DEFAULT_MAP)
        battle._assign_uids()
        diag = IterDiag(marines.name, marines.units, opp.units)
        battle.subscribers.append(diag)
        r = battle.run()

        wins[r.winner] += 1
        leader_atks_lead.append(
            diag.opp_shot_into_marine_leader + diag.opp_fought_into_marine_leader
        )
        bodyguard_atks_lead.append(
            diag.opp_shot_into_marine_bodyguard + diag.opp_fought_into_marine_bodyguard
        )
        leaders_killed_per_battle.append(diag.marine_leaders_killed_by_opp)
        leaders_present_per_battle.append(len(diag.marine_leaders))
        if diag.opp_damage_into_marines_total > 0:
            bucket_damage_pct_low.append(
                100.0 * diag.opp_damage_into_marines_by_bucket["low"]
                / diag.opp_damage_into_marines_total
            )
            bucket_damage_pct_full.append(
                100.0 * diag.opp_damage_into_marines_by_bucket["full"]
                / diag.opp_damage_into_marines_total
            )
        melee_into_char_per_battle.append(diag.opp_melee_attacks_into_marine_char)

    a, b, draws = wins.get("A", 0), wins.get("B", 0), wins.get(None, 0)
    total = a + b + draws
    wr = (a / total * 100.0) if total else 0.0

    return {
        "opp": opponent,
        "wr": wr,
        "n": total,
        "leader_atks_mean": statistics.mean(leader_atks_lead) if leader_atks_lead else 0.0,
        "bodyguard_atks_mean": statistics.mean(bodyguard_atks_lead) if bodyguard_atks_lead else 0.0,
        "leaders_killed_mean": statistics.mean(leaders_killed_per_battle) if leaders_killed_per_battle else 0.0,
        "leaders_present_mean": statistics.mean(leaders_present_per_battle) if leaders_present_per_battle else 0.0,
        "low_hp_damage_pct": statistics.mean(bucket_damage_pct_low) if bucket_damage_pct_low else 0.0,
        "full_hp_damage_pct": statistics.mean(bucket_damage_pct_full) if bucket_damage_pct_full else 0.0,
        "melee_into_char_mean": statistics.mean(melee_into_char_per_battle) if melee_into_char_per_battle else 0.0,
    }


def main() -> None:
    print(
        f"Iter-14 Marines AI-side audit — N={N_BATTLES} per matchup, "
        f"{POINTS}pt, {len(OPPONENTS)} opponents."
    )
    print()
    print("HYPOTHESES:")
    print("  H-A: opponent picker NEVER targets the Marine CHARACTER directly.")
    print("       leader_atk_share should be ~0; leaders_killed should be ~0.")
    print("  H-B: opponent picker dumps fire into low-HP marines.")
    print("       low_hp_dmg% should be > full_hp_dmg% if H-B holds.")
    print("  H-C: opponent melee NEVER hits a Marine CHARACTER directly.")
    print("       melee_into_char should be ~0 across all battles.")
    print()
    print(
        f"{'opp':22s} {'WR%':>6s} {'leaderAtk':>9s} {'guardAtk':>9s} "
        f"{'leadKld':>8s} {'leadPres':>8s} {'%loHP':>6s} {'%fuHP':>6s} {'mCharAtk':>9s}"
    )
    print("-" * 110)
    results = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        results.append(r)
        print(
            f"{r['opp']:22s} {r['wr']:>6.1f} "
            f"{r['leader_atks_mean']:>9.2f} {r['bodyguard_atks_mean']:>9.2f} "
            f"{r['leaders_killed_mean']:>8.2f} {r['leaders_present_mean']:>8.2f} "
            f"{r['low_hp_damage_pct']:>6.1f} {r['full_hp_damage_pct']:>6.1f} "
            f"{r['melee_into_char_mean']:>9.2f}"
        )
    print("-" * 110)
    mean_wr = statistics.mean(r["wr"] for r in results)
    mean_lead_atk = statistics.mean(r["leader_atks_mean"] for r in results)
    mean_guard_atk = statistics.mean(r["bodyguard_atks_mean"] for r in results)
    mean_killed = statistics.mean(r["leaders_killed_mean"] for r in results)
    mean_present = statistics.mean(r["leaders_present_mean"] for r in results)
    mean_low = statistics.mean(r["low_hp_damage_pct"] for r in results)
    mean_full = statistics.mean(r["full_hp_damage_pct"] for r in results)
    mean_melee_char = statistics.mean(r["melee_into_char_mean"] for r in results)
    print(
        f"{'OVERALL':22s} {mean_wr:>6.1f} "
        f"{mean_lead_atk:>9.2f} {mean_guard_atk:>9.2f} "
        f"{mean_killed:>8.2f} {mean_present:>8.2f} "
        f"{mean_low:>6.1f} {mean_full:>6.1f} "
        f"{mean_melee_char:>9.2f}"
    )
    print()
    print("=== INTERPRETATION ===")
    # Share of attacks landing on Marine LEADER
    total_atks = mean_lead_atk + mean_guard_atk
    if total_atks > 0:
        lead_share = 100.0 * mean_lead_atk / total_atks
    else:
        lead_share = 0.0
    print(
        f"H-A: opponent attacks on Marine LEADER = {lead_share:.1f}% of all opp attacks "
        f"into Marines. Marine leaders killed per battle = {mean_killed:.2f} "
        f"(out of {mean_present:.2f} present)."
    )
    if mean_present > 0:
        kill_pct = 100.0 * mean_killed / mean_present
    else:
        kill_pct = 0.0
    print(
        f"     -> {kill_pct:.0f}% of Marine leaders die per battle. "
        f"In real-meta play the opposing AI prioritises killing the buff char."
    )
    print(
        f"H-B: low-HP target damage share = {mean_low:.1f}% vs full-HP "
        f"= {mean_full:.1f}%. If low > full by >5pp, the picker is over-"
        f"concentrating on already-wounded targets (waste fire)."
    )
    print(
        f"H-C: opp melee attacks targeting Marine CHARACTER = {mean_melee_char:.2f} "
        f"per battle. If ~0, the melee picker is missing the high-value buff char."
    )
    print()
    print("=== FIX DECISION (faction-neutral) ===")
    if lead_share < 5.0 and kill_pct < 25.0:
        print(
            "PROCEED: H-A is the gap. Apply a CHARACTER-leader target priority "
            "bonus inside `_screen_target_bonus`-style multiplicative bias. "
            "(Already exists for SUPPORT role via _support_target_bonus 1.3x, "
            "but only applies to MELEE picker — not the SHOOT picker.)"
        )
    else:
        print(
            "ABSTAIN: H-A doesn't dominate. The fix probably lives in a "
            "different bias function — keep digging next iter."
        )


if __name__ == "__main__":
    main()
