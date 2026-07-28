"""Five-facet comparative + broad instrumented audit for the Astra Militarum
sc60a residual pole (sim 25.3 vs real 45.3, gated 16.8). TIER 2 read-only
audit (owner brief 2026-07-08). Private scratch script — do not import from
production code; run standalone.

Measures FIVE facets from ONE shared instrumented battle pass (so all five
share the same battle budget, ~146 games total):

  1. SITTING ON OBJECTIVES  — per-round fraction of the army's Objective
     Control actually parked within control radius of ANY marker, and of
     markers it actually CONTROLS (won the VP on), rounds 1-5.
  2. DENYING ENEMY VP       — the opponent's primary+secondary VP per game
     vs AM, compared to that same opponent's average VP when it plays (as
     the SAME side-B role) against a spread of reference-faction attackers.
     Decomposed kill-secondary vs positional-secondary vs objective-action.
  3. ACTIVELY ACHIEVING SECONDARIES — attempt rate: alive units carrying a
     live `pursue_target` (positional pursuit: Behind Enemy Lines / Engage)
     or a live `action_this_round` (Cleanse / Establish Locus / Sabotage /
     Recover Assets / Burn / Terraform) at each round's end, plus secondary
     VP attributed to its source (kill / positional / objective-action).
  4. KILLING THE RIGHT THINGS — ranged+melee damage dealt allocated by
     target class (CHAFF: OC<=1 & 1-wound; SCORING_INFANTRY: everything
     else non-vehicle/monster/character; CHARACTER; MONSTER_VEHICLE), plus
     units-finished-per-damage-dealt and the overkill/waste share (damage
     poured into 1-wound chaff beyond the 1 wound needed to kill it).
  5. SURVIVING AS EXPECTED — realized points-lost-per-round vs a stat-
     implied expectation built from the sim's own `_ranged_expected_wounds`
     (ranged) / `_kill_potential_wounds` (melee) helpers, applied to the
     PRE-BATTLE rosters. This is a clearly-labelled PROXY (see
     `_expected_incoming_wounds_per_round` docstring for exactly what it
     does and does not capture) — not a rules-perfect expectation.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._facet_audit_am
"""
from __future__ import annotations

import random
import sys
from collections import defaultdict
from statistics import mean

from code.army_builder import build_faction_random_army
from code.events import (
    EventLog, RoundStarted, RoundEnded, ObjectiveScored, UnitShot, UnitFought,
    UnitKilled,
)
from code.simulator import Battle
from code.strategy import _kill_potential_wounds
import code.secondaries as S
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

FOCUS = "Astra Militarum"

# The 12-opponent panel is BOTH (a) AM's own opponent spread and (b) the
# shared opponent panel each reference faction plays against — this makes
# every opponent's B-side stats frame-matched (always the B/defending side)
# whether it faced AM or a reference, which is what facet 2 needs.
AM_OPPONENTS = [
    "Adeptus Astartes", "Genestealer Cults",          # the two named craters
    "Death Guard", "Imperial Knights",                 # the durable pair
    "Orks", "Tyranids",                                # hordes / monsters
    "Necrons", "T'au Empire",                          # mid attrition / gunline
    "Aeldari", "Adeptus Custodes",                      # fast-fragile / elite-durable
    "Chaos Space Marines", "World Eaters",              # mid / melee-aggressive
]
REF_FACTIONS = ["Genestealer Cults", "T'au Empire", "Necrons",
                "Adeptus Astartes", "Death Guard"]
AM_SEEDS = [0, 1, 2]
REF_SEEDS = [0, 1]


def _target_class(profile) -> str:
    kw = set(profile.unit_keywords or ())
    if kw & {"MONSTER", "VEHICLE"}:
        return "monster_vehicle"
    if "CHARACTER" in kw:
        return "character"
    if (profile.oc or 0) <= 1 and (profile.health or 1) <= 1:
        return "chaff"
    return "scoring_infantry"


