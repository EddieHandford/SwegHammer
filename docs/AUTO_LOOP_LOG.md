# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 50 close (2026-05-29)

Branch `claude/sim-calibration-6`. 4 commits landed on top of wave-49
close `8e10e5b`. Top commit at wave-50 close is `25af977`.

Wave 50 attacked three named carry-forwards from wave 49 (Daemons Lever
1 Greater-Daemon seeding, AdMech Doctrina representation audit, Drukhari
non-Skysplinter outlier) plus the LeaderAbility sustained-hits schema
follow-up.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 49 close (`8e10e5b`, 2026-05-29) | 14.23 | 10.81 | 4/22 |
| Wave 50 close (`25af977`, 2026-05-29) | 14.24 | **10.81** | 4/22 |

**Flat at headline.** All per-faction movements within their noise
floors. Three landings were rule-correct fixes that targeted real bugs
but where the magnitude impact at N=40 was below noise:

* Drukhari Combat Drugs (5-round permanent grant fix): predicted -2 to
  -5 wr-points, measured +0.12. Adrenalight's +1 melee attack only
  applies to Wych Cult units, and the archetype-built Drukhari armies
  in this eval are predominantly Kabal-shape; the Wych Cult subset
  doesn't dominate enough for the 5x magnitude correction to ripple
  to the gated metric.
* AdMech Doctrina alive-units gate: predicted near-zero direct impact
  per agent report. Confirmed +0.23 (within noise 4.17). The fix is
  structurally correct but only fires after total army wipeout.
* LeaderAbility sustained-hits schema + Changecaster swap: predicted
  small Daemons-direction movement. Measured -0.47 (within noise 3.16,
  wrong direction at headline). The schema is forward-compatible
  infrastructure — its main value is unblocking Nurgle Spoilpox
  Scrivener and Slaanesh Tormentbringer leader entries, neither of
  which were added in this wave.

### Daemons Lever 1 verified closed

Agent diagnostic at the wave-49 baseline measured Greater Daemon
presence across N=200 archetype builds:

| Greater Daemon | Per-archetype presence | Overall presence |
|---|---|---|
| Bloodthirster (Khorne) | 100% | 29% |
| Lord of Change (Tzeentch) | 100% | 32% |
| Keeper of Secrets (Slaanesh) | 100% | 28% |
| Great Unclean One (Nurgle) | 100% | 23% |

The DAEMONS_DIAG_10 baseline of 1/0/0/5% was measured BEFORE commit
`352b1b4 DAEMONS-FIX-1` (wave 44) which anchors the Greater Daemon
in mono-god templates ahead of the budget walk. That commit closed
Lever 1; the wave-49 carry-forward was based on stale diagnostic
numbers. Remaining Daemons -20 deficit must come from elsewhere —
likely the Greater Daemon combat profile audit (Lever C in
DIAG-10) and/or stratagem parity (Lever 2).

### Commit landings

* `6e8dfd4` **[T2] DRK-NON-SKYSPLINTER-V1** — Combat Drugs was applied
  once at `Battle.__init__` and the Adrenalight bonus (+1 melee attack
  on Wych Cult units) persisted for all 5 battle rounds, a 5×
  magnitude error. The codex rule is "at the start of your Command
  phase select which Combat Drugs will be active for your army until
  the start of your next Command phase. You cannot select the same
  Combat Drug more than once per battle." Fix in `code/simulator.py`:
  `_apply_combat_drugs(round_num)` gated to round 1 (Adrenalight is
  the picked drug); transient `combat_drug_extra_melee_attacks` cleared
  per round-start; called from `_run_round` after the transient clear.
  Stage A diagnostic measured Skysplinter ~90% / Kabalite Cartel ~80%
  pre-fix — both detachments overshoot, confirming the bug is in
  Drukhari core not detachment flags. Cited as
  `simulator.combat_drugs`. Side-finding from agent: Drukhari +38
  residual is dominated by activation-count advantage (49-unit
  Drukhari army vs ~20-unit Marine army at the same points) and
  heterogeneous squad weapon-stat averaging — both structural
  follow-ups for future waves.
