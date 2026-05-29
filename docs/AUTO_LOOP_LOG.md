# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 50 in-flight (2026-05-29)

Branch `claude/sim-calibration-6`, top of `8e10e5b`. Task: DRK-NON-SKYSPLINTER-V1 (Stage 1 calibration, Tier 2).

### Stage A diagnostic

Per-detachment sim win rate vs Adeptus Astartes Gladius Strike Force at 1000 pt, N=20 pairs each
(Drukhari Skysplinter Assault archetype template, independent seeds per detachment):

| Detachment | Sim win rate | Real meta target |
|---|---:|---:|
| Skysplinter Assault | ~90% | 49.3% |
| Kabalite Cartel | ~80% | 49.3% |

Both detachments overshoot massively. The 10-point gap between them is Rain of Cruelty (disembark buff
fires on damaged-transport forced-disembark and voluntary-disembark when near objective). Both at ~80-90%
means the fix lever is in Drukhari core, not in Kabalite Cartel detachment flags.

Verification of all five task-listed failure modes:

- (a) Kabalite Cartel flags: NONE — detachment is a clean no-op composition shell. No fabricated flags. ✓
- (b) Power From Pain magnitude: no Lethal Hits or feel no pain 6+ fire. Token accrual is inert. ✓
- (c) Skysplinter carries stratagem-only flags: Skysplinter has NO detachment flags; Rain of Cruelty is wired
  via `simulator._disembark` (name-gated to "Skysplinter Assault"). ✓
- (d) Combat Drugs passive Lethal Hits + feel no pain 6+: already stripped in wave 46. BUT — Adrenalight
  was applied at battle start and persisted for all 5 rounds. Real codex: "At the start of your Command
  phase, select which Combat Drugs will be active for your army until the start of your next Command phase.
  You cannot select the same Combat Drug more than once per battle." Adrenalight can fire ONCE per game,
  not every round. Previous code gave Wych Cult units +1 melee attack for all 5 battle rounds — a 5x
  magnitude error. **Bug found.**
- (e) Skysplinter LANCE and IGNORES COVER magnitude: `transient_lance_this_turn` and
  `transient_ignores_cover_this_turn` are cleared at round-start by `_clear_transient_stratagem_flags`.
  LANCE gate requires `is_charging=True`. Both correctly scoped to the turn of disembark. ✓

### Stage B fix

**Root cause**: `_apply_combat_drugs()` was called once in `Battle.__init__` (pre-game) and set
`combat_drug_extra_melee_attacks = 1` permanently for the entire battle. The Wahapedia rule text
states the drug is active "until the start of your next Command phase" and "cannot select the same
Combat Drug more than once per battle." Adrenalight should fire for ONE battle round only.

**Fix** (`code/simulator.py`):

1. Removed pre-game `self._apply_combat_drugs()` call from `__init__`.
2. Modified `_apply_combat_drugs(round_num)` to accept a round number and return immediately for
   `round_num != 1` (Adrenalight fires Round 1 only; Rounds 2-5 no drug wired).
3. Added clearing of `combat_drug_extra_melee_attacks` (and other drug bonuses) in
   `_clear_transient_stratagem_flags` for Drukhari Wych Cult units. Clearing runs before
   `_apply_combat_drugs` each round, so net effect: drug active for one round only.
4. Added `self._apply_combat_drugs(round_num)` call in `_run_round` after the transient flag clear,
   matching the codex Command-phase timing.
5. Updated `data/rule_citations.json` (simulator.combat_drugs effect description).

**File and line**: `code/simulator.py` — `_clear_transient_stratagem_flags` (adds Wych Cult clearing),
`_apply_combat_drugs` (adds `round_num` gate), `_run_round` (adds per-round call after transient clear).

**Wahapedia citation**: https://wahapedia.ru/wh40k10ed/factions/drukhari/#Combat-Drugs

