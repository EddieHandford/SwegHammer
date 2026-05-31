# SwegHammer calibration — current state

**Last updated:** Wave 68 close (2026-05-31), core-rules-correctness batch.

**Status:** Headline gated MAE **8.74** (raw 12.05), in-band 5/22. Wave 68 was a
deliberate **fidelity-first** wave from the full 10e core-rules audit
(`docs/CORE_RULES_AUDIT.md`): removed the **Heroic Intervention fabrication** (not a
10e rule — was a free defensive move for every Character) and fixed five real bugs —
Fall Back no longer always rolls Desperate Escape (only when battle-shocked or
crossing enemies); Indirect Fire now applies its unmodified-1-3-auto-fail + Benefit
of Cover; in-engagement (Pistol/Big Guns) and Blast target restrictions; unmodified-6
always hits; disembark can't place within Engagement Range; battle-shocked units
fight first in Remaining Combats. 919 tests green (deleted the HI test file), audit
280/280.

The headline rose +0.94 (7.80 → 8.74) — expected: the fixes move factions away from
a calibration fitted on the old wrong rules. Concentrated on **Chaos Daemons
−13.7 → −19.0** (HI removal correctly weakened a Character-heavy melee army that the
fabrication propped up) and the shooty over-shooters **Aeldari/Sororitas** (Fall Back
fix lets them disengage and keep firing). The **archetype-list re-fit (task #22)** is
now the gating next step and must lift Daemons + Knights while trimming
Aeldari/Sororitas/Thousand Sons.

### Earlier — wave 67 (per-unit-mechanics batch, gated 7.56 → 7.80, in-band 3 → 5)

Headline gated MAE was **7.80** (raw 11.11), **in-band 5/22** (was 3/22).
Wave 67 landed all six top findings from the per-unit-mechanics audit in parallel
(one worktree agent each, cherry-picked to `ba2a8b4`): unit coherency (cluster
squads at deployment + objective control credited per unit), per-unit secondary
scoring (No Prisoners / Cull count destroyed units), Reanimation/Undying Legions
grouped by `squad_id`, stratagem transient buffs applied to the whole squad (60
sites), per-squad battleshock + Mob Rule by squad_id, and the once-per-unit gate
re-keys (Oath, Acts of Faith, Strands, Miracle die, Markerlight, Blood Surge,
Beacons). All rules-correct; 922 tests green; citation 281/281 (new
`simulator.unit_coherency`).

The gated headline rose +0.24 (7.56 → 7.80) even though in-band improved 3→5 and
big structural fixes landed (Necrons +4.2→−1.3 from reanimation; Drukhari
+30.1→+27.8 from coherency). The regression is one faction: **Adepta Sororitas
+10.1→+17.2** (gated 6.3→13.4) — stratagem-buff propagation + the Acts-of-Faith
squad re-key correctly made Sororitas stronger, past a list tuned around the old
bugs. This is the fidelity-then-refit pattern: the sim is now more correct, so the
**archetype-list re-fit (task #22)** is the immediate next step, Sororitas first.

### Earlier — wave 66 (mortal-wound spillover + Deadly Demise + Blast, gated 7.78→7.56)

Wave 66
landed the mortal-wound half of the allocation rule (`Battle._apply_mortal_wounds`:
excess mortal wounds carry to the next model of the unit, unlike normal damage),
fixed **Deadly Demise** to hit each *unit* once (was per-model), and scoped **Blast**
to the targeted unit via `squad_id`. Eval 7.78 → 7.56 (small, rules-correct).

A user question about per-model vs per-unit framing then triggered a four-agent
**per-unit-mechanics audit** (`docs/PER_UNIT_MECHANICS_AUDIT.md`): the per-model
representation pervades the codebase and `squad_id` is the fix key. Top open items
(tasks #23-28): coherency wave (deployment clustering + OC-per-unit — the likely
remaining lever on horde over-shoot), per-unit secondary scoring (No Prisoners /
Cull count models not units), Reanimation profile.name→squad_id pooling, stratagem
transient-buff propagation to squad siblings, per-squad battleshock.

### Earlier this session — wave 65 (damage-allocation spillover, gated 9.27→7.78)

Wave 65 landed the biggest fidelity fix in many waves: **damage-allocation spillover**
(`simulator.damage_allocation_spillover`). The sim previously dumped a whole
volley into ONE model of a multi-model unit and wasted the overkill; now each
unsaved wound allocates to the next surviving same-`squad_id` model, with a
destroyed model's excess damage lost (kills bounded by unsaved-wound count, not
damage total — the actual 10e rule). This was the real "Lever 1" win: it moved
exactly the structural-residual factions (Tyranids −10.4, Imperial Knights +8.0,
Orks −7.2, Drukhari −7.2, Chaos Knights +4.8, AdMech −4.6). Built on the P1
`squad_id` infrastructure (behaviour-neutral) added the same session. See
`docs/RULE_ACCURATE_FIX_DESIGN.md` and memory `project-squad-activation-contained-wash`.

Second-order effect to chase next: elite/MEQ armies (Custodes +9.9, Marines
+10.3, Thousand Sons +21.7, Aeldari +13.5) now clear chaff more efficiently and
drifted further over — candidates for an archetype-list re-fit.

This file is the fast-pickup point for any session continuing the loop.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 59 close (`f1c2825`) | 14.28 | 10.73 | 3/22 |
| Wave 60 close (`e1f3f53`+docs) | 14.27 | 10.71 | 2/22 |
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |
| Wave 63 close (`96fd68e`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 65 close (spillover+docs) | 11.15 | 7.78 | 2/22 |
| Wave 66 close (mortal+demise+blast) | 11.08 | 7.56 | 3/22 |
| Wave 67 close (per-unit batch ×6) | 11.11 | 7.80 | 5/22 |
| **Wave 68 close (core-rules batch, fidelity)** | **12.05** | **8.74** | **5/22** |

Wave 65's lever was a **core-rule fidelity fix** (damage allocation), not AI or
stats — confirming the `project-faction-residual-rootcause` thesis that the big
residuals are structural representation bugs, not tuning. In-band count is flat
at 2/22 but the error *magnitude* dropped sharply (gated −1.49); the improved
factions are still outside their noise floors but much closer.

## Handoff context — wave 61 close

Three fixes landed (all on `claude/sim-calibration-6`, pushed through
`d141a69`; `c4d6da6` is the AI-gate commit, docs/close on top):

- **KNIGHTS-TITANIC-ESCAPE** (`31e477c`): TITANIC/FLY exempt from Desperate
  Escape + threshold 1→1-2 (Wahapedia verbatim).
- **KNIGHTS-DEMISE-D6PLUS2** (`d141a69`): mapper D6+2 parse + 11 chassis
  overrides (Deadly Demise was 1, should be 5).
- **KNIGHTS-AI-FALLBACK** (`c4d6da6`, the dominant lever): melee-primary
  units stay and fight instead of Falling Back. Corrected Knights UP
  (IK +10.1) AND over-shooters DOWN (Votann/AdMech/Orks/Marines/AstraMil).

New over-shoots introduced by the gate (melee units now staying engaged):
**World Eaters +7.1, CSM slightly over** — top carry-forward to re-tune.

## Next ranked levers for wave 66

Spillover reshaped the residual landscape. Current biggest gated errors:
Chaos Knights −36.5 (33.3), Drukhari +29.0 (25.7), Imperial Knights −19.1
(16.1), Chaos Daemons −14.5 (11.3), Thousand Sons +21.7 (13.0).

1. **Archetype-list re-fit for the new elite over-shoots** — Custodes (+9.9),
   Marines (+10.3), Thousand Sons (+21.7), Aeldari (+13.5) drifted further over
   now that they clear chaff efficiently. These are list-composition tunable
   (see memory `project-calibration-surface`); the fidelity layer is now more
   correct, so re-fitting the lists against it is the natural follow-up.
2. **Mortal-wound spillover** — the spillover pointer covers normal + Devastating
   Wounds; true mortal wounds (Doombolt, Deadly Demise, Bloodthirster) still dump
   into one model and SHOULD carry over per the separate 10e rule. A second,
   smaller fidelity fix (likely TSON/Daemons-relevant).
3. **Per-kill trigger emission under spillover** — `_do_shoot`/`_do_fight` emit
   UnitKilled + per-kill awards (Votann Judgement, WE Blood Tithe) only for the
   primary target, so spilled-kill siblings under-fire those triggers. Low-risk
   accuracy refinement.
4. **Detachment citation/comment fixes** (task #10), **Necrons fabrications**
   (task #9, MAE-negative — care), **TOWERING** (task #3, measure).

## Structural track (owns the remaining headline)

- **Chaos Knights −36.5 gated** — still the single largest residual; spillover
  only moved it +4.8 (CK is War-Dog/Armiger heavy — fewer big anti-horde guns
  benefiting from spillover than Imperial Knights, which moved +8.0). Needs its
  own diagnostic (likely board-control / objective play, not firepower).
- **Drukhari +29.0** — came down −7.2 from spillover but still the #2 residual;
  the remaining gap is activation-count / fragility-tax, not damage allocation.
- **Strategy roadmap #1 (task #12)** — plan-level objective function (next-turn
  reachable Objective Control into intent + activation order). Highest-leverage
  remaining AI lever; addresses the positional under-shooters (Daemons, Knights).

NOTE: the IK/CK multi-profile weapon mapper is DONE (shipped pre-wave-60);
do not re-implement it. See memory `project-knights-multiprofile-weapons`.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go".
- Per CLAUDE.md §10: every rule fix needs a Wahapedia/BSData citation. The citation audit is ENFORCING on commit (`BLOCK_ON_MISSING_CITATIONS=True`).
- **Always** prefix the eval: `PYTHONHASHSEED=0 ... python -m scripts.evaluate_vs_meta --battles 40 --use-archetype` (segfault workaround; memory `project-eval-pythonhashseed-segfault`).
- Model tiering (global `~/.claude/CLAUDE.md`): set `model` per Agent dispatch; sonnet for T2 audits, never inherit Opus.
- Verify-first: agent and memory claims have been wrong repeatedly this branch — confirm file:line / rule text before acting.
- cwd-leak into agent worktrees is recurring — `cd` to main worktree and confirm `pwd` before git ops.

## Wave close checklist

1. Cherry-pick agent commits from the main worktree (check cwd).
2. pytest sweep + N=40 eval (`PYTHONHASHSEED=0`, `--use-archetype`).
3. Per-faction diff vs prior eval JSON.
4. Archive oldest wave-close block to `AUTO_LOOP_LOG_archive.md` (keep ~3).
5. Write new wave-close block at top of `AUTO_LOOP_LOG.md`.
6. Update this file with new headline + next levers.
7. `python scripts/loop_cleanup.py`.
8. Commit + push (push only on explicit user "go").
