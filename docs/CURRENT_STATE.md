# SwegHammer calibration — current state

**Last updated:** Wave 59 close (2026-05-29), top commit `f1c2825`

**Status:** Session paused intentionally by the user for structural work in
another agent. **Read the "Handoff context" section below before resuming.**

This file is the fast-pickup point for any new orchestrator session
continuing the auto-loop. Read this first; everything else is context.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

Session-scoped `/goal` directive. May need re-applying mentally if stop
hooks didn't survive across the session boundary. Drive gated MAE down via
rule-correct fixes, keeping rule correctness primary per CLAUDE.md §3 / §10.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Branch start (wave 48 close, `d82fb5d`) | 14.22 | 10.83 | 4/22 |
| Wave 58 close (`f1d8aaf`) | 14.38 | 10.82 | 4/22 |
| **Wave 59 close (`f1c2825`)** | **14.28** | **10.73** | **4/22** |

Headline has trended 10.5-10.9 across 11 waves; per-faction wins
compound. The per-model amplification pattern catalogue stands at **7
instances across 6 factions, -17.59 wr-points total** (memory entry
`[[project-one-unit-per-model-amplification]]`).

## Handoff context — wave 59 close

Wave 59 closed cleanly. Aeldari Battle Focus VEHICLE-gate fix moved
**-5.23 wr-points** (the biggest single-wave faction win since SOROR-V1
wave 51). AdMech Kataphron Destroyers fix landed but moved +1.54 wrong
direction at full-matrix N=40 — N=20 sample missed matchup asymmetry.

Sororitas agent was killed mid-investigation. Its interrupted trace
surfaced a Stage 2 finding: Morvenn Vahl at 185pt produces 16.9 avg
damage per battle vs Exorcist at 210pt producing 6.7 — likely a points
pricing issue, not a simulator bug. **Park for Stage 2.**

The user is pausing this session to do structural work in another
agent. Likely candidates for that work:

- **Drukhari activation count structural** (the largest residual,
  +36.53; squad-level activation grouping; T3 architecture).
- **Stage 2 multi-profile weapon mapper** (IK -36.83 / CK -43.69
  mapper-locked).

After structural work lands, resume from wave 60 with the
non-structural carry-forwards below.

## Next 3 ranked levers for wave 60 (non-structural)

If continuing wave-by-wave audits in parallel with the structural work:

1. **Marines +13.00** — Hellblasters fixed. Verify top damage
   contributors past them: Eradicators, Heavy Intercessors,
   Bladeguard Veterans. Per Wahapedia. Same shape as MARINES-AUDIT-V1
   (look for mapper substring matches like the `incinerator` → torrent
   fab).
2. **TSON +20.64** — Magnus / Ahriman leader-aura magnitudes. Last
   audited wave 53 / 58. Top contributor in archetype: Rubric Marines.
3. **Daemons -16.40** — stratagem dispatcher firing instrumentation.
   Wave-53 added 9 stratagems but didn't move metric; verify they're
   actually firing.

Lower priority but viable:
4. **Per-model amplification sweep**: DG Plague Companies, GSC Cult
   Ambush, Custodes Ka'tah remaining.
5. **Votann +18.08** — Hearthkyn weapon profile re-verify post pistol-
   basket ripple.
6. **AdMech +16.91** — Belisarius Cawl or Hastarii Fusiliers per agent.

## Patterns / lessons that pay off

Per `[[project-one-unit-per-model-amplification]]` memory:

- The pattern has 7 confirmed instances. Standard fix:
  `Army._<rule>_squad_names_used_this_round: set` + dedupe by
  `profile.name` + reset hook.
- Agent prediction discipline: require **N=20 archetype eval delta**
  as prediction basis, not random_fill DPP. Direction-correct ~70% of
  the time; magnitude unreliable. Treat as wide bounds.
- Mapper structural fixes (wave 48 invuln Shape 3, wave 52 extra_melee
  _profiles, wave 56 hetero-squad weighting, wave 57 pistol-basket)
  retire override sweeps but have wide cross-faction ripple.
- Stratagem and detachment-flag fixes typically sub-noise at N=40.
  Direct stat / weapon-profile fixes on archetype-build dominant
  damage contributors are more reliable.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go" — user has authorized push at each wave close in this session.
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
