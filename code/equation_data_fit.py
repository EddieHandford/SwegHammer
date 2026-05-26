"""
Data-driven equation fit: regress GW points on unit stats.

Replaces the sim-driven Track 3 pipeline that ran into a Stage 1 ceiling
(see ROADMAP.md "Track 4" and memory note project_data_driven_equation_fit).
The model is a Generalized Additive Model:

    log(price_per_model) = β₀ + Σ_i β_i · transform_i(feature_i)

Each feature has a configurable transform (linear / log / quadratic / cubic /
sqrt). Weights are fit by ordinary least squares against GW points, then
scaled per-faction by a tournament-meta multiplier so factions that
over-perform at GW pricing get marked up and under-performers get marked
down. The fit runs in milliseconds; no simulator involvement.

Public API
----------
extract_features(catalog)            -> pd.DataFrame
default_feature_specs()              -> List[FeatureSpec]
fit(features_df, specs, ...)         -> FitResult
predict(features_df, fit_result, ...) -> np.ndarray
faction_multipliers(snapshot, alpha) -> Dict[str, float]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .leaders import lookup_ability
from .units import UNIT_CATALOG, UnitProfile

# Reference target for the "expected damage" utility derivatives.
# A baseline Marine: T6, Sv3+ (3+ armour save → fails AP-modified rolls
# at probability (3 - ap - 1)/6 clamped to [0, 1]), no FNP, 2 wounds.
# Picked because it's the canonical mid-tier statline and matches the
# anchor unit (Intercessor Squad at 16 pts/model).
_REF_T = 6
_REF_SV = 3
_REF_FNP = 7   # 7 = no FNP

# Allowed transform names. Each maps a column to its transformed form.
# Order in this dict drives the UI options.
_TRANSFORMS: Dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "linear":    lambda x: x,
    "log":       lambda x: np.log1p(np.maximum(0.0, x)),  # log(1+x) — safe at 0
    "sqrt":      lambda x: np.sqrt(np.maximum(0.0, x)),
    "quadratic": lambda x: np.square(x),
    "cubic":     lambda x: np.power(x, 3),
}


def transform_names() -> List[str]:
    """Return the list of allowed transform identifiers, UI-ordered."""
    return list(_TRANSFORMS.keys())


# ---------------------------------------------------------------------------
# Feature specification
# ---------------------------------------------------------------------------

@dataclass
class FeatureSpec:
    """How a single feature is transformed and whether it's included in the fit."""
    name: str
    transform: str = "linear"
    include: bool = True
    description: str = ""

    def apply(self, values: np.ndarray) -> np.ndarray:
        if self.transform not in _TRANSFORMS:
            raise ValueError(
                f"Unknown transform {self.transform!r} for feature {self.name!r}; "
                f"expected one of {list(_TRANSFORMS.keys())}"
            )
        return _TRANSFORMS[self.transform](values.astype(float))


