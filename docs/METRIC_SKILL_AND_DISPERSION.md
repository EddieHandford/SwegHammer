# The headline metric is beaten by a constant

*Measured 2026-07-27 against the standing anchor `sc69a`
(`data/_anchor_sc69a_n80_log.json`, 36960 games). Instruments:
`scripts/_skill_vs_null.py`, `scripts/_matchup_dispersion.py`,
`scripts/_dispersion_by_templates.py`, `scripts/_army_variability_probe.py`,
`scripts/_dispersion_vs_variability.py`. Nothing under `code/` was touched to
produce any of it.*

## The result

Scored in the evaluation's own frame — army-A cells only, field-weighted across
opponents by `TOURNAMENT_GAMES`, through `evaluate_vs_meta._noise_gated_error`
with the real per-faction `NOISE_FLOOR`:

| predictor | raw error | gated error | inside noise band |
|---|---|---|---|
| the simulator | 5.56 | **2.85** | 7 of 22 |
| constant 48.8 percent for every faction | 3.36 | **0.66** | 11 of 22 |
| constant 50.0 percent for every faction | 3.63 | 0.82 | 12 of 22 |

Skill score `1 - simulator / null` is **−0.65 raw and −3.33 gated**. A predictor
that ignores the simulator entirely and answers "about average" for every
faction scores four times better on the exact number this project has been
minimising.

The reconstruction reproduces the recorded anchor value of 2.85 to the decimal,
which is what establishes that the frame is faithful rather than a
re-derivation of some other quantity. The result also survives the symmetrized
both-sides frame (simulator 2.61 against the same null 0.66), so it is not an
artefact of the army-A positional bias.

## The diagnosis is variance, not bias

| | real | simulated |
|---|---|---|
| per-faction spread (standard deviation) | 3.83 | 6.72 |

The simulator's per-faction win rates are about **1.75 times too widely
spread**. Correlation against reality is weak but not zero: Pearson +0.25,
Spearman +0.28. Keeping the simulator's ordering and rescaling its spread by
0.12 would reach 3.31 raw on its own.

Those two facts together are the whole finding. Mean absolute error can be
lowered either by getting factions right or by moving every prediction toward
the average, and for the last several months it has mostly been measuring the
second. **A lever that lowers the gated headline is not thereby evidence of
improved fidelity.**

## Where the spread is manufactured

Faction-level spread is built out of matchup-level spread. Across the 231
symmetrized pairings:

- standard deviation **13.4 points raw**, **12.9 after correcting for sampling
  noise** (3.8 points of the raw figure is binomial noise on an 80-game cell)
- only **53.2 percent** sit inside a realistic 40–60 band
- **13.9 percent** are decided 70/30 or harder, **2.6 percent** at 80/20

The raw figure falls as the battle count rises even when nothing about the
simulator changes — at N=1 it reads 38.5, because every cell is 0 or 100. Waves
in this project run at both N=40 and N=80, so **only the corrected figure may be
compared across runs**.
- most one-sided: Adeptus Astartes over Genestealer Cults **86.9**, Thousand
  Sons over Drukhari **81.9**, Death Guard over Grey Knights **81.2**

Tournament data does not contain matchups like these in that quantity.

## The structural cause, and a natural experiment that was already in the data

`build_archetype_army` picks uniformly at random among a faction's templates
each time an army is built (`code/archetypes.py`, line 3240). **Twenty-one of
the twenty-two factions define exactly one template.** A real faction's win rate
averages over hundreds of lists of widely varying quality piloted by players of
widely varying skill; one list has one fixed set of good and bad matchups and no
way to regress toward the middle.

Chaos Daemons is the only faction with more than one list — it has five. It
ranks **first of twenty-two** on precisely the metric the hypothesis predicts:

| | matchup standard deviation | matchups 70/30 or harder |
|---|---|---|
| Chaos Daemons (five lists) | **6.8** | **0 percent** |
| the twenty-one single-list factions | 11.9 | 15 percent |

Under a null of random ranking, first of twenty-two is about `p = 0.045`. With
one faction in the group this is suggestive, not proof.

### The confound check sharpens the claim rather than weakening it

