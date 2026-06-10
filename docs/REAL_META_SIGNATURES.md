# Real competitive-meta behavioural signatures (reference values for sim instruments)

Research compiled 2026-06-10 from the Goonhammer "Hammer of Math" statistical series (backed by the
Tabletop Battles app dataset, 9,467–112,503 games per analysis period), Wahapedia rule text, Games
Workshop Metawatch articles, and the Stat Check meta dashboard. Each value is tagged with a
confidence level. This answers the data-availability crux of the standing multi-metric fidelity
directive: which turn-by-turn / game-shape statistics have real-world reference values the sim can
be compared against, and which do not.

## Reference values (use these to calibrate sim instruments)

| # | Signature | Real reference value | Confidence | Sim measurement |
|---|-----------|---------------------|------------|-----------------|
| 1 | Mean primary victory points per player per game | ≈ 29 (Pariah Nexus, n = 9,467); ≈ 22.5 (Leviathan, n = 15,368); Chapter Approved 2025-26 "hasn't changed much" vs Pariah Nexus | HIGH | sum of per-round primary per player |
| 2 | Going-first win rate | ≈ 49–52% under Pariah Nexus / Chapter Approved 2025-26 (was 57–58% in Leviathan); under Chapter Approved 2025-26 "more or less always better to go second" | HIGH directional, MEDIUM exact | win × went-first per game |
| 3 | Mean secondary victory points per player per game | 22.7 (Pariah Nexus); ≈ 2.6 per tactical card drawn; Bring It Down averages 14 when chosen | HIGH | secondary total per player |
| 4 | Round-1 primary score | 0 by rule (primary scoring opens battle round 2) | HIGH | per-round primary, round 1 must be 0 |
| 5 | Per-turn primary cap | 15 victory points (3 objectives × 5); rarely hit early | HIGH (structural) | max per-round primary |
| 6 | Trailing-player catch-up trigger rate | Secret missions chosen in 7.2% of Pariah Nexus games (Chapter Approved 2025-26 replaced them with challenger cards, max 12) | HIGH (era-specific) | challenger trigger flag per game |
| 7 | Score-trajectory shape | 0 in round 1 → 5–10 per turn rounds 2–3 → peak 10–15 rounds 3–4 → attrition-constrained round 5; second player has the final scoring action | MEDIUM (consensus, no aggregate curve) | per-round primary mean across games |
| 8 | Deployment-map spread of primary mean | ±2–3 victory points across maps (Leviathan era: Hammer and Anvil 21, Search and Destroy 23.7) | HIGH (era-specific) | per-map primary mean |
| 9 | Victory-point margin winner − loser | No published mean; tournament scoring table implies most competitive games at 10–30, blowout threshold 50+ | LOW (inferred) | margin distribution per game |

## Scoring structure ground truth (Chapter Approved 2025-26, the deck the sim runs)

Primary max 50 · secondary max 40 · challenger cards max 12 · combined primary + secondary +
challenger capped at 90 · Battle Ready 10 · overall max 100. Primary scores in multiples of 5 with
a 15-per-turn ceiling, opening in battle round 2. Challenger cards are available to a player
trailing by 6 or more points at the start of a battle round.

## What does NOT exist publicly (honest gaps)

- **Per-marker per-round control data** — the exact thing the displacement Stage 0 instrument
  measures. The Tabletop Battles app records final scores only. Stage 0 is therefore the first
  measurement of displacement-addressable victory points anywhere; it sizes the prize internally
  but has no external target to match.
- Kill-point / units-destroyed averages per game.
- Fraction of games completing all five rounds (the sim always completes five; real games
  sometimes cut at three or four, biasing real primary averages slightly downward).
- Winner-versus-loser primary score means (only the combined per-player average is published).

## Sources

- https://www.goonhammer.com/hammer-of-math-stats-from-the-first-10000-games-of-pariah-nexus/
- https://www.goonhammer.com/hammer-of-math-early-results-from-chapter-approved-2025-26
- https://www.goonhammer.com/hammer-of-math-10th-edition-primary-scoring-statistics
- https://www.goonhammer.com/hammer-of-math-pariah-nexus-secret-missions/
- https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-battles/
- https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
- https://www.warhammer-community.com/en-gb/articles/Z8ZOFyMs/metawatch-how-did-going-first-affect-win-rate-at-the-warhammer-open-new-orleans/
- https://grimhammertactics.com/mastering-the-chapter-approved-2025-26-missions-mission-a-take-and-hold-on-tipping-point/
- https://www.stat-check.com/the-meta
