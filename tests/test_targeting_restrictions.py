"""Tests for the 10e core ranged-targeting restrictions: the Leader /
Attached-unit protection (SWEG_LEADER_ATTACH, default-on) and Lone Operative.
Both gates are implemented in `code.army.can_target_for_ranged`. Wahapedia
citations live in `data/rule_citations.d/core_targeting.json`. (The fabricated
"Look Out, Sir" gate these tests used to cover was deleted 2026-07-13.)
"""

from __future__ import annotations

import os
import unittest

from code.army import can_target_for_ranged
from code.units import Unit, UnitProfile


def _make_unit(
    name: str,
    position: tuple,
    unit_keywords: tuple = (),
    lone_operative: bool = False,
    precision: bool = False,
    squad_id: int = -1,
    attach_host_squad_id=None,
) -> Unit:
    """Build a barebones Unit instance for targeting-rule tests.

    The combat stats don't matter — only `position`, `unit_keywords`, the
    `lone_operative`/`precision` profile flags, and (for the attachment gate)
    `squad_id` / `_attach_host_squad_id` are read by `can_target_for_ranged`.
    """
    profile = UnitProfile(
        name=name,
        health=2.0,
        damage=1.0,
        hit_probability=2 / 3,
        ap=0,
        save=4,
        unit_keywords=tuple(unit_keywords),
        lone_operative=lone_operative,
        precision=precision,
    )
    u = Unit(profile)
    u.position = position
    u.squad_id = squad_id
    u._attach_host_squad_id = attach_host_squad_id
    return u


class LeaderAttachmentTests(unittest.TestCase):
    """10e Leader / Attached-unit protection (SWEG_LEADER_ATTACH, default-on):
    an attached CHARACTER cannot be selected as a target while its bound host
    squad still has a living bodyguard model, at ANY range; [PRECISION] picks it
    out; once the host squad is destroyed it is a normal target. (Replaces the
    deleted 'Look Out, Sir' tests.)"""

    def setUp(self):
        # Ensure the default-on gate is active regardless of prior tests.
        os.environ.pop("SWEG_LEADER_ATTACH", None)

    def _attached(self):
        host = _make_unit("Tactical Squad", (2.0, 0.0),
                          unit_keywords=("INFANTRY",), squad_id=7)
        char = _make_unit("Captain", (0.0, 0.0),
                          unit_keywords=("CHARACTER", "INFANTRY"),
                          attach_host_squad_id=7)
        return char, host

    def test_attached_leader_not_targetable_any_range(self):
        """No 12" escape — the leader is protected while its bodyguard lives."""
        char, host = self._attached()
        for d in (5.0, 15.0, 30.0):
            attacker = _make_unit("Sniper", (d, 0.0), unit_keywords=("INFANTRY",))
            self.assertFalse(
                can_target_for_ranged(attacker, char, [char, host]),
                f"attached leader must be untargetable at {d}in")

    def test_precision_picks_out_the_leader(self):
        char, host = self._attached()
        attacker = _make_unit("Vindicare", (15.0, 0.0),
                              unit_keywords=("INFANTRY",), precision=True)
        self.assertTrue(can_target_for_ranged(attacker, char, [char, host]))

    def test_targetable_once_host_destroyed(self):
        char, host = self._attached()
        host.current_health = 0.0          # bodyguard squad wiped
        attacker = _make_unit("Sniper", (15.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertTrue(can_target_for_ranged(attacker, char, [char, host]))

    def test_unattached_leader_is_a_normal_target(self):
        """A CHARACTER with no bound host (orphaned / not a leader) is targetable."""
        char = _make_unit("Captain", (0.0, 0.0),
                          unit_keywords=("CHARACTER", "INFANTRY"))
        attacker = _make_unit("Sniper", (30.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertTrue(can_target_for_ranged(attacker, char, [char]))


class LoneOperativeTests(unittest.TestCase):
    """Lone Operative: ranged attackers must be within 12"."""

    def test_lone_operative_blocks_long_range(self):
        """Lone Operative target, attacker 15" — NOT targetable."""
        target = _make_unit(
            "Eliminator", (0.0, 0.0),
            unit_keywords=("INFANTRY",), lone_operative=True,
        )
        attacker = _make_unit("Devastator", (15.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertFalse(can_target_for_ranged(attacker, target, [target]))

    def test_lone_operative_targetable_at_short_range(self):
        """Same target, attacker 8" — IS targetable (inside 12")."""
        target = _make_unit(
            "Eliminator", (0.0, 0.0),
            unit_keywords=("INFANTRY",), lone_operative=True,
        )
        attacker = _make_unit("Devastator", (8.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertTrue(can_target_for_ranged(attacker, target, [target]))


class LeaderSquadDedupeTests(unittest.TestCase):
    """SWEG_LEADER_SQUAD_DEDUPE (default-ON, adopted 2026-07-13): a multi-model
    LEADER unit — a Cadian Command Squad, whose non-commander models the BSData
    catalogue wrongly tags CHARACTER — must bind to a host as ONE leader, not
    once per model. Otherwise its models each claim a leader slot, hogging the
    host and crowding the army's real single-model character (a Cadian Castellan)
    out of protection. `SWEG_LEADER_SQUAD_DEDUPE=0` reverts to the per-model
    binding.
    """

    def setUp(self):
        os.environ.pop("SWEG_LEADER_SQUAD_DEDUPE", None)

    def tearDown(self):
        os.environ.pop("SWEG_LEADER_SQUAD_DEDUPE", None)

    def _army(self):
        # One host squad (2 leader slots) + the multi-model bug unit + a real
        # lone character that also attaches to the same host.
        from code.army import Army
        from code.units import UNIT_CATALOG
        a = Army("Astra Militarum")
        a.add_squad(UNIT_CATALOG["astra_militarum_cadian_shock_troops"], 10)
        a.add_squad(UNIT_CATALOG["astra_militarum_cadian_command_squad"], 5)
        a.add_unit(UNIT_CATALOG["astra_militarum_cadian_castellan"])
        return a

    def _castellan(self, army):
        return next(u for u in army.units
                    if u.profile.name == "Cadian Castellan")

    def _command_hosts(self, army):
        return [u._attach_host_squad_id for u in army.units
                if u.profile.name == "Cadian Command Squad"]

    def test_off_command_squad_hogs_slots_castellan_exposed(self):
        os.environ["SWEG_LEADER_SQUAD_DEDUPE"] = "0"   # force legacy path (default is now ON)
        from code.attachment import bind_leaders
        army = self._army()
        bind_leaders(army)                          # gate forced OFF
        self.assertIsNone(
            self._castellan(army)._attach_host_squad_id,
            "OFF: the real Castellan is crowded out of the host and left exposed")
        bound = [h for h in self._command_hosts(army) if h is not None]
        self.assertEqual(len(bound), 2,
                         "OFF: command-squad models consume both host slots per-model")

    def test_on_dedupe_binds_squad_as_one_and_frees_the_castellan(self):
        os.environ["SWEG_LEADER_SQUAD_DEDUPE"] = "1"
        from code.attachment import bind_leaders
        army = self._army()
        bind_leaders(army)                          # gate ON
        hosts = self._command_hosts(army)
        self.assertIsNotNone(hosts[0], "ON: the command squad should bind")
        self.assertEqual(len(set(hosts)), 1,
                         "ON: all command-squad models share ONE host (one leader)")
        self.assertIsNotNone(
            self._castellan(army)._attach_host_squad_id,
            "ON: freeing the hogged slot lets the real Castellan bind (protected)")


if __name__ == "__main__":
    unittest.main()
