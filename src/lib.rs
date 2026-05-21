use pyo3::prelude::*;

// ---------------------------------------------------------------------------
// Pure-math combat primitives ported from code/units.py and code/strategy.py.
// All functions operate on primitive types only — no Python objects cross the
// FFI boundary. Inlined so the compiler can constant-fold calls inside
// durability_core without a separate function-call frame.
// ---------------------------------------------------------------------------

#[inline(always)]
fn wound_probability_inner(strength: i32, toughness: i32) -> f64 {
    // Standard 40K wound table (units.py:wound_probability).
    if strength >= 2 * toughness {
        return 5.0 / 6.0;
    }
    if 2 * strength <= toughness {
        return 1.0 / 6.0;
    }
    if strength > toughness {
        return 4.0 / 6.0;
    }
    if strength == toughness {
        return 3.0 / 6.0;
    }
    2.0 / 6.0 // strength < toughness but not 2S <= T
}

#[inline(always)]
fn save_probability_inner(save: i32, ap: i32, in_cover: bool, is_infantry: bool) -> f64 {
    // Mirrors units.py:save_probability.
    // ap is a NEGATIVE integer: AP-1 stored as -1, so effective = save - ap = save + 1.
    let mut effective = save - ap;
    if in_cover {
        let mut improved = effective - 1; // cover improves save by 1 pip
        if is_infantry {
            // INFANTRY cannot improve save beyond 3+ via cover.
            improved = improved.max(3);
        }
        improved = improved.max(2); // universal 2+ armour floor
        // Cover never makes a save worse than it already was.
        effective = effective.min(improved);
    }
    if effective > 6 {
        return 0.0; // save negated entirely
    }
    f64::max(0.0, (7 - effective) as f64 / 6.0)
}

#[inline(always)]
fn unsaved_fraction_inner(save: i32, invuln_save: i32, attacker_ap: i32) -> f64 {
    // Mirrors strategy.py:_unsaved_fraction (was lru_cache'd there).
    let save_pass = save_probability_inner(save, attacker_ap, false, true);
    let invuln_pass = if invuln_save <= 6 {
        save_probability_inner(invuln_save, 0, false, true)
    } else {
        0.0
    };
    f64::max(0.05, 1.0 - f64::max(save_pass, invuln_pass))
}

#[inline(always)]
fn fnp_pass_fraction_inner(fnp: i32) -> f64 {
    // Mirrors strategy.py:_fnp_pass_fraction.
    if fnp >= 7 {
        return 0.0;
    }
    if fnp <= 2 {
        return 5.0 / 6.0;
    }
    (7 - fnp) as f64 / 6.0
}

// ---------------------------------------------------------------------------
// Exported Python functions
// ---------------------------------------------------------------------------

#[pyfunction]
fn wound_probability(strength: i32, toughness: i32) -> f64 {
    wound_probability_inner(strength, toughness)
}

#[pyfunction]
#[pyo3(signature = (save, ap=0, in_cover=false, is_infantry=true))]
fn save_probability(save: i32, ap: i32, in_cover: bool, is_infantry: bool) -> f64 {
    save_probability_inner(save, ap, in_cover, is_infantry)
}

#[pyfunction]
fn unsaved_fraction(save: i32, invuln_save: i32, attacker_ap: i32) -> f64 {
    unsaved_fraction_inner(save, invuln_save, attacker_ap)
}

#[pyfunction]
fn fnp_pass_fraction(fnp: i32) -> f64 {
    fnp_pass_fraction_inner(fnp)
}

/// Combined durability calculation — takes only primitives, avoids repeated
/// Python↔Rust round-trips for the armour/invuln/FNP arithmetic.
///
/// Mirrors strategy.py:_durability's final arithmetic after the Python side
/// has resolved fnp (via _fnp_resolved) and squad_factor (via _squad_size_factor).
///
/// toughness     : defender profile toughness characteristic
/// health        : defender current_health (raw, clamped to ≥ 1.0 here)
/// squad_factor  : multiplicative squad-size bonus (1.0 for lone model)
/// save          : defender base armour save (e.g. 3 means 3+)
/// invuln_save   : defender invuln save (7 = no invuln)
/// ap            : attacker AP (negative integer; AP-1 = -1)
/// fnp_mitigation: 1.0 − fnp_pass_fraction, already clamped to ≥ 0.05 by caller
#[pyfunction]
fn durability_core(
    toughness: i32,
    health: f64,
    squad_factor: f64,
    save: i32,
    invuln_save: i32,
    ap: i32,
    fnp_mitigation: f64,
) -> f64 {
    let unsaved = unsaved_fraction_inner(save, invuln_save, ap);
    (toughness as f64 * f64::max(1.0, health) * squad_factor) / (unsaved * fnp_mitigation)
}

#[pymodule]
fn sweghammer_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(wound_probability, m)?)?;
    m.add_function(wrap_pyfunction!(save_probability, m)?)?;
    m.add_function(wrap_pyfunction!(unsaved_fraction, m)?)?;
    m.add_function(wrap_pyfunction!(fnp_pass_fraction, m)?)?;
    m.add_function(wrap_pyfunction!(durability_core, m)?)?;
    Ok(())
}