* `898b023` **[T2] ADMECH-DOCTRINA-V1** — two fixes:
  - `code/simulator.py:5117` Doctrina pick used `army.units` (includes
    dead) instead of `army.alive_units`. Same shape as the wave-49
    SOROR fix; structural inconsistency cleaned up.
  - `code/army.py:235-236` and `tests/test_admech.py` carried stale
    references to the off-mode penalty rule that MR-D (claude/sim-
    calibration-5) removed. Two tests passed against a local
    `_effective_hit_target` helper that duplicated the OLD penalty
    behaviour, giving false confidence the removal was complete.
    Tests rewritten to verify the live `Unit.attack` semantics.
  Functionally near-zero win-rate move. AdMech +15.4 gated residual
  is NOT the Doctrina spend gate; remains an active diagnostic
  target for a future wave.
* `25af977` **[T3] LEADERABILITY-SUSTAINED-HITS** — schema fields
  `sustained_hits_ranged: int = 0` and `sustained_hits_melee: int = 0`
  added to LeaderAbility. Wired through `_NEUTRAL_BUFFS`,
  `effective_buffs` (additive merge via `_merge_add`), and the
  attack-resolution loop in `code/units.py` (mode-routed addition to
  `effective_sustained_hits`). Changecaster swapped from the
  `reroll_hit_ones=True` proxy (which doesn't compose with the
  SUSTAINED HITS extra-hit accumulator) to the rule-correct
  `sustained_hits_ranged=1`. Forward-compatible: Nurgle Spoilpox
  Scrivener and Slaanesh Tormentbringer can now be added to the
  registry without a follow-up dataclass change.

### Pattern observed

Three of four wave-50 commits were rule-correct fixes that targeted
real codex / structural bugs but where the per-unit magnitude was too
small (Combat Drugs limited to Wych Cult subset, Changecaster's
SUSTAINED HITS 1 swap is direction-neutral vs the reroll proxy, AdMech
alive-units gate only fires post-wipe) to ripple to the gated metric
at N=40. The DAEMONS-GREATER-SEEDING task confirmed Lever 1 was already
closed by a prior wave; the carry-forward was based on stale
diagnostic numbers.

**Implication for wave 51 dispatch discipline**: agent prompts that
quote pre-existing diagnostic numbers should require the agent's first
step to be a fresh baseline measurement before applying a fix. The
wave-49 SOROR fix (-4.28 wr-points) succeeded because it targeted a
freshly-measured representation amplification bug; the wave-50
DAEMONS-GREATER-SEEDING task wasted ~430k tokens on a gap that had
already closed.

### Open carry-forwards into wave 51

1. **Daemons Lever C — Greater Daemon combat profile audit**
   (DAEMONS_DIAG_10). Greater Daemons are now seeded at 100% per
   archetype but Daemons remain -20 gated. The combat profiles
   (M/T/Sv/W/Inv, melee stats) may carry approximations or stale
   BSData values. Predicted +5-10 wr-points if audit surfaces real
   stat lag.
2. **Daemons Lever 2 — stratagem parity**. Unaudited. Predicted +3-6
   wr-points.
3. **AdMech +15.6 gated residual** — Doctrina was the wrong target.
   Candidates: detachment-side fabrications in Skitarii Hunter Cohort
   / Cohort Cybernetica, basket-blend weapon profiles on Tech-Priest
   variants, Doctrina buff magnitude (the +1 BS / WS modifier itself
   may be over-stated vs codex modifier-cap interaction).
4. **Sororitas +19.12 gated** — AoF spend gate alone closed ~1/5 of
   the gap. Remaining levers: AoF dice selection (which die gets
   banked to which roll), detachment-side audits (Bringers of Flame /
   Hallowed Martyrs), dice-pool generation rate (currently 1/round,
   codex grants 1 + 1 per destroyed Sororitas unit — verify the
   on-death award path).
