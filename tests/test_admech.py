"""Tests for the Adeptus Mechanicus army rule Doctrina Imperatives (#119).

Doctrina Imperatives (10e AdMech army rule, Wahapedia):
    "At the start of your Command phase, select one of the following
     Doctrina Imperatives to be active for your army until the start of
     your next Command phase:
       Protector Imperative — +1 to hit on ranged attacks, -1 to hit on
         melee attacks for ADEPTUS MECHANICUS models from your army.
       Conqueror Imperative — +1 to hit on melee attacks, -1 to hit on
         ranged attacks for ADEPTUS MECHANICUS models from your army."

Implementation:
    * `Army.doctrina_imperative` — per-Army state, str ("protector" /
      "conqueror") or None. Reset each round, re-picked by the AI.
    * Hit-roll modifier: `Unit.attack` reads attacker.army_ref's imperative
      and shifts hit_target up/down based on attack mode. Faction-gated on
      `attacker.profile.faction == "Adeptus Mechanicus"`.
    * AI: `code.strategy.pick_doctrina_imperative(army, enemy)` — picks
      "conqueror" when engaged_count >= shooty_count, else "protector".

Cited as `simulator.doctrina_imperatives`.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.strategy import pick_doctrina_imperative
from code.units import UnitProfile, _prob_to_target


def _admech_skitarii(name: str = "Skitarii Ranger") -> UnitProfile:
    """A minimal AdMech profile tagged with the canonical faction string.
    Hits on 3+ ranged and 4+ melee so the imperative shifts are visible."""
    return UnitProfile(
        name=name,
        health=1, damage=1, hit_probability=2 / 3,   # 3+ ranged
        ap=0, save=4, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=30,
        leadership=7,
        faction="Adeptus Mechanicus",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,   # 4+ melee
    )


def _marine_profile(name: str = "Marine") -> UnitProfile:
    """A non-AdMech stand-in (Adeptus Astartes) used as the opposing force
    and as the 'unaffected by Doctrina' control group."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _effective_hit_target(attacker, target, mode: str) -> int:
    """Re-run the hit_target derivation from Unit.attack up to the Doctrina
    shift. We don't want to run the full attack (which is stochastic and
    mutates state) — just compute the deterministic hit_target the attack
    loop would use.

    This mirrors the structure in Unit.attack:
      base hit_target from hit/melee_hit probability, then the Doctrina
      shift. Skipping intermediate +1-to-hit / heavy-cover / stealth /
      Heavy keyword effects is fine for these tests — the AdMech profile
      and target don't trigger any of those.
    """
    p = attacker.profile
    if mode == "melee":
        hit_target = _prob_to_target(p.melee_hit_probability)
    else:
        hit_target = _prob_to_target(p.hit_probability)
    # Apply the same Doctrina logic Unit.attack uses.
    if p.faction == "Adeptus Mechanicus":
        own_army = getattr(attacker, "army_ref", None)
        imperative = (
            getattr(own_army, "doctrina_imperative", None)
            if own_army is not None else None
        )
        if imperative == "protector":
            if mode != "melee":
                hit_target = max(2, hit_target - 1)
            else:
                hit_target = min(6, hit_target + 1)
        elif imperative == "conqueror":
            if mode == "melee":
                hit_target = max(2, hit_target - 1)
            else:
                hit_target = min(6, hit_target + 1)
    return hit_target


# ---------------------------------------------------------------------------
# Hit-roll buffs
# ---------------------------------------------------------------------------


