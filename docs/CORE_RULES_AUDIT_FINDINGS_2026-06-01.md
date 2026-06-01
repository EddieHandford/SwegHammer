# Core-rules audit findings — 2026-06-01 (watchdog-run, 6 phase agents + coverage sweep)

Source of truth: `data/reference/wahapedia_core_rules_2026-06-01.txt` (current 10e — Core Rules 1.8
Oct 2025 + Balance Dataslate 3.4 Mar 2026, captured verbatim). Each fix MUST re-verify its finding
against that file and cite it (the citation audit enforces this) — do NOT apply a finding on this
doc's say-so alone. "Verified✓" = the watchdog already confirmed it against the primary text.

Coverage was broadly confirmed faithful for: 2D6 charge + per-squad roll, Fights-First step ordering,
fight eligibility, Advance shoot/charge lockout, Big Guns Never Tire, Blast/Rapid Fire/Heavy, Locked-in-
Combat shooting lockout, Devastating/Indirect Fire, OC summed + strictly-greater contest, battle-shock
trigger/test/OC-0/duration, CP gain. The items below are the DISCREPANCIES, grouped into work-streams
designed to be merge-safe when run in parallel.

## How to work these — PARALLEL where file-disjoint (user directive 2026-06-01)
Dispatch the file-disjoint streams as concurrent worktree-isolated fix agents (sweg-wave skill +
CLAUDE.md §8 base-reset dance — push WIP, reset each worktree to it, confirm HEAD). The cover/line-of-
sight cluster (Stream D) shares `map.py`/`units.py`/`simulator.py` hot functions and must be ONE coherent
stream, not sub-split. Each fix: re-verify vs the captured source, edit, cite, run the pytest sweep +
N=40 A/B, keep only if faithful (metric direction does not gate a correctness fix — but measure + report).

---

### Stream A — AI objective-control path (`code/strategy.py` only — clean parallel)
- **A1. `_oc_on_objective` uses raw `profile.oc`, ignoring the damaged-Knight bracket.** Scoring uses
  `_effective_oc` (correct) but the AI planner reads base OC, so a damaged Questoris "thinks" it still has
  OC 10 and holds markers it can no longer win. Fix: call `_effective_oc` (or equivalent) in
  `strategy._oc_on_objective` (~line 333). Severity: low-moderate; **feeds the IK over-hold residual via AI decisions.**
- **A2. `_oc_on_objective` ignores battle-shock.** Scoring zeroes battle-shocked OC; the AI planner does
  not, so it over-respects phantom defenders. Fix: exclude battle-shocked units in the AI path too. Low.

### Stream B — Stratagems (`code/stratagems.py` + `data/rule_citations.d/stratagems.json` — clean parallel)
- **B1. Counter-Offensive citation `quoted_text` is WRONG.** It reads "even if it has already fought";
  current 10e says the target must have **not** already been selected to fight this phase. Fix the
  `quoted_text` to match the source. (Code behaviour is incidentally OK under the non-alternating model.)
  Citation hygiene; verify vs source.
- **B2. Core universal Insane Bravery is MISSING.** Only the Orks War-Horde variant exists; the universal
  1 CP once-per-battle auto-pass-a-battle-shock-test stratagem is absent from `UNIVERSAL_STRATAGEMS`.
  Add it (battle-shock-step hook, once per battle). Medium. Verify the card text + cite.

### Stream C — Terrain density data (`code/maps.py` only — clean parallel; this is the P1 density build)
- See the P1 terrain task. Match real competitive Pariah Nexus density (~25–30% area + central
  line-of-sight ruins) vs our sparse ~8%. Even-handed, cited, no gerrymandering. Measure AFTER Stream D
  lands (the line-of-sight rules must be correct for the density A/B to mean anything).

### Stream D — Cover + line-of-sight + terrain RULES (SERIAL: `map.py` + `units.py` cover + `simulator.py` shoot/charge gates) — do as ONE stream
- **D1. Verified✓ HEAVY_COVER `-1 to hit` is stale 9e (HIGH).** 10e cover = Benefit of Cover (+1 save)
  only; no -1 to hit from terrain. Remove the -1-to-hit from `HEAVY_COVER`/`RUIN` (`map.py` enum +
  `units.py` ~2247 + `simulator.py` `_do_shoot` cover application). Collapse Light/Heavy into one
  Benefit of Cover. Affects every game with ruins; metric direction uncertain (measure).
- **D2. Verified✓ TOWERING over-applied to RUINS.** Keep towering ignoring woods/obscuring (correct);
  STOP towering forcing `ruin_pass` — for ruins only AIRCRAFT is a blanket exception, TOWERING sees out
  only when WITHIN. `map.py has_line_of_sight`. Plausibly trims the IK over-hold (measure).
- **D3. Verified✓ Infantry "shoot through ruin walls" (`_has_ruin_pass`) is stale.** Current Area-Terrain
  Ruins block line of sight fully; the INFANTRY/BEAST exception is movement-only ("shoot through" = 0 hits
  in the source). Remove the line-of-sight pass; re-cite. (One agent hedged — re-confirm vs source.)
- **D4. Benefit of Cover AP0 / save-3+ exception MISSING, and the cap is mis-gated to INFANTRY only.**
  10e: a model with save 3+ or better cannot get Benefit of Cover vs an AP0 attack — applies to ALL
  models, not just INFANTRY. Add it (`units.py` ~2349-2363). Medium; over-rates 3+-save units in cover.
