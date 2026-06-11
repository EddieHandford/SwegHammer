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

**3. Retributor+Paragon measured — gated 5.85 → 5.75, new standing anchor.** The two ungated
Sororitas commits change the production configuration, so the 5.85 anchor no longer matched
production. The Sororitas-scoped N=80 run (42/462 cells, ~11× cheaper than a full re-anchor)
merged via `paired_delta.py --scoped`: **Adepta Sororitas +1.99 decisive toward target** (141
flips, confidence interval ±1.57; the faction is the third-deepest under-pole at −17.8, so up is
right), Death Guard −0.22 decisive but tiny, every other faction flat. Gated mean absolute error
**5.85 → 5.75 — best yet on the honest scale**. **NEW STANDING ANCHOR
`data/_anchor_sc8a_n80_log.json`**, minted by overwriting the anchor's 3,360 Sororitas cells with
the scoped run's; self-checked by re-pairing old-versus-merged WITHOUT the scoped fill path, which
reproduces the scoped report exactly.

**4. Gate screens (serial).** **`SWEG_CHARGE_BASEEDGE=1` N=40 screen DONE: headline REGRESSION
+0.65 (matched-subset gated 5.95 → 6.59) but the mechanic HITS its physical target.** Five
decisive movers — melee factions down (World Eaters −6.62, Chaos Daemons −6.23, Death Guard
−3.94), shooty factions up (Drukhari +7.31, T'au +6.37); Daemons/Death Guard/Drukhari were
in-band so the headline cost is real. Non-win-rate corroboration via `diag_overlap_audit`
(screenshot matchup, seed 5): live overlap incidents 217 → 100, cross-army (the charge-placement
signature) 49 → 7 — the fix does exactly what it was built to do. Per the fidelity-first
authorization (headline rising is expected and authorised for faithful mechanics; this fixes the
user-flagged collision bug), the gate is NOT discarded on the screen verdict: the adoption call
moves to an N=80 confirm of the actual adoption configuration (both collision gates together)
after the remaining screens.

**`SWEG_DEPLOY_COLLISION=1` N=40 screen DONE: RIGHT-DIRECTION WIN — matched-subset gated
5.95 → 5.79 (−0.15), both decisive movers deep-pole factions moving toward target: Astra
Militarum +8.25 (second-deepest under-pole) and Imperial Knights −5.75 (over-pole).** This is
the avenue-2 physical-board-control prediction landing exactly as forecast — deployment spacing
spreads body armies honestly and stops Knight stacking. Flip counts ~250-300 per faction
(deployment touches every game) so most other movers stay inside wide confidence intervals at
N=40.

**5. Bringers of Flame [ASSAULT] leg ADOPTED AS DEFAULT — gated 5.08, best ever (`e5d523d`).**
The Sororitas-scoped N=80 paired A/B measured **Adepta Sororitas +16.19 decisive toward target**
(364 flips, confidence interval ±2.60): sim 35.0 → 51.2 versus a real target of ~52.8, moving the
faction from third-deepest under-pole to inside the noise band. Headline gated mean absolute
error **5.75 → 5.08**. Scoped self-check held (flips only in Sororitas-involving cells); the
other factions' small decisive DOWNs are their Sororitas matchups. The rule is the verbatim
cited Fervent Purgation grant, and the detachment picker only rolls Bringers of Flame in half
of Sororitas games — a real rule firing where it really applies, not a knob. Default flipped
ON (`SWEG_BOF_ASSAULT=0` = legacy path; gate-off tests opt out explicitly, the Acts-of-Faith
adoption pattern). Full suite 1536 green, citation audit clean, demonstration battle exit 0.
**NEW STANDING ANCHOR `data/_anchor_sc8b_n80_log.json` (gated 5.08)**, minted by merging the
scoped cells; self-check reproduces the scoped report exactly.

**6. Combined-collision N=80 confirm IN FLIGHT** (`SWEG_CHARGE_BASEEDGE=1 SWEG_DEPLOY_COLLISION=1`
versus the 5.08 anchor) — the adoption-configuration measurement for the collision pair: the
deploy half screened as a right-direction win, the charge half as a faithful-but-headline-costly
fix; the pair decision is made on this confirm. Held builds (Strands one-substitution, Yncarne
on-kill heal, Aeldari archetype reshape, Chaos Space Marines reshape) land after the collision
decision, then the Aeldari bundle measures Aeldari-scoped.

**7. Held builds pre-reviewed while the confirm runs (orchestrator pass over the four delivered
worktrees — all agents had completed with clean trees).** (a) **Strands of Fate charge fix
(`04c10f0`): review found the budget gate alone splits the squad** — the substituted roll stayed
local to the model that spent the Fate die, so squad-mates re-read the natural pair from the
per-squad cache and failed the very roll the rule had just flipped. The gate and the write-back
are complements, not alternatives (the build agent's commit message had framed them as
alternatives). Fixup committed in the same worktree (`2cb9583`, FATE-CHARGE-V2): on a successful
substitution the substituted pair is written back to `Battle._squad_charge_roll[sid]`; new test
asserts one die spent, the cache holds the substituted pair, and all five squad-mates end in
engagement — verified discriminating (fails on gate-only code). File suite 19 green from the
worktree. (b) **Yncarne on-kill D3 heal (`59348ee`): passes review** — killer-scoped trigger
verified at all four kill sites (the Counter-Offensive site's `retaliator`/`loser_army` naming
checked against the adjacent judgement-token hook), roll-then-cap matches "regains up to D3",
citation rewritten faithful. (c) **Chaos Space Marines reshape (`0fdb1eb`): passes review** —
two independent sources, seed-walk documented, the Daemons mono-god precedent applied; frame
change, fresh anchor on land. (d) **Movement-event emission sweep (`3774528`): passes review** —
emission-only, fingerprint-identical at its base, replay drift 0/0/0 on seeds 3-5; its charge
hunk will conflict with the `1b04961` rewrite at cherry-pick (re-apply inside both placement
branches). **Aeldari archetype reshape build DISPATCHED** (worktree agent off `a9c0fee`): the
spec's pre-build check is done — "Battle Host" is selected at runtime by `rng.choice`, so the
key rename is runtime-safe; literal references confined to `tests/test_aeldari_warhost_template.py`
and the `tests/test_archetypes.py` anchor test, both in the agent's scope.

**IN FLIGHT:** combined-collision N=80 confirm (healthy, ~12 workers since 18:08); Aeldari
archetype reshape build agent; movement-event emission sweep cherry-pick pending harvest.
Modularization Stage B complete on its own branch — awaiting the user's go to push and open
its pull request.

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
