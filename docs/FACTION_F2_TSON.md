# Faction F2 — Thousand Sons archetype diagnostic

Latest archetype-enabled eval-vs-meta puts **Thousand Sons (Cult of Magic)** at
~22.0% sim WR vs the real meta's 54.6% — a **-32.6 pt** gap, the largest
under-performance of any faction. This document records a focused 30-battle
diagnostic and ranks the root causes.

## Method

`scripts/tson_diag.py` — 30 seeded battles per matchup (TSON vs each of the 9
other archetype-enabled factions, 1000 pts, archetype=True on BOTH sides, same
seed schedule as the main eval). Per matchup we capture:

- A-win rate
- Mean rounds played
- Per-battle firing counts of Doombolt / Cabbalistic Empowerment / Twist of
  Fate / Glamour of Tzeentch
- Survival rate of every tracked TSON profile (Rubric Marines, Scarab Occult
  Terminators, Tzaangors, Exalted Sorcerer, Infernal Master, Helbrute)
- Start counts of tracked profiles per battle

## Per-matchup results

```
Opponent                  WR%     R     DB     CE     TF     GT
----------------------------------------------------------------------
Adeptus Astartes         20.0   4.9   4.60   4.67   3.70   0.20
Necrons                  16.7   5.0   4.67   4.90   3.37   0.10
Aeldari                  36.7   5.0   3.67   4.93   2.47   0.03
Tyranids                  3.3   5.0   4.93   4.97   3.90   0.03
Orks                     30.0   5.0   4.07   4.87   2.90   0.07
T'au Empire              23.3   5.0   4.50   5.00   3.37   0.00
Death Guard              10.0   5.0   3.97   4.87   2.63   0.13
Adeptus Custodes         30.0   5.0   3.37   4.73   2.33   0.23
Leagues of Votann        26.7   5.0   4.20   4.83   3.00   0.07
----------------------------------------------------------------------
Mean TSON WR vs 9 opponents: 21.9%
```

**Worst 3 matchups**: vs Tyranids (3.3%), vs Death Guard (10.0%), vs Necrons (16.7%).

## Random-pool baseline (no archetype)

For comparison, the same 30-seed harness with `use_archetype=False` on both
sides gives Thousand Sons a **mean 31.5% WR** vs the same 9 opponents.
**Turning the curated Cult-of-Magic archetype ON drops TSON by ~10 pts.**
The archetype is actively making them worse than the random pool.

## Cabal Points trajectory analysis

Doombolt fires ~4 times per 5-round battle in nearly every matchup — the CP
loop is **working**. Cabbalistic Empowerment also fires ~5x/battle (boosting
each Doombolt from median 2 MW to 3 MW). Twist of Fate fires 2-4x. Total
TSON stratagem volume is ~13-14 spends per battle, comparable to or higher
than other archetypes.

**The psychic phase is firing on every available round.** Cabal Points are
not the bottleneck.

## The actual problem — the archetype is broken at 1000 pts

At 1000 pts × `SEED_FRACTION = 0.3` → **300 pt seed budget**.
`_instantiate_template` walks the template cheapest-first:

| Entry                      | min_models | squad cost | seeded? |
|----------------------------|-----------:|-----------:|---------|
| Tzaangors                  |          9 |       70.0 | yes     |
| Exalted Sorcerer           |          1 |       80.0 | yes     |
| Infernal Master            |          1 |       95.0 | yes     |
| Helbrute                   |          1 |      110.0 | **NO** (245+110=355 > 300) |
| Rubric Marines             |          4 |      239.8 | **NO** (245+240=485 > 300) |
| Scarab Occult Terminators  |          4 |      395.9 | **NO** (skipped outright)  |

The seeded core is **9 Tzaangors + 2 characters**, then 750 pts of random
faction fill. Across 30 sampled armies, the random fill almost never picks
Rubrics or Scarab Occult — instead it returns Lord of Change, Daemon Prince,
Mutalith Vortex Beast, Chaos Spawn, Hellblades, Tzaangor Enlightened, etc.

In the diagnostic, **Rubric Marines and Scarab Occult Terminators have zero
start-counts across all 270 battles run**. The defensive anchors of Cult of
Magic are absent. The archetype's All Is Dust identity (D=1 mitigation) has
nothing to attach to.

Survival rates that DO appear (Tyranids matchup): Tzaangors 10.1%, Infernal
Master 22.2%, Exalted Sorcerer 35.1%. 9 W=1 Sv=6+ Tzaangors get swept by
40 Tyranid bodies inside two rounds; the two TSON psyker characters then
have no escort and are run down.

## Catalogue-side defensive deficits (compounding)

Independent of the archetype bug, the entire Thousand Sons catalogue carries
`invuln_save = 7` (i.e. no invuln). In real 10e:

- Rubric Marines have a 5+ invuln
- Scarab Occult Terminators have a 4+ invuln (and "All Is Dust" -1 to wound D=1)
- Daemon Prince / Magnus / Kairos / Lord of Change have 4+ invuln
- Mutalith / Maulerfiend / Helbrute have a 5+ invuln on some variants

