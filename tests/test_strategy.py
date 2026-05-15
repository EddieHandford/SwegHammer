"""Tests for the per-unit movement-intent strategy layer."""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map, Objective, Terrain, TerrainType
from code.strategy import (
    _gunline_charge_bonus,
    _is_gunline_target,
    _melee_target_score,
    pick_charge_target,
    pick_move_intent,
)
from code.units import Unit, UnitProfile


def _shooty_profile() -> UnitProfile:
    # High enough ranged DPA that classify() returns SHOOTY.
    return UnitProfile(
        name="Gunner", health=4, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24, melee_attacks=0,
    )


def _melee_profile() -> UnitProfile:
    return UnitProfile(
        name="Brawler", health=2, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=4, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5,
    )


def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


def _empty_map(*objectives: Objective) -> Map:
    return Map(name="test", width=60.0, height=60.0, objectives=tuple(objectives))


class HoldIntentTests(unittest.TestCase):

    def test_unit_on_uncontested_objective_holds(self):
        # OC=1 unit on an objective with no enemies around -> HOLD.
        objective = Objective(name="O1", x=30.0, y=30.0, control_radius=3.0)
        map_ = _empty_map(objective)
        friendly = _make_army("Friend", _shooty_profile(), [(30.0, 30.0)])
        # Enemies far away — definitely not contesting this objective.
        enemy = _make_army("Foe", _shooty_profile(), [(5.0, 5.0)])

        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(intent, "HOLD")
        self.assertEqual(target_pos, friendly.units[0].position)


class EngageIntentTests(unittest.TestCase):

    def test_melee_unit_with_no_nearby_objective_engages_nearest_enemy(self):
        # Map with one objective far away; MELEE role should bias to nearest enemy.
        objective = Objective(name="Far", x=2.0, y=2.0, control_radius=3.0)
        map_ = _empty_map(objective)
        friendly = _make_army("F", _melee_profile(), [(40.0, 40.0)])
        enemy = _make_army("E", _shooty_profile(), [(45.0, 40.0)])

        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(intent, "ENGAGE")
        self.assertEqual(target_pos, enemy.units[0].position)


class RepositionIntentTests(unittest.TestCase):

    def test_shooty_unit_with_enemy_in_range_reposition_no_move(self):
        # No objectives anywhere; SHOOTY with enemy inside range should stay put.
        map_ = Map(name="bare", width=60.0, height=60.0, objectives=())
        friendly = _make_army("F", _shooty_profile(), [(30.0, 30.0)])
        # Enemy within the shooter's 24" range.
        enemy = _make_army("E", _shooty_profile(), [(40.0, 35.0)])

        unit = friendly.units[0]
        target_pos, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertEqual(intent, "REPOSITION")
        # Same position -> simulator interprets this as "no move".
        self.assertEqual(target_pos, unit.position)


class StealVsCaptureTests(unittest.TestCase):
    """An enemy-held objective at 10" should beat an uncontested one at 6".

    Scoring (in code/strategy.py):
      STEAL value 3.5 / (1 + 10/12) ~= 1.91
      CAPTURE value 2.5 / (1 + 6/12)  ~= 1.67
    """

    def test_steal_beats_uncontested_at_shorter_range(self):
        uncontested = Objective(name="Near", x=36.0, y=30.0, control_radius=3.0)
        contested = Objective(name="Far",  x=20.0, y=30.0, control_radius=3.0)
        map_ = _empty_map(uncontested, contested)

        # Our unit is at (30, 30). Uncontested is 6 away, contested is 10 away.
        # Use a DUAL profile so role bias doesn't override objective scoring,
        # and place enemies away from both objectives' control radii except
        # the one we want to "steal".
        # DUAL role so neither REPOSITION (SHOOTY/HEAVY only) nor ENGAGE
        # (MELEE only) short-circuits the objective scorer.
        dual_profile = UnitProfile(
            name="Dual", health=2, damage=2, hit_probability=2 / 3,
            ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
            strength=4, range_inches=24,
            melee_attacks=2, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=4,
        )
        from code.roles import classify
        # Guard against future tuning changes: if this is no longer DUAL,
        # the role-bias branches change behaviour and this test fails noisily.
        self.assertEqual(classify(dual_profile), "DUAL")

        friendly = _make_army("F", dual_profile, [(30.0, 30.0)])

        # Place one enemy ON the contested objective (so b_oc > a_oc -> STEAL).
        # Keep other enemies far away from the uncontested objective.
        enemy = _make_army("E", dual_profile, [
            (20.0, 30.0),   # standing on the contested objective
            (55.0, 55.0),   # noise enemy, irrelevant
        ])

        unit = friendly.units[0]
        target_pos, intent = pick_move_intent(unit, friendly, enemy, map_)
        # The DUAL unit goes to (20, 30) — the contested objective AND a
        # high-value melee target. After the #96 strategy update, DUAL
        # units with a chargeable enemy in threat range emit ENGAGE
        # rather than STEAL; the destination is identical either way and
        # the simulator's downstream behaviour doesn't read the label.
        self.assertIn(intent, ("STEAL", "ENGAGE"))
        self.assertEqual(target_pos, (20.0, 30.0))


