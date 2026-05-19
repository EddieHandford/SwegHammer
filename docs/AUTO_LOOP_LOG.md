# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`.

### Iter 21 (2026-05-18) — LeaderAbility fabrication audit

6 agents cross-faction sweep. 5 commits landed via cherry-pick + cross-worktree merge; Orks was clean (no fabs).

**Fabrications dropped (all citation-grounded per Wahapedia)**:
- **Necrons**: Overlord/Trazyn `plus_one_to_hit`, Plasmancer `fnp=5`. Real rules are CP discounts (Strat-econ) and offensive Crit-on-5+ (not modelled). Plus Lychguard added to Overlord bodyguard list (host_keys).
- **Marines**: Guilliman/Captain `reroll_hit_ones`, Chaplain `reroll_wound_ones`. Real rules are CP-discount/once-per-battle Battleshock-removal. Plus Shield-Captain/Brother-Captain name-collision fix.
- **Aeldari**: Yncarne `plus_one_to_hit` (proxy for reactive-teleport), Autarch `plus_one_to_hit` (CP-discount, same as Overlord pattern), Avatar `reroll_hit_ones` (real rule is +1 Advance/Charge — movement phase).
- **TSON**: ADDED 4 NEW LeaderAbilities (Ahriman, Exalted Sorcerer, Infernal Master, Sorcerer in TA) — TSON was UNDER-modelling (LeaderAbility lookup returned None). Plus Magnus "Impossible Form" (−1 to incoming Damage), Ahriman +1 Cabal Psychic test. TSON 30% → 36.1% (+6.1pt).
- **DG**: Lord of Contagion `plus_one_to_wound` (iter 20 missed), Typhus `fnp=5` (iter 20 partial). host_keys corrected per codex (Blightlord/Deathshroud, not Plague Marines).
- **Orks**: clean — no fabs.

**Cumulative iter 21 (5 commits + cross-worktree merges)**: MAE **13.73 → 13.43pt** (Δ **−0.30**). Tests 776/776, Rule citations 221/221.

**Per-faction shifts (post-iter-20 → post-iter-21)**:
- Marines +20.3 → +19.5
- Necrons **+17.6 → +14.3** (−3.3 ✅ — Overlord fab removed)
- Aeldari −6.9 → −6.6
- Tyranids −17.7 → −18.6
- Orks +4.8 → +5.1
- T'au +11.1 → +11.3
- DG +23.7 → +23.9
- Custodes −3.8 → −3.8
- TSON −24.6 → −24.3
- Votann +6.8 → +6.8

## Loop pause — PR + Ed's main rebase (2026-05-18)

User directive: wrap up after iter 21, merge progress, pick up Ed's point-cost reference fixes from main before continuing iter 22+ (aura host_keys gating, variant invuln sweep, Magnus diag, AI improvements).

Iter 22-26 plan documented above remains valid for the next loop session.

## Branch pivot — claude/sim-calibration-2 (2026-05-19)

PR #22 merged onto main at `fe9458a` (Ed's point-cost reference fixes folded in). Branched `claude/sim-calibration-2` off the updated main. Fresh baseline at N=40 archetype: **MAE 9.13** (vs 13.43 on the old branch — Ed's main work dropped MAE by ~4.3 points). Per-faction:

- Marines −3.0, Necrons −6.5, Aeldari +2.8, Tyranids +5.1, Orks +11.5, T'au +7.2
- **DG +20.9** (major over), **Custodes −18.6** (major under)
- TSON −3.2, Votann +12.6

DG combat-model over-strength and Custodes under-modeling are now the dominant outliers.

### Iter 22 (2026-05-19) — host_keys aura gate + invuln long-tail sweep

3 agents dispatched in parallel:

1. **`effective_buffs` host_keys gate** (af396da4): per-leader aura merge in `code/leaders.py` was firing army-wide regardless of `host_keys`. Typhus FNP was applying to every Death Guard within 6 inches, Lieutenant +1-to-wound to every Marine within 6 inches — same structural bug across every faction with character auras. Gate now: if `leader.host_keys` is non-empty, the attacker's catalog key must be in `host_keys` for the buff to merge. Empty tuple `()` retained as the explicit army-wide convention for MONSTER auras (Hive Tyrant Onslaught, Avatar Bloody-Handed). Reverse name lookup widened to a tuple (Plague Marines exists in both DG and CSM catalogs; gate tests set intersection). Hive Tyrant `host_keys` cleared to `()` per Wahapedia (Onslaught is broadcast). 49 leaders tests pass. Faction-neutral structural fix.

