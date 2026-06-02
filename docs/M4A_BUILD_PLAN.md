# Anti-Knight stack — component 1 build plan: M4-α squad-cluster positioning (`SWEG_M4`)

**Date:** 2026-06-02 (wave 127). **Status:** plan, build next wave. Authorised by the user's
`M4_REPRESENTATION_PLAN.md` §7 decision (A — the combined anti-Knight package). Plan-first per the user's
"each plan-first + env-gated + own A/B" instruction. **Faithful genuine-positioning (A1), NOT the forbidden
A2 coherency-footprint counting.**

## The confirmed spread mechanism (from the move code)

A codex squad = the Units sharing a `squad_id`; each model is one Unit with its own `position`. Objective
Control is scored per-model within an objective's `control_radius` (3") — `_assign_army_oc`
(`simulator.py` ~6500-area / `_score_objectives`). The wave-93 drill found a body army's near-marker OC is
~2× larger within 6" than within 3" — half its near-marker models sit in the **3"–6" band, outside the
scoring radius**.

Why they strand there: `pick_move_intent` (`strategy.py:1930`) returns `(target_pos, intent)`, and `_do_move`
(`simulator.py:7464`) moves the model toward `target_pos` via `_move_toward`, stopping at it. For an
objective-seeker the intent uses `range_threshold = 3.0` (`simulator.py:7585`) — i.e. the model treats
"within 3" of the marker" as *arrived* and then HOLDs (`dist < 0.5 or intent == "HOLD": return`,
`simulator.py:7571`). A model that arrives at the **edge** of the 3" band (or just outside it, 3–6", because
its move ran out) is "close enough" and never tightens onto the marker. Multiplied across a squad, half the
near-marker bodies sit in the 3–6" ring contributing **zero** OC.

## The mechanic (genuine movement, even-handed)

When `SWEG_M4` is on and a model's intent is objective-seeking (`CAPTURE` / `STEAL`) **and** the model is
within a "contesting" range of the target marker (say ≤ 8") but not yet tightly on it, override its
`target_pos` with a **clustered slot inside the 3" scoring band** (≤ 2.5" from the marker centre), distinct
per squad-member, and let the existing `_do_move` logic close the remaining distance. The model genuinely
*moves* the last few inches into the band — no counting, no credit change.

Slot assignment (deterministic, PYTHONHASHSEED=0-stable):
- Gather the model's squad members (same `squad_id`) whose target marker is this marker; sort by `uid`.
- This model's index `k` → a slot in a tight concentric cluster centred on the marker: `k == 0` → centre;
  `k` in 1..6 → inner ring at radius ~1.4"; `k` ≥ 7 → outer ring at radius ~2.4" (still < 3"). Fixed angular
  spacing per ring. `cluster_step` mirrors the deployment cluster (`simulator.py` ~5900, 1.25" between
  models). All slots are ≤ 2.5" < 3" → every model that reaches its slot scores.
- A **1-model squad (a Knight) → k == 0 → the marker centre**: it already parks there, so M4-α is a no-op for
  it. Even-handed by construction — the benefit accrues to multi-model squads because they have models to
  pack, not via any faction or model-count branch.

Hook point: in `_do_move`, immediately after `pick_move_intent` returns, before the Advance/`_move_toward`
block (`simulator.py:7508`–7570). Add a private `_m4_cluster_target(attacker, target_pos)` that returns the
clustered slot (or the unchanged `target_pos` when the gate is off, the intent isn't objective-seeking, or no
marker is within the contesting range). OFF path: byte-identical (the helper returns `target_pos` unchanged).

## Hard-rails (from `M4_REPRESENTATION_PLAN.md` §6) — self-check

1. Faithful: a real squad clusters its models on the objective it holds; we move them there genuinely. ✓
2. Even-handed: no faction branch, no model-count weighting; a 1-model unit gets the centre slot (unaffected). ✓
3. No OC→VP factor, no body-army boost, no Knight penalty. Wrong-way test: a squad clustering on its objective
   is the more faithful representation even if it moved the metric the wrong way. ✓
4. Env-gated `SWEG_M4`; A/B N=40 (OFF must read 4.41 baseline) then N=80; per-matchup IK / Daemons on-marker
   within-3" OC drill; over-shooter watch (Drukhari/Votann/Custodes) for the frozen-under signature. ✓
5. Expect **M4-α alone to wash** (the §3 / wave-93 prior: clustering helps only units already at a marker; the
   value is in the STACK). If the stack washes, REPORT the floor and STOP — no knob, no A2, no re-fit. ✓

## Build + test checklist (next wave)

- `_m4_cluster_target` helper + the `_do_move` hook, gated `SWEG_M4` (default OFF for the isolation A/B — the
  stack components default OFF until the decisive full-stack run; the user's stack decides the final default).
- Citation `simulator.m4_squad_cluster` (scope `phase-gated`) — a positioning approximation of unit coherency
  on an objective; cite the 10e coherency + Objective Control core rules.
- Tests (`tests/test_m4_cluster.py`): a 5-model squad contesting a marker ends all 5 within 3" of it (ON) vs
  spread (OFF); a 1-model unit targets the centre (no-op); OFF path returns `target_pos` unchanged.
- Audit + full pytest + `run.py --cli`; N=40 A/B OFF==4.41 / ON; report the IK / Daemons on-marker delta.
