# Band-program plan — closing the remaining mean absolute error on the squad frame

**Frame:** post-random-fill-re-base, gated mean absolute error 7.05 (squads-on default, wave 219).
**Goal:** drive per-faction noise-gated mean absolute error toward the ≤ 2 point target.
Prepared 2026-06-09, then **re-grounded against the code 2026-06-09** after the worker's cross-check
showed the first draft's "missing mechanic" premises were false (see §2). **The mechanics are
largely already built; the residual is the fidelity / artificial-intelligence-piloting / tuning of
existing mechanics, not missing builds.** This is therefore a *diagnose-first* program.

## 1. The diagnosis (grounded)

Per-faction residual on the new frame, largest first (sim minus real, points):

| Over-rated (sim too high) | | Under-rated (sim too low) | |
|---|---|---|---|
| Imperial Knights | +17.0 | Chaos Daemons | −21.0 |
| Adeptus Custodes | +15.4 | Genestealer Cults | −20.5 |
| Adeptus Astartes | +14.2 | Astra Militarum | −14.1 |
| T'au Empire | +12.7 | Chaos Space Marines | −12.8 |
| Death Guard | +11.2 | Adepta Sororitas | −11.9 |
| Emperor's Children | +11.1 | Tyranids | −11.0 |

The structure is a single systemic bias: the simulator rewards killing, durability, and
objective-control-by-unit-count, and under-rewards the "soft" win conditions. **But the key soft
mechanics already exist in the simulator** — battle-shock (`_run_battleshock_phase`,
Objective-Control→0, action-ineligibility, Mob Rule / Synapse / Shadow-in-the-Warp), reserves /
deep strike / Cult Ambush resurrection (`_reserves`, `decide_deepstrike_drops`,
`cult_ambush_resurgence`), and the action / secondary economy (`_unit_can_perform_action`,
Cleanse / Sabotage / Burn). So the under-pole factions under-perform *despite* having their key
mechanics implemented — meaning the residual lives in **how well those mechanics are tuned and
piloted**, not in their absence.

**The cross-faction lever:** the matchup matrix is closed, so **raising the under-pole automatically
lowers the over-pole.** Drive from the under-pole; never a direct elite nerf (forbidden knob).

## 2. Lesson — ground "what's missing" in the CODE, not the research

The first draft followed a research agent and named "missing mechanics" as the levers. The agent
over-claimed **three times**, each refuted against the code:
1. "Vehicle / Monster / Titanic units cannot perform Actions" — false (only AIRCRAFT are barred;
   verified vs Chapter Approved 2025-26). Our sim was already faithful.
2. "Battle-shock appears missing" — false; `_run_battleshock_phase` is built and cited.
3. "Reserves / deep-strike missing" — false; `_reserves` / deep strike / Cult Ambush are built.

**Standing rule:** external research is for the *why* (real-world win conditions), never for *what is
missing in our sim*. Every "missing mechanic" claim is cross-checked against the code before any
build. (The worker's cross-check rail caught all three; the watchdog must apply the same rail to its
own plans — and not rely on a head-limited grep.)

## 3. Cross-faction discipline
1. One structural change per wave, then re-read the *full* matrix (matchup-scoping for genuinely
   single-faction changes; full re-anchor for matrix-wide ones).
2. Read the per-faction delta **and** matchup variance, not just the headline.
3. Viable-options test after each change (the re-base helped several factions but over-corrected
   Tyranids to under — watch for that).
4. Accept temporary regressions when adding faithful fidelity; unwind frozen-under offsets.
5. Stop at equilibrium-fidelity (mean absolute error ≤ 2), not perfect per-event fidelity.

## 4. The program — diagnose, then targeted-fix (ranked by residual size)

For each residual: run a **scoped diagnostic** (now cheap — `evaluate_vs_meta --factions "<faction>"`
on the squad frame, plus board-state / replay inspection) to localize the gap in the *existing*
mechanic, then apply a targeted faithful fix. The gap is usually one of: (a) the
artificial-intelligence player not exploiting a built mechanic (e.g. not deep-striking onto
objectives, not using ambush bodies to score, not spending a resource optimally — the standing
[[project-ai-piloting-top-lever]] pattern); (b) a tuning value off (arrival timing, aura range,
weighting); (c) a genuinely-absent *sub*-mechanic — but verify that against the code first.

1. **Chaos Daemons (−21) + Genestealer Cults (−20.5) — the two biggest residuals, both with deep
   strike / ambush already ON.** Scoped diagnostic first: why do they lose *with* their tempo
   mechanics implemented? Candidate gaps to localize: arrival artificial-intelligence not grabbing /
   contesting objectives on landing; reserves held too long; ambush bodies not directed at
   action-secondaries; a genuinely-absent sub-mechanic (e.g. Daemons' Corrupt Realspace
   objective-lock — verify). Fix the localized gap, not the whole mechanic.
2. **Imperial Knights (+17) — over-pole, fresh on the squad frame.** The collision win was partly
   undone by the re-base. Scoped diagnostic: why is the Knight over-rated against *real opponent
   squads*? (Opponent squads less able to concentrate fire / coherency-bunched? objective-reach?)
   The over-pole's residual is the known positional / objective-control-reach representation gap
   ([[project-oc-contest-faithful]]); re-measure it on the squad frame. Expect Priority-1 under-pole
   wins to pull this down via the matrix — track that before any direct work.
3. **Adepta Sororitas (−11.9), Chaos Space Marines (−12.8), Astra Militarum (−14.1).** Sororitas:
   verify whether Miracle Dice are modelled; if not, that is a genuine build (variance suppression).
   Chaos Space Marines: finish the per-unit Dark Pact abilities (Veterans landed; verify which
   remain) — single-faction, so matchup-scoping applies. Astra Militarum: scoped diagnostic (orders /
   indirect-fire / chaff-action fidelity).
4. **Tyranids (−11, freshly over-corrected by the re-base) and the remaining over-pole
   (Custodes / Astartes / T'au / Death Guard).** Re-measure after Priorities 1–2; much should move via
   the matrix.

## 5. Sequencing
Diagnose-first, biggest residual first: scoped Daemons + Genestealer Cults diagnostic → targeted fix →
re-measure (scoped if single-faction, full re-anchor if matrix-wide) → next residual. Each under-pole
fix is expected to trim the over-pole as a side effect; track that rather than nerfing the elites.

## 6. Sources
Residual table: `data/_fillsquads_on_n80_log.json` vs the Warp Friends target. Game-balance
methodology + 10th-edition win-conditions (for the *why* only): Goonhammer faction focuses; Stat
Check; Chapter Approved 2025-26 (Wahapedia); Riot / Stardock / Empirical Game-Theoretic Analysis /
Sirlin. Full URL list in the oversight log. **Mechanic-existence claims are grounded in the code, not
these sources.**
