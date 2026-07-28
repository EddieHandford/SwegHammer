"""Resolve the Cam Hawkins Aspect Host roster to catalogue keys.

Source: Cam Hawkins, Aeldari (Aspect Host), 1st place, OWN's Breaking Point
Grand Tournament, Game HQ, Oklahoma City, 33 players, 5 rounds, 9 May 2026.
Reported by Tabletop Battles, "Competitive Innovations in 10th: Wind Down".
TENTH edition, six weeks before the edition change on 20 June 2026.

The roster, verbatim from the expanded army list on that page:

    Asurmen 135 (Warlord)          Fire Prism 150
    Avatar of Khaine 280           Fire Prism 150
    Lhykhis 135                    Rangers 55 (5 models)
    Wave Serpent 125               War Walkers 85
    Dire Avengers 150 (10 models)  Warlock Skyrunners 45
    Fire Prism 150                 Warlock Skyrunners 45
    Warp Spiders 105 (5 models)    Wraithlord 130 x3
                                   = 2000 points

This prints which of those entries the catalogue can express, with its own
points and minimum squad size, so the template can be written against real keys
rather than guessed ones and the cost checked in the codebase's own currency.

Run: PYTHONHASHSEED=0 python -m scripts._aeldari_key_lookup
"""
from __future__ import annotations

from code.units import UNIT_CATALOG

# (search fragment, real roster count, real points each)
WANT = [
    ("asurmen", 1, 135),
    ("avatar_of_khaine", 1, 280),
    ("lhykhis", 1, 135),
    ("wave_serpent", 1, 125),
    ("dire_avenger", 1, 150),
    ("fire_prism", 3, 150),
    ("ranger", 1, 55),
    ("war_walker", 1, 85),
    ("warlock_skyrunner", 2, 45),
    ("warp_spider", 1, 105),
    ("wraithlord", 3, 130),
]


def main() -> None:
    keys = [k for k in UNIT_CATALOG if k.startswith("aeldari")]
    total = 0.0
    missing = []
    print("=== Cam Hawkins Aspect Host roster against the catalogue ===")
    print(f"{'roster entry':<22}{'count':>6}{'real pts':>10}  catalogue key "
          f"(sim points x min models)")
    for frag, count, real_pts in WANT:
        hits = [k for k in keys if frag in k]
        if not hits:
            print(f"{frag:<22}{count:>6}{real_pts:>10}  *** NOT IN CATALOGUE ***")
            missing.append(frag)
            continue
        # Prefer the shortest key: longer ones are usually variants.
        best = sorted(hits, key=len)[0]
        p = UNIT_CATALOG[best]
        mm = max(1, getattr(p, "min_models", 1) or 1)
        squad = p.points_cost * mm
        total += squad * count
        extra = "" if len(hits) == 1 else f"   [{len(hits)} candidates]"
        print(f"{frag:<22}{count:>6}{real_pts:>10}  {best} "
              f"({p.points_cost:.0f} x {mm} = {squad:.0f}){extra}")
        if len(hits) > 1:
            for h in sorted(hits, key=len)[1:]:
                print(f"{'':<38}    also: {h}")

    print()
    print(f"  real list total:            2000 points")
    print(f"  same list in sim currency:  {total:.0f} points "
          f"({total / 2000:.2f} of budget)")
    print(f"  seed slice available:       600 points "
          f"(SEED_FRACTION 0.3) -> overrun {total / 600:.2f}x")
    if missing:
        print()
        print(f"  MISSING FROM CATALOGUE: {', '.join(missing)}")
        print("  Per CLAUDE.md rule 9, a missing unit is added to")
        print("  data/overrides.json as a fully-specified entry, never by")
        print("  editing code/units.py.")


if __name__ == "__main__":
    main()
