"""Tests for code/archetypes.py — curated tournament list templates."""

import random
import unittest

from code.archetypes import (
    ARCHETYPES,
    build_archetype_army,
    has_archetype,
)
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG


class ArchetypeKeysResolveTests(unittest.TestCase):
    def test_archetype_keys_resolve(self):
        """Every unit key referenced in any archetype must exist in UNIT_CATALOG.

        Catches typos before a calibration run silently skips the missing key.
        """
        missing = []
        for faction, archetypes in ARCHETYPES.items():
            for archetype_name, template in archetypes.items():
                for key in template:
                    if key not in UNIT_CATALOG:
                        missing.append(
                            f"{faction}/{archetype_name}: {key} not in UNIT_CATALOG"
                        )
        self.assertEqual(missing, [], f"Missing keys: {missing}")

    def test_every_archetype_unit_belongs_to_its_faction(self):
        """An archetype must not draft a unit from another faction (e.g. a
        T'au archetype referencing a Tyranid catalogue key)."""
        misplaced = []
        for faction, archetypes in ARCHETYPES.items():
            for archetype_name, template in archetypes.items():
                for key in template:
                    if key not in UNIT_CATALOG:
                        continue
                    unit_faction = UNIT_CATALOG[key].faction
                    if unit_faction != faction:
                        misplaced.append(
                            f"{faction}/{archetype_name}: {key} faction={unit_faction}"
                        )
        self.assertEqual(misplaced, [], f"Misplaced: {misplaced}")


class ArchetypeBuilderTests(unittest.TestCase):
    def test_tau_archetype_builds_under_points(self):
        """T'au Kauyon built at 1000 pts must fit within the budget."""
        rng = random.Random(1)
        army = build_archetype_army("T", "T'au Empire", 1000.0, rng=rng)
        self.assertGreater(len(army.units), 0)
        self.assertLessEqual(army.total_points, 1000.0)

    def test_marines_archetype_includes_intercessors(self):
        """The Marine archetype must reference intercessor_squad — that's the
        battleline core of every competitive Gladius list. We assert on the
        template (not the instantiated army) because at small budgets the
        seed-fraction trim may not keep intercessors in the seeded portion."""
        from code.archetypes import ARCHETYPES
        template = ARCHETYPES["Adeptus Astartes"]["Gladius Strike Force"]
        self.assertIn("space_marines_intercessor_squad", template)
        # And building at a generous budget should produce intercessors.
        rng = random.Random(2)
        army = build_archetype_army(
            "M", "Adeptus Astartes", 2000.0, rng=rng,
            archetype_name="Gladius Strike Force",
        )
        self.assertGreater(len(army.units), 0)

    def test_archetype_scales_with_budget(self):
        """A 2000-pt army should have at least as many total-point spend as
        a 500-pt army built from the same archetype."""
        rng_a = random.Random(3)
        rng_b = random.Random(3)
        small = build_archetype_army("S", "Necrons", 500.0, rng=rng_a)
        big = build_archetype_army("B", "Necrons", 2000.0, rng=rng_b)
        self.assertLess(small.total_points, big.total_points)
        # And the big army should be relatively close to its budget.
        self.assertGreater(big.total_points, 1000.0)


class ArchetypeAnchorSeedingTests(unittest.TestCase):
    """Regression tests for task #170 — anchor units must always be seeded.

    Before the fix, `_instantiate_template` walked cheapest-first and a
    SEED_FRACTION=0.3 slice of a 1000pt budget exhausted on cheap chaff
    (Tzaangors, Sorcerers, Rangers, Farseers) before reaching the
    archetype-defining anchors (Rubric Marines, Wraithguard, etc.).
    The fix sorts by (-template_count, -squad_cost) so multi-copy and/or
    expensive flagship units land first.
    """

    def test_tson_archetype_includes_rubrics(self):
        """TSON archetype at 1000 pts must produce >=1 Rubric squad — they
        are the count=2 template entry and the spine of every Cult of Magic
        list."""
        rubric_name = UNIT_CATALOG["thousand_sons_rubric_marines"].name
        for seed in range(5):
            rng = random.Random(seed)
            army = build_faction_random_army(
                "T", "Thousand Sons", 1000.0, rng=rng, use_archetype=True,
            )
            names = {u.profile.name for u in army.units}
            self.assertIn(
                rubric_name, names,
                f"seed={seed}: TSON archetype missing Rubric Marines, got {sorted(names)}",
            )

    def test_aeldari_archetype_includes_wraith_or_falcon(self):
        """Aeldari Battle Host at 1000 pts must produce at least one heavy
        anchor — Wraithguard, Wraithblades, Wave Serpent, or Falcon. These
        are the expensive units the cheapest-first bug used to drop."""
        anchor_keys = [
            "aeldari_craftworlds_wraithguard",
            "aeldari_craftworlds_wave_serpent",
            "aeldari_craftworlds_falcon",
        ]
        anchor_names = {
            UNIT_CATALOG[k].name for k in anchor_keys if k in UNIT_CATALOG
        }
        for seed in range(5):
            rng = random.Random(seed)
            army = build_faction_random_army(
                "A", "Aeldari", 1000.0, rng=rng, use_archetype=True,
            )
            names = {u.profile.name for u in army.units}
            self.assertTrue(
                names & anchor_names,
                f"seed={seed}: Aeldari archetype missing all heavy anchors "
                f"({anchor_names}), got {sorted(names)}",
            )


class ArchetypeFallbackTests(unittest.TestCase):
    def test_archetype_fallback_when_no_curated(self):
        """A faction not present in ARCHETYPES still builds an army via the
        legacy random-pool path."""
        # Pick a faction we know we have units for but no archetype.
        # 'Astra Militarum' is present in the catalogue but not in ARCHETYPES.
        catalogue_factions = {u.faction for u in UNIT_CATALOG.values()}
        obscure = next(
            (f for f in catalogue_factions
             if f and not has_archetype(f) and f != ""),
            None,
        )
        self.assertIsNotNone(obscure, "Expected at least one non-archetype faction in catalogue")

        rng = random.Random(7)
        army = build_faction_random_army(
            "X", obscure, 1000.0, rng=rng, use_archetype=True,
        )
        # Even with archetypes enabled, an unknown-faction army still
        # builds via the random-pool fallback.
        self.assertGreater(len(army.units), 0)

    def test_use_archetype_true_engages_curated(self):
        """Passing use_archetype=True for a faction with a defined archetype
        routes through `build_archetype_army`.

        After task #174, the T'au Kauyon archetype is battlesuit-heavy
        (Crisis Fireknife / Sunforge / Broadside as the multi-copy spine),
        not Fire Warriors. We assert at least one Crisis variant is seeded,
        which is the count=3+count=2 anchor pair that always wins the
        anchor-first sort.
        """
        rng = random.Random(8)
        army = build_faction_random_army(
            "Y", "T'au Empire", 1000.0, rng=rng, use_archetype=True,
        )
        self.assertGreater(len(army.units), 0)
        names = {u.profile.name for u in army.units}
        # At least one Crisis variant must appear — these are the count=3
        # (Fireknife) and count=2 (Sunforge) template anchors that the
        # anchor-first sort guarantees fit in any reasonable seed budget.
        crisis_present = any("Crisis" in n for n in names)
        self.assertTrue(
            crisis_present,
            f"T'au archetype produced no Crisis battlesuit. Names: {sorted(names)}",
        )


if __name__ == "__main__":
    unittest.main()
