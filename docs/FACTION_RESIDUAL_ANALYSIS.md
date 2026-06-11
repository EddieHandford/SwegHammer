# Why specific factions over/under-shoot — root-cause analysis (2026-05-30)

A read-only diagnostic: per-faction sim residuals (from past N=40 eval snapshots) +
the sim's own 64-wave attributions, cross-referenced with real-world tournament
win rates and faction mechanics (web research, sources below). **No simulations
were run for this analysis.** Baseline = wave 64 (`09c5e9f`), gated MAE 9.27.

## The residuals (wave 64, sorted by |gated|)

| Faction | sim% | target% | residual | persistence (wave1→64) |
|---|---:|---:|---:|---|
| Chaos Knights | 6.2 | 47.5 | **−41** | ~3-7%, stuck/worsening |
| Drukhari | 85.5 | 49.3 | **+36** | 85→85, rock-stable |
| Imperial Knights | 21.4 | 48.5 | −27 | 18→21, stuck |
| Thousand Sons | 73.6 | 54.6 | +19 | 75→74, stuck |
| Tyranids | 64.2 | 47.4 | +17 | 74→64, partly responsive |
| Chaos Daemons | 38.1 | 50.8 | −13 | 32→38, stuck |
| Votann +13, Aeldari +13, Orks +12, Sororitas +12, AdMech +12, T'au +11 | | | | over |

The real-world targets are corroborated by 2026 tournament data (Warp Friends
weekly aggregates, ~10k games): IK 47.2%, CK 47.4%, Drukhari ~45-49%, Tyranids
~45-48%, TSON ~55%, Daemons ~51%. **These residuals survived 64 waves of
stat/rule tuning — they are structural, not tuning-fixable.**

## Two structural root causes (the dominant story)

### 1. One-Unit-per-model activation representation
The sim represents each model as its own Unit, so a 2000pt army gets one
activation **per model**: Drukhari ~69, Tyranids ~91, vs Knights 9-10. Per round,
a horde acts 7-9× more often than a low-model elite army.

- **Over-rates high-model armies** (Drukhari +36, Tyranids +17, Orks +12, AdMech)
  — they get far more activations than a real game (where a *unit/squad* activates
  once), and the sim runs fragile T3 bodies as full damage contributors. In real
  tournaments these armies are **mid-tier (~45-49%) precisely because they're
  fragile** — "die in droves," focus-fired off the board, no objective staying
  power. The sim never makes them pay that fragility tax at the right rate.
- **Under-rates low-model armies** (Chaos Knights −41, Imperial Knights −27) —
  they finish their ~10 activations early and the opponent gets dozens of "free"
  activations. The sim's own logs parked this as "Drukhari activation count
  structural (T3)" and "Knights board-control rebalance" in **every** wave.

### 2. Kill-centric scoring, not VP / objective / positional
Real 40k is won on **mission VP**, not kills. The sim rewards damage/kills and
under-weights the positional game:

- **Knights** win at 47% via **high-OC durable presence**: an Armiger is OC 8, a
  Questoris OC 10; they hold/sticky objectives and impose a "threat tax" (a Knight
  sitting un-engaged on an objective scores 3-5 VP/round while the opponent wastes
  fire on a 22-wound target). A kill-centric sim sees Knights killing fewer units
  and soaking fire → reads it as losing.
- **Chaos Daemons** (−13, *under* despite being a horde — breaks the model-count
  pattern) win via **deepstrike pressure** (Denizens of the Warp 3" deep strike,
  Realm of Chaos repositioning) + Shadow-of-Chaos board control + objective play —
  positional win-cons the sim's static/kill-centric model under-credits.
  **Verified:** their invuln saves ARE applied (68 override entries) and Shadow of
  Chaos IS modeled, so it is NOT a missing-mechanic bug — it's the same positional
  blindness as Knights, which is why a horde faction *under*-shoots.

## Faction-mechanic cases (the off-pattern over-shooters)

