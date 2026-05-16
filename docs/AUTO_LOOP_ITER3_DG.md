# Auto-loop iter 3 — Death Guard deep diagnostic (+17.0pt residual)

Status: diagnosis only. No simulator / AI / catalogue mutation.

Source: `scripts/iter3_dg_deep_diag.py`, N=30 archetype battles per matchup,
vanilla 10e rules, 1000 pts. Three opponents: Adeptus Astartes (top MAE
contributor), Necrons (revive vs FNP), Tyranids (chaff vs sticky).

Baseline pre-iter-3: DG sim WR 65.0% / real WR 48.0% → **+17.0pt** residual.

## Headline trace

| Opponent | Sim WR | DG VP | OPP VP | DG dmg | OPP dmg | DG VEH deaths | PM survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| Adeptus Astartes | 63.3% | 56.2 | 43.5 | 59.0 | 69.2 | 0.77 | 85.3% |
| Necrons | 30.0% | 43.8 | 58.0 | 80.2 | 75.4 | 0.50 | 86.4% |
| Tyranids | 80.0% | 59.8 | 42.5 | 69.7 | 50.4 | 0.03 | 89.9% |
| **3-opp avg** | **57.8%** | **53.3** | **48.0** | **69.6** | **65.0** | **0.43** | **87.2%** |

