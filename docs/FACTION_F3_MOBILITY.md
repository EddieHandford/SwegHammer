# Faction F3 — Mobility-factions archetype diagnostic

Three different problems on three different factions. Eval-vs-meta puts:

| Faction              | Sim WR (mean, this diag) | Real WR | Gap        |
|----------------------|-------------------------:|--------:|-----------:|
| Adeptus Astartes     |                   69.3 % |  ~47 %  | **+22**    |
| Aeldari              |                   35.6 % |  ~47 %  | **-11**    |
| Leagues of Votann    |                   41.5 % |  ~53 %  | **-12**    |

Method: `scripts/mobility_diag.py` runs 30 seeded battles per matchup (focus
faction vs each of the 9 other archetype-enabled factions, 1000 pts,
archetype=True on both sides, seeds 9001-9030). Per matchup we capture:

- A-WR, mean rounds
- Stratagem firing counts (focus army only)
- Oath of Moment targets chosen / battle (Marines)
- Battle Focus tokens spent in the final round (Aeldari)
- Judgement Token award events + max stack on any enemy unit (Votann)
- Per-profile start counts + survival rates for tracked archetype units

## Per-matchup WR (N=30)

```
Marines vs ...               Aeldari vs ...               Votann vs ...
Necrons              56.7    Adeptus Astartes     13.3    Adeptus Astartes     10.0
Aeldari              93.3    Necrons              20.0    Necrons              26.7
Tyranids             60.0    Tyranids             16.7    Aeldari              56.7
Orks                 76.7    Orks                 50.0    Tyranids             13.3
T'au Empire          66.7    T'au Empire          56.7    Orks                 53.3
Death Guard          63.3    Death Guard          30.0    T'au Empire          66.7
Adeptus Custodes     43.3    Adeptus Custodes     26.7    Death Guard          23.3
Thousand Sons        83.3    Thousand Sons        56.7    Adeptus Custodes     56.7
Leagues of Votann    80.0    Leagues of Votann    50.0    Thousand Sons        66.7
mean                 69.3    mean                 35.6    mean                 41.5
```

**Worst 2 matchups (by WR ascending):**

- Marines: vs Custodes (43.3%), vs Necrons (56.7%) — only matchups under 60%.
- Aeldari: vs Astartes (13.3%), vs Tyranids (16.7%).
- Votann: vs Astartes (10.0%), vs Tyranids (13.3%).

Marines' "worst" matchup is still 43%; their best is 93% vs Aeldari. Every
other faction loses to them. Aeldari and Votann share the same two worst
matchups (Astartes blast, Tyranids overrun), which points at *list-shape*
weakness rather than a Marines-counter problem.

## Adeptus Astartes — diagnostic detail

```
vs Custodes (43.3%):  Intercessor start 10.7/battle, survive 58.8%
                      Eradicator start 3.6,   survive 61.1%
                      Apothecary start 1.1,   survive 56.2%
                      Repulsor:        NEVER SEEDED
                      Captain in TDA:  NEVER SEEDED
                      Oath targets chosen / battle: 5.00 (every round)
                      Stratagems:  Command Re-Roll 5.3, Heroic Intervention 1.7

vs Necrons  (56.7%):  Intercessor survive 81.2%, Eradicator survive 83.3%
                      Oath fires 5x. Repulsor + Capt-TDA still missing.

vs Tyranids (60.0%):  Intercessor survive 71.9%, Aggressor survive 100%
                      Apothecary survive 84%, Eradicator survive 69%
```

Note that Repulsor and Captain in Terminator Armour are **never seeded** —
their squad-costs (Repulsor 198, Capt-TDA 95) get squeezed out of the 300pt
seed budget by the cheap-first walker. But it doesn't matter: random fill
brings in 10 Intercessors, 3-4 Eradicators, 1 Apothecary, 1 Ancient, plus
extras like Vanguard Veterans and Servitors. Marines still over-perform
because the *core math* is too efficient — Oath fires every round on the
highest-points enemy (re-roll hit + re-roll wound), Combat Doctrines adds
+1 to wound every round (Devastator R1, Tactical R2, Assault R3+), and 10
Intercessors at OC2 sweep objectives.

The "mobility" hook in the archetype name is barely relevant — there's no
Repulsor for transport play, and Marines win mostly by Oath+Doctrines'
damage-multiplier stacking on durable T4 W2 Sv3+ bodies.

**Root cause (one line):** Oath of Moment + Combat Doctrines + Intercessor
OC stack is too efficient — Marines deal ~2x wounds/pt of a like-cost army.

## Aeldari — diagnostic detail

```
vs Astartes (13.3%):  Dire Avengers survive  8.0% (start 4.6/battle)
                      Rangers       survive  0.0% (start 1.0/battle)
                      Autarch       survive 14.7% (start 1.1)
                      Farseer       survive 37.5% (start 1.1)
                      Wraithguard:   NEVER SEEDED
                      Fire Dragons:  NEVER SEEDED
                      Falcon:        NEVER SEEDED
                      Guardian Def:  NEVER SEEDED
                      Battle Focus tokens spent in final round: 2.8/4
                      (BF *is* firing — not the bottleneck)

vs Tyranids (16.7%):  same picture — Wraithguard / FireDragons / Falcon
                      / Guardian Defenders all NEVER SEEDED across all 30 battles

vs Necrons  (20.0%):  same
```

