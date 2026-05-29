# SwegHammer calibration — current state

**Last updated:** Wave 58 close (2026-05-29), top commit `74f06ac`

This file is the fast-pickup point for any new orchestrator session
continuing the auto-loop. Read this first; everything else is context.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

This is a session-scoped `/goal` directive. If a stop hook is no
longer active (e.g. after a usage-limit auto-cut + resume), re-apply
the goal mentally: drive gated MAE down via rule-correct fixes,
keeping rule correctness primary per CLAUDE.md §3 / §10.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Branch start (wave 48 close, `d82fb5d`) | 14.22 | 10.83 | 4/22 |
| Wave 57 close (`0fdacd8`) | 14.33 | 10.84 | 4/22 |
| Wave 58 close (`74f06ac`) | 14.38 | **10.82** | 4/22 |

Headline has been flat in the 10.5-10.9 range for ~10 waves, but
**per-faction wins compound**. The per-model amplification pattern
catalogue has 7 instances across 6 factions moving -17.59 wr-points
total (-16.99 from SOROR×2 + AM alone).

## Wave 58 commits landed + measured

| Commit | Faction | Predicted N=40 | Measured N=40 |
|---|---|---|---|
| `4eb490d` Marines plasma-Torrent fix | Adeptus Astartes | -10ish | **-2.14** |
| `b26c181` Aeldari Strands hit+save gate | Aeldari | -0.7 | +0.11 |
| `74f06ac` TSON Cabal-gen cap | Thousand Sons | negligible | -0.12 |

Wave 58 is closed and pushed. Continue with wave 59 dispatch.

## Next 3 ranked levers (wave 59+)

If continuing fresh: skip to wave 59 dispatch.

1. **Drukhari activation count structural** (T3 architecture) —
   biggest single residual (+36 gated). Direct measurement: 81-90
   Drukhari Unit instances vs 39-53 Marines at 2000pts (1.5-2×
   activation advantage). Fix shape: squad-level activation
   grouping. Multi-day branch.
2. **Cross-faction pistol-basket calibration sweep** — wave 56-57
   mapper fix shifted Marines/Sororitas/Votann/Necrons/Aeldari/DG
   upward (bolter dominance). Some of those are now over-shooting;
   per-faction stat audits on dominant ranged units.
3. **Per-model amplification pattern continues**:
   - DG Plague Companies stratagem cap
   - Custodes — already audited wave 57, clean
   - Necron Awakened Dynasty — already audited wave 57, parked (dead code, needs T3 leader-attachment registry)
   - GSC Cult Ambush ritual
   - Other "once per phase per officer/character" rules

## Patterns / lessons that pay off

Per `[[project-one-unit-per-model-amplification]]` memory:

- The pattern has 7 confirmed instances. Standard fix: `Army._<rule>_squad_names_used_this_round: set` + dedupe by `profile.name` + reset hook.
- Agent prediction discipline: require N=20 archetype eval delta as prediction basis, not random_fill DPP. Holds reliably.
- Mapper structural fixes (wave 48 invuln Shape 3, wave 52 extra_melee_profiles, wave 56 hetero-squad weighting) retire entire override sweeps but have wide cross-faction ripple.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go" — except the user has authorized push at each wave close in this session.
- Per CLAUDE.md §10: every rule fix needs verifiable Wahapedia / BSData citation. No fabrications.
- Per `feedback-tiered-model-selection`: Agent dispatches set `model="sonnet"` for T2 audit work, never inherit Opus.
- Per `feedback-parallelism-preference`: default to 3 parallel agents per wave when fixes are file-disjoint.
- Per `feedback-loop-uses-archetype-eval`: eval calibration uses `--use-archetype`, not random_fill.
- Per wave-50 / wave-55 process notes: cwd-leak into agent worktrees after parallel dispatch is recurring — explicitly `cd /c/Users/Jake/Claude/code/SwegHammer && pwd` after agent waits before `git` operations.

## Wave close checklist

Each wave ends with:

1. Cherry-pick agent commits to `claude/sim-calibration-6` from main worktree (check cwd).
2. Run full pytest sweep + N=40 eval (background, ~2 min).
3. Compute per-faction diff vs prior eval.
4. Archive oldest wave close block from `docs/AUTO_LOOP_LOG.md` to `docs/AUTO_LOOP_LOG_archive.md` (keep ~3 most recent visible).
5. Write new wave close block at top of AUTO_LOOP_LOG.md.
6. **Update this file (CURRENT_STATE.md) with the new headline + next 3 levers.**
7. Commit + push.
8. Dispatch next wave's 3 agents.
