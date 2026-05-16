"""Tests for the leader-before-led activation priority bump (#C4).

`Army.activation_queue` puts CHARACTER units with a registered
LeaderAbility ahead of their led squad so the leader's aura buffs are
applied to the squad's activation rather than after it. Faction-neutral:
the rule fires on any leader with a registered ability + a friendly
non-CHARACTER unit in aura range. The tests below build minimal armies
out of `UnitProfile` directly (no faction bias in the picker).

`UnitProfile.score` is a computed `lanchester_score(...)` property — to
get the squad to outscore the leader naturally (so we can verify the
bump overrides score-sort) we just hand the squad much higher damage.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.units import UnitProfile


def _leader_profile(name: str) -> UnitProfile:
    """A CHARACTER profile whose name substring-matches a registered
    LeaderAbility (Marines Captain → Rites of Battle, 6\" aura; Chaplain
    → Spiritual Leader, 6\" aura). Damage stays low so the squad
    out-scores the leader naturally.
    """
    return UnitProfile(
        name=name,
        health=4, damage=2,
        hit_probability=2 / 3, ap=-1, save=3,
        attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _squad_profile(name: str, damage: float = 30.0) -> UnitProfile:
    """A non-CHARACTER infantry profile with a HIGHER Lanchester score
    than the leader — high damage forces the squad ahead under the
    score-only path so the priority bump is observable.
    """
    return UnitProfile(
        name=name,
        health=6, damage=damage,
        hit_probability=2 / 3, ap=-1, save=3,
        attacks=10, weapon_damage_per_shot=damage / 10.0,
        strength=4, range_inches=24,
        melee_attacks=4, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        unit_keywords=("INFANTRY",),
    )


def _solo_character_profile(name: str = "Lone Hero") -> UnitProfile:
    """A CHARACTER whose name does NOT substring-match the LeaderAbility
    registry — used to confirm the bump is gated on the registry lookup,
    not on CHARACTER alone.
    """
    return UnitProfile(
        name=name,
        health=4, damage=2,
        hit_probability=2 / 3, ap=-1, save=3,
        attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _place(army: Army, profile: UnitProfile, pos) -> None:
    army.add_unit(profile)
    army.units[-1].position = pos


class LeaderBeforeLedTests(unittest.TestCase):

    def test_baseline_score_ordering_squad_outranks_leader(self):
        """Sanity check: without the leader-before-led bump (no registered
        ability) the high-damage squad sorts ahead of the leader by
        Lanchester score. This anchors what the bump is overriding."""
        army = Army("Generic")
        _place(army, _solo_character_profile("Lone Hero"), (10.0, 10.0))
        _place(army, _squad_profile("Heavy Squad"), (10.5, 10.0))

        queue = army.activation_queue(set())
        names = [u.profile.name for u in queue]
        # No registered ability for "Lone Hero" → score-only.
        self.assertEqual(names[0], "Heavy Squad")
        self.assertEqual(names[1], "Lone Hero")

    def test_captain_activates_before_intercessors(self):
        """Marine Captain (CHARACTER + Rites of Battle 6\" aura) leading
        an adjacent Intercessor squad sorts AHEAD of the squad in the
        activation queue, despite the squad's higher Lanchester score."""
        army = Army("Marines")
        _place(army, _leader_profile("Captain"), (10.0, 10.0))
        _place(army, _squad_profile("Intercessors"), (12.0, 10.0))

        queue = army.activation_queue(set())
        names = [u.profile.name for u in queue]
        self.assertEqual(names[0], "Captain")
        self.assertEqual(names[1], "Intercessors")

    def test_lone_captain_with_no_squad_in_range_no_bump(self):
        """A Captain with no friendly non-CHARACTER squad inside its 6\"
        aura is NOT bumped — there's no led teammate to buff. Falls back
        to score-sort behind a higher-scoring distant ally."""
        army = Army("Marines")
        _place(army, _leader_profile("Captain"), (10.0, 10.0))
        # Squad parked far outside the 6" aura.
        _place(army, _squad_profile("Far Squad"), (40.0, 40.0))

        queue = army.activation_queue(set())
        names = [u.profile.name for u in queue]
        self.assertEqual(names[0], "Far Squad")
        self.assertEqual(names[1], "Captain")

    def test_solo_character_with_no_registered_ability_no_bump(self):
        """A CHARACTER whose profile name does NOT substring-match the
        LeaderAbility registry receives no bump even when a squad is
        adjacent. Gates the rule on the registry lookup."""
        army = Army("Generic")
        _place(army, _solo_character_profile("Lone Hero"), (10.0, 10.0))
        _place(army, _squad_profile("Big Squad"), (10.5, 10.0))

        queue = army.activation_queue(set())
        names = [u.profile.name for u in queue]
        self.assertEqual(names[0], "Big Squad")
        self.assertEqual(names[1], "Lone Hero")

    def test_multiple_leader_led_pairs_all_leaders_first(self):
        """Two leader+squad pairs. Both leaders sort ahead of any squad
        in the queue. Confirms the bump is faction-neutral and applies
        per-leader, not per-army."""
        army = Army("Marines")
        _place(army, _leader_profile("Captain"), (10.0, 10.0))
        _place(army, _squad_profile("Intercessors"), (12.0, 10.0))
        _place(army, _leader_profile("Chaplain"), (40.0, 40.0))
        _place(army, _squad_profile("Tactical Squad"), (41.0, 40.0))

        queue = army.activation_queue(set())
        names = [u.profile.name for u in queue]
        leader_positions = [names.index(n) for n in ("Captain", "Chaplain")]
        squad_positions = [names.index(n) for n in ("Intercessors", "Tactical Squad")]
        self.assertLess(max(leader_positions), min(squad_positions))


if __name__ == "__main__":
    unittest.main()