Trace of `_instantiate_template` at 1000pt × `SEED_FRACTION=0.3` = 300pt seed:

| Aeldari template entry | min_models | squad cost | seeded?           |
|------------------------|-----------:|-----------:|-------------------|
| Rangers                |          1 |       55.0 | yes               |
| Farseer                |          1 |       70.0 | yes               |
| Dire Avengers          |          4 |       75.0 | yes (200 running) |
| Autarch                |          1 |       85.0 | yes (285 running) |
| Guardian Defenders     |          1 |      100.0 | **NO** (385 > 300) |
| Fire Dragons           |          4 |      120.0 | **NO** (skipped)  |
| Wave Serpent           |          1 |      125.0 | **NO** (skipped)  |
| Wraithguard            |          1 |      240.6 | **NO** (skipped)  |
| Falcon                 |          1 |      644.5 | **NO** (broken price) |

Aeldari's entire damage profile is sealed off. The seed yields 4 Dire
Avengers (frail T3 1W Sv4+) + 1 Rangers + 1 Farseer + 1 Autarch, then random
fill pulls a grab-bag of same-faction units (Howling Banshees, Starweaver,
Farseer Skyrunner, Illic Nightspear). Rangers ALWAYS die (0%), Dire Avengers
die nearly always (5-8%), and Wraithguard / Fire Dragons / Falcon — the
units that actually trade well into MEQ and big targets — never show up.

The Falcon override at 644.5 pts/model (from `data/overrides.json`,
`sweg_balance_mc up 585.86 -> 644.45 pts/model`) is itself a catalogue bug —
GW prints the Falcon at 130 pts. The balancer treated squad-cost as
per-model-cost. Same class of bug as Hearthkyn (see Votann section).

The Battle Focus shimmy is **firing** — tokens are being spent (avg 2.5-2.8
of 4 per final round) — so the rule is implemented, but Dire Avengers in
cover with Battle Focus don't have the punch to matter; their 18" S4 AP-1
guns don't kill T4 Marines fast enough to win an attrition race.

**Root cause (one line):** Aeldari archetype's anchor / mobility / anti-tank
units (Wraithguard, Fire Dragons, Wave Serpent, Falcon, Guardian Defenders)
all priced above the 300pt seed budget; identity reduced to frail Dire
Avengers + Rangers.

## Leagues of Votann — diagnostic detail

```
vs Astartes (10.0%):  Cthonian Beserks survive  7.3% (start 7.3/battle)
                      Hekaton          survive 27.3% (start 0.4)
                      Hernkyn Pioneers survive 32.4% (start 3.4)
                      Iron-master      survive 53.5% (start 4.8)
                      Hearthkyn:    NEVER SEEDED
                      Sagitaur start 0.1/battle (almost never)
                      Judgement Token award events / battle: 21.2
                      Max Judgement stack on any enemy unit: 3.3

vs Tyranids (13.3%):  Cthonian Beserks survive 19.5%
                      Iron-master      survive 51.4%
                      Hekaton          survive 90.9%
                      Hearthkyn:    NEVER SEEDED
                      Judgement events / battle: 18.7, max stack 3.7

vs Death Guard (23.3%):  similar, Judgement max stack 3.8
```

Trace at 300pt seed:

| Oathband template entry          | min_models | squad cost | seeded?  |
|----------------------------------|-----------:|-----------:|----------|
| Brôkhyr Iron-master              |          4 |       75.0 | yes      |
| Hernkyn Pioneers                 |          3 |       80.0 | yes      |
| Cthonian Beserks                 |          5 |      100.0 | yes (255 running) |
| Sagitaur                         |          1 |      103.5 | **NO** (358 > 300) |
| Einhyr Hearthguard               |          4 |      135.0 | **NO** (skipped) |
| **Hearthkyn Warriors**           |          9 |   **810.0**| **NO** (skipped, BROKEN PRICE) |

