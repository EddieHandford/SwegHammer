"""Phase I tests — Deep Strike / Scout / Infiltrators deployment abilities.

Three layers:
  1. Mapper: extract_deployment_abilities parses synthetic infoLink XML.
  2. Catalog: a UnitProfile flagged deep_strike=True stays in reserves at
     deployment time and is not placed on the board.
  3. Simulator: a scout_distance > 0 unit moves up to N inches in the
     pre-Round 1 scout phase and emits UnitScouted.
"""

from __future__ import annotations

import os
import random
import unittest
import xml.etree.ElementTree as ET

from code.army import Army
from code.bsdata.mapper import extract_deployment_abilities
from code.events import EventLog, UnitDeepStrike, UnitInfiltrated, UnitScouted
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Mapper extraction
# ---------------------------------------------------------------------------

def _make_entry(infolinks: list) -> ET.Element:
    """Build a tiny selectionEntry XML element with the given infoLinks.

    Each infolink is a tuple (name, modifiers) where modifiers is a list of
    (field, type, value) triples.
    """
    entry = ET.Element("selectionEntry", attrib={"name": "TestUnit", "type": "unit"})
    holder = ET.SubElement(entry, "infoLinks")
    for nm, mods in infolinks:
        il = ET.SubElement(holder, "infoLink", attrib={"name": nm, "type": "rule"})
        if mods:
            mods_holder = ET.SubElement(il, "modifiers")
            for field, mtype, value in mods:
                ET.SubElement(
                    mods_holder, "modifier",
                    attrib={"field": field, "type": mtype, "value": value},
                )
    return entry


class ExtractDeploymentAbilitiesTests(unittest.TestCase):

    def test_deep_strike_infolink(self):
        entry = _make_entry([("Deep Strike", [])])
        out = extract_deployment_abilities(entry)
        self.assertTrue(out["deep_strike"])
        self.assertFalse(out["infiltrator"])
        self.assertEqual(out["scout_distance"], 0)

    def test_infiltrators_infolink(self):
        entry = _make_entry([("Infiltrators", [])])
        out = extract_deployment_abilities(entry)
        self.assertTrue(out["infiltrator"])
        self.assertFalse(out["deep_strike"])

    def test_scouts_distance_via_modifier(self):
        # BSData canonical shape: name="Scouts" + child modifier appends ' 6"'.
        entry = _make_entry([
            ("Scouts", [("name", "append", "6\"")]),
        ])
        out = extract_deployment_abilities(entry)
        self.assertEqual(out["scout_distance"], 6)

    def test_scouts_distance_via_name(self):
        # Alternate shape: distance baked into the infoLink name.
        entry = _make_entry([("Scouts 8\"", [])])
        out = extract_deployment_abilities(entry)
        self.assertEqual(out["scout_distance"], 8)

    def test_scouts_default_distance_when_unparsed(self):
        # A bare 'Scouts' with no modifier and no number falls back to 6".
        entry = _make_entry([("Scouts", [])])
        out = extract_deployment_abilities(entry)
        self.assertEqual(out["scout_distance"], 6)

    def test_no_abilities_returns_zeros(self):
        entry = _make_entry([("Stealth", [])])
        out = extract_deployment_abilities(entry)
        self.assertFalse(out["deep_strike"])
        self.assertFalse(out["infiltrator"])
        self.assertEqual(out["scout_distance"], 0)

    def test_multiple_scouts_takes_largest(self):
        # Defensive: a unit with two Scouts infoLinks (legacy data quirk)
        # should take the larger distance.
        entry = _make_entry([
            ("Scouts", [("name", "append", "6\"")]),
            ("Scouts", [("name", "append", "9\"")]),
        ])
        out = extract_deployment_abilities(entry)
        self.assertEqual(out["scout_distance"], 9)


# ---------------------------------------------------------------------------
# Simulator deployment behaviour
# ---------------------------------------------------------------------------

def _basic_profile(**overrides) -> UnitProfile:
    """A minimal UnitProfile — useful for behaviour tests where stats are
    incidental and only deployment flags matter."""
    base = dict(
        name="TestUnit", health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
    )
    base.update(overrides)
    return UnitProfile(**base)


