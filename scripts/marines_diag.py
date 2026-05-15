"""
Marines (Gladius Strike Force) archetype diagnostic — task #172.

Marines diff jumped to +18.3 pts after G3 (battleshock + Synapse). This script
runs 30 seeded archetype battles Marines vs each of the 9 opponents and
captures three things, mapping to H1 / H2 / H3 from the task brief:

  * H1 — Oath of Moment generosity: what % of total Marine attacks (UnitShot +
    UnitFought events fired by a marine attacker) landed on the army's
    oath_target_uid for the round.
  * H2 — Combat Doctrines firing rate: a Marine attack benefits from the
    Doctrines wound-roll boost when the attacker is in Gladius Task Force,
    the round is the right one for the active doctrine (round 1 = ranged,
    round 2 = either, round 3+ = melee), and the attack mode matches. We
    count the rate at which a Marine attack hits the boosted gate per round.
  * H3 — OC stack: average Marine OC vs opponent OC on objectives at
    end-of-round (sampled from ObjectiveScored a_oc/b_oc).

Read-only — does NOT modify catalogue, simulator, or strategy code.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.marines_diag
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
        [sys.executable, "-m", "scripts.marines_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    ObjectiveScored,
    OathTargetChosen,
    RoundStarted,
    UnitFought,
    UnitShot,
)
from code.factions import is_marine_faction
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS: List[str] = [
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
MARINES = "Adeptus Astartes"
N_BATTLES = 30
POINTS = 1000


class DiagSubscriber:
    """Captures per-battle events for Oath/Doctrines/OC analysis."""

    def __init__(self, marine_army_name: str, opp_army_name: str) -> None:
        self.marine_army = marine_army_name
        self.opp_army = opp_army_name
        # Round tracking + the oath target uid currently in effect for our
        # marines this round (set by OathTargetChosen for marine_army).
        self.current_round = 0
        self.oath_target_uid: str | None = None
        # H1 counters
        self.marine_attacks_total = 0
        self.marine_attacks_on_oath = 0
        # H2 counters: how many marine attacks per round (so we can frame the
        # doctrines firing rate from the deterministic AI rotation, given
        # that the boosted gate is round-dependent + mode-dependent).
        self.marine_ranged_attacks_by_round: Dict[int, int] = defaultdict(int)
        self.marine_melee_attacks_by_round: Dict[int, int] = defaultdict(int)
        # H3 counters — OC on objectives (a_oc, b_oc) where a is Marines.
        # We'll keep per-objective tuples per round-end so we can average.
        self.marine_oc_samples: List[int] = []
        self.opp_oc_samples: List[int] = []
        # Side hints — set on first use.
        self._marine_is_a: bool | None = None

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
            # Oath target gets re-picked each Command phase. Reset our
            # tracker so we don't count attacks against last round's target.
            self.oath_target_uid = None
        elif isinstance(e, OathTargetChosen):
            if e.army_name == self.marine_army:
                self.oath_target_uid = e.target_uid
        elif isinstance(e, UnitShot):
            self._record_attack(
                e.attacker_uid, e.target_uid, mode="ranged",
            )
        elif isinstance(e, UnitFought):
            self._record_attack(
                e.attacker_uid, e.target_uid, mode="melee",
            )
        elif isinstance(e, ObjectiveScored):
            # a_oc / b_oc are reported with the army-A-is-Marines convention
            # we build. We pin which side Marines are on via marine_army vs
            # the army_name fields in scored events isn't reliable (None on
            # contested) — instead we record both raw a_oc/b_oc and let the
            # caller normalise based on construction order.
            if self._marine_is_a is None:
                # Build order in this script: marines = A, opponent = B.
                self._marine_is_a = True
            self.marine_oc_samples.append(e.a_oc)
            self.opp_oc_samples.append(e.b_oc)

    def _record_attack(self, attacker_uid: str, target_uid: str, mode: str) -> None:
        # Resolve attacker via the marine army's units list (looked up at
        # call time via the live battle ref isn't exposed in the event, so
        # we keep a side-band lookup via the marine army reference passed
        # at construction-equivalent time — see run_matchup).
        attacker = _UID_LOOKUP.get(attacker_uid)
        if attacker is None or not is_marine_faction(attacker.profile.faction):
            return
        self.marine_attacks_total += 1
        if (
            self.oath_target_uid is not None
            and target_uid == self.oath_target_uid
        ):
            self.marine_attacks_on_oath += 1
        if mode == "ranged":
            self.marine_ranged_attacks_by_round[self.current_round] += 1
        else:
            self.marine_melee_attacks_by_round[self.current_round] += 1


# Side-band attacker uid -> Unit lookup. Refreshed per-battle in run_matchup
# so we can resolve UnitShot.attacker_uid to a faction without instrumenting
# the event payload.
_UID_LOOKUP: Dict[str, "Unit"] = {}


def _doctrines_fires_in_round(round_num: int, mode: str) -> bool:
    """Mirror of the Gladius Task Force AI rotation in units.py.

    Round 1 Devastator => ranged only.
    Round 2 Tactical => either.
    Round 3+ Assault => melee only.
    """
    if round_num == 1:
        return mode == "ranged"
    if round_num == 2:
        return True
    if round_num >= 3:
        return mode == "melee"
    return False


def run_matchup(opponent: str) -> Dict:
    wins = Counter()
    rounds_played: List[int] = []
    oath_pct_per_battle: List[float] = []
    doctrines_pct_per_battle: List[float] = []
    marine_oc_means: List[float] = []
    opp_oc_means: List[float] = []
    marine_attack_totals: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 9001
        random.seed(seed)
        marines = build_faction_random_army(
            "A", MARINES, POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not marines.units or not opp.units:
            continue

        sub = DiagSubscriber(marines.name, opp.name)
        battle = Battle(marines, opp, map_=DEFAULT_MAP, subscribers=[sub])
        # Populate the uid lookup AFTER Battle.__init__ assigns uids. The
        # simulator does this in run() via _assign_uids, so we re-populate
        # after a no-op pass. The cheapest correct path: subscribe a tiny
        # listener that fills _UID_LOOKUP once UnitDeployed-style events fire.
        # Simpler: defer the lookup population to after .run() starts; the
        # attacker_uid is set when units are deployed and UnitShot/UnitFought
        # only fire after that. We refresh just before run() — uids are
        # assigned in run() before deploy, so we need a different hook.
        #
        # Simplest reliable approach: rely on the fact that Unit.uid is set
        # by _assign_uids at the very top of run(); we register a subscriber
        # that catches the first UnitShot to lazily fill the lookup. But that
        # means we'd miss the first marine attack's filter. Instead, refresh
        # the lookup AFTER run() finishes and re-process — no, events fire
        # only once.
        #
        # Cleanest: monkey-patch run() flow by capturing uids on every
        # UnitShot fire by walking the battle's armies. Lazy build below.
        r = battle.run()

        # Lazy uid lookup post-run for future battles — but for THIS battle
        # the events already fired with a possibly-empty _UID_LOOKUP. To
        # work around: clear _UID_LOOKUP and replay isn't possible without
        # re-running. Solution: pre-seed _UID_LOOKUP BEFORE .run() by
        # exploiting Battle._assign_uids being deterministic + idempotent.
        # We instead call it pre-run; reassignment after deploy is harmless
        # because run() calls _assign_uids() again at the very start.

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        marine_attack_totals.append(sub.marine_attacks_total)

        if sub.marine_attacks_total > 0:
            oath_pct_per_battle.append(
                100.0 * sub.marine_attacks_on_oath / sub.marine_attacks_total
            )
            # Doctrines: count how many marine attacks landed in a
            # (round, mode) bucket where the AI rotation grants the +1.
            doc_fires = 0
            for rnd, n in sub.marine_ranged_attacks_by_round.items():
                if _doctrines_fires_in_round(rnd, "ranged"):
                    doc_fires += n
            for rnd, n in sub.marine_melee_attacks_by_round.items():
                if _doctrines_fires_in_round(rnd, "melee"):
                    doc_fires += n
            doctrines_pct_per_battle.append(
                100.0 * doc_fires / sub.marine_attacks_total
            )

        if sub.marine_oc_samples:
            marine_oc_means.append(statistics.mean(sub.marine_oc_samples))
            opp_oc_means.append(statistics.mean(sub.opp_oc_samples))

    # Marines win rate from A's perspective.
    a_wins = wins.get("A", 0)
    b_wins = wins.get("B", 0)
    draws = wins.get(None, 0)
    total = a_wins + b_wins + draws
    wr = (a_wins / total * 100.0) if total else 0.0

    return {
        "opp": opponent,
        "wr": wr,
        "n": total,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        "marine_attacks_mean": (
            statistics.mean(marine_attack_totals) if marine_attack_totals else 0.0
        ),
        "oath_pct_mean": (
            statistics.mean(oath_pct_per_battle) if oath_pct_per_battle else 0.0
        ),
        "doctrines_pct_mean": (
            statistics.mean(doctrines_pct_per_battle)
            if doctrines_pct_per_battle else 0.0
        ),
        "marine_oc_mean": (
            statistics.mean(marine_oc_means) if marine_oc_means else 0.0
        ),
        "opp_oc_mean": statistics.mean(opp_oc_means) if opp_oc_means else 0.0,
    }


def _install_uid_capture_subscriber():
    """A subscriber that re-fills _UID_LOOKUP at BattleStarted time so
    UnitShot / UnitFought handlers can resolve attacker_uid to a Unit.

    BattleStarted carries InitialUnit snapshots WITHOUT references back to
    live Unit instances, so we can't fill via the event. Instead, we hook
    via the armies' units list at Battle construction. See run_matchup_v2.
    """
    pass


def run_matchup_v2(opponent: str) -> Dict:
    """Same as run_matchup, but pre-fills _UID_LOOKUP before battle.run()
    so attacker faction resolution works for the very first attack.

    We exploit Battle.__init__'s line `self._assign_uids = ...` — actually
    _assign_uids is called inside run(), so to get uids set BEFORE run we
    call it manually after constructing the Battle. The simulator's run()
    will call it again, but uids are based on a counter so values stay
    stable (the counter resets, but it iterates the same units list in the
    same order, so uid strings match).
    """
    global _UID_LOOKUP

    wins = Counter()
    rounds_played: List[int] = []
    oath_pct_per_battle: List[float] = []
    doctrines_pct_per_battle: List[float] = []
    marine_oc_means: List[float] = []
    opp_oc_means: List[float] = []
    marine_attack_totals: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 9001
        random.seed(seed)
        marines = build_faction_random_army(
            "A", MARINES, POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not marines.units or not opp.units:
            continue

        sub = DiagSubscriber(marines.name, opp.name)
        battle = Battle(marines, opp, map_=DEFAULT_MAP, subscribers=[sub])

        # Pre-fill the uid lookup so events fired during run() have a
        # resolvable attacker. Call _assign_uids manually; run() will
        # call it again, but with the same units list in the same order
        # so uid assignments stay stable.
        battle._assign_uids()
        _UID_LOOKUP = {}
        for u in marines.units:
            _UID_LOOKUP[u.uid] = u
        for u in opp.units:
            _UID_LOOKUP[u.uid] = u

        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        marine_attack_totals.append(sub.marine_attacks_total)

        if sub.marine_attacks_total > 0:
            oath_pct_per_battle.append(
                100.0 * sub.marine_attacks_on_oath / sub.marine_attacks_total
            )
            doc_fires = 0
            for rnd, n in sub.marine_ranged_attacks_by_round.items():
                if _doctrines_fires_in_round(rnd, "ranged"):
                    doc_fires += n
            for rnd, n in sub.marine_melee_attacks_by_round.items():
                if _doctrines_fires_in_round(rnd, "melee"):
                    doc_fires += n
            doctrines_pct_per_battle.append(
                100.0 * doc_fires / sub.marine_attacks_total
            )

        if sub.marine_oc_samples:
            marine_oc_means.append(statistics.mean(sub.marine_oc_samples))
            opp_oc_means.append(statistics.mean(sub.opp_oc_samples))

    a_wins = wins.get("A", 0)
    b_wins = wins.get("B", 0)
    draws = wins.get(None, 0)
    total = a_wins + b_wins + draws
    wr = (a_wins / total * 100.0) if total else 0.0

    return {
        "opp": opponent,
        "wr": wr,
        "n": total,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        "marine_attacks_mean": (
            statistics.mean(marine_attack_totals) if marine_attack_totals else 0.0
        ),
        "oath_pct_mean": (
            statistics.mean(oath_pct_per_battle) if oath_pct_per_battle else 0.0
        ),
        "doctrines_pct_mean": (
            statistics.mean(doctrines_pct_per_battle)
            if doctrines_pct_per_battle else 0.0
        ),
        "marine_oc_mean": (
            statistics.mean(marine_oc_means) if marine_oc_means else 0.0
        ),
        "opp_oc_mean": statistics.mean(opp_oc_means) if opp_oc_means else 0.0,
    }


def main() -> None:
    print(
        f"Marines (Gladius Strike Force) diagnostic — N={N_BATTLES} per matchup,"
        f" {POINTS} pts."
    )
    print(
        f"{'opp':24s} {'WR%':>6s} {'rnd':>5s} {'attk':>6s} "
        f"{'oath%':>7s} {'doc%':>7s} {'M_OC':>6s} {'O_OC':>6s}"
    )
    print("-" * 80)
    results = []
    for opp in OPPONENTS:
        r = run_matchup_v2(opp)
        results.append(r)
        print(
            f"{r['opp']:24s} {r['wr']:>6.1f} {r['rounds_mean']:>5.2f}"
            f" {r['marine_attacks_mean']:>6.1f}"
            f" {r['oath_pct_mean']:>7.2f} {r['doctrines_pct_mean']:>7.2f}"
            f" {r['marine_oc_mean']:>6.2f} {r['opp_oc_mean']:>6.2f}"
        )

    print("-" * 80)
    # Aggregate
    mean_oath = statistics.mean(r["oath_pct_mean"] for r in results)
    mean_doc = statistics.mean(r["doctrines_pct_mean"] for r in results)
    mean_moc = statistics.mean(r["marine_oc_mean"] for r in results)
    mean_ooc = statistics.mean(r["opp_oc_mean"] for r in results)
    mean_wr = statistics.mean(r["wr"] for r in results)
    print(
        f"{'OVERALL':24s} {mean_wr:>6.1f}"
        f" {'':5s} {'':6s}"
        f" {mean_oath:>7.2f} {mean_doc:>7.2f}"
        f" {mean_moc:>6.2f} {mean_ooc:>6.2f}"
    )


if __name__ == "__main__":
    main()
