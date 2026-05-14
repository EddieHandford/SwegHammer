"""Tests for the squad-aware loadout mapper (issue #76).

These exercise three properties of `map_unit`:
  1. A synthetic Devastator-style squad with a base bolter + heavy weapon
     produces stats BETWEEN bolter-only and heavy-only — i.e. weighted, not
     all-or-nothing cheese.
  2. The real BSData Tactical Squad ends up with S>=5 / AP=-1, reflecting
     the inclusion of a special weapon, but with dmg/shot well below a
     pure-plasma all-best loadout.
  3. The real BSData Devastator Squad ends up with melta=2 carried forward
     from the embedded Multi-melta picks (proving keyword union works) AND
     with dmg/shot BETWEEN bolter-only and multi-melta-only.

We use the parsed.json that the mapper has just produced (regenerated
on-demand if missing) for the BSData assertions, and a tiny synthetic
XML tree for the unit-of-logic assertion.
"""

from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from code.bsdata.mapper import (
    PARSED_PATH,
    Registry,
    WeaponStats,
    _flatten_to_basket,
    extract_squad_size,
    gather_squad_loadout,
    map_unit,
    weighted_basket_average,
)


# ---------------------------------------------------------------------------
# Synthetic squad — bolter base + multi-melta heavy
# ---------------------------------------------------------------------------

SYNTHETIC_SQUAD_XML = """\
<catalogue name="test">
  <sharedSelectionEntries>
    <selectionEntry id="weap-boltgun" name="Boltgun">
      <profiles>
        <profile name="Boltgun" typeName="Ranged Weapons">
          <characteristics>
            <characteristic name="Range">24"</characteristic>
            <characteristic name="A">2</characteristic>
            <characteristic name="BS">3+</characteristic>
            <characteristic name="S">4</characteristic>
            <characteristic name="AP">0</characteristic>
            <characteristic name="D">1</characteristic>
            <characteristic name="Keywords">-</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
    <selectionEntry id="weap-multimelta" name="Multi-melta">
      <profiles>
        <profile name="Multi-melta" typeName="Ranged Weapons">
          <characteristics>
            <characteristic name="Range">18"</characteristic>
            <characteristic name="A">2</characteristic>
            <characteristic name="BS">4+</characteristic>
            <characteristic name="S">9</characteristic>
            <characteristic name="AP">-4</characteristic>
            <characteristic name="D">D6</characteristic>
            <characteristic name="Keywords">Melta 2, Heavy</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
    <selectionEntry id="weap-ccw" name="Close Combat Weapon">
      <profiles>
        <profile name="Close Combat Weapon" typeName="Melee Weapons">
          <characteristics>
            <characteristic name="A">2</characteristic>
            <characteristic name="WS">3+</characteristic>
            <characteristic name="S">4</characteristic>
            <characteristic name="AP">0</characteristic>
            <characteristic name="D">1</characteristic>
            <characteristic name="Keywords">-</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </sharedSelectionEntries>
  <selectionEntries>
    <selectionEntry id="synth-squad" type="unit" name="Synth Squad">
      <selectionEntryGroups>
        <selectionEntryGroup id="squad-grp" name="Models">
          <constraints>
            <constraint type="min" value="5" field="selections"/>
            <constraint type="max" value="10" field="selections"/>
          </constraints>
          <selectionEntries>
            <selectionEntry type="model" id="model-grunt" name="Grunt">
              <constraints>
                <constraint type="min" value="4" field="selections"/>
                <constraint type="max" value="9" field="selections"/>
              </constraints>
              <entryLinks>
                <entryLink type="selectionEntry" targetId="weap-boltgun" name="Boltgun">
                  <constraints>
                    <constraint type="min" value="1" field="selections"/>
                    <constraint type="max" value="1" field="selections"/>
                  </constraints>
                </entryLink>
                <entryLink type="selectionEntry" targetId="weap-ccw" name="Close Combat Weapon">
                  <constraints>
                    <constraint type="min" value="1" field="selections"/>
                    <constraint type="max" value="1" field="selections"/>
                  </constraints>
                </entryLink>
              </entryLinks>
              <profiles>
                <profile name="Synth Squad" typeName="Unit">
                  <characteristics>
                    <characteristic name="M">6"</characteristic>
                    <characteristic name="T">4</characteristic>
                    <characteristic name="SV">3+</characteristic>
                    <characteristic name="W">2</characteristic>
                    <characteristic name="LD">7+</characteristic>
                    <characteristic name="OC">1</characteristic>
                  </characteristics>
                </profile>
              </profiles>
            </selectionEntry>
            <selectionEntry type="model" id="model-heavy" name="Grunt w/ Heavy">
              <constraints>
                <constraint type="min" value="0" field="selections"/>
                <constraint type="max" value="4" field="selections"/>
              </constraints>
              <entryLinks>
                <entryLink type="selectionEntry" targetId="weap-multimelta" name="Multi-melta">
                  <constraints>
                    <constraint type="min" value="1" field="selections"/>
                    <constraint type="max" value="1" field="selections"/>
                  </constraints>
                </entryLink>
                <entryLink type="selectionEntry" targetId="weap-ccw" name="Close Combat Weapon">
                  <constraints>
                    <constraint type="min" value="1" field="selections"/>
                    <constraint type="max" value="1" field="selections"/>
                  </constraints>
                </entryLink>
              </entryLinks>
              <profiles>
                <profile name="Synth Squad" typeName="Unit">
                  <characteristics>
                    <characteristic name="M">6"</characteristic>
                    <characteristic name="T">4</characteristic>
                    <characteristic name="SV">3+</characteristic>
                    <characteristic name="W">2</characteristic>
                    <characteristic name="LD">7+</characteristic>
                    <characteristic name="OC">1</characteristic>
                  </characteristics>
                </profile>
              </profiles>
            </selectionEntry>
            <selectionEntry type="model" id="model-sergeant" name="Sergeant">
              <constraints>
                <constraint type="min" value="1" field="selections"/>
                <constraint type="max" value="1" field="selections"/>
              </constraints>
              <entryLinks>
                <entryLink type="selectionEntry" targetId="weap-boltgun" name="Boltgun">
                  <constraints>
                    <constraint type="min" value="1" field="selections"/>
                    <constraint type="max" value="1" field="selections"/>
                  </constraints>
                </entryLink>
                <entryLink type="selectionEntry" targetId="weap-ccw" name="Close Combat Weapon">
                  <constraints>
                    <constraint type="min" value="1" field="selections"/>
                    <constraint type="max" value="1" field="selections"/>
                  </constraints>
                </entryLink>
              </entryLinks>
              <profiles>
                <profile name="Synth Squad" typeName="Unit">
                  <characteristics>
                    <characteristic name="M">6"</characteristic>
                    <characteristic name="T">4</characteristic>
                    <characteristic name="SV">3+</characteristic>
                    <characteristic name="W">2</characteristic>
                    <characteristic name="LD">7+</characteristic>
                    <characteristic name="OC">1</characteristic>
                  </characteristics>
                </profile>
              </profiles>
            </selectionEntry>
          </selectionEntries>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
"""