class DeploymentSimulatorTests(unittest.TestCase):

    def test_deep_strike_unit_not_on_board_at_deployment(self):
        random.seed(0)
        a = Army("Alpha")
        b = Army("Bravo")
        # Two units in Alpha: one stays put, one deep strikes.
        a.add_unit(_basic_profile(name="GroundPounder"))
        a.add_unit(_basic_profile(name="DropTrooper", deep_strike=True))
        b.add_unit(_basic_profile(name="Defender"))

        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()

        # Only one Alpha unit should be on-board; the deep-striker is in reserves.
        on_board_names = {u.profile.name for u in a.units}
        self.assertIn("GroundPounder", on_board_names)
        self.assertNotIn("DropTrooper", on_board_names)
        # The reserves bucket should hold the deep-striker.
        reserves_names = {u.profile.name for u in battle._reserves[a.name]}
        self.assertEqual(reserves_names, {"DropTrooper"})

    def test_scout_unit_moves_in_scout_phase(self):
        random.seed(0)
        a = Army("Alpha")
        b = Army("Bravo")
        a.add_unit(_basic_profile(name="Scout", scout_distance=6))
        b.add_unit(_basic_profile(name="Target"))

        log = EventLog()
        battle = Battle(a, b, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        # Capture pre-scout position
        scout = a.units[0]
        start_pos = scout.position
        battle._run_scout_phase()
        end_pos = scout.position

        # The scout should have moved toward the enemy (positive y direction
        # on this map since Bravo deploys on the high-y edge).
        moved_dist = ((end_pos[0] - start_pos[0]) ** 2
                      + (end_pos[1] - start_pos[1]) ** 2) ** 0.5
        self.assertGreater(moved_dist, 0.0)
        self.assertLessEqual(moved_dist, 6.0 + 1e-6)
        # UnitScouted event emitted.
        scouted = [e for e in log.events if isinstance(e, UnitScouted)]
        self.assertEqual(len(scouted), 1)
        self.assertEqual(scouted[0].unit_uid, scout.uid)

    def test_infiltrator_deploys_past_deployment_line(self):
        random.seed(0)
        a = Army("Alpha")
        b = Army("Bravo")
        a.add_unit(_basic_profile(name="StdInfantry"))
        a.add_unit(_basic_profile(name="Infiltrator", infiltrator=True))
        b.add_unit(_basic_profile(name="EnemyHQ"))

        log = EventLog()
        battle = Battle(a, b, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()

        std = next(u for u in a.units if u.profile.name == "StdInfantry")
        infil = next(u for u in a.units if u.profile.name == "Infiltrator")

        # Alpha deploys at low y; infiltrator should sit FURTHER from Alpha's
        # edge (i.e. higher y) than the standard unit.
        self.assertGreater(infil.position[1], std.position[1])
        # And it should be emitted as a UnitInfiltrated event.
        infiltrated = [e for e in log.events if isinstance(e, UnitInfiltrated)]
        self.assertEqual(len(infiltrated), 1)
        self.assertEqual(infiltrated[0].unit_uid, infil.uid)

    def test_deep_strike_arrives_after_round_one(self):
        random.seed(0)
        a = Army("Alpha")
        b = Army("Bravo")
        # Bravo has no deep-strikers; Alpha has one reserved unit.
        a.add_unit(_basic_profile(name="ReserveAlpha", deep_strike=True))
        # Add an on-board chaff unit so the battle doesn't terminate at deploy.
        a.add_unit(_basic_profile(name="GroundAlpha"))
        b.add_unit(_basic_profile(name="GroundBravo"))

        log = EventLog()
        battle = Battle(a, b, subscribers=[log])
        # Don't run the full battle — drive deployment + reserves arrival manually
        battle._assign_uids()
        battle._deploy_armies()
        self.assertEqual(len(battle._reserves[a.name]), 1)

        # Force arrival from Round 4 (auto-arrive) so the random gate doesn't
        # bite us in this test.
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=4)
        # The reserves should now be empty and the unit added to army.units.
        self.assertEqual(len(battle._reserves[a.name]), 0)
        names = {u.profile.name for u in a.units}
        self.assertIn("ReserveAlpha", names)
        # UnitDeepStrike emitted.
        ds_events = [e for e in log.events if isinstance(e, UnitDeepStrike)]
        self.assertEqual(len(ds_events), 1)

    def test_deep_strike_arrival_more_than_9in_from_enemies(self):
        random.seed(1)
        a = Army("Alpha")
        b = Army("Bravo")
        a.add_unit(_basic_profile(name="ReserveAlpha", deep_strike=True))
        # Need at least one on-board unit so the battle is well-formed.
        a.add_unit(_basic_profile(name="GroundAlpha"))
        b.add_unit(_basic_profile(name="Defender1"))
        b.add_unit(_basic_profile(name="Defender2"))

        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=4)

        arrived = next(u for u in a.units if u.profile.name == "ReserveAlpha")
        for enemy in b.alive_units:
            dx = arrived.position[0] - enemy.position[0]
            dy = arrived.position[1] - enemy.position[1]
            d = (dx * dx + dy * dy) ** 0.5
            self.assertGreater(d, 9.0,
                f"Deep-strike arrival at {arrived.position} was {d:.2f}\" "
                f"from enemy at {enemy.position} — should be >9\"")


