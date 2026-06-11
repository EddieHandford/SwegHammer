"""Regression tests for wave 235: four fabricated Necron leader ability flags removed.

The four fabrications removed:

  1. Overlord plus_one_to_hit=True
     Real "My Will Be Done" is a once-per-round Stratagem command-point
     discount, not a hit-roll aura.

  2. Trazyn the Infinite plus_one_to_hit=True
     Real abilities are Ancient Collector (sticky objective count) and
     Surrogate Hosts (once-per-battle 2+ self-revive to half wounds).
     Neither grants a to-hit aura. Trazyn's cp_refund_per_battle=1
     (Surreptitious Acquisition) is retained and tested.

  3. Chronomancer fnp=5
     Real "Chronometron" is a post-Shooting-phase 5-inch Normal move,
     not a feel no pain save.

  4. Plasmancer fnp=5
     Real "Harbinger of Destruction" lowers the ranged Critical Hit
     threshold to 5+ on the led unit's ranged attacks. The faithful
     rebuild requires new machinery (a ranged_crit_threshold_aura field
     plus a new att_buffs read in the ranged crit branch of code/units.py);
     per the wave 235 briefing, removal only is correct here.

All four entries are retained in the registry so lookup_ability resolves
cleanly per CLAUDE.md rule 13 (fail loud — no silent defaults).

BSData v10.6.0 Necrons.cat.gz confirms the verbatim rule text for each
entry; STRUCTURAL_DEBT_REVIEW.md orchestrator cross-verification log holds
the four verbatim quotes.
"""

from __future__ import annotations

import unittest

from code.leaders import lookup_ability


class OverlordFabricationRemovalTests(unittest.TestCase):
    """Overlord plus_one_to_hit must be absent after wave 235."""

    def test_overlord_resolves(self):
        ab = lookup_ability("Overlord")
        self.assertIsNotNone(
            ab,
            "Overlord must resolve from the registry (CLAUDE.md rule 13 fail-loud)",
        )

    def test_overlord_no_plus_one_to_hit(self):
        ab = lookup_ability("Overlord")
        self.assertFalse(
            ab.plus_one_to_hit,
            "Overlord plus_one_to_hit must be False — My Will Be Done is a "
            "Stratagem command-point discount, not a hit-roll aura "
            "(wave 235 fabrication removal)",
        )

    def test_overlord_no_fnp(self):
        ab = lookup_ability("Overlord")
        self.assertEqual(
            ab.fnp, 7,
            "Overlord must have no feel no pain (fnp=7 means none) after "
            "wave 235; no feel no pain was fabricated but the canonical "
            "value is the default 7",
        )

    def test_overlord_host_keys_retained(self):
        ab = lookup_ability("Overlord")
        self.assertTrue(
            len(ab.host_keys) > 0,
            "Overlord host_keys must be non-empty — the entry is retained "
            "for is_actually_led gating (Necron Warriors, Immortals, Lychguard)",
        )


class TrazynFabricationRemovalTests(unittest.TestCase):
    """Trazyn the Infinite plus_one_to_hit must be absent; cp_refund_per_battle=1 retained."""

    def test_trazyn_resolves(self):
        ab = lookup_ability("Trazyn the Infinite")
        self.assertIsNotNone(
            ab,
            "Trazyn the Infinite must resolve from the registry (CLAUDE.md rule 13)",
        )

    def test_trazyn_no_plus_one_to_hit(self):
        ab = lookup_ability("Trazyn the Infinite")
        self.assertFalse(
            ab.plus_one_to_hit,
            "Trazyn plus_one_to_hit must be False — Ancient Collector and "
            "Surrogate Hosts do not grant a to-hit aura "
            "(wave 235 fabrication removal)",
        )

    def test_trazyn_cp_refund_retained(self):
        ab = lookup_ability("Trazyn the Infinite")
        self.assertEqual(
            ab.cp_refund_per_battle, 1,
            "Trazyn cp_refund_per_battle=1 (Surreptitious Acquisition) must "
            "be retained — this is the faithful command-point steal mechanic, "
            "not a fabrication",
        )

    def test_trazyn_host_keys_retained(self):
        ab = lookup_ability("Trazyn the Infinite")
        self.assertTrue(
            len(ab.host_keys) > 0,
            "Trazyn host_keys must be non-empty — entry retained for "
            "is_actually_led gating",
        )


