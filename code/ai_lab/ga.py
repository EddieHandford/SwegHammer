"""Genetic-algorithm engine: fitness, selection, crossover, generations.

Deliberately Streamlit-independent (no imports from app.py) so the engine is
unit-testable and runnable headless via scripts/ai_lab_run.py.

Randomness discipline (the docs/PILOT_FINDINGS.md lesson): battle dice come
from the GLOBAL random module, seeded per duel inside run_duel from
duel_seed(epoch, generation, duel_index) — a pure function of WHEN, never of
WHICH genome, so all genomes in a generation face identical dice (paired
common random numbers). All GENETIC randomness (selection draws, crossover
weights, mutation noise) comes from a dedicated random.Random instance the
caller owns, so bookkeeping randomness can never perturb battle dice.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..units import UNIT_CATALOG
from .duel import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_SQUAD_SIZE,
    duel_seed,
    run_duel,
)
from .genome import DuelGenome, NEUTRAL_GENOME, crossover, mutate, random_genome

# Confirmation batches use a disjoint seed lane (generation + this offset in
# duel_seed) so a champion is never confirmed on the very dice it was
# selected on — selection picked it BECAUSE it did well on those seeds, and
# re-using them would inflate the confirmation read (selection bias).
CONFIRMATION_LANE = 5_000

# Default confirmation batch size. Must be large enough that a confirmation
# win rate landing exactly at the default promotion_threshold (0.55) clears
# the Wilson 95% lower-bound requirement in evolve_lineage's promotion gate
# (> 0.5) — n=385 is the exact crossover point
# (min_confirmation_n_for_threshold(0.55) == 385); 500 keeps a real,
# non-razor-thin margin above it. Below this,
# promotion is not just unlikely but MATHEMATICALLY IMPOSSIBLE at the
# default threshold — this was a real bug (see docs/AI_LAB_PLAN.md
# "Promotion-gate consistency") where the shipped default of 200 made every
# run report "epoch exhausted without a promotion" regardless of how good
# the evolved genome actually was. evolve_lineage validates this
# relationship at the start of every run via min_confirmation_n_for_threshold
# so a future default drift (or a user's own Advanced-parameters tuning)
# fails loud instead of silently reproducing the same trap.
DEFAULT_CONFIRMATION_N = 500


@dataclass(frozen=True)
class FitnessResult:
    fitness: float      # win_rate + margin_weight * mean_margin
    win_rate: float     # (wins + 0.5 * draws) / n
    mean_margin: float  # mean points-remaining margin, in [-1, 1]
    wins: int
    losses: int
    draws: int
    n: int


def evaluate_fitness(genome: DuelGenome, baseline: DuelGenome,
                     epoch: int, generation: int, n_duels: int,
                     margin_weight: float = 0.2,
                     profile_key: str = DEFAULT_PROFILE_KEY,
                     squad_size: int = DEFAULT_SQUAD_SIZE) -> FitnessResult:
    """Fitness of `genome` against `baseline` over n_duels paired duels.

    The challenger alternates sides (duel_index % 2) so deployment-side and
    going-first asymmetries wash out. Draws count as half a win in win_rate.
    Margin per duel = (challenger points remaining - baseline points
    remaining) / one side's starting points — a continuous tie-breaker in
    [-1, 1] under the flat win/loss signal.
    """
    starting_points = UNIT_CATALOG[profile_key].points_cost * squad_size
    if starting_points <= 0:
        raise ValueError(
            f"ai_lab evaluate_fitness: starting points for {profile_key!r} "
            f"x{squad_size} computed as {starting_points!r} — cannot "
            "normalise margins"
        )
    wins = losses = draws = 0
    margin_sum = 0.0
    for duel_index in range(n_duels):
        seed = duel_seed(epoch, generation, duel_index)
        challenger_is_a = (duel_index % 2 == 0)
        if challenger_is_a:
            result = run_duel(genome, baseline, seed,
                              profile_key=profile_key, squad_size=squad_size)
            challenger_name = result.a_name
            margin = result.a_points_remaining - result.b_points_remaining
        else:
            result = run_duel(baseline, genome, seed,
                              profile_key=profile_key, squad_size=squad_size)
            challenger_name = result.b_name
            margin = result.b_points_remaining - result.a_points_remaining
        if result.winner is None:
            draws += 1
        elif result.winner == challenger_name:
            wins += 1
        else:
            losses += 1
        margin_sum += margin / starting_points
    win_rate = (wins + 0.5 * draws) / n_duels
    mean_margin = margin_sum / n_duels
    return FitnessResult(
        fitness=win_rate + margin_weight * mean_margin,
        win_rate=win_rate,
        mean_margin=mean_margin,
        wins=wins, losses=losses, draws=draws, n=n_duels,
    )


def wilson_lower_bound(p: float, n: int, z: float = 1.96) -> float:
    """Lower edge of the Wilson score interval for a binomial proportion.

    Self-contained on purpose — app.py has a half-width variant, but the
    engine must not import Streamlit-adjacent code.
    """
    if n <= 0:
        return 0.0
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    spread = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return (centre - spread) / denom


def min_confirmation_n_for_threshold(promotion_threshold: float,
                                     z: float = 1.96) -> int:
    """Smallest confirmation_n at which a confirmation batch landing EXACTLY
    at promotion_threshold clears the Wilson 95% lower-bound requirement
    (> 0.5) — the minimum sample size at which the promotion gate is even
    mathematically satisfiable.

    Exists because the two promotion-gate conditions
    (`confirmation.win_rate >= promotion_threshold` and
    `wilson_lower_bound(confirmation.win_rate, confirmation_n) > 0.5`) are
    NOT automatically consistent: at a small confirmation_n, the Wilson
    lower bound of a win rate sitting right at the threshold can be BELOW
    0.5, making every promotion attempt fail regardless of how good the
    genome actually is — the exact bug this function guards against (see
    docs/AI_LAB_PLAN.md "Promotion-gate consistency").
    """
    if promotion_threshold <= 0.5:
        raise ValueError(
            f"ai_lab min_confirmation_n_for_threshold: promotion_threshold "
            f"{promotion_threshold} must exceed 0.5 — a threshold at or "
            f"below break-even can never clear the Wilson lower bound at "
            f"any sample size."
        )
    n = 2
    while wilson_lower_bound(promotion_threshold, n, z=z) <= 0.5:
        n += 1
        if n > 1_000_000:
            raise ValueError(
                f"ai_lab min_confirmation_n_for_threshold: no sample size "
                f"under 1,000,000 clears the Wilson bound for threshold "
                f"{promotion_threshold} — threshold is too close to 0.5."
            )
    return n


@dataclass
class GenerationStats:
    epoch: int
    generation: int
    best_genome: DuelGenome
    best: FitnessResult
    mean_fitness: float
    mean_win_rate: float
    # (genome, fitness) for every population member, sorted best-first.
    scored: List[Tuple[DuelGenome, FitnessResult]] = field(repr=False,
                                                           default_factory=list)


def tournament_select(scored: List[Tuple[DuelGenome, FitnessResult]],
                      rng: random.Random, k: int = 3) -> DuelGenome:
    """Classic k-tournament: sample k entrants, return the fittest."""
    if not scored:
        raise ValueError("ai_lab tournament_select: empty scored population")
    entrants = [scored[rng.randrange(len(scored))] for _ in range(k)]
    return max(entrants, key=lambda pair: pair[1].fitness)[0]


def run_generation(population: List[DuelGenome], baseline: DuelGenome,
                   epoch: int, generation: int, duels_per_genome: int,
                   ga_rng: random.Random,
                   elite_count: int = 2,
                   tournament_k: int = 3,
                   margin_weight: float = 0.2,
                   mutation_sigma_scale: float = 1.0,
                   profile_key: str = DEFAULT_PROFILE_KEY,
                   squad_size: int = DEFAULT_SQUAD_SIZE,
                   ) -> Tuple[List[DuelGenome], GenerationStats]:
    """Evaluate every genome, then breed the next generation.

    Elitism: the top `elite_count` genomes carry over unchanged. The rest of
    the next generation is tournament-select two parents -> blend crossover
    -> Gaussian mutation. Deterministic given (population order, ga_rng
    state, epoch, generation): the duel seeds are fixed by the schedule and
    the genetic draws consume ga_rng in a fixed order.
    """
    if elite_count >= len(population):
        raise ValueError(
            f"ai_lab run_generation: elite_count ({elite_count}) must be "
            f"smaller than the population ({len(population)})"
        )
    scored = [
        (genome,
         evaluate_fitness(genome, baseline, epoch, generation,
                          duels_per_genome, margin_weight=margin_weight,
                          profile_key=profile_key, squad_size=squad_size))
        for genome in population
    ]
    scored.sort(key=lambda pair: pair[1].fitness, reverse=True)

    stats = GenerationStats(
        epoch=epoch,
        generation=generation,
        best_genome=scored[0][0],
        best=scored[0][1],
        mean_fitness=sum(f.fitness for _, f in scored) / len(scored),
        mean_win_rate=sum(f.win_rate for _, f in scored) / len(scored),
        scored=scored,
    )

    next_population: List[DuelGenome] = [g for g, _ in scored[:elite_count]]
    while len(next_population) < len(population):
        parent_a = tournament_select(scored, ga_rng, k=tournament_k)
        parent_b = tournament_select(scored, ga_rng, k=tournament_k)
        child = mutate(crossover(parent_a, parent_b, ga_rng), ga_rng,
                       sigma_scale=mutation_sigma_scale)
        next_population.append(child)
    return next_population, stats


# ---------------------------------------------------------------------------
# Epoch loop, promotion gate, lineage
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PromotionRecord:
    epoch: int
    generation: int             # generation whose champion was promoted
    champion: DuelGenome
    confirmation: FitnessResult
    wilson_lower: float
    generations_to_promote: int  # generations run this epoch, inclusive


def evolve_lineage(seed_base: int,
                   population_size: int,
                   generations_per_epoch: int,
                   duels_per_genome: int,
                   max_epochs: int,
                   promotion_threshold: float = 0.55,
                   confirmation_n: int = DEFAULT_CONFIRMATION_N,
                   elite_count: int = 2,
                   tournament_k: int = 3,
                   margin_weight: float = 0.2,
                   mutation_sigma_scale: float = 1.0,
                   initial_baseline: DuelGenome = NEUTRAL_GENOME,
                   profile_key: str = DEFAULT_PROFILE_KEY,
                   squad_size: int = DEFAULT_SQUAD_SIZE):
    """The full outer loop, as a generator of (kind, payload) events.

    A generator so both consumers — the headless scripts/ai_lab_run.py
    printer and the Streamlit live chart — drive the SAME loop instead of
    each reimplementing it. Events, in emission order:

      ("generation",   GenerationStats)   after every generation
      ("confirmation", PromotionRecord)   a confirmation batch ran (the
                                          record's wilson_lower says whether
                                          it passed; emitted either way)
      ("promotion",    PromotionRecord)   the gate passed — baseline is now
                                          the champion; population reseeded
                                          around it; next epoch begins
      ("epoch_exhausted", int)            generations_per_epoch ran without a
                                          promotion — the lineage ends

    Promotion gate: the expensive confirmation batch only runs when the
    cheap per-generation win rate already clears promotion_threshold; it
    then re-measures the champion on a DISJOINT seed lane and promotes only
    if the confirmation point estimate clears the threshold AND its Wilson
    95% lower bound clears 0.5 ("clearly better" and "not just noise").

    Fully deterministic given seed_base and the parameters: battle dice
    follow the duel_seed schedule; every genetic draw comes from the single
    ga_rng below in a fixed order.
    """
    _min_n = min_confirmation_n_for_threshold(promotion_threshold)
    if confirmation_n < _min_n:
        raise ValueError(
            f"ai_lab evolve_lineage: confirmation_n={confirmation_n} is too "
            f"small for promotion_threshold={promotion_threshold} — even a "
            f"confirmation batch landing EXACTLY at the threshold would "
            f"fail the Wilson 95% lower-bound check (which must exceed "
            f"0.5), making promotion mathematically impossible regardless "
            f"of how good the evolved genome is. Raise confirmation_n to "
            f"at least {_min_n}, or lower promotion_threshold."
        )
    ga_rng = random.Random(seed_base)
    baseline = initial_baseline
    population = [random_genome(ga_rng, center=baseline)
                  for _ in range(population_size)]
    for epoch in range(max_epochs):
        promoted = False
        for generation in range(generations_per_epoch):
            population, stats = run_generation(
                population, baseline, epoch, generation, duels_per_genome,
                ga_rng, elite_count=elite_count, tournament_k=tournament_k,
                margin_weight=margin_weight,
                mutation_sigma_scale=mutation_sigma_scale,
                profile_key=profile_key, squad_size=squad_size,
            )
            yield ("generation", stats)
            if stats.best.win_rate < promotion_threshold:
                continue
            confirmation = evaluate_fitness(
                stats.best_genome, baseline, epoch,
                generation + CONFIRMATION_LANE, confirmation_n,
                margin_weight=margin_weight,
                profile_key=profile_key, squad_size=squad_size,
            )
            record = PromotionRecord(
                epoch=epoch,
                generation=generation,
                champion=stats.best_genome,
                confirmation=confirmation,
                wilson_lower=wilson_lower_bound(confirmation.win_rate,
                                                confirmation.n),
                generations_to_promote=generation + 1,
            )
            yield ("confirmation", record)
            if (confirmation.win_rate >= promotion_threshold
                    and record.wilson_lower > 0.5):
                yield ("promotion", record)
                baseline = record.champion
                population = [random_genome(ga_rng, center=baseline)
                              for _ in range(population_size)]
                promoted = True
                break
        if not promoted:
            yield ("epoch_exhausted", epoch)
            return