def _expected_incoming_wounds_per_round(attackers, defenders) -> float:
    """PROXY for facet 5. For each attacking unit, take the BETTER of its
    ranged (`Battle._ranged_expected_wounds`) or melee (`_kill_potential_wounds`)
    expected-wounds figure against each defending unit, averaged over the
    defending roster (a stand-in for "a representative target" since real
    target selection is not modelled here), then summed over all attackers.

    What this does NOT capture: actual positioning/range/charge feasibility,
    focus-fire concentration (this is a per-attacker AVERAGE against the
    roster, not a worst-case or a most-likely-target read), multi-phase
    activity (a unit that shoots AND fights), or round-to-round attrition of
    the attacking roster itself (the figure is a flat per-round rate from the
    STARTING rosters of both sides, not accounting for the attackers dying
    too). It is offered as the sensible cheap proxy the brief invited, not a
    rules-perfect expectation — read the ratio comparatively (AM vs baselines),
    not as an absolute physics claim.
    """
    if not defenders or not attackers:
        return 0.0
    total = 0.0
    for au in attackers:
        ap = au.profile
        vals = []
        for du in defenders:
            rew = Battle._ranged_expected_wounds(ap, du)
            mew = _kill_potential_wounds(ap, du.profile)
            vals.append(max(rew, mew))
        total += sum(vals) / len(vals)
    return total


# ---------------------------------------------------------------------------
# Secondary-VP-by-source patch (kill / positional / objective-action), keyed
# by SIDE (A/B) via `battle.a`/`battle.b` identity — generalises
# scripts/diag_secondary_breakdown.py's me/opp bucket to any A-vs-B pairing.
# ---------------------------------------------------------------------------
_CUR = {"battle": None, "bucket": None}
_real_round = S.score_round_delta
_real_pos = S.score_position_delta
_real_cleanse = Battle._score_cleanse
_real_sabotage = Battle._score_sabotage
_real_board = Battle._score_board_secondaries


def _side_of_army(army) -> str | None:
    bat = _CUR["battle"]
    if bat is None:
        return None
    if army is bat.a:
        return "A"
    if army is bat.b:
        return "B"
    return None


def _side_of_units(units_list) -> str | None:
    bat = _CUR["battle"]
    if bat is None:
        return None
    if units_list is bat.a.units:
        return "A"
    if units_list is bat.b.units:
        return "B"
    return None


def _patched_round(snapshot, enemy_units_now, *a, **k):
    bid, np_, cth, assn = _real_round(snapshot, enemy_units_now, *a, **k)
    b = _CUR["bucket"]
    if b is not None:
        killed_side = _side_of_units(enemy_units_now)
        scorer_side = {"A": "B", "B": "A"}.get(killed_side)
        if scorer_side is not None:
            b[f"{scorer_side}_kill"] += bid + np_ + cth + assn
    return bid, np_, cth, assn


def _patched_pos(own_units, *a, **k):
    eng, bel = _real_pos(own_units, *a, **k)
    b = _CUR["bucket"]
    if b is not None:
        side = _side_of_units(own_units)
        if side is not None:
            b[f"{side}_pos"] += eng + bel
    return eng, bel


def _patched_cleanse(self, army, opponent, own_is_army_a, *a, **k):
    vp = _real_cleanse(self, army, opponent, own_is_army_a, *a, **k)
    b = _CUR["bucket"]
    if b is not None and vp:
        side = _side_of_army(army)
        if side is not None:
            b[f"{side}_obj"] += vp
    return vp


def _patched_sabotage(self, army, own_is_army_a, *a, **k):
    vp = _real_sabotage(self, army, own_is_army_a, *a, **k)
    b = _CUR["bucket"]
    if b is not None and vp:
        side = _side_of_army(army)
        if side is not None:
            b[f"{side}_obj"] += vp
    return vp


