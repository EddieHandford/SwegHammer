"""Tests for the detachment registry — Phase: faction-coverage expansion."""

from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from code.army import Army
from code.detachments import (
    DEFAULT_BY_FACTION, DETACHMENTS, Detachment,
    FACTION_DETACHMENTS,
    _army_composition_signature,
    _score_detachment_for_army,
    default_detachment_for_faction,
    pick_detachment_for_army,
)
from code.units import UnitProfile


# Each tuple: (registry-key, faction-string the default lookup should resolve,
# expected boolean / int field that should be set to a non-default value).
_NEW_DETACHMENTS = (
    # (key, faction, attribute, expected value)
    ("hallowed_martyrs",       "Adepta Sororitas",       "plus_one_to_wound", True),
    ("shield_host",            "Adeptus Custodes",       "plus_one_save",     True),
    ("skitarii_hunter_cohort", "Adeptus Mechanicus",     "reroll_hit_ones",   True),
    ("inquisition_task_force", "Agents of the Imperium", "reroll_hit_ones",   True),
    ("combined_regiment",      "Astra Militarum",        "plus_one_to_hit",   True),
    ("teleport_strike_force",  "Grey Knights",           "reroll_wound_ones", True),
    ("battle_host",            "Aeldari",                "reroll_hit_ones",   True),
    ("skysplinter_assault",    "Drukhari",               "reroll_wound_ones", True),
    ("montka",                 "T'au Empire",            "plus_one_to_hit",   True),
    ("pactbound_zealots",      "Chaos Space Marines",    "reroll_wound_ones", True),
    # plague_company + cult_of_magic + oathband carry no passive flag
    # right now. plague_company / cult_of_magic earlier values were
    # uncited (CLAUDE.md §10); oathband's "army-wide re-roll hit 1s"
    # approximated the Eye of the Ancestors rule that now lives in
    # simulator.judgement_tokens, so the detachment-level reroll was
    # removed to avoid double-stacking with the Judgement Tokens buff.
    # All three will gain stratagem-level passives when #104 lands.
    # Registry presence is still checked separately below.
    ("berzerker_warband",      "World Eaters",           "plus_one_to_hit",   True),
    ("daemonic_incursion",     "Chaos Daemons",          "plus_one_to_hit",   True),
    ("final_day",              "Genestealer Cults",      "reroll_hit_ones",   True),
)


class DetachmentRegistryTests(unittest.TestCase):
    """Each new detachment must appear in DETACHMENTS and carry the right flag."""

    def test_each_new_detachment_present(self):
        for key, _faction, attr, expected in _NEW_DETACHMENTS:
            self.assertIn(key, DETACHMENTS, f"{key} missing from DETACHMENTS")
            det = DETACHMENTS[key]
            self.assertEqual(
                getattr(det, attr), expected,
                f"{key}.{attr} expected {expected!r}, got {getattr(det, attr)!r}",
            )

    def test_each_new_faction_resolves_via_default(self):
        for key, faction, _attr, _expected in _NEW_DETACHMENTS:
            det = default_detachment_for_faction(faction)
            self.assertIsNotNone(det, f"{faction!r} did not resolve a default detachment")
            self.assertEqual(
                DEFAULT_BY_FACTION[faction], key,
                f"{faction!r} should map to {key!r}, got {DEFAULT_BY_FACTION[faction]!r}",
            )

    def test_default_unknown_returns_none(self):
        self.assertIsNone(default_detachment_for_faction("Made-Up Faction"))

    def test_registry_grew(self):
        # Original: 5 detachments. After expansion: should be at least 5+16=21.
        self.assertGreaterEqual(len(DETACHMENTS), 21)


