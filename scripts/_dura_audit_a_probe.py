"""DURABILITY AUDIT A (read-only) — instrument the RANGED attack pipeline into
Knight bricks in replayed anchor games.

For a set of Astra Militarum / T'au Empire versus Chaos Knights (and Imperial
Knights) games reconstructed byte-exactly from the standing anchor
(data/_anchor_sc50a_n80_log.json), this:

  1. Enables the built-in SWEG_DURABILITY_INSTR hook (code/units.py) to collect
     realized effective saves / cover-applied / invuln-used rates per target
     class (VEHICLE vs INFANTRY) across every ranged hit in the games.
  2. Monkeypatches code.units.Unit.attack (from THIS scratch script only — no
     tracked file is modified) with a thin wrapper that, for every ranged
     attack call whose TARGET is a Knight brick, logs the attacker weapon,
     Strength, AP, the target's Toughness/Save/ranged-invuln, and then INDE-
     PENDENTLY re-derives the rule-correct wound target and save target and
     compares them against what the sim's own helpers (wound_probability /
     _prob_to_target and the save block) produce for the same inputs. Any
     mismatch is a pipeline divergence.
  3. Aggregates per (weapon, S/T) the fraction of activations that dealt zero.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dura_audit_a_probe
Writes nothing tracked; prints a report to stdout.
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._dura_audit_a_probe"] + sys.argv[1:],
        env=os.environ).returncode)

# Turn the built-in durability instrument on BEFORE importing units so the
# module-level gate reads it (it is read per-call, so order does not actually
# matter, but set it early for clarity).
os.environ["SWEG_DURABILITY_INSTR"] = "1"

import code.units as U
from code.units import wound_probability, _prob_to_target
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

KNIGHT_FACTIONS = {"Chaos Knights", "Imperial Knights"}

# ---- per-sequence capture ------------------------------------------------
seq_rows = []          # dict per ranged attack call into a Knight
wound_mismatches = []  # rule-derived vs code-helper disagreements

_orig_attack = U.Unit.attack


def _rule_wound_target(strength, toughness):
    """Independent hand-derivation of the printed S-vs-T chart (NOT the sim's
    function) so we can cross-check the sim's wound_probability/_prob_to_target."""
    if strength >= 2 * toughness:
        return 2
    if strength > toughness:
        return 3
    if strength == toughness:
        return 4
    if 2 * strength <= toughness:
        return 6
    return 5  # strength < toughness but not <= half


def _rule_save_target(save, ap, invuln_ranged, in_cover, cover_ap0_block):
    """Independent hand-derivation of the printed save step for a RANGED attack.
    ap is a non-positive int. Returns the effective save target (7 = none)."""
    save_after_ap = save - ap  # ap negative -> worse save
    if in_cover and not cover_ap0_block:
        save_after_ap = max(2, save_after_ap - 1)
    eff = min(save_after_ap, invuln_ranged) if invuln_ranged <= 6 else save_after_ap
    return eff


def _instrumented_attack(self, target, distance=0.0, mode="ranged",
                         is_charging=False, has_los=True, overwatch=False,
                         alloc_next_fn=None):
    is_ranged = (mode != "melee")
    tgt_is_knight = (target.profile.faction in KNIGHT_FACTIONS
                     and ("TITANIC" in (target.profile.unit_keywords or ())
                          or "WALKER" in (target.profile.unit_keywords or ())))
    hp_before = target.current_health
    dmg = _orig_attack(self, target, distance=distance, mode=mode,
                       is_charging=is_charging, has_los=has_los,
                       overwatch=overwatch, alloc_next_fn=alloc_next_fn)
    if is_ranged and tgt_is_knight:
        p = self.profile
        S = p.strength
        T = target.profile.toughness
        ap = p.ap
        sv = target.profile.save
        inv_r = target.profile.invuln_save_ranged
        sim_wt = _prob_to_target(wound_probability(S, T))
        rule_wt = _rule_wound_target(S, T)
        if sim_wt != rule_wt:
            wound_mismatches.append(
                {"weapon": p.weapon, "S": S, "T": T,
                 "sim_wound_target": sim_wt, "rule_wound_target": rule_wt})
        in_cover = bool(getattr(target, "in_cover", False))
        cover_ap0_block = (ap == 0 and sv <= 3)
        rule_st = _rule_save_target(sv, ap, inv_r, in_cover, cover_ap0_block)
        seq_rows.append({
            "attacker": p.name, "weapon": p.weapon, "S": S, "AP": ap,
            "wdps": round(p.weapon_damage_per_shot, 2), "attacks": p.attacks,
            "target": target.profile.name, "T": T, "Sv": sv, "inv_r": inv_r,
            "wound_target": sim_wt, "rule_save_target": rule_st,
            "in_cover": in_cover, "distance": round(distance, 1),
            "has_los": has_los, "dmg": round(dmg, 2),
            "hp_before": round(hp_before, 1),
        })
    return dmg