The catalogue's TSON units lose their save against AP-2 and AP-3 attacks
where they'd otherwise fall back on the invuln. This affects them even
under random-pool play (the -10.9 pt random-pool deficit pre-archetype).

## All Is Dust effectiveness

The simulator implements All Is Dust correctly (`code/units.py:755-769` —
+1 to wound target on D<=1 attacks against TSON non-DAEMON units). But in
the current catalogue **67-83% of opposing units have at least one D>=2
weapon (ranged or melee)**:

| Opponent       | % units with D>=2 |
|----------------|------------------:|
| Orks           |               83% |
| Aeldari        |               80% |
| Adeptus Custodes |             79% |
| Adeptus Astartes |             74% |
| Necrons        |               73% |
| Death Guard    |               73% |
| Leagues of Votann |            72% |
| Tyranids       |               71% |
| T'au Empire    |               67% |

Combined with the fact that the archetype-spawned TSON list contains zero
Rubrics anyway, All Is Dust has minimal opportunities to fire.

## Hypothesis ranking

**H3 (LIST COMPOSITION) — confirmed, dominant cause.**
The Cult of Magic archetype at 1000 pts seeds only Tzaangors + 2 characters
and lets random fill pick the rest. Rubrics and Scarab Occult — the entire
defensive identity of the archetype — never appear. This is a builder bug,
not a simulator bug. Switching off the archetype recovers ~10 pts of WR.

**H1 (ALL IS DUST IRRELEVANT) — confirmed, secondary.**
Even when Rubrics DO appear (random fill at 2000 pts builds 4 of them, see
`scripts/tson_diag.py` validation), 67-83% of attackers carry D>=2 weapons
that ignore the buff. The rule is implemented correctly but rarely fires.

**H4 (NO PSYCHIC ANCHOR) — confirmed, secondary.**
The archetype excludes Magnus / Ahriman. Real Cult of Magic lists are built
around a psychic anchor with 4+ invuln, 16-20 W, and powerful aura. The
catalogue contains Magnus (435 pts, T11, W16, Sv 2+, Inv 7 — no invuln in
catalogue), Ahriman, Kairos. None of these are seeded.

**H2 (DOOMBOLT TARGETING) — refuted.**
Doombolt fires ~4.5x/battle on the role-weighted highest-threat enemy.
Cabbalistic Empowerment fires alongside it ~5x/battle. The psychic loop is
operating at full cadence and is not the bottleneck.

## Concrete fixes (DO NOT IMPLEMENT — diagnose only)

Ranked by expected WR uplift.

### 1. Fix the archetype scaling at low budgets (highest priority)

`code/archetypes.py::_instantiate_template` should either:

- Drop `SEED_FRACTION` for Thousand Sons so the seed budget at 1000 pts
  reaches ~500-600 pts and Rubrics + Scarab Occult fit; or
- Walk the template in template-count-priority order rather than
  cheapest-first (the canon-2 Rubric squads should beat one Helbrute); or
- Scale `min_models` template entries to a fixed model count regardless of
  squad-min so a Rubric squad seeds as 4 models = 240 pts, fitting inside
  the seed.

Expected uplift: random-pool TSON sits at 31.5% WR (vs archetype's 21.9%).
A list with Rubrics + Scarab Occult + Tzaangors + 2 characters as the seed
core would likely hit 35-40% WR before further fixes.

### 2. Add psychic-anchor invuln saves via overrides (catalogue-side)

`data/overrides.json` should set:

- Rubric Marines: `invuln_save = 5`
- Scarab Occult Terminators: `invuln_save = 4`
- Magnus the Red / Ahriman / Lord of Change / Kairos Fateweaver / Daemon
  Prince variants: `invuln_save = 4`
- Helbrute / Maulerfiend / Mutalith: `invuln_save = 5` (or whichever the
  datasheet carries)

Cite each via Wahapedia URL in the overrides comment (CLAUDE.md §10).

Expected uplift: ~3-5 pts WR from invuln saves alone, larger if AP-spam
opponents currently chew through 3+ saves.

### 3. Add Ahriman or Magnus to the archetype template

Add an entry like `thousand_sons_ahriman: 1` (or magnus_the_red for 2000-pt
lists, ahriman for 1000-pt) so the psychic-anchor is seeded explicitly.
Ahriman at 100 pts is affordable inside even a 200-pt seed budget.

Expected uplift: smaller (~2 pt) — adds aura support and a third psyker
to keep Doombolt online if the Exalted Sorcerer dies.

## Files inspected

- `code/archetypes.py` — `_instantiate_template` (lines 187-246)
- `code/army_builder.py` — `build_faction_random_army` (lines 238-273)
- `code/detachments.py::CULT_OF_MAGIC` (lines 342-360)
- `code/stratagems.py::DOOMBOLT`, `TWIST_OF_FATE`, `GLAMOUR_OF_TZEENTCH`,
  `CABBALISTIC_EMPOWERMENT` (lines 114-270)
- `code/simulator.py::_try_doombolt` (lines 650-677)
- `code/strategy.py` Doombolt / Cabbalistic Empowerment AI (lines 1596-1606, 1823-1833)
- `code/units.py` All Is Dust rule (lines 755-769)
- `data/bsdata/parsed.json` — TSON profile stats (especially invuln_save = 7)
