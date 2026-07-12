"""Line-of-sight and cover fidelity instrument (terrain-and-line-of-sight program,
Phase 1 saturation-quantification).

READ-ONLY. Requires NO simulator edits and NO gate: it installs runtime wrappers
on ``Unit.attack``, ``Battle._do_shoot`` and ``Map.has_line_of_sight`` (all class
methods, restored on exit), runs a fixed-seed slate of single battles across mixed
faction pairs, and re-derives, for every RESOLVED ranged attack, what the real 10e
visibility and Benefit-of-Cover rules would have done on the sim's CURRENT map
geometry. It quantifies the terrain-fidelity gap BEFORE any build.

Why this instrument exists (the honest question it answers)
-----------------------------------------------------------
The terrain-realism proposal (docs/TERRAIN_REALISM_PROPOSAL.md) and the make-
terrain-real decision-ledger entry both assert "shooting has NO line of sight ...
walls never block a shot". The code contradicts that: since 2026-05-16
(commit 7a5ff80e) ``Battle._do_shoot`` filters shooting candidates through
``Map.has_line_of_sight``, which treats RUIN and OBSCURING footprints as real
occluders (whole-rectangle, with the 10e endpoint-inside / AIRCRAFT / TOWERING
exceptions). So line-of-sight target LEGALITY already exists. What this instrument
measures is therefore three distinct numbers, not one:

  1. CANDIDATE-STAGE DENIAL RATE. Of every in-range (shooter, target) candidate
     pair the sim evaluates, what fraction does the sim's own line-of-sight
     actually deny? This validates or refutes the "~45% denied" code comment and
     the "no line of sight exists" proposal claim. Reported per faction (via the
     ``_do_shoot`` context wrapper) and as the authoritative aggregate from the
     built-in ``TERRAIN_LOS_STATS`` counter (SWEG_TERRAIN_LOS routes the identical
     check through code.sim.los.has_los and populates it byte-identically).

  2. RESOLVED-SHOT BLOCKED FRACTION. Of shots that actually FIRED, what fraction
     have a shot line (attacker centre -> target centre) that a strict real-rules
     reading (every RUIN/OBSCURING footprint an Obscuring blocker) would occlude,
     split by weapon class (direct vs Indirect Fire; indirect is exempt from
     visibility). For DIRECT fire this is expected to be ~0 -- the sim already
     filtered those candidates by the same geometry -- which is itself the finding
     (the sim's resolved direct shots already respect Obscuring geometry). A
     non-zero residual is quantization/edge noise. For INDIRECT fire a positive
     fraction is expected and correct (indirect may shoot the unseen).

  3. COVER FIDELITY. The sim grants Benefit of Cover purely from the TARGET's
     position (``cover_at(target.position)``, angle-independent). This measures
     (a) how often that flat tax fires, (b) how often an ANGLE-DEPENDENT real-rules
     reading (target within cover with the shooter OUTSIDE that piece, or a cover
     piece intervening on the segment) would grant cover, and the two disagreement
     classes: FALSE cover (flat tax fired but the shooter stands in the same piece
     as the target -> no real occlusion) and MISSED cover (a cover piece is
     genuinely intervening but the sim's position-only lookup ignores it).

Every reading is reported on BOTH the production (default ``_competitive_terrain``)
geometry AND the sourced dense GW Pariah Nexus layouts (``SWEG_TERRAIN_DENSE``,
built in-process here), so the map-DENSITY question -- is the sim's terrain faithful
to real competitive boards, independent of the line-of-sight math -- is answered
with the same instrument.

Usage (PYTHONHASHSEED=0 for the project's determinism convention):
  PYTHONHASHSEED=0 python -m scripts.diag_los_blocked
  PYTHONHASHSEED=0 python -m scripts.diag_los_blocked --points 2000 --seed 7
  PYTHONHASHSEED=0 python -m scripts.diag_los_blocked --default-only

Single battles only; no evaluation, no RNG-stream perturbation (the wrappers only
read state and delegate), byte-identical to an unpatched run.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.map import Map, TerrainType, _segment_rect_intersects
from code.maps import STOCK_MAPS, _dense_competitive_terrain
from code.simulator import Battle, TERRAIN_LOS_STATS
from code.units import Unit

# Cover-granting terrain the sim's cover_at treats as Benefit of Cover in
# Battle._do_shoot (LIGHT_COVER / HEAVY_COVER / RUIN -- note OBSCURING is NOT in
# the sim's cover-firing set, a separate fidelity detail flagged in the writeup).
_SIM_COVER_TYPES = (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.RUIN)
# Real-rules sight blockers (whole-footprint Obscuring reading): Ruins and Woods.
_SIGHT_BLOCK_TYPES = (TerrainType.RUIN, TerrainType.OBSCURING)
# Cover-granting pieces for the angle-dependent real-cover proxy (any terrain that
# grants Benefit of Cover: the cover types plus Woods, which grants cover in 10e).
_REAL_COVER_TYPES = (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER,
                     TerrainType.RUIN, TerrainType.OBSCURING)

# A fixed, deployment-order-agnostic slate of mixed pairs chosen to load the
# durability watch-list (Death Guard / Imperial Knights / Chaos Knights over-poles,
# Astra Militarum under-pole) against a spread of gunlines and horde/mobility lists.
DEFAULT_PAIRS = (
    ("Astra Militarum", "Imperial Knights"),
    ("T'au Empire", "Death Guard"),
    ("Adeptus Astartes", "Orks"),
    ("Thousand Sons", "Astra Militarum"),
    ("Chaos Knights", "Adeptus Mechanicus"),
    ("Necrons", "Aeldari"),
    ("Adepta Sororitas", "Death Guard"),
    ("Astra Militarum", "T'au Empire"),
)

# Map rotation + the dense-layout key each rotation map is drawn with (matches
# code.maps: the stock map's dense_layout argument). Lets the dense pass rebuild
# the identical board with the sourced GW footprints, in-process.
ROTATION = (
    ("crucible_of_battle", "crucible_of_battle"),
    ("take_and_hold", "take_and_hold"),
    ("hammer_and_anvil", "hammer_and_anvil"),
    ("tipping_point", "tipping_point"),
    ("search_and_destroy", "search_and_destroy"),
)


# ---------------------------------------------------------------------------
# Real-rules geometry (mirrors the sim's own code.map._los_compute so the
# "would real visibility block this?" reading is the same rule the sim cites,
# applied at exact continuous positions instead of the sim's 0.5-inch grid).
# ---------------------------------------------------------------------------
def real_sight_blocked(apos, tpos, terrain, a_kw, t_kw) -> bool:
    """True if a strict whole-footprint Obscuring reading occludes apos->tpos.

    RUIN and OBSCURING footprints block sight unless an endpoint is inside the
    piece (10e see-in / see-out), TOWERING lifts OBSCURING, and AIRCRAFT lifts
    RUIN (either endpoint) -- the exact exceptions code.map.has_line_of_sight
    encodes. This is the sim's OWN rule; running it here on resolved shots shows
    how closely the sim's grid-quantized legality already matches it."""
    aircraft = ("AIRCRAFT" in a_kw) or ("AIRCRAFT" in t_kw)
    towering = ("TOWERING" in a_kw) or ("TOWERING" in t_kw)
    for terr in terrain:
        if terr.type is TerrainType.OBSCURING:
            if towering:
                continue
            if terr.contains(apos) or terr.contains(tpos):
                continue
            if _segment_rect_intersects(apos, tpos, terr):
                return True
        elif terr.type is TerrainType.RUIN:
            if terr.contains(apos) or terr.contains(tpos):
                continue
            if _segment_rect_intersects(apos, tpos, terr):
                if aircraft:
                    continue
                return True
    return False