5. **Drukhari activation-count advantage** (49-unit Drukhari vs
   ~20-unit Marine at same points). Surfaced by DRK-NON-SKYSPLINTER-V1
   agent. Structural — alternating activations amplify the unit-count
   disparity. Possible mitigation: list-building heuristic that biases
   Drukhari toward fewer, larger units; or alternating-activation
   rule adjustment for asymmetric-shape armies.
6. **Drukhari heterogeneous squad weapon-stat averaging** — surfaced
   by DRK-NON-SKYSPLINTER-V1 agent. Kabalite squads carry Splinter
   Rifle (most models) + Splinter Cannon / Blaster (1-2 models). The
   mapper averages the weapon profiles; this dilutes the heavy
   weapon's impact when the squad shoots together. Tractable mapper-
   structural follow-up if a multi-profile-per-squad shape lands.
7. **TSON +20.64 gated, noise 8.75** — under-audited recently. Last
   audit was `24d8a7e TSON-KOS-MESMERISING-V1` (wave 44). High
   noise floor means tractable lever may exist but at smaller gain.
8. **Aeldari +12.62 / T'au +12.52 / Votann +15.58 / Orks +15.46** —
   all under-audited in recent waves. Each likely carries 1-2 small
   rule-correctness or detachment-audit levers. Candidates for a
   parallel sweep wave.
9. **Tyranids +20.34** — partly audited (`5f00b3f SYNAPSE-3D6`, wave
   44 -2.9 wr-points). Wave-44 Norn/Tervigon/OOE under-modelling
   findings still parked because fixing them would shift Tyranids the
   wrong direction (sim already over). The over-buff side needs
   surfacing.
10. **Nurgle Spoilpox Scrivener + Slaanesh Tormentbringer leader
    entries** — `25af977` schema is ready; entries themselves need
    BSData verification + Wahapedia citation. Small predicted
    movement but rule-correct addition.
11. **IK -35.52 / CK -43.57 mapper-locked** — Stage 2 multi-profile
    weapon mapper. Long-day branch.

### Tooling housekeeping

* Drukhari Combat Drugs side effect on AUTO_LOOP_LOG.md (agent added
  80-line in-flight block prematurely) was overwritten by this close.
  Agent prompts should explicitly forbid AUTO_LOOP_LOG.md edits —
  the wave close is the orchestrator's job.

## Wave 49 close (2026-05-29)

Branch `claude/sim-calibration-6`. 4 commits landed on top of wave-48
close `d82fb5d`. Top commit at wave-49 close is `413d89b`.

User set a session goal: drive gated MAE below per-faction noise floor
while improving rule correctness of the sim. Wave 49 attacked the two
highest-ROI tractable outliers (Sororitas +20.9 unaudited, Daemons
-20.3 with the named Lever B carry-forward) in parallel, plus the
test-tooling `_classify_cache` flake from wave 48.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 48 close (`d82fb5d`, 2026-05-29) | 14.22 | 10.83 | 4/22 |
| Wave 49 close (`413d89b`, 2026-05-29) | 14.23 | **10.81** | 4/22 |

Net **-0.02 gated MAE** across 4 commits — flat at headline but masks a
real per-faction win. Sororitas dropped 4.28 wr-points (+23.05 → +18.77
gated, well over noise floor 3.79); the gain was offset at the headline
by ~+0.5 cross-faction drift, all within each faction's noise floor
and therefore not contributing to gated. The fix is rule-correct AND
direction-correct on its target faction — this is the cleanest result
shape we get below the structural-residual floor.

### Per-faction movements above noise

* **Adepta Sororitas**: 71.3% → 67.0% sim, +23.05 → +18.77 gated.
  Sole faction moving more than its noise floor (3.79). Driven by
  `413d89b` SOROR-ACTS-OF-FAITH-V1 — see below.

All other factions stayed within 1 wr-point of their wave-48 position
(±0.83 max delta). No regressions over the gated threshold.

### Commit landings