2. **Variant invuln long-tail sweep** (a6738d6f): 72 new override entries in `data/overrides.json` for units whose BSData v10.6.0 datasheet omits the Invulnerable-Save infoLink. Coverage spans every Aeldari Phoenix Lord and EPIC HERO, all Necron Lord characters, Death Guard / CSM / WE / EC HQ entries, Daemons library, Sororitas, Dark Angels HQs, Captain in Terminator Armour, Einhyr Champion. Each entry's `notes` cites the Wahapedia datasheet.

3. **LeaderAbility wide-aura audit** (ab89afd5): no code changes. Analysis-only; existing host_keys were already correct after iter 21. Discarded.

**Cumulative iter 22 (2 commits)**: MAE **9.13 → 9.20** (Δ **+0.07, flat within noise**).

**Per-faction shifts** (baseline → iter22):
- Marines −3.0 → **+0.1** (closer to zero, ✅)
- Necrons −6.5 → −7.9 (slight regress)
- Aeldari +2.8 → +1.7 (✅)
- Tyranids +5.1 → +6.2
- Orks +11.5 → **+8.7** (✅)
- T'au +7.2 → +7.2 (flat)
- DG +20.9 → **+22.8** (regress — host_keys gate removed phantom aura buffs that were partially counteracting DG over-strength)
- Custodes −18.6 → −22.2 (regress — Lieutenant-on-everyone correction made Marines stronger, Custodes look weaker by comparison)
- TSON −3.2 → −4.9
- Votann +12.6 → +10.4 (✅)

Per the iter 20 user directive (correctness > MAE), KEPT — both fixes are Wahapedia-grounded rule corrections. The two outstanding extreme outliers (DG +22.8 / Custodes −22.2) are unchanged and are the iter 23+ targets.

**Iter 23 priorities**:
1. **DG combat model audit** — Plague Marine sticky-objective, Disgustingly Resilient FNP triggering, Plague Weapons stratagem application, Mortarion deadly_demise interaction with the host_keys gate.
2. **Custodes diagnostic** — under-modeling persists from iter 20 (LOS+ablative already implemented in `code/army.py::can_target_for_ranged`); next vector is durability stack, Vexilla auras, Auric Mortalis detachment, or Trajann's per-leader buff.
3. **Magnus / TSON under-strength** — still −4.9. Magnus stat investigation from iter 21 didn't produce a fix; needs followthrough.

### Iter 23 (2026-05-19) — diagnostic-only, three parallel agents

DG / Custodes / TSON ranked root-cause reports. Outputs `iter23_dg_diag.md`, `iter23_custodes_diag.md`, `iter23_tson_diag.md` on each agent's worktree branch. No code changes.

**DG diag (LARGE/LARGE/MEDIUM)**:
1. Lord of Contagion `host_keys=("death_guard_plague_marines",)` is a CLAUDE.md §10 fabrication — Wahapedia bodyguard list is Blightlord/Deathshroud only. Iter22's effective_buffs gate then faithfully fires +1-to-wound on the spam unit.
2. Archetype seats Mortarion 4/20 — (-count, -cost) walk eats cheap units first.
3. Worldblight stratagem fires army-wide always-sticky instead of "end of Command phase + already controlling".

**Custodes diag (LARGE/LARGE/MEDIUM-LARGE)**:
1. Custodian Wardens have `fnp=7` in parsed.json + no innate -1 damage; the flagship brick is strictly less durable than Custodian Guard.
2. Trajann + Shield-Captain host_keys = Custodian Guard ONLY — Wardens / Allarus / Sagittarum / Vertus fight unbuffed. Blade Champion has no LeaderAbility entry (§13 fail-loud violation).
3. Six Custodes profiles wrongly flagged `deep_strike=True` (Guard / Wardens / Sagittarum / Trajann / Blade Champion / Shield-Captain).

**TSON diag (LARGE/MEDIUM/SMALL-MEDIUM)**:
1. Detachment lottery: TSON resolves to Grand Coven 11/20 (Kindred Sorcery not implemented; Grand Coven disables All Is Dust = no compensation).
2. Magnus seats 0/20 in archetype armies — template deliberately omits him; his wired rules (Impossible Form, Lord of the Planet) are dead code.
3. Magnus has no LeaderAbility entry — §13 fail-loud, like Blade Champion.

