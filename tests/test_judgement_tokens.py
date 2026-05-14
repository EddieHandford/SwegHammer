"""Tests for the Leagues of Votann army rule: Eye of the Ancestors / Judgement Tokens.

The mechanic:
  - When a non-Votann (enemy) unit destroys a Votann model, that enemy unit
    earns a token on itself; tokens are stored on the Votann army's
    `judgement_tokens` dict keyed by enemy unit uid.
  - 1+ tokens: Votann attacks against that target re-roll Hit rolls of 1.
  - 3+ tokens: Votann attacks against that target re-roll ALL failed Hit
    rolls AND re-roll Wound rolls of 1.
  - Non-Votann armies never gain tokens (their `judgement_tokens` stays
    empty for the whole battle).

We exercise the simulator at sub-method granularity (`_maybe_award_judgement_token`,
`Unit.attack`) so the tests pin the rule, not the activation loop.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army, VOTANN_FACTION_TAG
from code.detachments import Detachment
from code.events import EventLog, JudgementTokenAwarded
from code.simulator import Battle
from code.units import Unit, UnitProfile


# A no-op detachment used by the buff-application tests so neither side
# carries the default-faction passives (Oathband / Gladius) that would
# otherwise change the per-attack RNG branch count and obscure the
# Judgement Tokens delta.
_INERT_DET = Detachment(name="Inert", faction="(test)", notes="no passives")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _votann_profile(name: str = "Hearthkyn") -> UnitProfile:
    """A bare-bones Votann INFANTRY profile. Faction string matches
    code.factions.faction_of('Leagues of Votann.cat') so the army's
    `is_votann_army` property resolves True."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        range_inches=24,
        faction=VOTANN_FACTION_TAG,
        unit_keywords=("INFANTRY",),
    )


def _marine_profile(name: str = "Marine") -> UnitProfile:
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=-1, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        range_inches=24,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
    )


def _build_battle(votann_first: bool = True) -> Battle:
    """Set up a Battle with a Votann army on side A (by default) and a
    Space Marine army on side B. UIDs are assigned but the run loop is not
    invoked — these tests poke specific methods directly.
    """
    votann = Army("Votann")
    votann.add_unit(_votann_profile())
    votann.add_unit(_votann_profile())
    marines = Army("Marines")
    marines.add_unit(_marine_profile())
    marines.add_unit(_marine_profile())
    a, b = (votann, marines) if votann_first else (marines, votann)
    battle = Battle(a, b)
    battle._assign_uids()
    battle._deploy_armies()
    return battle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class FactionDetectionTests(unittest.TestCase):

    def test_votann_army_flag_true_when_unit_has_faction_tag(self):
        army = Army("V")
        army.add_unit(_votann_profile())
        self.assertTrue(army.is_votann_army)

    def test_non_votann_army_flag_false(self):
        army = Army("M")
        army.add_unit(_marine_profile())
        self.assertFalse(army.is_votann_army)

    def test_empty_army_flag_false(self):
        self.assertFalse(Army("Empty").is_votann_army)

    def test_judgement_tokens_dict_initialised_empty(self):
        self.assertEqual(Army("V").judgement_tokens, {})


