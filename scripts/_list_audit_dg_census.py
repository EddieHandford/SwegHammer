"""LIST AUDIT (Death Guard) scratch: build census of sim archetype Death Guard
armies with durability metrics, seed vs fill split.

Read-only. Replicates build_archetype_army's exact seed/fill sequence so the
boundary between the deterministic template seed and the random fill can be
recorded, then tabulates durability-per-point metrics on each half and on the
whole army, averaged over N sampled builds.

Run: PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._list_audit_dg_census
"""
import os
import random
import statistics
from collections import defaultdict

from code.units import UNIT_CATALOG
from code.army import Army
from code.archetypes import (
    ARCHETYPES,
    _effective_template,
    _instantiate_template,
    _random_fill,
)

FACTION = "Death Guard"
ARCH = "Virulent Vectorium"
BUDGET = 2000.0
N = 80


def build_split(seed):
    """Replicate build_archetype_army but record the seed/fill unit boundary.

    Mirrors code/archetypes.py build_archetype_army exactly at default env
    (SWEG_SEEDMAX unset -> min_models seed squads; SWEG_FILL_SQUADS default on).
    """
    rng = random.Random(seed)
    # Replicate build_archetype_army EXACTLY: with archetype_name=None the
    # production path consumes one rng.choice draw to pick the archetype even
    # when the faction has a single archetype (Death Guard -> Virulent
    # Vectorium). Omitting it offsets every subsequent draw, so the census
    # would sample a different-but-valid army than production. Consume it here.
    available = ARCHETYPES[FACTION]
    archetype_name = rng.choice(list(available.keys()))
    assert archetype_name == ARCH, archetype_name
    template = _effective_template(FACTION, available[archetype_name])
    counts = _instantiate_template(template, BUDGET, rng, faction=FACTION)
    army = Army(f"dg-{seed}")
    seed_max_mode = (os.environ.get("SWEG_SEEDMAX") or "").lower()
    for key, count in counts.items():
        profile = UNIT_CATALOG[key]
        squad_size = max(1, profile.min_models)
        if seed_max_mode == "1":
            squad_size = max(squad_size, profile.max_models or squad_size)
        for _ in range(count):
            army.add_squad(profile, squad_size)
    n_seed = len(army.units)
    remaining = BUDGET - army.total_points
    if remaining > 0:
        _random_fill(army, FACTION, remaining, rng, template=template)
    seed_units = army.units[:n_seed]
    fill_units = army.units[n_seed:]
    return army, seed_units, fill_units


def is_durable_platform(p):
    """A durable non-chaff platform: MONSTER/VEHICLE/TITANIC keyword OR a
    multi-wound elite brick (health >= 4). Excludes 1-2W chaff bodies."""
    kw = p.unit_keywords or ()
    if "MONSTER" in kw or "VEHICLE" in kw or "TITANIC" in kw:
        return True
    return p.health >= 4


def metrics(units):
    """Durability metrics over a list of per-model Unit instances."""
    if not units:
        return None
    n_models = len(units)
    total_pts = sum(u.profile.points_cost for u in units)
    total_wounds = sum(u.profile.health for u in units)
    # toughness weighted by wounds
    t_w = sum(u.profile.toughness * u.profile.health for u in units)
    avg_t = t_w / total_wounds if total_wounds else 0.0
    # coverage: fraction of WOUNDS behind each save layer
    w_with_invuln = sum(u.profile.health for u in units if u.profile.invuln_save <= 6)
    w_with_fnp = sum(u.profile.health for u in units if u.profile.fnp <= 6)
    w_2plus = sum(u.profile.health for u in units if u.profile.save <= 2)
    w_3plus = sum(u.profile.health for u in units if u.profile.save <= 3)
    # brick counts (per MODEL)
    n_t10 = sum(1 for u in units if u.profile.toughness >= 10)
    n_w15 = sum(1 for u in units if u.profile.health >= 15)
    n_brick = sum(1 for u in units if u.profile.toughness >= 10 or u.profile.health >= 15)
    # durable share of points
    durable_pts = sum(u.profile.points_cost for u in units if is_durable_platform(u.profile))
    veh_mon_pts = sum(
        u.profile.points_cost for u in units
        if any(x in (u.profile.unit_keywords or ()) for x in ("MONSTER", "VEHICLE", "TITANIC"))
    )
    return {
        "models": n_models,
        "points": total_pts,
        "wounds": total_wounds,
        "wpp": total_wounds / total_pts if total_pts else 0.0,
        "avg_T_by_w": avg_t,
        "invuln_cov": w_with_invuln / total_wounds if total_wounds else 0.0,
        "fnp_cov": w_with_fnp / total_wounds if total_wounds else 0.0,
        "save2_cov": w_2plus / total_wounds if total_wounds else 0.0,
        "save3plus_cov": w_3plus / total_wounds if total_wounds else 0.0,
        "n_T10": n_t10,
        "n_W15": n_w15,
        "n_brick": n_brick,
        "durable_share": durable_pts / total_pts if total_pts else 0.0,
        "vehmon_share": veh_mon_pts / total_pts if total_pts else 0.0,
    }