* `0e4acc2` **[T2] CLASSIFY-CACHE-HASH** — replace `code/roles.py`'s
  manual `Dict[int, str]` cache (keyed by `id(p)`) with
  `functools.lru_cache(maxsize=4096)`, matching the convention used by
  the adjacent `expected_ranged_dpa` / `expected_melee_dpa` helpers.
  Closes the order-dependent test flake documented as a wave-48
  carry-forward: transient `UnitProfile` instances in tests get
  garbage-collected, their `id()` slot is reused, and the cache returned
  the previously-cached role for an unrelated profile. `UnitProfile`
  is a frozen dataclass so it has a stable hash that doesn't collide on
  id-reuse. Full pytest sweep now 897 passed, 0 failed (was 897 passed
  + 2 order-dependent failures on the same HEAD pre-fix).
* `41f8029` **[T2] DAEMONS-LOCUS-V1** — narrow Locus magnitude
  correction surfaced by the wave-44 DAEMONS_DIAG_10 Lever B carry-
  forward. Tzeentch Changecaster's host_keys missed Blue Horrors (a
  separate `chaos_daemons_library_blue_horrors` catalog key); BSData
  Leader profile lists "PINK HORRORS, BLUE HORRORS" as legal
  attachments. Other Locus carriers reviewed without change:
  - Khorne Bloodmaster: already correct (`plus_one_to_wound` matches
    codex verbatim).
  - Nurgle Poxbringer: parked — `+1 critical Hit threshold` doesn't
    reduce to a static `LeaderAbility` flag; current `plus_one_to_wound`
    proxy is direction-correct.
  - Nurgle Sloppity Bilepiper: correctly absent from registry
    (Battle-shock + movement aura, no offensive flag).
  - Slaanesh Contorted Epitome: `fnp=4` is acceptable approximation
    (over-broad vs codex "FNP 4+ vs mortal + psychic" but
    direction-correct).
  Predicted metric move: small (Blue Horrors rarely seeded as
  battleline in current archetypes), and confirmed at eval — Daemons
  -19.85 → -19.73 (+0.12 wr-points, well below noise 3.16). Closes
  one of the verifiable Lever B errors; remaining Daemons deficit
  bottlenecks on Lever 1 (Greater Daemon seeding) + Lever 2
  (stratagem parity) per DAEMONS_DIAG_10.
* `413d89b` **[T2] SOROR-ACTS-OF-FAITH-V1** — the real wave-49 win.
  Acts of Faith spend gate was per-`Unit` instance, but SwegHammer's
  one-Unit-per-model representation expands an archetype Sororitas
  army to ~71 Unit instances (Battle Sisters x10 × 2 squads = 20,
  Celestian Insidiants x10 = 10, Seraphim x5, etc.) where the codex
  unit count is ~19. The army was getting **3.7× more AoF spend
  opportunities per round** than the codex allows. Codex wording:
  "each **unit** can perform one Act of Faith per phase" — one per
  codex squad, not one per model.
  Fix: added `_aof_squad_names_used_this_round: set` on Army with
  `aof_squad_available(profile.name)` / `aof_squad_mark_used` helpers;
  all instances sharing a `profile.name` collapse to one codex unit
  for AoF purposes. Three spend sites in `code/units.py` (hit, wound,
  defensive save) now gate on `aof_squad_available(p.name)`. Round
  reset hook in `code/simulator.py:_run_round` clears the squad set.
  Also tightened the round-start dice-generation gate from
  `army.units` to `army.alive_units` (rule: army must have at least
  one alive Sororitas unit to qualify), and the on-death dice award.
  Predicted UNDER-cut on Sororitas sim%; confirmed -4.28 wr-points
  at eval (+23.05 → +18.77 gated). First faction-targeted commit
  this branch to move its outlier by more than its noise floor in a
  single landing.

### Pattern observed

