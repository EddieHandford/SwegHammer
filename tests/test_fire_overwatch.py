"""Fire Overwatch — 10e universal core stratagem (env-gated SWEG_OVERWATCH).

The simulator did not model Fire Overwatch: the universal core stratagem that
lets a unit shoot out of sequence (in the opponent's Movement / Charge phase) at
a charging or arriving enemy, hitting only on UNMODIFIED Hit rolls of 6. Its
absence under-penalised melee / aggression versus gunlines — a charger or a
deep-striking unit never paid a price for closing on a shooting army.

This layer, env-gated ON, lets the defending army spend 1 Command Point to fire
one eligible unit (within 24", line of sight, able to do meaningful damage on
6s) at the charger / arriving unit, with every ranged attack hitting only on an
unmodified 6. Restriction: once per battle round per army. Gate unset reproduces
the baseline byte-for-byte (no Command Point spent, no extra random draws).

Cited as `simulator.fire_overwatch` (data/rule_citations.d/core_overwatch.json).
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


# --------------------------------------------------------------------------- #
# Profiles                                                                     #
# --------------------------------------------------------------------------- #


def _gunline(name: str = "Gunline", attacks: int = 12) -> UnitProfile:
    """A shooty unit with a real anti-infantry gun (Ballistic Skill 3+, i.e.
    hit_probability 2/3 in a normal Shooting phase) and high shot volume so the
    overwatch hit-rate assertion has a large sample. High Strength + AP so the
    wound / save legs pass reliably — the variable under test is the HIT leg."""
    return UnitProfile(
        name=name,
        health=8.0,
        damage=1.0,
        hit_probability=2 / 3,        # Ballistic Skill 3+ in a normal phase
        ap=-4,                        # strip the target's save so damage ~= hits
        save=3,
        strength=10,
        toughness=4,
        attacks=attacks,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _charger(name: str = "Charger", health: float = 40.0) -> UnitProfile:
    """A melee bruiser that charges the gunline. Toughness 4, no invulnerable, a
    poor save (so overwatch hits land), and lots of health (so a single
    overwatch volley does not wipe it — keeps the charge resolution downstream
    well-defined). Strength 10 vs Toughness 4 means the gunline wounds on 2+."""
    return UnitProfile(
        name=name,
        health=health,
        damage=4.0,
        hit_probability=2 / 3,
        ap=0,
        save=6,
        strength=8,
        toughness=4,
        attacks=0,                    # melee-only bruiser, no ranged shots
        range_inches=1,
        unit_keywords=("INFANTRY",),
        melee_attacks=6,
        melee_hit_probability=2 / 3,
        melee_strength=8,
        melee_damage_per_shot=2.0,
    )


def _knight_brick(name: str = "Knight Paladin") -> UnitProfile:
    """A durable charger the gunline's anti-infantry guns cannot meaningfully
    hurt even on 6s (Toughness 11, 2+ save, 5+ invulnerable). Used for the
    'no wasted Command Point' case."""
    return UnitProfile(
        name=name,
        health=26.0,
        damage=6.0,
        hit_probability=2 / 3,
        ap=-3,
        save=2,
        strength=12,
        toughness=11,
        invuln_save=5,
        attacks=0,
        range_inches=1,
        unit_keywords=("VEHICLE", "TITANIC"),
        melee_attacks=6,
        melee_hit_probability=2 / 3,
        melee_strength=14,
        melee_damage_per_shot=6.0,
    )


# --------------------------------------------------------------------------- #
# Scenario builder                                                            #
# --------------------------------------------------------------------------- #


def _build(defender_profiles, charger_profiles, cp: int = 3):
    """Build a Battle on a clean (terrain-free, objective-free) Map. The
    `defender_profiles` army owns the gunline that may overwatch; the
    `charger_profiles` army owns the charger / arriving unit. Returns
    (battle, defenders, chargers). Units are placed ~10" apart — inside 24"
    overwatch range, with clear line of sight."""
    army_def = Army("Defenders")
    for p in defender_profiles:
        army_def.add_unit(p)
    army_def.command_points = cp
    army_atk = Army("Attackers")
    for p in charger_profiles:
        army_atk.add_unit(p)
    battle = Battle(army_def, army_atk, map_=Map("Test", 60.0, 44.0))
    battle._assign_uids()
    battle._current_round = 2
    defenders = list(battle.a.units)
    chargers = list(battle.b.units)
    for i, d in enumerate(defenders):
        d.position = (float(i) * 2.0, 0.0)
    for j, c in enumerate(chargers):
        c.position = (float(j) * 2.0, 10.0)
    battle._advanced_this_round = set()
    battle._overwatched_this_round = set()
    return battle, defenders, chargers


# --------------------------------------------------------------------------- #
# The unmodified-6 hit gate (Unit.attack overwatch path)                      #
# --------------------------------------------------------------------------- #


class OverwatchHitGateTests(unittest.TestCase):
    """The core mechanic: an overwatch ranged attack only hits on an unmodified
    6, irrespective of the model's Ballistic Skill — far below its normal hit
    rate."""

    def test_overwatch_hits_only_on_sixes(self):
        """A Ballistic Skill 3+ gun (normal hit rate 2/3) firing overwatch lands
        ~1/6 of its shots as hits. With Strength 10 vs Toughness 4 (wound 2+) and
        AP-4 vs a 6+ save (save auto-fails), damage ~= hits, so the realised
        damage fraction approximates the 1/6 hit rate."""
        random.seed(20260602)
        shooter_p = _gunline(attacks=1)
        target_p = _charger(health=1.0e9)   # effectively unkillable, big sample
        shooter = Unit(shooter_p)
        target = Unit(target_p)
        shooter.position = (0.0, 0.0)
        target.position = (0.0, 10.0)
        trials = 20000
        total_dmg = 0.0
        for _ in range(trials):
            total_dmg += shooter.attack(
                target, distance=10.0, has_los=True, overwatch=True,
            )
        hit_frac = total_dmg / trials
        # 1/6 ~= 0.167; allow generous tolerance for the wound (~5/6 on 2+) and
        # the (auto-fail) save leg. The point is it is FAR below the 2/3 normal
        # hit rate.
        self.assertLess(hit_frac, 0.30, "overwatch must hit far below normal BS")
        self.assertGreater(hit_frac, 0.07, "overwatch on a 6 must still land some")

    def test_normal_shot_hits_far_more_than_overwatch(self):
        """Sanity: the SAME gun firing normally (no overwatch) lands far more
        than its overwatch rate — confirming the gate is what suppresses hits,
        not the profile."""
        random.seed(20260602)
        shooter = Unit(_gunline(attacks=1))
        target = Unit(_charger(health=1.0e9))
        shooter.position = (0.0, 0.0)
        target.position = (0.0, 10.0)
        trials = 20000
        normal = sum(
            shooter.attack(target, distance=10.0, has_los=True)
            for _ in range(trials)
        ) / trials
        overwatch = sum(
            shooter.attack(target, distance=10.0, has_los=True, overwatch=True)
            for _ in range(trials)
        ) / trials
        self.assertGreater(normal, 2.0 * overwatch,
                           "normal fire must out-hit overwatch by a wide margin")


# --------------------------------------------------------------------------- #
# The stratagem trigger on a declared charge                                   #
# --------------------------------------------------------------------------- #


class OverwatchChargeTriggerTests(unittest.TestCase):
    """Overwatch fires when a charge is declared within 24" of a gunline that
    has the Command Points and the gate ON."""

    def setUp(self):
        self._saved = os.environ.get("SWEG_OVERWATCH")
        os.environ["SWEG_OVERWATCH"] = "1"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("SWEG_OVERWATCH", None)
        else:
            os.environ["SWEG_OVERWATCH"] = self._saved

    def test_charge_declaration_triggers_overwatch_and_damages_charger(self):
        """Gate ON: a charger declaring a charge into the gunline takes overwatch
        damage, the army spends 1 Command Point, and the once-per-round flag is
        set. Averaged over several volleys so a single unlucky 0-hit roll (a
        ~11% event for 12 shots at 1/6) does not flake the 'deals damage' leg —
        the per-volley Command-Point spend and the once-per-round flag are
        asserted exactly on the first volley."""
        random.seed(7)
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_charger(health=1.0e9)], cp=3,
        )
        charger = chargers[0]

        # First volley: exact Command-Point spend + once-per-round flag.
        cp_before = battle.a.command_points
        hp0 = charger.current_health
        battle._fire_overwatch(battle.a, charger)
        self.assertEqual(battle.a.command_points, cp_before - 1,
                         "overwatch must cost exactly 1 Command Point")
        self.assertIn(battle.a.name, battle._overwatched_this_round)

        # Over many volleys (resetting the per-round flag + topping up CP each
        # time) the charger reliably takes SOME overwatch damage.
        total = hp0 - charger.current_health
        for _ in range(12):
            battle._overwatched_this_round.discard(battle.a.name)
            battle.a.command_points = 3
            before = charger.current_health
            battle._fire_overwatch(battle.a, charger)
            total += before - charger.current_health
        self.assertGreater(total, 0.0,
                           "overwatch must inflict damage on the charger over volleys")

    def test_overwatch_hit_rate_via_trigger_is_low(self):
        """Fired through the trigger, the realised damage is consistent with a
        ~1/6 hit rate (far below the gunline's 12 * 2/3 = 8 expected hits a
        normal phase would land). We bound it loosely to stay robust to seed."""
        random.seed(11)
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_charger(health=1.0e9)], cp=3,
        )
        charger = chargers[0]
        battle._fire_overwatch(battle.a, charger)
        dealt = 1.0e9 - charger.current_health
        # 12 shots * 1/6 hit * ~5/6 wound * 1 dmg ~= 1.7 expected; a normal phase
        # would be ~6.7. Assert it is comfortably in the overwatch regime.
        self.assertLess(dealt, 5.0, "overwatch volley must be far below a normal volley")


# --------------------------------------------------------------------------- #
# Command-Point economy + once-per-round + no-wasted-fire gates               #
# --------------------------------------------------------------------------- #


class OverwatchEconomyTests(unittest.TestCase):
    """Command-Point spend, the once-per-round cap, and the no-wasted-fire gate."""

    def setUp(self):
        self._saved = os.environ.get("SWEG_OVERWATCH")
        os.environ["SWEG_OVERWATCH"] = "1"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("SWEG_OVERWATCH", None)
        else:
            os.environ["SWEG_OVERWATCH"] = self._saved

    def test_zero_command_points_cannot_overwatch(self):
        """An army with 0 Command Points does not overwatch: no damage, and the
        Command Point pool never goes negative."""
        random.seed(7)
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_charger()], cp=0,
        )
        charger = chargers[0]
        hp_before = charger.current_health
        battle._fire_overwatch(battle.a, charger)
        self.assertEqual(charger.current_health, hp_before, "no damage with 0 CP")
        self.assertEqual(battle.a.command_points, 0, "Command Points stay at 0")
        self.assertNotIn(battle.a.name, battle._overwatched_this_round)

    def test_overwatch_at_most_once_per_round(self):
        """A second overwatch trigger in the same round does nothing — no second
        Command Point spent, no further damage."""
        random.seed(7)
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_charger()], cp=3,
        )
        charger = chargers[0]
        battle._fire_overwatch(battle.a, charger)
        cp_after_first = battle.a.command_points
        hp_after_first = charger.current_health
        # Second trigger this round.
        battle._fire_overwatch(battle.a, charger)
        self.assertEqual(battle.a.command_points, cp_after_first,
                         "second overwatch this round must not spend CP")
        self.assertEqual(charger.current_health, hp_after_first,
                         "second overwatch this round must deal no damage")

    def test_no_overwatch_when_cannot_meaningfully_damage(self):
        """A defender whose guns cannot meaningfully hurt the charger on 6s (an
        anti-infantry gunline into a Toughness-11, 2+/5++ Knight) does NOT
        overwatch — the Command Point is held, not wasted."""
        random.seed(7)
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_knight_brick()], cp=3,
        )
        brick = chargers[0]
        hp_before = brick.current_health
        cp_before = battle.a.command_points
        battle._fire_overwatch(battle.a, brick)
        self.assertEqual(brick.current_health, hp_before, "brick takes no overwatch")
        self.assertEqual(battle.a.command_points, cp_before, "no Command Point wasted")
        self.assertNotIn(battle.a.name, battle._overwatched_this_round)

    def test_out_of_range_defender_does_not_overwatch(self):
        """A gunline more than 24" from the charger cannot overwatch it (no
        damage, no Command Point spent)."""
        random.seed(7)
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_charger()], cp=3,
        )
        charger = chargers[0]
        defenders[0].position = (0.0, 0.0)
        charger.position = (0.0, 30.0)   # 30" away, beyond the 24" overwatch range
        hp_before = charger.current_health
        cp_before = battle.a.command_points
        battle._fire_overwatch(battle.a, charger)
        self.assertEqual(charger.current_health, hp_before)
        self.assertEqual(battle.a.command_points, cp_before)


# --------------------------------------------------------------------------- #
# The env gate: OFF reproduces the baseline                                   #
# --------------------------------------------------------------------------- #


class OverwatchGateOffTests(unittest.TestCase):
    """Gate unset: no overwatch ever occurs, so a charge resolves exactly as it
    does today and no Command Point is spent."""

    def setUp(self):
        self._saved = os.environ.get("SWEG_OVERWATCH")
        os.environ.pop("SWEG_OVERWATCH", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("SWEG_OVERWATCH", None)
        else:
            os.environ["SWEG_OVERWATCH"] = self._saved

    def test_gate_off_no_overwatch_no_cp_spent(self):
        """Gate unset: _fire_overwatch is a no-op — the charger is untouched, no
        Command Point is spent, no random draws are consumed."""
        battle, defenders, chargers = _build(
            [_gunline(attacks=12)], [_charger()], cp=3,
        )
        charger = chargers[0]
        hp_before = charger.current_health
        cp_before = battle.a.command_points
        rng_state = random.getstate()
        battle._fire_overwatch(battle.a, charger)
        self.assertEqual(charger.current_health, hp_before, "no damage when gate off")
        self.assertEqual(battle.a.command_points, cp_before, "no CP spent when gate off")
        self.assertEqual(random.getstate(), rng_state,
                         "gate off must consume no random draws")
        self.assertNotIn(battle.a.name, battle._overwatched_this_round)

    def test_gate_off_charge_declaration_is_byte_identical(self):
        """Gate unset: running _do_charge with a declared charge consumes the
        same random draws as it would with no overwatch code at all (the
        overwatch call is a no-op before the charge roll). We assert the random
        state after _do_charge matches a run where _fire_overwatch is stubbed to
        a pure no-op — i.e. the OFF overwatch hook adds zero draws."""
        # Reference run: stub _fire_overwatch to an explicit no-op.
        battle_ref, def_ref, atk_ref = _build(
            [_gunline(attacks=4)], [_charger()], cp=3,
        )
        # Give the charger a melee profile and make it WANT to charge.
        random.seed(99)
        state0 = random.getstate()
        orig = Battle._fire_overwatch
        try:
            Battle._fire_overwatch = lambda self, a, e: None
            battle_ref._do_charge(atk_ref[0], battle_ref.b, battle_ref.a)
        finally:
            Battle._fire_overwatch = orig
        ref_state = random.getstate()
        ref_cp = battle_ref.b.command_points

        # Live run with the real (gate-OFF) _fire_overwatch.
        battle_live, def_live, atk_live = _build(
            [_gunline(attacks=4)], [_charger()], cp=3,
        )
        random.setstate(state0)
        battle_live._do_charge(atk_live[0], battle_live.b, battle_live.a)
        live_state = random.getstate()
        live_cp = battle_live.b.command_points

        self.assertEqual(live_state, ref_state,
                         "gate-off charge must consume identical random draws")
        self.assertEqual(live_cp, ref_cp,
                         "gate-off charge must spend no extra Command Points")


if __name__ == "__main__":
    unittest.main()