### Iter 24 (2026-05-19) — fix bundles, three parallel agents

8 commits cherry-picked on `claude/sim-calibration-2`:

**DG bundle (D1-D4, commits `f4f3864`-`f12ba87`)**:
- D1: Lord of Contagion `host_keys` → Blightlord/Deathshroud only + test update.
- D2: Faction-neutral archetype EPIC HERO anchor guarantee — force-seed the most expensive template EPIC HERO with overflow up to `points_budget * 0.6`.
- D3: Worldblight strict OC-contest gate — sticky promotes only when DG side wins the contest on the marker.
- D4: Plaguebearers / Blightlord / Typhus FNP=5 overrides (mapper-gap; Disgustingly Resilient is codex-level, not per-unit in BSData).

**TSON bundle (T1-T3, commits `70fa5e7`, `bf1b652`, `0e96a96`)**:
- T1: Drop `grand_coven` from `FACTION_DETACHMENTS["Thousand Sons"]` until Kindred Sorcery is wired.
- T2: Add Magnus to Rubricae Phalanx archetype + TSON to `SEED_FRACTION_BY_FACTION` at 0.4 (800pt slice).
- T3: Add Magnus the Red placeholder LeaderAbility entry (no aura flags — his rules are self-conferred in simulator.py; entry exists for §13 fail-loud).

**Custodes bundle (C single commit `8f96a80`)**:
- C1: Resolute Will (Custodian Wardens datasheet) — defender-side -1 to Wound roll, gated by `defender.resolute_will` + `leaders.is_actually_led(defender)` + `attack.strength > defender.toughness`. New fields on UnitProfile + CatalogEntry; citation under `simulator.resolute_will`.
- C2: Trajann (Auric Sage) + Shield-Captain (Stoic Vigil) `host_keys` widened from Guard-only to (Guard + Adrasite-spear variant + Wardens) per the BSData Imperium - Adeptus Custodes Leader text.
- C3: Blade Champion LeaderAbility added structurally (no aura fields — Martial Inspiration + Swift Onslaught aren't expressible in the schema). Closes §13 silent-default gap.
- C4: `deep_strike: false` override on Custodian Guard / Wardens / Sagittarum / Trajann / Blade Champion / Shield-Captain. Wahapedia datasheets do not list Deep Strike on any of the six.

**Cumulative iter 24 (8 commits)**: MAE **9.20 → 6.51** (Δ **−2.69 at N=20**; iter22 baseline measured at N=40 so the comparison carries ~±2pt cross-N noise).

**Per-faction shifts** (iter22 N=40 baseline → iter24 N=20):
- Marines −3.0 → −4.1 (flat)
- Necrons −6.5 → −7.1 (flat)
- Aeldari +2.8 → −3.3 (6pt swing — partly noise, partly Magnus-on-TSON pressure)
- Tyranids +5.1 → −0.2 ✅
- Orks +11.5 → +7.9 ✅
- T'au +7.2 → +8.3 (slight regress)
- **DG +20.9 → +8.7** ✅ (−12.2pt — D1+D2+D3+D4 bundle landed as designed)
- **Custodes −18.6 → +2.6** ✅ (+21.2pt — Resolute Will + leader host_keys widening were the dominant levers)
- TSON −3.2 → −7.9 (regress — Magnus anchor eats budget but the unit appears under-priced relative to what it displaces; iter 25 attention)
- Votann +12.6 → +11.1 (slight ✅)

**Iter 25+ priorities**:
1. **Magnus / TSON re-tune** — T2's Magnus anchor regressed TSON. Either Magnus's stat profile is wrong (BSData has M=6 W=16; current Wahapedia shows M=12 W=18 — flagged for awareness in iter23 but not actioned) or his archetype anchor displaces too-strong picks. Re-measure after Ed's perf-optim main pivot.
2. **T'au +8.3 over** — second-largest outlier now. Needs a diag (Mont'ka / Markerlight / Crisis pricing).
3. **Votann +11.1 over** — third outlier. Likely Oathband stratagems + Sagitaur durability.

## Branch wrap-up — PR open + sim-calibration-3 pivot (2026-05-19)