class CoverSnapTests(unittest.TestCase):
    """Phase H: HOLD on an objective with a ruin within ~3" should snap
    the target position INTO the ruin rather than the bare marker."""

    def test_hold_snaps_to_nearby_heavy_cover(self):
        # Objective at (30, 30); a heavy-cover ruin spans (31, 31)..(34, 34),
        # so a 3" sample circle around the unit/objective will land inside it.
        objective = Objective(name="O1", x=30.0, y=30.0, control_radius=3.0)
        ruin = Terrain(
            name="Ruin", x=31.0, y=31.0,
            width=3.0, height=3.0, type=TerrainType.HEAVY_COVER,
        )
        map_ = Map(
            name="terrain-test", width=60.0, height=60.0,
            terrain=(ruin,), objectives=(objective,),
        )
        # Unit standing on the marker.
        friendly = _make_army("F", _shooty_profile(), [(30.0, 30.0)])
        enemy = _make_army("E", _shooty_profile(), [(5.0, 5.0)])

        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(intent, "HOLD")
        # The snapped point must lie inside the ruin (the HEAVY_COVER rect),
        # not at the bare marker.
        self.assertTrue(
            ruin.contains(target_pos),
            f"expected HOLD to snap into ruin, got {target_pos}",
        )

    def test_capture_snaps_to_nearby_heavy_cover(self):
        # No HOLD trigger (we approach an objective from outside its control
        # radius). The CAPTURE destination should still snap to cover near
        # the marker so we arrive in the ruin instead of on bare ground.
        objective = Objective(name="O1", x=30.0, y=30.0, control_radius=3.0)
        ruin = Terrain(
            name="Ruin", x=31.0, y=31.0,
            width=3.0, height=3.0, type=TerrainType.HEAVY_COVER,
        )
        map_ = Map(
            name="terrain-test", width=60.0, height=60.0,
            terrain=(ruin,), objectives=(objective,),
        )
        # DUAL profile to avoid the SHOOTY/HEAVY REPOSITION shortcut.
        dual = UnitProfile(
            name="Dual", health=2, damage=2, hit_probability=2 / 3,
            ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
            strength=4, range_inches=24,
            melee_attacks=2, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=4,
        )
        friendly = _make_army("F", dual, [(10.0, 10.0)])
        # Enemy far away from the objective so the route to the objective
        # isn't pre-empted by REPOSITION (also at >24" from our unit).
        enemy = _make_army("E", dual, [(55.0, 55.0)])

        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        # Should be a CAPTURE/STEAL targeting the objective area.
        self.assertIn(intent, ("CAPTURE", "STEAL"))
        # Snapped destination lies inside the ruin (within objective range).
        self.assertTrue(
            ruin.contains(target_pos),
            f"expected snap to ruin, got {target_pos}",
        )