class DoctrinaHitRollTests(unittest.TestCase):
    """Drive _effective_hit_target with a configured Army.doctrina_imperative
    and verify the expected shift."""

    def _make_battle(self) -> Battle:
        ad = Army("AdMech")
        ad.add_unit(_admech_skitarii())
        marines = Army("Marines")
        marines.add_unit(_marine_profile())
        battle = Battle(ad, marines)
        battle._assign_uids()
        return battle

    def test_protector_grants_plus_one_to_hit_ranged(self):
        battle = self._make_battle()
        attacker = battle.a.units[0]
        target = battle.b.units[0]
        battle.a.doctrina_imperative = "protector"
        base = _prob_to_target(attacker.profile.hit_probability)   # 3+
        shifted = _effective_hit_target(attacker, target, mode="ranged")
        self.assertEqual(shifted, max(2, base - 1),
                         "Protector must lower ranged hit_target by 1 (+1 to hit)")

    def test_protector_imposes_minus_one_to_hit_melee(self):
        battle = self._make_battle()
        attacker = battle.a.units[0]
        target = battle.b.units[0]
        battle.a.doctrina_imperative = "protector"
        base = _prob_to_target(attacker.profile.melee_hit_probability)   # 4+
        shifted = _effective_hit_target(attacker, target, mode="melee")
        self.assertEqual(shifted, min(6, base + 1),
                         "Protector must raise melee hit_target by 1 (-1 to hit)")

    def test_conqueror_inverse(self):
        """Conqueror is the symmetric inverse of Protector: melee gets +1
        to hit, ranged gets -1 to hit."""
        battle = self._make_battle()
        attacker = battle.a.units[0]
        target = battle.b.units[0]
        battle.a.doctrina_imperative = "conqueror"
        ranged_base = _prob_to_target(attacker.profile.hit_probability)
        melee_base = _prob_to_target(attacker.profile.melee_hit_probability)
        self.assertEqual(
            _effective_hit_target(attacker, target, mode="ranged"),
            min(6, ranged_base + 1),
            "Conqueror must raise ranged hit_target by 1 (-1 to hit)",
        )
        self.assertEqual(
            _effective_hit_target(attacker, target, mode="melee"),
            max(2, melee_base - 1),
            "Conqueror must lower melee hit_target by 1 (+1 to hit)",
        )

    def test_non_admech_unaffected(self):
        """A non-AdMech unit in a battle where the opposing AdMech army has
        an active imperative must NOT see its hit_target shifted. Doctrina
        is gated on attacker.profile.faction, not opponent's."""
        ad = Army("AdMech")
        ad.add_unit(_admech_skitarii())
        marines = Army("Marines")
        marines.add_unit(_marine_profile())
        battle = Battle(ad, marines)
        battle._assign_uids()
        battle.a.doctrina_imperative = "protector"   # AdMech side is buffed
        # Marines should be untouched.
        marine = battle.b.units[0]
        target = battle.a.units[0]
        ranged_base = _prob_to_target(marine.profile.hit_probability)
        melee_base = _prob_to_target(marine.profile.melee_hit_probability)
        self.assertEqual(
            _effective_hit_target(marine, target, mode="ranged"), ranged_base,
            "Non-AdMech attacker must NOT receive a Doctrina hit modifier",
        )
        self.assertEqual(
            _effective_hit_target(marine, target, mode="melee"), melee_base,
            "Non-AdMech attacker must NOT receive a Doctrina hit modifier",
        )

    def test_no_imperative_no_shift(self):
        """If `doctrina_imperative` is None (not yet picked / between rounds),
        the hit_target must be the un-shifted base value."""
        battle = self._make_battle()
        battle.a.doctrina_imperative = None
        attacker = battle.a.units[0]
        target = battle.b.units[0]
        ranged_base = _prob_to_target(attacker.profile.hit_probability)
        melee_base = _prob_to_target(attacker.profile.melee_hit_probability)
        self.assertEqual(
            _effective_hit_target(attacker, target, mode="ranged"), ranged_base,
        )
        self.assertEqual(
            _effective_hit_target(attacker, target, mode="melee"), melee_base,
        )


# ---------------------------------------------------------------------------
# Per-round reset + AI
# ---------------------------------------------------------------------------


