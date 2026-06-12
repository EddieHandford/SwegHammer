# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 242 (2026-06-12, CLOSED) — charge-path legality (the 10e "Charge Move" non-target rule) built, measured at both evaluation sizes, and ADOPTED AS DEFAULT: headline wash (+0.14) with T'au Empire and Imperial Knights both decisively toward target. Astra Militarum root cause found (orders never reach the army); wave-243 build dispatched.

**1. The diagnosis (systemic before per-faction, per the wave-241 ranking).** The charge-target
picker had NO path legality: chargers reached gunlines straight through screening bodies, violating
the verbatim core rule — "Without moving within Engagement Range of any enemy units that were not
a target of the charge" — already flagged in `docs/CORE_RULES_AUDIT.md`. Screens in the simulator
therefore protected nothing, which over-rated melee armies against shooting armies whose real-table
defence is the screen.

**2. The build (`884a8b8`, worktree agent, cherry-picked).** Gated `SWEG_CHARGE_PATH` in
`pick_charge_target` (`code/strategy.py`): (part a) non-FLY chargers are excluded from any candidate
whose straight-line move would pass within Engagement Range (one-inch base-edge gap) of a non-target
enemy — new pure-geometry point-to-segment helper `_charge_path_screen_gap` in
`code/sim/geometry.py`; (part b) ALL chargers including FLY are excluded when the approximate charge
end spot itself sits within Engagement Range of a non-target. Excluded candidates simply fall out of
the scorer, so redirection onto the screen EMERGES from the existing kill-value ranking — no new
behaviour knob. Cited `simulator.charge_path_non_target` (verbatim Wahapedia Charge Move text), zero
extra random draws, gate-off byte-identical, six new tests.

**3. Measurement (paired, like-to-like).** Screen at forty battles per pairing versus the 6.38
anchor (18,480 matched games): headline +0.09 wash; decisive movers T'au Empire +4.75 toward target,
Imperial Knights −7.20 toward target, Death Guard −4.76 toward target; the predicted Astra Militarum
recovery did NOT appear (+0.24 flat — prediction falsified, see item 5). Confirm at eighty battles
per pairing (36,960 matched games): headline gated 6.38 → 6.52 (+0.14, wash); T'au Empire +3.85
toward target (enters the noise band), Imperial Knights −5.46 toward target (gated 10.61 → 5.15);
Genestealer Cults +3.63 AWAY (new carried residual — horde screens now also protect the Cults' own
melee); the Death Guard screen improvement did not confirm (−1.59, flat). Verdict: a verbatim core
rule, cited and tested, at essentially zero headline cost with two decisive structural wins —
fidelity-first doctrine says adopt. **Default flipped ON** (`SWEG_CHARGE_PATH=0` restores the legacy
no-path-check behaviour). New standing anchor `data/_anchor_sc9b_n80_log.json` — gated 6.52, raw
9.88, 4/22 in band — promoted at zero evaluation cost (configuration equality with the confirm run).

