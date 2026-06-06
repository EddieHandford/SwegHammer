# Positional re-model — scope + plan (wave 93)

**Date:** 2026-06-01. **Phase:** the user's Q11 ruling (`STAGE1_AUTONOMOUS_GOAL.md` "Current phase
— UPDATED 2026-06-01 (Q11 ruling)"; commit 0541e23). **Status:** plan only, no code — the user
mandated plan-first for this (the high-risk, sharpest-metric-tuning surface), mirroring the
wave-73→74 / wave-82 plan→build pattern.

## 1. Goal and hard rails (from the ruling)

**Goal.** Re-model the real mechanic of how a body army's surviving Objective Control gets onto
and massed on the markers — the one structural axis left after the scoring/secondary track hit its
floor: **Imperial Knights +27 OVER-hold the markers, Chaos Daemons −22 UNDER-hold them** (the
one-Unit-per-model positioning/representation gap, opposite ends, ≈ half the gated mean absolute
error). This is the ONLY faithful path to that axis, and it is HIGH-RISK — every prior AI-positioning
attempt washed or regressed (value-targeting w72, focus fire w79, contest/deny w81;
`project-ai-frozen-under-mae-first`).

**Hard rails (verbatim intent from the ruling):**
- It MUST be a faithful representation / positioning fix — EITHER the AI actually moving body-army
  models onto and massing on objectives (a real tactic), OR a real coherency / range / geometry
  correction to how models contribute Objective Control on a marker. Cited if it implements a rule;
  EVEN-HANDED across all factions.
- It must NOT be a per-faction or per-model-count Objective-Control→primary-victory-point conversion
  knob, a body-army primary boost, or a Knight primary penalty. The test is unchanged: *would it be
  correct if it moved the metric the wrong way?* A conversion factor tuned to lift Daemons / lower
  Knights is metric-tuning — reject it.
- Plan-FIRST (this doc), env-gated A/B, per-matchup before/after on the Imperial Knights and Chaos
  Daemons objective-holding cells. Expect a possible regression/wash; if it washes, REPORT it
  honestly — do not force it or reach for a knob.

## 2. The confirmed diagnosis (waves 84, 90, 93)

The summed-Objective-Control contest is FAITHFUL — wave 84 verified credited `a_oc`/`b_oc` == the raw
per-model objective control within 3" (no counting bug, no under-credit from the one-objective-per-squad
rule at these objective spacings). So the residual is NOT an Objective-Control-math bug. It is that a
body army's huge total Objective Control barely reaches the markers. The wave-93 within-3"-vs-within-6"
drill (Imperial Knights vs Chaos Daemons / Astra Militarum / Tyranids) pins TWO contributing sub-causes:

| Body army | total OC | per-marker OC within 3" (scores) | within 6" (near but spread) |
|---|---:|---:|---:|
| Chaos Daemons | ~111 | 5.8 | 9.4 |
| Astra Militarum | ~95 | 4.5 | 8.4 |
| Tyranids | ~185 | 7.7 | 15.6 |

1. **Geometry / spread (secondary, but the cleaner lever).** The objective control *within 6"* of a
   marker is ~2× the objective control *within 3"* — so roughly HALF of a body army's near-marker
   objective control sits in the 3"–6" band, outside the scoring radius. Units that are *near* a marker
   are spread (one-Unit-per-model placement + coherency) so only their inner models score. In real 10e a
   unit holding an objective clusters its models on the marker, with most within 3". This is a real
   GEOMETRY / placement artifact — the user's explicitly-authorised "coherency / range / geometry
   correction" category.
2. **AI not massing (dominant).** Even the within-6" figure (8–16) is a tiny fraction of the army total
   (95–185) — the bulk of the army is nowhere near a marker (backfield, fighting, spread across the
   board). The AI does not concentrate body-army models on objectives. This is the regress-prone
   AI-positioning class (contest/deny w81 was exactly this and washed).

Crucially, the within-3" body-army objective control (4.5–7.7) is BELOW a big Knight's ~10, so the body
army *loses the contest at the marker it is on*. A geometry fix that recovers the 3"–6" band would
roughly DOUBLE on-marker objective control (toward the within-6" figure), letting body armies out-control
a Knight on contested markers — the faithful, even-handed lever.

## 3. Faithful candidate mechanisms (build sequence)

**Candidate A — the GEOMETRY / clustering correction (lead candidate; least like the washed AI lever).**
A unit that is holding / on an objective should have its models clustered on the marker (real play), so
more of them are within the 3" scoring radius — instead of the sim's artificial spread that leaves half
the near-marker objective control in the 3"–6" band. Build options to evaluate in wave 94:
- (A1) Movement: when a unit's move intent is to take/hold an objective, place its models clustered
  within the control radius of the marker (tighten the on-objective formation), rather than spread.
- (A2) Objective-control counting (representation): a unit whose centroid is within a marker's control
  radius contributes the objective control of its models within its coherency footprint of the marker
  (modelling that a unit "on" the objective holds it with its clustered strength). MUST stay even-handed
  (any multi-model unit; a 1-model Knight is unaffected) and be justified strictly as correcting the
  spread artifact, NOT as a body-army boost — verify the spread is a genuine sim artifact first (it is,
  per the within-6" data), and keep the effective footprint to real coherency (~2"), never an arbitrary
  radius bump.
A1 (real placement) is the more clearly-faithful of the two; A2 is a representation shortcut that needs
careful even-handedness to avoid becoming the forbidden knob. Evaluate A1 first.

**Candidate B — the AI MASSING tactic (the dominant sub-cause, but the regress-prone class).** The move
AI concentrates body-army units onto reachable contested / uncontrolled objectives and KEEPS enough
objective control there to win the contest (the real "flood the objective" tactic), rather than spreading
across the board. This is the same class as contest/deny (w81) which washed because generic massing helps
whoever has the better army. Build only if A does not suffice; expect a likely wash and report honestly.

## 4. Build + measurement protocol (wave 94+)

- Each candidate built env-gated (e.g. `SWEG_CLUSTER` for A, `SWEG_MASS` for B), one at a time.
- Measure: headline gated mean absolute error vs the current 4.15 baseline, AND the per-matchup
  objective-holding drill — body-army on-marker objective control within 3" before/after, the Imperial
  Knights residual, the Chaos Daemons residual, and a watch on the OTHER over-shooters (Drukhari, Votann)
  in case the fix helps whoever has bodies (the frozen-under signature).
- Keep ON only if it is a clear faithful win that moves the IK/Daemons axis without ballooning the
  over-shooters. If it washes or regresses, REPORT it (the axis is then a one-Unit-per-model
  representation limit that resists even a faithful geometry fix) — do NOT force it, do NOT reach for a
  per-faction or conversion knob, do NOT nerf.

## 5. Hard-rails self-check (before any build wave commits)

1. Is it a faithful representation / positioning mechanic (real placement, real coherency/geometry, or a
   real tactic) — verified against a genuine sim artifact, not invented?
2. Is it EVEN-HANDED across all factions (no per-faction branch; a 1-model Knight is affected only
   exactly as the geometry rule affects any 1-model unit)?
3. Is it free of any Objective-Control→primary-victory-point conversion factor, body-army boost, or Knight
   penalty? Would it still be correct if it moved the metric the wrong way?
4. If it washes, am I prepared to REPORT that as the finding rather than reach for a knob?
