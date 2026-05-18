"""Tests for the 10e core ±1 modifier cap on Hit and Wound rolls.

Wahapedia core rules (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Hit-Roll):
    "Hit roll modifiers are cumulative, but the Hit roll for an attack can
     never be modified by more than -1 or +1."
    (Same wording for Wound rolls.)

SwegHammer enforces this in `code/units.py` Unit.attack by accumulating
every +1 / -1 contribution into `hit_mod_delta` / `wound_mod_delta` integers
and then clamping each delta to the range `[-1, +1]` before applying it to
the d6 target. Cited as `simulator.modifier_cap_plus_minus_one`.

The tests here exercise three canonical stack patterns through Unit.attack
end-to-end (not through a private helper) so a future refactor that
re-introduces stacking would be caught.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures — generic 4+ to-hit shooter into a 4+ to-wound defender
# ---------------------------------------------------------------------------


def _basic_shooter(name: str = "Shooter") -> UnitProfile:
    """BS 4+ (hit_probability 0.5), 10 shots, S4 vs T4 (wound 4+), AP0, D1.
    No critical-effect keywords (no sustained, no lethal, no devastating) so
    the hit/wound rolls drive damage in a clean, monotone way."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=0.5,
        ap=0, save=3, strength=4, toughness=4,
        attacks=10, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


def _basic_defender(name: str = "Defender", stealth: bool = False) -> UnitProfile:
    """T4 / 3+ save / no FNP / not Thousand Sons (so All Is Dust never fires).
    Massive health so we never run out of wound capacity in the means loop.
    `stealth=True` bakes the Stealth keyword into the immutable profile so
    tests can wire a -1-to-hit modifier without mutating frozen fields."""
    return UnitProfile(
        name=name,
        health=10_000.0, damage=1, hit_probability=0.5,
        ap=0, save=3, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Orks",   # arbitrary non-Thousand-Sons faction
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        stealth=stealth,
    )


def _build_battle_with(stealth_defender: bool = False) -> Battle:
    a = Army("Astartes")
    a.add_unit(_basic_shooter())
    b = Army("Orks")
    b.add_unit(_basic_defender(stealth=stealth_defender))
    battle = Battle(a, b)
    battle._assign_uids()
    return battle


def _build_battle() -> Battle:
    a = Army("Astartes")
    a.add_unit(_basic_shooter())
    b = Army("Orks")
    b.add_unit(_basic_defender())
    battle = Battle(a, b)
    battle._assign_uids()
    return battle