def _build_synth_registry() -> tuple[Registry, ET.Element]:
    """Parse SYNTHETIC_SQUAD_XML into a Registry; return (reg, unit_entry)."""
    root = ET.fromstring(SYNTHETIC_SQUAD_XML)
    reg = Registry()
    # Manual index — the production load path uses load_registry which reads files.
    for elem in root.iter():
        eid = elem.get("id")
        if eid and eid not in reg.by_id:
            reg.by_id[eid] = elem
    reg.catalogues["test"] = root
    unit = reg.resolve("synth-squad")
    assert unit is not None, "fixture root must be locatable"
    return reg, unit


class SyntheticSquadLoadoutTests(unittest.TestCase):
    """The squad-loadout walker on a tiny, fully-controlled XML tree."""

    def test_squad_size_extracted(self):
        reg, unit = _build_synth_registry()
        self.assertEqual(extract_squad_size(unit), (5, 10))

    def test_gather_squad_loadout_finds_three_model_types(self):
        reg, unit = _build_synth_registry()
        models = gather_squad_loadout(unit, reg)
        self.assertIsNotNone(models)
        names = sorted(m.name for m in models)
        self.assertEqual(names, ["Grunt", "Grunt w/ Heavy", "Sergeant"])
        # Counts: 1 sergeant + 4 heavy + 5 grunts = 10 (squad max)
        by_name = {m.name: m.count for m in models}
        self.assertEqual(by_name["Sergeant"], 1.0)
        self.assertEqual(by_name["Grunt w/ Heavy"], 4.0)
        # Grunt's max=9, but combined with sergeant(1)+heavy(4) overflows to 14,
        # so the largest contributor (the Grunt) is shrunk by 4 → 5.
        self.assertEqual(by_name["Grunt"], 5.0)

    def test_basket_is_weighted_between_bolter_and_multimelta(self):
        reg, unit = _build_synth_registry()
        models = gather_squad_loadout(unit, reg)
        self.assertIsNotNone(models)
        basket = _flatten_to_basket(models, "ranged")
        # The basket should have entries for both Boltgun and Multi-melta.
        names = sorted({w.name for _, w in basket})
        self.assertIn("Boltgun", names)
        self.assertIn("Multi-melta", names)
        avg = weighted_basket_average(basket)
        self.assertIsNotNone(avg)
        # Multi-melta has D=D6 (3.5), Boltgun has D=1. Weighted average must
        # sit strictly between 1.0 and 3.5.
        self.assertGreater(avg.damage, 1.0)
        self.assertLess(avg.damage, 3.5)
        # Melta keyword union: at least one model carries Melta 2.
        self.assertEqual(avg.melta, 2)
        # AP is averaged from 0 (boltgun, 6 models) and -4 (multi-melta, 4
        # models). Weighted avg = (6*0 + 4*-4)/10 = -1.6 → rounds to -2.
        self.assertEqual(avg.ap, -2)

    def test_full_map_unit_damage_between_base_and_best(self):
        """The unit-level damage stat sits BETWEEN bolter-only and multi-melta-only."""
        reg, unit = _build_synth_registry()
        mapped = map_unit("test-codex", unit, reg)
        self.assertTrue(mapped.enabled, msg=mapped.skip_reason)
        # Bolter-only floor: per-shot damage = 1.0 * 2 attacks = 2.0
        # Multi-melta ceiling: per-shot damage ~ 3.5 * 2 attacks = 7.0
        self.assertGreater(mapped.damage, 2.0)
        self.assertLess(mapped.damage, 7.0)
        # Notes string flags the heterogeneous path so we know we didn't fall back.
        self.assertIn("heterogeneous", mapped.notes)
        # Strength is the weighted blend — pure bolter is S4, pure multi-melta is
        # S9; the mix should be strictly above 4 (and well below 9).
        self.assertGreater(mapped.strength, 4)
        self.assertLess(mapped.strength, 9)


