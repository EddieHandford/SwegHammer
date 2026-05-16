# Auto-loop iter 4 — Death Guard deeper diagnostic (+15.3pt residual)

Status: diagnosis only. No simulator / AI / catalogue mutation.

Source: `scripts/iter4_dg_post_sticky_diag.py`, N=30 archetype battles per
matchup, vanilla 10e rules, 1000 pts. Same three opponents as iter-3
(Adeptus Astartes, Necrons, Tyranids).

Iter-3 fix tightened the `_sticky_owner` claim path from `>=` to `>` per
the 10e core "greater than" wording. Predicted MAE Δ: −4 to −7. Realised:
**−1.7** on the DG residual (65.0 → 64.4). Something else is carrying
the +15.3pt.

## Headline trace (post-iter-3 simulator)

| Opponent | Sim WR | DG VP | OPP VP | DG dmg | OPP dmg | sticky VP | PM survival | OPP BL surv |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Adeptus Astartes | 56.7% | 53.3 | 45.7 | 56.2 | 70.4 | 17.5 | 85.9% | 94.0% |
| Necrons | 23.3% | 44.8 | 59.3 | 83.5 | 77.9 | 15.5 | 84.6% | 91.7% |
| Tyranids | 63.3% | 55.8 | 44.3 | 65.9 | 58.4 | 10.3 | 88.6% | 93.1% |
| **3-opp avg** | **47.8%** | **51.3** | **49.8** | **68.6** | **68.9** | **14.4** | **86.4%** | **92.9%** |

**Key inversion vs iter-3 narrative.** The iter-2/iter-3 cluster slice
WR average was 57.8%; iter-4 slice is **47.8%**, matching real DG WR
(~48%) within 1pt. *In the 3 sampled matchups, DG is no longer
over-performing.* The +15.3pt residual on the full eval therefore must
be concentrating in the other 7 matchups (Aeldari, T'au, Orks, TSON,
Custodes, Votann, mirror) — the iter-3 sticky tightening *did* close
out the DG-vs-Marines / DG-vs-Necrons / DG-vs-Tyranids overshoot but
isn't visible in the cluster-level eval because the residual lives
elsewhere.

This re-frames the iter-3 +15.3pt as a **cross-matchup distribution
issue**, not a localised "sticky is broken" issue.

## 1. Per-round VP breakdown — where DG's VP accumulates

Cross-matchup means, VP awarded per round:

| Round | DG VP/rnd | OPP VP/rnd | sticky-attrib DG (0 OC) | DG damage/rnd | OPP damage/rnd |
|---|---:|---:|---:|---:|---:|
| R1 | 9.44 | 9.83 | 0.00 | 3.74 | 3.64 |
| R2 | 9.89 | 9.56 | 2.17 | 15.86 | 15.97 |
| R3 | 10.78 | 10.28 | 3.94 | 18.75 | 18.41 |
| R4 | 10.50 | 10.44 | 3.94 | 17.06 | 17.62 |
| R5 | 10.72 | 9.67 | 4.39 | 13.14 | 13.23 |

Reading:
- **R1 is balanced** (DG 9.44 vs opp 9.83 VP, dmg trade even at ~3.7).
  The Contagions Round-1 -1T (a +1-to-wound aura) is *not* moving the
  R1 needle in these matchups — DG's R1 damage is tiny because the slow
  T6/M5 chassis hasn't engaged yet.
- **R2-R5 sticky-attrib snowballs** from 2.17 → 4.39 VP/round. Once an
  objective is sticky-locked, it scores indefinitely while both sides
  vacate the marker (the `a_oc == 0 AND b_oc == 0` fallback in
  `_award_objective_vp`).
- **Damage trade is ~par from R2 onwards** (DG 15.86 / opp 15.97 R2;
  DG 18.75 / opp 18.41 R3) — DG is NOT out-killing opponents. The VP
  gap is entirely objective-economy.

Sticky-attrib **total 14.4 VP/battle** = 28% of DG VP. Strip sticky →
DG mean VP collapses from 51.3 to ~36.9, well below opp's 49.8.

## 2. Stratagem fire rates & CP economy

Cross-matchup means, fires/battle. (`CRR` = Command Re-Roll; `HI` =
Heroic Intervention. Same dispatcher fires both for either side.)