**Qualitative metric prediction**: Small tightening on Drukhari — Wych Cult (Wyches, Hellions, Reavers)
lose the Adrenalight +1 melee attack bonus for Rounds 2-5 (retaining it for Round 1 only). Wych Cult
represents roughly 9% of the 1000-point archetype army cost, so the impact is bounded. Expect
Drukhari sim win rate to drop 2-5 percentage points in the production N=40 eval (the drugs were contributing
roughly 1-2 extra kills per game across 5 rounds; correcting to 1 round halves that to 0.2-0.4 extra kills).
The remaining +33 gated gap is driven by deeper structural factors (activation-count advantage from cheap
multi-model units, heterogeneous-loadout weapon averaging giving all models the squad's best weapon stats)
that require larger refactors.

### Open carry-forwards from wave 50

1. **Drukhari structural activation count** — 49-unit Drukhari army vs 20-unit Marine army at same points.
   Cheap multi-model squads (Kabalites min_models=10 at 12pt/model) give Drukhari 2.5x more activation
   opportunities per round. Direction-correct fix would be a per-squad activation cap or a shift to
   squad-aggregated unit representation for high-model-count squads. Significant refactor; parking-lot.
2. **Drukhari weapon stats averaging** — BSData mapper averages heterogeneous squad loadouts (Splinter Rifle
   x5 + Blaster x1 + Dark Lance x1 etc.) and applies the squad-average weapon stats to each individual model
   instance. Each Kabalite Warrior fires 2 shots at the squad-averaged damage (2.0 per shot, AP-1), giving
   each model the offensive output of a mixed-weapon squad rather than a basic Splinter Rifle. Direction-correct
   fix: per-weapon-model decomposition in the mapper. Significant refactor; parking-lot.
3. All wave-49 carry-forwards remain in place.

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

## Wave 46-47 close (2026-05-28)

Branch `claude/sim-calibration-6`. 10 commits landed on top of wave-45
close `4b3e18d`. Top commit at wave-47 close is `50e2601`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 45 close (`4b3e18d`, 2026-05-28) | 13.57 | 10.22 | 5/22 |
| Wave 47 batch-1 close (`660a677`, 2026-05-28) | 14.01 | 10.79 | 4/22 |
| Wave 47 batch-2 close (`50e2601`, 2026-05-28) | 14.01 | **10.79** | 4/22 |

Net **+0.57 gated MAE regression** across 10 commits. The regression is
front-loaded in wave 46: the AELDARI-SPLINTER-ANTI-INFANTRY-4 tightening
(`5e1cc0d`) plus the BSData-refresh churn nudged the metric the wrong
way relative to N=40 noise. Wave 47 corrections were rule-correctness-
positive but MAE-neutral — confirming the "easy levers spent" plateau
called out in wave 43-44.

### Wave 46: embark coupling + corrections-layer foundation

* `4f2cf26` **[T1] RESERVES-EMBARK-COUPLING** — pre-embark before reserves
  routing + co-route passengers + bring passengers in with their transport.
  Unblocks the wave-45 Skysplinter Assault wiring (passengers were never
  embarked at deploy time because their transport was routed to reserves
  first). Movement: Drukhari +0.0 at this N (the Skysplinter wiring is
  small-sample-size dependent).
* `5e1cc0d` **[T2] AELDARI-SPLINTER-ANTI-INFANTRY-4** — Drukhari and Ynnari
  Splinter weapons (Rifle / Cannon / Pistol / Carbine) had `ANTI-INFANTRY 3+`
  in BSData; current Wahapedia codex tightened to 4+ in the Sep 2024 errata.
  9 unit entries across the two factions, moved as overrides initially.
* `a5dc6fd` **[T1] CODEX-CORRECTIONS-LAYER-10E** — separate BSData-lag
  corrections from SwegHammer hand-tuning. New file
  `data/codex_corrections_10e.json` layered between BSData base and
  `data/overrides.json`. Moves the 9 Splinter entries out of overrides into
  corrections so a future BSData refresh can retire them cleanly (matching
  the `bsdata_was` snapshot in each entry).

### Wave 47: stale-faction sweep

The BSData snapshot fetched 2026-05-18 left ~10 factions whose `parsed.json`
entries had not been re-checked against current Wahapedia since the May
errata pass. Two batches of 5 parallel Sonnet agents (per
`feedback-tiered-model-selection`) — `[T2]` because the work is per-faction
audit-and-correct, not novel rule code.

**Batch 1 (Imperial Knights, Chaos Knights, Chaos Daemons, Ynnari, Deathwatch):**

* IK, CK, Ynnari — all clean (0 corrections). IK and CK gaps are unmodeled
  Knight rules (Harbingers, ranged-only invuln, Bloodlust, detachment
  effects), not BSData stat lag.
* Ynnari surfaced a parking-lot finding: Aeldari characters (Drukhari Archon,
  Craftworlds Autarch, Yvraine, Visarch, Yncarne) systematically missing
  their 4+ invuln save.
* `edc06b0` **CODEX-STALE-DEATHWATCH** — 1 correction (Watch Master invuln 4+),
  plus surfaced the systematic mapper bug: BSData encodes some invuln saves
  as inline `<profile>` text on the selectionEntry rather than as
  `<infoLink>`, so `mapper.extract_invuln()` misses them.
* `660a677` **[T2] CODEX-STALE-DAEMONS + Karanak override fix** — 7 invuln
  corrections (Bloodthirster, Lord of Change, Great Unclean One, Keeper of
  Secrets, Skarbrand, Bloodletters, Karanak) — all same mapper bug. Karanak
  override fix: codex value is 4+, overrides.json had it at 5+ (mis-identified
  in DAEMONS-DIAG-2); corrections layer now carries 4+ and the shadowing
  override field was removed.

**Audit Round 2** (`90a7ab5` **[T2] CODEX-AUDIT-ROUND-2**): retrospective
check on the May Plague-corrections found 5 over-broad DG/CSM Plague entries
from Round 1 to be over-zealous; reverted. First batch of post-revert audits
confirmed clean.

**BSData refresh** (`61366d1` **[T1] BSDATA-REFRESH**): pulled latest BSData
main; 1 caught-up correction retired (BSData upstream now carries the fixed
value).

**Batch 2 (Imperial Fists, Iron Hands, Dark Angels, White Scars,
Adeptus Titanicus):**

* IF, IH, White Scars — all clean (0 corrections). Chapter heroes and
  load-bearing units all match current Wahapedia 10e.
* `3ebb305` **[T2] CODEX-STALE-DARK-ANGELS** — 8 invuln corrections (Azrael,
  Belial, Sammael, Asmodai, Ezekiel, Lion El'Jonson, Deathwing Knights,
  Ravenwing Black Knights), all same mapper bug. Lion El'Jonson override
  fix: codex is 3+ (The Emperor's Shield), overrides.json had 4+ from an old
  sweep; corrections layer now carries 3+ and the shadowing override removed.
* `50e2601` **[T2] CODEX-STALE-TITANICUS** — 4 invuln corrections on Chaos
  Titans (Reaver, Warbringer Nemesis, Warhound, Warlord) for the 5+ Ion
  Shield. Same mapper bug. Loyalist Adeptus Titanicus side produces no
  parsed entries (the `.cat` uses only entryLinks into `Library - Titans`)
  and is scope-parked until the mapper learns to follow cross-catalogue
  entryLinks.

### Pattern observed

Every wave-47 invuln correction is the same root cause: BSData encodes
invuln saves as inline `<profile typeName="Abilities">` text rather than
as `<infoLink>`. The corrections file now has 20 such entries across 5
faction catalogues (Daemons Library, Deathwatch, Dark Angels, Titans
Library, plus the Ynnari parking-lot list still un-corrected). A
mapper-side fix to `mapper.extract_invuln()` would retire all of them in
one pass.

### Open carry-forwards into wave 48

1. **Mapper invuln-prose-walk fix** — single highest-leverage cleanup of
   the wave-47 corrections backlog. Teach `mapper.extract_invuln()` to
   parse inline `<profile typeName="Abilities">` text on the
   selectionEntry. Would retire 20+ correction entries and prevent the
   same bug appearing in every future stale-faction audit. Parking-lot
   instances still to add: Aeldari characters (Drukhari Archon,
   Craftworlds Autarch, Yvraine, Visarch, Yncarne) from the Ynnari audit.
2. **Loyalist Adeptus Titanicus parser support** — Imperium - Adeptus
   Titanicus .cat uses only entryLinks into Library - Titans and produces
   no parsed entries. Mapper needs cross-catalogue entryLink resolution.
3. **N=40 plateau** — gated MAE has been within 10.22-10.81 for 5
   consecutive evals across 10+ commits. The remaining gap is
   structurally locked (IK/CK -32/-41 mapper-bound, Drukhari +34
   Skysplinter-bound, Daemons -17 Locus-bound, Sororitas +17 spend-
   model bound). Without one of those four structural levers landing,
   further per-faction rule-correctness work will continue to be
   MAE-neutral. Recommended next pivot: mapper invuln fix (carry-forward 1)
   to retire the backlog, then attack one structural lever.
4. All wave-45 carry-forwards remain in place (Drukhari Skysplinter dormant
   pending the upstream reserves coupling firing in more samples, Sororitas
   Acts of Faith spend model unaudited, Daemons Locus magnitude unaudited,
   SECONDARY-SELECTION-V3 tier-table refinement, STRATAGEM-CHAIN-V2 cap 3).

