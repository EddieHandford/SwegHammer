"""Unit profiles and battle-instance unit class."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Baseline calibration constants — Space Marine is the reference unit
# ---------------------------------------------------------------------------

BASELINE_HEALTH: float = 1.0
BASELINE_DAMAGE: float = 1.0
BASELINE_HIT_PROB: float = 2 / 3       # 3+ to hit on a d6
BASELINE_AP: int = 0
BASELINE_SAVE: int = 3                  # 3+ armour save
BASELINE_STRENGTH: int = 4              # bolter S4
BASELINE_TOUGHNESS: int = 4             # Marine T4
BASELINE_POINTS: float = 15.0


def wound_probability(strength: int, toughness: int) -> float:
    """
    Standard 40K wound table:

      S >= 2T : wound on 2+ (5/6)
      S > T   : wound on 3+ (4/6)
      S == T  : wound on 4+ (3/6)
      S < T   : wound on 5+ (2/6)
      2S <= T : wound on 6+ (1/6)
    """
    if strength >= 2 * toughness:
        return 5 / 6
    if 2 * strength <= toughness:
        return 1 / 6
    if strength > toughness:
        return 4 / 6
    if strength == toughness:
        return 3 / 6
    return 2 / 6   # strength < toughness but not 2S <= T


def _prob_to_target(prob: float) -> int:
    """
    Invert a "succeed on N+" d6 probability back to its target. Clamped to [2,7]
    because a 1 always fails and 7+ is the canonical "no save / no hit".
    """
    target = int(round(7 - prob * 6))
    return max(2, min(7, target))


def save_probability(save: int, ap: int = 0, in_cover: bool = False) -> float:
    """
    Probability of passing an armour save roll on a d6.

    save:      the unit's base save characteristic (e.g. 3 means 3+)
    ap:        weapon AP modifier (negative integer, e.g. -1 degrades save by 1)
    in_cover:  cover improves save by 1 pip (e.g. 4+ → 3+), capped at 2+
    """
    effective = save - ap                       # AP-1 on a 3+ → 4+
    if in_cover:
        effective = max(2, effective - 1)       # cover: improve by 1, cap at 2+
    if effective > 6:
        return 0.0                              # save negated entirely
    return max(0.0, (7 - effective) / 6)


def _baseline_survival() -> float:
    """Fraction of hits that get through against a baseline Marine (no AP, no cover)."""
    return 1.0 - save_probability(BASELINE_SAVE, BASELINE_AP)


def points_for(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
    strength: int = BASELINE_STRENGTH,
    toughness: int = BASELINE_TOUGHNESS,
) -> float:
    """
    Points cost relative to the baseline Space Marine.

    Offensive ratio: expected unsaved damage this unit does to a baseline Marine
    (hit × wound vs T4 × unsaved vs 3+) divided by what a Marine does.

    Defensive ratio: expected hits-to-kill this unit by a baseline Marine, vs
    the baseline against itself.

    The two ratios are averaged (not multiplied) to prevent runaway costs for
    units that are dominant on both axes.
    """
    attacker_wound = wound_probability(strength, BASELINE_TOUGHNESS)
    offensive = damage * hit_prob * attacker_wound * (1.0 - save_probability(BASELINE_SAVE, ap))

    baseline_wound = wound_probability(BASELINE_STRENGTH, BASELINE_TOUGHNESS)
    baseline_offensive = BASELINE_DAMAGE * BASELINE_HIT_PROB * baseline_wound * _baseline_survival()
    off_ratio = offensive / baseline_offensive

    incoming_wound = wound_probability(BASELINE_STRENGTH, toughness)
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    if incoming_wound <= 0:
        incoming_wound = 1e-6
    durability = health / (incoming_wound * survive_chance)

    baseline_incoming_wound = wound_probability(BASELINE_STRENGTH, BASELINE_TOUGHNESS)
    baseline_survive = 1.0 - save_probability(BASELINE_SAVE)
    baseline_durability = BASELINE_HEALTH / (baseline_incoming_wound * baseline_survive)
    dur_ratio = durability / baseline_durability

    effectiveness = (off_ratio + dur_ratio) / 2.0
    return round(BASELINE_POINTS * effectiveness, 1)


def lanchester_score(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
    strength: int = BASELINE_STRENGTH,
    toughness: int = BASELINE_TOUGHNESS,
) -> float:
    """Lanchester priority score: dps × durability (used for activation order)."""
    attacker_wound = wound_probability(strength, BASELINE_TOUGHNESS)
    dps = damage * hit_prob * attacker_wound * (1.0 - save_probability(BASELINE_SAVE, ap))

    incoming_wound = wound_probability(BASELINE_STRENGTH, toughness)
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    if incoming_wound <= 0:
        incoming_wound = 1e-6
    durability = health / (incoming_wound * survive_chance)
    return dps * durability


# ---------------------------------------------------------------------------
# UnitProfile — immutable stat block
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitProfile:
    """Immutable stat block for a unit type."""

    name: str
    health: float
    damage: float                              # damage per unsaved hit
    hit_probability: float                     # probability of landing a hit (e.g. 2/3 for 3+)
    ap: int = 0                                # armour penetration modifier (0, -1, -2, -3 …)
    save: int = 7                              # armour save characteristic (7 = no save)
    strength: int = BASELINE_STRENGTH          # weapon strength used in the wound roll
    toughness: int = BASELINE_TOUGHNESS        # unit toughness defended in the wound roll
    move: float = 6.0                          # movement allowance in inches per activation
    range_inches: int = 24                     # weapon range; melee-only units use 1
    faction: str = ""                          # canonical faction tag for UI grouping / colours
    min_models: int = 1                        # smallest legal squad size (1 for single-model units)
    max_models: int = 1                        # largest legal squad size
    points_per_squad: float = 0.0              # BSData cost for a min-size squad (informational)
    # Per-shot damage decomposition — Unit.attack() loops `attacks` times per
    # activation, applying weapon_damage_per_shot each time. `damage` stays as
    # the per-activation total (= attacks * weapon_damage_per_shot) so the
    # points formula and UI displays don't change.
    attacks: int = 1
    weapon_damage_per_shot: float = 0.0        # 0 = derive damage / attacks at use site
    # Weapon abilities (parsed from BSData Keywords field by the mapper)
    lethal_hits: bool = False                  # critical hit (6 to hit) auto-wounds
    sustained_hits: int = 0                    # critical hit generates N extra normal hits
    twin_linked: bool = False                  # re-roll failed wound rolls
    devastating_wounds: bool = False           # critical wound (6 to wound) bypasses saves
    invuln_save: int = 7                       # invulnerable save (7 = none); use better of save-after-AP or invuln
    leadership: int = 7                        # Ld target for Battleshock tests (10e: 2D6 >= Ld passes)
    oc: int = 1                                # Objective Control characteristic (10e)
    # Phase A2 + A3 weapon keywords (carried from the unit's chosen ranged weapon)
    rapid_fire: int = 0                        # +N attacks at half range
    melta: int = 0                             # +N damage per shot at half range
    ignores_cover: bool = False                # target cover save bonus does not apply
    anti_keywords: Tuple[Tuple[str, int], ...] = ()  # ((keyword, threshold), ...) — tuple for hashability
    heavy: bool = False                        # +1 to hit if attacker did not move this turn
    assault: bool = False                      # can shoot after Advance
    torrent: bool = False                      # attacks auto-hit (skip to-hit roll)
    hazardous: bool = False                    # d6 self-harm on activation (1 = 3 mortal wounds)
    blast: bool = False                        # +1 attack per 5 enemy models in target unit
    # Phase F — niche 10e weapon keywords
    lance: bool = False                        # +1 to wound on melee if the unit charged this turn
    precision: bool = False                    # bypass cover when shooting a CHARACTER target
    pistol: bool = False                       # can shoot while in engagement (1.5") range
    indirect_fire: bool = False                # ignores LoS; -1 to hit vs non-visible targets
    one_shot: bool = False                     # weapon fires once per battle
    # Phase H — Stealth (-1 to be hit when shot at)
    stealth: bool = False
    # Phase I — deployment abilities (decided pre-Round 1 by the simulator)
    deep_strike: bool = False                  # starts in Reserves; arrives from Round 2
    scout_distance: int = 0                    # pre-game Normal Move up to N inches
    infiltrator: bool = False                  # deploys past the standard deployment line
    fnp: int = 7                               # Feel No Pain target (7 = none); roll after each unsaved wound
    unit_keywords: Tuple[str, ...] = ()        # 10e keywords (INFANTRY, VEHICLE, etc.) for Anti-X targeting
    # Phase B — melee profile (engagement range 1"). 0 = no usable melee profile.
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
    points_override: float = 0.0               # 0 = use derived points_cost; >0 wins (used by the balancer)

    @property
    def avg_damage_per_action(self) -> float:
        """Expected damage dealt per activation against a baseline Marine."""
        wound_p = wound_probability(self.strength, BASELINE_TOUGHNESS)
        unsaved = 1.0 - save_probability(BASELINE_SAVE, self.ap)
        return self.damage * self.hit_probability * wound_p * unsaved

    @property
    def per_shot_damage(self) -> float:
        """Damage per individual to-hit roll. Derived if not set explicitly."""
        if self.weapon_damage_per_shot > 0:
            return self.weapon_damage_per_shot
        return self.damage / max(1, self.attacks)

    @property
    def points_cost(self) -> float:
        if self.points_override and self.points_override > 0:
            return float(self.points_override)
        return points_for(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        )

    @property
    def score(self) -> float:
        return lanchester_score(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        )

    def __str__(self) -> str:
        save_str = f"{self.save}+" if self.save <= 6 else "none"
        ap_str = str(self.ap) if self.ap != 0 else "0"
        return (
            f"{self.name} "
            f"[H:{self.health} D:{self.damage} Hit:{self.hit_probability:.0%} "
            f"S:{self.strength} T:{self.toughness} AP:{ap_str} Sv:{save_str} "
            f"Pts:{self.points_cost}]"
        )


# ---------------------------------------------------------------------------
# Unit — mutable battle instance
# ---------------------------------------------------------------------------

class Unit:
    """A live unit on the battlefield, tracking current health and position."""

    __slots__ = (
        "profile", "current_health", "in_cover", "in_heavy_cover", "uid", "position",
        "army_ref", "moved_this_round",
    )

    def __init__(self, profile: UnitProfile, in_cover: bool = False) -> None:
        self.profile = profile
        self.current_health: float = profile.health
        self.in_cover: bool = in_cover
        # Set by Battle._do_shoot when the target stands in HEAVY_COVER terrain.
        # Drives the -1-to-hit penalty (in addition to the +1-to-save the
        # plain in_cover flag already grants). Restored to False after shot.
        self.in_heavy_cover: bool = False
        self.uid: str = ""                              # assigned by Battle at start
        self.position: tuple = (0.0, 0.0)               # (x, y) in inches
        # Back-reference to owning army (set by Army.add_unit). Lets
        # Unit.attack() resolve the army-wide detachment + check squad size
        # for keywords like Blast.
        self.army_ref = None
        # Set by Battle each round: True iff this unit moved during the
        # current round's movement sub-phase. Drives the Heavy keyword
        # (+1 to hit if attacker did NOT move).
        self.moved_this_round: bool = False

    @property
    def is_alive(self) -> bool:
        return self.current_health > 1e-9

    def receive_damage(self, amount: float, bonus_fnp: int = 7) -> None:
        """
        Apply damage. If this unit has Feel No Pain X+, each point of damage
        gets a d6 roll; on X+, it's ignored. Mortal wounds applied via this
        method also get FNP'd by default (matches 10e default behaviour).

        `bonus_fnp` lets the caller pass in a transient FNP value from a
        leader aura (lower of profile.fnp and bonus_fnp wins). 7 = no aura.
        """
        effective_fnp = min(self.profile.fnp, bonus_fnp)
        if effective_fnp < 7 and amount > 0:
            survived = 0
            for _ in range(int(round(amount))):
                if random.randint(1, 6) >= effective_fnp:
                    continue   # ignored
                survived += 1
            amount = survived + (amount - int(round(amount)))   # preserve fractional
        self.current_health = max(0.0, self.current_health - amount)

    def attack(
        self,
        target: "Unit",
        distance: float = 0.0,
        mode: str = "ranged",
        is_charging: bool = False,
        has_los: bool = True,
    ) -> float:
        """
        Full stochastic 10e attack sequence. For each of `attacks` shots:
          1. Roll d6 vs hit_target. Crit = 6.
          2. Sustained Hits N: crit-to-hit generates N extra normal hits.
          3. Lethal Hits: crit-to-hit auto-wounds (only the original crit, not
             its sustained extras).
          4. For each resulting hit, roll d6 vs wound_target. Twin-Linked
             re-rolls a failed wound roll once. Crit-to-wound = 6.
          5. Devastating Wounds: crit-to-wound bypasses saves (mortal wound).
          6. Otherwise roll d6 save vs better of (armour-after-AP) and invuln.

        Army-wide detachment rules and the Heavy keyword feed in as modifiers
        on hit_target, wound_target, n_attacks, save_target and the effective
        invuln before the loop runs.

        is_charging  - the attacker declared a charge this turn (Lance: +1 wound in melee)
        has_los      - the defender is visible from the attacker (Indirect Fire: -1 hit if False)
        """
        p = self.profile

        # ---- Buff lookups (detachment + in-range leader auras) -------------
        # Attacker side: detachment passives + every in-range friendly leader
        # whose aura covers this unit (re-rolls, +1 to hit/wound).
        # Target side: detachment passives + leader auras covering the target
        # (army-wide invuln, FNP). All composed via leaders.effective_buffs().
        from .leaders import effective_buffs
        att_buffs = effective_buffs(self)
        tgt_buffs = effective_buffs(target)

        if mode == "melee" and p.melee_attacks > 0:
            # Substitute the melee stat block for this resolution
            per_shot_dmg = p.melee_damage_per_shot or 1.0
            n_attacks = max(1, int(p.melee_attacks))
            hit_target = _prob_to_target(p.melee_hit_probability)
            strength = p.melee_strength
            ap = p.melee_ap
            ignore_cover = True   # melee always ignores cover
        else:
            per_shot_dmg = p.per_shot_damage
            n_attacks = max(1, int(p.attacks))
            hit_target = None     # set below
            strength = p.strength
            ap = p.ap
            ignore_cover = p.ignores_cover

        # ---- Range-dependent weapon keywords (Phase A2, ranged mode only) ----
        if mode != "melee":
            half_range = (p.range_inches or 24) / 2.0
            at_half_range = distance > 0 and distance <= half_range
            if at_half_range:
                n_attacks += int(p.rapid_fire)           # Rapid Fire X
                per_shot_dmg += float(p.melta)           # Melta X

        # ---- Blast: +1 attack per 5 enemy models in the target unit ----
        if p.blast and target.profile.blast is not None:  # always true; null-guard
            try:
                same_squad = sum(
                    1 for u in target.army_ref.alive_units
                    if u.profile.name == target.profile.name
                ) if target.army_ref is not None else 1
            except Exception:
                same_squad = 1
            n_attacks += same_squad // 5

        # ---- Buffs: +N extra attacks per weapon (detachment-only field) ----
        if att_buffs["plus_one_attack"]:
            n_attacks += int(att_buffs["plus_one_attack"])

        if hit_target is None:
            hit_target = _prob_to_target(p.hit_probability)
        wound_p = wound_probability(strength, target.profile.toughness)
        wound_target = _prob_to_target(wound_p)

        # ---- Buffs: +1 to hit / +1 to wound (lower the d6 target, min 2) ----
        if att_buffs["plus_one_to_hit"]:
            hit_target = max(2, hit_target - 1)
        if att_buffs["plus_one_to_wound"]:
            wound_target = max(2, wound_target - 1)

        # ---- Heavy keyword: +1 to hit when shooting and the attacker did
        # NOT move this round. Melee never benefits. Same math as +1-to-hit.
        if p.heavy and mode != "melee" and not self.moved_this_round:
            hit_target = max(2, hit_target - 1)

        # ---- Indirect Fire: -1 to hit when target is not visible (raises target).
        # Only meaningful in ranged mode.
        if p.indirect_fire and mode != "melee" and not has_los:
            hit_target = min(7, hit_target + 1)

        # ---- Lance: +1 to wound (lower wound_target by 1, min 2) when this
        # melee attack happens on a turn the attacker declared a charge.
        if p.lance and mode == "melee" and is_charging:
            wound_target = max(2, wound_target - 1)

        # ---- Heavy cover: -1 to hit (in addition to the +1 to save which
        # the plain in_cover flag already grants below). Ranged shots only;
        # melee always ignores cover. Ignores Cover bypasses both effects.
        if (
            mode != "melee"
            and target.in_heavy_cover
            and not ignore_cover
        ):
            hit_target = min(7, hit_target + 1)

        # ---- Stealth keyword: shooters take -1 to hit against the target.
        # Same math as a worsened hit roll. Capped at 7 (no possible hit).
        # Melee is unaffected (Stealth is a ranged defence).
        if mode != "melee" and target.profile.stealth:
            hit_target = min(7, hit_target + 1)

        # ---- Anti-X: lower the crit-wound threshold against matching keywords ----
        anti_crit_threshold = 6
        if p.anti_keywords and target.profile.unit_keywords:
            target_kw = set(target.profile.unit_keywords)
            for kw, thresh in p.anti_keywords:
                if kw in target_kw and thresh < anti_crit_threshold:
                    anti_crit_threshold = thresh

        save_after_ap = target.profile.save - ap
        # Precision: a ranged shot at a CHARACTER target pierces concealment —
        # cover does not improve the save. Same effect as Ignores Cover, but
        # gated on the target's keywords.
        precision_pierces_cover = (
            p.precision
            and mode != "melee"
            and "CHARACTER" in (target.profile.unit_keywords or ())
        )
        if target.in_cover and not ignore_cover and not precision_pierces_cover:
            save_after_ap = max(2, save_after_ap - 1)
        # ---- Target's buffs: +1 to armour save (cap 2+) ----
        if tgt_buffs["plus_one_save"]:
            save_after_ap = max(2, save_after_ap - 1)
        invuln = target.profile.invuln_save
        # ---- Target's buffs: army-wide invuln. Only overrides if better
        # (lower number) than what the target already has. 7 = unset.
        tgt_invuln_buff = int(tgt_buffs["extra_invuln"])
        if tgt_invuln_buff <= 6 and tgt_invuln_buff < invuln:
            invuln = tgt_invuln_buff
        effective_save = min(save_after_ap, invuln) if invuln <= 6 else save_after_ap
        save_target = effective_save  # 7 = no save

        # Re-roll flags from attacker's buffs.
        att_reroll_hit_ones = bool(att_buffs["reroll_hit_ones"])
        att_reroll_wound_ones = bool(att_buffs["reroll_wound_ones"])

        total_damage = 0.0
        for _ in range(n_attacks):
            # ---- Torrent: skip the to-hit roll, attack auto-hits ----
            if p.torrent:
                crit_hit = False   # torrent has no crit-on-hit
            else:
                roll = random.randint(1, 6)
                # Detachment "re-roll 1s to hit": replace the natural 1 with a
                # fresh d6, then proceed with the new value (used for crit /
                # threshold). Applies BEFORE crit detection per spec.
                if att_reroll_hit_ones and roll == 1:
                    roll = random.randint(1, 6)
                if roll < hit_target:
                    continue   # missed
                crit_hit = (roll == 6)
            n_hits = 1 + (p.sustained_hits if crit_hit else 0)

            for hit_i in range(n_hits):
                if p.lethal_hits and crit_hit and hit_i == 0:
                    wound_succeeded = True
                    crit_wound = False
                else:
                    wroll = random.randint(1, 6)
                    rerolled = False
                    # Re-roll natural 1s to wound (detachment). Compose with
                    # Twin-Linked (re-roll any failure) but never re-roll the
                    # same die twice.
                    if att_reroll_wound_ones and wroll == 1:
                        wroll = random.randint(1, 6)
                        rerolled = True
                    wound_succeeded = (wroll >= wound_target)
                    if not wound_succeeded and p.twin_linked and not rerolled:
                        wroll = random.randint(1, 6)
                        wound_succeeded = (wroll >= wound_target)
                    # Anti-X lowers the crit-wound threshold against that keyword
                    crit_wound = wound_succeeded and wroll >= anti_crit_threshold
                if not wound_succeeded:
                    continue

                tgt_fnp_buff = int(tgt_buffs["fnp"])
                if p.devastating_wounds and crit_wound:
                    target.receive_damage(per_shot_dmg, bonus_fnp=tgt_fnp_buff)
                    total_damage += per_shot_dmg
                    continue

                if save_target <= 6:
                    sroll = random.randint(1, 6)
                    if sroll >= save_target:
                        continue   # saved
                target.receive_damage(per_shot_dmg, bonus_fnp=tgt_fnp_buff)
                total_damage += per_shot_dmg

        # ---- Hazardous: d6 after firing; on a 1, take 3 mortal wounds ----
        if p.hazardous:
            if random.randint(1, 6) == 1:
                self.receive_damage(3.0)

        return total_damage

    def __repr__(self) -> str:
        return f"{self.profile.name}({self.current_health:.1f}/{self.profile.health}hp)"


# ---------------------------------------------------------------------------
# Unit catalogue
# ---------------------------------------------------------------------------
#
# Stats follow the SwegHammer abstraction (not 1:1 with any edition):
#   hit_probability: 1/2 = 4+, 2/3 = 3+, 5/6 = 2+ (on a d6)
#   ap:    0 = no AP,  -1 = AP1,  -2 = AP2,  -3 = AP3
#   save:  3 = 3+, 4 = 4+, 5 = 5+, 6 = 6+, 7 = no save
#   S / T: roughly aligned with 10th-edition datasheets, rounded for sanity
#
# UNIT_CATALOG is built at import time by merging:
#   data/bsdata/parsed.json — base stats from BSData WH40k 10th edition
#   data/overrides.json     — per-unit hand tuning
#
# To refresh the BSData base, run:
#     python -m code.bsdata.fetch --tag <release>
#     python -m code.bsdata.mapper
#
def _build_catalog(use_calibrated: bool = False) -> Dict[str, UnitProfile]:
    from .bsdata.loader import load_catalog
    from .factions import faction_of

    catalog: Dict[str, UnitProfile] = {}
    for key, entry in load_catalog(use_calibrated=use_calibrated).items():
        catalog[key] = UnitProfile(
            name=entry.name,
            health=entry.health,
            damage=entry.damage,
            hit_probability=entry.hit_probability,
            ap=entry.ap,
            save=entry.save,
            strength=entry.strength,
            toughness=entry.toughness,
            leadership=entry.leadership,
            oc=entry.oc,
            faction=faction_of(entry.codex),
            min_models=entry.min_models,
            max_models=entry.max_models,
            points_per_squad=entry.points_listed,
            attacks=entry.attacks,
            weapon_damage_per_shot=entry.weapon_damage_per_shot,
            lethal_hits=entry.lethal_hits,
            sustained_hits=entry.sustained_hits,
            twin_linked=entry.twin_linked,
            devastating_wounds=entry.devastating_wounds,
            invuln_save=entry.invuln_save,
            rapid_fire=entry.rapid_fire,
            melta=entry.melta,
            ignores_cover=entry.ignores_cover,
            anti_keywords=tuple((k, v) for k, v in (entry.anti_keywords or {}).items()),
            heavy=entry.heavy,
            assault=entry.assault,
            torrent=entry.torrent,
            hazardous=entry.hazardous,
            blast=entry.blast,
            lance=entry.lance,
            precision=entry.precision,
            pistol=entry.pistol,
            indirect_fire=entry.indirect_fire,
            one_shot=entry.one_shot,
            stealth=entry.stealth,
            deep_strike=entry.deep_strike,
            scout_distance=entry.scout_distance,
            infiltrator=entry.infiltrator,
            fnp=entry.fnp,
            unit_keywords=tuple(entry.unit_keywords or []),
            melee_attacks=entry.melee_attacks,
            melee_damage_per_shot=entry.melee_damage_per_shot,
            melee_hit_probability=entry.melee_hit_probability,
            melee_strength=entry.melee_strength,
            melee_ap=entry.melee_ap,
            melee_weapon=entry.melee_weapon,
            range_inches=entry.range_inches,
            points_override=entry.points_override,
        )
    return catalog


UNIT_CATALOG: Dict[str, UnitProfile] = _build_catalog()
# Same units, but with balancer-derived points overrides layered on (only
# converged calibration entries are applied). Lazily built when first
# requested so importing code.units stays cheap.
_BALANCED_CATALOG: Dict[str, UnitProfile] | None = None


def balanced_catalog() -> Dict[str, UnitProfile]:
    """Return the catalogue with calibrated_points.json applied as overrides."""
    global _BALANCED_CATALOG
    if _BALANCED_CATALOG is None:
        _BALANCED_CATALOG = _build_catalog(use_calibrated=True)
    return _BALANCED_CATALOG


# --- Dead code below: hand-rolled catalogue resurrected by an earlier merge
# conflict resolution. Kept for one beat in case anyone is mid-rebase, but
# the dict is immediately shadowed by `_build_catalog()` above and will be
# removed in a follow-up.
_LEGACY_HAND_ROLLED_CATALOG_SUPERSEDED: Dict[str, UnitProfile] = {
    # --- Space Marines ---
    "scout_marine": UnitProfile(
        name="Scout Marine",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "space_marine": UnitProfile(
        name="Space Marine",
        health=1, damage=1, hit_probability=2/3,
        ap=0, save=3, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "veteran_marine": UnitProfile(
        name="Veteran Marine",
        health=2, damage=1, hit_probability=2/3,
        ap=-1, save=3, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "terminator": UnitProfile(
        name="Terminator",
        health=3, damage=2, hit_probability=2/3,
        ap=-2, save=2, strength=5, toughness=5,
        move=5.0, range_inches=24,
    ),
    "dreadnought": UnitProfile(
        name="Dreadnought",
        health=8, damage=3, hit_probability=2/3,
        ap=-2, save=3, strength=7, toughness=10,
        move=6.0, range_inches=36,
    ),
    "predator_tank": UnitProfile(
        name="Predator Tank",
        health=11, damage=4, hit_probability=2/3,
        ap=-3, save=3, strength=9, toughness=10,
        move=10.0, range_inches=48,
    ),

    # --- Chaos ---
    "cultist": UnitProfile(
        name="Cultist",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=6, strength=3, toughness=3,
        move=6.0, range_inches=18,
    ),
    "chaos_space_marine": UnitProfile(
        name="Chaos Space Marine",
        health=2, damage=1, hit_probability=2/3,
        ap=-1, save=3, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "chaos_terminator": UnitProfile(
        name="Chaos Terminator",
        health=3, damage=2, hit_probability=2/3,
        ap=-2, save=2, strength=5, toughness=5,
        move=5.0, range_inches=24,
    ),
    "chaos_dreadnought": UnitProfile(
        name="Chaos Dreadnought",
        health=8, damage=3, hit_probability=2/3,
        ap=-2, save=3, strength=7, toughness=10,
        move=6.0, range_inches=36,
    ),

    # --- Orks ---
    "gretchin": UnitProfile(
        name="Gretchin",
        health=1, damage=1, hit_probability=1/3,
        ap=0, save=6, strength=2, toughness=3,
        move=5.0, range_inches=12,
    ),
    "ork_boy": UnitProfile(
        name="Ork Boy",
        health=2, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=5,
        move=6.0, range_inches=12,
    ),
    "ork_nob": UnitProfile(
        name="Ork Nob",
        health=3, damage=2, hit_probability=0.5,
        ap=-1, save=4, strength=5, toughness=5,
        move=6.0, range_inches=12,
    ),
    "mek_gun": UnitProfile(
        name="Mek Gun",
        health=5, damage=3, hit_probability=0.5,
        ap=-2, save=4, strength=6, toughness=6,
        move=4.0, range_inches=36,
    ),

    # --- Tyranids ---
    "termagant": UnitProfile(
        name="Termagant",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=3,
        move=6.0, range_inches=18,
    ),
    "hormagaunt": UnitProfile(
        name="Hormagaunt",
        health=1, damage=2, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=3,
        move=8.0, range_inches=1,
    ),
    "warrior": UnitProfile(
        name="Warrior",
        health=3, damage=2, hit_probability=2/3,
        ap=-1, save=4, strength=5, toughness=5,
        move=6.0, range_inches=24,
    ),
    "carnifex": UnitProfile(
        name="Carnifex",
        health=10, damage=4, hit_probability=2/3,
        ap=-3, save=3, strength=9, toughness=9,
        move=8.0, range_inches=18,
    ),
}
del _LEGACY_HAND_ROLLED_CATALOG_SUPERSEDED   # keep the symbol out of the namespace
