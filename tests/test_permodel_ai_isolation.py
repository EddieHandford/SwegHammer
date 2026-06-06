"""Per-model loadouts Stage 5 — AI aggregate-isolation (_score_profile).

Under SWEG_PERMODEL each model-Unit carries only its OWN narrowed weapons (Stage 3).
The OFFENSIVE tactical AI must still value a unit by its SQUAD AGGREGATE, not one model's
gun — otherwise it mis-targets / mis-charges (the measured Daemons-crater confound).
These tests pin that: every model of a squad scores the SAME aggregate, so the AI's
target/charge score is identical across the squad's models; and OFF (no per-model) the
helper is a no-op (squad_profile_ref None -> unit.profile), so behaviour is byte-identical.
"""
import os
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.strategy import _melee_target_score, _score_profile, pick_charge_target


def _first_multimodel_squad(army):
    squads = defaultdict(list)
    for u in army.units:
        if u.squad_id is not None and u.squad_id >= 0:
            squads[u.squad_id].append(u)
    for members in squads.values():
        if len(members) >= 2:
            return members
    return None


def test_off_path_is_noop():
    # Legacy path (SWEG_PERMODEL=0; per-model is now default-ON) -> squad_profile_ref
    # stays None -> _score_profile == unit.profile.
    os.environ["SWEG_PERMODEL"] = "0"
    a = build_faction_random_army("A", "Adeptus Astartes", 2000, rng=random.Random(5), use_archetype=True)
    for u in a.units:
        assert _score_profile(u) is u.profile


def test_permodel_ai_isolation():
    os.environ["SWEG_PERMODEL"] = "1"
    try:
        a = build_faction_random_army("A", "Adeptus Astartes", 2000, rng=random.Random(5), use_archetype=True)
        b = build_faction_random_army("B", "Orks", 2000, rng=random.Random(9), use_archetype=True)
        squad = _first_multimodel_squad(a)
        assert squad is not None, "expected a multi-model per-model squad"
        # every model of the squad resolves to the SAME aggregate profile object
        aggs = {id(_score_profile(u)) for u in squad}
        assert len(aggs) == 1, "models of one squad must share one aggregate"
        # so the offensive target score is identical across the squad's models
        defender = b.units[0]
        scores = {round(_melee_target_score(u, defender), 6) for u in squad}
        assert len(scores) == 1, f"AI not isolated — per-model scores diverge: {scores}"
        # and charge-target choice is identical across the squad's models
        picks = {pick_charge_target(u, b)[0] is not None for u in squad}
        assert len(picks) == 1, "charge-target eligibility diverges across the squad"
    finally:
        os.environ.pop("SWEG_PERMODEL", None)