def default_feature_specs() -> List[FeatureSpec]:
    """The starting feature set. Tunable via the Streamlit UI later."""
    return [
        # Defensive stats — durability drives a big share of cost.
        FeatureSpec("wounds_per_model", "log", True,
                    "Wounds per model (log). Bigger units are quadratically tougher; "
                    "log captures diminishing returns."),
        FeatureSpec("toughness", "linear", True,
                    "Toughness stat. Each point raises the S-vs-T wound table by a step."),
        FeatureSpec("save_quality", "linear", True,
                    "Armour save quality (7 minus save target). 4 for Sv3+, 5 for Sv2+, 0 for no save."),
        FeatureSpec("invuln_quality", "linear", True,
                    "Invulnerable save quality (7 minus invuln target). 0 if none."),
        FeatureSpec("fnp_quality", "linear", True,
                    "Feel No Pain quality (7 minus FNP target). 0 if none."),

        # Offensive ranged.
        FeatureSpec("ranged_attacks", "linear", True,
                    "Ranged shots per shooting phase (BSData attacks field)."),
        FeatureSpec("ranged_strength", "linear", True,
                    "Ranged weapon strength."),
        FeatureSpec("ranged_ap_abs", "linear", True,
                    "Absolute value of ranged AP (0 = AP0, 5 = AP-5)."),
        FeatureSpec("ranged_damage_per_shot", "linear", True,
                    "Damage per ranged hit."),
        FeatureSpec("ranged_range", "linear", True,
                    "Weapon range in inches. Long-range weapons engage from turn 1."),

        # Offensive melee.
        FeatureSpec("melee_attacks", "linear", True,
                    "Melee attacks per fight phase."),
        FeatureSpec("melee_strength", "linear", True,
                    "Melee weapon strength."),
        FeatureSpec("melee_ap_abs", "linear", True,
                    "Absolute value of melee AP."),
        FeatureSpec("melee_damage_per_shot", "linear", True,
                    "Damage per melee hit."),

        # Mobility + objective.
        FeatureSpec("move", "linear", True, "Movement characteristic in inches."),
        FeatureSpec("oc", "linear", True, "Objective Control per model."),
        FeatureSpec("min_models", "log", True,
                    "Minimum squad size (log). Big squads aren't simply N× the value of one model."),

        # Boolean / integer keywords — each is a small lift to log price.
        FeatureSpec("lethal_hits", "linear", True, "1 if any LETHAL HITS, else 0."),
        FeatureSpec("sustained_hits", "linear", True, "Integer N for SUSTAINED HITS N (ranged)."),
        FeatureSpec("twin_linked", "linear", True, "1 if TWIN-LINKED, else 0."),
        FeatureSpec("devastating_wounds", "linear", True, "1 if DEVASTATING WOUNDS, else 0."),
        FeatureSpec("blast", "linear", True, "1 if BLAST keyword on primary weapon."),
        FeatureSpec("torrent", "linear", True, "1 if TORRENT (auto-hits)."),
        FeatureSpec("melta", "linear", True, "Integer N for MELTA N bonus damage at half range."),
        FeatureSpec("rapid_fire", "linear", True, "Integer N for RAPID FIRE N extra shots at half range."),
        FeatureSpec("ignores_cover", "linear", False, "1 if IGNORES COVER."),

        # Deployment abilities — often valuable for tactical play.
        FeatureSpec("deep_strike", "linear", True, "1 if DEEP STRIKE deployment."),
        FeatureSpec("scout_distance", "linear", True, "SCOUT N inches pre-game move (0 = no scout)."),
        FeatureSpec("infiltrator", "linear", True, "1 if INFILTRATORS."),
        FeatureSpec("lone_operative", "linear", True, "1 if LONE OPERATIVE."),
        FeatureSpec("stealth", "linear", True, "1 if STEALTH (-1 to be hit)."),

        # Interaction features — capture non-additive stat combinations.
        FeatureSpec("toughness_x_wounds", "log", True,
                    "log(toughness × wounds/model). Captures the synergy between high "
                    "toughness and many wounds — a T12/3W model is much tankier than "
                    "the additive terms alone express."),
        FeatureSpec("total_wounds", "log", True,
                    "log(wounds/model × min_models). Squad-level total wounds; a 10-model "
                    "2W squad has 20 wounds to absorb, priced differently from a single "
                    "20W monster even when wounds_per_model appears equal."),

        # Utility derivatives — computed from the raw stats above. Multicollinearity
        # with the raw stats is real but R² benefits from the extra structure,
        # and coefficient interpretability is not a goal at this stage.
        FeatureSpec("expected_ranged_dmg_vs_meq", "linear", True,
                    "Expected damage per shooting phase vs MEQ baseline (T6 Sv3+)."),
        FeatureSpec("expected_melee_dmg_vs_meq", "linear", True,
                    "Expected damage per fight phase vs MEQ baseline."),
        FeatureSpec("effective_wounds", "linear", True,
                    "Wounds × save × invuln × FNP combined survivability index."),

        # Big keyword classes (from unit_keywords).
        FeatureSpec("is_monster", "linear", True, "1 if MONSTER keyword."),
        FeatureSpec("is_vehicle", "linear", True, "1 if VEHICLE."),
        FeatureSpec("is_character", "linear", True, "1 if CHARACTER."),
        FeatureSpec("is_fly", "linear", True, "1 if FLY."),

        # Leader aura buffs — flattened from code.leaders.LeaderAbility via
        # lookup_ability(name). Zero for any unit not in the leader registry,
        # so each coefficient is the log-price lift GW implicitly charges for
        # a CHARACTER that grants that buff to its attached bodyguard squad.
        FeatureSpec("has_aura", "linear", True,
                    "1 if this unit is in the leader registry (grants any aura)."),
        FeatureSpec("aura_reroll_hit_ones", "linear", True,
                    "1 if leader aura grants re-roll hit rolls of 1."),
        FeatureSpec("aura_reroll_wound_ones", "linear", True,
                    "1 if leader aura grants re-roll wound rolls of 1."),
        FeatureSpec("aura_plus_one_to_hit", "linear", True,
                    "1 if leader aura grants +1 to hit."),
        FeatureSpec("aura_plus_one_to_wound", "linear", True,
                    "1 if leader aura grants +1 to wound."),
        FeatureSpec("aura_plus_one_attack", "linear", True,
                    "Integer N of extra attacks per weapon from leader aura."),
        FeatureSpec("aura_plus_one_strength_ranged", "linear", True,
                    "1 if leader aura grants +1 strength on ranged attacks."),
        FeatureSpec("aura_plus_one_toughness", "linear", True,
                    "1 if leader aura grants +1 toughness to the led unit."),
        FeatureSpec("aura_plus_one_ap_melee", "linear", True,
                    "1 if leader aura improves melee AP by 1."),
        FeatureSpec("aura_extra_invuln_quality", "linear", True,
                    "Quality (7 minus target) of an aura-granted invulnerable save."),
        FeatureSpec("aura_fnp_quality", "linear", True,
                    "Quality (7 minus target) of an aura-granted Feel No Pain."),
        FeatureSpec("aura_heal_per_round", "linear", True,
                    "Wounds healed each round end by leader aura."),
        FeatureSpec("aura_revive_per_round", "linear", True,
                    "Destroyed infantry models revived each round by leader aura."),
        FeatureSpec("aura_cp_discount_per_round", "linear", True,
                    "Bonus command points each command phase (Warlord-gated leader ability)."),
        FeatureSpec("aura_cp_refund_per_battle", "linear", True,
                    "One-shot command point refunds per battle (Warlord-gated)."),
        FeatureSpec("aura_first_strat_free", "linear", True,
                    "1 if first stratagem each round costs zero command points (Warlord-gated)."),

        # Direct hit probabilities — were previously only fed into the
        # off-by-default expected-damage derivative. Surfacing them as raw
        # features gives the regression a clean signal for ballistic /
        # weapon skill quality.
        FeatureSpec("ranged_hit_prob", "linear", True,
                    "Probability of landing a ranged hit (BS as 0..1)."),
        FeatureSpec("melee_hit_prob", "linear", True,
                    "Probability of landing a melee hit (WS as 0..1)."),

        # Effective attack volume — attacks weighted by hit quality.
        FeatureSpec("effective_ranged_shots", "linear", True,
                    "Ranged attacks × hit probability — bakes in BS quality."),
        FeatureSpec("effective_melee_attacks", "linear", True,
                    "Melee attacks × hit probability — bakes in WS quality."),

        # Secondary weapon profile. ~47% of the catalogue has a second
        # weapon (sergeant fist + bolter, vehicle with two-gun crew, etc.);
        # zeroed when the unit has no secondary attacks so the columns
        # don't double-count the primary weapon's stats.
        FeatureSpec("secondary_attacks", "linear", True,
                    "Attacks on the secondary weapon profile (0 if none)."),
        FeatureSpec("secondary_strength", "linear", True,
                    "Strength of the secondary weapon profile."),
        FeatureSpec("secondary_ap_abs", "linear", True,
                    "Absolute AP of the secondary weapon profile."),
        FeatureSpec("secondary_damage_per_shot", "linear", True,
                    "Damage per hit on the secondary weapon profile."),
        FeatureSpec("secondary_hit_probability", "linear", True,
                    "Hit probability on the secondary weapon profile."),
        FeatureSpec("secondary_pistol", "linear", True,
                    "1 if the secondary weapon is a Pistol (can shoot in engagement)."),

        # Special weapon and unit keywords. Each is a real 10e ability with
        # a price tag — invisibility to the fit was probably costing us
        # log-price lift on units that lean on these mechanics.
        FeatureSpec("pistol", "linear", True,
                    "1 if primary weapon is a Pistol (can shoot at 1.5\" while in engagement)."),
        FeatureSpec("precision", "linear", True,
                    "1 if PRECISION — can target attached CHARACTERs through their bodyguard squad."),
        FeatureSpec("hazardous", "linear", True,
                    "1 if HAZARDOUS — self-damage chance on activation."),
        FeatureSpec("assault", "linear", True,
                    "1 if ASSAULT — can shoot after Advancing."),
        FeatureSpec("heavy", "linear", True,
                    "1 if HEAVY — +1 to hit when stationary."),
        FeatureSpec("lance", "linear", True,
                    "1 if LANCE — +1 to wound in melee on the charge turn."),
        FeatureSpec("indirect_fire", "linear", True,
                    "1 if INDIRECT FIRE — ignores line of sight (-1 to hit non-visible)."),
        FeatureSpec("one_shot", "linear", True,
                    "1 if ONE SHOT — weapon fires once per battle."),
        FeatureSpec("fights_first", "linear", True,
                    "1 if FIGHTS FIRST — strikes before non-FIGHTS-FIRST in melee."),
        FeatureSpec("melee_sustained_hits", "linear", True,
                    "Integer N for SUSTAINED HITS N on the melee profile."),
        FeatureSpec("firing_deck", "linear", True,
                    "Integer N for FIRING DECK N — embarked passengers that shoot through the transport."),

        # Anti-X keyword encoding.
        FeatureSpec("n_anti_keywords", "linear", True,
                    "Count of distinct Anti-X keywords on the weapon."),
        FeatureSpec("best_anti_threshold_quality", "linear", True,
                    "Quality (7 - threshold) of the best Anti-X threshold; 5 = Anti-X 2+."),

        # Durability and explosion extras.
        FeatureSpec("deadly_demise", "linear", True,
                    "Mortal wounds dealt on explosion when destroyed (Deadly Demise X)."),
        FeatureSpec("leadership_quality", "linear", True,
                    "7 minus the Leadership stat. Higher = passes battleshock more easily."),
        # Necron Reanimation Protocols at the army-pool level. Sparse (17 of
        # 1479) but iconic Necron mechanic — keep on user request even though
        # the coefficient will have wide error bars.
        FeatureSpec("reanimates_with_army", "linear", True,
                    "1 if the unit reanimates from the army-wide Necron pool."),

        # Round-3 polynomial features — quadratic transforms on key stats.
        FeatureSpec("wounds_per_model_sq", "linear", True,
                    "Wounds per model, squared. Captures non-linear durability scaling at high W."),
        FeatureSpec("toughness_sq", "linear", True,
                    "Toughness squared. A T12 monster is much more than 2× as tough as T6."),
        FeatureSpec("ranged_ap_abs_sq", "linear", True,
                    "Ranged AP magnitude squared. AP-4 weapons gate more saves than AP-2."),
        FeatureSpec("melee_ap_abs_sq", "linear", True,
                    "Melee AP magnitude squared."),
        FeatureSpec("ranged_damage_per_shot_sq", "linear", True,
                    "Ranged damage per shot squared. Captures the spike-damage premium."),
        FeatureSpec("melee_damage_per_shot_sq", "linear", True,
                    "Melee damage per shot squared."),

        # Round-3 interaction features — multiplicative stat combinations.
        FeatureSpec("ranged_attacks_x_strength", "linear", True,
                    "Ranged attacks × strength. Captures raw offensive power."),
        FeatureSpec("melee_attacks_x_strength", "linear", True,
                    "Melee attacks × melee strength."),
        FeatureSpec("ranged_dmg_x_attacks", "linear", True,
                    "Ranged attacks × damage per shot. Total expected damage potential."),
        FeatureSpec("melee_dmg_x_attacks", "linear", True,
                    "Melee attacks × melee damage per shot."),
        FeatureSpec("is_vehicle_x_wounds", "linear", True,
                    "Vehicle keyword × wounds per model. Vehicle durability premium."),
        FeatureSpec("is_monster_x_wounds", "linear", True,
                    "Monster keyword × wounds per model. Monster durability premium."),
        FeatureSpec("is_character_x_wounds", "linear", True,
                    "Character keyword × wounds per model. Character durability premium."),
        FeatureSpec("move_x_oc", "linear", True,
                    "Move inches × OC. Captures mobile scoring units."),

        # Diminishing-returns transforms on attack volume.
        FeatureSpec("ranged_attacks_sqrt", "linear", True,
                    "sqrt(ranged attacks). Diminishing returns on volume vs saves."),
        FeatureSpec("melee_attacks_sqrt", "linear", True,
                    "sqrt(melee attacks)."),

        # Squad-wide attack potential — offensive analogue of total_wounds.
        FeatureSpec("total_ranged_attacks", "linear", True,
                    "Attacks × min_models. Squad-wide ranged volume."),
        FeatureSpec("total_melee_attacks", "linear", True,
                    "Melee attacks × min_models. Squad-wide melee volume."),

        # Round-4 log transforms on damage and attacks.
        FeatureSpec("log_ranged_damage_per_shot", "linear", True,
                    "log(1 + ranged damage). Captures diminishing marginal value of high flat damage."),
        FeatureSpec("log_melee_damage_per_shot", "linear", True,
                    "log(1 + melee damage)."),
        FeatureSpec("log_ranged_attacks", "linear", True,
                    "log(1 + ranged attacks). Diminishing marginal value of more shots."),
        FeatureSpec("log_melee_attacks", "linear", True,
                    "log(1 + melee attacks)."),

        # Round-4 cubic toughness — captures the super-quadratic jump at T11+.
        FeatureSpec("toughness_cubed", "linear", True,
                    "Toughness cubed. Captures the super-quadratic value of T11+ monsters."),

        # Round-4 keyword × attack-volume interactions.
        FeatureSpec("precision_x_ranged_attacks", "linear", True,
                    "PRECISION × ranged attacks. Precision's value scales with shot volume."),
        FeatureSpec("pistol_x_ranged_attacks", "linear", True,
                    "PISTOL × ranged attacks. Pistol engagement value scales with shot count."),
        FeatureSpec("assault_x_move", "linear", True,
                    "ASSAULT × move. Advance-and-shoot is worth more on fast units."),
        FeatureSpec("lance_x_melee_attacks", "linear", True,
                    "LANCE × melee attacks. Lance's +1 wound on charge scales with attack count."),
        FeatureSpec("heavy_x_ranged_attacks", "linear", True,
                    "HEAVY × ranged attacks. Heavy's +1 to hit scales with shot volume."),
        FeatureSpec("fights_first_x_melee_attacks", "linear", True,
                    "FIGHTS FIRST × melee attacks. Strike-first matters more on heavier hitters."),

        # Save quality scaled by wounds — captures the tank-class durability premium.
        FeatureSpec("save_quality_x_wounds", "linear", True,
                    "Armour save quality × wounds. A 2+ save on 10W is much more durable than on 1W."),
    ]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _save_quality(save_target: int) -> float:
    """Map a save target (2..7) to a 0..5 quality value. 7 = no save = 0."""
    if save_target is None or save_target <= 0 or save_target >= 7:
        return 0.0
    return float(max(0, 7 - save_target))