def _patched_board(self, army, opponent, own_is_army_a, *a, **k):
    vp = _real_board(self, army, opponent, own_is_army_a, *a, **k)
    b = _CUR["bucket"]
    if b is not None and vp:
        side = _side_of_army(army)
        if side is not None:
            b[f"{side}_obj"] += vp
    return vp


def _install_patches() -> None:
    S.score_round_delta = _patched_round
    S.score_position_delta = _patched_pos
    Battle._score_cleanse = _patched_cleanse
    Battle._score_sabotage = _patched_sabotage
    Battle._score_board_secondaries = _patched_board


# ---------------------------------------------------------------------------
# Round-end snapshot subscriber (facet 3 attempt rate + facet 1 alive count)
# ---------------------------------------------------------------------------
class _RoundSnapshot:
    def __init__(self, a_army, b_army):
        self.a = a_army
        self.b = b_army
        self.by_round: dict = {}

    def _snap(self, army):
        alive = army.alive_units
        pursue = sum(1 for u in alive if getattr(u, "pursue_target", None) is not None)
        actions = defaultdict(int)
        for u in alive:
            act = getattr(u, "action_this_round", None)
            if act:
                actions[act] += 1
        return {"alive": len(alive), "pursue": pursue, "actions": dict(actions)}

    def on_event(self, e) -> None:
        if isinstance(e, RoundEnded):
            self.by_round[e.round_num] = {"A": self._snap(self.a), "B": self._snap(self.b)}


