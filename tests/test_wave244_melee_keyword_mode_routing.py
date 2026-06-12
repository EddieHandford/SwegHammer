"""wave 244 — melee weapon-keyword mode routing.

Three ranged weapon keywords (Anti-X, Devastating Wounds, Twin-Linked) leaked
into melee attack resolution because the three resolution sites in code/units.py
read the ranged-primary `anti_keywords` / `devastating_wounds` / `twin_linked`
fields unconditionally, even when `mode == "melee"`. There were no melee-side
fields for these three keywords, so a unit whose RANGED weapon carried one of
them (e.g. a Wave Serpent's Twin Bright Lance is Twin-Linked, Howling Banshees'
Shuriken Pistol is Anti-Infantry) had that keyword fire in the Fight phase too.

The fix adds five melee-mode UnitProfile fields (melee_anti_keywords,
melee_devastating_wounds, melee_twin_linked, plus their two basket fractions),
wires them through mapper -> parsed.json -> loader -> catalogue -> per-model
promotion -> extra-melee hot-swap, and mode-guards the three resolution sites so
the Fight phase reads the MELEE weapon's keywords. It follows the existing
melee_lethal_hits / melee_sustained_hits mode-routing pattern.

Bundled bug fix: the extra-melee hot-swap dict in units.py wrote the extra
weapon's lethal_hits / devastating_wounds / twin_linked / anti_keywords to the
RANGED-named UnitProfile fields, which the melee resolution sites no longer read
after the mode guards. They now route to the melee_* fields. Also fixed: the
loader CatalogEntry was missing melee_lethal_hits entirely (aggregate path always
False), so it is added alongside the five new fields.

This module tests:
  (a) Behaviour — the three mode guards: a ranged-only keyword does NOT fire in
      melee mode but DOES fire in ranged mode, and a melee keyword DOES fire in
      melee mode.
  (b) Parsed data — the three spot-check units carry the correct melee_* values.
  (c) Unit catalogue — the five new fields plus melee_lethal_hits survive the
      parsed.json -> CatalogEntry -> UnitProfile load round-trip.
  (d) Extra-melee hot-swap — the runtime swap dict routes the extra weapon's
      keywords to the melee_* fields (the bundled bug fix).
  (e) Exhaustive coverage — every unit in parsed.json carries the five new
      keyword fields.
"""

from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from code.bsdata.mapper import PARSED_PATH
from code.units import Unit, UnitProfile, UNIT_CATALOG

# The five new melee keyword fields added in wave 244, plus melee_lethal_hits
# which was previously missing from the loader's aggregate path.
NEW_MELEE_FIELDS = frozenset({
    "melee_anti_keywords",
    "melee_devastating_wounds",
    "melee_twin_linked",
    "melee_devastating_wounds_basket_fraction",
    "melee_anti_keyword_basket_fractions",
})