def _hit_prob_from_bs(hit_prob: float) -> float:
    """The catalogue already stores hit_probability as a 0..1 float; just clamp."""
    return float(max(0.0, min(1.0, hit_prob or 0.0)))


def _wound_prob(strength: int, toughness: int) -> float:
    """10e S-vs-T wound table."""
    if strength <= 0 or toughness <= 0:
        return 0.0
    if strength >= 2 * toughness: return 5.0 / 6.0
    if strength >  toughness:     return 4.0 / 6.0
    if strength == toughness:     return 3.0 / 6.0
    if strength * 2 <= toughness: return 1.0 / 6.0
    return 2.0 / 6.0


def _save_fail_prob(save_target: int, ap: int, invuln: int) -> float:
    """
    Probability a wound is not saved, given armour save target, attacker AP,
    and defender invulnerable save. Picks the better of armour-after-AP and
    invuln, then returns 1 minus the success probability of that save.
    """
    if save_target is None: save_target = 7
    if invuln is None: invuln = 7
    armour_after_ap = save_target - ap          # ap is negative, so this gets worse
    best_save = min(armour_after_ap, invuln)
    if best_save > 6:
        return 1.0   # no save possible
    if best_save < 2:
        best_save = 2  # 1s always fail
    # Save succeeds on best_save..6 inclusive: (7 - best_save) out of 6.
    success_p = max(0.0, min(1.0, (7 - best_save) / 6.0))
    return max(0.0, 1.0 - success_p)