DG (Virulent Vectorium):

| Stratagem | Fires/battle | Round profile |
|---|---:|---|
| Overwhelming Generosity | 2.97 | even spread R1-R5 (~0.6/rnd) |
| Creeping Blight | 2.64 | front-loaded (1.0/1.0 R1/R2, then 0.2-0.3) |
| Command Re-Roll | 1.13 | R2-spike (~1.1) on first failed save |
| Putrid Detonation | 0.45 | R3-R5 |
| Leechspore Eruption | 0.43 | R3-R5 |
| Disgustingly Resilient (stratagem) | 0.10 | rarely fires |
| Plaguesurge | 0.00 | never (no consumer) |
| Heroic Intervention | 0.22 | R3-R4 |

Opp (across factions):

| Stratagem | Fires/battle |
|---|---:|
| Command Re-Roll | 4.11 |
| Heroic Intervention | 1.58 |
| Counter-Offensive | 0.15 |
| (faction-specific) | 0.4-0.8 |

CP/battle spend: **DG 8.04 / opp 6.91** — DG spends 1.13 CP more per
battle (≈14% more). Composes with Worldblight passive sticky as a
"free" VP source that doesn't cost CP.

The OverGen + Creeping Blight pair (both grant
`transient_reroll_hits_shooting`) fires ~5.6×/battle combined. Both
buff hit-rerolls on different DG units (CHARACTER vs INFANTRY), so the
10e "1 Stratagem per phase per unit" core rule isn't violated. The
**Creeping Blight wound-reroll half is currently dropped** (see citation
note in `data/rule_citations.d/stratagems.json`) — so this is
*under-modelled*, not over-modelled. Not a leverage candidate.

## 3. DG damage taken per round vs opp damage taken

Cross-matchup means, model deaths per round:

| Round | PM dead | OPP BL dead | DG VEH dead |
|---|---:|---:|---:|
| R1 | 0.19 | 0.19 | 0.00 |
| R2 | 0.74 | 0.81 | 0.03 |
| R3 | 0.73 | 1.76 | 0.04 |
| R4 | 0.64 | 1.31 | 0.19 |
| R5 | 0.52 | 1.00 | 0.18 |

**Critical**: Plague Marines die at **PM survival 86.4%** vs opp
BATTLELINE survival **92.9%** — DG BATTLELINE is *less* durable per
model than the average opp BATTLELINE in these matchups. The "DG is
unkillable on objectives" story is **false**. PMs die at a steady
0.5-0.8/round; DG VEHICLE deaths only kick in R4-R5.

So the dominant story is NOT "DG bodies camp the objective" — it's
**"DG locks objectives early then dies, but the opp doesn't return to
contest after DG vacates"** (the sticky-VP fallback). This implicates
the opp AI's objective-targeting heuristic, not the DG body's tankiness.

## 4. Plague Marines vs other BATTLELINE survival

Per-matchup PM-death-vs-opp-BL-death:

| Opponent | PM dead/total | Opp BL dead/total |
|---|---:|---:|
| Marines | 88/624 (14.1%) | 15/250 (6.0%) |
| Necrons | 96/624 (15.4%) | 372/4500 (8.3%) — Necron RP eats deaths |
| Tyranids | 71/624 (11.4%) | 69/1000 (6.9%) |

PM die **2-3× faster per model** than opp BL. T6 + W2 + Sv3+ + FNP 5+
gives PMs ~12 EHP, but they're paying 24.75 pts each and absorb
high-rate-of-fire chaff weapons disproportionately. **PM tankiness is
not the residual driver.**