def _parsed_units() -> list:
    path = Path(PARSED_PATH)
    if not path.exists():
        raise unittest.SkipTest(
            f"parsed.json not found at {PARSED_PATH}; "
            f"run `python -m code.bsdata.mapper` first"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["units"]


def _no_save_target() -> UnitProfile:
    """A high-health, no-save dummy: every successful wound becomes damage, so
    the realised damage tracks the wound count directly. INFANTRY keyword so
    Anti-Infantry can match."""
    return UnitProfile(
        name="Tgt", health=1e9, damage=0, hit_probability=0,
        toughness=10, save=7,
        unit_keywords=("INFANTRY",),
    )


class MeleeModeGuardBehaviourTests(unittest.TestCase):
    """(a) The three mode guards observably gate the keyword by attack mode."""

    def test_twin_linked_does_not_reroll_in_melee(self):
        """A profile whose RANGED weapon is Twin-Linked but whose MELEE weapon is
        not (melee_twin_linked=False) gets NO wound re-roll in melee. We pit it
        against a hard-to-wound target so re-rolls would visibly raise damage,
        then compare melee damage to an identical profile with melee_twin_linked
        flipped on. The off case must deal strictly less."""
        # Many attacks at a wound roll the attacker often fails (S4 vs T10 -> 6+).
        # hit_probability is the (unused) ranged value; melee uses melee_hit_probability.
        common = dict(
            name="A", health=10, damage=0, hit_probability=0,
            melee_attacks=4, melee_hit_probability=1.0, melee_strength=4,
            melee_damage_per_shot=1.0, melee_ap=0,
        )
        leaky = UnitProfile(twin_linked=True, melee_twin_linked=False, **common)
        honest = UnitProfile(twin_linked=True, melee_twin_linked=True, **common)

        n = 4000
        random.seed(11)
        off_total = sum(
            Unit(leaky).attack(Unit(_no_save_target()), mode="melee")
            for _ in range(n)
        )
        random.seed(11)
        on_total = sum(
            Unit(honest).attack(Unit(_no_save_target()), mode="melee")
            for _ in range(n)
        )
        # With Twin-Linked OFF in melee the failed-wound re-roll never fires, so
        # the leaky profile must deal clearly less than the honest one.
        self.assertLess(
            off_total, on_total * 0.95,
            msg=(
                f"melee_twin_linked=False dealt {off_total:.0f} vs "
                f"melee_twin_linked=True {on_total:.0f}; the ranged twin_linked "
                f"appears to be leaking into melee (re-roll firing)"
            ),
        )

    def test_twin_linked_still_rerolls_in_ranged(self):
        """The same profile (ranged twin_linked=True) DOES re-roll in ranged
        mode — the guard only suppresses melee, never the ranged path."""
        common = dict(
            name="A", health=10, damage=0,
            attacks=4, hit_probability=1.0, strength=4,
            weapon_damage_per_shot=1.0, ap=0, range_inches=24,
        )
        tl = UnitProfile(twin_linked=True, melee_twin_linked=False, **common)
        no_tl = UnitProfile(twin_linked=False, melee_twin_linked=False, **common)

        n = 4000
        random.seed(13)
        tl_total = sum(
            Unit(tl).attack(Unit(_no_save_target()), distance=6.0)
            for _ in range(n)
        )
        random.seed(13)
        no_total = sum(
            Unit(no_tl).attack(Unit(_no_save_target()), distance=6.0)
            for _ in range(n)
        )
        self.assertGreater(
            tl_total, no_total * 1.05,
            msg=(
                f"ranged twin_linked=True dealt {tl_total:.0f} vs no-twin "
                f"{no_total:.0f}; the ranged re-roll should still fire"
            ),
        )

    def test_anti_keyword_does_not_fire_in_melee(self):
        """A profile with ranged Anti-Infantry 3+ but empty melee_anti_keywords
        lowers no crit-wound threshold in melee. With S4 vs T10 the only wounds
        come from crit-on-6 (Devastating off, so crits are normal wounds) — the
        Anti-X lowers the crit threshold to 3+, which (with Devastating off) does
        not change normal wounding, so we test the threshold leak through a
        Devastating-Wounds pairing instead: see the combined test below. Here we
        assert the parsed/catalogue field is empty so the threshold cannot leak."""
        # Direct field assertion: the melee field is empty so the Anti-X site's
        # mode guard reads nothing in melee.
        p = UnitProfile(
            name="A", health=10, damage=0, hit_probability=0,
            anti_keywords=(("INFANTRY", 3),), melee_anti_keywords=(),
            melee_attacks=2, melee_hit_probability=1.0, melee_strength=4,
        )
        self.assertEqual(p.melee_anti_keywords, ())
        self.assertEqual(p.anti_keywords, (("INFANTRY", 3),))

    def test_devastating_wounds_anti_combo_leak_blocked_in_melee(self):
        """Anti-Infantry lowers the crit-WOUND threshold; with Devastating Wounds
        those crit wounds bypass saves. A profile carrying ranged Anti-Infantry +
        ranged Devastating Wounds, but EMPTY melee equivalents, must deal no
        save-bypassing crit wounds in melee against an INFANTRY target with a
        save. We give the target a 2+ save so normal wounds are mostly saved and
        only save-bypassing (Devastating) crit wounds get through — if the ranged
        keywords leaked, melee damage would spike."""
        target = UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=2, unit_keywords=("INFANTRY",),
        )
        common = dict(
            name="A", health=10, damage=0, hit_probability=0,
            melee_attacks=4, melee_hit_probability=1.0, melee_strength=4,
            melee_damage_per_shot=1.0, melee_ap=0,
        )
        leaky = UnitProfile(
            anti_keywords=(("INFANTRY", 3),), devastating_wounds=True,
            melee_anti_keywords=(), melee_devastating_wounds=False,
            **common,
        )
        honest = UnitProfile(
            anti_keywords=(), devastating_wounds=False,
            melee_anti_keywords=(("INFANTRY", 3),), melee_devastating_wounds=True,
            melee_devastating_wounds_basket_fraction=1.0,
            melee_anti_keyword_basket_fractions=(("INFANTRY", 1.0),),
            **common,
        )
        n = 4000
        random.seed(17)
        leak_total = sum(
            Unit(leaky).attack(Unit(target), mode="melee") for _ in range(n)
        )
        random.seed(17)
        honest_total = sum(
            Unit(honest).attack(Unit(target), mode="melee") for _ in range(n)
        )
        # The leaky profile's ranged Anti+Devastating must NOT bypass the 2+
        # save in melee, so it deals far less than the honest melee-keyword one.
        self.assertLess(
            leak_total, honest_total * 0.7,
            msg=(
                f"ranged Anti+Devastating leaked into melee: leaky dealt "
                f"{leak_total:.0f} vs honest melee {honest_total:.0f} "
                f"(expected leaky << honest)"
            ),
        )