class GunlineChargeBonusTests(unittest.TestCase):
    """One-sided gunline-charge bonus (#114).

    Tough gunlines (T'au Crisis Battlesuits, Marine Devastators) under
    save-aware durability score as low-priority charge targets. Real
    opponents charge them anyway because letting them shoot is worse.
    The bonus fires only when (a) defender is gunline-style AND (b)
    attacker is NOT T'au — so T'au's own melee units (Vespid, Stealth
    Suits) don't game the bonus when picking enemy heavies.
    """

    @staticmethod
    def _battlesuit_profile(faction: str = "T'au Empire") -> UnitProfile:
        # T'au Crisis Battlesuit-ish: T5/W4/Sv3+, big ranged DPA, tiny melee.
        return UnitProfile(
            name="Crisis Battlesuit", faction=faction,
            health=4, damage=6, hit_probability=2 / 3,
            ap=-1, save=3, toughness=5,
            attacks=6, weapon_damage_per_shot=2.0,
            strength=5, range_inches=18,
            melee_attacks=2, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=4,
        )

    @staticmethod
    def _devastator_profile() -> UnitProfile:
        # Marine Devastators — gunline shape but Astartes faction.
        return UnitProfile(
            name="Devastator Squad", faction="Adeptus Astartes",
            health=2, damage=4, hit_probability=2 / 3,
            ap=-2, save=3, toughness=4,
            attacks=4, weapon_damage_per_shot=2.0,
            strength=8, range_inches=48,
            melee_attacks=2, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=4,
        )

    @staticmethod
    def _brawler_profile(faction: str = "Orks") -> UnitProfile:
        # Generic melee profile — close to neutral on the gunline detector.
        return UnitProfile(
            name="Brawler", faction=faction,
            health=2, damage=0, hit_probability=0,
            ap=0, save=4, toughness=4,
            attacks=0, range_inches=1,
            melee_attacks=4, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=5,
        )

    @staticmethod
    def _vespid_profile() -> UnitProfile:
        # T'au Vespid Stingwings — melee-leaning T'au unit. Faction is the
        # only thing that disqualifies it from the bonus.
        return UnitProfile(
            name="Vespid Stingwings", faction="T'au Empire",
            health=2, damage=2, hit_probability=0.5,
            ap=-1, save=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0,
            strength=5, range_inches=18,
            melee_attacks=3, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=4,
        )

    def _unit_at(self, profile: UnitProfile, pos):
        army = Army("X")
        army.add_unit(profile)
        u = army.units[-1]
        u.position = pos
        return u, army

    def test_opposing_army_attacker_gets_bonus_charging_battlesuit(self):
        # Ork brawler scoring a T'au battlesuit — bonus fires.
        ork = self._brawler_profile("Orks")
        suit = self._battlesuit_profile()
        bonus = _gunline_charge_bonus(ork, suit)
        self.assertGreater(
            bonus, 1.0,
            f"opposing-faction attacker should get gunline bonus, got {bonus}",
        )

    def test_tau_attacker_does_not_get_bonus_on_enemy_heavy(self):
        # T'au Vespid scoring an enemy Devastator gunline — NO bonus (T'au
        # attackers are excluded so the fix doesn't help T'au itself).
        vespid = self._vespid_profile()
        dev = self._devastator_profile()
        bonus = _gunline_charge_bonus(vespid, dev)
        self.assertEqual(
            bonus, 1.0,
            f"T'au attacker must not gain gunline bonus, got {bonus}",
        )

    def test_bonus_magnitude_on_synthetic_battlesuit(self):
        # Score Battlesuit as charge target from non-T'au attacker AND
        # compare to the same scoring with the bonus stripped — must be
        # >= 1.5x and bounded by 2.5x.
        attacker_prof = self._brawler_profile("Orks")
        target_prof = self._battlesuit_profile()
        bonus = _gunline_charge_bonus(attacker_prof, target_prof)
        self.assertGreaterEqual(
            bonus, 1.5,
            f"expected >=1.5x bonus on pure-gunline target, got {bonus}",
        )
        self.assertLessEqual(
            bonus, 2.5,
            f"bonus cap of 2.5x violated, got {bonus}",
        )

        # And the per-target score should reflect this multiplier.
        attacker, _ = self._unit_at(attacker_prof, (0.0, 0.0))
        target, _ = self._unit_at(target_prof, (5.0, 0.0))
        scored = _melee_target_score(attacker, target)
        # Recompute the base by routing through a "T'au attacker" — which
        # is forced to bonus=1.0. Use a stand-in T'au attacker with the
        # same stats so the only difference is the bonus gate.
        tau_stand_in = UnitProfile(
            **{**attacker_prof.__dict__, "faction": "T'au Empire"}
        )
        tau_attacker, _ = self._unit_at(tau_stand_in, (0.0, 0.0))
        base = _melee_target_score(tau_attacker, target)
        self.assertAlmostEqual(scored / base, bonus, places=4)
        self.assertGreaterEqual(scored / base, 1.5)

    def test_non_tau_gunline_also_gets_bonus(self):
        # Necron / Astartes attackers charging Marine Devastators should
        # ALSO trigger the bonus — it's a general gunline incentive, not
        # T'au-only. Choose a Necron-flavoured attacker faction.
        necron_attacker = self._brawler_profile("Necrons")
        dev = self._devastator_profile()
        self.assertTrue(_is_gunline_target(dev), "Devastators should classify as gunline target")
        bonus = _gunline_charge_bonus(necron_attacker, dev)
        self.assertGreater(
            bonus, 1.0,
            f"non-T'au gunline target should still trigger bonus, got {bonus}",
        )

    def test_brawler_target_does_not_get_bonus(self):
        # Sanity: a melee-heavy brawler is NOT a gunline target; bonus stays 1.0
        # even with the opposing-faction gate satisfied.
        ork_attacker = self._brawler_profile("Orks")
        marine_brawler = self._brawler_profile("Adeptus Astartes")
        bonus = _gunline_charge_bonus(ork_attacker, marine_brawler)
        self.assertEqual(bonus, 1.0)


if __name__ == "__main__":
    unittest.main()