U.Unit.attack = _instrumented_attack


def replay_one(a_fac, b_fac, s):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=primary)
    return battle.run()


def main():
    anchor = json.load(open("data/_anchor_sc50a_n80_log.json", encoding="utf-8"))
    games = anchor["games"]
    shooters = ["Astra Militarum", "T'au Empire"]
    bricks = ["Chaos Knights", "Imperial Knights"]
    picked = []
    seen = defaultdict(int)
    for a_fac, b_fac, s, winner in games:
        pair = {a_fac, b_fac}
        for sh in shooters:
            for br in bricks:
                if pair == {sh, br}:
                    key = (sh, br)
                    if seen[key] < 3:
                        picked.append((a_fac, b_fac, s))
                        seen[key] += 1
    print(f"Replaying {len(picked)} shooter-vs-Knight games ({dict(seen)})")
    for a_fac, b_fac, s in picked:
        replay_one(a_fac, b_fac, s)

    print("\n==================== DURABILITY_INSTR (built-in) ====================")
    for cls, dd in sorted(U.DURABILITY_STATS.items()):
        h = dd["hits"] or 1
        print(f"  class={cls:8s} hits={dd['hits']:6d}  "
              f"mean_base_save={dd['base']/h:4.2f}  "
              f"mean_eff_save={dd['eff']/h:4.2f}  "
              f"mean_AP={dd['ap']/h:4.2f}  "
              f"cover_rate={dd['cover']/h:5.1%}  invuln_rate={dd['inv']/h:5.1%}")

    print("\n==================== WOUND-TARGET CROSS-CHECK ====================")
    print(f"  ranged-into-Knight attack calls logged: {len(seq_rows)}")
    print(f"  wound-target mismatches (rule vs sim helper): {len(wound_mismatches)}")
    for m in wound_mismatches[:20]:
        print("   MISMATCH", m)

    print("\n==================== PER-WEAPON SUMMARY (ranged into Knights) ====================")
    byw = defaultdict(lambda: {"n": 0, "zero": 0, "dmg": 0.0, "S": 0, "AP": 0,
                               "T": 0, "wt": 0, "rst": 0, "cover": 0})
    for r in seq_rows:
        k = (r["weapon"], r["S"], r["AP"], r["T"])
        d = byw[k]
        d["n"] += 1
        d["dmg"] += r["dmg"]
        d["S"] = r["S"]; d["AP"] = r["AP"]; d["T"] = r["T"]
        d["wt"] = r["wound_target"]; d["rst"] = r["rule_save_target"]
        d["cover"] += 1 if r["in_cover"] else 0
        if r["dmg"] <= 0.0:
            d["zero"] += 1
    print(f"  {'weapon':32s} {'S':>3} {'AP':>3} {'T':>3} {'wnd+':>4} {'sv+':>4} "
          f"{'n':>5} {'zero%':>6} {'avgdmg':>7} {'cover%':>6}")
    rows = sorted(byw.items(), key=lambda kv: -kv[1]["n"])
    for (w, S, AP, T), d in rows[:40]:
        print(f"  {str(w)[:32]:32s} {S:3d} {AP:3d} {T:3d} {d['wt']:4d} "
              f"{d['rst']:4d} {d['n']:5d} {d['zero']/d['n']:6.1%} "
              f"{d['dmg']/d['n']:7.2f} {d['cover']/d['n']:6.1%}")

    tot = len(seq_rows)
    zero = sum(1 for r in seq_rows if r["dmg"] <= 0.0)
    print(f"\n  OVERALL ranged-into-Knight activations dealing zero: "
          f"{zero}/{tot} = {zero/max(1,tot):.1%}")


if __name__ == "__main__":
    main()
