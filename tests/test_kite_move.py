"""Tests for SWEG_KITE_MOVE — proactive kite-step for threatened gunlines.

The gap this fills: the legacy AI's SHOOTY/HEAVY in-range branch HOLDS the
instant a gunline is in weapon range, even when an enemy melee unit is one turn
from charging it; the unit then gets charged and locked out of shooting. A
competent player KITES — retreats to stay outside the enemy's next-turn charge
bubble (enemy move + 12" average charge) while keeping a target in weapon range,
preserving multi-turn shooting output.

This is an AI play-style heuristic (same class as the screen / synapse / tarpit
biases), NOT a 10e rule, so it carries no rule citation. Default-OFF; when unset
the hook is never entered and the legacy intent is returned byte-identically.

Tests here cover:
  * ON: a threatened gunline kites out of the bubble AND keeps a target in range
  * OFF: byte-identical to base (gate unset == no kite, position/intent match)
  * a melee-primary unit does NOT kite (the melee over-pole must be untouched)
  * the mandatory rail: if no retreat keeps a target in range, fall through
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.strategy import pick_move_intent, _REPOSITION_INTENT
from code.units import UnitProfile


def _gunline_profile() -> UnitProfile:
    """High-DPA ranged profile: classify() -> SHOOTY, _is_gunline_target True."""
    return UnitProfile(
        name="Gunline", health=4, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
        strength=4, toughness=4, range_inches=24,
        melee_attacks=0, move=6.0,
        unit_keywords=("INFANTRY",),
    )


def _melee_profile() -> UnitProfile:
    """Melee-primary profile: classify() -> MELEE, _is_melee_class True."""
    return UnitProfile(
        name="Brawler", health=2, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=4, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5,
        move=6.0,
        unit_keywords=("INFANTRY",),
    )


def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


def _open_map() -> Map:
    """60x60 board, one central objective so strategy always has data.

    Placed at the board edge (5, 5) so the gunline scenarios below are not
    sitting on the marker — that keeps the on-objective HOLD branch out of the
    way and lets us observe the kite / legacy-reposition behaviour cleanly.
    """
    obj = Objective(name="Corner", x=5.0, y=5.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _dist(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class KiteMoveOnTests(unittest.TestCase):
    """SWEG_KITE_MOVE=1: a threatened gunline kites out of the bubble."""

    def setUp(self):
        # Gunline at (30, 30); melee enemy 10" east at (40, 30). The enemy's
        # next-turn charge bubble is move(6) + 12 = 18", and 10 < 18, so the
        # gunline is inside it. Range 24" comfortably keeps the enemy in range
        # after a westward 6" kite (distance becomes ~16").
        self.friendly = _make_army("Friend", _gunline_profile(), [(30.0, 30.0)])
        self.enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        self.map_ = _open_map()

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_threatened_gunline_kites_away_and_keeps_target_in_range(self):
        unit = self.friendly.units[0]
        threat = self.enemy.units[0]
        d_before = _dist(unit.position, threat.position)

        pos, intent = pick_move_intent(unit, self.friendly, self.enemy, self.map_)

        self.assertEqual(intent, _REPOSITION_INTENT)
        # The kite must move strictly AWAY from the melee threat.
        self.assertGreater(
            _dist(pos, threat.position), d_before,
            "kite must increase distance from the nearest melee threat",
        )
        # Mandatory rail: a target must remain within the gunline's range.
        rng = float(unit.profile.range_inches)
        self.assertLessEqual(
            _dist(pos, threat.position), rng,
            "kite must keep at least one enemy within weapon range",
        )

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_kite_does_not_fire_when_no_melee_threat_in_bubble(self):
        # Move the melee enemy far out of its own charge bubble (50" away,
        # well past move+12=18"): no threat, so no kite — legacy intent stands.
        self.enemy.units[0].position = (30.0 + 50.0, 30.0)
        # Clamp inside the 60-wide board.
        self.enemy.units[0].position = (59.0, 30.0)
        unit = self.friendly.units[0]
        pos_on, intent_on = pick_move_intent(
            unit, self.friendly, self.enemy, self.map_,
        )
        # With the threat gone the kite cannot bite; the result must match the
        # gate-OFF (legacy) result exactly.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SWEG_KITE_MOVE", None)
            pos_off, intent_off = pick_move_intent(
                unit, self.friendly, self.enemy, self.map_,
            )
        self.assertEqual((pos_on, intent_on), (pos_off, intent_off))


class KiteMoveOffByteIdenticalTests(unittest.TestCase):
    """Gate unset: the kite hook is skipped and the legacy intent is returned
    byte-identically (same position, same intent)."""

    def test_off_is_byte_identical_to_base(self):
        friendly = _make_army("Friend", _gunline_profile(), [(30.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        map_ = _open_map()
        unit = friendly.units[0]

        # Capture the legacy result with the gate explicitly unset.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SWEG_KITE_MOVE", None)
            base_pos, base_intent = pick_move_intent(unit, friendly, enemy, map_)

        # The legacy SHOOTY in-range path does NOT kite away from the threat:
        # it never increases distance from the melee enemy.
        threat = enemy.units[0]
        d_before = _dist(unit.position, threat.position)
        self.assertLessEqual(
            _dist(base_pos, threat.position), d_before + 1e-9,
            "legacy (OFF) path must not retreat from the melee threat",
        )

        # Re-running with the gate unset again is identical (determinism).
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SWEG_KITE_MOVE", None)
            again_pos, again_intent = pick_move_intent(
                unit, friendly, enemy, map_,
            )
        self.assertEqual((base_pos, base_intent), (again_pos, again_intent))

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_on_changes_behaviour_vs_off(self):
        """The whole point: ON must produce a DIFFERENT (kited) position than
        OFF for a threatened gunline — proving the flag actually bites."""
        friendly = _make_army("Friend", _gunline_profile(), [(30.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        map_ = _open_map()
        unit = friendly.units[0]

        on_pos, on_intent = pick_move_intent(unit, friendly, enemy, map_)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SWEG_KITE_MOVE", None)
            off_pos, off_intent = pick_move_intent(unit, friendly, enemy, map_)

        self.assertNotEqual(
            on_pos, off_pos,
            "ON must kite to a different position than the OFF legacy hold",
        )
        threat = enemy.units[0]
        self.assertGreater(
            _dist(on_pos, threat.position), _dist(off_pos, threat.position),
            "ON must end up farther from the melee threat than OFF",
        )


class KiteMoveMeleeUnitTests(unittest.TestCase):
    """A melee-primary unit must NEVER kite — the gate excludes non-gunlines so
    the melee over-pole (Berzerkers / Ork Boyz / Tyranids) is untouched."""

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_melee_unit_does_not_kite(self):
        # A melee-primary unit threatened by an enemy melee unit must not kite;
        # MELEE units take the MELEE close-on-target branch, never REPOSITION
        # from the kite hook.
        friendly = _make_army("Friend", _melee_profile(), [(30.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        map_ = _open_map()
        unit = friendly.units[0]
        threat = enemy.units[0]
        d_before = _dist(unit.position, threat.position)

        pos, intent = pick_move_intent(unit, friendly, enemy, map_)

        # A melee unit closes IN, never retreats away from its target.
        self.assertLessEqual(
            _dist(pos, threat.position), d_before + 1e-9,
            "a melee-primary unit must not kite away from the enemy",
        )


class KiteMoveRailTests(unittest.TestCase):
    """The mandatory keep-a-target-in-range rail: if no retreat both reduces
    exposure AND keeps a target in range, the kite falls through to legacy."""

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_short_range_gunline_with_no_reachable_target_falls_through(self):
        # A short-range gunline (range 6") that is inside the melee bubble but
        # whose only enemy would drop out of weapon range the instant it
        # retreats must NOT kite — it should fall through to the legacy intent.
        short = UnitProfile(
            name="ShortGun", health=4, damage=4, hit_probability=2 / 3,
            ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
            strength=4, toughness=4, range_inches=6,
            melee_attacks=0, move=6.0,
            unit_keywords=("INFANTRY",),
        )
        # Gunline at (30,30); melee enemy 5" away (inside both the 6" weapon
        # range AND the move+12 charge bubble). A 6" kite away pushes the enemy
        # to ~11" — outside the 6" range — so the rail blocks the kite.
        friendly = _make_army("Friend", short, [(30.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(35.0, 30.0)])
        map_ = _open_map()
        unit = friendly.units[0]
        threat = enemy.units[0]
        d_before = _dist(unit.position, threat.position)

        pos, intent = pick_move_intent(unit, friendly, enemy, map_)

        # The kite must not have fired: the unit did not retreat out of range.
        self.assertLessEqual(
            _dist(pos, threat.position), d_before + 1e-9,
            "rail must block a kite that would drop every target out of range",
        )


class KiteObjectiveAwareTests(unittest.TestCase):
    """Wave-247 objective-awareness refinement: the kite must not abandon the
    primary game. Three behaviours:
      * a gunline that is the SWING body on a marker it holds/contests does NOT
        kite (it holds; reactive Fall Back still available if charged);
      * expendable chaff does NOT kite (it holds/screens);
      * when a valuable non-swing gunline DOES kite and the army holds a marker
        behind it, the retreat point steers TOWARD that marker.
    """

    @staticmethod
    def _gun(points_override: float = 20.0, oc: int = 2) -> UnitProfile:
        return UnitProfile(
            name="Gun", health=4, damage=4, hit_probability=2 / 3,
            ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
            strength=4, toughness=4, range_inches=24,
            melee_attacks=0, move=6.0, unit_keywords=("INFANTRY",),
            points_override=points_override, oc=oc,
        )

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_swing_holder_does_not_kite(self):
        # A lone gunline standing on a marker it solely controls (oc 2, no enemy
        # body on the marker) is the SWING: leaving flips the marker from held to
        # uncontrolled. The on-marker suppression must keep it put even though a
        # melee threat sits inside its charge bubble.
        obj = Objective(name="Mid", x=30.0, y=30.0, control_radius=3.0)
        map_ = Map(name="mid", width=60.0, height=60.0, objectives=(obj,))
        friendly = _make_army("Friend", self._gun(oc=2), [(30.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        unit = friendly.units[0]
        threat = enemy.units[0]
        d_before = _dist(unit.position, threat.position)

        pos, intent = pick_move_intent(unit, friendly, enemy, map_)

        # Must NOT retreat away from the threat — it holds the marker instead.
        self.assertLessEqual(
            _dist(pos, threat.position), d_before + 1e-9,
            "a swing marker-holder must not kite off its objective",
        )

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_expendable_chaff_does_not_kite(self):
        # A cheap (6-pt) gunline is chaff: it should hold/screen, never kite, so
        # the kite cannot retreat the whole cheap-bodies army off the board.
        obj = Objective(name="Corner", x=5.0, y=5.0, control_radius=3.0)
        map_ = Map(name="corner", width=60.0, height=60.0, objectives=(obj,))
        friendly = _make_army("Friend", self._gun(points_override=6.0, oc=1),
                              [(30.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        unit = friendly.units[0]
        threat = enemy.units[0]
        d_before = _dist(unit.position, threat.position)

        pos, intent = pick_move_intent(unit, friendly, enemy, map_)

        self.assertLessEqual(
            _dist(pos, threat.position), d_before + 1e-9,
            "expendable chaff must not kite away from the threat",
        )

    @mock.patch.dict(os.environ, {"SWEG_KITE_MOVE": "1"})
    def test_kite_steers_toward_a_wanted_marker(self):
        # A valuable gunline that is NOT the swing (a friendly buddy already
        # holds the west marker) kites away from the east threat AND should steer
        # toward the wanted west marker rather than fleeing on the bare
        # straight-back line.
        objw = Objective(name="West", x=10.0, y=30.0, control_radius=3.0)
        map_ = Map(name="west", width=60.0, height=60.0, objectives=(objw,))
        friendly = _make_army(
            "Friend", self._gun(oc=2), [(30.0, 30.0), (10.0, 30.0)],
        )
        enemy = _make_army("Foe", _melee_profile(), [(40.0, 30.0)])
        unit = friendly.units[0]          # the kiter
        threat = enemy.units[0]
        d_threat_before = _dist(unit.position, threat.position)
        d_west_before = _dist(unit.position, (10.0, 30.0))

        pos, intent = pick_move_intent(unit, friendly, enemy, map_)

        self.assertEqual(intent, _REPOSITION_INTENT)
        self.assertGreater(
            _dist(pos, threat.position), d_threat_before,
            "kite must still move away from the melee threat",
        )
        self.assertLess(
            _dist(pos, (10.0, 30.0)), d_west_before,
            "kite should steer toward the army's held west marker",
        )


if __name__ == "__main__":
    unittest.main()
