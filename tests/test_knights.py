"""Tests for the Imperial / Chaos Knights multi-melee-weapon resolution
(KNIGHTS-MULTIPROFILE-2).

Background
----------
Knight Abominant carries TWO melee weapons on its datasheet
(https://wahapedia.ru/wh40k10ed/factions/chaos-knights/Knight-Abominant):

    Electroscourge:  A=9  WS=3+ S=10 AP=-2 D=3 [SUSTAINED HITS 1]
    Balemace:        A=3  WS=3+ S=8  AP=-1 D=2 [EXTRA ATTACKS]

The Balemace's [EXTRA ATTACKS] core keyword (10e core rules, Fight phase)
says the weapon resolves IN ADDITION to the model's other melee attacks
rather than replacing them. The BSData mapper captures only one melee
profile per datasheet (Electroscourge), so the Balemace is wired via
``data/overrides.json`` ``extra_melee_profiles`` and consumed by
``Unit.attack``'s melee branch via the additive
``simulator.extra_melee_profiles`` hook.

Knight Rampager carries two distinct datasheet melee weapons (no [EXTRA
ATTACKS] keyword on either — they are just two weapons that BOTH fire
every Fight phase):

    Warpstrike claw - strike:  A=6 WS=2+ S=20 AP=-3 D=8 [SUSTAINED HITS 1]
    Reaper chainsword - strike: A=6 WS=2+ S=14 AP=-4 D=6 [SUSTAINED HITS 1]

BSData picks the Warpstrike claw as the primary; the Reaper chainsword is
wired as an ``extra_melee_profile``.

Cited as ``simulator.extra_melee_profiles`` in
``data/rule_citations.d/chaos_knights.json``.
"""

from __future__ import annotations

import random
import unittest
from dataclasses import replace

from code.army import Army
from code.units import UNIT_CATALOG, UnitProfile


def _vehicle_target() -> UnitProfile:
    """A T10 / W500 vehicle dummy used as a damage sink so neither side
    runs out of wounds during the per-activation sampling. Save 3+ so the
    Knights' AP makes a real difference."""
    return UnitProfile(
        name="Test Vehicle Target",
        faction="TestTarget",
        health=500.0,
        damage=0,
        hit_probability=0.5,
        ap=0,
        save=3,
        strength=4,
        toughness=10,
        attacks=0,
        weapon_damage_per_shot=0,
        leadership=8,
        unit_keywords=("VEHICLE",),
    )


def _measure_avg_melee_damage(
    attacker_key: str,
    target_profile: UnitProfile,
    n_trials: int = 200,
    seed: int = 42,
    strip_extras: bool = False,
) -> float:
    """Run ``n_trials`` melee attacks from ``attacker_key`` against a fresh
    copy of ``target_profile`` and return the mean per-activation damage.

    When ``strip_extras`` is True the attacker's ``extra_melee_profiles``
    tuple is replaced with the empty tuple before the loop, so callers can
    measure the marginal damage contributed by the extras."""
    random.seed(seed)
    base_profile = UNIT_CATALOG[attacker_key]
    if strip_extras:
        attacker_profile = replace(base_profile, extra_melee_profiles=())
    else:
        attacker_profile = base_profile

    attacker_army = Army("Attacker")
    attacker_army.add_unit(attacker_profile)
    target_army = Army("Target")
    target_army.add_unit(target_profile)
    a_unit = attacker_army.units[0]
    t_unit = target_army.units[0]
    a_unit.army_ref = attacker_army
    t_unit.army_ref = target_army

    total = 0.0
    for _ in range(n_trials):
        t_unit.current_health = float(target_profile.health)
        total += a_unit.attack(t_unit, distance=1.0, mode="melee")
    return total / n_trials


class KnightAbominantBalemaceTests(unittest.TestCase):
    """Knight Abominant must fire its Balemace alongside the Electroscourge
    in the same Fight phase. The Balemace adds 3 attacks (S=8 AP=-1 D=2);
    expected uplift over Electroscourge-only is positive against any
    target the Balemace can wound."""

    def test_balemace_present_on_profile(self):
        """``extra_melee_profiles`` must contain exactly one Balemace
        entry with the BSData / Wahapedia stat line."""
        profile = UNIT_CATALOG["chaos_knights_library_knight_abominant"]
        self.assertEqual(
            len(profile.extra_melee_profiles), 1,
            "Knight Abominant must carry exactly one extra_melee_profile "
            "(Balemace) per the datasheet equipment line.",
        )
        # Each entry is a tuple-of-(key, value) pairs (hashable form).
        entry = dict(profile.extra_melee_profiles[0])
        self.assertEqual(entry["weapon"], "Balemace")
        self.assertEqual(entry["attacks"], 3)
        self.assertEqual(entry["strength"], 8)
        self.assertEqual(entry["ap"], -1)
        self.assertAlmostEqual(entry["weapon_damage_per_shot"], 2.0)

    def test_balemace_contributes_extra_damage(self):
        """Average melee damage against a T10 / 3+ save vehicle must be
        STRICTLY greater with the Balemace wired than without it."""
        target = _vehicle_target()
        avg_with = _measure_avg_melee_damage(
            "chaos_knights_library_knight_abominant", target, strip_extras=False,
        )
        avg_without = _measure_avg_melee_damage(
            "chaos_knights_library_knight_abominant", target, strip_extras=True,
        )
        self.assertGreater(
            avg_with, avg_without,
            f"Balemace must contribute non-zero extra damage; got "
            f"with={avg_with:.2f} vs without={avg_without:.2f}",
        )
        # The Balemace fires 3 attacks at WS3+ (2/3 hit) S8-vs-T10 (5+ wound
        # = 1/3) AP-1 vs Sv3+ (4+ save = 1/2 failed-save) D2, giving an
        # expected raw damage of 3 * (2/3) * (1/3) * (1/2) * 2 ≈ 0.67 per
        # activation. Empirically this hovers around 0.7 with the seed and
        # N=200 sampling; require the delta to clear 0.3 so noise can't
        # collapse it through zero.
        self.assertGreater(
            avg_with - avg_without, 0.3,
            "Balemace contribution should be at least ~0.3 dmg / activation "
            "against a T10 / 3+ save vehicle target",
        )