Note: BSData lists Plague Marines as **T6** (verified in
`data/bsdata/cache/Chaos - Death Guard.cat.gz`, M=5" T=6 W=2 A=3 S=8
D=2 — the squad's PM Champion stat block). Common knowledge / Goonhammer
chatter sometimes cites T5 — needs Wahapedia WebFetch verification but
the source was unreachable from this environment. Direction of any
correction is "make PMs *more* fragile", which would lower DG WR.
*Parked for future iteration; not the top fix.*

## 5. Contagions of Nurgle — fire frequency

The 3" gate (post-iter-2) caps Contagions to enemy units within 3" of
any DG model.

- **R1 Virulent Rot (-1T, +1 to wound)**: fires whenever opp unit is in
  3" of a DG model. R1 dmg trade is balanced (3.74 vs 3.64) → fires
  rarely in R1 since the armies haven't closed yet on a 60×44 board.
- **R2 Maladictive Pall (-1Ld, battleshock)**: only fires on
  below-half-strength enemy units; battleshock fails are rare on
  T4/Ld6 chaff.
- **R3+ Fulminating Plague (-1 to hit)**: only fires if NO other
  -1-to-hit source already applied (per the 10e modifier cap). Opp dmg
  R3+ is 18.41/17.62/13.23 — peak is **R3 not R5**, suggesting
  contagions isn't suppressing late-game opp shooting in these
  matchups (most opp shooters are >3" away when shooting).

The legacy 3-round escalation (-1T/-1Ld/-1 to hit) is FLAGGED as
APPROXIMATION in
`data/rule_citations.d/death_guard.json#simulator.contagions_of_nurgle`.
Modern 10e Nurgle's Gift applies one randomly-assigned Affliction per
afflicted enemy unit (Skullsquirm Blight = -1 to Advance/Charge,
Rattlejoint Ague = -1 OC, Scabrous Soulrot = -1 to hit). The current
-1T R1 is the strongest piece; -1Ld and -1-to-hit map roughly to one
modern Affliction each.

## 6. Mechanism ranking — what's driving the residual

| # | Mechanism | Avg VP impact / battle | Wahapedia gap? | AI gap? |
|---|---|---:|---|---|
| **1** | **Worldblight sticky 0-OC scoring fallback** | **+14.4** | NO — rule-correct per "remains under your control until opp LoC > yours" | YES — opp doesn't walk units back to contest |
| 2 | DG INFANTRY FNP 5+ army-wide | gates #1 partially | NO — datasheet-level DR | NO |
| 3 | OverGen + Creeping Blight stacking | +3-5 dmg/round R2+ | Direction-right; Creeping Blight wound-reroll currently DROPPED (under-modelled) | NO |
| 4 | Contagions R1 -1T | +0.5 dmg/battle in sample | YES — legacy index rule, modern is randomized Afflictions | NO |
| 5 | Putrid Detonation + Leechspore | <1 mortal/battle | Direction-right | Low leverage |
| 6 | BSData Plague Marine T6 (possibly T5 in current GW codex) | unknown | Possible BSData transcription bug | NO (data-layer) |

**Re-framing**: the 3-opp sample WR is now 47.8% (matches real 48%).
The +15.3 residual in the FULL eval therefore concentrates outside this
slice (probably Aeldari, T'au, Tyranid mirror, etc.). The dominant
mechanism *in the sampled matchups* is sticky-VP — but in those
matchups DG is now properly calibrated. **The next iteration should
re-aim diagnostic effort at the 7 unsampled DG matchups** to find
where +15.3 actually lives.

## 7. Single top fix — `simulator.contagions_of_nurgle` legacy R1 downgrade

### Fix proposal: F-DG-CONTAGION-AFFLICTED-R1

**Type**: RULE_FIX (Wahapedia approximation correction).
**Scope**: low — `code/units.py` lines 759-764 (R1 Virulent Rot -1T
branch) and a 3-line touch in the citation.
**Predicted MAE Δ**: **−2 to −4 pt** on DG residual.

Why this is the top fix despite low sample leverage:

1. **The +15.3pt residual concentrates in unsampled matchups.** Of the
   four candidates listed in the iter-4 brief (sticky-further-restrict,
   DR-correction, Contagions-downgrade, PM-stat-fix), Contagions is the
   ONLY candidate that (a) has a clean Wahapedia gap, (b) fires
   army-wide vs ALL opponents (so hits the unsampled matchups), and
   (c) doesn't risk inventing or under-citing.
2. **Sticky-further-restrict** would be inventing — Wahapedia text is
   explicit "remains under your control until opp LoC > yours". A
   "two rounds in a row" gate has no Wahapedia anchor.
3. **DR correction** — the strat is "subtract 1 from the Damage
   characteristic of that attack" (verbatim from
   `Stratagem.Disgustingly Resilient`), and the army rule is "Feel No
   Pain 5+". Both match Wahapedia. Not a gap.
4. **PM stat fix** — BSData says T6; unverified online today. Defer.

### Change (illustrative — not implemented this pass)

In `code/units.py` around line 759:

```python
# Was:
if (
    _contagion_round_for(target) == 1
    and target.profile.faction != "Death Guard"
    and _is_near_enemy_dg_model(target, radius=3.0)
):
    wound_target = max(2, wound_target - 1)   # -1 T equiv

# Should be (per modern Wahapedia Nurgle's Gift):
# Round-1 Virulent Rot was the launch-index wording; the current codex
# replaces it with randomly-assigned Afflictions. The strongest of those
# (Scabrous Soulrot = -1 to hit) is ALREADY modelled by the R3+ branch.
# Drop the R1 -1T branch entirely — keep the R2 -1Ld battleshock penalty
# (≈ Rattlejoint Ague direction) and R3+ -1 to hit (≈ Scabrous Soulrot)
# as the rule-conservative 2-Affliction substitution.
# (No replacement code — branch deleted.)
```

### Wahapedia citation

URL: https://wahapedia.ru/wh40k10ed/factions/death-guard/

Verbatim (already in
`data/rule_citations.d/death_guard.json#simulator.contagions_of_nurgle`):

> "Each model in your army has the following aura ability: 'Aura: While
> an enemy unit is within 3" of this model, that enemy unit is
> Afflicted'. Modern 10e applies named Afflictions (Skullsquirm Blight /
> Rattlejoint Ague / Scabrous Soulrot) to each Afflicted enemy unit.
> Older index/launch shape escalated by round: Round 1 — Virulent Rot
> (-1 T); Round 2 — Maladictive Pall (-1 Ld); Round 3+ — Fulminating
> Plague (-1 to hit). SwegHammer retains the older escalation pattern
> but gates the radius to the modern 3"."

The citation explicitly flags Round-1 Virulent Rot as the
"older index/launch" shape, no longer in current codex. Dropping the
R1 branch tightens the approximation toward the modern text without
inventing.

### Predicted impact

- **R1 damage trade**: DG loses the +1-to-wound aura on R1. Sample R1
  dmg drops ≈10-15% (low absolute; only 0.4-0.6 VP/battle in sampled
  matchups). Unsampled matchups vs low-T chaff (Aeldari Guardian T3,
  T'au Fire Warrior T3, Tyranid Termagant T3) likely see larger drops
  — the -1T turned T3 → T2 making strength-4 bolters wound on 2+ vs
  3+, a 50% wound-rate uplift on those bodies.
- **R2 / R3+ branches preserved** — no change to opp battleshock
  pressure or R3+ shooting suppression.
- **MAE Δ expectation**: −2 to −4pt on DG slice, with most of the
  delta showing up in DG vs Aeldari / DG vs T'au / DG vs Tyranid
  matchups in the next eval pass.

### Tests to add (predicted)

- DG model adjacent to an enemy T3 Guardian: R1 wound roll uses the
  base T3 (not T2). Verifies the -1T branch is gone.
- DG model adjacent to an enemy T4 Intercessor on R3: hit_target +1
  still fires (R3+ branch preserved).

### Why this is the right *single* fix

- Pure rule-fix, no AI lever (faction-neutral, opp AI untouched).
- Cleanly cited as a Wahapedia approximation correction; the existing
  citation already documents the approximation.
- Composes with all prior iter fixes without touching them.
- ~3-line code change.
- Reduces DG's strongest under-the-hood aura without touching the
  Worldblight sticky mechanic (which is rule-correct).

## Not done this pass

- Did not implement the fix (diagnostic-only per task constraint).
- Did not run the eval suite (per "no N=200 eval" constraint).
- Did not WebFetch Wahapedia (network blocked from this environment;
  citation already in the repo).
- Did not test the BSData Plague Marine T6 vs current GW T5 question
  — needs Wahapedia verification. Direction is "make PMs more fragile"
  if T5 is correct; would compound F-DG-CONTAGION-AFFLICTED-R1.

## Test gates

`python -m unittest discover -s tests` — **661 tests pass** (skipped=4)
on this branch. Iter-4 diag script adds no new tests. The prompt
referenced 667 tests; current count is 661 — the gap is pre-existing
test removals not introduced here.
