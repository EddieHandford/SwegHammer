"""AI Lab — genetic-algorithm duel sandbox for evolving unit piloting.

This package is an EXPLORATORY sandbox, explicitly outside SwegHammer's
two-stage calibration pipeline (Stage 1: simulator fidelity vs tournament
data; Stage 2: points-equation fitting). Nothing in here touches
data/calibrated_points.json, data/equilibrium_points*.json, or the
tournament mean-absolute-error gate, and none of it models a Warhammer 40k
rule — it is an AI-tuning parameter layer riding the Battle pilot hooks
(_pilot_move / _pilot_charge / the army-level _ai_lab_dual_scales), the
same category as the pre-existing _pilot_focus test hook.

See docs/AI_LAB_PLAN.md for the design document.
"""