# ---------------------------------------------------------------------------
# Intelligent deployment + screening (env-gated SWEG_DEPLOY)
# ---------------------------------------------------------------------------

def _chaff_profile() -> UnitProfile:
    """A cheap, high-model-count, low-value screen unit (Guardsman-ish)."""
    return _basic_profile(
        name="Chaff", health=1, save=5, toughness=3, strength=3,
        attacks=1, weapon_damage_per_shot=1.0, points_per_squad=60,
        min_models=10, max_models=20,
    )


def _gunline_brick() -> UnitProfile:
    """A durable, high-value back-line shooting brick (tank-ish)."""
    return _basic_profile(
        name="GunlineBrick", health=12, save=2, toughness=10, strength=10,
        ap=-3, attacks=8, weapon_damage_per_shot=3.0, points_per_squad=200,
        min_models=1, max_models=1, unit_keywords=("VEHICLE",),
    )


def _character() -> UnitProfile:
    """A lone high-value support character."""
    return _basic_profile(
        name="WarlordCharacter", health=6, save=2, toughness=4, strength=4,
        attacks=4, weapon_damage_per_shot=1.0, points_per_squad=90,
        min_models=1, max_models=1, unit_keywords=("CHARACTER",),
    )


def _deploy_with_gate(a: Army, b: Army, gate_on: bool):
    """Deploy both armies with SWEG_DEPLOY set/unset and return the Battle."""
    prev = os.environ.get("SWEG_DEPLOY")
    if gate_on:
        os.environ["SWEG_DEPLOY"] = "1"
    else:
        os.environ["SWEG_DEPLOY"] = "0"   # intelligent deployment is now default-ON
    try:
        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()
        return battle
    finally:
        if prev is None:
            os.environ.pop("SWEG_DEPLOY", None)
        else:
            os.environ["SWEG_DEPLOY"] = prev


