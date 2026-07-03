"""LIST AUDIT (Death Guard) scratch: durability-per-point of SOURCED real
May-2026 competitive Death Guard lists, priced on the SAME sim/BSData
catalogue as the census (the correct footing to isolate list-COMPOSITION
fidelity from the separate pricing question — both sides use identical
points and defensive statlines, so any gap is pure composition).

Real lists reconstructed from repo-cited + sourced structure (web decklist
sites are JS-rendered / 403 and could not be fetched; per the brief this
falls back to the sources already cited in the repo and reasons from BSData
values):

  Real-A  Virulent Vectorium, Mortarion durability-brick build. Structure:
          WAVE250_LIST_REALISM.md (3 Grimhammer lists Jul/Oct/Nov 2025) +
          tabletopbattles Detachment Focus: Virulent Vectorium
          (Daemon Prince "in most, if not all, competitive lists").
  Real-B  Mortarion's Hammer "cheap hulls" vehicle-swarm. Structure:
          spikeybits Warhammer Open Tacoma 1st (Steve Trimble) extraction
          (2 Lord of Contagion + 1 Lord of Virulence, 3 Deathshroud squads,
          3 Foetid Bloat-Drones, 2 Myphitic Blight-Haulers, 3 Plagueburst
          Crawlers, 3 Poxwalkers squads; no Mortarion, no Plague Marines).
          Given at full Trimble structure AND trimmed to fit the 2000 sim
          budget (sim over-prices the hulls vs GW, so 3 crawlers + full
          bodies exceed 2000 sim points).

Run: PYTHONIOENCODING=utf-8 python -m scripts._list_audit_dg_real
"""
from code.units import UNIT_CATALOG


def is_durable_platform(p):
    kw = p.unit_keywords or ()
    if "MONSTER" in kw or "VEHICLE" in kw or "TITANIC" in kw:
        return True
    return p.health >= 4


def metrics_from_list(entries):
    """entries: list of (catalogue_key, n_squads, models_per_squad)."""
    units = []  # (profile, ) one per model
    for key, n_squads, per_squad in entries:
        p = UNIT_CATALOG[key]
        for _ in range(n_squads * per_squad):
            units.append(p)
    n_models = len(units)
    total_pts = sum(u.points_cost for u in units)
    total_wounds = sum(u.health for u in units)
    t_w = sum(u.toughness * u.health for u in units)
    avg_t = t_w / total_wounds if total_wounds else 0.0
    w_invuln = sum(u.health for u in units if u.invuln_save <= 6)
    w_fnp = sum(u.health for u in units if u.fnp <= 6)
    w_2 = sum(u.health for u in units if u.save <= 2)
    w_3 = sum(u.health for u in units if u.save <= 3)
    n_t10 = sum(1 for u in units if u.toughness >= 10)
    n_w15 = sum(1 for u in units if u.health >= 15)
    n_brick = sum(1 for u in units if u.toughness >= 10 or u.health >= 15)
    durable_pts = sum(u.points_cost for u in units if is_durable_platform(u))
    veh_mon_pts = sum(
        u.points_cost for u in units
        if any(x in (u.unit_keywords or ()) for x in ("MONSTER", "VEHICLE", "TITANIC"))
    )
    return {
        "models": n_models, "points": total_pts, "wounds": total_wounds,
        "wpp": total_wounds / total_pts, "avg_T_by_w": avg_t,
        "invuln_cov": w_invuln / total_wounds, "fnp_cov": w_fnp / total_wounds,
        "save2_cov": w_2 / total_wounds, "save3plus_cov": w_3 / total_wounds,
        "n_T10": n_t10, "n_W15": n_w15, "n_brick": n_brick,
        "durable_share": durable_pts / total_pts, "vehmon_share": veh_mon_pts / total_pts,
    }


REAL_A = [  # Virulent Vectorium, Mortarion durability-brick (~2000 sim pts)
    ("death_guard_mortarion", 1, 1),
    ("death_guard_daemon_prince_of_nurgle", 1, 1),
    ("death_guard_lord_of_contagion", 1, 1),
    ("death_guard_lord_of_virulence", 1, 1),
    ("death_guard_deathshroud_terminators", 2, 3),
    ("death_guard_foetid_bloat_drone", 3, 1),
    ("death_guard_myphitic_blight_hauler", 2, 1),
    ("death_guard_poxwalkers", 3, 10),
    ("death_guard_plague_marines", 2, 5),
]