def _expected_dmg_vs_ref(
    attacks: int, hit_p: float, strength: int, ap: int, dmg_per_shot: float,
    ref_t: int = _REF_T, ref_sv: int = _REF_SV, ref_fnp: int = _REF_FNP,
) -> float:
    """Expected damage per phase vs the MEQ reference defender."""
    if attacks <= 0 or hit_p <= 0 or dmg_per_shot <= 0:
        return 0.0
    wound_p = _wound_prob(strength, ref_t)
    fail_p = _save_fail_prob(ref_sv, ap, invuln=7)
    fnp_pass = max(0.0, min(1.0, (7 - ref_fnp) / 6.0)) if ref_fnp <= 6 else 0.0
    fnp_through = 1.0 - fnp_pass
    return float(attacks * hit_p * wound_p * fail_p * fnp_through * dmg_per_shot)


def _aura_features(profile_name: str) -> Dict[str, float]:
    """
    Flatten a unit's LeaderAbility (if any) into a fixed-shape feature dict.
    Returns all-zero defaults for non-leaders so the column set is uniform
    across the catalogue. Defensive aura targets (invuln, FNP) are mapped
    to the same 7-minus-target "quality" scale used for armour saves, so
    "no aura" reads as 0 and a 4+ FNP reads as 3.
    """
    ab = lookup_ability(profile_name)
    if ab is None:
        return {
            "has_aura": 0,
            "aura_reroll_hit_ones": 0,
            "aura_reroll_wound_ones": 0,
            "aura_plus_one_to_hit": 0,
            "aura_plus_one_to_wound": 0,
            "aura_plus_one_attack": 0,
            "aura_plus_one_strength_ranged": 0,
            "aura_plus_one_toughness": 0,
            "aura_plus_one_ap_melee": 0,
            "aura_extra_invuln_quality": 0.0,
            "aura_fnp_quality": 0.0,
            "aura_heal_per_round": 0,
            "aura_revive_per_round": 0,
            "aura_cp_discount_per_round": 0,
            "aura_cp_refund_per_battle": 0,
            "aura_first_strat_free": 0,
        }
    return {
        "has_aura": 1,
        "aura_reroll_hit_ones": int(bool(ab.reroll_hit_ones)),
        "aura_reroll_wound_ones": int(bool(ab.reroll_wound_ones)),
        "aura_plus_one_to_hit": int(bool(ab.plus_one_to_hit)),
        "aura_plus_one_to_wound": int(bool(ab.plus_one_to_wound)),
        "aura_plus_one_attack": int(ab.plus_one_attack or 0),
        "aura_plus_one_strength_ranged": int(bool(ab.plus_one_strength_ranged)),
        "aura_plus_one_toughness": int(bool(ab.plus_one_toughness)),
        "aura_plus_one_ap_melee": int(bool(ab.plus_one_ap_melee)),
        "aura_extra_invuln_quality": _save_quality(ab.extra_invuln),
        "aura_fnp_quality": _save_quality(ab.fnp),
        "aura_heal_per_round": int(ab.heal_per_round or 0),
        "aura_revive_per_round": int(ab.revive_destroyed_per_round or 0),
        "aura_cp_discount_per_round": int(ab.cp_discount_per_round or 0),
        "aura_cp_refund_per_battle": int(ab.cp_refund_per_battle or 0),
        "aura_first_strat_free": int(bool(ab.first_stratagem_free_per_round)),
    }