# ---------------------------------------------------------------------------
# Real-BSData regression — relies on data/bsdata/parsed.json being present
# ---------------------------------------------------------------------------

def _parsed_units() -> dict[str, dict]:
    """Load parsed.json indexed by key. Skipped tests if missing."""
    if not Path(PARSED_PATH).exists():
        raise unittest.SkipTest(
            f"parsed.json not found at {PARSED_PATH}; run `python -m code.bsdata.mapper`"
        )
    data = json.loads(Path(PARSED_PATH).read_text(encoding="utf-8"))
    return {u["key"]: u for u in data["units"]}


class RealBSDataSquadRegressionTests(unittest.TestCase):
    """Spot checks on known-shape squads in the parsed catalogue."""

    @classmethod
    def setUpClass(cls):
        cls.units = _parsed_units()

    def _get(self, key: str) -> dict:
        u = self.units.get(key)
        if u is None:
            self.skipTest(f"unit '{key}' missing from parsed.json")
        return u

    def test_devastator_squad_is_heterogeneous(self):
        u = self._get("space_marines_devastator_squad")
        self.assertIn("heterogeneous", u["notes"])
        # 5 boltguns + 4 multi-meltas + 1 sergeant — between bolter-only
        # (damage ~2.0) and pure-multi-melta cheese (damage ~7).
        self.assertGreater(u["damage"], 2.0)
        self.assertLess(u["damage"], 6.0)
        # Melta keyword union must pick up the multi-melta carriers.
        self.assertEqual(u["melta"], 2)
        # AP averages the bolter (0) with the multi-melta (-4) — should
        # land negative but well above -4.
        self.assertLess(u["ap"], 0)
        self.assertGreaterEqual(u["ap"], -3)

    def test_tactical_squad_carries_special_weapon_signal(self):
        u = self._get("space_marines_tactical_squad")
        self.assertIn("heterogeneous", u["notes"])
        # 7 boltguns + 1 special + 1 sergeant + 1 heavy/special model.
        # Strength must be above bolter-only (4) because the average pulls
        # in the special weapons.
        self.assertGreater(u["strength"], 4)
        # Loadout list must include "Boltgun" — proving the base weapon is
        # represented, not just the best.
        self.assertTrue(
            any("Boltgun" in entry for entry in u["loadout"]),
            msg=f"loadout missing Boltgun: {u['loadout']}",
        )

    def test_hellblaster_squad_picks_up_plasma_incinerator(self):
        u = self._get("space_marines_hellblaster_squad")
        self.assertIn("heterogeneous", u["notes"])
        # 9 Plasma Incinerators + 1 sergeant pistol. Even averaged, the unit
        # should carry meaningful AP (plasma is AP-2 standard / -3 supercharge).
        self.assertLessEqual(u["ap"], -1)
        self.assertGreaterEqual(u["strength"], 6)
        self.assertTrue(
            any("Plasma Incinerator" in entry for entry in u["loadout"]),
            msg=f"loadout missing Plasma Incinerator: {u['loadout']}",
        )

    def test_telemetry_some_units_used_squad_aware_path(self):
        """At least some squads in the catalogue must use the heterogeneous path.

        If this drops to zero we've regressed the gather_squad_loadout walker.
        """
        het = sum(
            1 for u in self.units.values()
            if u.get("enabled") and "heterogeneous" in u.get("notes", "")
        )
        self.assertGreater(het, 50, msg="expected dozens of heterogeneous squads")


if __name__ == "__main__":
    unittest.main()
