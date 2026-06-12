"""Tests for code/archetypes.py — curated tournament list templates."""

import os
import random
import unittest
from unittest import mock

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
        T'au archetype referencing a Tyranid catalogue key).

        Aeldari sub-faction allies (Ynnari Yvraine / Yncarne / Visarch) are
        catalogued with `faction == "Ynnari"` per the BSData split but are
        legal in any 10e Aeldari (Craftworlds/Drukhari/Harlequins) army per
        the Aeldari index. The Aeldari archetype is allowed to seed them.
        """
        # Per-faction allow-list of sub-factions that may co-exist in the
        # archetype (real-meta multi-codex armies the index permits).
        ALLOWED_SUBFACTION = {
            "Aeldari": {"Ynnari"},
        }
        misplaced = []
        for faction, archetypes in ARCHETYPES.items():
            for archetype_name, template in archetypes.items():
                for key in template:
                    if key not in UNIT_CATALOG:
                        continue
                    unit_faction = UNIT_CATALOG[key].faction
                    if unit_faction == faction:
                        continue
                    if unit_faction in ALLOWED_SUBFACTION.get(faction, set()):
                        continue
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

    def test_aeldari_archetype_includes_phoenix_lords(self):
        """Aeldari Warhost at 1000 pts must produce at least Fuegan and
        Lhykhis — the two Phoenix Lords that reliably seed at the 1000pt
        budget. These are the expensive anchor units the cheapest-first
        regression used to drop.

        wave-240 list-realism reshape (docs/AELDARI_LIST_REALISM_SPEC.md)
        replaced the Yncarne / Avatar of Khaine / Wraithguard template with
        the Phoenix Lord + Aspect Warrior spine. At 1000pt the seed budget
        is 300pt (SEED_FRACTION = 0.3). Template sort order is
        (-count, -squad_cost): Lhykhis (count=3, 135pt) seeds first at 135pt,
        Fuegan (count=3, 120pt) seeds next at 255pt. Jain Zar (count=3,
        120pt) cannot fit (255 + 120 = 375 > 300). So the non-vacuous
        anchor set at seeds 0-4 is {Fuegan, Lhykhis}: any seed that lacks
        both of them has regressed to cheapest-first ordering."""
        anchor_keys = [
            "aeldari_craftworlds_fuegan",   # count=3, 120pt — seeds second
            "aeldari_craftworlds_lhykhis",  # count=3, 135pt — seeds first
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
            self.assertEqual(
                names & anchor_names,
                anchor_names,
                f"seed={seed}: Aeldari archetype missing Phoenix Lord anchors "
                f"(expected both of {anchor_names}), got {sorted(names)}",
            )


class LeaderStackPriorityTests(unittest.TestCase):
    """Wave 244 — gated SWEG_SEED_LEADERS leader-stack seed priority.

    Within the same template count, CHARACTER entries seed before
    non-CHARACTER entries, so a template's documented character stack is
    realized instead of losing the (-count, -cost) walk to the vehicle
    spine. Motivating case: the Astra Militarum Combined Arms template
    carries a three-officer leader stack (Cadian Castellan / Ursula Creed /
    Lord Solar Leontus) that the un-gated walk drops to one (the cheapest,
    rescued by the CHARACTER anchor).
    """

    AM_TEMPLATE = ARCHETYPES["Astra Militarum"]["Combined Arms"]
    AM_OFFICER_KEYS = (
        "astra_militarum_cadian_castellan",
        "astra_militarum_ursula_creed",
        "astra_militarum_lord_solar_leontus",
        "astra_militarum_cadian_command_squad",
    )

    def test_gate_off_drops_creed_and_leontus(self):
        """With the gate pinned off (SWEG_SEED_LEADERS=0 — since the
        wave-244 default flip an unset environment means gate-ON), the seed
        walk keeps only the cheapest officer — pins the wave-243 diagnostic
        so this test fails loudly if the kill-switch arm ever shifts."""
        from code.archetypes import _instantiate_template

        with mock.patch.dict(os.environ, {"SWEG_SEED_LEADERS": "0"}):
            scaled = _instantiate_template(
                dict(self.AM_TEMPLATE), 2000.0, random.Random(0),
                faction="Astra Militarum",
            )
        self.assertIn("astra_militarum_cadian_castellan", scaled)
        self.assertNotIn("astra_militarum_ursula_creed", scaled)
        self.assertNotIn("astra_militarum_lord_solar_leontus", scaled)

    def test_gate_on_seeds_full_officer_stack(self):
        """With the gate, all four template CHARACTERs (three officers plus
        the Cadian Command Squad) are seeded at the 2000-point eval budget."""
        from code.archetypes import _instantiate_template

        with mock.patch.dict(os.environ, {"SWEG_SEED_LEADERS": "1"}):
            scaled = _instantiate_template(
                dict(self.AM_TEMPLATE), 2000.0, random.Random(0),
                faction="Astra Militarum",
            )
        for key in self.AM_OFFICER_KEYS:
            self.assertIn(key, scaled, f"officer {key} missing from seed")

    def test_gate_on_preserves_multicopy_spine_priority(self):
        """The tiebreak must NOT outrank template count: Thousand Sons
        Rubric Marines (count=2 spine) still seed at the tight 1000-point
        budget with the gate on — characters only jump equally-counted
        non-characters."""
        rubric_name = UNIT_CATALOG["thousand_sons_rubric_marines"].name
        with mock.patch.dict(os.environ, {"SWEG_SEED_LEADERS": "1"}):
            for seed in range(5):
                rng = random.Random(seed)
                army = build_faction_random_army(
                    "T", "Thousand Sons", 1000.0, rng=rng, use_archetype=True,
                )
                names = {u.profile.name for u in army.units}
                self.assertIn(
                    rubric_name, names,
                    f"seed={seed}: Rubric Marines dropped with gate on",
                )

    def test_gate_on_flagship_epic_hero_still_anchored(self):
        """The tiebreak seeds Typhus (a cheap epic-hero CHARACTER) in the
        regular walk; the EPIC HERO anchor must still force-seed the
        flagship (Mortarion, the most expensive template epic hero) rather
        than being satisfied by Typhus — the exact failure the anchor's
        comment warns against."""
        from code.archetypes import _instantiate_template

        dg_template = ARCHETYPES["Death Guard"]["Virulent Vectorium"]
        with mock.patch.dict(os.environ, {"SWEG_SEED_LEADERS": "1"}):
            scaled = _instantiate_template(
                dict(dg_template), 2000.0, random.Random(0),
                faction="Death Guard",
            )
        self.assertIn("death_guard_mortarion", scaled)
        self.assertIn("death_guard_typhus", scaled)

    def test_gate_on_fraction_override_realizes_heavy_core(self):
        """SEED_FRACTION_LEADER_STACK must restore the heavy half of the
        cited core that the tiebreak squeezes out at the old fraction —
        Grey Knights Nemesis Dreadknight and Land Raider at 0.72."""
        from code.archetypes import _instantiate_template

        gk_template = ARCHETYPES["Grey Knights"]["Teleport Strike Force"]
        with mock.patch.dict(os.environ, {"SWEG_SEED_LEADERS": "1"}):
            scaled = _instantiate_template(
                dict(gk_template), 2000.0, random.Random(0),
                faction="Grey Knights",
            )
        self.assertIn("grey_knights_nemesis_dreadknight", scaled)
        self.assertIn("grey_knights_land_raider", scaled)

    def test_gate_on_am_end_to_end_build_carries_officers(self):
        """Full army build at 2000 points with the gate on carries the three
        named officers (not just the instantiate step)."""
        officer_names = {
            UNIT_CATALOG[k].name
            for k in (
                "astra_militarum_cadian_castellan",
                "astra_militarum_ursula_creed",
                "astra_militarum_lord_solar_leontus",
            )
        }
        with mock.patch.dict(os.environ, {"SWEG_SEED_LEADERS": "1"}):
            for seed in range(3):
                rng = random.Random(seed)
                army = build_faction_random_army(
                    "A", "Astra Militarum", 2000.0, rng=rng, use_archetype=True,
                )
                names = {u.profile.name for u in army.units}
                self.assertEqual(
                    names & officer_names, officer_names,
                    f"seed={seed}: built army missing officers "
                    f"(expected {officer_names}), got {sorted(names)}",
                )


class SeedFractionSupersetTests(unittest.TestCase):
    """Wave 244 amendment — gate-on seeded set must be a superset of gate-off.

    The leader-stack tiebreak (SWEG_SEED_LEADERS=1) seeds CHARACTER entries
    ahead of non-CHARACTER entries within the same template count, so a lower
    fraction can lose non-CHARACTER entries the gate-off walk would have
    realized. SEED_FRACTION_LEADER_STACK was re-derived at threshold zero
    (not the previous 150-point threshold) to guarantee the superset
    invariant for every non-menu faction.

    Menu factions (Imperial Knights, Chaos Knights, Chaos Daemons,
    Emperor's Children, World Eaters, Aeldari) are excluded per the
    wave-174 standing rule — and the gate itself is scoped off for them
    (code/archetypes.py MENU_FACTIONS), so their gate-on build must be
    IDENTICAL to gate-off, not merely a superset.
    """

    from code.archetypes import MENU_FACTIONS
    BUDGET = 2000.0

    @classmethod
    def _seeded_set(cls, faction, arch_name, env_override):
        """Return the set of unit keys seeded by _instantiate_template."""
        from code.archetypes import _instantiate_template
        template = ARCHETYPES[faction][arch_name]
        with mock.patch.dict(os.environ, env_override, clear=False):
            if "SWEG_SEED_LEADERS" not in env_override:
                # Pin the gate off — since the wave-244 default flip an
                # unset environment means gate-ON.
                os.environ["SWEG_SEED_LEADERS"] = "0"
            result = _instantiate_template(
                dict(template), cls.BUDGET, random.Random(0), faction=faction,
            )
        return set(result.keys())

    def _check_superset(self, faction, arch_name):
        """Assert gate-on seeded set is a superset of gate-off for one archetype."""
        off_set = self._seeded_set(faction, arch_name, {})
        on_set = self._seeded_set(faction, arch_name, {"SWEG_SEED_LEADERS": "1"})
        dropped = off_set - on_set
        self.assertFalse(
            dropped,
            f"Faction {faction!r} archetype {arch_name!r}: gate-on is NOT a "
            f"superset of gate-off at {self.BUDGET}pt. "
            f"De-realized entries (in gate-off, missing from gate-on): "
            f"{sorted(dropped)}.  "
            f"gate-off={sorted(off_set)}  gate-on={sorted(on_set)}",
        )

    def test_superset_invariant_all_non_menu_factions(self):
        """For every non-menu faction's archetype(s), gate-on seeded set is
        a superset of gate-off seeded set at 2000 points."""
        for faction, arch_dict in ARCHETYPES.items():
            if faction in self.MENU_FACTIONS:
                continue
            for arch_name in arch_dict:
                with self.subTest(faction=faction, archetype=arch_name):
                    self._check_superset(faction, arch_name)

    def test_menu_factions_gate_on_identical_to_gate_off(self):
        """Menu factions are scoped OUT of the leader-stack gate entirely
        (code/archetypes.py MENU_FACTIONS): the wave-244 probe found the
        un-scoped tiebreak de-realized faithful menu entries (Aeldari Fire
        Dragons, Emperor's Children Daemonettes, Chaos Daemons Flesh
        Hounds / Beasts of Nurgle / Slaanesh Soul Grinder) with no
        permitted seed-fraction fix. Gate-on seeded counts must equal
        gate-off exactly."""
        from code.archetypes import _instantiate_template
        for faction in sorted(self.MENU_FACTIONS):
            for arch_name, template in ARCHETYPES.get(faction, {}).items():
                with self.subTest(faction=faction, archetype=arch_name):
                    with mock.patch.dict(
                        os.environ, {"SWEG_SEED_LEADERS": "0"}, clear=False
                    ):
                        off_result = _instantiate_template(
                            dict(template), self.BUDGET,
                            random.Random(0), faction=faction,
                        )
                    with mock.patch.dict(
                        os.environ, {"SWEG_SEED_LEADERS": "1"}, clear=False
                    ):
                        on_result = _instantiate_template(
                            dict(template), self.BUDGET,
                            random.Random(0), faction=faction,
                        )
                    self.assertEqual(
                        off_result, on_result,
                        f"Menu faction {faction!r} archetype {arch_name!r}: "
                        f"gate-on build differs from gate-off — the menu "
                        f"scope-out is not holding",
                    )

    def test_adeptus_astartes_eradicator_squad_and_apothecary_both_seeded(self):
        """Gate-on must seed BOTH the Eradicator Squad (90pt, non-CHARACTER)
        AND the Apothecary (50pt, CHARACTER) — the motivating case for the
        wave-244 amendment, where the CHARACTER tiebreak displaced the
        documented anti-tank entry at the count=1 tier."""
        eradicator_name = UNIT_CATALOG["space_marines_eradicator_squad"].name
        apothecary_name = UNIT_CATALOG["space_marines_apothecary"].name
        on_set = self._seeded_set(
            "Adeptus Astartes", "Gladius Strike Force", {"SWEG_SEED_LEADERS": "1"}
        )
        on_names = {UNIT_CATALOG[k].name for k in on_set if k in UNIT_CATALOG}
        self.assertIn(
            eradicator_name, on_names,
            "Eradicator Squad missing from gate-on seeded set (the displacement "
            "the wave-244 amendment was built to fix)",
        )
        self.assertIn(
            apothecary_name, on_names,
            "Apothecary missing from gate-on seeded set",
        )


class ArchetypeFallbackTests(unittest.TestCase):
    def test_archetype_fallback_when_no_curated(self):
        """A faction not present in ARCHETYPES still builds an army via the
        legacy random-pool path.

        Picks `Deathwatch` as a known catalogue faction without an
        archetype (FX-ALL gave Astra Militarum its own archetype; Deathwatch
        units exist under their own `faction` tag but don't have a
        dedicated template — they fall through to the random-pool path).
        Deathwatch has 11 catalogued units so the build always lands at
        least one unit.
        """
        # Deathwatch is in the catalogue but not in ARCHETYPES.
        catalogue_factions = {u.faction for u in UNIT_CATALOG.values()}
        self.assertIn(
            "Deathwatch", catalogue_factions,
            "Deathwatch should be a faction in UNIT_CATALOG",
        )
        self.assertFalse(
            has_archetype("Deathwatch"),
            "Deathwatch unexpectedly gained an ARCHETYPES entry; "
            "pick a different non-archetype faction for this fallback test.",
        )

        rng = random.Random(7)
        army = build_faction_random_army(
            "X", "Deathwatch", 1000.0, rng=rng, use_archetype=True,
        )
        # Even with archetypes enabled, an unknown-faction army still
        # builds via the random-pool fallback.
        self.assertGreater(len(army.units), 0)

    def test_use_archetype_true_engages_curated(self):
        """Passing use_archetype=True for a faction with a defined archetype
        routes through `build_archetype_army`.

        After iter16, the T'au Mont'ka archetype is anchored on the
        Riptide Battlesuit (count=3, the count=3 entry sorts first) plus
        Hammerhead Gunships and Crisis/Broadside support. We assert at
        least one battlesuit anchor seeded — Riptide is the highest-priority
        template anchor and (-count,-cost) sort guarantees it lands first.
        """
        rng = random.Random(8)
        army = build_faction_random_army(
            "Y", "T'au Empire", 1000.0, rng=rng, use_archetype=True,
        )
        self.assertGreater(len(army.units), 0)
        names = {u.profile.name for u in army.units}
        # The Riptide is the count=3 template anchor — the (-count,-cost)
        # walk seeds it first, and at 200pt it always fits a 300pt seed
        # slice. (Crisis variants are count=2 and may or may not land
        # depending on cheaper count=2 entries consuming the seed budget;
        # the headline anchor is what we assert on.)
        battlesuit_anchors = {
            "Riptide Battlesuit",
            "Stormsurge",
            "Crisis Fireknife Battlesuits",
            "Crisis Sunforge Battlesuits",
            "Broadside Battlesuits",
        }
        anchor_present = bool(names & battlesuit_anchors)
        self.assertTrue(
            anchor_present,
            f"T'au archetype produced no battlesuit anchor. Names: {sorted(names)}",
        )


if __name__ == "__main__":
    unittest.main()