class ArmyResolveDetachmentTests(unittest.TestCase):
    """Newly-added factions must auto-resolve via Army.resolve_detachment()."""

    @staticmethod
    def _profile(faction: str) -> UnitProfile:
        return UnitProfile(
            name="Trooper", health=1, damage=1, hit_probability=0.5,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            faction=faction,
        )

    def test_tau_army_resolves(self):
        army = Army("Tau")
        army.add_unit(self._profile("T'au Empire"))
        det = army.resolve_detachment()
        self.assertIsNotNone(det)
        self.assertEqual(det.name, "Mont'ka")
        self.assertTrue(det.plus_one_to_hit)

    def test_death_guard_army_resolves(self):
        army = Army("DG")
        army.add_unit(self._profile("Death Guard"))
        det = army.resolve_detachment()
        self.assertIsNotNone(det)
        # Plague Company's fnp=5 was an uncited approximation, removed
        # per CLAUDE.md §10. Re-introduce once real DG stratagem effects
        # land in #103. For now, just verify the detachment resolves.
        self.assertEqual(det.name, "Plague Company")

    def test_custodes_army_resolves(self):
        army = Army("Custodes")
        army.add_unit(self._profile("Adeptus Custodes"))
        det = army.resolve_detachment()
        self.assertIsNotNone(det)
        self.assertTrue(det.plus_one_save)

    def test_explicit_detachment_overrides_default(self):
        explicit = Detachment(name="Override", faction="X", plus_one_to_wound=True)
        army = Army("Mixed", detachment=explicit)
        army.add_unit(self._profile("T'au Empire"))
        det = army.resolve_detachment()
        self.assertIs(det, explicit)


class CompositionSignatureTests(unittest.TestCase):
    """Composition signature reads unit keywords + points spend."""

    @staticmethod
    def _make(name: str, keywords, points: float = 100.0) -> UnitProfile:
        return UnitProfile(
            name=name, health=1, damage=1, hit_probability=0.5,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            unit_keywords=tuple(keywords),
            points_override=points,
        )

    def test_composition_signature(self):
        # All-vehicle army: vehicle_fraction == 1.0, infantry/monster == 0.
        vehicle = self._make("Tank", ["VEHICLE"], points=200.0)
        sig = _army_composition_signature([vehicle, vehicle, vehicle])
        self.assertAlmostEqual(sig["vehicle_fraction"], 1.0)
        self.assertAlmostEqual(sig["infantry_fraction"], 0.0)
        self.assertAlmostEqual(sig["monster_fraction"], 0.0)
        self.assertAlmostEqual(sig["character_fraction"], 0.0)

    def test_mixed_signature_sums_correctly(self):
        # 200pt vehicle + 100pt infantry + 100pt character (infantry too) →
        # vehicle 0.5, infantry 0.5 (both non-vehicle infantry), char 0.25.
        vehicle = self._make("Tank", ["VEHICLE"], points=200.0)
        trooper = self._make("Trooper", ["INFANTRY"], points=100.0)
        captain = self._make("Captain", ["INFANTRY", "CHARACTER"], points=100.0)
        sig = _army_composition_signature([vehicle, trooper, captain])
        self.assertAlmostEqual(sig["vehicle_fraction"], 0.5)
        self.assertAlmostEqual(sig["infantry_fraction"], 0.5)
        self.assertAlmostEqual(sig["character_fraction"], 0.25)

    def test_empty_army_signature(self):
        sig = _army_composition_signature([])
        for k, v in sig.items():
            self.assertEqual(v, 0.0, f"{k} should be 0 for empty army")


class PickerSingleDetachmentTests(unittest.TestCase):
    """Factions with one registered detachment always resolve to it."""

    def test_picker_returns_unique_when_only_one(self):
        # Tyranids still has only invasion_fleet in FACTION_DETACHMENTS
        # (Necrons gained canoptek_court in #126, so use Tyranids as the
        # 1-detachment canary).
        self.assertEqual(FACTION_DETACHMENTS["Tyranids"], ("invasion_fleet",))
        rng = random.Random(42)
        det = pick_detachment_for_army("Tyranids", [], rng)
        self.assertIsNotNone(det)
        self.assertEqual(det.name, "Invasion Fleet")

    def test_picker_unmapped_faction_falls_back(self):
        det = pick_detachment_for_army("Made-Up Faction", [], random.Random(0))
        self.assertIsNone(det)