Loop housekeeping + iter 22-24 complete on `claude/sim-calibration-2`. Pivoting to `claude/sim-calibration-3` (off updated main) to pick up Ed's simulator performance optimisations (Tier 1 pure-function caching, Tier 2 alive_units cache + vectorised deepstrike, Tier 3 LOS/cover/durability caching — perf only, no behaviour change). Iter 25-26 will run on the new branch.

## sim-calibration-3 baseline (2026-05-19)

Branch = `claude/sim-calibration-2` + Ed's main merged in (commits `d48c8c6`, `4ea0519`, `cc38091`, `80c9a78`). Clean merge — no conflict markers. Baseline N=20 archetype eval:

- **MAE 6.62 pts** (vs iter24 sim-cal-2 N=20 = 6.51 — essentially flat, +0.11)
- **Wall-clock: 257s** for full N=20 matrix. Compared to ~10-15 min on sim-cal-2 (no perf optims) — **roughly 3-4x speedup** at N=20. Bigger expected gains at N=40+ where the per-battle caches amortise more.

Per-faction shape redistributed even though cumulative held flat — Ed's caching has small behaviour deltas on some paths. Notable shifts (iter24 → sim-cal-3 baseline):
- Marines, Necrons, Aeldari all moved closer to target (under-performers improved by 2-6pt)
- DG, T'au, Votann, TSON all moved further from target (over-performers grew, TSON under-perf deepened)