**4. Test fallout from the default flip (the wave-241 lesson applied — scenarios spread, gate never
pinned off).** Two incidental failures, both collinear stagings where the new rule legitimately
changes the outcome: `test_charge_baseedge.py::test_charger_does_not_overlap_other_models` (an enemy
bystander parked on the straight approach now makes that charge illegal and the picker redirects
onto the screen — the bystander is now FRIENDLY, which forces the same angular collision search
without the illegality) and `test_charge_picker_wont_crack.py` (brick dead on the squishy's approach
line). Digging into the latter exposed a PRE-EXISTING vacuous-assertion bug: the picker-preference
tests compared `target.uid`, but `uid` is only assigned by `Battle` at start, so every comparison
was `"" == ""` — true whatever the picker chose. With real `assertIs` assertions the
"picks the most damageable among uncrackables" claim turned out NEVER true (the scorer ranks
uncrackables by full charge score — ranged-output value and counter-threat included — under which
the heavier brick's bigger guns win, gate on or off). Tests now pin what the code actually
promises: genuine squishy-preference on legal-path stagings, and no-veto (someone is still picked
when every candidate is uncrackable).

**5. Astra Militarum root cause (the −18.99 under-shooter, biggest single residual).** The screen
falsified the melee-bypass hypothesis, so a read-only diagnostic agent traced the Orders pipeline:
`code/orders.py` proxies the codex REGIMENT / SQUADRON order-target keywords as
BATTLELINE+INFANTRY / BATTLELINE+VEHICLE — but BSData v10.6.0 grants BATTLELINE to almost nothing
(ZERO Astra Militarum vehicles; only Cadian Shock Troops, Catachan Jungle Fighters, and Death Korps
of Krieg infantry). Orchestrator-verified against the BSData cache: the real categoryLinks carry
"Regiment" ×33 and "Squadron" ×45. Net effect today: tank commanders issue zero orders every game,
Lord Solar's SQUADRON and TITANIC legs never fire, and Kasrkin / Tempestus Scions / Heavy Weapons
Squads are never order-eligible — the faction's signature army rule is structurally absent. Hazard
caught at review: do NOT stuff BATTLELINE into vehicles (archetype list generation keys squad caps
on BATTLELINE — that would be a silent frame change). Faithful shape: REGIMENT / SQUADRON as
first-class tracked keywords in the mapper plus an orders-plumbing switch. Wave-243 build agent
dispatched (worktree, Sonnet). Bundling candidate for the same measurement: the Wyvern's primary
weapon is misidentified (the anti-tank-picker-bias class — Heavy bolter chosen over the real Quad
Stormshard Mortar with BLAST and INDIRECT FIRE).

**6. Fork resolution without escalation.** The fight-alternation re-test (melee over-pole cluster:
Adeptus Custodes 19.96, World Eaters 16.27, Death Guard 12.43, Emperor's Children 11.95, Chaos
Daemons 10.03) is already authorised by watchdog queue item 9 — the old "genuinely refuted" tag
predates roughly sixty waves of frame change and the wave-166/168 reject was a doubling confound.
Ranked after the wave-243 work.

## Wave 241 (2026-06-11, CLOSED) — CRITICAL FIX landed: the wave-240 charge placement shipped without its measurement half, structurally disabling melee under the adopted default; the gate-aware Engagement Range measure now lands everywhere; honest re-anchor gated 6.38 (the +1.30 versus the last honest frame is the cost of melee actually working).

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

**5. Honest re-anchor landed: gated 6.38 (raw 9.88, 4/22 in band) — NEW STANDING ANCHOR
`data/_anchor_sc9a_n80_log.json`.** The paired decomposition against the last honest frame
(`_anchor_sc8b_n80_log.json`, gated 5.08 — pre-collision-adoption, melee intact) attributes the
+1.30 cleanly: **every melee faction rises decisively now that charges actually connect** (Chaos
Space Marines +17.31, Chaos Daemons +13.00, Death Guard +12.58, World Eaters +12.47, Grey Knights
+9.70, Adeptus Custodes +8.63, Emperor's Children +7.25, Thousand Sons +6.69) while shooty
factions give back wins they were taking from melee armies whose melee never fired (T'au −14.80,
Aeldari −9.46, Leagues of Votann −5.65, Adeptus Mechanicus −4.74, Adeptus Astartes −3.56). The
wave-240/241 fidelity work hit its targets on the honest frame: **Chaos Space Marines gated
21.28 → 0.00 in band** (the archetype reshape), **Adepta Sororitas in band** (Bringers of Flame
survives honestly), **Aeldari gated 2.39** (reshape + Strands + Yncarne, as diagnosed). The
broken-melee frame's apparent Astra Militarum windfall was bug-flattered — the faction is back to
**17.48 gated under** (sim 24.6 versus real 45.3), and the exposed melee over-poles are the new
lever surface: **Adeptus Custodes 21.56, World Eaters 15.07, Death Guard 14.02, Imperial Knights
10.61, Necrons 9.56, Emperor's Children 9.50, Chaos Daemons 9.10**. Headline rising for a faithful
mechanic is expected and authorised (fidelity-first); the simulator is more correct at 6.38 than
it was at 5.08.

**Checkpoint shipped:** pull request 73 opened on the user's explicit go (waves 240-241,
rolling-branch checkpoint pattern, size caveat and the 5.13 invalidation stated in the
description); continuation branch `claude/sim-calibration-9` rolled off the checkpoint head
`d66a251` per the merge-wait-must-not-bottleneck directive — wave 242 lands there.

**NEXT (wave 242) on the new anchor:** (1) Adeptus Custodes 21.56 over — the elite board-control
residual, now amplified by working melee; (2) Astra Militarum 17.48 under — the banked structural
displacement diagnosis, no longer masked; (3) the melee over-pole cluster (World Eaters 15.07,
Death Guard 14.02, Chaos Daemons 9.10) — first question is whether base-edge placement plus
working melee now over-rates charge reach or fight output systemically (one mechanic, many
factions) before any per-faction work.