class TokenAwardOnKillTests(unittest.TestCase):
    """`_maybe_award_judgement_token` increments the token count when the
    victim's army is Votann and the killer's army is not."""

    def test_killing_a_votann_unit_awards_a_token(self):
        battle = _build_battle(votann_first=True)
        votann, marines = battle.a, battle.b
        killer = marines.units[0]
        victim = votann.units[0]
        log = EventLog()
        battle.subscribers.append(log)

        battle._maybe_award_judgement_token(
            killer=killer, killer_army=marines,
            victim=victim, victim_army=votann,
        )

        self.assertEqual(votann.judgement_tokens.get(killer.uid), 1)
        events = [e for e in log.events if isinstance(e, JudgementTokenAwarded)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].target_uid, killer.uid)
        self.assertEqual(events[0].total_tokens, 1)

    def test_tokens_stack_on_the_same_target(self):
        battle = _build_battle(votann_first=True)
        votann, marines = battle.a, battle.b
        killer = marines.units[0]
        for _ in range(3):
            battle._maybe_award_judgement_token(
                killer=killer, killer_army=marines,
                victim=votann.units[0], victim_army=votann,
            )
        self.assertEqual(votann.judgement_tokens[killer.uid], 3)

    def test_different_killers_get_separate_token_counts(self):
        battle = _build_battle(votann_first=True)
        votann, marines = battle.a, battle.b
        k0, k1 = marines.units[0], marines.units[1]
        battle._maybe_award_judgement_token(
            killer=k0, killer_army=marines,
            victim=votann.units[0], victim_army=votann,
        )
        battle._maybe_award_judgement_token(
            killer=k1, killer_army=marines,
            victim=votann.units[1], victim_army=votann,
        )
        battle._maybe_award_judgement_token(
            killer=k1, killer_army=marines,
            victim=votann.units[0], victim_army=votann,
        )
        self.assertEqual(votann.judgement_tokens[k0.uid], 1)
        self.assertEqual(votann.judgement_tokens[k1.uid], 2)

    def test_non_votann_victims_do_not_award_tokens(self):
        """A Marine killing another Marine never awards tokens."""
        battle = _build_battle(votann_first=True)
        marines = battle.b
        # Build a second non-Votann army so the killer isn't Votann either.
        orks = Army("Orks")
        orks.add_unit(_marine_profile("Boy"))
        battle._maybe_award_judgement_token(
            killer=marines.units[0], killer_army=marines,
            victim=orks.units[0], victim_army=orks,
        )
        self.assertEqual(marines.judgement_tokens, {})
        self.assertEqual(orks.judgement_tokens, {})

    def test_votann_on_votann_kill_does_not_award_token(self):
        """Mirror-match: Votann shooting a Votann opponent does not stamp
        the Votann attacker with a token on its own army (we don't want
        them buffing themselves by self-killing)."""
        battle = _build_battle(votann_first=True)
        votann = battle.a
        # Build a second Votann army to serve as the "victim" side.
        votann_b = Army("Votann B")
        votann_b.add_unit(_votann_profile("Hearthkyn B"))
        # Manually assign uid so the call works without going through
        # Battle._assign_uids (which only walks self.a / self.b).
        votann_b.units[0].uid = "VB0"
        battle._maybe_award_judgement_token(
            killer=votann.units[0], killer_army=votann,
            victim=votann_b.units[0], victim_army=votann_b,
        )
        self.assertEqual(votann_b.judgement_tokens, {})