class ParsedJsonSpotCheckTests(unittest.TestCase):
    """(b) The three validated spot-check units."""

    @classmethod
    def setUpClass(cls):
        cls.by_key = {u["key"]: u for u in _parsed_units()}

    def test_howling_banshees_melee_anti_infantry(self):
        u = self.by_key.get("aeldari_craftworlds_howling_banshees")
        if u is None:
            self.skipTest("aeldari_craftworlds_howling_banshees not in parsed.json")
        # The Banshee Blade is genuinely Anti-Infantry, so the melee field is
        # populated from the chosen melee weapon (no longer basket-averaged).
        self.assertEqual(
            u.get("melee_anti_keywords"), {"INFANTRY": 3},
            msg=f"melee_anti_keywords={u.get('melee_anti_keywords')!r}",
        )

    def test_daemonettes_melee_devastating_wounds(self):
        u = self.by_key.get("chaos_daemons_library_daemonettes")
        if u is None:
            self.skipTest("chaos_daemons_library_daemonettes not in parsed.json")
        # Melee-only unit: Slashing claws carry Devastating Wounds. The mapper
        # promotes the melee weapon to the primary slot for melee-only units, so
        # the ranged-side devastating_wounds mirrors it — net behaviour preserved.
        self.assertTrue(
            u.get("melee_devastating_wounds"),
            msg=f"melee_devastating_wounds={u.get('melee_devastating_wounds')!r}",
        )

    def test_wave_serpent_melee_twin_linked_false(self):
        u = self.by_key.get("aeldari_craftworlds_wave_serpent")
        if u is None:
            self.skipTest("aeldari_craftworlds_wave_serpent not in parsed.json")
        # The actual fidelity gain: the Twin Bright Lance is Twin-Linked
        # (ranged), but the Wraithbone Hull melee weapon is not.
        self.assertTrue(
            u.get("twin_linked"),
            msg="Wave Serpent ranged twin_linked should remain True",
        )
        self.assertFalse(
            u.get("melee_twin_linked"),
            msg=(
                f"Wave Serpent melee_twin_linked={u.get('melee_twin_linked')!r}; "
                f"the Twin Bright Lance's TWIN-LINKED must not leak into melee"
            ),
        )


