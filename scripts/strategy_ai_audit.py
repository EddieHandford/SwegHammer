"""Faction-neutral strategy AI audit (auto-loop iter 1 Cluster C).

Quantifies five strategy.py / simulator.py decision points across 30 mixed
vanilla battles to surface the highest-leverage AI gaps. Diagnostic only —
emits a console table; no simulator mutation.

Run:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.strategy_ai_audit
"""
from __future__ import annotations

import os
import random
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable,
               [sys.executable, "-m", "scripts.strategy_ai_audit"] + sys.argv[1:],
               os.environ)

from code.army_builder import build_faction_random_army
from code.events import (
    EventLog, UnitActivated, UnitShot, UnitFought, UnitCharged, UnitKilled,
    UnitMoved, StratagemFired, RoundStarted,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig
from code.roles import classify

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes", "Thousand Sons",
    "Leagues of Votann",
]

N_BATTLES = 30


def _name_lookup(army, uid: str):
    for u in army.units:
        if u.uid == uid:
            return u
    return None


def _profile_for(uid: str, a, b):
    u = _name_lookup(a, uid) or _name_lookup(b, uid)
    return u.profile if u else None


def run_audit():
    # ---- Per-area counters ----
    shoot_target_picks = Counter()            # what role gets shot at
    shoot_should_have_picked = 0              # alternative was strictly better
    shoot_total = 0
    shoot_hp_remaining_at_pick: List[float] = []   # HP frac of target

    fight_target_nearest_wasted = 0           # fight picker chose nearest but a better in-range option existed
    fight_total = 0

    charge_target_roles = Counter()           # what roles get charged
    charge_into_brick_count = 0               # charged a HEAVY (T8+, save 2+) when a fragile option was in range
    charge_total = 0

    activation_first_uid_role = Counter()     # role of first unit activated per army-turn
    activation_character_before_led = 0       # leader activated before led unit (good)
    activation_character_after_led = 0
    activation_total_leaders = 0

    strat_fire_round = Counter()              # round each strat fired
    strat_total_fired = 0
    strat_fire_by_name: Dict[str, Counter] = defaultdict(Counter)   # name -> round

    move_capture_to_already_held = 0          # CAPTURE intent to objective already controlled by us
    move_steal_to_empty = 0
    move_total = 0

    rng_base = random.Random(20260516)
    pairings: List[Tuple[str, str, int]] = []
    while len(pairings) < N_BATTLES:
        a = rng_base.choice(FACTIONS)
        b = rng_base.choice(FACTIONS)
        if a == b:
            continue
        pairings.append((a, b, len(pairings)))

    for a_fac, b_fac, seed in pairings:
        random.seed(seed)
        a = build_faction_random_army("A", a_fac, 1000, rng=random.Random(seed))
        b = build_faction_random_army("B", b_fac, 1000, rng=random.Random(seed + 50000))
        if not a.units or not b.units:
            continue
        log = EventLog()
        battle = Battle(a, b, map_=DEFAULT_MAP, subscribers=[log],
                        rules=RulesConfig.vanilla_10e())
        battle.run()

        events = list(log.events)
        # Build a uid -> profile / role lookup once per battle.
        role_for: Dict[str, str] = {}
        side_for: Dict[str, str] = {}
        for u in a.units:
            try:
                role_for[u.uid] = classify(u.profile)
            except Exception:
                role_for[u.uid] = "?"
            side_for[u.uid] = "A"
        for u in b.units:
            try:
                role_for[u.uid] = classify(u.profile)
            except Exception:
                role_for[u.uid] = "?"
            side_for[u.uid] = "B"

        # ---- Activation ordering: first activated this round (per side) ----
        cur_round = 0
        seen_in_round: Dict[str, set] = {"A": set(), "B": set()}
        led_first: Dict[str, set] = {"A": set(), "B": set()}   # uids of leaders that activated
        for ev in events:
            if isinstance(ev, RoundStarted):
                cur_round = ev.round_num
                seen_in_round = {"A": set(), "B": set()}
                led_first = {"A": set(), "B": set()}
            elif isinstance(ev, UnitActivated):
                army_letter = "A" if ev.army_name == a.name else "B"
                if ev.unit_uid in seen_in_round[army_letter]:
                    continue
                if not seen_in_round[army_letter]:
                    role = role_for.get(ev.unit_uid, "?")
                    activation_first_uid_role[role] += 1
                seen_in_round[army_letter].add(ev.unit_uid)
                # Track CHARACTER vs led-squad activation order. A leader is
                # any unit with CHARACTER keyword; we score it as "before-led"
                # if it activates and a same-army INFANTRY of same name-base
                # has not yet activated.
                u = _name_lookup(a, ev.unit_uid) or _name_lookup(b, ev.unit_uid)
                if u is None:
                    continue
                kw = u.profile.unit_keywords or ()
                if "CHARACTER" in kw:
                    activation_total_leaders += 1
                    # Has any non-character INFANTRY teammate from same army
                    # already activated this round?
                    own_army = a if u in a.units else b
                    teammate_activated = False
                    for other_uid in seen_in_round[army_letter]:
                        if other_uid == ev.unit_uid:
                            continue
                        ou = _name_lookup(own_army, other_uid)
                        if ou is None:
                            continue
                        okw = ou.profile.unit_keywords or ()
                        if "INFANTRY" in okw and "CHARACTER" not in okw:
                            teammate_activated = True
                            break
                    if teammate_activated:
                        activation_character_after_led += 1
                    else:
                        activation_character_before_led += 1

        # ---- Shoot target picks ----
        for ev in events:
            if isinstance(ev, UnitShot):
                shoot_total += 1
                # Target's profile & remaining HP frac.
                tgt = _name_lookup(a, ev.target_uid) or _name_lookup(b, ev.target_uid)
                if tgt is not None:
                    role = role_for.get(ev.target_uid, "?")
                    shoot_target_picks[role] += 1
                    frac = max(0.0, ev.target_hp_after / max(1.0, tgt.profile.health))
                    shoot_hp_remaining_at_pick.append(frac)

        # ---- Fight target picks (uses nearest — sub-optimal) ----
        for ev in events:
            if isinstance(ev, UnitFought):
                fight_total += 1
                # Simulator picks nearest unconditionally. If multiple enemies
                # were in 1.5" at the strike moment, that's a documentable
                # waste. We can't reconstruct positions perfectly post-hoc, so
                # we proxy with "the chosen target was a HORDE/SCREEN-type
                # role" vs alternative — if the attacker is MELEE/DUAL with
                # high DPA hitting a chaff role, that's the well-known
                # nearest-bias problem.
                attacker_role = role_for.get(ev.attacker_uid, "?")
                target_role = role_for.get(ev.target_uid, "?")
                if attacker_role in ("MELEE", "DUAL") and target_role == "HORDE":
                    fight_target_nearest_wasted += 1

        # ---- Charge target picks ----
        for ev in events:
            if isinstance(ev, UnitCharged):
                charge_total += 1
                tgt = _name_lookup(a, ev.target_uid) or _name_lookup(b, ev.target_uid)
                if tgt is None:
                    continue
                role = role_for.get(ev.target_uid, "?")
                charge_target_roles[role] += 1
                # "Brick" target: HEAVY/MONSTER, save 2/3+ and T>=8.
                p = tgt.profile
                if p.toughness >= 8 and p.save <= 3:
                    charge_into_brick_count += 1

        # ---- Stratagem firing ----
        cur_round = 0
        for ev in events:
            if isinstance(ev, RoundStarted):
                cur_round = ev.round_num
            elif isinstance(ev, StratagemFired):
                strat_total_fired += 1
                strat_fire_round[cur_round] += 1
                strat_fire_by_name[ev.stratagem_name][cur_round] += 1

    # ---- Report ----
    out: List[str] = []
    out.append("# Strategy AI Audit (iter 1 Cluster C, vanilla 10e, N=30)\n")
    out.append("\n## 1. Shoot target picks (role distribution)\n")
    out.append(f"Total UnitShot events: {shoot_total}\n")
    for role, n in sorted(shoot_target_picks.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * n / max(1, shoot_total)
        out.append(f"  {role:8s}  {n:5d}  {pct:5.1f}%\n")
    if shoot_hp_remaining_at_pick:
        mean_hp = sum(shoot_hp_remaining_at_pick) / len(shoot_hp_remaining_at_pick)
        out.append(f"Mean target HP-frac AFTER shot (lower=killed): {mean_hp:.2f}\n")

    out.append("\n## 2. Fight target picks (simulator uses nearest)\n")
    out.append(f"Total UnitFought events: {fight_total}\n")
    out.append(f"MELEE/DUAL attacking HORDE-role targets: {fight_target_nearest_wasted} "
               f"({100.0 * fight_target_nearest_wasted / max(1, fight_total):.1f}%)\n")
    out.append("(MELEE bricks fighting whoever's nearest, not the best target — sim\n"
               "calls `min(enemies, key=distance)` in `_do_fight`, ignoring per-target\n"
               "kill-potential / threat-back. The shoot picker has a screen-bonus but\n"
               "the fight picker does NOT.)\n")

    out.append("\n## 3. Charge target picks\n")
    out.append(f"Total UnitCharged events: {charge_total}\n")
    for role, n in sorted(charge_target_roles.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * n / max(1, charge_total)
        out.append(f"  {role:8s}  {n:5d}  {pct:5.1f}%\n")
    out.append(f"Charges into 'brick' targets (T8+ S<=3): {charge_into_brick_count} "
               f"({100.0 * charge_into_brick_count / max(1, charge_total):.1f}%)\n")

    out.append("\n## 4. Activation ordering (first unit per army-turn)\n")
    for role, n in sorted(activation_first_uid_role.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * n / max(1, sum(activation_first_uid_role.values()))
        out.append(f"  {role:8s}  {n:5d}  {pct:5.1f}%\n")
    total_leader_evs = activation_character_before_led + activation_character_after_led
    if total_leader_evs:
        pct_before = 100.0 * activation_character_before_led / total_leader_evs
        out.append(f"\nLeader activates BEFORE led teammate: "
                   f"{activation_character_before_led}/{total_leader_evs} "
                   f"({pct_before:.1f}%)\n")
        out.append(f"Leader activates AFTER led teammate:  "
                   f"{activation_character_after_led}/{total_leader_evs} "
                   f"({100.0 - pct_before:.1f}%)\n")

    out.append("\n## 5. Stratagem firing cadence\n")
    out.append(f"Total StratagemFired events: {strat_total_fired}\n")
    for rd in sorted(strat_fire_round):
        n = strat_fire_round[rd]
        pct = 100.0 * n / max(1, strat_total_fired)
        out.append(f"  Round {rd}: {n:5d}  ({pct:5.1f}%)\n")
    out.append("\nTop-fired stratagems (round distribution):\n")
    name_totals = sorted(
        ((nm, sum(rd.values())) for nm, rd in strat_fire_by_name.items()),
        key=lambda kv: -kv[1],
    )[:10]
    for nm, tot in name_totals:
        rds = strat_fire_by_name[nm]
        rd_str = ", ".join(f"R{r}={rds[r]}" for r in sorted(rds))
        out.append(f"  {nm:35s}  total={tot:4d}  ({rd_str})\n")

    text = "".join(out)
    print(text)
    return text


if __name__ == "__main__":
    run_audit()