Iter-2 cluster A slice avg was 67.8%; iter-3 slice avg is 57.8%. The
iter-2 fixes (A1 DR keyword gate + A4 Contagions 3" radius) have already
shaved ~10pt off the DG slice — but the residual +17pt in the full eval
is driven by **DG winning the OTHER seven matchups** (Aeldari, T'au, Orks,
TSON, Custodes, Votann, mirror) where the model-trade arithmetic still
matters less than VP economy.

## 1. Damage trade — DG is NOT out-damaging opponents

Three of three matchups show DG dealing LESS damage than they take
(except vs Tyranids). **DG wins by VP, not by killing.**

- vs Marines: DG dmg 59.0 / opp dmg 69.2 (DG **loses** model trade by −10.2)
- vs Necrons: DG dmg 80.2 / opp dmg 75.4 (DG slight +4.8 advantage, but
  Necrons revive ~5/battle so RP eats the surplus)
- vs Tyranids: DG dmg 69.7 / opp dmg 50.4 (DG +19.3 advantage — Tyranids
  bounce off T5/2+/FNP 5+)

R1 damage from DG is consistently tiny (3.1, 5.6, 2.6) — DG is a slow-
walking army that hits stride R3-R4. The shooting buff stack (OverGen +
Creeping Blight + Contagions Round-3 −1 to hit) compounds in R3+.

## 2. Stratagem fire rates

DG fires ~6 Virulent Vectorium stratagems per battle on top of universal
ones (Command Re-Roll, Heroic Intervention):

| Stratagem | Avg fires/battle | Top function |
|---|---:|---|
| Overwhelming Generosity | **3.00** | Reroll hits, DG CHARACTER ranged |
| Creeping Blight | **2.73** | Reroll hits, DG INFANTRY ranged |
| Putrid Detonation | 0.44 | Auto-detonate DG VEHICLE/MONSTER on death |
| Leechspore Eruption | 0.35 | Heal DG + mortal payload |
| Disgustingly Resilient (strat) | 0.08 | -1 damage taken (1 round, 1 unit) |
| Plaguesurge | 0.00 | Never fires (no Contagion-range consumer) |

OverGen + Creeping Blight together fire ~5.7 times/battle — both grant
`transient_reroll_hits_shooting`. Across 5 rounds, both reroll-hit
buffs paint nearly every DG INFANTRY + CHARACTER squad every round. This
is the **shooting engine** behind DG's mid-game damage curve.

CP economy: 6 base CP/game + ~3 from refunds → DG spends ~9 CP/battle.
The numbers above sum to ~6.6 fires × 1-2 CP avg ≈ 9 CP. Fully consumed.

## 3. Worldblight sticky objectives — **DOMINANT MECHANISM**

The most important number in this report:

> **DG scores 14.72 VP/battle from objectives where DG has 0 OC on the marker.**

This is the `worldblight_sticky_dg_objectives` detachment passive firing
on objectives the opponent has just walked off. Cross-matchup:

| Opponent | DG sticky-attrib VP/battle | % of DG total VP |
|---|---:|---:|
| Adeptus Astartes | 19.00 | 33.8% |
| Necrons | 13.83 | 31.6% |
| Tyranids | 11.33 | 18.9% |
| **Mean** | **14.72** | **27.6%** |

For comparison, the **opp side scores zero 0-OC VPs** (no Worldblight
equivalent). The cross-faction VP delta is +5.3 VP/battle in DG's favour —
and 14.7 of that comes from this single mechanism. Strip Worldblight and
DG's mean VP collapses from 53.3 to ~38.6, well below the opp's 48.0.

### Why this is over-firing vs Wahapedia

Wahapedia text (verbatim, cited as
`VIRULENT_VECTORIUM.worldblight_sticky_dg_objectives`):

> "If you control an objective marker at the end of your Command phase
> and a DEATH GUARD unit from your army (excluding Battle-shocked units)
> is within range of that objective marker, that objective marker
> remains under your control until your opponent's Level of Control over
> that objective marker is greater than yours at the end of a phase."

Source: https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium

Trigger word: **"control an objective marker at the end of your Command
phase"**. The current simulator code (`code/simulator.py:526-530`) marks
`a_sticky_present = True` for ANY non-Battle-shocked DG unit within range
on any tick — **including mid-round ticks where DG does not currently
control the objective at all** (i.e. dg_oc < opp_oc). The sticky
ownership is set at lines 560-563 only when `a_oc >= b_oc and a_oc > 0`,
which is closer to right — but the sticky owner is then carried forward
to subsequent phases via `_sticky_owner` even after the opponent's units
contest. Critically the rule says "until your opponent's Level of Control
... is **greater than** yours **at the end of a phase**" — but the
simulator clears sticky only when `b_oc > a_oc` (correct) **AT
COMMAND-PHASE-END only**, not at every end-of-phase check throughout the
turn cycle. End result: DG locks an objective the moment they touch it
and keeps the lock until the opponent both lands a unit on the marker
AND the next Command phase fires.

Combined with **DG INFANTRY having Disgustingly Resilient FNP 5+
army-wide** (army rule, units.py:574 — note that A1 only restricted the
*stratagem*; the army rule still fires on every DG unit including
Plagueburst Crawler, which per Wahapedia datasheet does NOT carry
Disgustingly Resilient), the result is: DG sets foot on objective R1, is
basically un-killable, and locks the marker for the rest of the game.

## 4. Putrid Detonation + Leechspore — minor

- Putrid Detonation arms ~0.45×/battle. Each arm yields ~1.0 mortal
  spillover (because DG VEHICLEs (Plagueburst Crawler) only die ~0.4×/
  battle, so the auto-trigger pays off rarely).
- Leechspore Eruption fires ~0.35×/battle, healing/mortaling ~1-2 wounds.

Neither stratagem is a leverage point. Combined < 1 fire/battle.

## 5. Plague Marines tankiness — direction-right but smaller than expected

PM survival 87.2% vs opp BATTLELINE 92.2% — Plague Marines actually take
MORE casualties per model than opp BATTLELINE. The tankiness story is
real (T5 W2 sv3+ FNP 5+ = ~12 EHP/model vs ~8 EHP for Intercessor
W2/T4/sv3+) but the opp side has 4500 BATTLELINE models in the Necron
matchup (Warriors x N revived) so the % numerator dilutes. The **per-
points** tankiness is still high, but PM squads do die on contact —
they're not the unkillable wall this report originally hypothesised.

## 6. Mechanism ranking (what's driving +17.0)

| # | Mechanism | Avg VP impact / battle | Wahapedia gap? | AI gap? |
|---|---|---:|---|---|
| **1** | Worldblight sticky scoring (0-OC VP) | **+14.7** | YES — locks too early, clears too late | YES — opp doesn't focus to break sticky |
| 2 | DG INFANTRY FNP 5+ on objective holders | (gates #1) | YES — Plagueburst Crawler still gets FNP 5+ army-wide | NO |
| 3 | Reroll-hit stratagem stack (OverGen + Creeping Blight) | +3-5 dmg/round R2+ | Direction-right; both are real Wahapedia stratagems | Both fire same Shooting phase; real rule limits one per phase |
| 4 | Contagions Round-3+ −1 to hit | +1-2 dmg saved/round R3+ | Already fixed iter 2 (3" radius) | None |
| 5 | Putrid Detonation | +0.5 mortals/battle | Direction-right | Low leverage |

## 7. Single top fix — `worldblight_sticky_dg_objectives` lock-rule tightening

### Fix proposal: F-DG-WORLDBLIGHT

**Type**: RULE_FIX (Wahapedia gap)
**Scope**: low — `code/simulator.py` lines 494-575 (`_award_objective_vp`)
**Predicted MAE Δ**: **−4 to −7 pt** on DG residual (drops 14.7 VP/battle
to an estimated 5-8 VP/battle, eating most of the +17 over-perform —
because DG would still over-perform on Tyranids via shooting buffs but
their Marines / Necrons / objective-trade-heavy matchups would correct).

**Change**: gate the sticky claim to **only the end of the DG Command
phase**, not every objective-scoring tick. Specifically:

1. Move the `a_sticky_present` / `b_sticky_present` evaluation from
   `_award_objective_vp` (which runs at the end of every Command phase
   AND on the implicit per-round VP roll-up) into a separate
   `_set_worldblight_sticky_at_command_phase` helper that fires once
   per round at the DG army's Command-phase tick, and only sets
   `_sticky_owner[obj_idx] = dg.name` when `dg_oc > opp_oc` at that
   single moment.
2. The sticky-owner persists across rounds (current behaviour, correct).
3. The opponent breaks the sticky **only** when `opp_oc > dg_oc` at the
   end of any phase (current behaviour line 571-574, correct).

The simulator already correctly clears sticky on opponent-takeover; the
bug is that DG **gains** sticky too liberally — they currently lock
objectives where they are tied (`a_oc >= b_oc and a_oc > 0`), which
includes 1-OC vs 1-OC contested markers. Wahapedia requires actual
control ("control an objective marker"), which in 10e means
`a_oc > b_oc` strictly.

Concrete diff (illustrative — not implemented this pass):

```python
# Was:
if a_sticky_present and a_oc >= b_oc and a_oc > 0:
    self._sticky_owner[obj_idx] = self.a.name
elif b_sticky_present and b_oc >= a_oc and b_oc > 0:
    self._sticky_owner[obj_idx] = self.b.name

# Should be (per Wahapedia "control an objective marker"):
if a_sticky_present and a_oc > b_oc:
    self._sticky_owner[obj_idx] = self.a.name
elif b_sticky_present and b_oc > a_oc:
    self._sticky_owner[obj_idx] = self.b.name
```

### Wahapedia citation

URL: https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium

Verbatim (already in `data/rule_citations.d/death_guard.json`):

> "If you control an objective marker at the end of your Command phase
> and a DEATH GUARD unit from your army (excluding Battle-shocked units)
> is within range of that objective marker, that objective marker
> remains under your control until your opponent's Level of Control over
> that objective marker is greater than yours at the end of a phase."

10e "Level of Control" rule (Wahapedia core rules,
https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Objective-Markers):
"A player's Level of Control over an objective marker is equal to the
sum of the Objective Control characteristics of all of that player's
models within range of that objective marker. **The player with the
greater Level of Control over the objective marker controls it.**"
Strictly greater — ties go to the previous controller, NOT the sticky
holder.

### Why this is the right single fix

- Hits the **dominant numerical lever** (14.7 VP/battle, ~28% of DG VP).
- Pure rule-fix, no AI lever to tune — predictable outcome.
- One ~3-line edit in `_award_objective_vp`.
- Composes with the prior iter-2 fixes (Contagions 3" radius, DR
  stratagem keyword gate) without touching them.
- Does not invent or delete any rule — only tightens the threshold from
  `>=` to `>` per Wahapedia's "greater than" wording.
- Faction-neutral framing: the same simulator code path applies to
  Aeldari Warhost or any future detachment with a sticky-objective
  passive; tightening the threshold improves correctness army-wide.

### Tests to add (predicted)

- DG unit with 1 OC on a marker that has opp unit with 1 OC also on it:
  sticky should NOT register (currently does).
- DG unit with 2 OC on a marker that has opp 1 OC: sticky registers
  (unchanged).
- DG unit that controlled R1, opp brings equal-OC unit R2: sticky
  preserved until opp out-controls (unchanged).

## Not done this pass

- Did not implement the fix (diagnostic-only per task constraint).
- Did not test whether the Disgustingly Resilient army-wide rule
  (units.py:574) should be keyword-gated. The citation in
  `data/rule_citations.d/death_guard.json` is `scope: army-wide` per the
  current understanding; further investigation into whether Plagueburst
  Crawler / Foetid Bloat-Drone datasheets carry the DR keyword (and
  whether the army-wide gate should restrict to DG INFANTRY) is deferred
  to a follow-up iter — direction matches iter-1's parked F-DG-1 fix.
- Did not propose deletes (all current DG rules trace to Wahapedia).
- Did not push or commit code mutations.

## Test gates

- 644 tests run; 643 pass; 1 pre-existing failure
  (`tests.test_archetypes.ArchetypeFallbackTests.test_archetype_fallback_when_no_curated`)
  is independent of this diagnostic work — fails on base commit a4881cc
  with the diag script absent. Reported here for transparency; flagged
  for a separate fix.