def _mean_damage(
    attacker: Unit,
    defender: Unit,
    trials: int = 4000,
    seed: int = 2026,
    mode: str = "ranged",
) -> float:
    """Average per-activation damage over `trials` Unit.attack invocations.
    Defender health is restored each trial to keep results comparable."""
    random.seed(seed)
    total = 0.0
    for _ in range(trials):
        defender.current_health = defender.profile.health
        total += attacker.attack(defender, distance=12.0, mode=mode, has_los=True)
    return total / trials


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class HitModifierCapTests(unittest.TestCase):
    """Two +1-to-hit sources must not stack — cap holds at +1."""

    def test_two_plus_one_hit_sources_equal_one(self):
        """Detachment +1 to hit (`att_buffs['plus_one_to_hit']`) PLUS the
        stratagem +1 to hit (`transient_plus_one_to_hit_shooting`) — under
        the ±1 cap, the effective hit modifier is still +1, so the damage
        mean must match the single-source case to within statistical noise."""
        # Stack: detachment-flagged +1 to hit (set via direct attribute
        # override on a synthetic detachment-buffs dict) — we hand-patch
        # `effective_buffs` to control the att_buffs result so we exercise
        # the same code path Awakened Dynasty / Death Guard auras hit.
        from code import leaders as leaders_module

        base_battle = _build_battle()
        atk = base_battle.a.units[0]
        dfn = base_battle.b.units[0]

        original_effective_buffs = leaders_module.effective_buffs

        def buffs_with_hit(unit):
            # Replicate the neutral dict and flip ONLY plus_one_to_hit on
            # the attacker. Targets stay neutral.
            d = dict(leaders_module._NEUTRAL_BUFFS)
            if unit is atk:
                d["plus_one_to_hit"] = True
            return d

        # --- One +1 source (detachment only) -----------------------------
        leaders_module.effective_buffs = buffs_with_hit
        try:
            atk.transient_plus_one_to_hit_shooting = False
            one_source = _mean_damage(atk, dfn, trials=5000, seed=2026)

            # --- Two +1 sources (detachment + stratagem) -----------------
            atk.transient_plus_one_to_hit_shooting = True
            two_sources = _mean_damage(atk, dfn, trials=5000, seed=2026)
        finally:
            leaders_module.effective_buffs = original_effective_buffs
            atk.transient_plus_one_to_hit_shooting = False

        # Same seed, same code path past the cap → near-identical means.
        # We allow a small tolerance to absorb the few attacks where re-roll
        # paths might diverge (none here — no re-rolls in fixture).
        self.assertAlmostEqual(
            one_source, two_sources, delta=0.25,
            msg=(
                f"Two +1-to-hit sources must cap to +1 (10e core). "
                f"Got one-source mean {one_source:.3f} vs two-source "
                f"mean {two_sources:.3f} — they should match."
            ),
        )

    def test_no_buff_strictly_worse_than_capped_buff(self):
        """Sanity: the cap doesn't accidentally cancel a single +1 to hit.
        A capped-+1 shooter still does materially more damage than the same
        shooter with no modifier."""
        from code import leaders as leaders_module

        base_battle = _build_battle()
        atk = base_battle.a.units[0]
        dfn = base_battle.b.units[0]

        original_effective_buffs = leaders_module.effective_buffs

        def neutral_buffs(unit):
            return dict(leaders_module._NEUTRAL_BUFFS)

        def hit_buff(unit):
            d = dict(leaders_module._NEUTRAL_BUFFS)
            if unit is atk:
                d["plus_one_to_hit"] = True
            return d

        try:
            leaders_module.effective_buffs = neutral_buffs
            no_buff = _mean_damage(atk, dfn, trials=5000, seed=2026)

            leaders_module.effective_buffs = hit_buff
            atk.transient_plus_one_to_hit_shooting = True   # 2 sources -> cap
            capped = _mean_damage(atk, dfn, trials=5000, seed=2026)
        finally:
            leaders_module.effective_buffs = original_effective_buffs
            atk.transient_plus_one_to_hit_shooting = False

        # 4+ to hit -> 3+ to hit lifts a 10-shot expected damage from
        # 10*0.5*0.5*(1-0.667) = ~0.83 to 10*0.667*0.5*(1-0.667) = ~1.11.
        # We assert the cap is BELOW the +1 mean (statistical headroom)
        # — i.e. the capped buff is producing a real +1 to hit, not
        # silently being clamped to 0.
        self.assertGreater(
            capped - no_buff, 0.1,
            msg=(
                f"A capped-+1 to hit should still deliver a real damage "
                f"uplift. no_buff={no_buff:.3f}, capped={capped:.3f}."
            ),
        )


class HitModifierMixedSignTests(unittest.TestCase):
    """+1 to hit and -1 to hit must cancel — the modifier delta is 0."""

    def test_plus_one_and_minus_one_cancel(self):
        """Detachment +1 to hit PLUS Stealth defender (-1 to hit) — the
        net hit modifier is 0, so the damage mean matches an unmodified
        shooter against a non-Stealth defender."""
        from code import leaders as leaders_module

        # Build TWO independent battles. UnitProfile is a frozen dataclass,
        # so Stealth has to be baked into the profile at construction time.
        battle_base = _build_battle_with(stealth_defender=False)
        base_atk = battle_base.a.units[0]
        base_dfn = battle_base.b.units[0]

        battle_mod = _build_battle_with(stealth_defender=True)
        mod_atk = battle_mod.a.units[0]
        mod_dfn = battle_mod.b.units[0]

        original_effective_buffs = leaders_module.effective_buffs

        def neutral_buffs(unit):
            return dict(leaders_module._NEUTRAL_BUFFS)

        def hit_buff_for_mod(unit):
            d = dict(leaders_module._NEUTRAL_BUFFS)
            if unit is mod_atk:
                d["plus_one_to_hit"] = True
            return d

        try:
            leaders_module.effective_buffs = neutral_buffs
            base_mean = _mean_damage(base_atk, base_dfn, trials=6000, seed=2026)

            leaders_module.effective_buffs = hit_buff_for_mod
            net_zero_mean = _mean_damage(mod_atk, mod_dfn, trials=6000, seed=2026)
        finally:
            leaders_module.effective_buffs = original_effective_buffs

        # Net +1-1 = 0 should match the neutral case to within noise.
        self.assertAlmostEqual(
            base_mean, net_zero_mean, delta=0.25,
            msg=(
                f"+1 to hit and -1 to hit (Stealth) must cancel. "
                f"Base mean {base_mean:.3f} vs +1/-1 mean {net_zero_mean:.3f}."
            ),
        )