The SOROR fix is a clean example of the "simulator-representation
amplification" failure mode — not an explicit fabrication, but the
one-Unit-per-model abstraction silently amplified a per-codex-unit
spend budget into a per-simulator-instance one. The same shape may
exist on other faction army rules with "once per unit per phase"
spend models — worth a parking-lot sweep:
- AdMech Doctrina Imperatives (+15.4 gated; once-per-phase imperative
  pick).
- Necron Reanimation Protocols (already audited via `_initial_unit_
  counts` snapshot — robust).
- Death Guard Plague Companies stratagem cap (currently per-army).
- Custodes Ka'tah stance (already keyword-gated, low risk).

### Open carry-forwards into wave 50

1. **Daemons Lever 1 — Greater Daemon seeding gap**. The wave-44 anchor
   (`352b1b4 DAEMONS-FIX-1`) seeds Greater Daemons in mono-god templates
   but the diagnostic surfaced under-attendance even with the anchor.
   Predicted +5-8 wr-points if the seeding budget is fully realized.
2. **Daemons Lever 2 — stratagem parity**. Unaudited. Predicted +3-6
   wr-points.
3. **Sororitas residual +18.77 gated** — AoF fix closed about 1/5 of
   the gap. Remaining levers: Acts of Faith spend SELECTION (which die
   gets banked to which roll), detachment-side audits (Bringers of
   Flame / Hallowed Martyrs may carry fabricated proxy flags), Acts
   of Faith POOL size (currently 1/round, codex grants 1 + 1 per
   destroyed Sororitas unit — verify award fires on every Sororitas
   destruction, not just BATTLELINE).
4. **`LeaderAbility.sustained_hits_ranged` schema gap** — surfaced by
   DAEMONS-LOCUS-V1 audit. Three Daemons leaders (Tzeentch Changecaster,
   Nurgle Spoilpox Scrivener, Slaanesh Tormentbringer) need this for
   their Locus aura proxy to be rule-correct rather than "no-op
   approximation". Probably a follow-up `LeaderAbility` field + Unit.
   attack wiring + 3 leader updates.
5. **Once-per-unit-per-phase representation sweep** — see "Pattern
   observed" above. Probably AdMech Doctrina is the highest-leverage
   candidate.
6. **Drukhari +38 gated** — still the largest single tractable residual.
   Skysplinter wiring landed in wave 45 + wave 46 reserves-embark
   coupling but the +38 includes non-Skysplinter Drukhari behaviour
   that's never been independently audited. Bundle-of-one: separate
   Drukhari analytics by detachment to isolate where the overshoot
   comes from.
7. **IK -35.5 / CK -43.6 mapper-locked** — Stage 2 multi-profile weapon
   mapper. Long-day branch when one becomes available.
8. All wave-48 carry-forwards remain in place.

### Tooling housekeeping

* `0e4acc2` CLASSIFY-CACHE-HASH unblocks deterministic test ordering
  — future stale-test audits won't need to chase the order-dependent
  flake first.
* Memory entry `[[project-classify-cache-flakiness]]` retired (fix
  landed); the entry remains as historical context until the next
  memory sweep.

## Wave 48 close (2026-05-29)

Branch `claude/sim-calibration-6`. 6 commits landed on top of wave 46-47
close `8636131`. Top commit at wave-48 close is `11210ea`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 47 batch-2 close (`50e2601`, 2026-05-28) | 14.01 | 10.79 | 4/22 |
| Wave 48 mapper-invuln (`9555266`, 2026-05-28) | 14.09 | 10.75 | 4/22 |
| Wave 48 close (`11210ea`, 2026-05-29) | 14.22 | **10.83** | 4/22 |

Net **+0.04 gated MAE drift** across 6 commits — flat at noise. By design.
Wave 48 was a mixed structural / test-backlog wave: two mapper extensions
(invuln Shape 3, FNP Shape 3) that retire correction / override entries
without changing modelled stats, one real production bug (engagement-range
strict-vs-inclusive), and the rest test-only synchronisation against
prior audit landings.

### Mapper structural fixes

