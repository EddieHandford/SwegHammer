"""SwegHammer battle-simulator package.

This package is the staged home for the simulator that historically lived in
the single module ``code/simulator.py``. It is being populated by pure code
motion (see ``docs/SIM_MODULARIZATION_PLAN.md``): each extraction moves a
coherent group of definitions out of ``code/simulator.py`` into a submodule
here, with zero behaviour change, while ``code/simulator.py`` re-imports every
moved name so it remains the public import surface for the rest of the code
base.

Stage A (constants, geometry) lands first because it is the lowest-coupling
material. Later stages move the data classes and then the per-phase engines.
"""
