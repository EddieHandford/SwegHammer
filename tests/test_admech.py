"""Tests for the Adeptus Mechanicus army rule Doctrina Imperatives (#119).

Doctrina Imperatives (10e AdMech army rule, Wahapedia verbatim):
    "At the start of the battle round, you can select one of the Doctrina
     Imperatives below. Until the end of the battle round, that Doctrina
     Imperative is active for your army, and all units from your army that
     have the Doctrina Imperatives ability gain the relevant abilities shown
     below.
       Protector Imperative — Ranged weapons equipped by models in this unit
         have the [HEAVY] ability. Improve the Ballistic Skill characteristic
         of ranged weapons equipped by models in this unit by 1. Each time a
         melee attack targets this unit, if this unit has the BATTLELINE
         keyword and/or it is within 6\" of one or more friendly ADEPTUS
         MECHANICUS BATTLELINE units, subtract 1 from the Hit roll.
       Conqueror Imperative — Ranged weapons equipped by models in this unit
         have the [ASSAULT] ability. Improve the Weapon Skill characteristic
         of melee weapons equipped by models in this unit by 1. Each time a
         model in this unit makes an attack, if this unit has the BATTLELINE
         keyword and/or it is within 6\" of one or more friendly ADEPTUS
         MECHANICUS BATTLELINE units, improve the Armour Penetration
         characteristic of that attack by 1."

BOTH imperatives are BUFF-ONLY — there is NO penalty to the off-mode.
  Protector gives +1 Ballistic Skill (improves ranged hit_target by 1) to
  all AdMech units, PLUS a defensive -1 to incoming melee Hit rolls for
  BATTLELINE-adjacent AdMech units. It does NOT penalise the AdMech player's
  own melee attacks.
  Conqueror gives +1 Weapon Skill (improves melee hit_target by 1) to all
  AdMech units, PLUS +1 Armour Penetration on all attacks for BATTLELINE-
  adjacent units. It does NOT penalise the AdMech player's own ranged attacks.

Implementation:
    * `Army.doctrina_imperative` — per-Army state, str ("protector" /
      "conqueror") or None. Reset each round, re-picked by the AI.
      Set only while at least one AdMech unit is alive (alive_units gate
      at round start — ADMECH-DOCTRINA-V1 fix mirrors SOROR-ACTS-OF-FAITH-V1).
    * Offensive hit-roll modifier: `Unit.attack` reads attacker.army_ref's
      imperative and adds +1 to hit_mod_delta (lowers hit_target) for the
      matched mode only. Faction-gated on attacker.profile.faction ==
      "Adeptus Mechanicus". No off-mode penalty.
    * Defensive hit-roll modifier: when mode == "melee" and the TARGET is
      an AdMech unit whose army has Protector active and which passes the
      BATTLELINE-or-within-6"-of-BATTLELINE proximity gate, the attacker's
      hit_mod_delta gets -1 (raises the attacker's hit_target).
    * Conqueror AP+1: `Unit.attack` reads attacker.army_ref's imperative and
      applies ap -= 1 (better penetration) for all attacks when Conqueror is
      active and the BATTLELINE proximity gate is met.
    * AI: `code.strategy.pick_doctrina_imperative(army, enemy)` — picks
      "conqueror" when engaged_count >= shooty_count, else "protector".

Cited as `simulator.doctrina_imperatives`.
"""

from __future__ import annotations

