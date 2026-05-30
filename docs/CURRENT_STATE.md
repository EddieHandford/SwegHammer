# SwegHammer calibration — current state

**Last updated:** Wave 63 close (2026-05-30), top fix commit `96fd68e`
(docs/close commit on top).

**Status:** Headline gated MAE now **9.27** (was 10.71 five waves ago). Wave 61
was the breakthrough (systemic AI fall-back fix, -1.35). Wave 62 removed the
Custodes AURIC_CHAMPIONS fabrication; wave 63 fixed World Eaters Blood Tithe
over-accrual (per-model → per-unit, -0.12). Both later waves clean and rules-
correct. Strong queue of follow-ups below.

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
| **Wave 63 close (`96fd68e`+docs)** | **12.80** | **9.27** | **2/22** |

The headline sat at 10.5-10.9 for 12 waves, then dropped 1.35 in one wave.
The lever was **AI piloting**, not rules or stats — the strategist review's
thesis (AI mis-piloting is a dominant cross-faction error source) is now
empirically confirmed.

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

## Next ranked levers for wave 64

The clean rules-correct + MAE-positive wins are now largely captured. Remaining
non-structural work is lower-value or has a correctness/metric tension:

1. **Detachment citation/comment fixes + Grey Knights deep-strike gate**
   (task #10) — low-risk rules-hygiene, roughly headline-neutral.
2. **Necrons detachment fabrications** (task #9) — rules-correct but
   MAE-negative (Necrons under-shoots); fixing fabrications here worsens the
   headline. Handle with care / pair with compensating work.
3. **TOWERING line-of-sight + cover** (task #3) — ambiguous direction; measure.

Done: WE Blood Tithe (wave 63, gated 6.01→4.46); AURIC_CHAMPIONS (wave 62).
The CSM under-shoot from the wave-61 gate is matchup-driven, not a clean fix
(the rejected wounded-fallback gate confirmed a faction-neutral gate over-
corrects the horde factions).

## Structural track (owns the remaining headline)

- **Chaos Knights -37.8 gated** — now the single largest residual. The
  fall-back gate helped Imperial Knights far more (CK is War-Dog/Armiger
  heavy, fewer TITANIC chassis). Needs its own diagnostic.
- **Drukhari +37.0** — squad-level activation-count grouping. T3.
- **Strategy roadmap #1 (the big lever, task #6 review)** — a plan-level
  objective function: estimate each side's next-turn reachable Objective
  Control per marker and feed it into intent + activation order. The
  strategist argues this is the highest-leverage change for the WHOLE
  calibration (replaces ~15 per-faction heuristic patches with one
  principled term). Wave 61 proved an AI fix can move many factions at
  once — this is the next, bigger one. Structural / high cost.

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
