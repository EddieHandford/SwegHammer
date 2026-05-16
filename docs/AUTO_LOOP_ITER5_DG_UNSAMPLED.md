# Auto-loop iter 5 — DG diagnostic for the 7 UNSAMPLED matchups

Status: diagnosis only. No simulator / AI / catalogue mutation.

Source: `scripts/iter5_dg_unsampled_diag.py`, N=30 vanilla battles per
matchup, 1000 pts, archetype builder OFF, no run.py, no eval suite.

Iter-4 framing: the 3 sampled DG opponents (Marines / Necrons / Tyranids)
calibrated to 47.8% WR vs the real 48%, so the +15.3pt DG residual on the
full eval lives in the OTHER 7 matchups. This iteration samples those.

## Headline

| Opponent (DG vs) | WR | DG VP | OPP VP | gap | sticky VP | PM srv | OPP BL srv | DG dmg | OPP dmg | DG strats | OPP strats |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Aeldari | 76.7% | 49.5 | 34.8 | +14.7 | 12.7 | 87.5% | 92.0% | 65.1 | 73.6 | 8.50 | 7.67 |
| T'au Empire | 36.7% | 34.8 | 47.7 | -12.8 | 9.7 | 81.9% | 89.9% | 56.9 | 84.0 | 8.30 | 7.00 |
| Orks | 63.3% | 55.0 | 42.8 | +12.2 | 13.3 | 88.9% | 95.6% | 64.3 | 68.5 | 8.73 | 7.93 |
| Thousand Sons | 53.3% | 54.8 | 38.8 | +16.0 | 14.8 | 83.3% |  n/a  | 60.9 | 78.0 | 8.40 | 7.93 |
| **Adeptus Custodes** | **76.7%** | 53.8 | 30.2 | **+23.7** | **16.7** | 77.8% | 96.0% | **36.3** | 89.3 | 8.80 | 7.23 |
| Leagues of Votann | 53.3% | 51.0 | 48.2 | +2.8 | 11.5 | 81.9% |  n/a  | 65.8 | 72.6 | 8.40 | 7.47 |
| Death Guard (mirror) | 56.7% | 52.7 | 51.3 | +1.3 | 12.0 | 90.3% | 88.9% | 59.4 | 65.9 | 9.10 | 8.63 |
| **7-opp MEAN** | **59.5%** | 50.2 | 42.0 | +8.2 | **13.0** | 84.5% | — | 58.4 | 75.7 | 8.60 | 7.69 |

(BL "n/a" = random builder drafted no opp BATTLELINE in 30 builds — TSON and
Votann each have one BL profile available but the no-archetype random pool
sometimes skips them.)

**Slice mean 59.5%** vs real DG meta ~48% → **+11.5pt over** in the 7
unsampled matchups. Composed with the iter-4 3-opp slice (47.8%, real
48%, +0pt), the overall DG residual is dominated by THIS slice. iter-4
brief's +15.3pt was correctly localised.

## Dominant residual mechanism — Worldblight sticky × low-model opponents

Strongest single signal: **sticky-attributed VP is inversely correlated
with opp model count.**

| Opponent | OPP models | sticky VP | WR |
|---|---:|---:|---:|
| Adeptus Custodes | 30 | 16.7 | 76.7% |
| Thousand Sons | 39 | 14.8 | 53.3% |
| Aeldari | 55 | 12.7 | 76.7% |
| Orks | 57 | 13.3 | 63.3% |
| Death Guard | 64 | 12.0 | 56.7% |
| T'au Empire | 69 | 9.7 | 36.7% |
| Leagues of Votann | 71 | 11.5 | 53.3% |