- **Thousand Sons +19** — elite/low-model, so NOT activation-count. The **Cabal of
  Sorcerers** rituals (Doombolt mortal wounds, Twist-of-Fate AP) fire **every
  Shooting phase with none of the real-world failure modes**: the psyker is never
  sniped/out-of-range, rituals fire regardless of positioning, no game-realistic
  attempt cadence. In reality Doombolt lands ~2-3×/game, not 5. **Verified:** All
  Is Dust is correctly gated (D1 + RUBRICAE only), so the over-model is the
  unconstrained ritual engine, matching the sim's "Cabal point-generation rate"
  attribution. This one is partly tunable (gate rituals on psyker survival/range).

## What this means for MAE

The bulk of the headline (Chaos Knights, Imperial Knights, Drukhari, Tyranids =
~half the gated MAE) is driven by root causes **1 and 2** — the per-model
activation representation and the kill-centric scoring model. **No amount of
per-unit stat tuning will move them** (the `overrides.json` data is already
rule-correct — see `project-calibration-surface`). The genuine levers are:

1. **Squad-level activation grouping** — activate a codex *unit* once, not per
   model. Directly attacks the high-vs-low-model imbalance (Drukhari/Tyranids down,
   Knights up) — potentially the largest single MAE move available. T3 structural.
2. **VP/objective-aware play + scoring** — the plan-level objective function (model
   the threat-tax, sticky objectives, deepstrike pressure, screening) so durable
   low-model and positional armies (Knights, Daemons) get credit for how they
   actually win. Structural (#12).
3. **Per-faction-mechanic approximations** (smaller, MAE-down on over-shooters):
   gate the TSON Cabal rituals on psyker survival/range/cadence.

Caveat (see `project-ai-frozen-under-mae-first`): the current 9.27 is fitted
around the present AI + representation. Structural fixes 1-2 will shift many
matchups at once and likely need a re-fit of the archetype lists afterward.

## Sources
Warp Friends weekly meta aggregates (Dec 2025 – May 2026); Goonhammer Competitive
Faction Focus + Hammer of Math (Knights, Drukhari, Tyranids, Thousand Sons, Chaos
Daemons); Goonhammer Q3/Q4 2025 balance updates; Stat Check / Spikey Bits meta
tiers; tournament reports (Cherokee Open, Gothcon, World Championships). Full URLs
in the session research transcripts.

## Chaos Space Marines re-diagnosis (wave 238, frame `0550475`, anchor gated 5.83)

Read-only diagnostic over the 36,960-game anchor log (toolbox sections 7, 4, 6
consulted; 1, 2, 3, 5 skipped as requiring new runs). Findings, evidence-ranked:

1. **The deficit is uniform across all 21 opponents** (worst five 22.5-28.7%,
   best three 49-58%, no single matchup carrying it) - the signature of an
   army-construction problem, not an isolated missing mechanic.
2. **Roughly half the deficit is Chaos-Space-Marines-specific**: 14-18-point
   shortfalls persist against at-or-below-50% opponents (Drukhari 31.2%,
   Leagues of Votann 35.0%, Chaos Daemons 33.8%), which opponent over-rating
   cannot explain (correlation with opponent inflation r = -0.715 covers only
   the other half).
3. **The archetype is the FX-ALL coverage stub, never tuned**: 21 unit types,
   all count=1 except Legionaries - the 0.3 seed walk places two squads then
   random-fills from 18 leftover types, building a different incoherent army
   every game. The Chaos Daemons conversion from the same stub class to tight
   mono-god templates moved that faction -9.7 to -0.4.
4. **Dark Pacts is verified correctly implemented** (wave-209 expansion testing
   confirmed every broadening variant worsens it) and the defender-allocation
   frame shift contributed only -1.3 (noise-level).

**Named lever (wave 239):** reshape the archetype to the real May 2026
Pactbound Zealots backbone (Abaddon warlord anchor, three Legionaries squads,
Obliterators count=2, Forgefiend, attached characters; about 9-11 types) -
data-layer only, sourced from the real meta, same class as the adopted Daemons
and list-realism passes. Expected direction +8 to +15 toward target.

**Instrumentation gap logged:** the game log carries only faction/seed/winner;
a `units_a`/`units_b` roster field and a per-unit alive-on-marker end-state
flag in `_write_game_log` would let future positional diagnostics partition by
built army without re-running battles.