class ChronomangerFabricationRemovalTests(unittest.TestCase):
    """Chronomancer fnp=5 must be absent after wave 235."""

    def test_chronomancer_resolves(self):
        ab = lookup_ability("Chronomancer")
        self.assertIsNotNone(
            ab,
            "Chronomancer must resolve from the registry (CLAUDE.md rule 13)",
        )

    def test_chronomancer_no_fnp(self):
        ab = lookup_ability("Chronomancer")
        self.assertEqual(
            ab.fnp, 7,
            "Chronomancer fnp must be 7 (none) — Chronometron is a "
            "post-Shooting 5-inch Normal move, not a feel no pain save "
            "(wave 235 fabrication removal)",
        )

    def test_chronomancer_no_plus_one_to_hit(self):
        ab = lookup_ability("Chronomancer")
        self.assertFalse(
            ab.plus_one_to_hit,
            "Chronomancer must not carry plus_one_to_hit — no hit-roll "
            "aura is present in the real Chronometron rule",
        )

    def test_chronomancer_host_keys_retained(self):
        ab = lookup_ability("Chronomancer")
        self.assertTrue(
            len(ab.host_keys) > 0,
            "Chronomancer host_keys must be non-empty — entry retained for "
            "is_actually_led gating",
        )


class PlasmancerFabricationRemovalTests(unittest.TestCase):
    """Plasmancer fnp=5 must be absent after wave 235.

    The real Harbinger of Destruction lowers the ranged Critical Hit
    threshold to 5+; this requires new machinery (ranged_crit_threshold_aura
    field on LeaderAbility plus a new att_buffs read in code/units.py) so
    the wave 235 fix is removal-only — no rebuild wired.
    """

    def test_plasmancer_resolves(self):
        ab = lookup_ability("Plasmancer")
        self.assertIsNotNone(
            ab,
            "Plasmancer must resolve from the registry (CLAUDE.md rule 13)",
        )

    def test_plasmancer_no_fnp(self):
        ab = lookup_ability("Plasmancer")
        self.assertEqual(
            ab.fnp, 7,
            "Plasmancer fnp must be 7 (none) — Harbinger of Destruction is a "
            "ranged crit-hit-threshold lowering ability (5+ instead of 6), "
            "not a feel no pain save (wave 235 fabrication removal)",
        )

    def test_plasmancer_no_plus_one_to_hit(self):
        ab = lookup_ability("Plasmancer")
        self.assertFalse(
            ab.plus_one_to_hit,
            "Plasmancer must not carry plus_one_to_hit — the real rule is a "
            "ranged crit-hit threshold change, not a flat hit modifier",
        )

    def test_plasmancer_host_keys_retained(self):
        ab = lookup_ability("Plasmancer")
        self.assertTrue(
            len(ab.host_keys) > 0,
            "Plasmancer host_keys must be non-empty — entry retained for "
            "is_actually_led gating (Immortals, Necron Warriors)",
        )

    def test_technomancer_fnp_unaffected(self):
        """Technomancer fnp=5 is the FAITHFUL codex rule (Rites of Reanimation:
        'While this model is leading a unit, models in that unit have the
        Feel No Pain 5+ ability.') — it must NOT have been collateral-removed.
        """
        ab = lookup_ability("Technomancer")
        self.assertIsNotNone(ab, "Technomancer must resolve from the registry")
        self.assertEqual(
            ab.fnp, 5,
            "Technomancer fnp must remain 5 — Rites of Reanimation is a "
            "faithful feel no pain grant per the BSData v10.6.0 codex text; "
            "wave 235 must NOT have altered it",
        )


if __name__ == "__main__":
    unittest.main()