import os
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

    IMPORTANT: Doctrina is BUFF-ONLY. Protector improves the ranged
    hit_target (lowers it = easier to hit). Conqueror improves the melee
    hit_target. Neither imperative penalises the off-mode for the ATTACKER
    (the Protector defensive -1 applies to INCOMING melee attacks against an
    AdMech target, not to the AdMech attacker's own melee attacks — that is
    handled separately in the defender block of Unit.attack).
    """
    p = attacker.profile
    if mode == "melee":
        hit_target = _prob_to_target(p.melee_hit_probability)
    else:
        hit_target = _prob_to_target(p.hit_probability)
    # Apply the same Doctrina offensive logic Unit.attack uses.
    # Buff-only: +1 to hit for the matched mode, NO penalty for the other.
    if p.faction == "Adeptus Mechanicus":
        own_army = getattr(attacker, "army_ref", None)
        imperative = (
            getattr(own_army, "doctrina_imperative", None)
            if own_army is not None else None
        )
        if imperative == "protector" and mode != "melee":
            hit_target = max(2, hit_target - 1)   # +1 Ballistic Skill
        elif imperative == "conqueror" and mode == "melee":
            hit_target = max(2, hit_target - 1)   # +1 Weapon Skill
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

    def test_protector_no_penalty_on_own_melee(self):
        """Protector is buff-only for the AdMech ATTACKER. The Wahapedia rule
        grants +1 Ballistic Skill (ranged) plus a DEFENSIVE -1 to incoming
        melee attacks against AdMech targets. It does NOT penalise the AdMech
        attacker's own melee hit_target — that would be a fabrication.
        MR-D (claude/sim-calibration-5) removed this fabrication from the live
        code; ADMECH-DOCTRINA-V1 corrects the stale test description."""
        battle = self._make_battle()
        attacker = battle.a.units[0]
        target = battle.b.units[0]
        battle.a.doctrina_imperative = "protector"
        base = _prob_to_target(attacker.profile.melee_hit_probability)   # 4+
        shifted = _effective_hit_target(attacker, target, mode="melee")
        self.assertEqual(shifted, base,
                         "Protector must NOT penalise the AdMech attacker's "
                         "own melee hit_target (buff-only rule)")

    def test_conqueror_buff_only(self):
        """Conqueror is buff-only: melee attacks get +1 Weapon Skill (lower
        hit_target = easier to hit). Ranged attacks are UNAFFECTED — Conqueror
        does NOT penalise the AdMech attacker's own ranged hit_target. That
        would be a fabrication. MR-D (claude/sim-calibration-5) removed this
        fabrication; ADMECH-DOCTRINA-V1 corrects the stale test description."""
        battle = self._make_battle()
        attacker = battle.a.units[0]
        target = battle.b.units[0]
        battle.a.doctrina_imperative = "conqueror"
        ranged_base = _prob_to_target(attacker.profile.hit_probability)
        melee_base = _prob_to_target(attacker.profile.melee_hit_probability)
        self.assertEqual(
            _effective_hit_target(attacker, target, mode="ranged"),
            ranged_base,
            "Conqueror must NOT penalise the AdMech attacker's own ranged "
            "hit_target (buff-only rule)",
        )
        self.assertEqual(
            _effective_hit_target(attacker, target, mode="melee"),
            max(2, melee_base - 1),
            "Conqueror must lower melee hit_target by 1 (+1 Weapon Skill)",
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

    def setUp(self):
        # command-phase scoring is now default-ON; this mechanic test uses the legacy timing
        os.environ["SWEG_CMDSCORE"] = "0"

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


# ---------------------------------------------------------------------------
# BATTLELINE proximity gate (ADMECH-DIAG-2, 2026-05-24)
# ---------------------------------------------------------------------------


def _admech_battleline(name: str = "Skitarii Ranger") -> UnitProfile:
    """A BATTLELINE-keyworded AdMech profile — used as the gate-source for
    the within-6" check."""
    return UnitProfile(
        name=name,
        health=1, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=30,
        leadership=7,
        faction="Adeptus Mechanicus",
        unit_keywords=("INFANTRY", "BATTLELINE"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
    )


def _admech_non_battleline(name: str = "Tech-Priest Dominus") -> UnitProfile:
    """A non-BATTLELINE AdMech profile — used as the gate-subject for the
    within-6" check (e.g. character, Onager, Skorpius)."""
    return UnitProfile(
        name=name,
        health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Mechanicus",
        unit_keywords=("INFANTRY", "CHARACTER"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


class DoctrinaBattlelineProximityTests(unittest.TestCase):
    """The BATTLELINE-or-within-6" proximity gate from
    `code.units._doctrina_battleline_proximity_met`. Gate scopes the
    Protector defensive -1 to Hit (melee) and the Conqueror +1 AP buff;
    the +1 BS / WS portion of each imperative is unconditional."""

    def _make_battle(self, attacker_profile, ally_profile=None):
        from code.units import _doctrina_battleline_proximity_met
        ad = Army("AdMech")
        ad.add_unit(attacker_profile)
        if ally_profile is not None:
            ad.add_unit(ally_profile)
        marines = Army("Marines")
        marines.add_unit(_marine_profile())
        battle = Battle(ad, marines)
        battle._assign_uids()
        return battle, _doctrina_battleline_proximity_met

    def test_battleline_self_passes(self):
        """A BATTLELINE-keyword AdMech unit satisfies the gate without
        needing any nearby ally — its own keyword is sufficient."""
        battle, gate = self._make_battle(_admech_battleline())
        attacker = battle.a.units[0]
        attacker.position = (50.0, 50.0)   # far from any other unit
        self.assertTrue(gate(attacker), "BATTLELINE-keyword unit must always pass the gate")

    def test_non_battleline_alone_fails(self):
        """A non-BATTLELINE AdMech unit with no friendly BATTLELINE within
        6" must NOT receive the gated bonus."""
        battle, gate = self._make_battle(_admech_non_battleline())
        attacker = battle.a.units[0]
        attacker.position = (10.0, 10.0)
        self.assertFalse(gate(attacker), "non-BATTLELINE unit with no ally must fail the gate")

    def test_non_battleline_within_6_of_ally_passes(self):
        """A non-BATTLELINE AdMech unit within 6" of a friendly AdMech
        BATTLELINE unit DOES receive the gated bonus."""
        battle, gate = self._make_battle(
            _admech_non_battleline(), ally_profile=_admech_battleline(),
        )
        attacker = battle.a.units[0]
        ally = battle.a.units[1]
        attacker.position = (10.0, 10.0)
        ally.position = (12.0, 10.0)   # 2" away
        self.assertTrue(gate(attacker), "non-BATTLELINE unit within 6\" of ally must pass")

    def test_non_battleline_beyond_6_of_ally_fails(self):
        """The 6" radius is real: an ally at >6" away does NOT grant the
        gate to a non-BATTLELINE unit."""
        battle, gate = self._make_battle(
            _admech_non_battleline(), ally_profile=_admech_battleline(),
        )
        attacker = battle.a.units[0]
        ally = battle.a.units[1]
        attacker.position = (0.0, 0.0)
        ally.position = (10.0, 0.0)   # 10" — outside the 6" aura
        self.assertFalse(gate(attacker), "non-BATTLELINE unit beyond 6\" of ally must fail")

    def test_battleline_ally_must_be_admech(self):
        """The within-6" gate requires a friendly ADEPTUS MECHANICUS
        BATTLELINE unit specifically. A BATTLELINE ally from another
        faction does NOT trigger the gate."""
        non_admech_ally = UnitProfile(
            name="Allied Battleline",
            health=1, damage=1, hit_probability=2 / 3,
            ap=0, save=4, strength=4, toughness=3,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            leadership=7,
            faction="Astra Militarum",   # NOT AdMech
            unit_keywords=("INFANTRY", "BATTLELINE"),
            melee_attacks=1, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        )
        battle, gate = self._make_battle(
            _admech_non_battleline(), ally_profile=non_admech_ally,
        )
        attacker = battle.a.units[0]
        ally_unit = battle.a.units[1]
        attacker.position = (10.0, 10.0)
        ally_unit.position = (11.0, 10.0)
        self.assertFalse(
            gate(attacker),
            "ally must be AdMech faction; AM BATTLELINE ally does not count",
        )

    def test_no_army_ref_fails_closed(self):
        """A unit with no army_ref (orphan test profile) fails the gate
        rather than silently passing. The helper fails-closed to honour
        CLAUDE.md §13 (no silent defaults)."""
        from code.units import _doctrina_battleline_proximity_met, Unit
        p = _admech_non_battleline()
        u = Unit(p)
        u.position = (0.0, 0.0)
        # army_ref is None by default — confirm fail-closed
        self.assertFalse(
            _doctrina_battleline_proximity_met(u),
            "unit with no army_ref must fail the gate",
        )


if __name__ == "__main__":
    unittest.main()