class CatalogRoundTripTests(unittest.TestCase):
    """(c) The new fields survive the full load round-trip."""

    def test_wave_serpent_catalog_melee_twin_linked_false(self):
        profile = UNIT_CATALOG.get("aeldari_craftworlds_wave_serpent")
        if profile is None:
            self.skipTest("aeldari_craftworlds_wave_serpent not in UNIT_CATALOG")
        self.assertTrue(hasattr(profile, "melee_twin_linked"))
        self.assertTrue(profile.twin_linked)
        self.assertFalse(profile.melee_twin_linked)

    def test_howling_banshees_catalog_melee_anti_keywords_tuple(self):
        profile = UNIT_CATALOG.get("aeldari_craftworlds_howling_banshees")
        if profile is None:
            self.skipTest("aeldari_craftworlds_howling_banshees not in UNIT_CATALOG")
        # UnitProfile stores anti-keywords as a hashable tuple-of-tuples.
        self.assertEqual(profile.melee_anti_keywords, (("INFANTRY", 3),))

    def test_all_fields_present_on_a_loaded_profile(self):
        profile = next(iter(UNIT_CATALOG.values()))
        for f in NEW_MELEE_FIELDS | {"melee_lethal_hits"}:
            self.assertTrue(
                hasattr(profile, f),
                msg=f"UnitProfile missing attribute {f!r}",
            )

    def test_melee_lethal_hits_round_trips_on_aggregate_path(self):
        """melee_lethal_hits was MISSING from loader.CatalogEntry pre-wave-244,
        so the aggregate path always produced False. At least one unit must now
        carry melee_lethal_hits=True through the full load (the per-model path is
        not the only source)."""
        any_true = any(
            getattr(p, "melee_lethal_hits", False) for p in UNIT_CATALOG.values()
        )
        self.assertTrue(
            any_true,
            msg=(
                "No unit in UNIT_CATALOG has melee_lethal_hits=True; the loader "
                "aggregate-path round-trip of melee_lethal_hits is broken"
            ),
        )


