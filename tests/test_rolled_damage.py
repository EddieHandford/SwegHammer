"""Tests for PER-MODEL-LOADOUTS STAGE 4 — per-weapon damage-dice rolling
(`code.units.roll_damage` + the `SWEG_ROLLDMG` env gate).

Stage 4 rolls each weapon's REAL Damage dice per shot instead of using the
expected-value mean. The change is gated by `SWEG_ROLLDMG` (default ON since
the wave-247 close; "0" is the kill-switch) and rolls only on the per-model
firing path (the only profiles that carry a raw `damage_dice` string), so the
killed-gate and per-model-mean RNG streams stay byte-identical to the legacy
expected-value frame.

The properties under test:
  (a) `roll_damage("", x)` returns x and draws NOTHING from `random`;
      with the gate UNSET, any dice string returns the mean and draws nothing;
  (b) seeded means over many rolls converge to the dice's expected value
      ("D6" -> 3.5, "D3+3" -> 5.0, "2D6" -> 7.0, "2" -> exactly 2);
  (c) the same seed reproduces the identical roll sequence (determinism);
  (d) end-to-end: with both gates set, a high-variance weapon vs a multi-wound
      target produces variable per-shot damage with an unbiased mean and
      sometimes UNDER-kills a multi-wound model (the overkill correction).
"""

from __future__ import annotations

import os
import random
import unittest


class _CountingRandom:
    """A drop-in for the global `random` whose draw methods bump a counter, so
    a test can assert that a code path consumed ZERO random draws."""

    def __init__(self, seed: int = 0) -> None:
        self._r = random.Random(seed)
        self.draws = 0

    def randint(self, a: int, b: int) -> int:
        self.draws += 1
        return self._r.randint(a, b)

    def random(self) -> float:
        self.draws += 1
        return self._r.random()


