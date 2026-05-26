# SwegHammer v1.0 — Recalibrated (alpha)

Math-fitted points for Warhammer 40,000. Every unit in the game priced by a
single regression equation over the stat line, then nudged per faction by
real tournament results.

## Headline numbers

- **1,479 units priced** &mdash; full BSData WH40k 10e v10.6.0 catalogue plus per-unit overrides
- **111 stat features** &mdash; wounds, toughness, save, AP, attacks, damage, hit probability, weapon keywords (precision, lance, assault, heavy, indirect fire, anti-X, ...), secondary weapon profile, leader aura buffs, Necron reanimation, and a handful of cross-stat interaction terms
- **R&sup2; = 0.962** against Games Workshop's printed prices &mdash; the equation explains 96% of GW's pricing variance
- **Mean absolute error = 17 points per model** &mdash; most predictions land within &plusmn;10% of GW

## What's in this release

- [`sweghammer_points.html`](https://github.com/EddieHandford/SwegHammer/releases/download/v1.0.0/sweghammer_points.html) &mdash; single-file playtester reference. Open it in any browser. No install, no dependencies. Contains:
  - The equation in plain language
  - A breakdown of what families of stats drive cost (durability, offense, mobility, special abilities, faction adjustment)
  - A SwegHammer-vs-Games-Workshop scatter plot for every priced unit
  - Methodology + data sources + limitations
  - Searchable, sortable table of all 1,479 priced units
- [`sweg_points_v1.json`](https://github.com/EddieHandford/SwegHammer/releases/download/v1.0.0/sweg_points_v1.json) &mdash; the underlying prices dataset. Per-unit predictions, the fitted coefficients, family-level rollups, and active faction multipliers.

## How it works

1. Every unit&apos;s stat line is read from BSData v10.6.0.
2. A regression equation predicts log(price per model) from those stats.
3. The result is multiplied by a per-faction tournament-meta multiplier (Warp Friends rolling aggregate, May 2026, ~10,000 games). Over-performing factions get marked up; under-performing factions get marked down.
4. Final price is rounded to the nearest 5 points.

See `docs/sweghammer_points.html` &rarr; **How it works** section for the longer version.

## Limitations &amp; known rough edges

This is an **early alpha**. Tell us what feels wrong &mdash; especially:

- **Named characters with bespoke abilities** the equation cannot see (once-per-battle effects, complex psychic powers, stratagem-targeted abilities). Eldrad-style characters will be priced based on their stat line plus their generic leader aura, not their unique flavour.
- **Super-heavies and Apocalypse units** (Titans, Knights, strongpoints). Priced by the same equation as everything else; predictions for these rare profiles carry more uncertainty than mid-tier infantry. We don't fall back to the printed cost &mdash; we want playtesters to be able to field cool stuff at math-fitted prices.
- **Detachment-specific synergies** are not modelled. A unit inside a detachment that loves it may feel undercosted.
- **Unit-vs-unit matchup rock-paper-scissors** is not modelled. The equation prices each unit on average against all opponents.

## How to give feedback

Open an issue on the repository or message the team directly. Useful things to include:

- The unit name and faction
- The SwegHammer price vs the printed Games Workshop price
- Why you think the SwegHammer price is wrong (too cheap / too expensive / wrong relative to a sibling unit)

## What's next

This release is the equation alone, fitted directly to GW prices. Future
releases will integrate the in-house combat simulator: instead of fitting
to GW's prices we'll fit to simulated win rates across the catalogue, so a
unit is priced for what it actually does on the table rather than what GW
happened to charge for it.

## Provenance

- **Stat lines:** BSData WH40k 10e v10.6.0
- **Tournament meta:** Warp Friends May 2026 rolling aggregate (~10,000 games)
- **Source code:** https://github.com/EddieHandford/SwegHammer
- **Methodology paper:** `PROJECT.tex` in the repository

Built 2026-05-26.