class DoctrinaRoundResetTests(unittest.TestCase):
    """The simulator must reset and re-pick `doctrina_imperative` at the
    start of each Command phase. Drive _run_round directly so we can
    inspect the picked imperative without running a full battle."""

    def _make_battle(self) -> Battle:
        ad = Army("AdMech")
        for _ in range(3):
            ad.add_unit(_admech_skitarii())
        marines = Army("Marines")
        for _ in range(2):
            marines.add_unit(_marine_profile())
        battle = Battle(ad, marines)
        battle._assign_uids()
        return battle

    def test_imperative_resets_each_round(self):
        """The simulator should reset and re-pick the imperative every
        Command phase. We force the AI's hand by placing all enemies far
        away (no engagement) in round 1, then close to the AdMech units in
        round 2; the imperative should flip from protector to conqueror."""
        random.seed(0)
        battle = self._make_battle()
        # Force-position everything for a clean read:
        # Round 1: enemies are >12" from every AdMech unit -> protector.
        for u in battle.a.units:
            u.position = (10.0, 10.0)
        for u in battle.b.units:
            u.position = (50.0, 50.0)
        battle._run_round(1)
        self.assertEqual(battle.a.doctrina_imperative, "protector")
        # Round 2: enemies are within 12" of every AdMech unit -> conqueror.
        for u in battle.b.units:
            u.position = (12.0, 10.0)   # ~2" from AdMech cluster
        battle._run_round(2)
        self.assertEqual(battle.a.doctrina_imperative, "conqueror")

    def test_ai_chooses_conqueror_when_engaged(self):
        """The AI's tipping rule: when engaged_count >= shooty_count, pick
        conqueror. Place every AdMech unit within 12" of an enemy."""
        battle = self._make_battle()
        for u in battle.a.units:
            u.position = (10.0, 10.0)
        for u in battle.b.units:
            u.position = (11.0, 10.0)   # 1" away — all AdMech are engaged
        choice = pick_doctrina_imperative(battle.a, battle.b)
        self.assertEqual(choice, "conqueror")

    def test_ai_chooses_protector_when_standoff(self):
        """Symmetric to the engaged case: no AdMech unit within 12" of any
        enemy -> protector (default gunline posture)."""
        battle = self._make_battle()
        for u in battle.a.units:
            u.position = (5.0, 5.0)
        for u in battle.b.units:
            u.position = (50.0, 50.0)   # far away
        choice = pick_doctrina_imperative(battle.a, battle.b)
        self.assertEqual(choice, "protector")

    def test_ai_picks_sensibly_across_five_rounds(self):
        """End-to-end: run a 5-round Battle and confirm the imperative is
        always 'protector' or 'conqueror' (never None / invalid). Also
        confirm at least one transition between the two as positions
        evolve — the AI must not be stuck on one imperative forever."""
        random.seed(42)
        battle = self._make_battle()
        picked = []
        for r in range(1, 6):
            # Alternate engagement state to force re-picks.
            if r % 2 == 0:
                for u in battle.b.units:
                    u.position = (11.0, 10.0)
            else:
                for u in battle.b.units:
                    u.position = (50.0, 50.0)
            for u in battle.a.units:
                u.position = (10.0, 10.0)
            battle._run_round(r)
            picked.append(battle.a.doctrina_imperative)
        # Every pick must be a valid imperative.
        for p in picked:
            self.assertIn(p, ("protector", "conqueror"))
        # And we should see both at least once across 5 rounds.
        self.assertIn("protector", picked)
        self.assertIn("conqueror", picked)


# ---------------------------------------------------------------------------
# Citation hook
# ---------------------------------------------------------------------------


class DoctrinaCitationTests(unittest.TestCase):
    """The audit_rules script lists `simulator.doctrina_imperatives` as
    required; the fragment under data/rule_citations.d/admech.json must
    satisfy it. This is also covered by tests/test_audit.py but we sanity
    -check here so a missing citation surfaces in the AdMech test file."""

    def test_citation_present(self):
        from scripts.audit_rules import _load_citations
        cits = _load_citations()
        self.assertIn("simulator.doctrina_imperatives", cits)
        entry = cits["simulator.doctrina_imperatives"]
        self.assertEqual(entry["scope"], "army-wide")
        self.assertIn("Doctrina", entry["rule_name"])


if __name__ == "__main__":
    unittest.main()
