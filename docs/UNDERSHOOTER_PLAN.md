# Plan — addressing the remaining under-shooters (2026-06-04)

**Context.** The over-side Group-2 melee has bottomed out: every *direct* combat lever is tried + rejected/neutral
(attacker-count refuted, split-fire neutral, fight-alternation rejected — the once/round melee is a fortunate-
cancellation abstraction; see `OVERSHOOTER_PLAN.md` Phase-2 RESULTS). What remains on the over-side is the big
bounding-fidelity track (user decision) or accepting a representation floor. So we pivot to the **under-side**: smaller
in total (~23 gated vs ~62 over-side) but **cleaner, higher-value-per-effort fidelity work** — under-modelled rules and
under-holding, not an exhausted floor.

**The discipline is identical to the over-side (fidelity-first).** Under-shooters under-perform because the sim is
MISSING fidelity that *helps* them — an under-modelled army rule, an under-holding AI, a fragility/output gap — NOT
because their stats are too low. **NEVER buff a unit's stats to raise a win rate** (forbidden; metric-tuning; poisons
Stage 2). Every fix ADDS a missing faithful mechanic, exactly like the over-side fixes removed/corrected un-faithful ones.

## Current actionable under-shooters (N=80, default baseline)

| Faction | Diff | Gated | Thread |
|---|---|---|---|
| Adeptus Mechanicus | −12.2 | **8.0** | B — structural (biggest, murkiest) |
| Chaos Space Marines | −10.0 | **7.5** | B — under-modelled army rule (Dark Pacts) |
| Necrons | −8.1 | **4.9** | A — under-HOLDER (durable midfield) |
| Astra Militarum | −6.0 | **2.8** | A — under-HOLDER (gunline + screens) |

In-band / resolved (leave them): T'au (−3.9, markerlights fixed it), Daemons (−2.7, faction-bug fix), Aeldari (−1.1 —
its 40% sim ≈ 41.5% real, so it's CALIBRATED, not under-shooting; its low win rate is faithful).

## Two threads, two kinds of fix

**Thread A — under-HOLDERS: Necrons (4.9) + Astra Militarum (2.8) ≈ 7.7 gated.** Durable/gunline armies that LEAVE
PRIMARY VP on the table by not getting onto objectives — the mirror image of the IK over-hold (the user's symmetry
hypothesis). **Stage B coherency CONFIRMED this:** with `SWEG_COHERE` on, Necrons gated 5.13→3.27 (rose as IK fell).
→ **The lever is the COHERENCY FLIP — already BUILT, faithful, and pending the USER's go (the standing Stage-B
decision).** It is the #1 under-side lever: FREE (no new build), faithful (real 10e Unit Coherency), and it closes a
chunk of Necrons + Guard WHILE bringing IK down — both ends from one switch. Re-bases the default 4.05 → 3.93.

**Thread B — under-OUTPUTTERS / structural: AdMech (8.0) + CSM (7.5) ≈ 15.5 gated.** Under-modelled rules + structural
gaps, each its own fix:
- **CSM (7.5) — under-modelled ARMY RULE (Dark Pacts).** Currently broken/under-fired (per-army not per-unit; the
  holistic #52 was re-scoped to multi-wave because the offsetting Marks of Chaos need PER-UNIT MARK-ASSIGNMENT
  infrastructure the catalogue lacks). → Build the mark-assignment data layer, then fix Dark Pacts faithfully (per-unit,
  one keyword [Lethal Hits], on a PASSED Leadership test) + Marks of Chaos (passed-test bonus) + Dark Apostle, TOGETHER
  (the wave-146 isolated Dark-Pacts fix REGRESSED — the synergies must land as one). A clear faithful fix gated on the
  infra. CITE everything (the Dark-Pacts keyword grant is BSData-verified per `feedback-verify-stats-against-bsdata`).
- **AdMech (8.0, the biggest single under-shooter, but the MURKIEST) — STRUCTURAL.** The leader-aura abilities WASHED at
  N=80 (Machine Vengeance was N=40 noise), and Go-To-Ground (now on) did NOT close it at N=80 (still −12.2 GtG-on) — so
  it is NOT primarily fragility or abilities. The gap is deeper. → A DEEP INSTRUMENTED diagnostic (like the IK/Daemons
  probes, numbers before any fix): what does AdMech LOSE on — primary VP? secondary? out-dealt damage? out-positioned?
  Candidates to instrument, not pre-judge: doctrina imperatives (modelled faithfully + impactful?), the archetype list
  (Kastelan Robots / Skitarii / Dunecrawlers — is it the competitive list?), residual infantry-shooting fragility
  beyond GtG, or a mid-model-shooty representation issue. Pin the mechanism BEFORE wiring anything.

## The diagnostic spine — the multi-metric VP review (the user's queued directive)

Extract per-faction **turn-by-turn PRIMARY + SECONDARY victory points + kills** from the sim and compare to real
tournament data. This SEGMENTS the under-shooters definitively and grounds the whole plan:
- **Under-holders (Necrons, Guard)** should show LOW primary VP with normal secondary/kills → confirms Thread A + that
  coherency is the right fix.
- **Under-outputters (AdMech, CSM)** should show low kills/damage-dealt → confirms Thread B + points the AdMech probe.

**Crux: this needs the user's real per-faction VP reference data** (sim-side extraction is buildable now; the
comparison is blocked on the reference). If the user can supply real per-faction primary/secondary splits, run this
FIRST (it grounds + segments everything). If not, proceed on the established segmentation above.

## Phasing

- **Phase 1 — FLIP COHERENCY (Thread A, free + built).** The standing Stage-B decision. Closes part of Necrons + Guard,
  brings IK down, re-bases to 3.93. Just needs the user's go. (Open question for later: is there MORE faithful
  holding-AI beyond coherency? CAUTION — Stage E's aggressive marker-massing was UN-faithful and over-flooded; any
  further holding work must be the faithful "hold correctly" kind, not "hold everywhere.")
- **Phase 2 — CSM Dark Pacts + mark-assignment infra (Thread B).** Build the per-unit mark layer → fix Dark Pacts
  holistically. The clearest faithful under-side fix; bounded by the infra build.
- **Phase 3 — AdMech deep diagnostic (Thread B, biggest + murkiest).** Instrument what it loses on → pin the structural
  gap → faithful fix. Highest single payoff, least certain.
- **Phase 4 — multi-metric VP review** (grounds + confirms; gated on the user's real data) + the smaller residuals
  (the cited unmodelled-ability backlog for any thin archetypes, per the idle-default).

## Rails (non-negotiable)

- **Every fix ADDS missing faithful fidelity** — turn on built mechanics (coherency), fix under-modelled rules (Dark
  Pacts), diagnose + close structural gaps (AdMech). NEVER buff stats or add a per-faction win-rate dial.
- **Watch the over-correct risk:** the holding fixes must be the FAITHFUL coherency (which helped Necrons), NOT the
  aggressive marker-flooding that made Stage E un-faithful. "Hold correctly," not "hold everywhere."
- **A/B + cite each** (N=40→N=80 serial), read the full per-faction table, keep-if-faithful regardless of direction.
- The under-side is smaller (~23 gated) but cleaner — realistic target: coherency (~−0.1 headline + the symmetry) +
  CSM + AdMech could take the default 4.05 toward ~3.3-3.5 with purely faithful fixes.
