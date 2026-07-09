"""DuelGenome — the interpretable gene vector the genetic algorithm evolves.

Five genes in v1, each a numeric knob on one specific existing decision
heuristic. The NEUTRAL genome reproduces production behaviour byte-for-byte
(proven by tests/test_ai_lab_pilot_hooks.py); every gene's override is
structurally skipped at its neutral value, so attaching a neutral pilot to a
Battle changes nothing.

GENE_SPECS drives population initialisation, mutation, crossover, and the
Streamlit sliders generically — adding a sixth gene later is one new spec row
plus its pilot override, not a new code path.

Deferred future genes (named in docs/AI_LAB_PLAN.md so they are not
forgotten): focus_target_bias (which enemy model to focus fire — rides the
existing Battle._pilot_focus hook), charge_target_bias (whom to charge),
cover_seek_radius_bonus (needs pick_move_intent to expose the pre-snap
cover-search centre first).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, fields
from typing import Dict, NamedTuple, Tuple


class GeneSpec(NamedTuple):
    name: str
    neutral: float
    low: float
    high: float
    mutation_sigma: float


# One row per gene. Ranges chosen so the extremes are meaningfully different
# play styles but not degenerate (a 0.0 charge_aggression would just be the
# never-charge unit the melee floor already produces).
GENE_SPECS: Tuple[GeneSpec, ...] = (
    # Multiplies melee damage-per-activation in Battle._wants_to_charge before
    # the max(ranged_dpa, 1.0) comparison. >1 charges marginal trades, <1 only
    # clearly-favourable ones. 1.0 reproduces _wants_to_charge exactly.
    GeneSpec("charge_aggression", 1.0, 0.4, 2.5, 0.15),
    # Scales the 12.0" charge-threat buffer in pick_move_intent's DUAL branch
    # (via the army-level _ai_lab_dual_scales attribute read inside the
    # branch, so a narrowed pick falls through to objective logic naturally).
    GeneSpec("charge_range_buffer", 1.0, 0.4, 2.0, 0.12),
    # Scales the 0.1 _melee_target_score acceptance threshold in the same
    # branch — the "risk tolerance for committing to melee" knob. Range
    # calibrated against the Intercessor mirror: the raw
    # _melee_target_score(intercessor, intercessor) is ~1.19, so the veto
    # goes live at gene ~11.9 — the range must reach past that (and the
    # sigma be large enough to get there in a few mutations) or the knob is
    # dead across the whole flagship duel.
    GeneSpec("melee_engage_score_min", 1.0, 0.2, 20.0, 3.0),
    # Inches to nudge a HOLD intent toward (+) or away from (-) the nearest
    # enemy. 0.0 = structurally skipped (no override built).
    GeneSpec("advance_vs_hold_bias", 0.0, -4.0, 4.0, 0.5),
    # Stand-off slack in inches: on an ENGAGE intent a ranged-dominant unit
    # already in weapon range holds instead of closing, provided staying keeps
    # at least this many inches clear beyond engagement range. <= 0.0 =
    # structurally skipped (explicit early-return, like the SWEG_KITING gate).
    GeneSpec("kite_hold_range", 0.0, 0.0, 8.0, 0.75),
)

_SPEC_BY_NAME: Dict[str, GeneSpec] = {s.name: s for s in GENE_SPECS}


@dataclass(frozen=True)
class DuelGenome:
    charge_aggression: float = 1.0
    charge_range_buffer: float = 1.0
    melee_engage_score_min: float = 1.0
    advance_vs_hold_bias: float = 0.0
    kite_hold_range: float = 0.0

    def as_dict(self) -> Dict[str, float]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "DuelGenome":
        # Fail loud on unknown or missing keys (CLAUDE.md rule 13): a typo'd
        # gene name silently defaulting would corrupt a whole run's lineage.
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise KeyError(
                f"DuelGenome.from_dict: unknown gene(s) {sorted(unknown)}; "
                f"known genes are {sorted(known)}"
            )
        missing = known - set(d)
        if missing:
            raise KeyError(
                f"DuelGenome.from_dict: missing gene(s) {sorted(missing)}"
            )
        return cls(**{k: float(v) for k, v in d.items()})

    def is_neutral(self) -> bool:
        return all(
            getattr(self, s.name) == s.neutral for s in GENE_SPECS
        )


NEUTRAL_GENOME = DuelGenome()

# Sanity check at import time: the dataclass defaults and GENE_SPECS neutrals
# must agree, or the byte-identity guarantee silently rots.
for _s in GENE_SPECS:
    if getattr(NEUTRAL_GENOME, _s.name) != _s.neutral:
        raise AssertionError(
            f"GENE_SPECS neutral for {_s.name!r} ({_s.neutral}) disagrees "
            f"with DuelGenome default ({getattr(NEUTRAL_GENOME, _s.name)})"
        )


def _clamp(value: float, spec: GeneSpec) -> float:
    return max(spec.low, min(spec.high, value))


def random_genome(rng: random.Random, center: DuelGenome = NEUTRAL_GENOME) -> DuelGenome:
    """Gaussian jitter around `center`, clamped to each gene's range.

    Used for the initial population (center = the epoch's baseline) and for
    reseeding after a promotion (center = the newly promoted champion), so
    each epoch explores the neighbourhood of the current best strain.
    """
    values = {}
    for spec in GENE_SPECS:
        base = getattr(center, spec.name)
        values[spec.name] = _clamp(rng.gauss(base, spec.mutation_sigma), spec)
    return DuelGenome(**values)


def mutate(genome: DuelGenome, rng: random.Random,
           sigma_scale: float = 1.0) -> DuelGenome:
    """Per-gene Gaussian noise at GENE_SPECS sigma (scaled), clamped."""
    values = {}
    for spec in GENE_SPECS:
        base = getattr(genome, spec.name)
        values[spec.name] = _clamp(
            rng.gauss(base, spec.mutation_sigma * sigma_scale), spec
        )
    return DuelGenome(**values)


def crossover(a: DuelGenome, b: DuelGenome, rng: random.Random) -> DuelGenome:
    """Blend crossover: per-gene random weight in [0, 1] between the parents.

    Appropriate for a small real-valued vector — every child gene lies on the
    segment between its parents' values, so it needs no re-clamping.
    """
    values = {}
    for spec in GENE_SPECS:
        w = rng.random()
        va = getattr(a, spec.name)
        vb = getattr(b, spec.name)
        values[spec.name] = w * va + (1.0 - w) * vb
    return DuelGenome(**values)