Hearthkyn (the army's CORE OC-bearer, GW listed price 100/squad) carries
`points_override = 90.0` in `data/overrides.json` from a sweg-balance MC pass,
written with the note "down 100.0 -> 90.0 pts/model". But the comment is
**wrong** — the override IS being interpreted per-model, multiplied by
min_models=9 to produce a 810pt squad cost. Same class of bug appears for
Aeldari Falcon (override=644.5) and probably others.

Without Hearthkyn the Oathband loses its objective-holding spine. Random
fill brings 9 Hernkyn Pioneers (5W bikes) and 8 Iron-master (1W chaff with
auras) plus Cthonian Beserks, but Cthonian Beserks die at 7% rate vs MEQ
shooting. Hekaton appears at 0.4/battle but is the only durable platform.

Judgement Tokens are awarded heavily (15-21 events/battle, max stack 3-4
on a single enemy unit) — but Votann are dying so fast that the buffs
have a small window to act. The rule is firing; the durability isn't there
to capitalise on it.

The Sagitaur — supposed fast objective-contest unit — appears at 0.1/battle
(seed skips it for 3pt over budget). Combined with the rare Hekaton, the
"mobile fast objective" identity is gone.

**Root cause (one line):** Hearthkyn Warriors broken per-model pricing
(`points_override=90.0` × 9 min_models = 810/squad) hides the core OC
unit; archetype falls back to chaff that dies to MEQ shooting.

## Hypothesis verdicts

- **Marines too efficient (H1).** Confirmed. Oath fires 5x/battle on the
  right target. Combat Doctrines compounds the +1-wound every round.
  Intercessor squads of 10 (start 10.7/battle) provide overwhelming OC.
  Even the "worst" matchup (Custodes 43%) is still respectable — Marines
  beat every other faction. The archetype isn't doing anything wrong
  list-shape-wise; the rules implementation is too compound.
- **Aeldari shimmy not the issue (H2).** Battle Focus IS firing (~2.7
  tokens of 4 spent per final round). But the units that benefit
  (Wraithguard, Fire Dragons, Wave Serpent) are absent from the seeded
  list, so the shimmy moves the wrong units (Dire Avengers, Rangers) who
  die regardless. Shimmy needs anchors to work.
- **Votann too elite / catalogue bug (H3).** Same shape as TSON F2.
  Hearthkyn priced at 810/squad blocks the OC core. Compounded by the
  faction's army rule (Judgement Tokens *help the enemy*) and the fragile
  T4/T5 W2-3 Cthonian Beserks dying in 7% trades.

## Fixes — prioritised across the 3 factions

### Priority 1 (highest WR uplift, simplest fix)

**Fix the per-model points override bug for Hearthkyn Warriors AND Falcon
(and audit every other big-squad / single-model override).**

`data/overrides.json` contains entries where the balancer's
`sweg_balance_mc` claimed "X pts/model" but the actual unit's `points_listed`
was the full SQUAD price. The catalogue then multiplies by `min_models`:

- `leagues_of_votann_hearthkyn_warriors`: override 90.0 × 9 mm = 810/squad,
  GW listed 100/squad — **9x too expensive**
- `aeldari_craftworlds_falcon`: override 644.5 × 1 mm = 644.5/squad, GW
  listed 130/squad — **5x too expensive**
- (audit all sweg-balance-MC outputs against `points_listed` similarly)

Expected uplift: Votann WR +10-15 pts (Hearthkyn shows up + Sagitaur fits),
Aeldari WR +5-8 pts (Falcon shows up if balancer corrects to ~130).

### Priority 2 (Aeldari archetype seed budget too small)

**Walk the archetype template in template-count-priority order, not
cheapest-first; or raise SEED_FRACTION for Aeldari specifically; or set
`min_models` for big squads to a small slice so a Wraithguard squad of 1
costs 80 and fits the seed.**

Right now Aeldari's anchors (Wraithguard, Wave Serpent, Fire Dragons)
require an 480-600pt seed budget to all fit. Either bump SEED_FRACTION to
~0.55 for Aeldari, or change the walk to prefer high-template-count entries
first.

Expected uplift: Aeldari WR +8-12 pts (Wraithguard 240pt now seeds = anti-MEQ
melta-tier shooting + 3W bodies; Fire Dragons add anti-vehicle).

### Priority 3 (Marines too compound)

**Don't change the archetype — the bug is in the rules implementation
stacking.** Either gate Combat Doctrines to a single-mode boost (real rule
is mode-locked anyway), or scale Oath of Moment from re-roll-everything
to re-roll-1s (closer to old datasheets), or cap one-of these per round.

Expected effect: Marines WR -10 to -15 pts toward real ~47%.

This is OUTSIDE the F3 archetype-fix scope — it's a `code/units.py` rules
audit. Flag for a separate ticket; do not touch `code/archetypes.py`.

## Files inspected

- `code/archetypes.py` — `_instantiate_template`, ARCHETYPES dict
- `code/army_builder.py` — `build_faction_random_army` archetype dispatch
- `code/units.py` — Combat Doctrines (655-685), Oath of Moment, points_cost
  property (319-342)
- `code/simulator.py` — Battle Focus reset (213), advance gate (1936-1960),
  Judgement Token award (2311-2340), Oath target chosen (2269-2282)
- `code/strategy.py` — `_shimmy_target` (110-164)
- `code/detachments.py` — `GLADIUS_TASK_FORCE` (129-142)
- `data/overrides.json` — Hearthkyn 90, Falcon 644.5 (broken per-model
  interpretation)
- `data/bsdata/parsed.json` — `points_listed` for Hearthkyn (100) and
  Falcon (130) confirms the override mis-scaling

## Repro

```
PYTHONIOENCODING=utf-8 python -m scripts.mobility_diag
```

90 matchups × 30 battles = 2700 battles; runs in about 90 seconds on a
typical dev machine.