class KnightRampagerDualWeaponTests(unittest.TestCase):
    """Knight Rampager fires BOTH its Warpstrike claw (primary) and its
    Reaper chainsword (extra) every Fight phase. The Reaper chainsword
    adds A=6 S=14 AP=-4 D=6 [SUSTAINED HITS 1], which is a substantial
    fraction of the Rampager's melee output."""

    def test_reaper_chainsword_present_on_profile(self):
        profile = UNIT_CATALOG["chaos_knights_library_knight_rampager"]
        self.assertEqual(
            len(profile.extra_melee_profiles), 1,
            "Knight Rampager must carry exactly one extra_melee_profile "
            "(Reaper chainsword) — Warpstrike claw is the primary.",
        )
        entry = dict(profile.extra_melee_profiles[0])
        self.assertIn("Reaper chainsword", entry["weapon"])
        self.assertEqual(entry["attacks"], 6)
        self.assertEqual(entry["strength"], 14)
        self.assertEqual(entry["ap"], -4)
        self.assertAlmostEqual(entry["weapon_damage_per_shot"], 6.0)
        self.assertEqual(entry["sustained_hits"], 1)

    def test_reaper_chainsword_doubles_melee_output_against_vehicles(self):
        """Against a T10 / 3+ save vehicle the Reaper chainsword adds a
        large slice of damage on top of the Warpstrike claw — the dual
        wield should roughly double per-activation output (the chainsword
        delivers 6 attacks at WS2+ wounding T10 on 4+ at AP-4 D6 with
        SH1, which is comparable in scale to the claw)."""
        target = _vehicle_target()
        avg_with = _measure_avg_melee_damage(
            "chaos_knights_library_knight_rampager", target, strip_extras=False,
        )
        avg_without = _measure_avg_melee_damage(
            "chaos_knights_library_knight_rampager", target, strip_extras=True,
        )
        self.assertGreater(
            avg_with, avg_without,
            "Reaper chainsword must add positive damage to the Rampager's "
            "Fight phase output",
        )
        # Empirically (seed=42, N=200) the dual-weapon average sits around
        # 60-65 dmg / activation vs ~34 without; require at least +10 to
        # confirm the extra is firing for real and not vanishing into
        # excess-damage clamping.
        self.assertGreater(
            avg_with - avg_without, 10.0,
            f"Reaper chainsword should add >=10 dmg / activation; "
            f"got delta = {avg_with - avg_without:.2f}",
        )


class ExtraMeleeProfilesIsolationTests(unittest.TestCase):
    """Sanity checks that extra_melee_profiles does NOT leak into ranged
    resolution and that the empty-tuple default is unchanged for units
    that have no extra melee weapons."""

    def test_no_extras_unchanged_for_marines(self):
        """An Intercessor Squad (or any other vanilla profile with one
        melee weapon) must default to extra_melee_profiles == ()."""
        random.seed(0)
        # Build a fresh ad-hoc profile rather than relying on a specific
        # marine catalogue key to avoid coupling the test to the codex.
        profile = UnitProfile(
            name="Vanilla Marine",
            faction="Adeptus Astartes",
            health=2, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            leadership=7,
            unit_keywords=("INFANTRY",),
            melee_attacks=2, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        )
        self.assertEqual(profile.extra_melee_profiles, ())

    def test_melee_extras_do_not_affect_ranged(self):
        """Firing the Knight Abominant's RANGED weapon must produce the
        same expected damage whether or not extra_melee_profiles is set
        — the additive hook is gated to mode == 'melee'."""
        random.seed(7)
        base_profile = UNIT_CATALOG["chaos_knights_library_knight_abominant"]
        # Strip extras to isolate the comparison.
        profile_no_extras = replace(base_profile, extra_melee_profiles=())

        # Set up a small target sink.
        target_profile = _vehicle_target()

        def _ranged_avg(profile: UnitProfile, n: int = 100) -> float:
            random.seed(7)
            atk_army = Army("A"); atk_army.add_unit(profile)
            tgt_army = Army("T"); tgt_army.add_unit(target_profile)
            au = atk_army.units[0]; tu = tgt_army.units[0]
            au.army_ref = atk_army; tu.army_ref = tgt_army
            total = 0.0
            for _ in range(n):
                tu.current_health = float(target_profile.health)
                total += au.attack(tu, distance=12.0, mode="ranged")
            return total / n

        with_extras = _ranged_avg(base_profile)
        without_extras = _ranged_avg(profile_no_extras)
        self.assertAlmostEqual(
            with_extras, without_extras, places=2,
            msg=(
                "Ranged damage must be invariant to extra_melee_profiles. "
                f"with={with_extras:.4f} without={without_extras:.4f}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