Iter 25 priorities locked in based on the new outlier shape:
1. Votann +16.8 — V1 diag-and-fix
2. TSON -12.9 — T1 Magnus retune or anchor backout
3. DG +12.6 regress — D1 diagnostic (verify iter24 commits intact, scan Ed's commits for DG-touching paths)

### Iter 25 (2026-05-19) — bundle-of-one fix-first protocol

First iter run under the new `docs/AUTO_LOOP_PROCEDURE.md` rules (A-F). Three parallel agents, ≤30 tool uses each, ~400-token prompts.

**T1 — TSON Magnus anchor backout** (commit `6af92d8`, agent: 48k tokens, 26 tool uses, 7min). Root cause: BSData mapper folds Magnus's two weapon profiles (Tempestus Sceptre ranged + Blade of Magnus melee) into one — his combat output is half-represented while he eats half the budget. Reverted iter24-T2 (template seed + SEED_FRACTION_BY_FACTION bump). T1 (drop grand_coven) + T3 (Magnus LeaderAbility placeholder) preserved. Eval: TSON -12.9 → +2.1; MAE 6.51 → 5.26.

**V1 — Votann Eye of the Ancestors retired-rule removal** (commit `5ccc301`, agent: 64k tokens, 37 tool uses, 9min). Root cause: `code/units.py` was implementing the RETIRED launch-day Eye of the Ancestors re-roll buffs (re-roll hit 1s at 1 token, re-roll all hits + re-roll wound 1s at 3 tokens). Current 10e codex Prioritised Efficiency has no re-roll buffs — `code/simulator.py:5104-5107` literally documented this as known stale. Removed the buff branch; kept token bookkeeping infrastructure intact. Updated `tests/test_judgement_tokens.py` (two tests pinned to the retired rule). Eval: Votann +16.8 → +14.0; MAE 6.51 → 5.86.

**D1 — Death Guard regression diagnostic** (no commit, agent: 44k tokens, 14 tool uses, 2min). Verified all iter24 D1-D4 fixes are intact. Verified Ed's Tier 1/2/3 caches don't touch FNP-relevant paths. Conclusion: latent AI blindness — `_durability()` in `code/strategy.py` ignores FNP entirely, so opponent AIs see DG only by (save, invuln, AP) and bounce off the FNP wall. iter24-D4 making more DG units carry FNP=5 exacerbated this. Iter 26 recipe: fold `fnp` into `_durability` and `_unsaved_fraction` (faction-neutral AI improvement helping every FNP-carrying army).

**Cumulative iter 25 (T1 + V1, 2 commits)**: MAE **6.62 → 4.49** (Δ **-2.13**). Best result of the entire calibration loop. Six factions within ±2.6pt of target.

**Per-faction shifts** (sim-cal-3 baseline → iter25):
- Marines -1.9 → -1.3 ✅
- Necrons -1.0 → -0.4 ✅ (at target)
- Aeldari -1.1 → -1.6 (flat)
- Tyranids +1.4 → +2.6 (slight)
- Orks +7.3 → +5.7 ✅
- T'au +9.9 → +8.3 ✅
- DG +12.6 → +10.3 ✅ (cross-N variance settling)
- Custodes -1.3 → +0.3 (at target)
- **TSON -12.9 → +3.2** ✅ +16.1pt (T1 backout)
- **Votann +16.8 → +11.2** ✅ -5.6pt (V1 retired-rule removal)

**Iter 26 priorities**:
1. **S1 (faction-neutral AI):** fold FNP into `_durability` and `_unsaved_fraction` in `code/strategy.py` (per D1 diag recipe). Helps DG, Necrons, Custodes, Tyranids, Nurgle daemons — every FNP-carrying army. Expected DG / Custodes / Necrons movement toward zero; T'au / Votann / Orks neutral (no FNP).
2. **V2:** Votann second pass — V1 was partial (-2.8pt). Probable next lever: Sagitaur durability or Hearthkyn Warriors stats.
3. **T1:** T'au +8.3 diag — Mont'ka, Markerlight, Crisis Suit pricing.

Token-efficiency note: iter 25 total agent spend = 156k tokens / 77 tool uses across 3 agents. Compare to iter 24's 4-bundle agent: ~70k for ONE incomplete bundle + manual cleanup. The bundle-of-one + trimmed-prompt protocol is roughly 3x more efficient per fix shipped.

### Iter 26 (2026-05-19) — 3 parks, MAE flat at 4.49

Three bundle-of-one agents dispatched. All three correctly held the new procedure's "STOP rather than invent" line; the loop's easy leverages near the noise floor are depleting and that's reflected in the outcome.

**S1 — faction-neutral FNP in AI threat-score** (agent: 62k tokens, 33 tool uses, 18min). Implementation correct: folded Feel No Pain into `_durability` and the four `_melee_target_score` / `pick_charge_target` callers in `code/strategy.py`. Cited under `simulator.fnp_in_threat_score`. Target factions improved as predicted (DG +10.3 → +9.8, Tyranids +2.6 → -0.2). Cross-faction effect regressed Orks (+5.7 → +10.1) — FNP-bearing defenders now correctly read Orks as soft and push harder, while Orks have no FNP to compensate. **Cumulative MAE 4.49 → 4.99 (+0.50)**. Per the loop rule (regressions get parked), the fix stays on the agent's worktree branch (commit `35d71c2`) and is not cherry-picked. Iter 27 follow-up: symmetric Orks attacker-side AI improvement, then re-land S1.

**V2 — Votann second pass** (agent: 60k tokens, 30 tool uses, 5min). Audited Sagitaur, Hearthkyn, Hearthguard, Eye of the Ancestors (already neutralised by iter25-V1), OATHBAND detachment, Kâhl LeaderAbility, Einhyr Champion override. All match Wahapedia / BSData. No provable lever within the 8-tool diagnostic budget — STOPPED. Residual +11.2 hypothesis: AI CP heuristic over-firing on Votann, baseline drift, or Stage 2 sweg_balance_mc points cuts on Sagitaur / Hekaton (out of Stage 1 scope).

**T1 — T'au +8.3 diag-and-fix** (agent: 73k tokens, 53 tool uses, 28min). Found a real rule-fidelity issue: Mont'ka LETHAL HITS fires every round in `code/units.py:1155-1164`, but Wahapedia restricts it to battle rounds 1-3. Tested fix — T'au win rate unchanged (battles decided rounds 1-3 anyway). Reverted per the brief. Diag file flagged iter 27 follow-ups: (a) Markerlight realism (current `_run_markerlight_phase` auto-marks with no roll / no LOS / 36" range — likely the real T'au lever), (b) Riptide / Stormsurge weapon-profile audit, (c) full audit of six wired `MONTKA_STRATAGEMS` for round/phase gating.

**Cumulative iter 26**: no commits cherry-picked. MAE stays **4.49**.

Token-efficiency: 195k tokens / 116 tool uses across 3 agents for net-zero code shipped — but three high-quality diagnostic deliverables landing in agent-worktree diag files. The procedure's tradeoff is working as designed: shipping zero buggy fixes is the right outcome when no clean lever exists.