def cover_classification(apos, tpos, terrain) -> tuple:
    """(sim_cover, real_cover, false_cover, missed_cover) booleans for one shot.

    sim_cover    : the flat positional tax -- target stands in a LIGHT/HEAVY/RUIN
                   piece (exactly the Battle._do_shoot cover_at condition).
    real_cover   : an angle-aware reading grants Benefit of Cover -- the target is
                   within a cover piece the SHOOTER is not also within (genuine
                   body-in-terrain cover) OR a cover piece intervenes on the shot
                   segment (intervening-terrain cover).
    false_cover  : sim_cover fired but the only covering piece the target sits in
                   also contains the shooter -> point-blank same-feature, no real
                   occlusion (the clearest angle-independence error).
    missed_cover : real intervening-terrain cover applies but the sim's position-
                   only lookup granted none (the flat tax's blind spot).
    """
    target_pieces = [t for t in terrain
                     if t.type in _REAL_COVER_TYPES and t.contains(tpos)]
    sim_pieces = [t for t in terrain
                  if t.type in _SIM_COVER_TYPES and t.contains(tpos)]
    sim_cover = bool(sim_pieces)
    attacker_in_same = any(t.contains(apos) for t in target_pieces)
    within_cover = bool(target_pieces) and not attacker_in_same
    intervening = any(
        t.type in _REAL_COVER_TYPES
        and not t.contains(tpos) and not t.contains(apos)
        and _segment_rect_intersects(apos, tpos, t)
        for t in terrain
    )
    real_cover = within_cover or intervening
    false_cover = sim_cover and not real_cover
    missed_cover = real_cover and not sim_cover
    return sim_cover, real_cover, false_cover, missed_cover


