"""Seeded genome-vs-genome duels — the fitness-evaluation primitive.

A duel is one Battle between two 5-model Intercessor Squads (by default),
each side piloted by a DuelGenome via code/ai_lab/pilot.attach. Seeding
follows the project's paired common-random-number discipline
(docs/EVAL_PROTOCOL.md): the seed derives from WHEN the duel happens
(epoch, generation, duel index), never from WHICH genomes fight — so every
genome in a generation is measured against the exact same dice.
"""

from __future__ import annotations

import random
from typing import Optional

from ..army import Army
from ..army_builder import build_homogeneous_army
from ..simulator import Battle, BattleResult
from ..units import UNIT_CATALOG
from .genome import DuelGenome
from .pilot import attach, _guard_squadact

DEFAULT_PROFILE_KEY = "space_marines_intercessor_squad"
DEFAULT_SQUAD_SIZE = 5


def build_duel_army(name: str,
                    profile_key: str = DEFAULT_PROFILE_KEY,
                    squad_size: int = DEFAULT_SQUAD_SIZE) -> Army:
    """One squad of exactly `squad_size` models.

    build_homogeneous_army defaults squad_size to profile.max_models (10 for
    Intercessors), so both the size AND a budget of exactly one squad's cost
    are passed explicitly. Using the same points_cost value for budget and
    squad keeps the arithmetic self-consistent regardless of the known
    points-cost currency issue flagged in PROJECT.tex.
    """
    profile = UNIT_CATALOG[profile_key]   # KeyError = fail loud on a typo
    return build_homogeneous_army(
        name, profile,
        points_budget=profile.points_cost * squad_size,
        squad_size=squad_size,
    )


def duel_seed(epoch: int, generation: int, duel_index: int) -> int:
    """Stable integer seed from WHEN the duel happens (never from genomes).

    Plain integer arithmetic in the style of evaluate_vs_meta.py's
    pair_seed — deliberately not Python's hash(), which is salted per
    process unless PYTHONHASHSEED is pinned.
    """
    return (epoch * 100_000 + generation) * 10_000 + duel_index


def run_duel(genome_a: DuelGenome, genome_b: DuelGenome, seed: int,
             profile_key: str = DEFAULT_PROFILE_KEY,
             squad_size: int = DEFAULT_SQUAD_SIZE,
             subscribers: Optional[list] = None,
             squad_move_as_unit: bool = True) -> BattleResult:
    """One seeded duel: genome_a pilots army "A", genome_b pilots army "B".

    Seeds the GLOBAL random module immediately before army construction,
    matching the discipline of every calibration entry point (the Battle
    engine reads the global RNG directly).

    squad_move_as_unit (default True): both sides' squads pick one shared
    walk target per round instead of the calibration simulator's per-model
    walks — see code/ai_lab/pilot.attach. Symmetric by construction, so
    fitness comparisons stay fair; pass False only for hook-inertness
    proofs.
    """
    _guard_squadact()
    random.seed(seed)
    army_a = build_duel_army("A", profile_key, squad_size)
    army_b = build_duel_army("B", profile_key, squad_size)
    battle = Battle(army_a, army_b, subscribers=subscribers)
    attach(battle, genome_a, genome_b,
           squad_move_as_unit=squad_move_as_unit)
    return battle.run()