REAL_B_FULL = [  # Mortarion's Hammer vehicle-swarm, full Trimble structure
    ("death_guard_lord_of_contagion", 2, 1),
    ("death_guard_lord_of_virulence", 1, 1),
    ("death_guard_deathshroud_terminators", 3, 3),
    ("death_guard_foetid_bloat_drone", 3, 1),
    ("death_guard_myphitic_blight_hauler", 2, 1),
    ("death_guard_plagueburst_crawler", 3, 1),
    ("death_guard_poxwalkers", 3, 10),
]

REAL_B_2K = [  # same, trimmed to fit 2000 sim points (1 fewer Deathshroud squad)
    ("death_guard_lord_of_contagion", 2, 1),
    ("death_guard_lord_of_virulence", 1, 1),
    ("death_guard_deathshroud_terminators", 2, 3),
    ("death_guard_foetid_bloat_drone", 3, 1),
    ("death_guard_myphitic_blight_hauler", 2, 1),
    ("death_guard_plagueburst_crawler", 3, 1),
    ("death_guard_poxwalkers", 3, 10),
]

# Sim census whole-army averages (from _list_audit_dg_census.py, N=80,
# build_split validated byte-identical to production build_faction_random_army)
SIM = {
    "models": 50.6, "points": 1983.9, "wounds": 149.4, "wpp": 0.0753,
    "avg_T_by_w": 7.93, "invuln_cov": 0.679, "fnp_cov": 0.285,
    "save2_cov": 0.472, "save3plus_cov": 0.823, "n_T10": 3.02, "n_W15": 1.00,
    "n_brick": 3.02, "durable_share": 0.817, "vehmon_share": 0.552,
}


def show(label, m):
    print(f"\n=== {label} ===")
    print(f"  models {m['models']:.1f} | points {m['points']:.0f} | wounds {m['wounds']:.0f}")
    print(f"  wounds/point     : {m['wpp']:.4f}")
    print(f"  avg T (w-wtd)    : {m['avg_T_by_w']:.2f}")
    print(f"  invuln coverage  : {m['invuln_cov']*100:.1f}%")
    print(f"  feel-no-pain cov : {m['fnp_cov']*100:.1f}%")
    print(f"  save 2+ coverage : {m['save2_cov']*100:.1f}%")
    print(f"  save 3+ coverage : {m['save3plus_cov']*100:.1f}%")
    print(f"  T10+ / W15+ / brick: {m['n_T10']:.1f} / {m['n_W15']:.1f} / {m['n_brick']:.1f}")
    print(f"  durable-share    : {m['durable_share']*100:.1f}%")
    print(f"  vehicle/monster  : {m['vehmon_share']*100:.1f}%")


def main():
    ra = metrics_from_list(REAL_A)
    rbf = metrics_from_list(REAL_B_FULL)
    rb2 = metrics_from_list(REAL_B_2K)
    show("SIM archetype whole-army (N=80 avg)", SIM)
    show("REAL-A Virulent Vectorium (Mortarion brick)", ra)
    show("REAL-B Mortarion's Hammer vehicle-swarm (Trimble, FULL)", rbf)
    show("REAL-B Mortarion's Hammer vehicle-swarm (trimmed to 2000)", rb2)

    print("\n=== DURABILITY-PER-POINT GAP: sim vs real (wounds/point) ===")
    for label, m in [("Real-A", ra), ("Real-B full", rbf), ("Real-B 2k", rb2)]:
        gap = (SIM["wpp"] - m["wpp"]) / m["wpp"] * 100
        print(f"  sim {SIM['wpp']:.4f} vs {label} {m['wpp']:.4f}  -> sim is {gap:+.1f}% wounds/pt")
    print("\n=== durable-share gap (fraction of points in durable platforms) ===")
    for label, m in [("Real-A", ra), ("Real-B full", rbf), ("Real-B 2k", rb2)]:
        gap = (SIM["durable_share"] - m["durable_share"]) * 100
        print(f"  sim {SIM['durable_share']*100:.1f}% vs {label} {m['durable_share']*100:.1f}%  -> sim {gap:+.1f} pts")
    print("\n=== vehicle/monster share gap ===")
    for label, m in [("Real-A", ra), ("Real-B full", rbf), ("Real-B 2k", rb2)]:
        gap = (SIM["vehmon_share"] - m["vehmon_share"]) * 100
        print(f"  sim {SIM['vehmon_share']*100:.1f}% vs {label} {m['vehmon_share']*100:.1f}%  -> sim {gap:+.1f} pts")


if __name__ == "__main__":
    main()
