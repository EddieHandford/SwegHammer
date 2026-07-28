"""Manual-pilot LOOP engine — pilot the UNDER-pole against the AI over-pole,
batch-test a battery of pilot tactics against a cached baseline, and report the
paired win-flip delta for each. Harness-only: wraps the AI decision functions
(`pick_move_intent`, `pick_charge_target`) for army A; B keeps the real AI.

Goal of the loop: find pilot tactics that lift the under-pole's win rate toward
its real (Warp Friends) rate. Under-pole-only / asymmetric is fine (user frame).

The comparison is PAIRED on the seed (the sim is deterministic per seed), so a
tactic's effect is read as win-flips (loss->win, win->loss) vs the baseline, not
just an aggregate — clean signal at low N.

Run:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.pilot_manual <N> [under] [over]
"""
from __future__ import annotations

import random
import sys

from code import strategy, simulator
from code.army_builder import build_faction_random_army
from code.events import EventLog, RoundEnded
from code.simulator import Battle
from code.strategy import (classify, _score_profile, _kill_potential_wounds,
                           _is_melee_class)
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

MY_ARMY = "A"
CONFIG: dict = {}                 # the active tactic; wrappers read this
_ORIG_MOVE = strategy.pick_move_intent
_ORIG_CHARGE = strategy.pick_charge_target


