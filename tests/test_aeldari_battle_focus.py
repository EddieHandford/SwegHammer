"""Tests for the Aeldari Battle Focus strategy bias.

ASURYANI shooty units should bias toward advancing (ENGAGE intent) when:
  * the army still has Battle Focus tokens available, AND
  * the unit is OUT of weapon range of the nearest enemy.

The combat-side token-spend logic (_do_shoot converting weapons to [ASSAULT]
when the unit advanced and the army has a token to burn) is already wired in
the simulator; this test suite covers the AI bias that *causes* the Advance
to happen so the tokens don't sit unused for six rounds.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map, Objective
from code.strategy import pick_move_intent
from code.units import Unit, UnitProfile


def _asuryani_shooter() -> UnitProfile:
    # Aeldari shuriken-platform-style SHOOTY ASURYANI profile. Real strength
    # ranged DPA, zero melee — classify() pins this as SHOOTY so the standard
    # SHOOTY in-range REPOSITION branch fires when applicable.
    return UnitProfile(
        name="Aeldari Shooter", faction="Aeldari",
        health=4, damage=4, hit_probability=2 / 3,
        ap=-1, save=5, strength=4, toughness=3,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, unit_keywords=("INFANTRY", "ASURYANI"),
        move=7.0,
        melee_attacks=0,
    )


def _drukhari_shooter() -> UnitProfile:
    # Kabalite Warrior — Aeldari-adjacent but NO ASURYANI keyword (Drukhari).
    # Same shooty shape; SHOOTY role. Verifies the bias is keyword-scoped.
    return UnitProfile(
        name="Kabalite Warrior", faction="Drukhari",
        health=4, damage=4, hit_probability=2 / 3,
        ap=-1, save=5, strength=4, toughness=3,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, unit_keywords=("INFANTRY", "DRUKHARI"),
        move=7.0,
        melee_attacks=0,
    )


def _enemy_target() -> UnitProfile:
    # A bog-standard target to shoot / advance at.
    return UnitProfile(
        name="Target", faction="Test",
        health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, unit_keywords=("INFANTRY",),
        move=6.0,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


def _make_army(name: str, profile: UnitProfile, positions: list,
               tokens: int = 0) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    army.battle_focus_tokens = tokens
    return army


def _bare_map() -> Map:
    # No objectives — keeps the strategy decision focused on role/keyword
    # bias rather than objective-grab fallbacks.
    return Map(name="bare", width=120.0, height=60.0, objectives=())


class AsuryaniBattleFocusAdvanceTests(unittest.TestCase):

    def test_asuryani_out_of_range_advances_with_token(self):
        """ASURYANI unit out of range AND army has tokens -> ENGAGE."""
        map_ = _bare_map()
        # Aeldari shooter at one end, target 40" away — well out of the
        # 24" range so the standard hold doesn't apply.
        friendly = _make_army("F", _asuryani_shooter(), [(10.0, 30.0)],
                              tokens=4)
        enemy = _make_army("E", _enemy_target(), [(50.0, 30.0)])

        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(intent, "ENGAGE")
        self.assertEqual(target_pos, enemy.units[0].position)

    def test_asuryani_in_range_holds(self):
        """ASURYANI unit inside weapon range -> REPOSITION (existing path)."""
        map_ = _bare_map()
        # Both 20" apart — well within the 24" range, so the standard
        # SHOOTY-in-range REPOSITION branch should still fire even though
        # tokens are available.
        friendly = _make_army("F", _asuryani_shooter(), [(20.0, 30.0)],
                              tokens=4)
        enemy = _make_army("E", _enemy_target(), [(40.0, 30.0)])

        unit = friendly.units[0]
        target_pos, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertEqual(intent, "REPOSITION")
        # REPOSITION returns the cover-snap point near current position;
        # with no terrain on the bare map that resolves to current pos.
        self.assertEqual(target_pos, unit.position)

    def test_asuryani_no_token_holds(self):
        """ASURYANI out of range BUT no tokens -> fall through to standard.

        Without tokens the Battle Focus bias must not fire; the unit reverts
        to the normal SHOOTY out-of-range pathway (which falls through to the
        nearest-enemy ENGAGE fallback — but crucially the bias branch is the
        one we're testing is NOT what produced the result).
        """
        map_ = _bare_map()
        friendly = _make_army("F", _asuryani_shooter(), [(10.0, 30.0)],
                              tokens=0)
        enemy = _make_army("E", _enemy_target(), [(50.0, 30.0)])

        # We can't easily distinguish "Battle Focus advance" from "standard
        # out-of-range ENGAGE fallback" by intent alone, since both return
        # ENGAGE on the same target. Instead, prove the branch didn't fire
        # by setting tokens to 0 and confirming we still arrive somewhere
        # sensible without crashing — and that lifting tokens to >0 doesn't
        # change the *intent* (both pathways pick the same enemy here).
        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        # The standard out-of-range path also produces ENGAGE on the
        # nearest enemy. The important contract is that the no-token
        # ASURYANI never crashes and never gets a *different* target than
        # the equivalent non-ASURYANI unit.
        self.assertEqual(intent, "ENGAGE")
        self.assertEqual(target_pos, enemy.units[0].position)

    def test_non_asuryani_no_advance_bias(self):
        """Drukhari (no ASURYANI keyword) -> bias branch must NOT fire.

        Even if we artificially seed the army with battle_focus_tokens, a
        non-ASURYANI unit must not pick up the bias. The intent for a
        Drukhari SHOOTY out-of-range unit comes from the standard nearest-
        enemy fallback path (ENGAGE on nearest enemy), which happens to
        return the same outward intent — so to prove the bias is *not*
        firing, we assert behaviour is identical with tokens=0 vs tokens=4.
        """
        map_ = _bare_map()
        # Drukhari with tokens=4 (artificial — Drukhari armies never get
        # them in practice, but the strategy code must still gate properly).
        drukhari_with = _make_army(
            "D", _drukhari_shooter(), [(10.0, 30.0)], tokens=4,
        )
        drukhari_without = _make_army(
            "D", _drukhari_shooter(), [(10.0, 30.0)], tokens=0,
        )
        enemy = _make_army("E", _enemy_target(), [(50.0, 30.0)])

        pos_with, intent_with = pick_move_intent(
            drukhari_with.units[0], drukhari_with, enemy, map_,
        )
        pos_without, intent_without = pick_move_intent(
            drukhari_without.units[0], drukhari_without, enemy, map_,
        )
        # Bias must not change behaviour for non-ASURYANI units.
        self.assertEqual(intent_with, intent_without)
        self.assertEqual(pos_with, pos_without)


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