class TokenBuffApplicationTests(unittest.TestCase):
    """Votann attackers reading their own army's tokens get tier-1 (1+
    re-roll Hit 1s) and tier-3 (re-roll all Hit + Wound 1s) buffs."""

    def _votann_shooter(self) -> UnitProfile:
        """Custom shooter: 4+ to hit (so the re-roll buffs have a measurable
        effect), S5 vs T4 (3+ to wound — 1s are infrequent but present),
        many attacks for low variance, attacks reset per shot."""
        return UnitProfile(
            name="Hearthkyn",
            health=1, damage=1, hit_probability=0.5,
            ap=0, save=4, strength=5, toughness=5,
            attacks=12, weapon_damage_per_shot=1.0,
            range_inches=24,
            faction=VOTANN_FACTION_TAG,
            unit_keywords=("INFANTRY",),
        )

    def _soft_target(self) -> UnitProfile:
        """No save, high HP — every successful unsaved wound turns into
        damage. Keeps the test focused on the hit/wound stages."""
        return UnitProfile(
            name="Tgt",
            health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
            faction="Adeptus Astartes",
        )

    def _run(self, n_trials: int, tokens: int, seed: int) -> float:
        random.seed(seed)
        # Inert detachment on both sides — strips Oathband / Gladius
        # default passives so only the Judgement Tokens delta is measured.
        votann = Army("Votann", detachment=_INERT_DET)
        for _ in range(n_trials):
            votann.add_unit(self._votann_shooter())
        marines = Army("Marines", detachment=_INERT_DET)
        marines.add_unit(self._soft_target())
        # Wire army_ref + uid manually (we're not running Battle.run).
        marines.units[0].uid = "T0"
        if tokens > 0:
            votann.judgement_tokens[marines.units[0].uid] = tokens
        total = 0.0
        for shooter in votann.units:
            shooter.army_ref = votann
            total += shooter.attack(marines.units[0], distance=12.0)
        return total

    def test_one_token_target_improves_hit_rate(self):
        """At 4+ to hit, re-rolling 1s lifts hit rate ~16% relative. Over
        many trials the 1-token total should exceed the 0-token total."""
        n_trials = 200
        zero_dmg = self._run(n_trials, tokens=0, seed=11)
        one_dmg = self._run(n_trials, tokens=1, seed=11)
        # Re-roll 1s at 4+ is +16% relative hit chance. The 1-token total
        # must be measurably higher than the 0-token baseline.
        self.assertGreater(one_dmg, zero_dmg * 1.05)

    def test_three_tokens_strictly_more_damage_than_one_token(self):
        """Tier-3 (re-roll all hits + wound 1s) should clearly outdamage
        tier-1 (re-roll hit 1s)."""
        n_trials = 200
        one_dmg = self._run(n_trials, tokens=1, seed=23)
        three_dmg = self._run(n_trials, tokens=3, seed=23)
        # Re-roll all hits at 4+ raises hit rate from 50% to ~75% (vs.
        # re-roll 1s only -> ~58%). Plus reroll wound 1s. Expect ~25%+
        # damage boost. We assert a conservative 1.15x.
        self.assertGreater(three_dmg, one_dmg * 1.15)

    def test_no_tokens_no_buff(self):
        """A Votann attacker against a target with zero tokens behaves
        exactly like a non-Votann attacker — no re-roll buff applies."""
        n_trials = 200
        # Pre-roll RNG state for the no-token Votann run.
        votann_dmg = self._run(n_trials, tokens=0, seed=42)

        # Now repeat with a non-Votann faction tag on the shooter — must
        # come out identical to the no-token Votann run (no buff in
        # either case, same seed).
        random.seed(42)
        non_votann = Army("Imperium", detachment=_INERT_DET)
        shooter_p = self._votann_shooter()
        # Strip the Votann tag — same stats, different faction.
        shooter_p = UnitProfile(
            **{**shooter_p.__dict__, "faction": "Adeptus Astartes"}
        )
        for _ in range(n_trials):
            non_votann.add_unit(shooter_p)
        target_p = self._soft_target()
        marines = Army("Marines", detachment=_INERT_DET)
        marines.add_unit(target_p)
        marines.units[0].uid = "T0"
        baseline = 0.0
        for shooter in non_votann.units:
            shooter.army_ref = non_votann
            baseline += shooter.attack(marines.units[0], distance=12.0)
        # Within 1% (RNG is identical -> totals identical).
        self.assertAlmostEqual(votann_dmg, baseline, places=5)

    def test_non_votann_army_does_not_gain_tokens(self):
        """Even if a non-Votann army's judgement_tokens dict is mutated
        manually (it shouldn't be — but be defensive), the buff path
        gates on `is_votann_army` and ignores the entries."""
        marines = Army("Marines", detachment=_INERT_DET)
        shooter_p = UnitProfile(
            name="Marine", health=1, damage=1, hit_probability=0.5,
            attacks=12, weapon_damage_per_shot=1.0, range_inches=24,
            strength=10, faction="Adeptus Astartes",
        )
        for _ in range(50):
            marines.add_unit(shooter_p)
        target_p = self._soft_target()
        target_army = Army("Tgt", detachment=_INERT_DET)
        target_army.add_unit(target_p)
        target_army.units[0].uid = "T0"
        # Spuriously stash 5 tokens — the buff path must ignore them
        # because `marines.is_votann_army` is False.
        marines.judgement_tokens[target_army.units[0].uid] = 5

        random.seed(99)
        with_fake_tokens = 0.0
        for shooter in marines.units:
            shooter.army_ref = marines
            with_fake_tokens += shooter.attack(target_army.units[0], distance=12.0)

        random.seed(99)
        marines.judgement_tokens.clear()
        without = 0.0
        for shooter in marines.units:
            shooter.army_ref = marines
            without += shooter.attack(target_army.units[0], distance=12.0)

        # Identical RNG, identical buff path (no buff in either case).
        self.assertAlmostEqual(with_fake_tokens, without, places=5)


if __name__ == "__main__":
    unittest.main()