# ---------------------------------------------------------------------------
# Accumulators (module-level so the class wrappers can reach them).
# ---------------------------------------------------------------------------
def _new_class_row():
    return {"shots": 0, "blocked_strict": 0, "sim_no_los": 0, "overwatch": 0,
            "sim_cover": 0, "real_cover": 0, "false_cover": 0, "missed_cover": 0}


class Acc:
    def __init__(self):
        # (faction, "direct"|"indirect") -> class row
        self.by_class = defaultdict(_new_class_row)
        # faction -> [candidate_checks, candidate_denied]  (from the LoS wrapper)
        self.cand = defaultdict(lambda: [0, 0])
        self.los_stats = {"checked": 0, "denied": 0}  # authoritative aggregate


_ACC: Acc | None = None
_ACTIVE_MAP: Map | None = None
_CTX = {"faction": None}
# The most recent Map.has_line_of_sight call, stashed so the resolved-shot record
# can use the position the sim actually measured visibility/cover to. In
# Battle._do_shoot the sim computes cover_at(math_target.position) and
# has_line_of_sight(attacker.position, math_target.position) against the IN-RANGE
# model (math_target), THEN the defender may reallocate the wounds to a different,
# possibly-occluded model (shoot_target) -- faithful 10e (a unit visible via one
# model may have wounds allocated to any model). So the shot line the sim measured
# is attacker->math_target, captured here as the last LoS call, not attacker->
# shoot_target (the object passed to Unit.attack). Guarded on the attacker position
# so a stale stash from a different activation is never reused.
_LAST_LOS = None

_orig_attack = None
_orig_do_shoot = None
_orig_los = None


def _record_shot(attacker: Unit, target: Unit, has_los: bool, overwatch: bool,
                 map_: Map) -> None:
    if _ACC is None:
        return
    apos = attacker.position
    # Prefer the model the sim measured visibility/cover to (math_target), captured
    # from the immediately-preceding has_line_of_sight call for this attacker;
    # fall back to the wound-allocation target only if no matching stash exists.
    global _LAST_LOS
    if _LAST_LOS is not None and _LAST_LOS[0] == apos:
        _, tpos, a_kw, t_kw, _ = _LAST_LOS
    else:
        tpos = target.position
        a_kw = attacker.profile.unit_keywords or ()
        t_kw = target.profile.unit_keywords or ()
    _LAST_LOS = None
    faction = attacker.profile.faction or "?"
    klass = "indirect" if attacker.profile.indirect_fire else "direct"
    row = _ACC.by_class[(faction, klass)]
    row["shots"] += 1
    if overwatch:
        row["overwatch"] += 1
    if not has_los:
        row["sim_no_los"] += 1
    if real_sight_blocked(apos, tpos, map_.terrain, a_kw, t_kw):
        row["blocked_strict"] += 1
    sim_c, real_c, false_c, missed_c = cover_classification(apos, tpos, map_.terrain)
    row["sim_cover"] += int(sim_c)
    row["real_cover"] += int(real_c)
    row["false_cover"] += int(false_c)
    row["missed_cover"] += int(missed_c)


def _install():
    global _orig_attack, _orig_do_shoot, _orig_los
    _orig_attack = Unit.attack
    _orig_do_shoot = Battle._do_shoot
    _orig_los = Map.has_line_of_sight

    def attack_wrap(self, target, distance=0.0, mode="ranged", is_charging=False,
                    has_los=True, overwatch=False, alloc_next_fn=None):
        if mode == "ranged" and _ACTIVE_MAP is not None:
            _record_shot(self, target, has_los, overwatch, _ACTIVE_MAP)
        return _orig_attack(self, target, distance=distance, mode=mode,
                            is_charging=is_charging, has_los=has_los,
                            overwatch=overwatch, alloc_next_fn=alloc_next_fn)

    def do_shoot_wrap(self, attacker, attacker_army, defender_army):
        prev = _CTX["faction"]
        _CTX["faction"] = attacker.profile.faction or "?"
        try:
            return _orig_do_shoot(self, attacker, attacker_army, defender_army)
        finally:
            _CTX["faction"] = prev

    def los_wrap(self, attacker, target, attacker_keywords=None,
                 target_keywords=None):
        res = _orig_los(self, attacker, target,
                        attacker_keywords=attacker_keywords,
                        target_keywords=target_keywords)
        global _LAST_LOS
        _LAST_LOS = (attacker, target, tuple(attacker_keywords or ()),
                     tuple(target_keywords or ()), res)
        fac = _CTX["faction"]
        if fac is not None and _ACC is not None:
            row = _ACC.cand[fac]
            row[0] += 1
            if not res:
                row[1] += 1
        return res

    Unit.attack = attack_wrap
    Battle._do_shoot = do_shoot_wrap
    Map.has_line_of_sight = los_wrap


