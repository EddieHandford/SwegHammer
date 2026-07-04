# Death Guard elite-infantry crater — diagnosis

Read-only diagnostic on the standing anchor `data/_anchor_sc54a_n80_log.json`
(base `c4fc070`, branch `claude/sim-calibration-19`). No tracked simulator files
were changed. Scratch scripts: `scripts/_dgcrater_replay.py` (reproduction +
instrumentation + contagion-gate ablation), `scripts/_dgcrater_objtrace.py`
(single-game objective-control trace), `scripts/_dgcrater_objspread.py`
(cell-wide objective-spread quantifier).

## The question

Death Guard is the top over-pole (field-weighted 66.6 percent versus real 47.6).
The over-pole is a specific class cratering: Death Guard beats low-model elite
infantry (Thousand Sons 85 percent, Grey Knights 79, Emperor's Children 77,
Adeptus Astartes 77, Custodes 77, Orks 75) while holding near even against
mobile / shooting armies and losing to Genestealer Cults and Imperial Knights.
Is the crater (a) a faithful-rules floor for Stage-2 pricing, or (b) an
addressable mechanism — the recently adopted contagion pieces over-contributing,
or an artificial-intelligence play gap?

## Reproduction gate — PASSED

All winners replayed byte-for-byte against the anchor (both orderings, 80 seeds
each, 160 games per cell):

| Cell | Recorded | Replayed win rate | Winners matched |
|---|---|---|---|
| Death Guard vs Thousand Sons | 85.3 | 85.0 percent | 160 / 160 |
| Death Guard vs Grey Knights | 79.1 | 78.8 percent | 160 / 160 |
| Death Guard vs Genestealer Cults (inverse control) | 42.2 | 41.2 percent | 160 / 160 |
| Death Guard vs T'au Empire (mobile control) | 53.4 | 53.1 percent | 160 / 160 |

No conclusion below relies on any un-reproduced game.

## Verdict

**The crater is NOT contagion over-contribution.** It is a primary-objective
("Take and Hold" marker-spread) outcome with two compounding causes, neither of
which is the Death Guard contagion:

1. **A Stage-1 structural durability / model-count objective over-reward
   (floor — price it in Stage-2).** Death Guard is the most durable infantry
   army in the catalogue (Feel No Pain, Disgustingly Resilient, high Toughness),
   and its bodies are Dual / Melee / Horde roles that spread onto objectives.
   It out-holds elite low-model infantry regardless of how they play. This is
   the same over-reward the codebase already documents — every adopted durable
   ranged-hold (Adeptus Astartes, Leagues of Votann, Chaos Knights) OVERSHOOTS
   its real win rate — expressed at its extreme through the most durable army.
   Against Grey Knights (24 starting bodies) it is a hard floor: no positioning
   lets 24 bodies out-hold 50 durable bodies on a five-marker board.

2. **An addressable artificial-intelligence play gap: the elite gunline cedes
   the objective majority (amplifier).** The Thousand Sons scoring core, Rubric
   Marines, is role Shooty. The movement heuristic (`code/strategy.py` line
   ~3748) makes a Shooty or Heavy unit HOLD in place and shoot the moment any
   enemy is inside weapon range, and the "mass idle bodies onto objectives"
   branch (`SWEG_MASS`, line ~3714) fires only for units OUT of range. Against
   short-ranged Death Guard a Death Guard model is almost always inside the
   Rubrics' 24-inch range, so the Rubrics park on their own half and shoot,
   never fanning out to contest the objective majority.

## Evidence that decides floor-versus-contagion

### The contagion is ruled out by gate ablation

Turning off all three DURA-AUDIT contagion pieces at once — D1
(`SWEG_DG_CONTAGION_ESCALATION`, the 3/6/9-inch aura growth), D2
(`SWEG_DG_AFFLICTED_TOUGHNESS`, Afflicted minus-one Toughness), D3
(`SWEG_DG_CHOSEN_PLAGUE`, the chosen-plague save/hit/objective-control debuff) —
barely dents the crater:

| Cell | baseline | D1 off | D2 off | D3 off | all three off |
|---|---|---|---|---|---|
| Thousand Sons | 85.0 | 80.6 | 81.9 | 82.5 | **78.8** |
| Grey Knights | 78.8 | 74.4 | 76.2 | 83.1 | **70.6** |
| Genestealer Cults | 41.2 | 37.5 | 37.5 | 33.1 | 37.5 |
| T'au Empire | 53.1 | 42.5 | 45.6 | 50.0 | **41.2** |

Roughly 79 percent (Thousand Sons) and 71 percent (Grey Knights) of the crater
survive with the contagion fully removed. The contagion contributes only about
six to eight points to the craters — and its single largest effect anywhere is
against T'au (minus 11.9), an army Death Guard is merely even against, not a
crater. Note also that removing D3 against Grey Knights RAISES Death Guard's win
rate (78.8 to 83.1): the chosen-plague artificial-intelligence pick
(Rattlejoint Ague, worsen Save, chosen in all 160 Grey Knights games) is not
even net positive for Death Guard there. The contagion is faithful and is not
the mechanism — leave it.

### Same plague, opposite outcomes — the crater tracks the opponent, not Death Guard

Under the identical Scabrous Soulrot plague, Death Guard wins 86.4 percent
versus Thousand Sons but only 41.2 versus Genestealer Cults and 53.1 versus
T'au. Same Death Guard mechanism, three different results — the crater is
driven by what the opponent does.