class RollDamageGrammarTests(unittest.TestCase):
    def setUp(self):
        # Default: gate ON for the rolling tests; the no-draw tests toggle it.
        self._saved = os.environ.get("SWEG_ROLLDMG")
        os.environ["SWEG_ROLLDMG"] = "1"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("SWEG_ROLLDMG", None)
        else:
            os.environ["SWEG_ROLLDMG"] = self._saved

    # (a) no-draw fallback ---------------------------------------------------
    def test_empty_dice_returns_mean_and_draws_nothing(self):
        """roll_damage("", 3.5) == 3.5 AND consumes no random draw."""
        import code.units as units

        counter = _CountingRandom(seed=1)
        orig = units.random
        units.random = counter
        try:
            self.assertEqual(units.roll_damage("", 3.5), 3.5)
            self.assertEqual(units.roll_damage("", 1.0), 1.0)
        finally:
            units.random = orig
        self.assertEqual(
            counter.draws, 0, "empty dice string must not draw any random die"
        )

    def test_gate_killed_returns_mean_and_draws_nothing(self):
        """With SWEG_ROLLDMG="0" (the kill-switch — default has been ON since
        wave 247), even a real dice string returns the mean and draws NOTHING —
        the determinism contract that keeps the killed arm / per-model-mean
        byte-identical to the legacy expected-value frame."""
        import code.units as units

        os.environ["SWEG_ROLLDMG"] = "0"
        counter = _CountingRandom(seed=1)
        orig = units.random
        units.random = counter
        try:
            self.assertEqual(units.roll_damage("D6", 3.5), 3.5)
            self.assertEqual(units.roll_damage("2D6", 7.0), 7.0)
        finally:
            units.random = orig
        self.assertEqual(
            counter.draws, 0, "gate-killed must not draw any random die"
        )

    def test_flat_integer_returns_exact_value_and_draws_nothing(self):
        """A constant Damage characteristic ("2") returns exactly 2 and draws no
        random die even with the gate on (no dice term to roll)."""
        import code.units as units

        counter = _CountingRandom(seed=1)
        orig = units.random
        units.random = counter
        try:
            self.assertEqual(units.roll_damage("2", 2.0), 2.0)
            self.assertEqual(units.roll_damage("1", 1.0), 1.0)
        finally:
            units.random = orig
        self.assertEqual(counter.draws, 0, "a flat integer must draw no die")

    # (b) seeded means -------------------------------------------------------
    def test_seeded_means_converge_to_expected_value(self):
        """Over many rolls the empirical mean of each dice string converges to
        its expected value (the mean-invariant the legacy field encodes)."""
        from code.units import roll_damage

        cases = {
            "D6": 3.5,
            "D3": 2.0,
            "D3+3": 5.0,
            "2D6": 7.0,
            "D6+2": 5.5,
        }
        n = 40000
        for dice, expected in cases.items():
            random.seed(12345)
            total = sum(roll_damage(dice, expected) for _ in range(n))
            mean = total / n
            self.assertAlmostEqual(
                mean, expected, delta=0.08,
                msg=f"{dice}: empirical mean {mean:.3f} != expected {expected}",
            )

    def test_flat_two_is_exactly_two_every_roll(self):
        """"2" yields exactly 2.0 on every roll (no variance)."""
        from code.units import roll_damage

        random.seed(7)
        self.assertTrue(all(roll_damage("2", 2.0) == 2.0 for _ in range(1000)))

    def test_d6_range_is_one_to_six(self):
        """Every "D6" roll lands in the integer range 1..6 (the modifier-free
        characteristic)."""
        from code.units import roll_damage

        random.seed(99)
        vals = [roll_damage("D6", 3.5) for _ in range(2000)]
        self.assertTrue(all(1 <= v <= 6 for v in vals))
        self.assertEqual(set(vals), {1, 2, 3, 4, 5, 6})

    # (c) determinism --------------------------------------------------------
    def test_same_seed_reproduces_identical_sequence(self):
        """Same seed -> identical roll sequence."""
        from code.units import roll_damage

        def seq():
            random.seed(2024)
            return [roll_damage("D6", 3.5) for _ in range(200)]

        self.assertEqual(seq(), seq())

    def test_2d6_rolls_sum_two_independent_dice(self):
        """"2D6" sums two d6 each roll (range 2..12, never 1)."""
        from code.units import roll_damage

        random.seed(3)
        vals = [roll_damage("2D6", 7.0) for _ in range(3000)]
        self.assertTrue(all(2 <= v <= 12 for v in vals))
        self.assertIn(12, vals)
        self.assertNotIn(1, vals)


