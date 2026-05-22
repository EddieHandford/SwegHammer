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
        FeatureSpec("ranged_range", "linear", False,
                    "Weapon range in inches. Often correlated with strength; off by default."),

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

        # Utility derivatives — computed from the raw stats above.
        FeatureSpec("expected_ranged_dmg_vs_meq", "linear", False,
                    "Expected damage per shooting phase vs MEQ baseline (T6 Sv3+). "
                    "Correlates with raw stats but captures keyword interactions; "
                    "off by default to avoid double-counting."),
        FeatureSpec("expected_melee_dmg_vs_meq", "linear", False,
                    "Expected damage per fight phase vs MEQ baseline."),
        FeatureSpec("effective_wounds", "linear", False,
                    "Wounds × save × invuln × FNP combined survivability index."),

        # Big keyword classes (from unit_keywords).
        FeatureSpec("is_monster", "linear", True, "1 if MONSTER keyword."),
        FeatureSpec("is_vehicle", "linear", True, "1 if VEHICLE."),
        FeatureSpec("is_character", "linear", True, "1 if CHARACTER."),
        FeatureSpec("is_fly", "linear", True, "1 if FLY."),
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

            # Unit-type keyword classes
            "is_monster":   int("MONSTER" in unit_kw),
            "is_vehicle":   int("VEHICLE" in unit_kw),
            "is_character": int("CHARACTER" in unit_kw),
            "is_fly":       int("FLY" in unit_kw),
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
