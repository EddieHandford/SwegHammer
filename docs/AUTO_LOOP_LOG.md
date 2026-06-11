# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 240 (2026-06-11, in progress) — first workflow-orchestrated agenda wave: five builds landed with adversarial per-commit review on `claude/sim-calibration-8`; checkpoint pull request 72 merged by Ed and folded; review fixes applied; measurement frames queued.

**0. Branch transition + checkpoint shipped.** Continuation branch `claude/sim-calibration-8` rolled
off the `claude/sim-calibration-7` checkpoint head per the user's merge-wait-must-not-bottleneck
directive (now standing policy in memory). Checkpoint pull request 72 opened on the user's explicit
go (size agreed oversized) — Ed merged it almost immediately; `origin/main` folded back content-
identical (`71b6424`), the 5.85 anchor survives the fold.

**1. Workflow execution (user-requested).** Six agenda items dispatched through the Workflow tool as
`sweg-wave-240-agenda` — per-item worktree build agents with structured output plus an adversarial
per-commit review stage (scope / gate-off byte-identity / determinism / citation / acronym / test-
substance checks). Five builds succeeded and were cherry-picked clean: **charge-end base-edge
placement** `1b04961` (`SWEG_CHARGE_BASEEDGE`, default-OFF — charge ends within one inch of the
target's base EDGE at a collision-legal spot, deterministic angular search, legacy fallback when
surrounded); **deployment collision relaxation** `c06afb4` (`SWEG_DEPLOY_COLLISION`, default-OFF —
deterministic push-apart pass after `_deploy_line`, zero extra random draws); **Bringers of Flame
[ASSAULT] leg** `74a65ed` (`SWEG_BOF_ASSAULT`, default-OFF — army-wide ASSAULT via the new
`army_wide_assault` detachment field); **Retributor Storm of Retribution** `0f327ab` (ungated
always-on, re-roll ones to hit and wound on ranged); **Paragon Warsuits Righteous Paragons**
`d1b5eb2` (ungated always-on, plus one to hit and wound versus MONSTER/VEHICLE). The sixth item
(Aeldari issue #44 diagnostic) died on context overflow — the agent Read the N=80 anchor log
wholesale; re-dispatched standalone with an explicit parse-with-scripts-never-Read-large-logs
briefing.

**2. Review findings fixed** (`8ca2f8a`): the deployment-collision test file never exercised the
push-apart loop (default spacing produces zero overlaps for every test army; the one comparative
assertion was guarded by a condition that was never true) — new RelaxationExerciseTests force real
overlaps synthetically and assert resolution, bounds, zone clamps, and determinism; the Bringers of
Flame gate-on tests asserted a tautology (less-than-or-equal on defender health with a profile that
misses under the fixed seed) — now a guaranteed-lethal profile and a strict health-drop assertion;
Retributor citation scope corrected to keyword-gated and the loader reads the field directly. Full
suite 1536 green, demonstration battle exit 0, pushed.

**3. Measurement frames (queued, serial).** The two ungated Sororitas commits change the production
configuration, so the 5.85 anchor no longer matches production — a Sororitas-scoped N=80 run is IN
FLIGHT (42/462 cells; merge into the anchor via `paired_delta.py --scoped` per the matchup-scoping
method) to measure the Retributor+Paragon delta and mint the new standing anchor. Then, serially:
`SWEG_CHARGE_BASEEDGE=1` full-matrix paired A/B, `SWEG_DEPLOY_COLLISION=1` full-matrix paired A/B,
`SWEG_BOF_ASSAULT=1` Sororitas-scoped paired A/B.

**IN FLIGHT:** Sororitas-scoped N=80 re-anchor run; Aeldari over-pole diagnostic agent (re-dispatch);
movement-event emission sweep agent (briefed against `1fb141e` — its commit will need a cherry-pick
across the `1b04961` charge rewrite); Chaos Space Marines archetype reshape build; modularization
Stage B agent.

## Wave 239 (2026-06-11, CLOSED) — Acts of Faith per-phase adopted as default + Stage A folded with on-branch fingerprint proof + anchor promoted at zero evaluation cost.

**1. Displacement Stage 2 verdict recorded** (`b0b36c6`): wash missing its target, parked default-off
— full detail in the wave-238 block below and the decision ledger.

**2. Acts of Faith per-phase adopted as production default** (`7834b75`). The N=80 paired A/B versus
the 5.83 anchor measured metric-neutral: headline +0.03, Adepta Sororitas −0.62 inside the ±0.90
confidence interval (31 flips), every other faction byte-flat. The expected +2-4 uplift did not
materialize — but the per-phase grant is the verbatim codex rule, the conservative cap's historical
justification (the +14.39 over-performance) was attributed to the since-fixed invulnerable-save
mapper bug, and the fidelity-first precedent (conditional invulnerable saves, kept default-on as
metric-neutral fidelity) applies directly. Legacy per-round path kept behind `=0`; gate-off tests
opt out explicitly.

**3. Modularization Stage A folded with an on-branch behaviour proof** (merge commit, procedure §H).
Ed merged pull request 71; because the calibration branch has diverged ~2,400 lines from main, the
main-side fingerprint proof does not automatically transfer — so the motion-proof harness was run on
THIS branch's tree immediately before and after the merge: fingerprint identical both sides
(`45df5b56…`). The fold is behaviour-neutral here too; the standing anchor survives. Full suite
1500 green on the merged tree, demonstration battle exit 0.

**4. Standing anchor promoted at zero evaluation cost.** With the default flipped, the production
configuration now equals the Acts-of-Faith ON arm exactly, and the Stage A fold is proven
behaviour-neutral — so the ON-arm log was promoted directly to
**NEW STANDING ANCHOR `data/_anchor_sc7d_n80_log.json` (gated 5.85, raw 8.81, 5/22 in band)**
with no re-run, per the no-redundant-evaluations rule.

**5. GitHub hygiene on the user's direction.** Stage-2-function issues relabelled (`stage-2` +
`blocked`: #45-#49, #51, each with a comment naming its unblock condition) and two milestones
created: "Stage 1 completion" (#44, #52, #61, #63 — definition of done: gated mean absolute error
below the per-faction noise floor) and "Post-convergence (Stage 2 and held work)".

**6. User-directed display work (same wave, display-only).** Three requests from the user's live
replay session, all built and visually verified: (a) the Streamlit army table now shows composition
in the natural reading order ("2 × 10 = 20" — two squads of ten models, twenty models total);
(b) the replay renderer gained a full victory-point display — running score in the title bar and
legend, per-objective holder tint with the holder's army colour and a white outline (user-confirmed
direction), objective markers resized to their physical forty-millimetre footprint (the old
three-and-a-half-inch diamond out-sized its own control ring and read as a giant stacked unit),
a per-frame scoring flash showing the points awarded and both sides' objective control, and an
end-of-round banner showing each army's secondary victory points (the only place secondary points
are observable in the event stream); (c) `event_description` and the title now carry the running
total. All reconstruction is event-stream-pure — legacy logs still scrub.

