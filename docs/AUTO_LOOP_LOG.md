# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 241 (2026-06-11) — CRITICAL FIX: the wave-240 charge placement shipped without its measurement half, structurally disabling melee under the adopted default; the gate-aware Engagement Range measure now lands everywhere, and the 5.13 anchor is declared INVALID pending a fresh re-anchor.

**1. The bug (caught by a new one-question diagnostic, not by the metric).** `scripts/diag_fightgate_check.py`
(now registered in the analysis toolbox) asks: does a successful charge ever produce a melee swing
under the current gates? Under the adopted `SWEG_CHARGE_BASEEDGE` default the answer was NO —
**18 successful charges, 0 fight activations, 0.0 melee damage** (seed-7 fixed bundle). Root cause:
wave 240 shipped only the PLACEMENT half of the base-edge rule. The charger now ends its move one
inch from the target's base EDGE — about 2.26 inches centre-to-centre for two 32-millimetre bases —
but every Engagement Range check in the simulator still measured CENTRE distance against the
one-inch threshold. Fight eligibility, the shooting melee-lock, the Fall Back crossing test, and
the charge-roll candidate filter all judged the charger "not engaged" at its own legal charge-end
spot. Melee never resolved in any game under the production default.

**2. The fix: the measurement half of the same rule.** New gate-aware primitive
`_er_gap(pos_a, profile_a, pos_b, profile_b)` in `code/sim/geometry.py` — gate ON it returns the
base-edge gap (centre distance minus both base radii, minus a one-nanometre epsilon so the exact
one-inch placement spot counts as engaged); gate OFF it returns the plain centre distance, keeping
the legacy path byte-identical. Twelve simulator sites and five strategy sites converted together
(fight eligibility, the shooting melee-lock, Fall Back, overwatch eligibility, the
`pick_charge_target` filter, the m4 melee-lock, the displace-swarm rails) so no check can diverge
from another. The charge-roll requirement is now the REAL move the 2D6 must cover —
`max(0, gap − 1")` — not the centre distance, matching the 10e charge rule's "ends within
Engagement Range" wording. Cited `simulator.engagement_range_base_edge` (placement and measurement
are two halves of one rule under one gate) and registered in the `scripts/audit_rules.py`
required-keys list; audit green, 343/343.

**3. Validation.** The diagnostic now reads **gate ON: 18 charges / 20 fight activations / 10.0
melee damage** (gate OFF: 19 / 16 / 7.0 — legacy behaviour intact). New
`EngagementMeasurementTests` class (eight tests) in `tests/test_charge_baseedge.py` covers the
pure math both gate ways, fight resolution at the gated charge-end spot, the shooting melee-lock
at base contact, the charge requirement as real-move-not-centre-distance (forced 2D6 against an
eleven-inch Knight), and a full-battle mirror of the diagnostic scenario. Fourteen full-suite
failures triaged — every one a centre-distance-era TEST SCENARIO artifact (stand-ins without
profiles in the m4 tests; units placed at 2.0 inches centre, which used to mean "near but not
engaged" and now means "already engaged", in the displace-swarm, Apoplectic Frenzy, and Relentless
Onslaught scenarios) — fixed by spreading the scenarios past the base-edge threshold with
explanatory comments, NOT by pinning the gate off, so the production default stays the tested path.

**4. Consequence: the wave-240 adoption measurement is INVALID.** The combined-collision N=80
confirm (gated 5.13, 8/22 in band) and the standing anchor `data/_anchor_sc8c_n80_log.json` were
measured on a simulator whose melee never fired under the ON arm. The melee-faction movement in
that confirm (World Eaters, Chaos Daemons, Death Guard down; shooty factions up) is the bug's
signature, not the mechanic's. The ADOPTION itself stands — the placement rule is faithful and the
measurement now matches it — but the headline and residual surface must be re-measured: **fresh
full N=80 re-anchor queued on the fixed tree** (`data/wf_w241_fightgate_n80.json`). The held-build
harvest already landed on this branch before the fix (Strands charge write-back, Yncarne on-kill
heal, the Chaos Space Marines and Aeldari archetype reshapes, the movement-event sweep — commits
`97255b9` through `e82951a`), so the one re-anchor covers the harvest and the fight fix together;
the two reshapes are frame changes that required a fresh anchor regardless.

## Wave 240 (2026-06-11, in progress) — first workflow-orchestrated agenda wave: five builds landed with adversarial per-commit review on `claude/sim-calibration-8`; checkpoint pull request 72 merged by Ed and folded; review fixes applied; measurement frames queued. **[Wave-241 correction: the collision-pair confirm and the 5.13 anchor below were measured on broken melee — see the wave-241 block above.]**

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
and the `tests/test_archetypes.py` anchor test, both in the agent's scope. **DELIVERED
(`a7c98fc`):** "Battle Host" → "Warhost" with a Phoenix Lord trio template (Fuegan, Jain Zar,
Lhykhis anchors plus Aspect/transport core), both test files rewritten, 1535 green in its
worktree, demonstration battle exit 0 — queued for the harvest.

**8. COLLISION PAIR ADOPTED AS DEFAULT — both gates flipped ON.** The combined
`SWEG_CHARGE_BASEEDGE=1 SWEG_DEPLOY_COLLISION=1` N=80 confirm versus the 5.08 anchor came back
**metric-neutral: gated mean absolute error 5.08 → 5.13 (+0.04)** with twelve decisive movers
that largely cancel, and the **in-band count rises 5/22 → 8/22** (World Eaters, Orks, and
Emperor's Children enter the noise band). The deepest structural under-pole moves hard toward
target: Astra Militarum gated 14.8 → 3.89 (+11.31 — the banked displacement diagnosis paying
out through deployment spacing), Adeptus Custodes 13.0 → 8.63 (−4.30 toward). The cost
concentrates on existing over-poles (Necrons 14.09, Adeptus Mechanicus 17.69, T'au 8.73) and
Chaos Space Marines deepens to 21.28 (its archetype reshape is already built and queued).
Physical corroboration on the exact adoption configuration (`diag_overlap_audit`, seed 5):
live overlap incidents **217 → 53**, cross-army **49 → 2** — the user-flagged stacking bug is
substantially closed; the residual same-army overlaps are pile-in/consolidate placement sites
(a future lever). Faithful physical mechanic, headline-neutral, band-count up — fidelity-first
adopts. Defaults flipped in `code/simulator.py` (both gates `"1"` unset; `=0` restores the
legacy paths), the `simulator.charge_end_base_to_base` citation records the adoption
measurement (the deployment relaxation intentionally carries no citation — physical-
representation aid, documented in its docstring), and both gate test files moved to the
explicit-opt-out pattern (the Bringers-of-Flame/Acts-of-Faith precedent). **NEW STANDING
ANCHOR `data/_anchor_sc8c_n80_log.json` (gated 5.13, raw 8.03, 8/22 in band)** — the ON-arm
log promoted directly at zero evaluation cost (config equality after the flip).

**IN FLIGHT:** held-build harvest next (cherry-pick order: Strands `04c10f0`+`2cb9583`, Yncarne
`59348ee`, Chaos Space Marines reshape `0fdb1eb`, Aeldari reshape `a7c98fc`, movement-event sweep
`3774528` with the known charge-hunk conflict); the two reshapes are frame changes, so one fresh
full N=80 re-anchor after the batch covers all five builds. Modularization Stage B complete on
its own branch — awaiting the user's go to push and open its pull request.

*Wave 239 and older archived to `AUTO_LOOP_LOG_archive.md`.*