def _uninstall():
    Unit.attack = _orig_attack
    Battle._do_shoot = _orig_do_shoot
    Map.has_line_of_sight = _orig_los


# ---------------------------------------------------------------------------
# Battle runner
# ---------------------------------------------------------------------------
def _run_slate(pairs, seed: int, points: float, dense: bool, acc: Acc) -> None:
    """Run one battle per pair; ``dense`` swaps the production terrain for the
    sourced GW dense layout (built in-process, bypassing the import-time env gate).
    SWEG_TERRAIN_LOS=1 is set so the built-in TERRAIN_LOS_STATS candidate counter
    is populated (byte-identical to the default legality check)."""
    global _ACTIVE_MAP, _ACC
    _ACC = acc
    os.environ["SWEG_TERRAIN_LOS"] = "1"
    TERRAIN_LOS_STATS["checked"] = 0
    TERRAIN_LOS_STATS["denied"] = 0
    for i, (fa, fb) in enumerate(pairs):
        map_key, dense_key = ROTATION[i % len(ROTATION)]
        stock = STOCK_MAPS[map_key]
        if dense:
            terr = _dense_competitive_terrain(stock.width, stock.height, dense_key)
            board = dataclasses.replace(stock, terrain=terr)
        else:
            board = stock
        a = build_faction_random_army("A", fa, points,
                                      rng=random.Random(seed + i),
                                      use_archetype=True)
        b = build_faction_random_army("B", fb, points,
                                      rng=random.Random(seed + i + 10000),
                                      use_archetype=True)
        _ACTIVE_MAP = board
        battle = Battle(a, b, map_=board)
        battle.run()
    _ACTIVE_MAP = None
    _ACC = None
    acc.los_stats["checked"] = TERRAIN_LOS_STATS["checked"]
    acc.los_stats["denied"] = TERRAIN_LOS_STATS["denied"]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def _pct(n, d):
    return f"{(100.0 * n / d):6.1f}%" if d else "     - "