**7. Collision report from the same session: ROOT CAUSE FOUND.** The user's screenshot showed
overlapping bases and "units leaving objectives". New audit `scripts/diag_overlap_audit.py`
(registered in the toolbox) measured both failure modes on the screenshot matchup: REAL overlap
(80–114 live incidents per game; deploy already 21–36; tanks 2.2–3.0 inches deep; cross-army
charge cases) and REPLAY drift (27–42 units per game up to 9.99 inches between live and
event-reconstructed positions — the "leaving objectives" was the replay drawing stale positions).
One root cause explains both: `_do_charge` (code/simulator.py:11763-11772) places the charger one
inch from the target's CENTER with no collision-legality check and assigns the position without
emitting a movement event. Deployment placement also never consults collision. Fix split per the
telemetry precedent: the silent-position-assignment emission sweep is telemetry-only (UnitActivated
precedent, byte-identical) → dispatched now; charge-end placement legality (one inch from base
EDGE, collision-legal) and deployment spacing are behaviour-changing calibration levers → queued
gated + paired for wave 240.

**IN FLIGHT at last update:** Chaos Space Marines archetype reshape build agent (frame change on
land → fresh anchor); movement-event emission sweep agent. **NEXT:** wave-240 gated collision
levers (charge-end placement legality, deployment spacing); Sororitas F5 Bringers of Flame ASSAULT
leg; Aeldari issue #44 scoped diagnostic; modularization Stage B on its own branch off main.