The Custodes line is the textbook case: DG dmg→opp is the LOWEST in the
slice (36.3 — Custodes T6/T7 W3+, 4++ invuln, DG can't crack them) and
OPP dmg→DG is the HIGHEST (89.3 — Custodes elite shooting + melee carves
PMs steadily). DG **loses the damage race by 53 dmg/battle** yet wins
76.7% of battles because Custodes (30 models on board) cannot park
enough OC tokens on enough objectives to break the Worldblight sticky
fallback. DG vacates the marker R3+ as PMs die, but no Custodes unit
returns to the marker, so the `a_oc == 0 AND b_oc == 0` fallback awards
DG the VP per `_score_objectives`. Same shape against Aeldari, TSON,
Orks.

T'au is the inversion (36.7% — DG's only losing matchup): T'au's
S5/AP-1 mass shooting + 69 models per army puts DG dmg→opp at only
56.9 *and* OPP dmg→DG at 84.0 — DG bodies die before sticky can latch
(sticky VP just 9.7, the lowest in the slice). T'au is the ONE
unsampled matchup where simulator-DG matches the real-meta DG WR
direction (DG ~45% vs T'au in real meta).

Stratagem economy is structurally tilted DG-side in every matchup:
**DG fires 8.3-9.1 stratagems/battle vs opp 7.0-8.6.** The 1-2-fires-
per-battle DG advantage comes from **Overwhelming Generosity firing at
0.83/battle R1** in every matchup — i.e. **83% of R1s activate OG**
despite DG dmg→opp R1 being only 0.7-2.5 (the DG CHARACTER unit
almost never has a viable target in R1 on a 60×44 board with terrain).

Looking under the hood of OG: `_try_overwhelming_generosity` picks the
highest-DPA DG CHARACTER and the highest-threat enemy, then fires. The
real Wahapedia text **"Select one enemy unit visible to your unit"**
requires the CHARACTER to actually **have line of sight to the target**.
The simulator drops that visibility gate — so OG fires R1 even when
the CHARACTER has no LoS to anything, wasting 1 CP for a buff that
never lands (R1 dmg trace confirms: the buff produces no measurable R1
extra damage). The CP saved would NOT have armed any other useful R1
stratagem, but it WOULD have been carried forward (CP unused this round
adds to the pool, capped at 15), giving DG a fatter pool for the
already-tight R2-R5 spend that drives the 1-2-fires/battle advantage.

## Why this is the top fix — F-DG-OG-VISIBILITY-GATE

**Type**: RULE_FIX (visibility gate per Wahapedia "visible to your
unit" wording, currently dropped).
**Scope**: low — `code/simulator.py:_try_overwhelming_generosity`
(~5 lines): after picking the highest-DPA DG CHARACTER candidate and
the highest-threat target, add a LoS check `if not
self._has_los(candidate, target): return` (or skip to next candidate
if implemented as a loop). The simulator already has visibility
helpers used in shooting target selection — reuse.
**Predicted MAE Δ**: **-2 to -4 pt** on DG slice MAE.

Why this beats the other candidates:

1. **Wahapedia-anchored, not invented.** The existing rule citation
   (`Stratagem.Overwhelming Generosity`) verbatim quotes "Select one
   enemy unit **visible to your unit**." The current implementation
   note already flags this as "approximation: ... visibility check
   omitted." This fix tightens an existing approximation toward the
   real text.
2. **Faction-neutral.** OG is DG-only by definition (Virulent Vectorium
   detachment), so the fix is automatically faction-neutral in the
   sense that no opponent AI is touched. The fix targets DG's CP
   over-use.
3. **Composes across all 7 unsampled matchups.** Data shows OG R1
   fires at 0.83/battle in EVERY matchup — the fix takes effect
   uniformly, not concentrated on one opponent.
4. **Direction-correct on Custodes outlier.** Custodes dmg in 89.3 is
   too high for DG to absorb across 5 rounds; cutting DG's R1 buff
   waste compounds to ~1 extra CP/battle that DG can no longer dump
   into Command Re-Roll (DG fires CRR 2.13-3.13×/battle). Fewer CRRs
   = fewer saved Sv 3+ on PMs = faster PM erosion = sticky lock
   breaks earlier.
5. **Composes with iter-4 A5 (1-strat-per-Command-phase) cap.** A5
   gated Command-phase strats; this gates Shooting-phase OG fires.
   Same shape (LoS-gated), no rule conflict.

### Change (illustrative — not implemented this pass)

In `code/simulator.py` around line 1115:

```python
target = self._highest_threat_enemy(opponent)
if target is None:
    return
# Wahapedia: "Select one enemy unit VISIBLE to your unit." Without LoS
# from the DG CHARACTER to the target, OG has no valid target and
# cannot be fired. The visibility helper used by shooting targeting
# is `_has_line_of_sight(candidate, target)` (or equivalent).
if not self._has_line_of_sight(candidate, target):
    return
ctx = {"attacker": candidate, "target": target}
```

### Wahapedia citation (already in
`data/rule_citations.d/stratagems.json#Stratagem.Overwhelming Generosity`)

> "WHEN: Start of your Shooting phase. TARGET: One DEATH GUARD CHARACTER
> unit from your army. EFFECT: Select one enemy unit **visible to your
> unit**. Until the end of the phase, each time a DEATH GUARD unit from
> your army selects that enemy unit as the target of any ranged
> attacks, you can re-roll the dice to determine how many attacks a
> weapon equipped by a model in that unit makes."
> — https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium

### Predicted impact

- **R1 OG fires drop from 0.83 → ~0.10** (most DG CHARACTERs have no
  LoS to any enemy in R1 on the default 60×44 map with terrain).
- **DG CP economy tightens by ~0.7 CP/battle** (R1 OG saved fires;
  unused CP capped at 15 so the saving accrues toward the late-game
  spend).
- **Command Re-Roll fires drop ~10-15%** in mid-game (the CP saved
  was the marginal CRR fire; CRR is the dominant DG sink at
  2.1-3.1/battle).
- **PM survival drops 1-3 pts** in matchups where DG saves on CRR
  (Aeldari / Orks / TSON / Custodes — the high-sticky-VP cluster).
- **Sticky-VP drops 1-3 VP/battle**: with fewer CRR saves, PMs die
  faster, DG vacates objectives faster, opp gets one extra round to
  contest, sticky lock breaks earlier.
- **MAE expectation**: -2 to -4 pt on the DG slice. Composes with
  iter-3 sticky-`>` fix and iter-4 A5 cap; nothing it touches is
  load-bearing for any other faction.

### Tests to add (predicted)

- DG CHARACTER with no LoS to any enemy (deep-set terrain) on R1:
  `_try_overwhelming_generosity` returns without firing (no
  `StratagemFired` event emitted, CP unchanged).
- DG CHARACTER with clear LoS to a visible enemy R2: OG fires as
  before (regression guard).

## Other candidates considered, rejected, why

| Fix | Rejected because |
|---|---|
| **PM stat T6→T5** | Verified via WebSearch: 10e Plague Marines ARE T6 ("All marine units in Death Guard gained a point of toughness, making T6 Plague Marines a very annoying break point to remove" — Goonhammer 10e Death Guard review surfaced by WebSearch on `"Plague Marines" "T5" OR "T6" 10th edition`). BSData is correct. No inventing. |
| **Custodes Martial Ka'tah army rule** | Not in repo. Adding it is faction-biased AI per task constraint ("don't propose faction-biased AI"). |
| **Sticky require 2-round-in-a-row hold** | Inventing — Wahapedia "remains under your control until opp LoC > yours" has no two-round gate. iter-4 already rejected this. |
| **OG drop wound-reroll half** | Wound-reroll half is already DROPPED (citation states this). Already conservative. |
| **DG vs T'au** WR fix (36.7% vs real ~45%) | T'au is the ONLY matchup where simulator UNDER-shoots DG. The +11.5pt is concentrated in the other 6 — fixing the over-shoot is higher leverage. |

## Test gate

`python -m unittest discover -s tests` — **664 tests pass** (skipped=4)
on this branch after the diag script is added. iter-5 adds no new
tests, no production-code changes.

## Not done this pass

- Did not implement the fix (diagnostic-only).
- Did not run the eval suite (per "no N=200 eval" constraint).
- Did not WebFetch Wahapedia (host unreachable from this environment;
  rule text already in the repo citation).
- Did not modify catalogue / strategy / simulator.