class IntelligentDeploymentTests(unittest.TestCase):

    def _mixed_armies(self):
        random.seed(0)
        a = Army("Alpha")
        b = Army("Bravo")
        for army in (a, b):
            army.add_squad(_chaff_profile(), size=10)   # screen
            army.add_squad(_gunline_brick(), size=1)    # back
            army.add_squad(_character(), size=1)        # back
        return a, b

    def test_screen_deploys_forward_of_high_value_both_armies(self):
        a, b = self._mixed_armies()
        battle = _deploy_with_gate(a, b, gate_on=True)
        height = battle.map.height

        a_chaff = [u for u in a.units if u.profile.name == "Chaff"]
        a_brick = next(u for u in a.units if u.profile.name == "GunlineBrick")
        a_char = next(u for u in a.units if u.profile.name == "WarlordCharacter")
        b_chaff = [u for u in b.units if u.profile.name == "Chaff"]
        b_brick = next(u for u in b.units if u.profile.name == "GunlineBrick")
        b_char = next(u for u in b.units if u.profile.name == "WarlordCharacter")

        a_screen_y = a_chaff[0].position[1]
        b_screen_y = b_chaff[0].position[1]

        # Alpha deploys at low y; mid-board is at higher y. The screen must sit
        # at a higher y (closer to mid-board) than the brick and character.
        self.assertGreater(a_screen_y, a_brick.position[1])
        self.assertGreater(a_screen_y, a_char.position[1])
        # Bravo deploys at high y; mid-board is at lower y. Mirrored: the screen
        # must sit at a LOWER y (closer to mid-board) than its back units.
        self.assertLess(b_screen_y, b_brick.position[1])
        self.assertLess(b_screen_y, b_char.position[1])

    def test_both_groups_inside_deployment_zone(self):
        a, b = self._mixed_armies()
        battle = _deploy_with_gate(a, b, gate_on=True)
        dz = battle.map.deployment_width
        height = battle.map.height

        # Alpha's deployment zone is y in [0, dz]; Bravo's is [height-dz, height].
        for u in a.units:
            if u.embarked_in is not None:
                continue
            self.assertGreaterEqual(u.position[1], 0.0)
            self.assertLessEqual(u.position[1], dz + 1e-6,
                f"Alpha unit {u.profile.name} at y={u.position[1]} forward of zone")
        for u in b.units:
            if u.embarked_in is not None:
                continue
            self.assertLessEqual(u.position[1], height + 1e-6)
            self.assertGreaterEqual(u.position[1], height - dz - 1e-6,
                f"Bravo unit {u.profile.name} at y={u.position[1]} forward of zone")

    def test_squad_coherency_preserved(self):
        a, b = self._mixed_armies()
        _deploy_with_gate(a, b, gate_on=True)
        # The 10-model chaff squad's models must each be within 2" of another
        # model in the squad (coherency), as _deploy_line guarantees.
        chaff = [u for u in a.units if u.profile.name == "Chaff"]
        xs = sorted(u.position[0] for u in chaff)
        for i in range(1, len(xs)):
            self.assertLessEqual(xs[i] - xs[i - 1], 2.0 + 1e-6)
        # All chaff models share one y (one deployment row).
        ys = {round(u.position[1], 6) for u in chaff}
        self.assertEqual(len(ys), 1)

    def test_off_is_byte_identical_to_single_line(self):
        # Build two identical army pairs; deploy one with the gate OFF and one
        # via the legacy single _deploy_line call directly. Positions must match.
        # SWEG_DEPLOY_COLLISION is pinned OFF for the full-pipeline arm: the
        # hand-built reference below calls _deploy_line directly and so never
        # runs the (default-ON since wave 240) post-placement collision
        # relaxation — this test isolates the SWEG_DEPLOY identity only.
        a1, b1 = self._mixed_armies()
        prev_coll = os.environ.get("SWEG_DEPLOY_COLLISION")
        os.environ["SWEG_DEPLOY_COLLISION"] = "0"
        try:
            battle_off = _deploy_with_gate(a1, b1, gate_on=False)
        finally:
            if prev_coll is None:
                os.environ.pop("SWEG_DEPLOY_COLLISION", None)
            else:
                os.environ["SWEG_DEPLOY_COLLISION"] = prev_coll

        a2, b2 = self._mixed_armies()
        battle_ref = Battle(a2, b2)
        battle_ref._assign_uids()
        # Reproduce the legacy path by hand: single line at the zone midline.
        a_y = battle_ref.map.deployment_width / 2.0
        b_y = battle_ref.map.height - battle_ref.map.deployment_width / 2.0
        battle_ref._embark_pregame_passengers()
        a_std = [u for u in a2.units if u.embarked_in is None]
        b_std = [u for u in b2.units if u.embarked_in is None]
        battle_ref._deploy_line(a_std, a_y)
        battle_ref._deploy_line(b_std, b_y)

        off_pos = {u.uid: u.position for u in a1.units + b1.units}
        ref_pos = {u.uid: u.position for u in a2.units + b2.units}
        self.assertEqual(off_pos, ref_pos)

    def test_pure_gunline_all_in_back(self):
        # No screen-class unit available → everything deploys in the back group.
        random.seed(0)
        a = Army("Alpha")
        b = Army("Bravo")
        for army in (a, b):
            army.add_squad(_gunline_brick(), size=1)
            army.add_squad(_character(), size=1)
        battle = _deploy_with_gate(a, b, gate_on=True)
        dz = battle.map.deployment_width
        # All Alpha units sit in the back group — at the deployment-zone midline
        # (the legacy gunline position with a clear firing lane; wave-103
        # refinement un-buried the guns from the board edge), i.e. none was pushed
        # to the forward screen row at y≈dz-3.
        for u in a.units:
            self.assertLess(u.position[1], dz - 3.0,
                f"{u.profile.name} at y={u.position[1]} should be in the back group, not the forward screen row")


if __name__ == "__main__":
    unittest.main()
