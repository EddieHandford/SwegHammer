# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 45 close (2026-05-28)

Branch `claude/sim-calibration-6`. 1 commit landed on top of wave-44 close
`0aaa73c`. Top commit at wave-45 close is `4b3e18d`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 44 close (`0aaa73c`, 2026-05-28) | 13.57 | 10.22 | 5/22 |
| Wave 45 close (`4b3e18d`, 2026-05-28) | 13.57 | **10.22** | 5/22 |

Wave 45 is a no-metric-move iter. Skysplinter Assault wiring is correct
but inert because of an upstream gap. SECONDARY-SELECTION-V2 was attempted,
regressed, and reverted.

### Landings

* `4b3e18d` **[T1] DRK-SKYSPLINTER-DISEMBARK** — wire LANCE + IGNORES
  COVER on Drukhari units the turn they disembark from a TRANSPORT,
  closing the largest tractable outlier (Drukhari +33 gated). Added
  `Unit.transient_lance_this_turn` + `Unit.transient_ignores_cover_this_turn`
  flags, composed via OR with the profile flags in `Unit.attack`; set
  by `_disembark` when the army's detachment is Skysplinter Assault; 9
  new tests in `tests/test_skysplinter_disembark.py`.

  **Eval: zero metric movement (Drukhari 86.5% to 86.5%).** Root cause:
  the Drukhari Raider and Venom both carry `deep_strike=True` in BSData
  (the Aeldari "Deep Strike" infoLink). `_deploy_armies` routes every
  `deep_strike=True` unit into reserves BEFORE `_embark_pregame_passengers`
  runs, so the pregame embark pass sees zero Drukhari transports on the
  board. Across 40 sample battles (~17 with Skysplinter Assault), zero
  Drukhari disembark events fire. The wiring is rule-correct and will
  activate the day the upstream gap closes.

### Failed attempt: SECONDARY-SELECTION-V2

Faction-aware picker (replacing V1's uniform heuristic) was attempted
to close the V1 +0.66 regression. Faction tiers were classified as
ELITE / MOBILE / MID. Eval result: gated MAE 10.22 to 10.89 (+0.67,
worse than V1).

Root cause of the regression: tier table miscalibration. Adeptus Astartes
classified as "elite" (BiD + Assassination Fixed) crashed Marines sim
55.8% to 39.5% — Tactical Marines field 5-10 model squads and are
mid-shape, not the 3-5 elite shape Custodes / Knights occupy. The V2
revert spec (gated MAE > 10.6 indicates V2 isn't an improvement)
triggered; reverted in working tree, no commit.

### Open carry-forwards into wave 46

1. **Upstream reserves + embark coupling** — when a TRANSPORT is routed
   into reserves at `_deploy_armies`, route its matched INFANTRY
   passengers into reserves alongside it (or pre-embark before reserves
   routing). Unblocks the dormant Skysplinter wiring and probably similar
   gaps on Marines Drop Pods / Aeldari Wave Serpents / etc.
2. **SECONDARY-SELECTION-V3** — V2's tier table was over-aggressive on
   elite tier. V3 should put Marines / Sororitas / GK in MID, leaving
   only Custodes / IK / CK as ELITE. The structural V1 fix stays in
   place; V3 is a tier-table refinement only.
3. **Daemons Locus broadcast magnitude** — anchor (DAEMONS-FIX-1) landed
   in wave-44 but the +0.6 wr-points was below noise. Per
   DAEMONS-DIAG-10 findings the remaining levers are the Locus aura
   broadcast magnitude and Greater Daemon combat profile audit.
4. **Sororitas Acts of Faith spend model** — unaudited, gated 16.05.
5. **STRATAGEM-CHAIN-V2** — widen cap from 2 to 3.
6. All wave-44 carry-forwards remain in place.