- **D5. Cover granted by position, not visibility.** APPROXIMATED (acceptable for a 2D sim) — note, don't fix.
- **D6. Re-frame `TerrainType` toward 10e categories** + re-cite `simulator.towering_los` /
  `core_terrain_ruins.json` to the verbatim 10e Ruins/Woods visibility + Benefit-of-Cover text.

### Stream E — Fall Back lockout (SERIAL with D — shares `simulator.py` `_do_shoot`/`_do_charge`; sequence after or fold into D)
- **E1. Verified✓ Fall Back FLY exemption is stale 9e (MEDIUM).** 10e: a unit that Fell Back cannot shoot
  or declare a charge — NO FLY exception (FLY only grants moving over models + skipping Desperate Escape).
  Remove `and not attacker.profile.fly` at `simulator.py` ~7146 (shoot) and ~7655 (charge); re-cite
  `core_fall_back.json` (currently quotes 9e text). Over-rates FLY factions (Aeldari, **Drukhari** +17).
- **E2. Charge-while-engaged / non-target engagement / disembark-after-transport-move.** Lower-priority
  charge-eligibility gaps (charge agent #2/#5/#11). Same file as E1 — bundle.

### Needs DESIGN, not a quick parallel fix (flag, do not rush)
- **Melee "Look Out, Sir" / characters absorb melee.** Ranged is faithful (`army.can_target_for_ranged`);
  melee has no character-protection gate, so characters die too fast in melee. But the sim models
  attachment as a proximity aura, not a merged unit — a faithful fix needs the leader+bodyguard
  representation, so this is a design item (relates to the one-Unit-per-model limits), not a 10-minute fix.
- **Fight-phase alternating activation** (active player fights a full pass; no IGOUGO alternation). HIGH
  structural, already a documented approximation — out of scope for a quick-fix batch.

### Coverage sweep — absent WHOLE mechanics (build-new tasks; separate from the quick-fix batch)
Reassuring baseline: the sim is broadly COMPLETE — the full weapon-keyword set (Lethal/Sustained/
Devastating/Anti/Blast/Melta/Heavy/Hazardous/Torrent/Lance/Indirect/Precision/Rapid Fire/Pistol/Assault/
One-Shot/Extra Attacks), modifier caps (±1 hit/wound, +1 save), unmodified-6 crit hit/wound, re-rolls-
before-modifiers, Feel No Pain, mortal-wound overflow + no-save, Deadly Demise, Deep Strike (9", R2+),
transports (embark/disembark/firing deck/destroyed-disembark), scouts, infiltrators, lone operative,
auras, CP economy, battle-shock — all PRESENT. The gaps below are whole mechanics that are ABSENT/stubbed.
These are BUILD-NEW (bigger) tasks — queue separately from and below the quick-fix batch; rank by impact.

1. **Deterministic damage (expected-value, not rolled) — RESOLVED 2026-06-01: USER APPROVED ROLLING IT
   (now goal-doc task P1.5).** Variable damage (D6, D3+3, etc.) is collapsed to its mean at load
   (`parse_dice_expr`); no per-shot roll. This OVER-rates high-variance high-damage weapons vs multi-wound
   models (plausibly feeds the Knight/big-gun over-rate) AND — the user's key point — leaves every
   damage-reroll / minimum-damage ability DEAD (no roll to manipulate; Space Marines' built-in optional
   damage re-rolls benefit immensely once damage is rolled). Build: (1) roll variable damage per shot;
   (2) wire the damage-reroll / floor abilities that were inert. Sequence after Stream-D `units.py` work;
   re-check the noise floor (rolled damage widens variance). (Med–High; global; structural.)
2. **Fire Overwatch (core stratagem) — ABSENT (High).** Out-of-phase reaction shooting at chargers /
   arriving reserves. Heavily used; its absence under-penalises melee/aggression and over-rewards melee
   vs shooting. Needs an out-of-phase shooting hook. Metric-relevant (melee vs gunline balance).
3. **Go To Ground / Smokescreen (core defensive stratagems) — ABSENT (Med).** Fragile infantry that
   leans on these is systematically over-killed → over-rates shooting, under-rates infantry resilience.
4. **AIRCRAFT special rules — ABSENT (High for aircraft units).** No 20" min move, 90° pivot, board-edge
   reserves fallback, non-FLY-can't-charge, no Pile-In/Consolidate, no Hover. Aircraft run as ordinary
   FLY → overstates their mobility. Affects Astra Militarum (Valkyrie), Space Marines (Storm Raven/
   Stormtalon), Aeldari (Hemlock). Build only if these units are in the archetype lists.
5. **Strategic Reserves (board-edge arrival) + Rapid Ingress — ABSENT (Med).** Only Deep Strike + Cult
   Ambush exist; the board-edge reserve path (6" edge, R2/3 gates, no enemy DZ R2) and the Rapid Ingress
   core stratagem are missing → under-models flanking/points-denial reserve builds.
6. **Mid-game voluntary embark — ABSENT (Med).** Units never re-embark a live transport → under-models
   Drukhari Skysplinter embark/disembark cycling and tactical transport use.
7. **Surge moves — ABSENT (Med).** No general surge primitive (only Khorne Blood Surge hard-coded).
8. **Lower severity:** Plunging Fire / barricade fight-reach / per-terrain-keyword effects (terrain is 5
   generic types); redeployment step; mid-game coherency removal; simultaneous-effect roll-offs;
   the ≤1-extra-CP-per-round cross-source cap. Defer.

Note (verify at fix time): the per-phase parallel agents reported a few items the coverage sweep marks
PRESENT (e.g. modifier caps, crit hits) — coverage and phase audits agree the per-attack engine is sound;
the disputes are only over the cover/Fall-Back/AI-OC items already in the quick-fix batch.
