"""Group-2 #2 — faithful 10e Fight-phase alternation (gate SWEG_FIGHTALT).

The vanilla fight loop resolved only the ACTIVE army's units, deferring the
defender's retaliation to its own later turn. `Battle._run_fight_alternation`
restores 10e: both armies' engaged units fight in this Fight phase, alternating
(Fights First step then Remaining Combats), so a locked defender swings back
in-phase. These tests prove the in-phase retaliation and the fight-once-per-phase
property, driving the method directly. Cited `simulator.fight_alternation`.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


def _brawler(name: str, health: float = 12.0) -> UnitProfile:
    # Heavy reliable melee so a strike lands deterministic damage, high health so
    # neither model dies in one exchange (both get to fight).
    return UnitProfile(
        name=name,
        health=health,
        damage=1.0,
        hit_probability=0.5,
        ap=0,
        save=6,
        strength=4,
        toughness=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=1,
        unit_keywords=("INFANTRY",),
        melee_attacks=6,
        melee_hit_probability=1.0,
        melee_strength=8,
        melee_damage_per_shot=2.0,
    )


def _one_unit_army(name: str, pos) -> Army:
    army = Army(name)
    army.add_unit(_brawler(name + "U"))
    army.units[0].position = pos
    army.units[0].army_ref = army
    return army


class FightAlternationTests(unittest.TestCase):
    def _battle(self, a: Army, b: Army) -> Battle:
        battle = Battle(a, b, map_=Map("Test", 60.0, 44.0))
        battle._assign_uids()
        battle._current_round = 2
        return battle

    def test_defender_retaliates_in_phase(self):
        random.seed(7)
        a = _one_unit_army("A", (10.0, 10.0))
        b = _one_unit_army("B", (10.6, 10.0))   # within 1" Engagement Range
        battle = self._battle(a, b)
        ah = a.units[0].current_health
        bh = b.units[0].current_health
        battle._run_fight_alternation(a, b)
        # BOTH took damage — the defender (B) swung back in the active player's
        # fight phase, which the vanilla active-only loop would not have allowed.
        self.assertLess(b.units[0].current_health, bh, "defender should take damage")
        self.assertLess(a.units[0].current_health, ah, "attacker should take retaliation in-phase")

    def test_vanilla_active_only_no_retaliation(self):
        # Contrast: the per-model fight (what the OFF loop calls) lets only the
        # active unit strike; the defender does not swing back this call.
        random.seed(7)
        a = _one_unit_army("A", (10.0, 10.0))
        b = _one_unit_army("B", (10.6, 10.0))
        battle = self._battle(a, b)
        ah = a.units[0].current_health
        battle._do_fight(a.units[0], a, b)
        self.assertEqual(a.units[0].current_health, ah,
                         "active unit takes no damage when only it fights (no in-phase retaliation)")
        self.assertLess(b.units[0].current_health, 12.0, "defender took the active unit's blows")

    def test_each_unit_fights_at_most_once(self):
        # Two active brawlers both engaging one defender: the alternation must not
        # let either fight twice in one phase (fought-set guard).
        random.seed(1)
        a = Army("A")
        a.add_unit(_brawler("A0"))
        a.add_unit(_brawler("A1"))
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.2, 10.4)
        for u in a.units:
            u.army_ref = a
        b = _one_unit_army("B", (10.6, 10.0))
        b.units[0].current_health = 200.0   # tanky so it survives to bound the test
        battle = self._battle(a, b)

        calls = []
        real = battle._do_fight
        battle._do_fight = lambda u, aa, ff: (calls.append(u.uid), real(u, aa, ff))[1]
        battle._run_fight_alternation(a, b)
        self.assertEqual(len(calls), len(set(calls)),
                         "no unit fights twice in a single fight phase")


    def test_round_scoped_tracker_prevents_second_fight_and_resets_next_round(self):
        """Variant-b bounding: a unit that fought as a retaliating defender in
        the first player's Fight phase is NOT eligible to fight again in the
        second player's Fight phase of the SAME battle round (round-scoped
        tracker). The tracker resets at the start of each new round, so the
        unit CAN fight in the next round's Fight phase.

        Gate: SWEG_FIGHTALT=1 must be set for this path to execute.
        """
        import os
        os.environ["SWEG_FIGHTALT"] = "1"
        try:
            random.seed(42)
            a = _one_unit_army("A", (10.0, 10.0))
            b = _one_unit_army("B", (10.6, 10.0))   # within 1" Engagement Range
            # Give both sides enough health that neither dies in one exchange.
            a.units[0].current_health = 100.0
            b.units[0].current_health = 100.0
            battle = self._battle(a, b)

            # --- First player's Fight phase (active=A, other=B) ---
            battle._run_fight_alternation(a, b)
            # B's unit fought as the retaliating defender in A's fight phase;
            # its UID must now be in the round-scoped tracker.
            self.assertIn(b.units[0].uid, battle._fought_this_round,
                          "defender's UID must be recorded in _fought_this_round after retaliating")

            # --- Second player's Fight phase (active=B, other=A) in the SAME round ---
            # B's unit is now the active army, but it already fought this round;
            # variant-b prevents it from fighting again.
            calls_before = []
            real_do_fight = battle._do_fight
            fought_uids = []

            def _tracking_do_fight(u, aa, ff):
                fought_uids.append(u.uid)
                return real_do_fight(u, aa, ff)

            battle._do_fight = _tracking_do_fight
            battle._run_fight_alternation(b, a)

            self.assertNotIn(b.units[0].uid, fought_uids,
                             "B's unit must not fight again in the second player's Fight phase of the same round")

            # --- Next round: tracker resets, B's unit can fight again ---
            # Simulate _run_round's reset of the round-scoped tracker.
            battle._fought_this_round = set()
            fought_uids.clear()
            battle._run_fight_alternation(b, a)
            self.assertIn(b.units[0].uid, fought_uids,
                          "B's unit must be able to fight again after the round tracker resets")
        finally:
            del os.environ["SWEG_FIGHTALT"]


if __name__ == "__main__":
    unittest.main()