Every faction already gets *some* army variation, because `_random_fill` tops up
the budget after the template is seeded. Measured across twelve seeds, that
filler churn runs 0.24 to 0.39 turnover for the single-list factions; Chaos
Daemons runs **0.823**.

Correlation of turnover against matchup dispersion is **−0.44 across all
twenty-two factions but only −0.18 across the twenty-one single-list
factions**. Filler churn does not predict dispersion. It is strategic difference
between genuinely *different lists* that compresses matchups, not shuffling
which filler units top up the budget — so adding more filler variance would buy
nothing.

## A hypothesis that was tested and failed

The Leagues of Votann result (a known-good six-nil tournament list, faithfully
transcribed, winning 77.3 percent against a real 48.0) and the Death Guard
residual of +11.4 are both armies built on the most durable chassis their
faction owns. The obvious unifying explanation is that the simulator
over-rewards durability.

It does not. Correlating each faction's residual against the reference attacks
needed to remove its army per hundred points gives **−0.16 for light attacks,
−0.23 for medium, +0.09 for heavy, and −0.13 for offence**. Grey Knights and
T'au Empire are the two most durable armies in the catalogue by this measure and
both *under*-perform. The hypothesis is dead and the Votann result is local.
(`scripts/_durability_residual_probe.py`.)

## A MECHANISM for the over-dispersion (added 2026-07-28)

The spread above was measured but not explained. There is now a candidate
mechanism, and it is quantified against a cited source.

| | primary | secondary | total | secondary share |
|---|---|---|---|---|
| real, Pariah Nexus, ~7,600 games | 29.1 | **22.7** | 51.8 | **43.8 percent** |
| simulator, 231 battles, all 22 factions | 37.7 | **11.8** | 49.5 | **23.8 percent** |

The simulator scores roughly **30 percent too much primary and 48 percent too
little secondary**, while the **total comes out very nearly right**. That
compensating-errors pattern is why it survived: any check of total victory
points shows a believable number, and nothing reported the split until
`scripts/_vp_split_probe.py`.

Why this bears on dispersion: primary is board control, which is comparatively
deterministic — the better-positioned army holds objectives and keeps holding
them. Secondary is card-driven, with draw order, discard choices and mission
variance. A simulator deciding games 76 percent on primary where reality decides
them 56 percent on primary will produce systematically **more decisive outcomes
than reality does**, which is exactly the excess spread documented above.

Real figures: Goonhammer, "Hammer of Math: Stats from the First Month of Pariah
Nexus, Part 2" (verbatim: "Players score an average of 22.7 VP on secondary per
game") and its companion article for the 51.8 total, which is explicitly primary
plus secondary excluding the Battle-Ready 10.

**Era caveat:** that data is from June–July 2024, the Pariah Nexus launch window,
against a May 2026 calibration target. Both are tenth edition on the same mission
pack and the caps are structural, so the comparison is sound in kind — but norms
may have shifted over two years of dataslates, so treat the exact magnitude as
approximate. The direction is not in doubt: 22.7 against 11.8 is far too large a
gap to be an era artefact.

This is a hypothesis for the dispersion, not a demonstrated cause. Fixing the
scoring split and re-measuring the spread is what would confirm it.

## The list-population proposal, and why it is WITHDRAWN

The original conclusion drawn from the section above was to give each faction
two to four sourced lists and sample per game. **That proposal is withdrawn**,
on the owner's reading of the project goal (2026-07-27), which is sharper than
the reasoning that produced it.

The simulator's job is to field the best list available and pilot it as well as
a tournament player would. A tournament player locks one list before the event
without knowing their opponents, then adapts their *piloting* per matchup. So
**one list per faction is correct**, and Chaos Daemons sampling among five is
the one faction doing the wrong thing — its low dispersion is a symptom, not a
model to copy.

Worse, the change would have been the exact failure this document warns about
one section earlier. Measured: keeping the simulator's current ordering and
rescaling its spread optimally reaches **3.31** raw against the constant null's
**3.36**. A dead heat. At a correlation of +0.25 there is not enough ordering
information for spread calibration to buy anything, so list-population averaging
would have driven the headline from 5.56 to roughly 3.4 — a spectacular-looking
result containing no fidelity at all.