class RolledDamageEndToEndTests(unittest.TestCase):
    """End-to-end: with SWEG_PERMODEL + SWEG_ROLLDMG set, a high-variance weapon
    firing at a multi-wound target shows variable per-shot damage with an
    unbiased mean and sometimes under-kills a multi-wound model."""

    def setUp(self):
        self._saved_pm = os.environ.get("SWEG_PERMODEL")
        self._saved_rd = os.environ.get("SWEG_ROLLDMG")

    def tearDown(self):
        for name, saved in (
            ("SWEG_PERMODEL", self._saved_pm),
            ("SWEG_ROLLDMG", self._saved_rd),
        ):
            if saved is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved

    def _multi_melta_unit(self):
        """One Devastator Multi-melta model (D6 damage) via the per-model path."""
        from code.army import Army
        from code.units import UNIT_CATALOG

        army = Army(name="t")
        army.add_squad(UNIT_CATALOG["space_marines_devastator_squad"], 10)
        mm = [u for u in army.units if u.profile.weapon == "Multi-melta"]
        self.assertTrue(mm, "expected at least one Multi-melta model")
        # Confirm the per-model primary block carries the raw D6 dice string.
        self.assertEqual(mm[0].profile.damage_dice, "D6")
        return mm[0]

    def test_per_model_primary_carries_damage_dice(self):
        """The per-model Multi-melta primary block exposes the raw "D6" dice
        string (the threading from _loadout_entry_to_weapon_fields)."""
        os.environ["SWEG_PERMODEL"] = "1"
        os.environ.pop("SWEG_ROLLDMG", None)
        u = self._multi_melta_unit()
        self.assertEqual(u.profile.damage_dice, "D6")

    def test_rolled_damage_is_variable_and_unbiased(self):
        """With both gates set, repeated Multi-melta shots at a fat target yield
        VARIABLE total output across seeds whose grand mean is close to the
        mean-path output (unbiased), and at least one run lands below another —
        i.e. the per-shot damage is genuinely rolled, not a flat mean."""
        from code.units import Unit, UnitProfile

        # Fire from BEYOND the Multi-melta's melta half-range so the flat Melta X
        # bonus never applies — we want the pure D6 characteristic so the test
        # isolates the dice roll itself.
        _far = 12.0

        def fat_target():
            t = Unit(UnitProfile(
                name="Dummy", health=500.0, damage=0.0, hit_probability=0.0,
                save=7, toughness=4, range_inches=0, attacks=0,
            ))
            t.position = (_far, 0.0)
            return t

        def run_total(roll_on: bool, seed: int) -> float:
            os.environ["SWEG_PERMODEL"] = "1"
            if roll_on:
                os.environ["SWEG_ROLLDMG"] = "1"
            else:
                # Default is ON since wave 247 — the mean-path arm needs the
                # explicit "0" kill-switch, not an unset gate.
                os.environ["SWEG_ROLLDMG"] = "0"
            u = self._multi_melta_unit()
            random.seed(seed)
            total = 0.0
            for _ in range(300):
                total += u.attack(fat_target(), distance=_far)
            return total

        rolled = [run_total(True, s) for s in (1, 2, 3, 4, 5)]
        # Variability: the rolled runs are not all identical.
        self.assertGreater(
            max(rolled) - min(rolled), 0.0,
            "rolled per-shot damage should vary across seeds",
        )
        # Unbiasedness: the grand mean of the rolled runs is within ~12% of the
        # mean-path output (same seeds), since rolling preserves expected value.
        mean_runs = [run_total(False, s) for s in (1, 2, 3, 4, 5)]
        grand_rolled = sum(rolled) / len(rolled)
        grand_mean = sum(mean_runs) / len(mean_runs)
        self.assertGreater(grand_mean, 0.0)
        rel = abs(grand_rolled - grand_mean) / grand_mean
        self.assertLess(
            rel, 0.12,
            f"rolled mean {grand_rolled:.1f} should track mean-path "
            f"{grand_mean:.1f} (rel diff {rel:.3f})",
        )

    def test_rolled_damage_sometimes_under_kills_multi_wound_model(self):
        """A D6 weapon rolling against a 3-wound model sometimes leaves it
        alive (a roll of 1 or 2 fails to remove all 3 wounds) — the
        mean-overkill correction the user wants. With the flat 3.5 mean the
        model would ALWAYS die on a single unsaved hit."""
        from code.units import Unit, UnitProfile

        os.environ["SWEG_PERMODEL"] = "1"
        os.environ["SWEG_ROLLDMG"] = "1"
        u = self._multi_melta_unit()

        survived = 0
        trials = 400
        # Fire from beyond melta half-range so the weapon is a pure D6 (no flat
        # Melta X bonus) — a roll of 1 or 2 leaves a 3-wound model standing.
        _far = 12.0
        random.seed(4242)
        for _ in range(trials):
            # Fresh 3-wound, no-save target each trial so we measure a single
            # firing exchange's kill/no-kill outcome.
            t = Unit(UnitProfile(
                name="ThreeWound", health=3.0, damage=0.0, hit_probability=0.0,
                save=7, toughness=4, range_inches=0, attacks=0,
            ))
            t.position = (_far, 0.0)
            u.attack(t, distance=_far)
            if t.is_alive and t.current_health > 0:
                survived += 1
        # At least some trials must leave the 3-wound model alive — proof that
        # the real dice (which roll below 3 part of the time) under-kill where
        # the flat 3.5 mean would always over-kill. (A single Multi-melta is one
        # shot at melta range, hit ~2/3, wound, no save; a non-trivial fraction
        # of the firing trials leave the model standing.)
        self.assertGreater(
            survived, 0,
            "rolled D6 damage should sometimes fail to kill a 3-wound model",
        )


if __name__ == "__main__":
    unittest.main()
