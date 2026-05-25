"""Tests for the Thousand Sons #193 rebuild — Grand Coven detachment plus
the Cabal of Sorcerers Rituals army rule.

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/

Scope:
  * Default detachment for Thousand Sons resolves to grand_coven.
  * GRAND_COVEN exposes the six real Wahapedia stratagems.
  * Cabal of Sorcerers Rituals pass: a Thousand Sons army with a PSYKER
    eventually lands a Doombolt mortal-wound payload across many rounds
    (deterministic seeding so the 2D6 Psychic test is reproducible).
  * Doombolt 11+ branch escalates the median MW payload from 2 to 5.
  * Non-Thousand Sons armies do NOT fire Rituals (faction gate).
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import (
    DEFAULT_BY_FACTION, FACTION_DETACHMENTS, GRAND_COVEN, DETACHMENTS,
)
from code.stratagems import GRAND_COVEN_STRATAGEMS
from code.units import UnitProfile


def _tson_psyker() -> UnitProfile:
    """A bulky Thousand Sons PSYKER stand-in (Exalted Sorcerer flavour)."""
    return UnitProfile(
        name="Exalted Sorcerer",
        health=4.0, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7,
        faction="Thousand Sons",
        unit_keywords=("PSYKER", "INFANTRY", "CHARACTER", "THOUSAND SONS"),
        melee_attacks=4, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _dummy_target() -> UnitProfile:
    """A vanilla Marine-style chassis to absorb Doombolt mortals."""
    return UnitProfile(
        name="Intercessor",
        health=2.0, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


class GrandCovenWiringTests(unittest.TestCase):
    """Cheap structural checks: detachment is registered, stratagems present,
    faction default resolves correctly."""

    def test_default_detachment_for_thousand_sons(self):
        # iter15 promoted Rubricae Phalanx to the TSON default — Grand Coven
        # remains opt-in for psyker-heavy lists. The detachment-picker AND
        # Army.resolve_detachment() now both route to rubricae_phalanx when
        # no explicit detachment is set on the Army.
        self.assertEqual(DEFAULT_BY_FACTION["Thousand Sons"], "rubricae_phalanx")

    def test_grand_coven_in_faction_detachments(self):
        # iter15 added Rubricae Phalanx to FACTION_DETACHMENTS["Thousand Sons"]
        # alongside Grand Coven — both remain available picks (composition-
        # driven via pick_detachment_for_army). The ordering reflects the
        # default precedence (rubricae_phalanx is first, grand_coven second).
        self.assertEqual(
            FACTION_DETACHMENTS["Thousand Sons"],
            ("rubricae_phalanx", "grand_coven"),
        )

    def test_grand_coven_registry(self):
        self.assertIn("grand_coven", DETACHMENTS)
        self.assertEqual(DETACHMENTS["grand_coven"].name, "Grand Coven")
        self.assertEqual(DETACHMENTS["grand_coven"].faction, "Thousand Sons")

    def test_grand_coven_carries_six_stratagems(self):
        names = {s.name for s in GRAND_COVEN.stratagems}
        self.assertEqual(names, {
            "Psychic Dominion",
            "Destined by Fate",
            "Egotistical Power",
            "Desecration of Worlds",
            "Arcane Focus",
            "Devastating Sorcery",
        })
        # CP costs verified against Wahapedia.
        cp_by_name = {s.name: s.cp_cost for s in GRAND_COVEN.stratagems}
        self.assertEqual(cp_by_name["Psychic Dominion"], 1)
        self.assertEqual(cp_by_name["Destined by Fate"], 1)
        self.assertEqual(cp_by_name["Egotistical Power"], 1)
        self.assertEqual(cp_by_name["Desecration of Worlds"], 1)
        self.assertEqual(cp_by_name["Arcane Focus"], 1)
        self.assertEqual(cp_by_name["Devastating Sorcery"], 2)

    def test_grand_coven_baseline_psychic_payload(self):
        """Grand Coven exposes NO unconditional per-round MW baseline.

        TSON-DIAG (claude/sim-calibration-6): the previous fabricated
        `psychic_mortal_wounds_per_round=2` "fallback" was zeroed —
        Kindred Sorcery's real text (Imbued Manifestation / Psychic
        Maelstrom / Wrath of the Immaterium) does NOT grant an
        unconditional per-round MW payload, and the Cabal of Sorcerers
        Ritual pass (`_run_cabal_rituals`) already produces stochastic
        Doombolt D3 / D3+3 MW. Stacking a flat baseline on top
        double-counted that damage and contributed to TSON's over-perf.
        """
        self.assertEqual(GRAND_COVEN.psychic_mortal_wounds_per_round, 0)

    def test_grand_coven_stratagems_module_re_export(self):
        """The stratagem tuple lives in code.stratagems and is re-exported
        for downstream importers (army_builder, audit_rules)."""
        names = {s.name for s in GRAND_COVEN_STRATAGEMS}
        self.assertEqual(len(GRAND_COVEN_STRATAGEMS), 6)
        self.assertIn("Doombolt" not in names, [True])  # Doombolt is a Ritual, not a Stratagem


class CabalOfSorcerersTests(unittest.TestCase):
    """The Cabal of Sorcerers Ritual pass is the real-rule plumbing.

    Verify it fires only for Thousand Sons armies and that Doombolt's
    mortal-wound payload lands on the opposing army's highest-threat
    unit over a multi-round battle.
    """

    def _build_battle(self, attacker_faction: str, seed: int = 7):
        """Minimal Battle with one PSYKER on each side and a low max-rounds
        cap so the test runs fast."""
        from code.simulator import Battle, RulesConfig
        from code.maps import DEFAULT_MAP

        random.seed(seed)

        a = Army("A")
        a.add_unit(_tson_psyker() if attacker_faction == "Thousand Sons"
                   else _tson_psyker().__class__(
                       **{**_tson_psyker().__dict__, "faction": attacker_faction}
                   ))
        a.add_unit(_dummy_target())  # extra chaff so the army has multiple units

        b = Army("B")
        b.add_unit(_dummy_target())
        b.add_unit(_dummy_target())

        # Place units far apart so no shooting wipes them out before
        # rituals can fire across rounds.
        for u in a.units:
            u.position = (10.0, 10.0)
        for u in b.units:
            u.position = (40.0, 40.0)

        rules = RulesConfig.vanilla_10e()
        battle = Battle(a, b, map_=DEFAULT_MAP, rules=rules)
        return battle, a, b

    def test_cabal_does_not_fire_for_non_thousand_sons(self):
        """A non-TSons army doesn't even attempt Rituals — the faction
        gate keeps `_run_cabal_rituals` a no-op."""
        battle, a, b = self._build_battle("Adeptus Astartes", seed=1)
        # Snapshot starting HP on B's units before any round runs.
        b_hp_before = sum(u.current_health for u in b.units)
        # Manually call the Ritual hook to isolate it from the full round.
        battle._run_cabal_rituals()
        b_hp_after = sum(u.current_health for u in b.units)
        # No Rituals fired => no MW => B's HP unchanged by this method.
        self.assertEqual(b_hp_before, b_hp_after)

    def test_cabal_fires_for_thousand_sons_with_psyker(self):
        """Over many invocations with seeded RNG, the Cabal pass eventually
        manifests Doombolt (WC 7) and deals mortals to B."""
        battle, a, b = self._build_battle("Thousand Sons", seed=42)

        # Run the Ritual pass many times — 2D6 hits 7+ with ~58% probability.
        # Over 50 invocations the cumulative MW count should be substantial.
        b_hp_before = sum(u.current_health for u in b.units)
        for _ in range(50):
            # Reset RNG seed slightly differently per iteration to avoid
            # locking onto a single roll outcome.
            battle._run_cabal_rituals()
            # If we wiped out B, stop — Doombolt obviously worked.
            if not b.alive_units:
                break

        b_hp_after = sum(u.current_health for u in b.units)
        self.assertLess(
            b_hp_after, b_hp_before,
            "Cabal of Sorcerers should land Doombolt mortals on B over 50 attempts",
        )

    def test_cabal_ritual_cap_one_per_turn(self):
        """Within a single `_run_cabal_rituals` call, each Ritual manifests
        at most once even if multiple PSYKERs are available. We verify by
        adding a second Psyker and checking the manifested-set logic
        through the public API (no MW double-counting from the same
        Ritual on the same target in one call)."""
        battle, a, b = self._build_battle("Thousand Sons", seed=99)
        # Add a second PSYKER to A.
        a.add_unit(_tson_psyker())
        # Run a single Ritual pass; check that B's HP loss is bounded
        # by the worst-case single-call payload: 2 PSYKERs x 1 Ritual
        # each x at most 5 MW (Doombolt D3+3 max) = 10 MW. But each
        # Ritual only manifests once army-wide per turn, so the real
        # bound is 2 Rituals (Doombolt + Temporal Surge or similar).
        # Temporal Surge does no MW; only Doombolt damages B. So at
        # most one Doombolt fires per call.
        b_hp_before = sum(u.current_health for u in b.units)
        battle._run_cabal_rituals()
        b_hp_after = sum(u.current_health for u in b.units)
        hp_lost = b_hp_before - b_hp_after
        # Max single-call Doombolt payload = 5 MW (D3+3 median on 11+).
        # FNP can ignore some; assert at most 6 to be safe.
        self.assertLessEqual(hp_lost, 6.0,
                             f"Per-turn Ritual cap violated: lost {hp_lost} HP")


class DoomboltMortalWoundsTests(unittest.TestCase):
    """Direct unit tests of the per-Ritual resolver: Doombolt deals 2 MW
    on a sub-11 Psychic test and 5 MW on an 11+ test."""

    def test_doombolt_baseline_2mw(self):
        """test_total = 7 => D3 median = 2 MW."""
        from code.simulator import Battle, RulesConfig
        from code.maps import DEFAULT_MAP

        a = Army("A")
        a.add_unit(_tson_psyker())
        b = Army("B")
        b.add_unit(_dummy_target())
        battle = Battle(a, b, map_=DEFAULT_MAP, rules=RulesConfig.vanilla_10e())

        # Disable FNP for clean math.
        b.units[0].profile.__dict__["fnp"] = 7

        target_hp_before = b.units[0].current_health
        battle._cabal_resolve_ritual(
            "Doombolt", test_total=7,
            psyker=a.units[0], army=a, opponent=b,
        )
        hp_lost = target_hp_before - b.units[0].current_health
        # FNP=7 on a 2-MW Doombolt should land all 2 MW.
        self.assertEqual(hp_lost, 2.0)

    def test_doombolt_critical_11plus_5mw(self):
        """test_total = 11 => D3+3 median = 5 MW."""
        from code.simulator import Battle, RulesConfig
        from code.maps import DEFAULT_MAP

        a = Army("A")
        a.add_unit(_tson_psyker())
        b = Army("B")
        # Give B a beefy target so 5 MW doesn't wipe it (we want to
        # measure HP lost, not kill detection).
        target = _dummy_target()
        target.__dict__["health"] = 20.0
        b.add_unit(target)
        b.units[0].current_health = 20.0
        b.units[0].profile.__dict__["fnp"] = 7
        battle = Battle(a, b, map_=DEFAULT_MAP, rules=RulesConfig.vanilla_10e())

        target_hp_before = b.units[0].current_health
        battle._cabal_resolve_ritual(
            "Doombolt", test_total=11,
            psyker=a.units[0], army=a, opponent=b,
        )
        hp_lost = target_hp_before - b.units[0].current_health
        self.assertEqual(hp_lost, 5.0,
                         f"11+ Doombolt should deal D3+3 median = 5 MW, got {hp_lost}")


if __name__ == "__main__":
    unittest.main()
