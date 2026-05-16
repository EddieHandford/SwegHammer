"""Tests for the 10e Enhancement (Warlord upgrade) system."""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.army_builder import _assign_enhancement_to_warlord, build_faction_random_army
from code.detachments import (
    DETACHMENTS, GLADIUS_TASK_FORCE, default_detachment_for_faction,
)
from code.enhancements import (
    CHAMPION_OF_HUMANITY,
    ENHANCEMENTS,
    ENHANCEMENTS_BY_DETACHMENT,
    Enhancement,
    enhancements_for_detachment,
    pick_enhancement,
)
from code.leaders import effective_buffs
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Synthetic profiles — keep math obvious, isolated from BSData drift
# ---------------------------------------------------------------------------

def _captain_profile() -> UnitProfile:
    return UnitProfile(
        name="Captain",
        health=4, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _grunt_profile() -> UnitProfile:
    return UnitProfile(
        name="Tactical Marine",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
    )


def _target_character_profile() -> UnitProfile:
    return UnitProfile(
        name="Enemy Champion",
        health=6, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------

class EnhancementRegistryTests(unittest.TestCase):

    def test_three_enhancements_registered(self):
        # Three enhancements, one per surviving implemented detachment in
        # the starter set. Two enhancements (Arcane Vortex, Living Plague)
        # were removed per the 2026-05-15 fabrication audit (commit fa9a957)
        # because they pointed at fabricated detachment keys (cult_of_magic,
        # plague_company) that have been deleted.
        self.assertEqual(len(ENHANCEMENTS), 3)

    def test_each_enhancement_has_detachment_and_cost(self):
        for name, enh in ENHANCEMENTS.items():
            self.assertIsInstance(enh, Enhancement)
            self.assertIn(enh.detachment, DETACHMENTS, f"{name}: detachment key {enh.detachment!r} not in DETACHMENTS")
            self.assertGreater(enh.points_cost, 0)
            self.assertEqual(name, enh.name)

    def test_enhancements_grouped_by_detachment(self):
        # Each surviving starter Detachment has exactly one Enhancement
        # wired. cult_of_magic and plague_company were deleted per the
        # 2026-05-15 fabrication audit (commit fa9a957), so their
        # enhancements (Arcane Vortex, Living Plague) are gone too.
        for det_key in ("gladius_task_force", "awakened_dynasty", "montka"):
            with self.subTest(det=det_key):
                wired = enhancements_for_detachment(det_key)
                self.assertEqual(len(wired), 1)

    def test_detachment_carries_enhancement_tuple(self):
        # The Detachment instance itself exposes the enhancement tuple
        # (post the dataclass.replace patch at module import time).
        self.assertEqual(len(GLADIUS_TASK_FORCE.enhancements), 1)
        self.assertEqual(GLADIUS_TASK_FORCE.enhancements[0].name, "Champion of Humanity")


# ---------------------------------------------------------------------------
# Picker — deterministic given a seeded RNG
# ---------------------------------------------------------------------------

class EnhancementPickerTests(unittest.TestCase):

    def test_pick_returns_one_for_known_detachment(self):
        rng = random.Random(42)
        enh = pick_enhancement("gladius_task_force", rng=rng)
        self.assertIsNotNone(enh)
        self.assertEqual(enh.detachment, "gladius_task_force")

    def test_pick_returns_none_for_unwired_detachment(self):
        # `invasion_fleet` has no Enhancement wired in this starter set.
        rng = random.Random(7)
        self.assertIsNone(pick_enhancement("invasion_fleet", rng=rng))

    def test_pick_seeded_deterministic(self):
        # cult_of_magic was the original exemplar; that detachment was
        # deleted per fa9a957. Use montka — also has exactly one wired
        # enhancement (Puretide Engram Neurochip).
        a = pick_enhancement("montka", rng=random.Random(0))
        b = pick_enhancement("montka", rng=random.Random(0))
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# Effective-buffs composition — enhancement merges into the buff dict
# ---------------------------------------------------------------------------

class EffectiveBuffsCompositionTests(unittest.TestCase):

    def _make_marine_army(self, with_enhancement: bool) -> Army:
        army = Army("Marines")
        # 1 captain + 4 marines, deployed close together so the aura covers.
        army.add_unit(_captain_profile())
        for _ in range(4):
            army.add_unit(_grunt_profile())
        for u in army.units:
            u.position = (0.0, 0.0)
        army.detachment = GLADIUS_TASK_FORCE
        if with_enhancement:
            army.units[0].enhancement = CHAMPION_OF_HUMANITY
        return army

    def test_no_enhancement_no_plus_one_to_wound(self):
        army = self._make_marine_army(with_enhancement=False)
        # Pick a grunt (not the captain) to read attacker buffs on.
        grunt = army.units[1]
        buffs = effective_buffs(grunt)
        # Gladius no longer carries reroll_wound_ones (that was the lossy
        # Combat Doctrines approximation, replaced in #115/#116 by the
        # round-rotating +1-to-wound simulator gate). Both flags off here.
        self.assertFalse(buffs["plus_one_to_wound"])
        self.assertFalse(buffs["reroll_wound_ones"])

    def test_enhancement_grants_plus_one_to_wound(self):
        army = self._make_marine_army(with_enhancement=True)
        grunt = army.units[1]
        buffs = effective_buffs(grunt)
        self.assertTrue(buffs["plus_one_to_wound"])
        # Gladius itself no longer touches reroll_wound_ones; only the
        # enhancement's plus_one_to_wound shows up on the grunt.
        self.assertFalse(buffs["reroll_wound_ones"])


# ---------------------------------------------------------------------------
# Effect fires: more wounds inflicted with Champion of Humanity than without
# ---------------------------------------------------------------------------

class EnhancementEffectFiresTests(unittest.TestCase):
    """Synthetic Marines-attacking-a-CHARACTER scenario. With Champion of
    Humanity attached to the captain (and the captain in aura range), the
    +1-to-wound aura must produce strictly more total damage across a
    seeded N-resolution sample than the no-enhancement baseline."""

    def _run_sim(self, with_enhancement: bool, seed: int, trials: int = 200) -> float:
        random.seed(seed)
        # Attacker side: 1 captain + 1 marine, captain carries enhancement.
        att = Army("Attacker")
        att.add_unit(_captain_profile())
        att.add_unit(_grunt_profile())
        att.detachment = GLADIUS_TASK_FORCE
        for u in att.units:
            u.position = (0.0, 0.0)
        if with_enhancement:
            att.units[0].enhancement = CHAMPION_OF_HUMANITY

        # Defender: enemy CHARACTER target.
        defn = Army("Defender")
        defn.add_unit(_target_character_profile())
        defn.units[0].position = (12.0, 0.0)

        total_damage = 0.0
        for _ in range(trials):
            # Reset target HP each trial so survival doesn't truncate the run.
            defn.units[0].current_health = defn.units[0].profile.health
            # Grunt shoots; if it doesn't kill, we still count total damage.
            d = att.units[1].attack(defn.units[0], distance=12.0, mode="ranged")
            total_damage += d
        return total_damage

    def test_enhancement_increases_wound_yield(self):
        baseline = self._run_sim(with_enhancement=False, seed=99)
        upgraded = self._run_sim(with_enhancement=True, seed=99)
        # +1 to wound on a S4 v T4 baseline shifts wound target from 4+ to 3+,
        # which moves wound prob from 0.5 to 2/3 — a ~33% uplift in wounds
        # per attack. With re-roll wound 1s already active, marginal uplift
        # is smaller but still strictly positive; we just check direction.
        self.assertGreater(
            upgraded, baseline,
            f"Champion of Humanity should increase wound yield: baseline={baseline}, upgraded={upgraded}",
        )


# ---------------------------------------------------------------------------
# Builder-level invariants
# ---------------------------------------------------------------------------

class WarlordAssignmentTests(unittest.TestCase):
    """Smoke test for `_assign_enhancement_to_warlord` — runs against the
    real BSData-derived unit catalogue, so the Marines roster must contain
    at least one CHARACTER for the assignment to land."""

    def test_marines_build_assigns_enhancement(self):
        # Seed = 0 so the build is reproducible.
        army = build_faction_random_army(
            "Test Marines", "Adeptus Astartes", points_budget=1000.0,
            rng=random.Random(0),
        )
        # Detachment resolved
        det = army.resolve_detachment()
        self.assertIsNotNone(det)
        # At least one CHARACTER picked
        chars = [u for u in army.units if "CHARACTER" in (u.profile.unit_keywords or ())]
        if not chars:
            self.skipTest("Marines build didn't produce a CHARACTER at seed=0")
        # Second-detachment picker (#126) may resolve Ironstorm Spearhead for
        # vehicle-heavy Marines rosters, which carries no wired enhancements.
        # Skip cleanly in that case — the wiring is verified independently
        # via test_only_one_enhancement_even_with_multiple_characters below.
        if not getattr(det, "enhancements", ()):
            self.skipTest(
                f"Detachment {det.name!r} has no wired enhancements at seed=0"
            )
        # Exactly one CHARACTER must carry an enhancement; the rest carry None.
        enh_carriers = [u for u in army.units if u.enhancement is not None]
        self.assertEqual(len(enh_carriers), 1,
                         f"expected exactly 1 enhancement, got {len(enh_carriers)}")
        # The bearer is a CHARACTER.
        self.assertIn("CHARACTER", enh_carriers[0].profile.unit_keywords or ())

    def test_only_one_enhancement_even_with_multiple_characters(self):
        # Construct manually: 2 captains + 4 marines.
        army = Army("Marines")
        army.add_unit(_captain_profile())
        army.add_unit(_captain_profile())
        for _ in range(4):
            army.add_unit(_grunt_profile())
        army.detachment = GLADIUS_TASK_FORCE
        _assign_enhancement_to_warlord(army, random.Random(0))
        carriers = [u for u in army.units if u.enhancement is not None]
        self.assertEqual(len(carriers), 1)

    def test_no_enhancement_when_detachment_has_none(self):
        # invasion_fleet (Tyranids) carries no wired enhancement.
        army = Army("Test")
        army.add_unit(_captain_profile())  # synthetic CHARACTER
        army.detachment = DETACHMENTS["invasion_fleet"]
        _assign_enhancement_to_warlord(army, random.Random(0))
        carriers = [u for u in army.units if u.enhancement is not None]
        self.assertEqual(len(carriers), 0)

    def test_no_enhancement_when_no_characters(self):
        army = Army("Marines")
        for _ in range(4):
            army.add_unit(_grunt_profile())   # no CHARACTERS in this army
        army.detachment = GLADIUS_TASK_FORCE
        _assign_enhancement_to_warlord(army, random.Random(0))
        carriers = [u for u in army.units if u.enhancement is not None]
        self.assertEqual(len(carriers), 0)


class EnhancementCostAccountingTests(unittest.TestCase):
    """Enhancement costs are real points: the army's effective points spend
    is `total_unit_points + bearer.enhancement.points_cost`. We don't claw
    back from the unit budget at build time (that would shrink the army
    visibly) — instead the cost is exposed as a readable property on the
    bearer for downstream accounting."""

    def test_enhancement_cost_readable_on_bearer(self):
        army = Army("Marines")
        army.add_unit(_captain_profile())
        army.add_unit(_grunt_profile())
        army.detachment = GLADIUS_TASK_FORCE
        _assign_enhancement_to_warlord(army, random.Random(0))
        bearer = next(u for u in army.units if u.enhancement is not None)
        # The enhancement carries a cost that contributes to army value.
        self.assertGreater(bearer.enhancement.points_cost, 0)
        # Champion of Humanity is 20 pts per the starter registry.
        self.assertEqual(bearer.enhancement.points_cost, 20)


if __name__ == "__main__":
    unittest.main()