def _report(label: str, acc: Acc, factions_order) -> None:
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")

    cs = acc.los_stats
    print("\n[1] CANDIDATE-STAGE line-of-sight denial (the sim's own has_line_of_sight)")
    print(f"    authoritative aggregate (TERRAIN_LOS_STATS, candidate filter only):")
    print(f"      in-range candidate pairs checked : {cs['checked']}")
    print(f"      denied by a Ruin/Woods occluder  : {cs['denied']}  "
          f"({_pct(cs['denied'], cs['checked']).strip()})")
    print("    per shooting faction (includes the 1 resolved-target recheck/shot,"
          " so very slightly diluted):")
    print(f"      {'faction':20s} {'checks':>8s} {'denied':>8s} {'denial-rate':>12s}")
    for fac in factions_order:
        if fac not in acc.cand:
            continue
        c, d = acc.cand[fac]
        print(f"      {fac:20s} {c:8d} {d:8d} {_pct(d, c):>12s}")

    print("\n[2] RESOLVED-SHOT blocked fraction (real whole-footprint Obscuring reading)")
    print(f"      {'faction':20s} {'class':>8s} {'shots':>7s} {'blk-strict':>11s}"
          f" {'sim-noLoS':>10s} {'overwatch':>10s}")
    tot = defaultdict(int)
    for (fac, klass) in sorted(acc.by_class.keys()):
        r = acc.by_class[(fac, klass)]
        print(f"      {fac:20s} {klass:>8s} {r['shots']:7d} "
              f"{_pct(r['blocked_strict'], r['shots']):>11s} "
              f"{_pct(r['sim_no_los'], r['shots']):>10s} "
              f"{r['overwatch']:10d}")
        for k in ("shots", "blocked_strict"):
            tot[(klass, k)] += r[k]
    for klass in ("direct", "indirect"):
        s = tot[(klass, "shots")]
        b = tot[(klass, "blocked_strict")]
        if s:
            print(f"      {'ALL':20s} {klass:>8s} {s:7d} {_pct(b, s):>11s}")

    print("\n[3] COVER fidelity (flat positional tax vs an angle-aware real reading)")
    print(f"      {'faction':20s} {'shots':>7s} {'sim-cov':>8s} {'real-cov':>9s}"
          f" {'false-cov':>10s} {'missed-cov':>11s}")
    cov = defaultdict(int)
    for fac in factions_order:
        srow = {"shots": 0, "sim_cover": 0, "real_cover": 0,
                "false_cover": 0, "missed_cover": 0}
        seen = False
        for (f, klass), r in acc.by_class.items():
            if f != fac:
                continue
            seen = True
            for k in srow:
                srow[k] += r[k]
        if not seen:
            continue
        for k in srow:
            cov[k] += srow[k]
        s = srow["shots"]
        print(f"      {fac:20s} {s:7d} {_pct(srow['sim_cover'], s):>8s} "
              f"{_pct(srow['real_cover'], s):>9s} "
              f"{_pct(srow['false_cover'], s):>10s} "
              f"{_pct(srow['missed_cover'], s):>11s}")
    s = cov["shots"]
    print(f"      {'ALL':20s} {s:7d} {_pct(cov['sim_cover'], s):>8s} "
          f"{_pct(cov['real_cover'], s):>9s} {_pct(cov['false_cover'], s):>10s} "
          f"{_pct(cov['missed_cover'], s):>11s}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--points", type=float, default=2000.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--default-only", action="store_true",
                    help="skip the SWEG_TERRAIN_DENSE comparison pass")
    args = ap.parse_args()

    if os.environ.get("PYTHONHASHSEED") != "0":
        print("WARNING: PYTHONHASHSEED is not 0 -- set it for the project's "
              "determinism convention (PYTHONHASHSEED=0 python -m scripts.diag_los_blocked).")

    pairs = DEFAULT_PAIRS
    factions_order = []
    for a, b in pairs:
        for f in (a, b):
            if f not in factions_order:
                factions_order.append(f)

    print(f"terrain / line-of-sight fidelity instrument")
    print(f"pairs ({len(pairs)}), seed {args.seed}, {args.points:.0f} pts, "
          f"archetype lists, single battles")
    for a, b in pairs:
        print(f"  - {a}  vs  {b}")

    _install()
    try:
        default_acc = Acc()
        _run_slate(pairs, args.seed, args.points, dense=False, acc=default_acc)
        _report("PRODUCTION MAPS (default _competitive_terrain -- the eval geometry)",
                default_acc, factions_order)

        if not args.default_only:
            dense_acc = Acc()
            _run_slate(pairs, args.seed, args.points, dense=True, acc=dense_acc)
            _report("SOURCED DENSE MAPS (SWEG_TERRAIN_DENSE GW Pariah Nexus layouts)",
                    dense_acc, factions_order)

            print(f"\n{'=' * 78}\nDENSITY DELTA (dense minus default, aggregate)\n{'=' * 78}")
            dc, dd = default_acc.los_stats["checked"], default_acc.los_stats["denied"]
            ec, ed = dense_acc.los_stats["checked"], dense_acc.los_stats["denied"]
            print(f"  candidate denial rate  default {_pct(dd, dc).strip():>7s}"
                  f"   dense {_pct(ed, ec).strip():>7s}")
    finally:
        _uninstall()

    print("\nReading guide:")
    print("  [1] is the number the 'no line of sight exists' claim must be checked")
    print("      against: a substantial denial rate means the sim DOES block shots.")
    print("  [2] blk-strict ~0 for DIRECT fire means resolved direct shots already")
    print("      respect Obscuring geometry (the sim's legality filter is faithful);")
    print("      a positive INDIRECT figure is correct (indirect ignores visibility).")
    print("  [3] false-cov is the angle-independence error rate (flat tax fired with")
    print("      the shooter in the same piece); missed-cov is intervening cover the")
    print("      position-only lookup ignores. The gap between sim-cov and real-cov")
    print("      sizes the cover-model fidelity cost.")
    print("  Density: compare [1]/[2]/[3] across the two map passes to judge whether")
    print("  the production geometry is as blocking as real competitive boards.")


if __name__ == "__main__":
    main()
