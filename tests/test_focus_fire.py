"""Wave 101 — army-level focus fire (env-gated SWEG_FOCUSFIRE).

The simulator's per-unit shooting picker selects the lowest-current-health
enemy (the shooting-side analogue of the charge won't-crack penalty), so every
unit individually avoids a durable brick — a Knight Paladin (Toughness 11, 26
wounds, 5+ invulnerable) that no single unit cracks — and shoots a killable
Armiger / chaff instead. Against such a brick NOTHING coordinates several units'
fire onto it, the inverse of the real counter-Knight focus-fire tactic.

This layer, when env-gated ON, nominates the most dangerous enemy brick the
firing army can crack COLLECTIVELY this phase and points every unit that can
wound it onto it. A brick the army CANNOT collectively crack is never nominated,
so no fire is wasted (the wave-79 SWEG_FOCUS pathology this avoids). Even-handed
for ALL factions versus ANY brick; gate unset reproduces the baseline target
selection byte-for-byte.

Cited as `simulator.focus_fire` (data/rule_citations.d/focus_fire.json).
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


# --------------------------------------------------------------------------- #
# Profiles                                                                     #
# --------------------------------------------------------------------------- #


def _knight_brick(name: str = "Knight Paladin") -> UnitProfile:
    """A durable brick: Toughness 11, 26 wounds, 5+ invulnerable, 2+ save, and a
    real gun (so it reads as a high-THREAT brick worth removing). No single
    anti-tank unit below cracks 0.20 x 26 = 5.2 wounds in one round, so the
    per-unit picker avoids it — but several together CAN finish it."""
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
        attacks=6,
        weapon_damage_per_shot=3.0,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC", "IMPERIAL KNIGHTS"),
        melee_attacks=6,
        melee_hit_probability=2 / 3,
        melee_strength=14,
        melee_damage_per_shot=6.0,
    )


def _big_vehicle_brick(name: str = "Battle Tank") -> UnitProfile:
    """A non-Knight brick (even-handedness): a Toughness 11, 18-wound VEHICLE
    with a heavy gun. Same focus-fire treatment as a Knight."""
    return UnitProfile(
        name=name,
        health=18.0,
        damage=6.0,
        hit_probability=2 / 3,
        ap=-2,
        save=2,
        strength=10,
        toughness=11,
        invuln_save=7,
        attacks=4,
        weapon_damage_per_shot=4.0,
        range_inches=48,
        unit_keywords=("VEHICLE", "MONSTER"),
        melee_attacks=3,
        melee_hit_probability=0.5,
        melee_strength=8,
        melee_damage_per_shot=3.0,
    )


def _antitank(name: str) -> UnitProfile:
    """A dedicated anti-tank shooter — high-Strength, high-AP, multi-damage
    shots with the Anti-VEHICLE keyword. One unit alone inflicts FAR below 0.20
    of a 26-wound Knight's health in a round (~6 wounds < 5.2 only marginally;
    well under the durability the won't-crack picker reads), so per-unit the
    picker still avoids the brick — but four together exceed the brick's wounds,
    so the army CAN crack it collectively. Per-unit expected wounds vs the
    Knight: 4 shots * 2/3 hit * 1/2 (Anti-VEHICLE 4+) * 2/3 save-fail (2+ save
    vs AP-3 -> 5+, no invuln) * 5 dmg ~= 4.4; four units ~= 17.8 ... so we add
    enough that the army collective clears 0.85 x 26 = 22.1 (see test)."""
    return UnitProfile(
        name=name,
        health=10.0,
        damage=30.0,
        hit_probability=2 / 3,
        ap=-3,
        save=3,
        strength=12,
        toughness=9,
        invuln_save=7,
        attacks=6,
        weapon_damage_per_shot=5.0,
        range_inches=48,
        unit_keywords=("VEHICLE",),
        anti_keywords=(("VEHICLE", 4),),
        melee_attacks=3,
        melee_hit_probability=0.5,
        melee_strength=6,
        melee_damage_per_shot=1.0,
    )


def _chaff(name: str, health: float = 2.0) -> UnitProfile:
    """Killable infantry chaff: low health, an anti-infantry weapon (AP0, D1)
    that cannot meaningfully hurt a Toughness-11 brick. The lowest-health pick
    always lands here when there is no focus target."""
    return UnitProfile(
        name=name,
        health=health,
        damage=1.0,
        hit_probability=2 / 3,
        ap=0,
        save=4,
        strength=4,
        toughness=4,
        attacks=2,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


# --------------------------------------------------------------------------- #
# Scenario builder                                                            #
# --------------------------------------------------------------------------- #


def _build(shooter_profiles, target_profiles):
    """Build a Battle on a clean (terrain-free, objective-free) Map so line of
    sight is always clear and the objective-contesting branch is inert. Returns
    (battle, shooters, targets). All units are placed in a tight cluster well
    within every weapon's range, every shooter facing every target."""
    army_a = Army("Shooters")
    for p in shooter_profiles:
        army_a.add_unit(p)
    army_b = Army("Targets")
    for p in target_profiles:
        army_b.add_unit(p)
    # Clean board: standard dimensions, no terrain, no objectives — so line of
    # sight is always clear and the objective-contesting branch in _do_shoot is
    # inert (the focus-fire picker is what we are exercising).
    battle = Battle(army_a, army_b, map_=Map("Test", 60.0, 44.0))
    battle._assign_uids()
    battle._current_round = 2  # any round > 1; avoids round-1 carve-outs
    shooters = list(battle.a.units)
    targets = list(battle.b.units)
    # Place shooters on one line, targets on another, 10" apart — inside every
    # weapon's range, outside engagement range, clear line of sight.
    for i, s in enumerate(shooters):
        s.position = (float(i) * 2.0, 0.0)
    for j, t in enumerate(targets):
        t.position = (float(j) * 2.0, 10.0)
    # Defensive: clear any per-round state the picker reads.
    battle._advanced_this_round = set()
    return battle, shooters, targets


