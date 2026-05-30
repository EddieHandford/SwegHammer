# SwegHammer calibration — current state

**Last updated:** Wave 60 close (2026-05-30), top fix commit `e1f3f53`
(docs/close commit on top).

**Status:** Wave 60 closed cleanly. Citation backlog cleared and the
citation guard is now enforcing. Ready to continue wave-by-wave from
wave 61, or pivot to the structural track.

This file is the fast-pickup point for any new orchestrator session
continuing the auto-loop. Read this first; everything else is context.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

Drive gated MAE down via rule-correct fixes, keeping rule correctness
primary per CLAUDE.md §3 / §10.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 58 close (`f1d8aaf`) | 14.38 | 10.82 | 4/22 |
| Wave 59 close (`f1c2825`) | 14.28 | 10.73 | 3/22 |
| **Wave 60 close (`e1f3f53`+docs)** | **14.27** | **10.71** | **2/22** |

Headline has trended 10.5-10.9 across 12 waves. The non-structural
levers reliably move their target faction sub-noise but cannot move the
headline while three structural residuals dominate it: **Chaos Knights
-43.7, Imperial Knights -37.0, Drukhari +37.0**. Closing the headline
needs the structural track, not more wave-by-wave audits.

## Handoff context — wave 60 close

Wave 60 ran three parallel rule-correctness audits. All three found real
bugs and moved their faction in the correct direction (combined -2.03
faction gated error), but each was sub-noise at the headline:

- **MARINES-AUDIT-V2** (`d057c3c`): Aggressor Squad Flamestorm-Gauntlets
  torrent fab → Auto Boltstorm Gauntlets. Marines gated 10.84→10.00.
- **TSON-AURA-V2** (`1f1b3c5`): Ahriman/Infernal Master/Sorcerer in Term.
  Armour hit-reroll leaked into melee → new `reroll_hit_ones_shooting_only`
  field. TSON gated 11.88→11.41.
- **DAEMONS-STRAT-INSTRUMENT-V1** (`e1f3f53`): 4 shared Daemonic Incursion
  stratagems missing from all 4 god sub-detachments → added. Daemons gated
  13.24→12.52.

Two process items also landed this session (before the wave):
- Citation backlog cleared (`32e11aa`): audit 278/278, exit 0;
  `BLOCK_ON_MISSING_CITATIONS=True` (guard enforcing, machine-local in
  gitignored `.claude/hooks/`).
- **Eval gotcha**: always run `PYTHONHASHSEED=0 python -m
  scripts.evaluate_vs_meta ...` — the script's `os.execvpe` re-exec
  segfaults on this Windows box otherwise. Memory
  `project-eval-pythonhashseed-segfault`.

## Next 3 ranked levers for wave 61 (non-structural)

1. **Marines +12.2** — still top non-structural over-shooter. Past
   Aggressors (Eradicators clean): audit Sternguard, Devastators, Marine
   vehicle ranged profiles for mapper loadout fabs. Per Wahapedia.
2. **TSON +20.2** — melee-leak fix was small; overshoot is broader. Next:
   Rubric Marines durability (All Is Dust) or Cabal ritual magnitudes.
3. **Votann +18.8 / AdMech +16.8** — untouched this wave, cleanest
   mid-size over-shooters. Weapon-profile audits on archetype contributors
   (Votann Hearthkyn post pistol-basket; AdMech Cawl / Hastarii Fusiliers).

## Structural track (separate from wave-by-wave; owns the headline)

- **Drukhari +37.0** — squad-level activation-count grouping. T3 architecture.
- **Imperial Knights -37.0 / Chaos Knights -43.7** — Stage 2 multi-profile
  weapon mapper (BSData mapper captures only 2 ranged profiles).

These three are ~half the total gated MAE between them; until they move,
wave-by-wave audits will keep landing sub-noise at the headline even when
each is individually rule-correct.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go".
- Per CLAUDE.md §10: every rule fix needs a verifiable Wahapedia / BSData citation. The citation audit is now ENFORCING on commit (no missing/malformed citations on rule-bearing files).
- Per global `~/.claude/CLAUDE.md` (model tiering): Agent dispatches set `model="sonnet"` for T2 audit work, never inherit Opus.
- Per global `~/.claude/CLAUDE.md` (parallelise): default to 3 parallel agents per wave when fixes are file-disjoint.
- Per `feedback-loop-uses-archetype-eval`: eval calibration uses `--use-archetype`, not random_fill.
- **Always** prefix the eval with `PYTHONHASHSEED=0` and use the `-m scripts.evaluate_vs_meta` module form (segfault workaround).
- cwd-leak into agent worktrees after parallel dispatch is recurring — `cd` back to the main worktree and confirm `pwd` before any `git` op.

## Wave close checklist

1. Cherry-pick agent commits to `claude/sim-calibration-6` from the main worktree (check cwd).
2. Run full pytest sweep + N=40 eval (`PYTHONHASHSEED=0`, `--use-archetype`).
3. Compute per-faction diff vs prior eval JSON.
4. Archive oldest wave-close block from `docs/AUTO_LOOP_LOG.md` to `docs/AUTO_LOOP_LOG_archive.md` (keep ~3 recent visible).
5. Write new wave-close block at top of `AUTO_LOOP_LOG.md`.
6. Update this file (CURRENT_STATE.md) with the new headline + next 3 levers.
7. `python scripts/loop_cleanup.py` (opt-in cleanup).
8. Commit + push (push only on explicit user "go").
9. Dispatch next wave's agents.