# ---------------------------------------------------------------------------
# Feature families — grouping for display purposes (HTML / dashboard).
# ---------------------------------------------------------------------------
# Many features in the model are correlated (wounds, wounds², toughness×wounds
# all measure durability) and the per-coefficient signs are arbitrary inside
# each cluster — OLS distributes weight in mathematically valid but visually
# confusing ways. Aggregating features into families before display sidesteps
# the multicollinearity: the SUM of a family's contributions is interpretable
# even when the individual coefficients aren't.
#
# Each feature appears in exactly one family. Used by bake_html_points.py and
# app.py to roll per-feature contributions up to per-family bars.
FEATURE_FAMILIES: Dict[str, List[str]] = {
    "Durability": [
        # Wounds, toughness, saves, FNP. Includes the per-keyword wound
        # interactions and the explode-on-death / reanimation specials.
        "wounds_per_model", "wounds_per_model_sq",
        "toughness", "toughness_sq", "toughness_cubed",
        "toughness_x_wounds", "total_wounds", "effective_wounds",
        "save_quality", "invuln_quality", "fnp_quality",
        "save_quality_x_wounds",
        "is_monster_x_wounds", "is_vehicle_x_wounds", "is_character_x_wounds",
        "deadly_demise", "reanimates_with_army",
    ],
    "Offense": [
        # Ranged + melee weapon stats together — for a playtester this is one
        # concept ("how hard the unit hits") and splitting muddies the chart.
        "ranged_attacks", "ranged_strength", "ranged_ap_abs", "ranged_ap_abs_sq",
        "ranged_damage_per_shot", "ranged_damage_per_shot_sq", "ranged_range",
        "ranged_hit_prob",
        "log_ranged_damage_per_shot", "log_ranged_attacks", "ranged_attacks_sqrt",
        "ranged_attacks_x_strength", "ranged_dmg_x_attacks",
        "total_ranged_attacks", "expected_ranged_dmg_vs_meq",
        "effective_ranged_shots",
        "secondary_attacks", "secondary_strength", "secondary_ap_abs",
        "secondary_damage_per_shot", "secondary_hit_probability",
        "secondary_pistol",
        "melee_attacks", "melee_strength", "melee_ap_abs", "melee_ap_abs_sq",
        "melee_damage_per_shot", "melee_damage_per_shot_sq",
        "melee_hit_prob",
        "log_melee_damage_per_shot", "log_melee_attacks", "melee_attacks_sqrt",
        "melee_attacks_x_strength", "melee_dmg_x_attacks",
        "total_melee_attacks", "expected_melee_dmg_vs_meq",
        "effective_melee_attacks", "melee_sustained_hits",
    ],
    "Mobility": [
        "move", "oc", "move_x_oc",
        "deep_strike", "scout_distance", "infiltrator",
        "lone_operative", "stealth",
    ],
    "Special abilities": [
        # Weapon keywords (precision / lance / assault / heavy / anti-X / etc.)
        # + leader aura buffs — both are "the unit does something special on
        # top of its raw stats", which is the playtester's mental model.
        "lethal_hits", "sustained_hits", "twin_linked", "devastating_wounds",
        "blast", "torrent", "melta", "rapid_fire", "ignores_cover",
        "precision", "lance", "heavy", "assault", "hazardous", "pistol",
        "indirect_fire", "one_shot", "fights_first", "firing_deck",
        "n_anti_keywords", "best_anti_threshold_quality",
        "precision_x_ranged_attacks", "pistol_x_ranged_attacks",
        "assault_x_move", "lance_x_melee_attacks",
        "heavy_x_ranged_attacks", "fights_first_x_melee_attacks",
        "aura_reroll_hit_ones", "aura_reroll_wound_ones",
        "aura_plus_one_to_hit", "aura_plus_one_to_wound",
        "aura_plus_one_attack",
        "aura_plus_one_strength_ranged", "aura_plus_one_toughness",
        "aura_plus_one_ap_melee",
        "aura_extra_invuln_quality", "aura_fnp_quality",
        "aura_heal_per_round", "aura_revive_per_round",
        "aura_cp_discount_per_round", "aura_cp_refund_per_battle",
        "aura_first_strat_free",
    ],
    # NOTE: A handful of features are deliberately NOT in any family and
    # therefore do not show up in the playtester chart:
    #   * min_models — the squad-size discount (negative coefficient because
    #     bigger squads cost less per model; correct math but confusing in a
    #     "what makes a unit cost more" chart).
    #   * is_monster / is_vehicle / is_character / is_fly — unit-type fixed
    #     effects that adjust the baseline price without being a stat the
    #     player feels day-to-day.
    #   * leadership_quality — battleshock target, low individual signal.
    #   * has_aura — redundant with the aura_* features.
    # These still contribute to the equation's prediction; they're just not
    # surfaced as their own bar. compute_family_contributions skips features
    # that don't appear in any family.
}


def feature_to_family() -> Dict[str, str]:
    """Reverse FEATURE_FAMILIES into a feature -> family lookup dict."""
    out: Dict[str, str] = {}
    for family, features in FEATURE_FAMILIES.items():
        for f in features:
            out[f] = family
    return out


def compute_family_contributions(
    features_df: pd.DataFrame,
    fit_result: "FitResult",
    specs: Sequence["FeatureSpec"],
) -> Dict[str, np.ndarray]:
    """Per-family signed contribution to log(price), one row per unit.

    Returns ``{family_name: ndarray of shape (n_units,)}``. Each entry is the
    sum of ``coefficient × transform(feature_value)`` across the family's
    features for that unit. Signs are preserved — when summed inside a
    family, the OLS noise mostly cancels and the family total reflects the
    actual price effect.
    """
    f2f = feature_to_family()
    spec_by_name = {s.name: s for s in specs}
    coef_by_name = dict(zip(fit_result.feature_names, fit_result.coefficients))

    family_arrays: Dict[str, np.ndarray] = {
        family: np.zeros(len(features_df)) for family in FEATURE_FAMILIES
    }

    for name, coef in coef_by_name.items():
        family = f2f.get(name)
        if family is None:
            continue
        spec = spec_by_name.get(name)
        if spec is None:
            continue
        transformed = spec.apply(features_df[name].to_numpy())
        family_arrays[family] += float(coef) * transformed

    return family_arrays


def _effective_wounds(w: float, save_q: float, inv_q: float, fnp_q: float) -> float:
    """Defensive durability index. Multiplicative bonus from each save layer."""
    save_factor = 1.0 + save_q / 6.0          # +1 save quality ≈ +17% effective wounds
    inv_factor  = 1.0 + inv_q / 6.0
    fnp_factor  = 1.0 + fnp_q / 6.0
    return w * save_factor * inv_factor * fnp_factor