def _fire_all(battle, shooters):
    """Run one Shooting phase: nominate (focus fire) then every shooter fires
    once via _do_shoot. Returns the list of target uids actually shot at, in
    activation order (read off the emitted health deltas is fragile, so we wrap
    _do_shoot to capture the chosen target)."""
    # Seed so the per-shot rolls (hits/wounds/saves) are deterministic — the
    # target-was-shot inference reads health deltas, which an unseeded random
    # roll of zero damage could hide (an anti-infantry weapon may fail every
    # save against the chaff it picked). The seed does not affect WHICH target
    # the AI selects, only whether the inflicted damage is reliably > 0.
    import random
    random.seed(20260602)
    chosen = []
    orig = battle._do_shoot

    def _wrapped(attacker, attacker_army, defender_army):
        before = {u.uid: u.current_health for u in defender_army.alive_units}
        orig(attacker, attacker_army, defender_army)
        after = {u.uid: u.current_health for u in defender_army.alive_units}
        for uid, hp0 in before.items():
            if uid in after and after[uid] < hp0 - 1e-9:
                chosen.append(uid)
                break
    battle._nominate_focusfire_target(battle.a, battle.b)
    for s in shooters:
        if s.is_alive:
            _wrapped(s, battle.a, battle.b)
    return chosen


class FocusFireGateTests(unittest.TestCase):
    """The env gate: unset reproduces the baseline; set activates the layer."""

    def setUp(self):
        self._saved = os.environ.get("SWEG_FOCUSFIRE")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("SWEG_FOCUSFIRE", None)
        else:
            os.environ["SWEG_FOCUSFIRE"] = self._saved

    def test_gate_off_no_focus_target(self):
        """Gate unset: no focus target is ever nominated."""
        os.environ.pop("SWEG_FOCUSFIRE", None)
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2"), _antitank("AT3"), _antitank("AT4")],
            [_knight_brick(), _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_focusfire_target_uid", None))

    def test_gate_off_spreads_onto_chaff_brick_survives(self):
        """Gate OFF (current pathology): the anti-tank units each pick the
        lowest-health enemy (the chaff). With enough chaff bodies to absorb the
        activations, the Knight brick takes no anti-tank fire and survives the
        phase untouched — the inverse of the real focus-fire counter."""
        os.environ.pop("SWEG_FOCUSFIRE", None)
        # One chaff body per anti-tank shooter, so the lowest-health picker
        # always has a fresh 2-wound target and never falls through to the
        # 26-wound Knight.
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2"), _antitank("AT3"), _antitank("AT4")],
            [
                _knight_brick(),
                _chaff("Scout1"), _chaff("Scout2"),
                _chaff("Scout3"), _chaff("Scout4"),
            ],
        )
        knight = targets[0]
        hp_before = knight.current_health
        _fire_all(battle, shooters)
        # The brick is completely untouched (every shot dumped into chaff).
        self.assertTrue(knight.is_alive)
        self.assertEqual(knight.current_health, hp_before)

    def test_gate_on_focus_target_nominated(self):
        """Gate ON: the army can collectively crack the Knight, so it is
        nominated as the focus target."""
        os.environ["SWEG_FOCUSFIRE"] = "1"
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2"), _antitank("AT3"), _antitank("AT4")],
            [_knight_brick(), _chaff("Scout")],
        )
        knight = targets[0]
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertEqual(getattr(battle.a, "_focusfire_target_uid", None), knight.uid)

    def test_gate_on_concentrates_and_cracks_the_brick(self):
        """Gate ON: every anti-tank unit converges on the Knight and brings it
        below half (the win condition the OFF path fails). The chaff is ignored
        until the brick is removed."""
        os.environ["SWEG_FOCUSFIRE"] = "1"
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2"), _antitank("AT3"), _antitank("AT4")],
            [_knight_brick(), _chaff("Scout")],
        )
        knight = targets[0]
        hp_before = knight.current_health
        _fire_all(battle, shooters)
        self.assertLess(
            knight.current_health, hp_before * 0.5,
            "Focus fire ON must bring the brick below half health",
        )