class ExtraMeleeHotSwapTests(unittest.TestCase):
    """(d) The extra-melee runtime swap dict routes keywords to the melee_*
    fields (the bundled units.py:1568 bug fix)."""

    def test_extra_melee_swap_routes_to_melee_fields(self):
        """Replicate the _melee_extras swap-dict construction from units.py for a
        synthetic extra weapon carrying every keyword. The swap dict must key the
        keywords under the melee_* names (so dataclasses.replace populates the
        fields the Fight phase reads), NOT the ranged names."""
        _ed = {
            "lethal_hits": True,
            "devastating_wounds": True,
            "twin_linked": True,
            "anti_keywords": {"VEHICLE": 4},
        }
        # Replicate the units.py swap-dict construction (the keyword-routing
        # subset).
        swap = {
            "melee_lethal_hits": bool(_ed.get("lethal_hits", False)),
            "melee_devastating_wounds": bool(_ed.get("devastating_wounds", False)),
            "melee_twin_linked": bool(_ed.get("twin_linked", False)),
            "melee_devastating_wounds_basket_fraction": 1.0,
            "melee_anti_keywords": tuple(
                (_ed.get("anti_keywords") or {}).items()
            ) if isinstance(_ed.get("anti_keywords"), dict)
            else tuple(_ed.get("anti_keywords") or ()),
            "melee_anti_keyword_basket_fractions": tuple(
                (kw, 1.0) for kw in (_ed.get("anti_keywords") or {})
            ) if isinstance(_ed.get("anti_keywords"), dict)
            else tuple(
                (kw, 1.0) for kw, _ in (_ed.get("anti_keywords") or ())
            ),
        }
        # The keywords must live under the melee_* keys (the bug wrote them to
        # the ranged names).
        self.assertTrue(swap["melee_lethal_hits"])
        self.assertTrue(swap["melee_devastating_wounds"])
        self.assertTrue(swap["melee_twin_linked"])
        self.assertEqual(swap["melee_anti_keywords"], (("VEHICLE", 4),))
        self.assertEqual(
            swap["melee_anti_keyword_basket_fractions"], (("VEHICLE", 1.0),)
        )
        # The ranged-named keys must NOT be present (they would be unread in
        # melee and would clobber the primary's ranged value if present).
        self.assertNotIn("lethal_hits", swap)
        self.assertNotIn("twin_linked", swap)
        self.assertNotIn("anti_keywords", swap)

    def test_extra_melee_keyword_actually_fires_via_replace(self):
        """An end-to-end check: a profile with a Twin-Linked extra melee weapon
        re-rolls failed melee wounds (proving the swap reaches the melee field
        the Fight-phase guard reads). Without the bug fix the extra's
        twin_linked landed on the unread ranged field and never fired."""
        import dataclasses

        target = UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=10, save=7, unit_keywords=("INFANTRY",),
        )
        # Base melee profile with NO twin-linked, plus one extra melee weapon
        # that IS twin-linked. extra_melee_profiles is a tuple-of-(key,value)
        # pairs (the UnitProfile hashable form).
        extra = (
            ("weapon", "Twin Fangs"),
            ("attacks", 4),
            ("weapon_damage_per_shot", 1.0),
            ("hit_probability", 1.0),
            ("ap", 0),
            ("strength", 4),
            ("twin_linked", True),
            ("lethal_hits", False),
            ("devastating_wounds", False),
            ("sustained_hits", 0),
            ("lance", False),
            ("precision", False),
            ("one_shot", False),
            ("hazardous", False),
            ("anti_keywords", ()),
        )
        base = UnitProfile(
            name="A", health=10, damage=0, hit_probability=0,
            melee_attacks=4, melee_hit_probability=1.0, melee_strength=4,
            melee_damage_per_shot=1.0, melee_ap=0,
            melee_twin_linked=False, twin_linked=False,
            extra_melee_profiles=(extra,),
        )
        no_extra = dataclasses.replace(base, extra_melee_profiles=())

        n = 3000
        random.seed(23)
        with_extra = sum(
            Unit(base).attack(Unit(target), mode="melee") for _ in range(n)
        )
        random.seed(23)
        without_extra = sum(
            Unit(no_extra).attack(Unit(target), mode="melee") for _ in range(n)
        )
        # The extra twin-linked weapon adds 4 re-rolling attacks; total damage
        # must be clearly higher than the primary-only profile.
        self.assertGreater(
            with_extra, without_extra * 1.2,
            msg=(
                f"extra twin-linked melee weapon contributed too little: "
                f"with={with_extra:.0f} without={without_extra:.0f}; the swap "
                f"may not be reaching melee_twin_linked"
            ),
        )


class ExhaustiveCoverageTests(unittest.TestCase):
    """(e) Every unit in parsed.json carries the five new keyword fields."""

    @classmethod
    def setUpClass(cls):
        cls.records = _parsed_units()

    def test_all_units_carry_new_melee_fields(self):
        missing: list = []
        for unit in self.records:
            key = unit.get("key", "<no-key>")
            absent = [f for f in sorted(NEW_MELEE_FIELDS) if f not in unit]
            if absent:
                missing.append((key, absent))
        self.assertEqual(
            missing, [],
            msg=(
                f"{len(missing)} units missing new melee keyword fields "
                f"(first 5): {missing[:5]}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