### It is an objective-spread outcome, not an attrition wipe

Averaged over all 160 games per cell:

| Cell | Death Guard markers per round | Opponent markers per round | Spread | Death Guard end-alive | Opponent end-alive |
|---|---|---|---|---|---|
| Thousand Sons | 1.84 | 0.93 | **+0.90** | 11.6 | 18.4 |
| Grey Knights | 1.82 | 1.02 | +0.81 | 14.9 | 8.3 |
| Genestealer Cults (beats Death Guard) | 1.41 | 1.60 | **−0.19** | 14.4 | 20.5 |
| T'au (even) | 1.59 | 1.29 | +0.30 | 7.3 | 25.0 |

The Thousand Sons paradox: it ends with MORE surviving bodies than Death Guard
(18.4 versus 11.6) and roughly equal units sitting on objectives (2.67 versus
2.58), yet scores only HALF the markers (0.93 versus 1.84 per round). Its bodies
double up on its own two near markers while Death Guard fans across three. The
single-game trace (`_dgcrater_objtrace.py`, seed 0) shows the split cleanly:
Thousand Sons cleanly holds the two markers on its own side with high Objective
Control and never contests the centre and far markers, which Death Guard holds
uncontested. The damage exchange is nearly even (132 dealt / 126 taken versus
Thousand Sons; against Grey Knights Death Guard deals LESS — 95 versus 125 — and
still wins), so this is not a tabling. Death Guard wins on the primary because it
holds one more marker per round.

### The controls localise the mechanism

- **Genestealer Cults beats Death Guard** because it is the one opponent that
  out-spreads it (1.60 versus 1.41 markers per round; 2.61 versus 2.21 on
  objectives): 79 Horde bodies plus the Ambush-alpha posture push forward and
  contest the majority. It also never triggers the strong counter-plagues (its
  cheap low-save low-output bodies draw only the general-utility Scabrous
  Soulrot in all 160 games).
- **T'au holds even** despite ALSO being a Shooty camping army (Crisis suits are
  Shooty and get pinned by the same in-range hold): its firepower is lethal
  enough to break Death Guard (185 damage dealt, Death Guard reduced to 15
  percent survivors) so it survives the objective game via raw killing. Rubric
  Marines (ranged damage per activation 0.94, All-Is-Dust) cannot — their guns
  are too weak to break Death Guard's durability, so camping simply cedes the
  primary.
- **Grey Knights** ends with only 1.12 units on objectives (versus Death Guard
  3.30) — it has too few bodies (24 starting) to cover the board at all. This is
  the pure low-model floor, and it is mostly why removing the contagion still
  leaves it at 71 percent.

### Role asymmetry is why the spread happens

Death Guard's roster spreads onto objectives; the Thousand Sons scoring core
does not:

| Unit | Faction | Role | Behaviour |
|---|---|---|---|
| Plague Marines | Death Guard | Dual | goes to objectives (attrition posture) |
| Blightlord / Deathshroud Terminators, Chaos Lord | Death Guard | Melee | close on nearest enemy / objectives |
| Poxwalkers, Cultists | Death Guard | Horde | bodies onto objectives |
| Rubric Marines | Thousand Sons | **Shooty** | **pinned in place when enemy in 24-inch range** |

Grey Knights units (Strike, Terminator, Paladin) are all Melee and DO close, so
their crater is the body-count floor, not the pin.

## Named lever direction (not built, per brief)

The addressable amplifier is the elite-gunline objective-contest gap, NOT the
contagion. The lever: a movement-artificial-intelligence behaviour that, for a
Shooty / gunline unit whose army is BEHIND on the primary marker count, relaxes
the in-range hold and pushes a redundant scoring body (a second unit doubled on
an already-held marker) to contest an enemy-held or uncontested objective — the
"contest the objective majority when losing the primary" cousin of the adopted
ranged-hold family. It is cross-cutting: the same Shooty-pin under-holds
objectives in every gunline-elite matchup, so it plausibly deflates those
armies' overall under-poles (Thousand Sons minus 7.6, Emperor's Children minus
10.6) at the same time as Death Guard's over-pole — one fix, multiple poles.

Two honesty caveats on that lever:

1. It would REDUCE, not eliminate, the crater. Toggling the existing Thousand
   Sons ranged-hold off (letting Rubrics Advance) moves Death Guard only 85.0 to
   78.8 and barely changes the spread (+0.90 to +0.88) — Rubrics that simply
   advance get ground in the Death Guard grind rather than cleanly contesting.
   The lever must SPREAD scoring bodies to distinct uncontested markers, not just
   advance them.
2. Its ceiling is bounded by the floor. The T'au case shows Death Guard edging
   the marker count (1.59 to 1.29) even when the opponent puts MORE units on
   objectives (3.86 to 1.30), because Death Guard's durable holders win the
   Objective Control contest on shared markers. Grey Knights is essentially all
   floor and this lever would not touch it.

## Bottom line

Faithful rules produce most of this crater. The Death Guard contagion (D1/D2/D3)
is faithful and is a minor amplifier (about six to eight points), not the cause —
do not revert it. The dominant cause is the Stage-1 structural durability /
model-count objective over-reward the project already tracks, sitting under an
addressable artificial-intelligence play gap where elite gunlines cede the
objective majority. Stage-2 pricing must carry the floor; the objective-contest
artificial-intelligence lever is the cross-cutting Stage-1 opportunity.