## What the goal reframing does to the over-dispersion finding

If the simulator answers *"best list, best piloting, both sides"*, the Warp
Friends aggregate answers a different question: *"what happens across hundreds
of lists piloted by everyone from champions to novices."* Player skill variance
is probably the largest randomiser in real Warhammer, and two symmetrically
optimal policies remove it entirely.

A simulator doing its job correctly **should** be more dispersed than that
aggregate. The 13.4 matchup standard deviation is therefore not established as a
defect, and neither is losing to the constant on distance — the constant is a
good predictor of a population average, which is not what the simulator is
trying to produce.

**One number survives the reframing intact.** Over-dispersion is excusable under
this goal; wrong ORDERING is not. A simulator answering the optimal-play
question correctly should be more spread out than reality while ranking the
factions in roughly the same order. Spearman rank correlation is **+0.28**.
That is the real indictment and no reframing rescues it.

## Three hypotheses tested, three dead

No global army-property axis explains the residual.

| hypothesis | measure | result |
|---|---|---|
| simulator over-rewards durability | residual against effective wounds per point | −0.16 light, −0.23 medium, +0.09 heavy, −0.13 offence |
| one list per faction causes over-dispersion | see above | withdrawn on goal grounds |
| simulator pilots melee badly | residual against melee damage share | +0.004; and −0.017 to +0.051 across three reference targets, with the group gap flipping sign |

The melee reading came from sorting factions by reputation rather than by
measured composition. Death Guard measures a 0.83 melee damage share — third
highest in the game — and is the third largest over-performer; T'au Empire
measures 0.09 and under-performs. (`scripts/_piloting_axis_probe.py`,
`scripts/_durability_residual_probe.py`.)

That triple null is itself the finding: **the residual is not a property of what
kind of army a faction fields.** It is per-faction, which means the
faction-at-a-time method is sound and the Tyranid list fix (+9.49 from one
corrected template) is the template for the work — it was only ever the
*scoring* of that method that was broken.

## What follows

**Change the metric first — BUILT 2026-07-27.** `evaluate_vs_meta` now prints an
ORDERING DIAGNOSTICS block after the existing table, and writes the same values
under a `diagnostics` key in the snapshot when `--out` is given:

- Spearman rank correlation (labelled the headline) and Pearson correlation
- spread ratio, simulated standard deviation over real
- skill against the constant null, through the identical noise gate
- matchup standard deviation, sampling-corrected, with the share of pairings
  inside 40–60 and the share decided 70/30 or harder

The change is purely additive. `report` is untouched and returns the same three
numbers, so every historical figure in this repository still means what it said,
and nothing that reads the evaluation's output or its return value changes.
A `--factions` run refuses to print the block at all rather than compute a
correlation across factions that never played.

Verified by `scripts/_verify_diagnostics.py`, which rebuilds the evaluation's
inputs from the `sc69a` game log and asserts the wired-in block reproduces the
standalone instruments from a separate code path — all five values agree.

Persisting the values in the snapshot is what makes them usable: with 22
factions a single wave's correlation carries a confidence interval far too wide
to act on, so the guidance to read it as a trend is empty unless the numbers are
on disk to compare.

Stage 1 converged should now mean "the simulator orders the factions the way
reality does", not "the distances match" — because the stated target of 2.0
points is already beaten by a constant scoring 0.66, so the current criterion
can be satisfied by a model containing no simulation at all. **Changing the
stated target in `CLAUDE.md` is an owner decision and has not been made.**

One caution on the new instrument: with 22 factions a correlation of +0.25 has a
95 percent confidence interval of roughly −0.19 to +0.61. Read it as a trend
across several waves, never as a per-wave verdict — otherwise one over-trusted
number has simply replaced another.

Two cautions carried forward:

1. **Do not treat a falling headline as success.** Until the correlation rises
   for a reason found in the rules, the headline is measuring convergence
   toward the mean.
2. **Do not adopt a list because it improves the metric.** That is the failure
   already documented in `docs/TYRANID_LIST_FIDELITY.md`, where the most
   metric-tuned template in the project was also its worst residual.