**Iter 27 priorities**:
1. **T'au Markerlight realism** (largest residual outlier where a clear bug is named) — gate auto-Guided behind a roll + LOS check.
2. **Orks attacker-side AI heuristic** — symmetric counterpart to S1's defender FNP fix. Once Orks correctly identify FNP-bearing defenders as hard targets, S1 can re-land and the cumulative MAE should drop.
3. **Riptide / Stormsurge weapon profile audit** if T'au isn't closed by Markerlight alone.

### Iter 27 (2026-05-19) — Markerlight realism lands, 2 parks

Three agents on the locked-in priorities. One shipped, two parked with strong diag value.

**M1 — Markerlight realism** (commit `43f4826` → `86e3137`, agent: 99k tokens, 95 tool uses, 36min). Gated `_run_markerlight_phase` on 36" range + `Map.has_line_of_sight` + `can_target_for_ranged` (LOS+ablative) + d6 hit roll vs carrier BS via `_prob_to_target`. Token bookkeeping preserved. Cited under `simulator.markerlight_emission`. New test `test_markerlight_hit_roll_failure_grants_no_token`. **T'au +8.3 → +4.9 (-3.4pt). MAE 4.49 → 4.08 (-0.41)**. Note: agent went over the procedure's 30-tool-use cap (95 used) — the cap may be too tight for non-trivial simulator changes; consider relaxing to 50 for code/simulator.py edits.

**M2 — Riptide / Stormsurge audit** (agent: 58k tokens, 35 tool uses, 10min). Riptide / Stormsurge stats verified clean against BSData. Tested switching Stormsurge to Pulse Driver Cannon (the long-range Heavy 6-shot profile vs the focused Pulse Blastcannon). **Regressed** — MAE 4.49 → 4.72; T'au +8.3 → +9.4. Reverted. Mechanism finding: **damage wastage is unmodelled in the sim** — D12 high-damage weapons waste damage on low-wound targets, so multi-shot D3 profiles are systematically more efficient than codex intent. Damage spillover/carry-over is a structural Stage 1 issue larger than a bundle-of-one. Added to iter 28+ recipes.

**O1 — Orks diag-and-fix** (agent: 75k tokens, 39 tool uses, 10min). Found a real bug: `UnitProfile.sustained_hits` populated from the ranged primary weapon but read in melee mode at `code/units.py:1222`. On Orks the War Horde +1 stacks → fabricated SUSTAINED HITS 2 melee on Flash Gitz, Kaptin Badrukk, etc. Tested gate to ranged-only — **regressed** because other factions have legitimate melee SH that the gate killed. Proper fix needs separate `melee_sustained_hits` field on `UnitProfile` with mapper-side `best_melee` routing. Out of bundle-of-one scope; added to iter 28+ recipes.

**Cumulative iter 27 (1 commit)**: MAE **4.49 → 4.08** (Δ **-0.41**). Seven factions within ±2.2pt of target. Eval wall-clock 268s (Ed's perf optims giving consistent ~4-min N=20).

**Per-faction shifts** (iter 25 → iter 27):
- Marines -1.3 → -0.8 ✅
- Necrons -0.4 → -1.5 (slight)
- Aeldari -1.6 → -2.2 (slight)
- Tyranids +2.6 → +0.9 ✅
- Orks +5.7 → +7.3 (slight regress — M1 cross-effect; less Guided T'au fire means other T'au shots redistribute)
- **T'au +8.3 → +4.9** ✅ (-3.4 — M1 target hit)
- DG +10.3 → +11.4 (slight regress)
- Custodes +0.3 → +1.4 (flat)
- TSON +3.2 → -0.7 ✅
- Votann +11.2 → +9.6 ✅

**Iter 28 priorities**:
1. **DG +11.4 deep-dive** — iter25-D1 said cross-N variance + AI FNP-blindness; the FNP fix regressed Orks. DG is now the worst outlier. Re-baseline at N=40 or N=80 and decide if it's a real structural lever or noise.
2. **Damage spillover modelling** — M2 finding. Fundamental Stage 1 issue: high-damage weapons waste output on low-wound targets, low-damage multi-shot is systematically over-efficient. Affects DG / T'au / Votann pricing simultaneously.
3. **`melee_sustained_hits` mapper field** — O1 finding. Mapper schema change + unit.attack re-routing. Enables iter28 Orks-side correction without breaking other factions.

