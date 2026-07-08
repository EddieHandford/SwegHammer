"""Top-level worker module for parallel battle execution.

Kept separate from app.py so worker processes can import this without
triggering Streamlit's top-level module code.
"""
from code.simulator import Battle
from code.army import Army
from code.army_builder import build_army_from_composition


def _army_from_spec(spec: dict) -> Army:
    # The spec carries composition rows (unit_key, num_squads, models_per_squad)
    # so the worker rebuilds REAL squads (one shared squad_id each), identical to
    # the app's preview/replay build. A flat key list would collapse every squad
    # to one model per unit and silently desync the parallel stats from the
    # single replay shown to the user.
    if not spec["comp"]:
        return Army(spec["name"], in_cover=spec["in_cover"])
    return build_army_from_composition(
        spec["name"], spec["comp"], in_cover=spec["in_cover"]
    )


def run_one_battle(spec_a: dict, spec_b: dict, map_) -> Battle:
    return Battle(_army_from_spec(spec_a), _army_from_spec(spec_b), map_=map_).run()