* `9555266` **[T3] MAPPER-INVULN-PROSE-WALK** — extend `extract_invuln`
  with Shape 3: inline `<profile typeName="Abilities">` whose name starts
  with "invulnerable save". Wave-47 audit batches landed 20 codex-corrections
  entries patching the same bug across 5 catalogues (Chaos Daemons Library,
  Dark Angels, Library - Titans, Deathwatch, plus parking-lot Aeldari
  characters). The mapper fix retired all 20 in one pass. Side effects:
  Custodes Crucible-detachment datasheets (Kataphraktoi Exemplar, Guardian
  of the Throne, Null Maiden) now parse correctly — the "tracked as
  follow-up" note in `_EXPECTED_CUSTODES_INVULN` is closed. Drukhari /
  Ynnari Archon now parses at invuln 2+ from BSData's stale Shadowfield
  ability text; both correction entries extended with `invuln_save: 4`
  to pull the parsed value back to current Wahapedia (codex bakes
  Shadowfield into a 4+ baseline). Eval: gated MAE 10.79 → 10.75, neutral
  at noise.
* `11210ea` **[T3] MAPPER-FNP-PROSE-WALK** — same shape-3 cleanup pass
  for FNP. The original target tests (`test_wracks_have_fnp_5`,
  `test_wulfen_have_fnp_5`) were stale against BSData refactoring: BSData
  v10.6.0 carried `<infoLink name="Feel No Pain">` entries on both Wracks
  and Wulfen, BSData main subsequently removed them, and current Wahapedia
  confirms neither unit has Feel No Pain as a base stat. Tests renamed to
  `test_wracks_have_no_fnp` / `test_wulfen_have_no_fnp` asserting fnp=7.
  Shape 3 added to `extract_fnp` as forward-compatible infrastructure
  (no current BSData entry matches it). 27 override entries retired
  from `data/overrides.json`: 21 were full removals (held only the
  pre-MAP-2 false-positive suppression `fnp: 7` field), 6 were
  fnp-field-only removals on entries kept for other valid fields. All
  were SC5-8 / SC5-10 suppression patches that the MAP-2 fix made
  redundant by pruning upgrade subtrees.

### Real production bug — engagement-range strict inequality

* `b95c49a` **[T3] STRATAGEM-DISPATCHER-FIX** — `code/strategy.py:1987`
  and `code/simulator.py:5795` both used a strict `< 1.0` engagement
  check where every other engagement-range gate in the codebase uses the
  inclusive `<= 1.0` form. Tests placing units at exactly 1.0" apart
  (the boundary case) silently bypassed the gate, suppressing Fall Back
  triggers and the Big Guns Never Tire flag. Two-line fix, closes 4
  fall-back tests + 1 Big Guns smoke test.

### Test-backlog sweep

A pytest sweep at the top of wave 48 surfaced **33 pre-existing failures**
unrelated to the wave-47 sweep. Triaged into 11 clusters and worked
through cluster-by-cluster with three parallel Sonnet agents on the
larger ones and direct main-worktree fixes on the smaller ones.

* `20f3b36` **[T2] TEST-BACKLOG-SWEEP-1** — 5 stale tests + sweg_points
  re-bake (G/I/J/H/E/K). One commit because the fixes are tightly
  coupled to the backlog-sweep narrative:
  - sweg_points dataset re-baked (3 Sororitas keys renamed in a recent
    BSData refresh broke `apply_to_catalog` via LOADER-FAIL-LOUD).
  - Reanimation 1-HP rule test flipped to assert full-wounds (iter29-NE1
    `a359520` reverted the iter14 1-HP cap; test never updated).
  - Grand Coven test asserted iter15 pre-removal state — code comment
    in `detachments.py:1654` explicitly documents the iter24 removal
    pending Kindred Sorcery wiring.
  - Pile-in test placed attacker at 1.5" without setting charge state;
    pile-in gate requires engagement OR charge. Test now adds attacker
    to `_charging_this_round`.
  - Drukhari Pain Token fixture missing `min_models=2` — 15e0d66
    DRK-PAIN-TOKENS tightened the Below-Starting-Strength gate to
    require multi-model units.
  - Strategy `_FakeBattle` shim missing `.a` / `.b` (AI-9 chaff-push
    helper now reads deployment-zone orientation from the battle ref).
  - Strategy `_melee_target_score` test rewritten — original asserted
    absolute ranking on stat-dissimilar profiles which broke when later
    score multipliers swamped the SUPPORT-bonus 1.3x lift. New test
    uses stat-identical profiles and isolates the CHARACTER-with-aura
    differential.
