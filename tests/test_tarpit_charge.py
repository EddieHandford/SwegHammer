"""Tests for the general tarpit-charge valuation (anti-Knight stack component 2).

`SWEG_TARPIT` (default OFF). Inside the charge planner's won't-crack branch, an
EXPENDABLE (chaff) attacker pinning a DURABLE target is valued by the enemy
ranged output it DENIES (Big Guns Never Tire) rather than suppressed. Even-handed
(universal points + toughness; no faction branch). AI heuristic on the
already-faithful pin mechanic — no new citation.

The `_is_tarpit_charge` gate is the testable core; its behavioural effect on
`pick_charge_target` is validated by the env-gated N=40 A/B. The helper reads a
small, fixed set of fields, so lightweight stand-ins exercise every gate.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

from code.strategy import _is_tarpit_charge, _tarpit_enabled


def _attacker(pts=4.0, keywords=("INFANTRY",)):
    return SimpleNamespace(
        profile=SimpleNamespace(points_cost=pts, unit_keywords=keywords)
    )


def _target(toughness=12, health=22.0):
    return SimpleNamespace(current_health=health), SimpleNamespace(toughness=toughness)


class TarpitGateEnvTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("SWEG_TARPIT", None)

    def tearDown(self):
        os.environ.pop("SWEG_TARPIT", None)

    def test_gate_default_off(self):
        self.assertFalse(_tarpit_enabled())

    def test_gate_on(self):
        os.environ["SWEG_TARPIT"] = "1"
        self.assertTrue(_tarpit_enabled())


class IsTarpitChargeTests(unittest.TestCase):
    def test_chaff_vs_durable_toughness_is_tarpit(self):
        unit, prof = _target(toughness=12, health=22.0)
        self.assertTrue(_is_tarpit_charge(_attacker(pts=4.0), unit, prof))

    def test_chaff_vs_high_hp_low_toughness_is_tarpit(self):
        # A big wound pool counts as durable even at modest toughness.
        unit, prof = _target(toughness=7, health=20.0)
        self.assertTrue(_is_tarpit_charge(_attacker(pts=4.0), unit, prof))

    def test_chaff_vs_soft_not_tarpit(self):
        unit, prof = _target(toughness=3, health=1.0)
        self.assertFalse(
            _is_tarpit_charge(_attacker(pts=6.0), unit, prof),
            "A soft, low-wound target is not a durable brick — not a tarpit.",
        )

    def test_expensive_attacker_not_tarpit(self):
        unit, prof = _target(toughness=12, health=22.0)
        self.assertFalse(
            _is_tarpit_charge(_attacker(pts=40.0), unit, prof),
            "Only EXPENDABLE (chaff) attackers tarpit — you don't throw a "
            "40-point model away to pin a Knight.",
        )

    def test_character_chaff_not_tarpit(self):
        unit, prof = _target(toughness=12, health=22.0)
        self.assertFalse(
            _is_tarpit_charge(
                _attacker(pts=10.0, keywords=("CHARACTER",)), unit, prof
            ),
            "A cheap CHARACTER is excluded from the chaff/expendable set.",
        )

    def test_zero_points_attacker_not_tarpit(self):
        # points_cost 0 means 'unknown' to _is_chaff_unit — not treated as chaff.
        unit, prof = _target(toughness=12, health=22.0)
        self.assertFalse(_is_tarpit_charge(_attacker(pts=0.0), unit, prof))


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