def mean_metrics(rows):
    keys = rows[0].keys()
    return {k: statistics.mean(r[k] for r in rows) for k in keys}


def main():
    whole_rows, seed_rows, fill_rows = [], [], []
    # per-key aggregation: models, points, squads across all builds
    key_models = defaultdict(int)
    key_points = defaultdict(float)
    key_seed_models = defaultdict(int)
    key_fill_models = defaultdict(int)
    key_builds_present = defaultdict(int)

    for seed in range(N):
        army, su, fu = build_split(seed)
        whole_rows.append(metrics(army.units))
        seed_rows.append(metrics(su))
        fr = metrics(fu)
        if fr:
            fill_rows.append(fr)
        present = set()
        for u in army.units:
            key_models[u.profile.name] += 1
            key_points[u.profile.name] += u.profile.points_cost
            present.add(u.profile.name)
        for u in su:
            key_seed_models[u.profile.name] += 1
        for u in fu:
            key_fill_models[u.profile.name] += 1
        for nm in present:
            key_builds_present[nm] += 1

    def show(label, rows):
        m = mean_metrics(rows)
        print(f"\n=== {label} (avg over {len(rows)} builds) ===")
        print(f"  models          : {m['models']:.1f}")
        print(f"  points          : {m['points']:.1f}")
        print(f"  total wounds     : {m['wounds']:.1f}")
        print(f"  wounds/point     : {m['wpp']:.4f}")
        print(f"  avg T (w-wtd)    : {m['avg_T_by_w']:.2f}")
        print(f"  invuln coverage  : {m['invuln_cov']*100:.1f}% of wounds")
        print(f"  feel-no-pain cov : {m['fnp_cov']*100:.1f}% of wounds")
        print(f"  save 2+ coverage : {m['save2_cov']*100:.1f}% of wounds")
        print(f"  save 3+ coverage : {m['save3plus_cov']*100:.1f}% of wounds")
        print(f"  T10+ models      : {m['n_T10']:.2f}")
        print(f"  W15+ models      : {m['n_W15']:.2f}")
        print(f"  bricks (T10|W15) : {m['n_brick']:.2f}")
        print(f"  durable-share    : {m['durable_share']*100:.1f}% of points")
        print(f"  vehicle/monster  : {m['vehmon_share']*100:.1f}% of points")

    print(f"BUILD CENSUS: {FACTION} / {ARCH} @ {BUDGET:.0f}pts, N={N}, defaults")
    show("WHOLE ARMY", whole_rows)
    show("SEED (template)", seed_rows)
    show("FILL (random)", fill_rows)

    print("\n=== PER-UNIT (avg per build) ===")
    print(f"{'unit':40s} {'mdl/bld':>8s} {'pts/bld':>8s} {'seed':>6s} {'fill':>6s} {'in%':>5s}")
    allkeys = sorted(key_models, key=lambda k: -key_points[k])
    for nm in allkeys:
        print(f"{nm[:40]:40s} {key_models[nm]/N:8.2f} {key_points[nm]/N:8.1f} "
              f"{key_seed_models[nm]/N:6.2f} {key_fill_models[nm]/N:6.2f} "
              f"{key_builds_present[nm]/N*100:5.0f}")


if __name__ == "__main__":
    main()