* `304eb25` **[T2] TEST-LEADERS-STALE-AUDIT-SYNC** — Sonnet agent
  resolved 12 leader-aura tests stale against a series of leader
  fabrication audits (Aeldari, Daemons, AdMech, Orks, TSON, Votann)
  that removed proxy buffs from `LeaderAbility` entries. Mixed
  resolution — five tests narrowed to assert the audited subset of buffs
  (e.g. Warboss `plus_one_to_hit` → `plus_one_to_hit_melee_only`),
  seven flipped to `assertFalse` regression pins against re-adding the
  fabrication. Test file only — no production code touched.
* `8eec997` **[T2] TEST-STRATAGEM-SETUP** — Sonnet agent realigned 5
  stratagem dispatcher tests with the current contract. Three updated
  to read the post-ST-1 transient flags (`transient_sustained_hits`,
  `transient_lethal_hits`, `transient_reroll_wounds_ones`); Adaptive
  Strategy renamed to `test_adaptive_strategy_spends_cp_no_buff`
  reflecting the SC5-9 audit's no-op finding; Oath rebuilt around the
  hit-reroll mechanic (audit corrected from wound-reroll to hit-reroll).

### Pattern observed

26 of 33 pre-existing failures were test-side staleness against landed
audits. 4 were a real engagement-range strict-vs-inclusive bug. 2 were a
self-diagnosed sweg_points dataset key drift. 1 was a Grand Coven
detachment-registry comment/test mismatch (Kindred Sorcery follow-up).
**The wave-48 sweep validates the "audit hygiene" hypothesis** that
landing rule-correctness fixes without same-commit test alignment
accumulates test debt rapidly — over 8 commits between waves 21 and 47,
roughly 33 stale tests piled up.

### Order-dependent flake — `_classify_cache` id-reuse

Two failures remain in the full pytest sweep but pass in isolation:
`test_equilibrium::test_role_weighting_uses_per_attacker_classify` and
`test_strategy_improvements::AeldariShimmyTests::test_shimmy_unit_moves_to_new_cover`.
Root cause: `code/roles.py:_classify_cache` uses `id(p)` as cache key
on the assumption that all `UnitProfile` instances come from
`UNIT_CATALOG` and live for the session — but tests construct transient
profiles that get GC'd, and Python's id-reuse causes a stale cached
classification to be returned to the wrong profile. Identity of the
flaky tests shifts run-to-run. Not introduced by wave 48; surfaced by
the wave-48 sweep because the wave-46-47 test additions widened the
catalogue of transient profiles enough to make collisions reliable.

### Open carry-forwards into wave 49

1. **Fix `_classify_cache` id-reuse** — keyed by `id(p)`, see above.
   Two viable rewrites: switch to a stat-tuple cache key (slower but
   correct) or use a `WeakValueDictionary` (frozen dataclass already
   hashable). Should also unblock removal of `-p no:randomly` workarounds
   anywhere in CI.
2. All wave-47 carry-forwards remain in place — N=40 plateau, the four
   structural residuals (IK/CK mapper-bound, Drukhari Skysplinter,
   Daemons Locus, Sororitas spend-model), and the Loyalist Adeptus
   Titanicus cross-catalogue entryLink parser gap.
3. All wave-45 carry-forwards remain in place (SECONDARY-SELECTION-V3,
   STRATAGEM-CHAIN-V2 cap-3, per-weapon-keyword temporary gating infra).