# ---------------------------------------------------------------------------
# The instrumented single-battle runner
# ---------------------------------------------------------------------------
def run_one(a_fac: str, b_fac: str, seed: int):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None

    a_oc_start = sum((u.profile.oc or 0) for u in a.units)
    b_oc_start = sum((u.profile.oc or 0) for u in b.units)
    a_pts_start = sum(u.profile.points_cost for u in a.units)
    b_pts_start = sum(u.profile.points_cost for u in b.units)
    a_exp_incoming = _expected_incoming_wounds_per_round(b.units, a.units)  # B shooting A
    b_exp_incoming = _expected_incoming_wounds_per_round(a.units, b.units)  # A shooting B

    log = EventLog()
    snap = _RoundSnapshot(a, b)
    bucket = defaultdict(float)
    _CUR["bucket"] = bucket

    battle = Battle(a, b, subscribers=[log, snap], map_=_pick_rotation_map(seed),
                     primary_mission=_pick_primary_mission(seed))
    _CUR["battle"] = battle
    result = battle.run()
    _CUR["battle"] = None
    _CUR["bucket"] = None

    # roster (uid -> (side, profile)) — built AFTER run() since uid is
    # assigned by Battle at start; a.units/b.units are the SAME objects
    # mutated in place, dead units remain in the list.
    roster = {}
    for u in a.units:
        roster[u.uid] = ("A", u.profile)
    for u in b.units:
        roster[u.uid] = ("B", u.profile)

    # facet 1 — per-round OC on any marker / controlled markers
    cur_round = 0
    oc_any = {"A": defaultdict(int), "B": defaultdict(int)}
    oc_ctrl = {"A": defaultdict(int), "B": defaultdict(int)}
    for e in log.events:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, ObjectiveScored):
            if e.a_oc:
                oc_any["A"][cur_round] += e.a_oc
                if e.army_name == "A":
                    oc_ctrl["A"][cur_round] += e.a_oc
            if e.b_oc:
                oc_any["B"][cur_round] += e.b_oc
                if e.army_name == "B":
                    oc_ctrl["B"][cur_round] += e.b_oc

    # facet 4 — damage by target class, kills, overkill-on-chaff; also feeds
    # facet 5's realized points-lost-by-round.
    dmg_by_class = {"A": defaultdict(float), "B": defaultdict(float)}
    dmg_total = {"A": 0.0, "B": 0.0}
    kills = {"A": 0, "B": 0}
    overkill_chaff = {"A": 0.0, "B": 0.0}
    killed_uids: set = set()
    pts_lost_by_round = {"A": defaultdict(float), "B": defaultdict(float)}
    cur_round = 0
    for e in log.events:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, (UnitShot, UnitFought)):
            att_side = roster.get(e.attacker_uid, (None, None))[0]
            tgt_side, tgt_prof = roster.get(e.target_uid, (None, None))
            if att_side is None or tgt_prof is None:
                continue
            cls = _target_class(tgt_prof)
            dmg_by_class[att_side][cls] += e.damage
            dmg_total[att_side] += e.damage
            if cls == "chaff":
                overkill_chaff[att_side] += max(0.0, e.damage - 1.0)
            if not e.target_alive_after and e.target_uid not in killed_uids:
                killed_uids.add(e.target_uid)
                kills[att_side] += 1
                if tgt_side is not None:
                    pts_lost_by_round[tgt_side][cur_round] += tgt_prof.points_cost

    # cumulative points-lost by round 1..5
    for side in ("A", "B"):
        run_tot = 0.0
        cum = {}
        for r in range(1, 6):
            run_tot += pts_lost_by_round[side].get(r, 0.0)
            cum[r] = run_tot
        pts_lost_by_round[side] = cum

    a_primary = battle._a_vp - battle._a_secondary_vp - battle._a_challenger_vp
    b_primary = battle._b_vp - battle._b_secondary_vp - battle._b_challenger_vp

    return {
        "a_fac": a_fac, "b_fac": b_fac, "seed": seed,
        "winner": result.winner or "D",
        "a_vp_capped": None, "b_vp_capped": None,  # filled below if needed
        "a_vp_total": battle._a_vp, "b_vp_total": battle._b_vp,
        "a_primary": a_primary, "b_primary": b_primary,
        "a_sec": battle._a_secondary_vp, "b_sec": battle._b_secondary_vp,
        "a_oc_start": a_oc_start, "b_oc_start": b_oc_start,
        "oc_any": oc_any, "oc_ctrl": oc_ctrl,
        "a_kill_vp": bucket.get("A_kill", 0.0), "b_kill_vp": bucket.get("B_kill", 0.0),
        "a_pos_vp": bucket.get("A_pos", 0.0), "b_pos_vp": bucket.get("B_pos", 0.0),
        "a_obj_vp": bucket.get("A_obj", 0.0), "b_obj_vp": bucket.get("B_obj", 0.0),
        "pursue_actions": snap.by_round,
        "dmg_by_class": dmg_by_class, "dmg_total": dmg_total,
        "kills": kills, "overkill_chaff": overkill_chaff,
        "a_pts_start": a_pts_start, "b_pts_start": b_pts_start,
        "a_exp_incoming": a_exp_incoming, "b_exp_incoming": b_exp_incoming,
        "pts_lost_by_round": pts_lost_by_round,
    }


# ---------------------------------------------------------------------------
# Battle plan + aggregation
# ---------------------------------------------------------------------------
def build_plan():
    plan = []
    for opp in AM_OPPONENTS:
        for s in AM_SEEDS:
            plan.append((FOCUS, opp, s, "AM"))
    for ref in REF_FACTIONS:
        for opp in AM_OPPONENTS:
            if opp == ref:
                continue
            for s in REF_SEEDS:
                plan.append((ref, opp, s, "REF"))
    return plan


def main() -> None:
    plan = build_plan()
    print(f"# facet audit — {len(plan)} planned battles", file=sys.stderr)
    results = []
    for i, (af, bf, s, tag) in enumerate(plan):
        r = run_one(af, bf, s)
        if r is not None:
            r["_tag"] = tag
            results.append(r)
        if (i + 1) % 20 == 0:
            print(f"...{i+1}/{len(plan)}", file=sys.stderr)

    import pickle
    with open("data/_facet_audit_am_raw.pkl", "wb") as fh:
        pickle.dump(results, fh)
    print(f"# {len(results)} battles completed, raw data -> data/_facet_audit_am_raw.pkl", file=sys.stderr)


if __name__ == "__main__":
    _install_patches()
    main()
