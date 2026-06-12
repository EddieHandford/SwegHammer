"""Wave 247 lever 1 — Born Soldiers REGIMENT keyword gate (SWEG_BORN_REGIMENT).

BSData verbatim (Imperium - Astra Militarum - Library.cat.gz, rule id
b65e-c54b-b8fe-e8e2):
"Each time a model in a **^^Regiment^^** unit from your army makes a ranged
attack that targets a visible unit (excluding **^^Monsters^^** and
**^^Vehicles^^**) that attack has the **[LETHAL HITS]** ability."

Wave 243 made REGIMENT a first-class tracked keyword from BSData categoryLinks
(31 units). This wave adds SWEG_BORN_REGIMENT to allow the simulator to check
the codex-literal REGIMENT keyword rather than the legacy BATTLELINE proxy:

  unset / "0": legacy BATTLELINE proxy (byte-identical to pre-wave-247)
  "1":         corrected REGIMENT keyword check

Tests cover the three gate states and the Vehicle/Monster exclusion:
  (a) gate unset ("0" path): REGIMENT non-BATTLELINE attacker (Kasrkin) does
      NOT get the lethal-hits leg; BATTLELINE attacker does (legacy pinned).
  (b) gate "1": REGIMENT non-BATTLELINE attacker (Kasrkin) gets
      effective_lethal_hits vs an INFANTRY target; NOT vs a VEHICLE target;
      a VEHICLE-keyword attacker remains excluded.
  (c) gate "0" explicit: identical to unset — legacy behaviour confirmed.

All tests operate at the unit-level (Unit.attack), no full battles.  Lethal
hits are detected by a deterministic die-roll sequence: the hit roll is always
a natural 6 (crit hit), the wound roll is always a 1 (fail — too weak to wound
normally without Lethal Hits).  With effective_lethal_hits=True the wound roll
is bypassed entirely and the attack deals damage.  Without it the wound roll
fires (returns 1) and the attack deals zero damage.

Target toughness is set to 12 (wound target 6+) and attacker strength to 3
(well below T/2), so the only path to dealing damage is the lethal-hits
auto-wound from a crit hit.  The target has no save (save=7, invuln=7) to
isolate the lethal-hits signal cleanly.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from code.army import Army
from code.detachments import COMBINED_REGIMENT
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Die-sequence helper
# ---------------------------------------------------------------------------

def _make_die_sequence(*values):
    """Return a mock for random.randint that yields ``values`` in order,
    then raises StopIteration if the sequence is exhausted.  Using
    side_effect with a list is the standard unittest.mock idiom — the mock
    pops from the list on each call and raises StopIteration when empty."""
    return mock.patch(
        "random.randint",
        side_effect=list(values),
    )


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------

def _kasrkin_profile() -> UnitProfile:
    """Kasrkin: REGIMENT + INFANTRY but NOT BATTLELINE (wave-243 BSData data).

    Attacks=1, strength=3 vs toughness-12 target: wound target is 6+.
    With the die sequence [6, 1] (hit=6 crit, wound=1 fail) the attack deals
    damage ONLY if effective_lethal_hits fires (crit auto-wounds, bypassing the
    wound roll entirely).  Without lethal hits the wound roll fires, returns 1,
    and the attack deals zero damage.
    """
    return UnitProfile(
        name="Kasrkin",
        faction="Astra Militarum",
        health=2,
        damage=0,
        hit_probability=1 / 6,    # ballistic skill 6+, only crit matters
        ap=-1,
        save=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        strength=3,               # so S << T/2 => wound target 6+ (no help)
        toughness=4,
        move=6.0,
        oc=1,
        unit_keywords=("REGIMENT", "INFANTRY"),   # NOT BATTLELINE
    )


def _cadian_profile() -> UnitProfile:
    """Cadian Shock Troops: BATTLELINE + REGIMENT + INFANTRY — carries both
    keywords, so it should receive the lethal-hits leg under both the legacy
    BATTLELINE proxy (gate=0) AND the corrected REGIMENT gate (gate=1).
    """
    return UnitProfile(
        name="Cadian Shock Troops",
        faction="Astra Militarum",
        health=2,
        damage=0,
        hit_probability=1 / 6,
        ap=-1,
        save=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        strength=3,
        toughness=4,
        move=6.0,
        oc=1,
        unit_keywords=("INFANTRY", "BATTLELINE", "REGIMENT"),
    )


def _vehicle_attacker_profile() -> UnitProfile:
    """Armoured Sentinels: REGIMENT + VEHICLE + SQUADRON. Carries REGIMENT but
    also VEHICLE, so it is excluded from the REGIMENT leg regardless of gate
    (the codex excludes VEHICLE attackers from the REGIMENT leg — they get
    the SQUADRON leg vs VEHICLE/MONSTER targets instead)."""
    return UnitProfile(
        name="Armoured Sentinels",
        faction="Astra Militarum",
        health=6,
        damage=2,
        hit_probability=2 / 3,
        ap=-2,
        save=3,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        strength=6,
        toughness=8,
        move=8.0,
        oc=2,
        unit_keywords=("VEHICLE", "WALKER", "REGIMENT", "SQUADRON"),
    )


def _infantry_target_profile() -> UnitProfile:
    """A generic INFANTRY target with high toughness (T=12) and no save so
    the only path to damage is the lethal-hits auto-wound from a crit hit."""
    return UnitProfile(
        name="TargetInfantry",
        faction="Test",
        health=100,
        damage=0,
        hit_probability=0.5,
        ap=0,
        save=7,         # no save (7+ never passes on a d6)
        attacks=0,
        weapon_damage_per_shot=0.0,
        range_inches=12,
        strength=4,
        toughness=12,   # wound target=6+; attacker S=3 wounds on 6+ too;
        move=6.0,       # with lethal_hits the wound roll is bypassed entirely
        oc=1,
        unit_keywords=("INFANTRY",),
    )


def _vehicle_target_profile() -> UnitProfile:
    """A VEHICLE target. REGIMENT leg excludes VEHICLE targets; a REGIMENT
    attacker must NOT get lethal hits vs this target."""
    return UnitProfile(
        name="TargetVehicle",
        faction="Test",
        health=100,
        damage=0,
        hit_probability=0.5,
        ap=0,
        save=7,
        attacks=0,
        weapon_damage_per_shot=0.0,
        range_inches=12,
        strength=8,
        toughness=8,
        move=6.0,
        oc=3,
        unit_keywords=("VEHICLE",),
    )


# ---------------------------------------------------------------------------
# Army builder helper
# ---------------------------------------------------------------------------

def _am_army_with_unit(profile: UnitProfile) -> tuple[Army, Unit]:
    """Build a one-unit Astra Militarum army with the Combined Arms detachment
    (Born Soldiers enabled) and return (army, unit)."""
    army = Army("AM", detachment=COMBINED_REGIMENT)
    army.add_unit(profile)
    unit = army.units[0]
    unit.uid = "A0"
    return army, unit


def _target_unit(profile: UnitProfile) -> Unit:
    """Wrap a profile in a bare Unit (no army) for use as an attack target."""
    target = Unit(profile)
    target.uid = "T0"
    return target


# ---------------------------------------------------------------------------
# (a) Gate unset / "0": legacy BATTLELINE proxy
# ---------------------------------------------------------------------------

class GateUnsetLegacyBATTLELINETest(unittest.TestCase):
    """With SWEG_BORN_REGIMENT unset (defaulting to the legacy BATTLELINE
    path), a REGIMENT non-BATTLELINE attacker (Kasrkin) must NOT receive
    the lethal-hits leg, and a BATTLELINE attacker (Cadian Shock Troops)
    MUST receive it."""

    def _attack_damage(self, attacker_profile, target_profile, gate_value=None):
        """Run one attack with die sequence [6, 1] (crit hit, wound fail).
        Returns total damage dealt.  Die sequence is deterministic: if lethal
        hits fires the wound roll is skipped and damage > 0; if not the wound
        roll fires (returns 1, fails against T=12), damage == 0.
        """
        env = {k: v for k, v in os.environ.items()
               if k != "SWEG_BORN_REGIMENT"}
        if gate_value is not None:
            env["SWEG_BORN_REGIMENT"] = gate_value

        army, attacker = _am_army_with_unit(attacker_profile)
        target = _target_unit(target_profile)

        # Die sequence: 6=crit hit, 1=wound roll (only consumed if wound fires)
        with mock.patch.dict(os.environ, env, clear=True):
            with _make_die_sequence(6, 1):
                damage = attacker.attack(target, distance=12.0, mode="ranged")
        return damage

    def test_gate_unset_kasrkin_no_lethal_hits(self):
        # Kasrkin: REGIMENT but NOT BATTLELINE. Legacy proxy checks BATTLELINE.
        # With SWEG_BORN_REGIMENT unset, the BATTLELINE check fails → lethal
        # hits does NOT fire → wound roll fires (returns 1) → no damage.
        dmg = self._attack_damage(
            _kasrkin_profile(), _infantry_target_profile(), gate_value=None,
        )
        self.assertEqual(
            dmg, 0.0,
            "Gate unset (legacy BATTLELINE): Kasrkin (REGIMENT, non-BATTLELINE) "
            "must NOT receive lethal hits — wound roll fires and fails on 1.",
        )

    def test_gate_unset_cadian_gets_lethal_hits(self):
        # Cadian Shock Troops: BATTLELINE + REGIMENT. Legacy proxy checks
        # BATTLELINE → fires → wound roll skipped → damage > 0.
        dmg = self._attack_damage(
            _cadian_profile(), _infantry_target_profile(), gate_value=None,
        )
        self.assertGreater(
            dmg, 0.0,
            "Gate unset (legacy BATTLELINE): Cadian Shock Troops (BATTLELINE) "
            "MUST receive lethal hits — wound roll skipped, damage > 0.",
        )

    def test_gate_explicit_zero_kasrkin_no_lethal_hits(self):
        # Explicit SWEG_BORN_REGIMENT="0" mirrors unset (same code path).
        dmg = self._attack_damage(
            _kasrkin_profile(), _infantry_target_profile(), gate_value="0",
        )
        self.assertEqual(
            dmg, 0.0,
            "Gate='0' (explicit legacy): Kasrkin (non-BATTLELINE) must NOT "
            "receive lethal hits — byte-identical to unset behaviour.",
        )

    def test_gate_explicit_zero_cadian_gets_lethal_hits(self):
        # Explicit "0" with a BATTLELINE unit: still grants lethal hits.
        dmg = self._attack_damage(
            _cadian_profile(), _infantry_target_profile(), gate_value="0",
        )
        self.assertGreater(
            dmg, 0.0,
            "Gate='0' (explicit legacy): Cadian (BATTLELINE) must still receive "
            "lethal hits — same as unset.",
        )


# ---------------------------------------------------------------------------
# (b) Gate "1": corrected REGIMENT keyword check
# ---------------------------------------------------------------------------

class GateOnREGIMENTTest(unittest.TestCase):
    """With SWEG_BORN_REGIMENT='1', the REGIMENT keyword (not BATTLELINE) is
    the gate.  This covers Kasrkin and other non-BATTLELINE REGIMENT units."""

    def _attack_damage(self, attacker_profile, target_profile):
        """Run one attack with gate=1 and die sequence [6, 1]."""
        army, attacker = _am_army_with_unit(attacker_profile)
        target = _target_unit(target_profile)
        with mock.patch.dict(os.environ, {"SWEG_BORN_REGIMENT": "1"}):
            with _make_die_sequence(6, 1):
                return attacker.attack(target, distance=12.0, mode="ranged")

    def test_kasrkin_vs_infantry_gets_lethal_hits(self):
        # Kasrkin: REGIMENT + INFANTRY, not BATTLELINE. Gate=1: checks REGIMENT
        # → fires → wound roll skipped → damage > 0.
        dmg = self._attack_damage(
            _kasrkin_profile(), _infantry_target_profile(),
        )
        self.assertGreater(
            dmg, 0.0,
            "Gate='1': Kasrkin (REGIMENT, non-BATTLELINE) vs INFANTRY target "
            "MUST receive lethal hits — wound roll skipped, damage > 0.",
        )

    def test_kasrkin_vs_vehicle_no_lethal_hits(self):
        # REGIMENT leg excludes VEHICLE targets. Kasrkin vs VEHICLE target must
        # NOT get lethal hits even with gate=1.
        # Die sequence: 6=crit hit, 1=wound roll (fires because no lethal hits
        # against VEHICLE; wound=1 fails against T=8 too).
        army, attacker = _am_army_with_unit(_kasrkin_profile())
        target = _target_unit(_vehicle_target_profile())
        with mock.patch.dict(os.environ, {"SWEG_BORN_REGIMENT": "1"}):
            with _make_die_sequence(6, 1):
                dmg = attacker.attack(target, distance=12.0, mode="ranged")
        self.assertEqual(
            dmg, 0.0,
            "Gate='1': Kasrkin (REGIMENT) vs VEHICLE target must NOT receive "
            "lethal hits from the REGIMENT leg — wound roll fires and fails.",
        )

    def test_vehicle_attacker_excluded_from_regiment_leg(self):
        # Armoured Sentinels: VEHICLE + REGIMENT. Carries REGIMENT but the
        # REGIMENT leg explicitly excludes VEHICLE attackers (the condition
        # checks 'VEHICLE' not in attacker_kws). Must NOT get lethal hits
        # from the REGIMENT leg (it would get the SQUADRON leg vs VEHICLE
        # targets only, which is separately gated by name allowlist).
        army, attacker = _am_army_with_unit(_vehicle_attacker_profile())
        target = _target_unit(_infantry_target_profile())
        with mock.patch.dict(os.environ, {"SWEG_BORN_REGIMENT": "1"}):
            with _make_die_sequence(6, 1):
                dmg = attacker.attack(target, distance=12.0, mode="ranged")
        self.assertEqual(
            dmg, 0.0,
            "Gate='1': VEHICLE-keyword attacker (Armoured Sentinels) must NOT "
            "receive lethal hits from the REGIMENT leg — VEHICLE attackers are "
            "excluded even if they carry REGIMENT.",
        )

    def test_cadian_vs_infantry_still_gets_lethal_hits(self):
        # Cadian Shock Troops carry BATTLELINE + REGIMENT. Gate=1 checks
        # REGIMENT → fires → damage > 0 (same result as gate=0 / unset).
        dmg = self._attack_damage(
            _cadian_profile(), _infantry_target_profile(),
        )
        self.assertGreater(
            dmg, 0.0,
            "Gate='1': Cadian Shock Troops (BATTLELINE + REGIMENT) vs INFANTRY "
            "target must still receive lethal hits under the REGIMENT gate.",
        )


if __name__ == "__main__":
    unittest.main()