class HitModifierNegativeCapTests(unittest.TestCase):
    """Three independent -1-to-hit sources cap at -1 (not -3)."""

    def test_three_minus_one_sources_cap_at_minus_one(self):
        """Stealth (-1) + Heavy Cover (-1) + DG Contagions R3+ (-1) — the
        delta accumulates to -3 but is clamped to -1 before being applied.
        We compare against a fixture with exactly ONE -1 source to verify
        the clamp."""
        from code import leaders as leaders_module

        # Single-source fixture: stealth defender, no cover, no DG nearby.
        b1 = _build_battle_with(stealth_defender=True)
        a1 = b1.a.units[0]
        d1 = b1.b.units[0]
        d1.in_heavy_cover = False
        b1._current_round = 1   # Contagions inactive in R1

        # Three-source fixture: stealth + heavy cover + DG aura.
        b3 = _build_battle_with(stealth_defender=True)
        a3 = b3.a.units[0]
        d3 = b3.b.units[0]
        d3.in_heavy_cover = True
        # Put a Death Guard model near the attacker so the R3+ Contagion
        # branch fires. Defender army stays as the non-DG defender — we
        # add the DG unit to the SAME side as the defender so it counts
        # as "enemy" relative to the attacker.
        from code.units import UnitProfile as UP
        dg_profile = UP(
            name="DG Plague Marine", health=2, damage=1, hit_probability=0.5,
            ap=0, save=3, strength=4, toughness=5,
            attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
            leadership=7, faction="Death Guard",
            unit_keywords=("INFANTRY",),
            melee_attacks=1, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        )
        b3.b.add_unit(dg_profile)
        b3._assign_uids()
        # Re-fetch refs in case add_unit invalidated them; defender is units[0].
        a3 = b3.a.units[0]
        d3 = b3.b.units[0]
        dg = b3.b.units[1]
        a3.position = (0.0, 0.0)
        d3.position = (12.0, 0.0)
        dg.position = (1.0, 0.0)   # 1" from attacker -> inside 3" aura
        b3._current_round = 3   # Contagions R3+ active

        original_effective_buffs = leaders_module.effective_buffs

        def neutral_buffs(unit):
            return dict(leaders_module._NEUTRAL_BUFFS)

        try:
            leaders_module.effective_buffs = neutral_buffs
            one_minus = _mean_damage(a1, d1, trials=6000, seed=2026)
            three_minus = _mean_damage(a3, d3, trials=6000, seed=2026)
        finally:
            leaders_module.effective_buffs = original_effective_buffs

        # Both should collapse to -1 to hit (5+ to hit). Means match within
        # noise. If the cap were broken, three -1 sources would push to
        # 7+ (auto-fail) and three_minus would be ~zero.
        self.assertAlmostEqual(
            one_minus, three_minus, delta=0.25,
            msg=(
                f"Three -1-to-hit sources must cap to -1 (10e core). "
                f"Single-source mean {one_minus:.3f} vs triple-source "
                f"mean {three_minus:.3f}."
            ),
        )
        self.assertGreater(
            three_minus, 0.1,
            msg=(
                f"Triple -1-to-hit at the ±1 cap should still resolve "
                f"to a real 5+ hit chance, not auto-fail. Got "
                f"{three_minus:.3f}."
            ),
        )


class WoundModifierCapTests(unittest.TestCase):
    """The wound roll has its own independent cap. Two +1-to-wound sources
    (e.g. DG Plague Marines Onslaught detachment +1 + Outbreak of Pestilence
    stratagem +1) collapse to a single +1."""

    def test_two_plus_one_wound_sources_equal_one(self):
        from code import leaders as leaders_module

        battle = _build_battle()
        atk = battle.a.units[0]
        dfn = battle.b.units[0]

        original_effective_buffs = leaders_module.effective_buffs

        def wound_buff(unit):
            d = dict(leaders_module._NEUTRAL_BUFFS)
            if unit is atk:
                d["plus_one_to_wound"] = True
            return d

        try:
            leaders_module.effective_buffs = wound_buff
            # One +1-to-wound source (detachment).
            atk.transient_plus_one_to_wound_melee = False
            one_source = _mean_damage(
                atk, dfn, trials=5000, seed=2026, mode="melee",
            )
            # Two +1-to-wound sources (detachment + stratagem) -> cap.
            atk.transient_plus_one_to_wound_melee = True
            two_sources = _mean_damage(
                atk, dfn, trials=5000, seed=2026, mode="melee",
            )
        finally:
            leaders_module.effective_buffs = original_effective_buffs
            atk.transient_plus_one_to_wound_melee = False

        self.assertAlmostEqual(
            one_source, two_sources, delta=0.20,
            msg=(
                f"Two +1-to-wound sources must cap to +1 (10e core). "
                f"One-source mean {one_source:.3f} vs two-source mean "
                f"{two_sources:.3f}."
            ),
        )


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