class FocusFireCollectiveCrackGateTests(unittest.TestCase):
    """The collective-crack gate: a brick the army cannot collectively crack is
    NOT nominated, so no fire is wasted on an unkillable target."""

    def setUp(self):
        os.environ["SWEG_FOCUSFIRE"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_FOCUSFIRE", None)

    def test_uncrackable_brick_not_nominated(self):
        """A single weak anti-tank unit cannot collectively crack a 26-wound
        Knight (it needs >= 0.85 x 26 = 22 expected wounds, far beyond one
        unit's output), so no focus target is set and the unit plays normally."""
        battle, shooters, targets = _build(
            [_antitank("AT1")],
            [_knight_brick(), _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_focusfire_target_uid", None))

    def test_pure_chaff_army_cannot_crack_brick(self):
        """An army of only anti-infantry chaff (D1, AP0, cannot wound Toughness
        11) collectively contributes ~0 to the brick, so it is never nominated
        — no wasted fire."""
        battle, shooters, targets = _build(
            [_chaff("Inf1"), _chaff("Inf2"), _chaff("Inf3"), _chaff("Inf4")],
            [_knight_brick(), _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_focusfire_target_uid", None))

    def test_single_solo_cracker_not_overridden(self):
        """The layer concentrates MULTIPLE units; a lone contributor (even a
        strong one) does not get the coordination override (contributors < 2),
        so the normal picker still runs."""
        battle, shooters, targets = _build(
            [_antitank("AT1"), _chaff("Inf2")],
            [_big_vehicle_brick(), _chaff("Scout")],
        )
        # Only AT1 can wound the brick; the chaff cannot — one contributor.
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_focusfire_target_uid", None))


class FocusFireEvenHandedTests(unittest.TestCase):
    """Even-handed: the layer fires for ANY brick, not just Knights."""

    def setUp(self):
        os.environ["SWEG_FOCUSFIRE"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_FOCUSFIRE", None)

    def test_fires_for_non_knight_vehicle_brick(self):
        """A big non-Knight VEHICLE/MONSTER brick gets the same collective
        focus-fire treatment when the army can crack it."""
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2"), _antitank("AT3")],
            [_big_vehicle_brick(), _chaff("Scout")],
        )
        brick = targets[0]
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertEqual(getattr(battle.a, "_focusfire_target_uid", None), brick.uid)
        hp_before = brick.current_health
        _fire_all(battle, shooters)
        self.assertLess(brick.current_health, hp_before * 0.6)

    def test_a_unit_that_cannot_wound_the_brick_is_not_redirected(self):
        """An anti-infantry unit that cannot wound the focus brick keeps
        clearing chaff (no wasted fire); only units that can wound it converge."""
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2"), _antitank("AT3"), _chaff("Bolters")],
            [_knight_brick(), _chaff("Scout", health=2.0)],
        )
        knight, scout = targets[0], targets[1]
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertEqual(getattr(battle.a, "_focusfire_target_uid", None), knight.uid)
        scout_before = scout.current_health
        _fire_all(battle, shooters)
        # The bolter chaff cannot wound the Knight, so it shot the Scout.
        self.assertLess(scout.current_health, scout_before)


class RangedExpectedWoundsTests(unittest.TestCase):
    """The ranged expected-wounds proxy used by the collective-crack gate."""

    def test_zero_when_weapon_cannot_wound(self):
        """A D1 AP0 Strength-4 bolter into a Toughness-11 Knight wounds only on a
        natural 6 (raw wound fraction 1/6) and carries no Anti-keyword, so it
        'genuinely can't hurt the brick' — the proxy returns exactly 0.0, so the
        bolter is never counted toward the collective crack and never redirected
        (no wasted fire)."""
        chaff_p = _chaff("Bolters")
        knight = Unit(_knight_brick())
        ew = Battle._ranged_expected_wounds(chaff_p, knight)
        self.assertEqual(ew, 0.0)

    def test_anti_keyword_lifts_wound_fraction(self):
        """An Anti-VEHICLE 4+ gun reads as able to hurt a Toughness-11 brick:
        its expected wounds are substantial (multi-damage, AP-3, wounds on 4+
        despite Strength 12 vs Toughness 11 already being 4+)."""
        at = _antitank("AT")
        knight = Unit(_knight_brick())
        ew = Battle._ranged_expected_wounds(at, knight)
        self.assertGreater(ew, 1.0)

    def test_no_shots_returns_zero(self):
        """A melee-only profile (0 ranged attacks) contributes nothing."""
        melee_only = UnitProfile(
            name="Berserker",
            health=2.0,
            damage=0.0,
            hit_probability=0.0,
            attacks=0,
            range_inches=1,
            melee_attacks=4,
            melee_hit_probability=2 / 3,
            melee_strength=6,
            melee_damage_per_shot=2.0,
        )
        knight = Unit(_knight_brick())
        self.assertEqual(Battle._ranged_expected_wounds(melee_only, knight), 0.0)


if __name__ == "__main__":
    unittest.main()