class PickerCompositionPreferenceTests(unittest.TestCase):
    """A two-detachment faction should prefer the comp-matching choice."""

    @staticmethod
    def _make(name: str, keywords, points: float = 200.0) -> UnitProfile:
        return UnitProfile(
            name=name, health=1, damage=1, hit_probability=0.5,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            unit_keywords=tuple(keywords),
            points_override=points,
        )

    def test_picker_prefers_matching_composition(self):
        # Synthetic 2-detachment "Mockstodes" faction: a vehicle-tagged
        # detachment and an infantry-tagged one. Patch FACTION_DETACHMENTS
        # + DETACHMENTS so the picker sees them.
        vehicle_det = Detachment(
            name="Tank Brigade", faction="Mockstodes",
            preferred_composition="vehicle",
        )
        infantry_det = Detachment(
            name="Boot Company", faction="Mockstodes",
            preferred_composition="infantry",
        )

        # High-vehicle army (one infantry unit added so the dominant check
        # still resolves cleanly to "vehicle").
        vehicle_unit = self._make("Battletank", ["VEHICLE"], points=400.0)
        infantry_unit = self._make("Grunt", ["INFANTRY"], points=50.0)
        army_units = [vehicle_unit, vehicle_unit, infantry_unit]

        patched_factions = dict(FACTION_DETACHMENTS)
        patched_factions["Mockstodes"] = ("mock_tanks", "mock_boots")
        patched_dets = dict(DETACHMENTS)
        patched_dets["mock_tanks"] = vehicle_det
        patched_dets["mock_boots"] = infantry_det

        with patch.dict(FACTION_DETACHMENTS, patched_factions, clear=True), \
             patch.dict(DETACHMENTS, patched_dets, clear=True):
            picks = []
            for seed in range(100):
                rng = random.Random(seed)
                det = pick_detachment_for_army("Mockstodes", army_units, rng)
                picks.append(det.name)

        vehicle_pick_count = picks.count("Tank Brigade")
        self.assertGreater(
            vehicle_pick_count, 50,
            f"High-vehicle army picked Tank Brigade {vehicle_pick_count}/100 "
            "times — expected >50.",
        )


class ScoringTests(unittest.TestCase):
    """Direct exercise of _score_detachment_for_army."""

    def test_matching_pref_scores_higher(self):
        veh_det = Detachment(name="V", faction="X", preferred_composition="vehicle")
        inf_det = Detachment(name="I", faction="X", preferred_composition="infantry")
        vehicle_comp = {
            "vehicle_fraction": 1.0,
            "infantry_fraction": 0.0,
            "monster_fraction": 0.0,
            "character_fraction": 0.0,
        }
        self.assertGreater(
            _score_detachment_for_army(veh_det, vehicle_comp),
            _score_detachment_for_army(inf_det, vehicle_comp),
        )


