"""Wave 250 — World Eaters list-realism anchor swap (gated SWEG_WE_REALISM).

The army-builder force-seeds the most expensive template EPIC HERO, which for
the World Eaters "Berzerker Warband" template is Angron. Three sourced May-2026
competitive lists are Khârn-anchored with no Angron. When SWEG_WE_REALISM=1, the
World Eaters template drops Angron before the seed walk so Khârn the Betrayer —
the next-most-expensive EPIC HERO — anchors instead. The OFF path (default) is
byte-identical to the pre-wave-250 build.
"""
import os
import random

import pytest

from code.archetypes import ARCHETYPES, _instantiate_template

WE_TEMPLATE = ARCHETYPES["World Eaters"]["Berzerker Warband"]
ANGRON = "world_eaters_angron"
KHARN = "world_eaters_kh_rn_the_betrayer"


@pytest.fixture(autouse=True)
def _clear_gate():
    """Ensure the gate starts unset and is restored after each test."""
    prior = os.environ.pop("SWEG_WE_REALISM", None)
    try:
        yield
    finally:
        os.environ.pop("SWEG_WE_REALISM", None)
        if prior is not None:
            os.environ["SWEG_WE_REALISM"] = prior


def _seed(faction="World Eaters", seed=7):
    return _instantiate_template(
        dict(WE_TEMPLATE), 2000.0, random.Random(seed), faction
    )


def test_template_contains_both_anchors():
    # Sanity: the template fields both Angron and Khârn so the swap is meaningful.
    assert ANGRON in WE_TEMPLATE
    assert KHARN in WE_TEMPLATE


def test_off_seeds_angron():
    # Default (gate unset): Angron is the priciest EPIC HERO and is anchored.
    seeded = _seed()
    assert ANGRON in seeded


def test_on_drops_angron_anchors_kharn():
    os.environ["SWEG_WE_REALISM"] = "1"
    seeded = _seed()
    assert ANGRON not in seeded, "gate on must drop Angron from the seed"
    assert KHARN in seeded, "Khârn should anchor as the next-priciest epic hero"


def test_gate_only_fires_on_exact_one():
    # "0" (and any non-"1") leaves the build byte-identical to unset.
    base = _seed()
    os.environ["SWEG_WE_REALISM"] = "0"
    assert _seed() == base


def test_gate_is_faction_scoped():
    # Gate on, but a non-World-Eaters faction label must not trigger the filter.
    os.environ["SWEG_WE_REALISM"] = "1"
    seeded = _instantiate_template(
        dict(WE_TEMPLATE), 2000.0, random.Random(7), "Death Guard"
    )
    assert ANGRON in seeded, "the filter must be scoped to World Eaters only"