def extract_features(
    catalog: Optional[Dict[str, UnitProfile]] = None,
) -> pd.DataFrame:
    """Build a one-row-per-unit feature DataFrame from a UnitProfile dict."""
    if catalog is None:
        catalog = UNIT_CATALOG

    rows = []
    for key, u in catalog.items():
        gw_per_squad = u.points_per_squad if u.points_per_squad else 0.0
        gw_per_model = gw_per_squad / max(1, u.min_models) if gw_per_squad > 0 else 0.0

        save_q = _save_quality(u.save)
        inv_q  = _save_quality(getattr(u, "invuln_save", 7))
        fnp_q  = _save_quality(getattr(u, "fnp", 7))

        ranged_dmg = _expected_dmg_vs_ref(
            u.attacks or 0,
            _hit_prob_from_bs(u.hit_probability),
            u.strength or 0,
            u.ap or 0,
            u.weapon_damage_per_shot or 0,
        )
        melee_dmg = _expected_dmg_vs_ref(
            u.melee_attacks or 0,
            _hit_prob_from_bs(u.melee_hit_probability),
            u.melee_strength or 0,
            u.melee_ap or 0,
            u.melee_damage_per_shot or 0,
        )

        unit_kw = set(k.upper() for k in (u.unit_keywords or ()))
        aura = _aura_features(u.name)

        # Secondary weapon profile — zero out the whole block when this unit
        # has no second weapon (secondary_attacks == 0), so we don't get a
        # spurious "S=4" signal from the dataclass default on the ~50% of
        # the catalogue that's single-profile.
        sec_atk = int(u.secondary_attacks or 0)
        has_secondary = sec_atk > 0
        sec_str = int(u.secondary_strength or 0) if has_secondary else 0
        sec_ap = int(abs(u.secondary_ap or 0)) if has_secondary else 0
        sec_dmg = float(u.secondary_weapon_damage_per_shot or 0) if has_secondary else 0.0
        sec_hp = float(u.secondary_hit_probability or 0) if has_secondary else 0.0

        anti_kws = u.anti_keywords or ()
        n_anti = len(anti_kws)
        best_anti_q = max((7 - int(threshold) for _, threshold in anti_kws), default=0)

        ranged_hp = _hit_prob_from_bs(u.hit_probability)
        melee_hp = _hit_prob_from_bs(u.melee_hit_probability)

        rows.append({
            "key": key,
            "name": u.name,
            "faction": u.faction or "Unknown",
            "gw_points_per_model": gw_per_model,
            "gw_points_per_squad": gw_per_squad,
            "min_models": int(u.min_models or 1),

            # Defensive
            "wounds_per_model": float(u.health or 0),
            "toughness": int(u.toughness or 0),
            "save_quality": save_q,
            "invuln_quality": inv_q,
            "fnp_quality": fnp_q,

            # Ranged
            "ranged_attacks": int(u.attacks or 0),
            "ranged_strength": int(u.strength or 0),
            "ranged_ap_abs": int(abs(u.ap or 0)),
            "ranged_damage_per_shot": float(u.weapon_damage_per_shot or 0),
            "ranged_range": float(u.range_inches or 0),

            # Melee
            "melee_attacks": int(u.melee_attacks or 0),
            "melee_strength": int(u.melee_strength or 0),
            "melee_ap_abs": int(abs(u.melee_ap or 0)),
            "melee_damage_per_shot": float(u.melee_damage_per_shot or 0),

            # Mobility / objective
            "move": float(u.move or 0),
            "oc": int(u.oc or 0),

            # Boolean / integer keywords
            "lethal_hits": int(bool(u.lethal_hits)),
            "sustained_hits": int(u.sustained_hits or 0),
            "twin_linked": int(bool(u.twin_linked)),
            "devastating_wounds": int(bool(u.devastating_wounds)),
            "blast": int(bool(u.blast)),
            "torrent": int(bool(u.torrent)),
            "melta": int(u.melta or 0),
            "rapid_fire": int(u.rapid_fire or 0),
            "ignores_cover": int(bool(u.ignores_cover)),

            # Deployment abilities
            "deep_strike": int(bool(u.deep_strike)),
            "scout_distance": int(u.scout_distance or 0),
            "infiltrator": int(bool(u.infiltrator)),
            "lone_operative": int(bool(u.lone_operative)),
            "stealth": int(bool(u.stealth)),

            # Utility derivatives
            "expected_ranged_dmg_vs_meq": ranged_dmg,
            "expected_melee_dmg_vs_meq":  melee_dmg,
            "effective_wounds": _effective_wounds(float(u.health or 0), save_q, inv_q, fnp_q),

            # Interaction / derived durability
            # toughness_x_wounds: captures the synergy between high toughness and many
            # wounds — e.g. a T12 3W unit is much tankier than additive stats suggest.
            "toughness_x_wounds": float((u.toughness or 0) * (u.health or 0)),
            # total_wounds: squad-level durability — wounds/model × squad size. A 10-model
            # squad with 2W/model has 20 effective wounds to chew through, priced differently
            # from a single 20W monster even if wounds_per_model alone looks similar.
            "total_wounds": float((u.health or 0) * max(1, u.min_models or 1)),

            # Unit-type keyword classes
            "is_monster":   int("MONSTER" in unit_kw),
            "is_vehicle":   int("VEHICLE" in unit_kw),
            "is_character": int("CHARACTER" in unit_kw),
            "is_fly":       int("FLY" in unit_kw),

            # Leader aura buffs — sourced from code.leaders._REGISTRY via
            # lookup_ability(name). Zero for any unit not in the registry, so
            # these columns act as a per-buff-type lift on log-price for
            # CHARACTER units that grant auras to their attached squad. The
            # regression decides which auras GW implicitly prices highest.
            **aura,

            # Direct hit probabilities (BS / WS). Always populated; previously
            # only consumed via the off-by-default expected_dmg derivative.
            "ranged_hit_prob": ranged_hp,
            "melee_hit_prob": melee_hp,

            # Effective attack volume — raw attacks × hit_prob. More honest
            # than raw attacks alone because a BS2+ shot and a BS5+ shot
            # don't deliver equal damage even at matched volume.
            "effective_ranged_shots": float(int(u.attacks or 0) * ranged_hp),
            "effective_melee_attacks": float(int(u.melee_attacks or 0) * melee_hp),

            # Secondary weapon profile (zeroed when has_secondary is False).
            "secondary_attacks": sec_atk,
            "secondary_strength": sec_str,
            "secondary_ap_abs": sec_ap,
            "secondary_damage_per_shot": sec_dmg,
            "secondary_hit_probability": sec_hp,
            "secondary_pistol": int(bool(u.secondary_pistol)),

            # Special weapon / unit keywords not previously in the fit.
            "pistol": int(bool(u.pistol)),
            "precision": int(bool(u.precision)),
            "hazardous": int(bool(u.hazardous)),
            "assault": int(bool(u.assault)),
            "heavy": int(bool(u.heavy)),
            "lance": int(bool(u.lance)),
            "indirect_fire": int(bool(u.indirect_fire)),
            "one_shot": int(bool(u.one_shot)),
            "fights_first": int(bool(u.fights_first)),
            "melee_sustained_hits": int(u.melee_sustained_hits or 0),
            "firing_deck": int(u.firing_deck or 0),

            # Anti-X keyword encoding. n_anti_keywords = how many Anti-X
            # entries the weapon has; best_anti_threshold_quality = 7 minus
            # the best (lowest) threshold across them, so Anti-VEHICLE 2+
            # scores 5 and Anti-INFANTRY 4+ scores 3.
            "n_anti_keywords": n_anti,
            "best_anti_threshold_quality": best_anti_q,

            # Durability and explosion extras.
            "deadly_demise": int(u.deadly_demise or 0),
            # Leadership quality: 7 minus Ld stat. Higher = passes battleshock
            # more easily. Ld5 → 2, Ld6 → 1, Ld7 (default) → 0, Ld8+ → negative.
            "leadership_quality": int(7 - int(u.leadership or 7)),
            # Necron Reanimation Protocols at army-pool level. Sparse (17
            # samples) but included on user request — it's the iconic Necron
            # mechanic and ignoring it would price every Necron unit too low.
            "reanimates_with_army": int(bool(u.reanimates_with_army)),

            # Round-3 polynomial features. Quadratic transforms capture the
            # super-linear value of high-end stats: a T12 monster is much
            # more than 2× as tough as a T6 marine, an AP-4 weapon is much
            # more than 2× as good as AP-2, etc.
            "wounds_per_model_sq": float((u.health or 0) ** 2),
            "toughness_sq": float((u.toughness or 0) ** 2),
            "ranged_ap_abs_sq": float(abs(u.ap or 0) ** 2),
            "melee_ap_abs_sq": float(abs(u.melee_ap or 0) ** 2),
            "ranged_damage_per_shot_sq": float((u.weapon_damage_per_shot or 0) ** 2),
            "melee_damage_per_shot_sq": float((u.melee_damage_per_shot or 0) ** 2),

            # Round-3 interaction features. Capture stat synergies the
            # additive model can't express on its own.
            "ranged_attacks_x_strength": float((u.attacks or 0) * (u.strength or 0)),
            "melee_attacks_x_strength": float((u.melee_attacks or 0) * (u.melee_strength or 0)),
            "ranged_dmg_x_attacks": float((u.attacks or 0) * (u.weapon_damage_per_shot or 0)),
            "melee_dmg_x_attacks": float((u.melee_attacks or 0) * (u.melee_damage_per_shot or 0)),
            # Durability premium scoped by unit type — a Monster with 12W
            # is priced differently from an Infantry character with 12W.
            "is_vehicle_x_wounds": float(int("VEHICLE" in unit_kw) * (u.health or 0)),
            "is_monster_x_wounds": float(int("MONSTER" in unit_kw) * (u.health or 0)),
            "is_character_x_wounds": float(int("CHARACTER" in unit_kw) * (u.health or 0)),
            # Mobile-scoring interaction — a fast objective-grabber is worth
            # more than the additive sum of its move and OC stats.
            "move_x_oc": float((u.move or 0) * (u.oc or 0)),

            # Diminishing-returns transforms on volume features. A unit with
            # 8 attacks isn't 8× as offensive as one with 1 attack against
            # the same defender — wound saves cap the realised damage.
            "ranged_attacks_sqrt": float((u.attacks or 0) ** 0.5),
            "melee_attacks_sqrt": float((u.melee_attacks or 0) ** 0.5),

            # Squad-wide attack potential — captures the offensive scaling
            # of blob squads the way `total_wounds` captures defensive scaling.
            "total_ranged_attacks": float((u.attacks or 0) * max(1, u.min_models or 1)),
            "total_melee_attacks": float((u.melee_attacks or 0) * max(1, u.min_models or 1)),

            # Round-4 log transforms — flat-N damage / N-attacks have
            # diminishing marginal value, so log shape often fits GW
            # pricing better than the linear or quadratic forms.
            "log_ranged_damage_per_shot": float(np.log1p(max(0.0, u.weapon_damage_per_shot or 0))),
            "log_melee_damage_per_shot": float(np.log1p(max(0.0, u.melee_damage_per_shot or 0))),
            "log_ranged_attacks": float(np.log1p(max(0, u.attacks or 0))),
            "log_melee_attacks": float(np.log1p(max(0, u.melee_attacks or 0))),

            # Round-4 cubic toughness — T11+ monsters scale super-quadratically
            # against most weapons because the wound table jumps in tiers.
            "toughness_cubed": float((u.toughness or 0) ** 3),

            # Round-4 keyword × volume interactions — these abilities scale
            # with how many attacks they're attached to. PRECISION on a
            # 1-shot sniper is worth less than on a 6-shot autorifle squad,
            # LANCE on 1 melee attack is barely a buff vs LANCE on 6.
            "precision_x_ranged_attacks": float(int(bool(u.precision)) * (u.attacks or 0)),
            "pistol_x_ranged_attacks": float(int(bool(u.pistol)) * (u.attacks or 0)),
            "assault_x_move": float(int(bool(u.assault)) * (u.move or 0)),
            "lance_x_melee_attacks": float(int(bool(u.lance)) * (u.melee_attacks or 0)),
            "heavy_x_ranged_attacks": float(int(bool(u.heavy)) * (u.attacks or 0)),
            "fights_first_x_melee_attacks": float(int(bool(u.fights_first)) * (u.melee_attacks or 0)),

            # Save quality scaled by wounds — a 1W marine with 2+ save is
            # not the same as a 10W terminator with 2+ save.
            "save_quality_x_wounds": float(save_q * (u.health or 0)),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fit
# ---------------------------------------------------------------------------

@dataclass
class FitResult:
    """Output of fit(). All arrays are aligned to the input DataFrame's row order."""
    feature_names: List[str]
    transforms: List[str]
    coefficients: np.ndarray       # one per included feature
    intercept: float
    predicted_log_price: np.ndarray
    predicted_price: np.ndarray
    residuals: np.ndarray          # log-space residuals (log(predicted) - log(actual))
    r_squared: float
    mae_log: float                 # MAE on log-price
    mae_price: float               # MAE on raw price (per model)


def _design_matrix(
    df: pd.DataFrame, specs: Sequence[FeatureSpec],
) -> tuple[np.ndarray, List[str], List[str]]:
    """Build the design matrix X for a fit. Returns (X, included_feature_names, transforms)."""
    cols = []
    names = []
    transforms = []
    for spec in specs:
        if not spec.include:
            continue
        if spec.name not in df.columns:
            raise KeyError(f"Feature {spec.name!r} not present in DataFrame columns.")
        cols.append(spec.apply(df[spec.name].to_numpy()))
        names.append(spec.name)
        transforms.append(spec.transform)
    if not cols:
        raise ValueError("No features included; toggle at least one FeatureSpec on.")
    X = np.column_stack(cols)
    return X, names, transforms


def fit(
    features_df: pd.DataFrame,
    specs: Optional[Sequence[FeatureSpec]] = None,
    target_col: str = "gw_points_per_model",
    min_target: float = 1.0,
) -> FitResult:
    """
    Fit ``log(price) = β·transform(features) + intercept`` via least squares.

    ``min_target`` clamps the lower bound on GW per-model price before taking
    the log; units with non-positive price are dropped from the fit (they
    have no training signal).
    """
    if specs is None:
        specs = default_feature_specs()

    valid_mask = features_df[target_col].to_numpy() >= min_target
    if not valid_mask.any():
        raise ValueError(f"No units with {target_col} >= {min_target}; cannot fit.")

    df_fit = features_df.loc[valid_mask].reset_index(drop=True)
    X_fit, names, transforms = _design_matrix(df_fit, specs)
    y_log = np.log(df_fit[target_col].to_numpy())

    # Augment with an intercept column.
    X_aug = np.column_stack([np.ones(X_fit.shape[0]), X_fit])
    coefs, _resid_sse, _rank, _sv = np.linalg.lstsq(X_aug, y_log, rcond=None)
    intercept = float(coefs[0])
    beta = coefs[1:]

    # Predict for the FULL DataFrame (not just the fit-eligible subset).
    X_all, _, _ = _design_matrix(features_df, specs)
    # The BLAS-backed matmul on numpy 2.x can emit benign "divide by zero" /
    # "overflow" warnings when the design matrix has wildly different
    # magnitudes between features (e.g. log(Wounds)~3 vs raw range~72). The
    # actual results remain finite and correct, so we suppress those warnings
    # here rather than rescale everything.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        predicted_log = intercept + X_all @ beta
        predicted_price = np.exp(predicted_log)

    # Residuals computed only where target is valid.
    y_full_log = np.where(valid_mask, np.log(np.maximum(min_target, features_df[target_col].to_numpy())), np.nan)
    residuals = predicted_log - y_full_log

    # R² on the fit subset, log-space.
    y_mean = float(np.mean(y_log))
    ss_tot = float(np.sum((y_log - y_mean) ** 2))
    ss_res = float(np.sum((predicted_log[valid_mask] - y_log) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    mae_log = float(np.nanmean(np.abs(residuals[valid_mask])))
    mae_price = float(np.nanmean(np.abs(
        predicted_price[valid_mask] - features_df.loc[valid_mask, target_col].to_numpy()
    )))

    return FitResult(
        feature_names=names,
        transforms=transforms,
        coefficients=beta,
        intercept=intercept,
        predicted_log_price=predicted_log,
        predicted_price=predicted_price,
        residuals=residuals,
        r_squared=r2,
        mae_log=mae_log,
        mae_price=mae_price,
    )


def predict(
    features_df: pd.DataFrame,
    fit_result: FitResult,
    specs: Optional[Sequence[FeatureSpec]] = None,
) -> np.ndarray:
    """Apply a stored FitResult to a (possibly different) feature DataFrame."""
    if specs is None:
        specs = default_feature_specs()
    # Filter specs to the features the fit knew about, in the fit's order.
    name_to_spec = {s.name: s for s in specs}
    ordered_specs = []
    for name, tform in zip(fit_result.feature_names, fit_result.transforms):
        spec = name_to_spec.get(name)
        if spec is None:
            spec = FeatureSpec(name=name, transform=tform)
        else:
            spec = FeatureSpec(name=name, transform=tform, include=True)
        ordered_specs.append(spec)
    X, _, _ = _design_matrix(features_df, ordered_specs)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        log_pred = fit_result.intercept + X @ fit_result.coefficients
        return np.exp(log_pred)


# ---------------------------------------------------------------------------
# Faction multipliers (real-meta correction)
# ---------------------------------------------------------------------------

def faction_multipliers(
    meta_snapshot: Dict,
    alpha: float = 2.0,
    clip: tuple = (0.5, 2.0),
) -> Dict[str, float]:
    """
    Compute per-faction price multipliers from the Warp-Friends snapshot.

    For each faction with real tournament data, ``multiplier = 1 + α · (winrate - 0.5)``,
    clipped to [clip_lo, clip_hi]. Factions in FX_ALL (no real data) get 1.0.
    """
    out: Dict[str, float] = {}
    factions = meta_snapshot.get("factions") or []
    for row in factions:
        faction = row.get("faction")
        if not faction:
            continue
        # FX_ALL placeholder factions are marked `is_approx=True` because
        # their tournament_pct is the 50 % midpoint guess, not a real
        # measurement. Skip them so the caller defaults their multiplier
        # to 1.0.
        if row.get("is_approx"):
            continue
        tournament_pct = row.get("tournament_pct")
        if tournament_pct is None:
            continue
        winrate = float(tournament_pct) / 100.0
        mult = 1.0 + alpha * (winrate - 0.5)
        mult = max(clip[0], min(clip[1], mult))
        out[faction] = float(mult)
    return out
