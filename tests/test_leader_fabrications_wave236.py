"""Wave 236 leader fabrication removal lock-in tests.

Two fabricated leader ability proxies are dropped in wave 236:

  Fix A — Farseer "Branching Fates": the prior reroll_wound_ones=True was an
    always-on wound-reroll aura. The real ability is once-per-phase set-one-
    roll-to-6 (verified against Wahapedia and BSData v10.6.0). No matching
    simulator field exists; proxy removed. Registry entry retained for
    is_actually_led host-key gating.

  Fix B — Chaos Lord "Lord of Chaos": the prior plus_one_to_wound=True was a
    flavour proxy for a once-per-battle-round Stratagem command-point-discount
    ability (verified against Wahapedia and BSData v10.6.0, ability id
    73e9-284e-fd62-4056). No offensive aura component in the real rule. Proxy
    removed. Host routing corrected from the dormant
    chaos_space_marines_traitor_guardsmen_squad key to the codex-accurate
    chaos_space_marines_legionaries + chaos_space_marines_chosen pair.

Both tests are tripwires: if a proxy is re-added without first wiring the real
codex mechanic into the simulator, these tests fail immediately.
"""

from __future__ import annotations

import unittest

from code.leaders import lookup_ability


class FarseeBranchingFatesRemovalTests(unittest.TestCase):
    """Fix A: Farseer reroll_wound_ones was a fabricated always-on proxy.

    Branching Fates is once-per-phase set-one-roll-to-6; the simulator has no
    such hook. Proxy removed in wave 236.
    """

    def test_farseer_reroll_wound_ones_is_false(self):
        """The Farseer registry entry must NOT carry reroll_wound_ones."""
        ab = lookup_ability("Farseer")
        self.assertIsNotNone(ab, "Farseer must remain in the registry")
        self.assertFalse(
            ab.reroll_wound_ones,
            "Farseer reroll_wound_ones must be False — Branching Fates is a "
            "once-per-phase set-one-roll-to-6 ability, not an always-on "
            "wound-reroll aura. Fabricated proxy removed in wave 236.",
        )

    def test_farseer_registry_entry_retained(self):
        """The Farseer entry must still be in the registry (host-key gating)."""
        ab = lookup_ability("Farseer")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.aura_range, 6.0,
            "Farseer aura_range must remain 6.0 for is_actually_led gating")

    def test_farseer_no_offensive_flags(self):
        """All offensive aura flags must be absent — Branching Fates carries none."""
        ab = lookup_ability("Farseer")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_wound_ones)
        self.assertFalse(ab.reroll_hit_ones)
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)
        self.assertEqual(ab.plus_one_attack, 0)


class ChaosLordLordOfChaosRemovalTests(unittest.TestCase):
    """Fix B: Chaos Lord plus_one_to_wound was a fabricated flavour proxy.

    Lord of Chaos is a once-per-battle-round Stratagem command-point-discount
    (BSData v10.6.0 ability id 73e9-284e-fd62-4056; Wahapedia confirmed). No
    offensive aura component in the real rule. Proxy removed in wave 236.
    Host routing corrected to legionaries + chosen per BSData Leader text.
    """

    def test_chaos_lord_plus_one_to_wound_is_false(self):
        """The Chaos Lord registry entry must NOT carry plus_one_to_wound."""
        ab = lookup_ability("Chaos Lord")
        self.assertIsNotNone(ab, "Chaos Lord must remain in the registry")
        self.assertFalse(
            ab.plus_one_to_wound,
            "Chaos Lord plus_one_to_wound must be False — Lord of Chaos is a "
            "once-per-battle-round Stratagem command-point-discount ability, "
            "not a wound-roll aura. Fabricated proxy removed in wave 236.",
        )

    def test_chaos_lord_registry_entry_retained(self):
        """The Chaos Lord entry must still be in the registry (host-key gating)."""
        ab = lookup_ability("Chaos Lord")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.aura_range, 6.0,
            "Chaos Lord aura_range must remain 6.0 for is_actually_led gating")

    def test_chaos_lord_no_offensive_flags(self):
        """All offensive aura flags must be absent — Lord of Chaos carries none."""
        ab = lookup_ability("Chaos Lord")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.plus_one_to_wound)
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.reroll_hit_ones)
        self.assertFalse(ab.reroll_wound_ones)
        self.assertEqual(ab.plus_one_attack, 0)

    def test_chaos_lord_host_keys_contain_legionaries(self):
        """Host routing must include legionaries — the codex-accurate attachment target."""
        ab = lookup_ability("Chaos Lord")
        self.assertIsNotNone(ab)
        self.assertIn(
            "chaos_space_marines_legionaries",
            ab.host_keys,
            "Chaos Lord host_keys must include chaos_space_marines_legionaries "
            "(BSData v10.6.0 Leader text: 'CHOSEN / LEGIONARIES'). "
            "Prior routing to traitor_guardsmen_squad was dormant and wrong.",
        )

    def test_chaos_lord_host_keys_contain_chosen(self):
        """Host routing must include chosen — the codex-accurate attachment target."""
        ab = lookup_ability("Chaos Lord")
        self.assertIsNotNone(ab)
        self.assertIn(
            "chaos_space_marines_chosen",
            ab.host_keys,
            "Chaos Lord host_keys must include chaos_space_marines_chosen "
            "(BSData v10.6.0 Leader text: 'CHOSEN / LEGIONARIES').",
        )

    def test_chaos_lord_host_keys_exclude_traitor_guardsmen(self):
        """The dormant mis-routed key must no longer be present."""
        ab = lookup_ability("Chaos Lord")
        self.assertIsNotNone(ab)
        self.assertNotIn(
            "chaos_space_marines_traitor_guardsmen_squad",
            ab.host_keys,
            "chaos_space_marines_traitor_guardsmen_squad was a mis-routed key "
            "that caused the Chaos Lord's aura to fire on absent units. "
            "Corrected to legionaries + chosen in wave 236.",
        )


if __name__ == "__main__":
    unittest.main()