def _dist(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _oc(alive_units, obj) -> int:
    return sum((u.profile.oc or 0) for u in alive_units
               if _dist(u.position, (obj.x, obj.y)) <= obj.control_radius)


# ---- MY under-pole policy (reads CONFIG) ------------------------------------
def my_move_intent(unit, friendly, enemy, map_, army_plan=None,
                   _phase_their_oc=None, _phase_our_oc=None):
    role = classify(_score_profile(unit))
    if CONFIG.get("heavy_hold") and role == "HEAVY":
        return unit.position, "HOLD(pilot)"

    # KITE: a fragile ranged unit retreats from an approaching melee threat
    # (a charge next turn would lock/kill it). Move directly away at full Normal
    # move (no Advance → keeps shooting). The glass-cannon survival tactic.
    if CONFIG.get("kite") and role in ("SHOOTY", "HEAVY", "DUAL"):
        threats = [e for e in enemy.alive_units
                   if _is_melee_class(_score_profile(e))
                   and _dist(unit.position, e.position) < 14.0]
        if threats:
            th = min(threats, key=lambda e: _dist(unit.position, e.position))
            dx = unit.position[0] - th.position[0]
            dy = unit.position[1] - th.position[1]
            m = (dx * dx + dy * dy) ** 0.5 or 1.0
            return (unit.position[0] + dx / m * 100.0,
                    unit.position[1] + dy / m * 100.0), "KITE(pilot)"

    objs = list(map_.objectives)
    wants_move = (CONFIG.get("contest_spare") or CONFIG.get("surgical_contest")
                  or CONFIG.get("screen_home") or CONFIG.get("sticky_race"))
    if objs and wants_move:
        # only redirect a GENUINELY SPARE unit (not already on/near a marker)
        on_any = any(_dist(unit.position, (o.x, o.y)) <= o.control_radius for o in objs)
        if not on_any:
            fa, ea = friendly.alive_units, enemy.alive_units
            our = {id(o): _oc(fa, o) for o in objs}
            their = {id(o): _oc(ea, o) for o in objs}
            own = unit.profile.oc or 0
            # STICKY-RACE: a sticky_objective unit (AM = Cadian Shock Troops) grabs
            # the nearest marker AM would CONTROL after it arrives, to claim sticky
            # ownership — then the marker keeps scoring even after the body dies /
            # leaves (issue #85). AM's real counter to being out-held by durable
            # bodies: bank markers early, don't physically hold them to the end.
            if CONFIG.get("sticky_race") and getattr(unit.profile, "sticky_objective", False):
                grabbable = [o for o in objs
                             if their[id(o)] < our[id(o)] + own]   # AM controls after arrival
                if grabbable:
                    t = min(grabbable, key=lambda o: _dist(unit.position, (o.x, o.y)))
                    return (t.x, t.y), "STICKY(pilot)"
            if CONFIG.get("surgical_contest"):
                # only markers we are CLOSE to flipping (one more body wins it)
                winnable = [o for o in objs if their[id(o)] > 0
                            and 0 <= their[id(o)] - our[id(o)] < max(own, 1)]
                if winnable:
                    t = min(winnable, key=lambda o: _dist(unit.position, (o.x, o.y)))
                    return (t.x, t.y), "FLIP(pilot)"
            if CONFIG.get("screen_home"):
                # reinforce our nearest held marker that an enemy is approaching
                held = [o for o in objs if our[id(o)] > their[id(o)]]
                threatened = [o for o in held
                              if any(_dist(e.position, (o.x, o.y)) < 14 for e in ea)]
                if threatened:
                    t = min(threatened, key=lambda o: _dist(unit.position, (o.x, o.y)))
                    return (t.x, t.y), "SCREEN(pilot)"
            if CONFIG.get("contest_spare"):
                contested = [o for o in objs
                             if their[id(o)] > 0 and our[id(o)] <= their[id(o)]]
                if contested:
                    t = min(contested, key=lambda o: _dist(unit.position, (o.x, o.y)))
                    return (t.x, t.y), "CONTEST(pilot)"

    return _ORIG_MOVE(unit, friendly, enemy, map_, army_plan,
                      _phase_their_oc, _phase_our_oc)


def my_charge_target(attacker, enemy, map_=None):
    # FORCE-MELEE-KNIGHT (Chaos Knights Karnivore exploit): a melee unit charges
    # the most-damaged big enemy Knight — in the fight phase the Knight's 5++ is
    # ranged-only, so melee hits at full effect. Overrides the AI's pick (which
    # may decline the durable target). The sim's charge resolution enforces range.
    if CONFIG.get("force_melee_knight") and _is_melee_class(_score_profile(attacker)):
        knights = [u for u in enemy.alive_units if _is_big_knight(u.profile)]
        if knights:
            tgt = min(knights, key=lambda u: u.current_health)
            return tgt, _dist(attacker.position, tgt.position)
    target, dist = _ORIG_CHARGE(attacker, enemy, map_)
    if target is None:
        return target, dist
    if CONFIG.get("charge_durable") and (target.profile.toughness or 0) >= 9:
        return None, 0.0
    if CONFIG.get("charge_futile"):
        kp = _kill_potential_wounds(attacker.profile, target.profile)
        if kp < (target.profile.wounds or 1):   # can't even remove one model
            return None, 0.0
    return target, dist


def _is_big_knight(profile) -> bool:
    """A Questoris-class Knight (toughness >= 11) — the big target the anti-Knight
    playbooks concentrate fire / melee on (excludes T9 Armiger War Dogs)."""
    return (profile.toughness or 0) >= 11


def _pilot_focus_cb(battle, attacker, attacker_army, pool):
    """Anti-Knight SHOOT-TARGET: army A concentrates ANTI-TANK fire on the
    most-damaged big enemy Knight (crack one Knight at a time — the universal
    anti-Knight rule from the research). Anti-infantry weapons fall through to the
    AI so they keep clearing chaff. Defers for army B / gate off / no Knight in
    range (returns None)."""
    if attacker_army.name != MY_ARMY:
        return None
    aa = battle._is_antiarmour_weapon(attacker.profile)
    if CONFIG.get("anti_knight_shoot") and aa:
        knights = [u for u in pool if _is_big_knight(u.profile)]
        if knights:
            return min(knights, key=lambda u: u.current_health)
    # FOCUS-THREAT: anti-infantry fire finishes multi-wound SCORING bodies
    # (Khorne Berzerkers W2, OC1) instead of the AI's lowest-health pick, which
    # wastes fire on 1-wound chaff (Jakhals). Audit finding: AM poured 33 damage
    # into Jakhals vs only 21 into the 30 Berzerkers that actually hold objectives.
    # Skips 1-wound chaff and durable bricks (T>8) the anti-infantry gun can't crack.
    if CONFIG.get("focus_threat") and not aa:
        threats = [u for u in pool
                   if (u.profile.oc or 0) >= 1
                   and (u.profile.health or 1) >= 2
                   and (u.profile.toughness or 0) <= 8]
        if threats:
            return min(threats, key=lambda u: u.current_health)
    # CHASE-VP: pick the shootable target whose DESTRUCTION scores the most VP,
    # among targets this weapon can actually hurt (the target-economics floor).
    # VP terms mirror the real Pariah Nexus secondaries: Bring It Down (kill a
    # MONSTER/VEHICLE), No Prisoners (FINISH a whole unit -> boost near-dead
    # squads), plus objective-denial (an enemy holder). Faithful "play to score"
    # objective function the production picker lacks (it keys on threat/health,
    # not VP yield). Uses the battle's live enemy squads + objectives.
    if CONFIG.get("chase_vp"):
        objs = list(battle.map.objectives)
        enemy = battle.b if attacker_army is battle.a else battle.a
        best = None
        best_score = -1.0
        for u in pool:
            kp = _kill_potential_wounds(attacker.profile, u.profile)
            if kp <= 0.0:
                continue  # can't hurt it -> never worth VP-chasing (economics floor)
            mult = 1.0
            kw = set(u.profile.unit_keywords or ())
            if kw & {"MONSTER", "VEHICLE"}:
                mult *= 3.0                       # Bring It Down (2-6 VP/kill)
            if any(_dist(u.position, (o.x, o.y)) <= o.control_radius for o in objs):
                mult *= 1.5                       # deny an objective holder (primary)
            squad_hp = sum(
                max(0.0, x.current_health) for x in enemy.alive_units
                if getattr(x, "squad_id", -9) == getattr(u, "squad_id", -8)
            )
            mult *= 1.0 + 3.0 / (1.0 + squad_hp)  # No Prisoners: finish near-dead units
            score = mult / max(1.0, u.current_health)  # VP-weighted, prefer finishable
            if score > best_score:
                best_score, best = score, u
        if best is not None:
            return best
    # CLEAR-HOLDER: concentrate the WHOLE army's fire on the single enemy unit
    # that is controlling an objective we CONTEST (our OC on it > 0 but <=
    # theirs), to clear it off the marker and flip the objective — the narrow
    # "displace the objective-holder specifically" mechanic (NOT blanket
    # focus-fire on threats, which the ledger proved wastes fire on bricks).
    # Returns the SAME holder for every attacker this phase -> concentration.
    # `_crack` variant additionally skips holders this weapon cannot dent.
    if CONFIG.get("clear_holder") or CONFIG.get("clear_holder_crack"):
        objs = list(battle.map.objectives)
        ours = attacker_army.alive_units
        best = None; best_key = None
        for u in pool:
            for o in objs:
                if _dist(u.position, (o.x, o.y)) > o.control_radius:
                    continue
                their = _oc(pool, o)
                our = _oc(ours, o)
                # only markers we contest but do not yet control (clearing the
                # holder is what flips it) — skip markers we already own and
                # markers we have no stake in.
                if our <= 0 or their < our:
                    continue
                if CONFIG.get("clear_holder_crack"):
                    kp = _kill_potential_wounds(attacker.profile, u.profile)
                    if kp <= 0.0:
                        break
                # rank: closest-to-flip marker first (small their-our gap),
                # then the holder we can most finish (lowest current health).
                key = (their - our, u.current_health)
                if best_key is None or key < best_key:
                    best, best_key = u, key
                break
        if best is not None:
            return best
    # SHOOT-HOLDERS-ANY: the ledger's asymmetric +2.5 lever, reproduced —
    # NON-anti-armour fire finishes the most-wounded enemy unit standing on ANY
    # objective (contested or not), so anti-tank stays free for bricks. Broader
    # than clear_holder (no our-OC gate), which is why it fires far more often.
    if CONFIG.get("shoot_holders_any") and not aa:
        objs = list(battle.map.objectives)
        onmark = [u for u in pool
                  if any(_dist(u.position, (o.x, o.y)) <= o.control_radius for o in objs)]
        if onmark:
            return min(onmark, key=lambda u: u.current_health)
    return None


def _move_wrapper(unit, friendly, enemy, map_, army_plan=None,
                  _phase_their_oc=None, _phase_our_oc=None):
    if friendly.name == MY_ARMY:
        return my_move_intent(unit, friendly, enemy, map_, army_plan,
                              _phase_their_oc, _phase_our_oc)
    return _ORIG_MOVE(unit, friendly, enemy, map_, army_plan,
                      _phase_their_oc, _phase_our_oc)


def _charge_wrapper(attacker, enemy, map_=None):
    if getattr(attacker, "army", None) == MY_ARMY:
        return my_charge_target(attacker, enemy, map_)
    return _ORIG_CHARGE(attacker, enemy, map_)


def _patch():
    strategy.pick_move_intent = _move_wrapper
    simulator.pick_move_intent = _move_wrapper
    strategy.pick_charge_target = _charge_wrapper
    simulator.pick_charge_target = _charge_wrapper
    simulator.Battle._pilot_focus = staticmethod(_pilot_focus_cb)


def _unpatch():
    strategy.pick_move_intent = _ORIG_MOVE
    simulator.pick_move_intent = _ORIG_MOVE
    strategy.pick_charge_target = _ORIG_CHARGE
    simulator.pick_charge_target = _ORIG_CHARGE
    simulator.Battle._pilot_focus = None


def _winner(under, over, seed):
    # FAITHFUL to scripts.evaluate_vs_meta._play_pairing so harness win rates match
    # the calibration anchor log: seed the global RNG per game, rotate a PRIMARY
    # MISSION from the CA-2025-26 deck (_pick_primary_mission), and decide the winner
    # via the sim's official BattleResult.winner — NOT raw victory points (which
    # diverged from the calibration by 20+ points).
    random.seed(seed)
    a = build_faction_random_army("A", under, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", over, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return "D", 0, 0
    log = EventLog()
    r = Battle(a, b, subscribers=[log], map_=_pick_rotation_map(seed),
               primary_mission=_pick_primary_mission(seed)).run()
    rends = [e for e in log.events if isinstance(e, RoundEnded)]
    # Report the capped standing (what decides the winner), not the uncapped total.
    av, bv = (rends[-1].a_vp_capped, rends[-1].b_vp_capped) if rends else (0, 0)
    return (r.winner or "D"), av, bv


def _run(under, over, seeds, cfg):
    global CONFIG
    CONFIG = cfg
    out = {}
    for s in seeds:
        out[s] = _winner(under, over, s)
    return out


# ---- the tactic battery (edited each loop iteration) ------------------------
# Anti-Knight strategy battery (research playbooks for AM / Chaos Knights vs IK).
# Run for under="Astra Militarum" and under="Chaos Knights", over="Imperial Knights".
BATTERY = [
    ("all-off (==baseline check)", {}),
    # --- VP-conversion battery: AM's close losses vs a gunline keep equal/more
    #     points-remaining but score no midfield objectives + no secondaries.
    #     Test objective-CONTEST-when-behind + bank-early + kill-the-holder. ---
    ("surgical_contest",     {"surgical_contest": True}),        # spare bodies flip near-won markers
    ("contest_spare",        {"contest_spare": True}),           # spare bodies contest enemy-held markers
    ("sticky_race",          {"sticky_race": True}),             # Cadians bank markers early, don't camp home
    ("surgical+sticky",      {"surgical_contest": True, "sticky_race": True}),
    ("shoot_holders_any",    {"shoot_holders_any": True}),       # clear the enemy holder off the marker
    ("contest+shoot_holders",{"contest_spare": True, "shoot_holders_any": True}),
    ("focus_threat",         {"focus_threat": True}),            # finish scoring bodies
    ("chase_vp",             {"chase_vp": True}),                # shoot for VP yield (BiD/NoPrisoners/deny)
]


SCAN_OPPONENTS = [
    "Imperial Knights", "T'au Empire", "Astra Militarum", "Leagues of Votann",
    "Necrons", "Adeptus Custodes", "World Eaters", "Adeptus Astartes",
    "Chaos Space Marines", "Tyranids",
]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    under = sys.argv[2] if len(sys.argv) > 2 else "Astra Militarum"
    over = sys.argv[3] if len(sys.argv) > 3 else "Imperial Knights"
    mode = sys.argv[4] if len(sys.argv) > 4 else "battery"
    seeds = list(range(n))

    # SCAN: the under-pole's baseline win% vs a spread of opponents — to pick the
    # matchup where it genuinely under-performs (a valid single-matchup test).
    if mode == "scan":
        print(f"# SCAN — {under} baseline win% vs opponents  N={n}")
        for opp in SCAN_OPPONENTS:
            if opp == under:
                continue
            w = _run(under, opp, seeds, {})
            aw = sum(1 for s in seeds if w[s][0] == "A")
            print(f"  {under:18} vs {opp:22} {100*aw/n:5.1f}%  ({aw}/{n})")
        return

    print(f"# PILOT LOOP — {under} (A, piloted) vs {over} (B, AI)  N={n}")
    _patch()
    try:
        base = _run(under, over, seeds, {})
        base_w = sum(1 for s in seeds if base[s][0] == "A")
        base_avp = sum(base[s][1] for s in seeds) / n
        base_bvp = sum(base[s][2] for s in seeds) / n
        print(f"BASELINE: A win {100*base_w/n:5.1f}%  ({base_w}/{n})  "
              f"mean VP {base_avp:.1f}-{base_bvp:.1f}")
        print(f"{'tactic':30} {'Awin%':>6} {'Δpp':>5} {'L>W':>4} {'W>L':>4} {'meanVP A':>9}")
        for name, cfg in BATTERY:
            w = _run(under, over, seeds, cfg)
            aw = sum(1 for s in seeds if w[s][0] == "A")
            lw = sum(1 for s in seeds if base[s][0] != "A" and w[s][0] == "A")
            wl = sum(1 for s in seeds if base[s][0] == "A" and w[s][0] != "A")
            avp = sum(w[s][1] for s in seeds) / n
            d = 100 * (aw - base_w) / n
            print(f"{name:30} {100*aw/n:6.1f} {d:+5.1f} {lw:4d} {wl:4d} {avp:9.1f}")
    finally:
        _unpatch()


if __name__ == "__main__":
    main()
