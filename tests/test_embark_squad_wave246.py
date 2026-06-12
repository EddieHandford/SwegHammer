"""Wave 246 — squad-level pre-game embark (SWEG_EMBARK_SQUAD gate) tests.

These tests verify the SWEG_EMBARK_SQUAD gate added in wave 246:

  (a) Gate-off inertness — with the gate unset or set to "0", a transport
      army embarks exactly one Unit instance (the original single-instance
      behaviour); the rest of the squad remains unboarded.

  (b) Gate-on squad embark — when the gate is "1", every member of the
      highest-score squad embarks.  The passenger count equals the squad
      size (all members of the elected squad are on board, not just the top
      scorer).

  (c) No-split rule — a squad that is larger than the transport's remaining
      capacity is skipped in favour of a smaller squad that fits.  The
      transport is never partially loaded with half a squad.

  (d) Forced disembark on transport death releases all passengers — this
      exercises the multi-passenger destroyed-transport path and confirms
      that all squad members are placed outside the transport and cleared
      from its passengers list after the carrier is destroyed.

All tests use small synthetic UnitProfile fixtures so they run without any
dependency on the BSData catalogue or evaluate_vs_meta.
Cited as `simulator.embark`.
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.events import EventLog
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _transport_profile(name: str = "Rhino") -> UnitProfile:
    """Minimal VEHICLE + TRANSPORT profile, capacity 12."""
    return UnitProfile(
        name=name, faction="Adeptus Astartes",
        health=10, damage=1, hit_probability=0.5,
        ap=0, save=3, strength=5, toughness=9,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        move=12.0, unit_keywords=("VEHICLE", "TRANSPORT"),
    )


def _infantry_profile(name: str = "Trooper", score: float = 1.0) -> UnitProfile:
    """Minimal INFANTRY profile.  The `score` field is stored directly on
    the profile via a keyword argument so we can simulate high-value and
    low-value squads without needing full weapon stats.

    UnitProfile.score is a computed property; we cannot override it via
    dataclass init.  Instead we pass a `damage` value proportional to the
    desired Lanchester score — the score property formula in this codebase
    is approximately `attacks * damage * hit_probability / toughness`, so
    scaling damage scales score monotonically for identical other fields.
    """
    return UnitProfile(
        name=name, faction="Adeptus Astartes",
        health=1, damage=score, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=float(score), range_inches=24,
        move=6.0, unit_keywords=("INFANTRY",),
    )


def _build_battle(army_a_setup, army_b_setup=None):
    """Create a Battle with armies A and B configured by the setup callables.

    Each setup callable receives an Army and may add units to it.  Army B
    defaults to a single inert enemy unit if no setup is provided.
    """
    a = Army("A")
    b = Army("B")
    army_a_setup(a)
    if army_b_setup is not None:
        army_b_setup(b)
    else:
        b.add_unit(_infantry_profile("Enemy"))
    log = EventLog()
    battle = Battle(a, b, subscribers=[log])
    battle._assign_uids()
    # Place everyone in the centre so range/engagement checks don't interfere.
    for u in a.units + b.units:
        u.position = (20.0, 20.0)
    return battle, a, b, log


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class EmbarkSquadWave246Tests(unittest.TestCase):
    """Wave 246 gate tests for squad-level pre-game embark."""

    # ------------------------------------------------------------------
    # (a) Gate-off inertness
    # ------------------------------------------------------------------

    def test_gate_off_embarks_exactly_one_instance(self):
        """With SWEG_EMBARK_SQUAD unset (defaults to '0'), the original
        single-instance behaviour is preserved: exactly one Unit instance
        ends up in the transport's passengers list, even when the passenger
        unit is a multi-model squad.
        """
        def setup(a):
            a.add_unit(_transport_profile())
            # A 3-model squad all sharing one squad_id.
            a.add_squad(_infantry_profile("Trooper", score=2.0), size=3)

        env_patch = {"SWEG_EMBARK_SQUAD": "0"}
        with unittest.mock.patch.dict(os.environ, env_patch, clear=False):
            battle, a, _b, _log = _build_battle(setup)
            battle._embark_pregame_passengers()

        transport = a.units[0]
        self.assertEqual(
            len(transport.passengers), 1,
            "Gate OFF: transport should have exactly one passenger (one instance).",
        )
        # The remaining squad members must still be unboarded.
        unboarded = [
            u for u in a.units
            if u is not transport and u.embarked_in is None
        ]
        self.assertEqual(
            len(unboarded), 2,
            "Gate OFF: two squad members should remain unboarded.",
        )

    def test_gate_off_when_env_unset(self):
        """When SWEG_EMBARK_SQUAD is not set in the environment at all, the
        gate behaves identically to gate=0 (single-instance election).
        """
        def setup(a):
            a.add_unit(_transport_profile())
            a.add_squad(_infantry_profile("Trooper", score=2.0), size=4)

        # Remove the key entirely if present.
        env_without_key = {k: v for k, v in os.environ.items()
                           if k != "SWEG_EMBARK_SQUAD"}
        with unittest.mock.patch.dict(os.environ, env_without_key, clear=True):
            battle, a, _b, _log = _build_battle(setup)
            battle._embark_pregame_passengers()

        transport = a.units[0]
        self.assertEqual(
            len(transport.passengers), 1,
            "Gate absent: transport should have exactly one passenger (gate-off path).",
        )

    # ------------------------------------------------------------------
    # (b) Gate-on: whole squad embarks
    # ------------------------------------------------------------------

    def test_gate_on_whole_squad_embarks(self):
        """With SWEG_EMBARK_SQUAD=1, the entire highest-score squad embarks
        in one go.  The passenger count must equal the squad size (all
        members of the elected squad are in the transport's passengers list).
        """
        squad_size = 5

        def setup(a):
            a.add_unit(_transport_profile())
            # One squad of size 5, all sharing one squad_id.
            a.add_squad(_infantry_profile("Trooper", score=3.0), size=squad_size)

        with unittest.mock.patch.dict(os.environ, {"SWEG_EMBARK_SQUAD": "1"}, clear=False):
            battle, a, _b, _log = _build_battle(setup)
            battle._embark_pregame_passengers()

        transport = a.units[0]
        self.assertEqual(
            len(transport.passengers), squad_size,
            f"Gate ON: all {squad_size} squad members must be in passengers.",
        )
        # Every passenger must have is_embarked True and embarked_in = transport.
        for p in transport.passengers:
            self.assertTrue(p.is_embarked)
            self.assertIs(p.embarked_in, transport)

    def test_gate_on_elects_highest_score_squad(self):
        """When there are two squads, gate-on must elect the one with the
        higher summed profile.score, not a lower-score alternative.
        """
        def setup(a):
            a.add_unit(_transport_profile())
            # Low-score squad (2 members, score ~0.5 each → summed ~1.0).
            a.add_squad(_infantry_profile("Low", score=0.5), size=2)
            # High-score squad (2 members, score ~3.0 each → summed ~6.0).
            a.add_squad(_infantry_profile("High", score=3.0), size=2)

        with unittest.mock.patch.dict(os.environ, {"SWEG_EMBARK_SQUAD": "1"}, clear=False):
            battle, a, _b, _log = _build_battle(setup)
            battle._embark_pregame_passengers()

        transport = a.units[0]
        # Both squads are size 2 and fit easily; the High squad must win.
        self.assertEqual(len(transport.passengers), 2)
        for p in transport.passengers:
            self.assertEqual(
                p.profile.name, "High",
                "Gate ON must elect the squad with the higher summed score.",
            )

    # ------------------------------------------------------------------
    # (c) No-split: oversized squad is skipped
    # ------------------------------------------------------------------

    def test_no_split_oversized_squad_skipped(self):
        """A squad whose size exceeds the transport's remaining capacity
        must be skipped.  The next-best squad that fits is elected instead.

        Here: transport capacity is 12.  A 10-member squad would fit the
        full capacity if it were alone.  But we pre-fill 10 passenger slots
        manually, leaving remaining = 2.  The 10-member squad cannot fit
        (10 > 2) so it must be skipped; a 2-member squad must be elected.
        """
        def setup(a):
            a.add_unit(_transport_profile())
            # Filler squad — 10 members (score 1.0 each, summed 10.0).
            a.add_squad(_infantry_profile("Big", score=1.0), size=10)
            # Small squad — 2 members (score 0.8 each, summed 1.6).
            a.add_squad(_infantry_profile("Small", score=0.8), size=2)

        with unittest.mock.patch.dict(os.environ, {"SWEG_EMBARK_SQUAD": "1"}, clear=False):
            battle, a, _b, _log = _build_battle(setup)
            transport = a.units[0]
            # Pre-fill 10 slots with dummy passengers so remaining = 2.
            # We do this by adding 10 extra solo infantry units to army A
            # and manually calling _embark for each (not via the pre-game
            # pass — we want precise control).
            dummy_units = []
            for i in range(10):
                u = __import__("code.units", fromlist=["Unit"]).Unit(
                    _infantry_profile(f"Dummy{i}"),
                )
                u.army_ref = a
                # squad_id stays -1 (singleton); must not pass _eligible in the
                # real pass since they won't be in army.units.
                transport.passengers.append(u)
                u.embarked_in = transport
                dummy_units.append(u)
            # Remaining capacity = 12 - 10 = 2.
            self.assertEqual(
                len(transport.passengers), 10,
                "Pre-condition: transport already has 10 passengers.",
            )
            battle._embark_pregame_passengers()

        # The big squad (size 10) must NOT have embarked (would exceed remaining=2).
        big_squad_in_transport = [
            p for p in transport.passengers if p.profile.name == "Big"
        ]
        self.assertEqual(
            len(big_squad_in_transport), 0,
            "The 10-member squad must be skipped — it does not fit in remaining=2.",
        )
        # The small squad (size 2) must have embarked.
        small_squad_in_transport = [
            p for p in transport.passengers if p.profile.name == "Small"
        ]
        self.assertEqual(
            len(small_squad_in_transport), 2,
            "The 2-member squad must have embarked — it fits in remaining=2.",
        )

    # ------------------------------------------------------------------
    # (d) Forced disembark on transport death releases all passengers
    # ------------------------------------------------------------------

    def test_destroyed_transport_releases_all_squad_passengers(self):
        """When the transport is destroyed with multiple passengers aboard
        (a whole squad embarked via gate-on), every passenger must be
        force-disembarked: placed near the transport's last position,
        cleared from its passengers list, and embarked_in set to None.

        We use gate-on to embark the squad, then call
        _maybe_apply_deadly_demise to trigger the forced-disembark path,
        pinning the D6 roll to 6 (no model loss) so the test is strictly
        about the disembark mechanics.
        """
        from unittest import mock
        squad_size = 4

        def setup(a):
            a.add_unit(_transport_profile())
            a.add_squad(_infantry_profile("Rider", score=2.0), size=squad_size)

        with unittest.mock.patch.dict(os.environ, {"SWEG_EMBARK_SQUAD": "1"}, clear=False):
            battle, a, _b, _log = _build_battle(setup)
            battle._embark_pregame_passengers()

        transport = a.units[0]
        last_pos = transport.position

        # Confirm all squad members boarded.
        self.assertEqual(
            len(transport.passengers), squad_size,
            "Pre-condition: all squad members must be aboard before destroying the transport.",
        )

        # Destroy the transport; pin D6 to 6 so no passenger is killed by
        # the destroyed-transport mortal wound roll.
        transport.current_health = 0.0
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(transport)

        # All passengers must now be disembarked.
        self.assertEqual(
            len(transport.passengers), 0,
            "Destroyed transport must have an empty passengers list.",
        )
        # Check each squad member's state.
        riders = [u for u in a.units if u.profile.name == "Rider"]
        self.assertEqual(len(riders), squad_size)
        for rider in riders:
            self.assertFalse(
                rider.is_embarked,
                f"{rider.uid} must not be embarked after forced disembark.",
            )
            self.assertIsNone(rider.embarked_in)
            # Placed within 3" of the transport's last position.
            dx = rider.position[0] - last_pos[0]
            dy = rider.position[1] - last_pos[1]
            dist = (dx * dx + dy * dy) ** 0.5
            self.assertLessEqual(
                dist, 3.0 + 1e-6,
                f"{rider.uid} placed {dist:.2f}\" from transport — exceeds 3\" cap.",
            )


# ---------------------------------------------------------------------------
# Ensure unittest.mock is importable (it is in the stdlib, but make the
# import explicit at module level for IDE clarity).
# ---------------------------------------------------------------------------
import unittest.mock  # noqa: E402  (imported above already via `from unittest import mock`)

if __name__ == "__main__":
    unittest.main()
