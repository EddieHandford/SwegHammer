# SwegHammer decision ledger — what's been tried (READ THIS before proposing a lever)

**Purpose.** The compact, routinely-read index of what has already been **landed**,
**reverted**, **parked**, or **ruled out**, so neither the worker nor the watchdog
burns a wave (or tokens) re-attempting something already settled. One line per item.

**This file is the index, not the story.** Full narrative detail lives in the archives
(`docs/AUTO_LOOP_LOG_archive.md`, `docs/CURRENT_STATE_archive.md`, `LOOP_QA_ARCHIVE.md`)
and the auto-memory. The live `docs/CURRENT_STATE.md` head holds the current frame + next
levers; this ledger holds the long memory.

**Update rule.** Add exactly one line when a mechanic **lands**, is **reverted**, or is
**parked** — newest-last within each section. Do not narrate here; that is the archives'
job. If you are about to propose a lever, check the Reverted / Parked / Forbidden sections
first.

---

## LANDED (kept; gate flag default-on unless noted)
- Collision + no-overlap + ruin-walls-block-non-`INFANTRY` + pathfind-around — `SWEG_COLLISION` / `SWEG_PATHFIND` / `SWEG_OCCGRID`, wave 211. Fixed the Imperial Knights over-pole representation root (72.8 → 49.4 %, in band). See [[project-physical-board-control-avenue2]].
- Per-attack-type conditional invulnerable saves — `SWEG_COND_INVULN`, wave 217 (Task #92). Wyches 4+ melee / 6+ ranged, Ion Shield ranged-only. KEEP on fidelity-first; metric-neutral. See [[project-conditional-invuln-single-value-gap]].
- Chaos Space Marines Legionaries "Veterans of the Long War" — `SWEG_VETERANS`, wave 217.
- Chaos Space Marines leader host-routing fix — `SWEG_CSM_LEADERS`, wave 213 (Dark Apostle / Sorcerer route to the Legionaries / Chosen core).
- T'au Commander "Coordinated Fire Plan" fabrication REMOVED — wave 212 (deleted a fabricated army-wide +1 to Hit).
- Chapter Approved 2025-26 mission deck re-alignment — waves 91-92 (the deck the May-2026 target used). See [[project-mission-deck-ca-2025]].
- Damaged-bracket −1-to-Hit generalised to all 260 big models — wave 191.
- Balanced objective-contest AI + free-contest extension — waves 192-193 (first faithful levers to move the over-pole down).
- Rolling damage (replaced expected-value) — user-approved. See [[project-core-rules-audit-2026-06]].
- Squad-activation damage-allocation spillover — wave 65 (gated 9.27 → 7.78). See [[project-squad-activation-contained-wash]].
- Fall-Back mis-pilot fix — wave 61 (gated MAE −1.35 across many factions). See [[project-ai-piloting-top-lever]].
- Daemonic Manifestation (friendly Shadow of Chaos) — wave 88. Built + cited but METRIC-NEUTRAL; kept as fidelity, does NOT explain the Daemons residual. See [[project-daemons-manifestation-missing]].
- Paired / Common-Random-Numbers eval mode (core) — wave 218 (`adf9140`, `--log-games` + `scripts/paired_delta.py`). Watchdog-verified correct (McNemar estimator, additive). See [[feedback-paired-crn-low-n-ab]].

## REVERTED / REJECTED (tried, made it worse or proven wrong — do NOT re-attempt)
- Dark Pacts coverage experiment — wave 209, REVERTED. The Chaos Space Marines under-output is NOT Dark-Pacts-coverage.
- Candidate A clustering-geometry positional fix — wave 94, REGRESSED 4.15 → 4.30 (helped over-shooters that already hold markers, not Imperial Knights / Daemons), reverted. See [[project-matchup-fidelity-diagnosis]].
- Squad-activation contained decision-overlay — wave 64-65, WASH (9.27 → 9.30); only the spillover half landed. See [[project-squad-activation-contained-wash]].
- Threat-priority targeting alone — wave 189, wrong-direction (Imperial Knights 25.52 → 28.21); the over-pole is compound.
- Anti-tank strength / squad-size maxing — wave 190, made Imperial Knights WORSE; the "kill the Knight harder" axis is exhausted.
- Fab band-aid on thin archetypes — dropping fabrications from under-performers WORSENS mean absolute error (they were compensating for archetype thinness). See [[project-fab-bandaid-on-thin-archetypes]].
- Primary-mission rotation as the over-pole lever — wave 187, REFUTED.

## PARKED (not pursued now; needs NEW information to reopen — the line says what would reopen it)
- Candidate B AI massing body-armies onto markers (`SWEG_MASS`) — expected wash; if it washes, report as a one-Unit-per-model representation limit and STOP chasing it (no knob/nerf). See [[project-matchup-fidelity-diagnosis]].
- Imperial Knights / Daemons positional residual — likely a one-Unit-per-model representation limit; reopen only with a representation change, never a knob. See [[project-oc-contest-faithful]].
- Stage 2 (equation fit) outputs — provisional until Stage 1 converges; `calibrated_points` / `equilibrium_points` are redo-able, do not treat as final.
- Chaos Lord "Chance for Glory" — the real rule is a once-per-battle self buff, NOT a +1-to-wound aura; current flag is a fabrication firing on nothing. Do NOT route it onto a squad until the effect is corrected.
- Dice-roll vectorization (numpy-batch the per-attack `random.randint` loop, `units.py:3485`) — 2-4× per-game, but it BREAKS determinism and invalidates every Common-Random-Numbers anchor log; reopen only if eval speed becomes a permanent hard constraint that the cheaper levers can't meet.
- PyPy / alternate runtime (the "Rust/faster runtime" angle) — 2-5× theoretical on the pure-Python hot path, but unproven Windows-spawn + dataclasses compatibility needs a real shakedown; the structural "big bet", deferred until the cheaper throughput levers are exhausted.

## FORBIDDEN (user-ruled out of bounds — never propose)
- Re-fitting stats / overrides / lists to force win rates — metric-tuning, poisons Stage 2; the win-rate gap is sim-fidelity, not stats. See [[project-winrate-gap-is-sim-fidelity-not-stats]].
- Make-way / horde-AI-nerf to free Knights through walls — the walls are a faithful horde strategy; fix faithfully (friendly pass-through, pathfind-around). See [[project-physical-board-control-avenue2]].
- Gating a faithful 10e mechanic OFF to protect the metric — fidelity-first; a rising headline is expected + authorised. See [[project-fidelity-first-rebuild-authorized]].
- The "re-calibration" conclusion (declaring the sim done by re-fitting to the target) — killed by user ruling.

## OPEN LEVERS (ranked; the live to-do — authority for ordering is the `docs/CURRENT_STATE.md` head)
1. **Throughput tooling.** Wave-218 suite (paired / Common-Random-Numbers delta, sequential early-stop, regression sentinel, gated caches, robust wrapper) — LANDED + watchdog-verified, shipped in pull request #64. **NEXT (user-approved 2026-06-09):** matchup-scoping (a `--factions` filter that runs only a changed faction's row + column — ~42 of 462 cells — and merges against a full saved anchor; about 10× on single-faction band waves, composes with the paired method) plus two trivial infra tweaks (a worker-count override flag, and chunksize 8 → 50-100). Full buildable spec is in `LOOP_QA.md`. See [[feedback-paired-crn-low-n-ab]].
2. **Random-fill re-base (greenlit).** `_random_fill` `add_unit`-loop → `add_squad(chosen, size)`, gated `SWEG_FILL_SQUADS`, N=80 A/B (big re-base, low Common-Random-Numbers benefit), then re-verify collision + the band levers on the corrected frame. See [[project-one-unit-per-model-amplification]].
3. **Band program (after the speed tooling lands).** More Chaos Space Marines Dark Pact abilities (Terminators "Despoilers", Possessed "Unholy Bloodshed"), advance-to-score AI, the durability under-pole cluster, the Aeldari Farseer once-per-phase fix-to-6, the Chaos Space Marines Dark Apostle +1-to-wound-melee.