class SecondDetachmentTests(unittest.TestCase):
    """#126: each second detachment fires its buff under the trigger condition."""

    @staticmethod
    def _profile(name: str, faction: str, keywords=(), move: float = 6.0) -> UnitProfile:
        return UnitProfile(
            name=name, health=1, damage=1, hit_probability=0.5,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            unit_keywords=tuple(keywords),
            faction=faction,
            move=move,
        )

    def test_ironstorm_buffs_vehicle_attacker(self):
        """Ironstorm Spearhead: VEHICLE attacker gets reroll_hit_ones."""
        from code.detachments import IRONSTORM_SPEARHEAD
        from code.leaders import effective_buffs
        army = Army("Marines", detachment=IRONSTORM_SPEARHEAD)
        army.add_unit(self._profile(
            "Predator", "Adeptus Astartes", keywords=("VEHICLE",),
        ))
        army.add_unit(self._profile(
            "Intercessor", "Adeptus Astartes", keywords=("INFANTRY",),
        ))
        # Position both at origin so leader-aura distance code is unambiguous.
        for u in army.units:
            u.position = (0.0, 0.0)
        vehicle = army.units[0]
        infantry = army.units[1]
        veh_buffs = effective_buffs(vehicle)
        inf_buffs = effective_buffs(infantry)
        self.assertTrue(veh_buffs["reroll_hit_ones"], "VEHICLE should get reroll_hit_ones")
        self.assertFalse(inf_buffs["reroll_hit_ones"], "INFANTRY shouldn't")

    def test_canoptek_court_buffs_canoptek_attacker(self):
        """Canoptek Court: profile-name-prefix 'Canoptek' gets +1 to wound."""
        from code.detachments import CANOPTEK_COURT
        from code.leaders import effective_buffs
        army = Army("Necrons", detachment=CANOPTEK_COURT)
        army.add_unit(self._profile(
            "Canoptek Wraiths", "Necrons", keywords=("INFANTRY",),
        ))
        army.add_unit(self._profile(
            "Necron Warriors", "Necrons", keywords=("INFANTRY",),
        ))
        for u in army.units:
            u.position = (0.0, 0.0)
        wraiths = army.units[0]
        warriors = army.units[1]
        self.assertTrue(effective_buffs(wraiths)["plus_one_to_wound"])
        self.assertFalse(effective_buffs(warriors)["plus_one_to_wound"])

    def test_saim_hann_grants_extra_move_to_aspect_warriors(self):
        """Saim-Hann Wild Host: Aspect Warriors / Bikes gain +1" Move."""
        from code.detachments import SAIM_HANN_WILD_HOST, effective_move
        army = Army("Aeldari", detachment=SAIM_HANN_WILD_HOST)
        army.add_unit(self._profile(
            "Howling Banshees", "Aeldari", keywords=("INFANTRY",), move=8.0,
        ))
        army.add_unit(self._profile(
            "Guardian Defenders", "Aeldari", keywords=("INFANTRY",), move=7.0,
        ))
        banshees = army.units[0]
        guardians = army.units[1]
        self.assertAlmostEqual(effective_move(banshees), 9.0)
        self.assertAlmostEqual(effective_move(guardians), 7.0)

    def test_plague_marines_onslaught_buffs_plague_marines(self):
        """Plague Marines Onslaught: only profile.name == 'Plague Marines'."""
        from code.detachments import PLAGUE_MARINES_ONSLAUGHT
        from code.leaders import effective_buffs
        army = Army("Death Guard", detachment=PLAGUE_MARINES_ONSLAUGHT)
        army.add_unit(self._profile(
            "Plague Marines", "Death Guard", keywords=("INFANTRY",),
        ))
        army.add_unit(self._profile(
            "Poxwalkers", "Death Guard", keywords=("INFANTRY",),
        ))
        for u in army.units:
            u.position = (0.0, 0.0)
        plague = army.units[0]
        pox = army.units[1]
        self.assertTrue(effective_buffs(plague)["plus_one_to_wound"])
        self.assertFalse(effective_buffs(pox)["plus_one_to_wound"])

    def test_registry_count_grew_by_four(self):
        """Registry should have at least 25 entries after #126 (was 21)."""
        from code.detachments import DETACHMENTS
        self.assertGreaterEqual(len(DETACHMENTS), 25)

    def test_picker_tilts_canoptek_court_on_canoptek_heavy_army(self):
        """Necron army that's mostly Canoptek points should usually pick
        Canoptek Court, not Awakened Dynasty."""
        canoptek = UnitProfile(
            name="Canoptek Wraiths", health=4, damage=1, hit_probability=0.667,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            unit_keywords=("INFANTRY",), faction="Necrons",
            points_override=200.0,
        )
        warrior = UnitProfile(
            name="Necron Warriors", health=1, damage=1, hit_probability=0.667,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            unit_keywords=("INFANTRY",), faction="Necrons",
            points_override=50.0,
        )
        # 600 pts Canoptek vs 50 pts Warriors → ~92% Canoptek.
        army_units = [canoptek, canoptek, canoptek, warrior]
        picks = []
        for seed in range(60):
            rng = random.Random(seed)
            det = pick_detachment_for_army("Necrons", army_units, rng)
            picks.append(det.name)
        canoptek_picks = picks.count("Canoptek Court")
        self.assertGreater(
            canoptek_picks, 30,
            f"Canoptek-heavy Necron army picked Canoptek Court "
            f"{canoptek_picks}/60 — expected >30",
        )


if __name__ == "__main__":
    unittest.main()
