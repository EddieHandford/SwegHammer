"""Top-level worker module for parallel battle execution.

Kept separate from app.py so worker processes can import this without
triggering Streamlit's top-level module code.
"""
from code.simulator import Battle
from code.army import Army
from code.army_builder import build_army_from_list


def _army_from_spec(spec: dict) -> Army:
    if not spec["keys"]:
        return Army(spec["name"], in_cover=spec["in_cover"])
    return build_army_from_list(spec["name"], spec["keys"], in_cover=spec["in_cover"])


def run_one_battle(spec_a: dict, spec_b: dict, map_) -> Battle:
    return Battle(_army_from_spec(spec_a), _army_from_spec(spec_b), map_=map_).run()
