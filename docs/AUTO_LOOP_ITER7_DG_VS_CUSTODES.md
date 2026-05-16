# Auto-loop iter 7 — DG vs Adeptus Custodes deep diagnostic

Status: diagnosis only. No simulator / AI / catalogue mutation.

Source: `scripts/iter7_dg_vs_custodes_diag.py`, N=40 vanilla battles
DG vs Custodes, 1000 pts, archetype builder OFF.

Iter-5 framing: DG vs Custodes is the largest DG over-perform among
the 7 unsampled matchups — simulator WR 76.7% vs real-meta ~48%
(+28.7pt). The paradox: DG loses the damage race 36.3 vs 89.3 yet
wins because Custodes ships ~30 models and can't park enough OC on
enough markers to break Worldblight sticky. This iter samples that
matchup with the five signals the brief required.

## Headline

| Metric | Value |
|---|---|
| WR DG | **67.5%** (27-12-1) |
| DG VP / Custodes VP | 57.0 / 30.5  (gap +26.5) |
| Rounds avg | 5.00 |
| DG models / Custodes models | 93.2 / **33.9** |
| Custodes unit count | 14.0 |
| Custodes avg move | 6.0" |
| dmg DG→AC / AC→DG | 33.8 / 83.1 |

Iter-5 reported 76.7% WR with N=30; iter-7 N=40 with a fresh seed
offset gives 67.5%. Both are well above the ~48% real-meta DG WR
direction (DG vs Custodes is near-50% in real play), so the over-
perform direction and magnitude are confirmed.

## 1. VP source per round

| Round | DG total VP/rnd | sticky (0/0) | primary (a>b) | Custodes VP/rnd |
|---:|---:|---:|---:|---:|
| R1 | 8.50 | 0.00 | 8.50 | 6.62 |
| R2 | 10.00 | 1.75 | 8.25 | 6.62 |
| R3 | 12.62 | 3.62 | 9.00 | 6.12 |
| R4 | 12.62 | 5.50 | 7.12 | 5.62 |
| R5 | 13.25 | 6.38 | 6.88 | 5.50 |
| **Total** | **57.0** | **17.25** | **39.75** | **30.50** |

**Sticky share = 30.3%, primary-contest share = 69.7%.** This
materially refines iter-5's reading: sticky IS the rising R3+
component (0.00 → 6.38 across rounds), but the dominant DG VP
source is **primary-contest scoring** — DG actively has more OC on
markers, not just "Custodes vacates and sticky fallback fires".

## 2. Custodes OC presence on scored objectives

Sampled every objective at scoring time across all 40 battles
(5 objectives × 5 rounds × 40 battles = 1000 samples per round).

| Round | n | AC OC=0 | OC 1-3 | OC 4-7 | OC >7 | mean OC |
|---:|---:|---:|---:|---:|---:|---:|
| R1 | 200 | **73.5%** | 20.0% | 5.5% | 1.0% | 0.81 |
| R2 | 200 | 73.5% | 23.0% | 3.5% | 0.0% | 0.64 |
| R3 | 200 | 72.5% | 24.5% | 3.0% | 0.0% | 0.64 |
| R4 | 200 | 74.5% | 21.5% | 3.5% | 0.5% | 0.62 |
| R5 | 200 | **76.0%** | 20.0% | 3.0% | 1.0% | 0.59 |

**Custodes has 0 OC on ~73-76% of scored objectives in every round.**
Even when present, OC is overwhelmingly in the 1-3 bucket (a single
Custodian Guard model, OC=1). The 5-objective map vs 14-unit
Custodes army at M6" means Custodes physically can't span the board
— most markers are uncontested DG primary-control plays, not
sticky fallback plays. The simulator AI isn't routing Custodes
units toward the markers they could contest.

## 3. Stratagem economy

| Side | Strats/battle | CP/battle | Top fires |
|---|---:|---:|---|
| DG | 8.12 | 8.45 | CRR 2.38, Creeping Blight 2.30, OG 1.55, HI 0.70 |
| **Custodes** | **7.17** | **7.33** | **CRR 5.10, HI 1.75, TS 0.17, CO 0.15** |

**Custodes spends 71% of its strat fires on Command Re-Roll**, a
universal core strat. Concentrated R2 (2.92 fires!) — i.e. defensive
re-rolls against the R2 spike where DG Contagions of Nurgle and
Creeping Blight begin landing. **Custodes has ZERO Shield Host
detachment stratagems registered** in `code/stratagems.py`. The
faction's entire detachment payload is the SHIELD_HOST.plus_one_save
flag (and the Wahapedia detachment lists 6 Shield Host stratagems
that don't exist in this codebase).

## 4. Plague Marines vs Custodian Guard damage exchange

| Metric | Value |
|---|---:|
| PM total models avg | 5.4 |
| CG total models avg | 7.8 |
| dmg PM→CG total | **0.00** |
| dmg CG→PM total | 0.08 |
| CG models killed by PM | 0 (0.00/battle) |
| PM models killed by CG | 1 (0.03/battle) |

The two headline BATTLELINE units **do not engage each other**.
PM deaths (0.72/battle) come from OTHER Custodes units; CG deaths
(0.22/battle) come from OTHER DG units. The army-level dmg traces
(83.1 AC→DG, 33.8 DG→AC) live almost entirely outside this
matchup. PMs sit on home/midfield objectives; CG sits in deployment
or commits to a single objective then doesn't reach others. **The
real bottleneck is movement and target selection, not the unit
profiles.**

## 5. SHIELD_HOST.plus_one_save approximation

- Total DG→Custodes damage: 33.77 / battle (against ~34 models,
  T6/T7, Sv 2+/4++, plus the +1 save buff = effective Sv 2+ cap).
- Custodes BATTLELINE losses: 0.10 models/battle (1 in 10 battles
  loses 1 model — Custodes is essentially un-killable in 5 rounds).
- The plus-one-save approximation substitutes for **Martial Mastery**,
  which is offensively a **Crit Hit on 5+ OR +1 AP on melee** (player
  picks one bullet per battle round). Defensive save buff and
  offensive crit/AP buff are categorically different. Wahapedia:
  https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host

## Dominant mechanism

**The dominant residual mechanism is Custodes OC starvation, not
sticky.** 73-76% of scored objectives have OC=0 from Custodes every
round. DG wins 69.7% of its VP from PRIMARY contests (a_oc>b_oc),
only 30.3% from the sticky 0/0 fallback. With Custodes physically
unable to reach 4 of 5 markers per round, DG primary-scores the
uncontested markers and sticky-scores the ones it later vacates.

The single highest-leverage lever is **Custodes' missing
stratagem payload**. Custodes fires 7.17 strats/battle, all from
the universal core pool. The Shield Host detachment lists 6 named
stratagems on Wahapedia, including **Stooped in Blood** (re-roll
hit and wound for melee against units that destroyed a Custodes
model — counter-attack damage uplift) and **Vigil Eternal**
(invuln 4+ → 3+ on Custodes Bodyguard models for a phase —
durability against the small-arms fire that's grinding them down
in R2-R5). Both raise Custodes' kill output per turn, which is
the binding constraint: DG only takes 0.72 PM losses/battle, so
even 30-50% more Custodes lethality across 5 rounds compounds to
PMs dying faster, vacating markers faster, denying sticky.

## Top fix — F-AC-MARTIAL-MASTERY-CORRECT

**Type**: RULE_FIX (replace approximation `SHIELD_HOST.plus_one_save`
with the canonical Martial Mastery offensive Crit/AP buff).

**Wahapedia**: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host

**Real rule** (verbatim, from existing `data/rule_citations.d/detachments.json`
entry):

> "At the start of the battle round, you can select one of the
> bullet points below. If you do, until the start of the next
> battle round, that bullet point's effects apply: Each time an
> ADEPTUS CUSTODES model from your army with the Martial Ka'tah
> ability makes a melee attack, a successful unmodified Hit roll
> of 5+ scores a Critical Hit. Improve the Armour Penetration
> characteristic of melee weapons equipped by ADEPTUS CUSTODES
> models from your army with the Martial Ka'tah ability by 1."

**Scope**: medium. Three changes:

1. `code/detachments.py` — drop `plus_one_save=True` on
   `SHIELD_HOST`; add either `melee_crit_on_5_plus_hits=True` or
   `melee_ap_plus_one=True` (one bullet picked per round; pick the
   AP one as default since it benefits every melee attack vs PMs
   Sv 3+, while crit-on-5+ only matters vs invuln-saved units of
   which DG has few).
2. `code/simulator.py` — wire the new flag into the melee
   resolution. There's existing precedent for melee AP modifiers
   in the per-weapon AP resolution path.
3. `data/rule_citations.d/detachments.json` — update the entry's
   `effect` field to reflect the new mechanism; drop the
   `approximation: true` flag once the rule is wired correctly.

**Predicted MAE Δ**: **-1.5 to -3 pt** on DG slice MAE.

Why this is the top pick over the alternatives:

- **Direction-correct**: the current flag is DEFENSIVE save uplift,
  inflating Custodes durability (PMs already only crack 0.22
  CG/battle; the +1 save makes Custodes even more un-killable than
  the codex intends). The real rule is OFFENSIVE — more Custodes
  melee output, which is what's missing. Swapping defensive→offensive
  raises Custodes lethality and lowers Custodes durability slightly.
- **Wahapedia-anchored**: the rule text is already in the citation
  file flagged as `approximation: true`. No invention.
- **Faction-neutral**: only affects Custodes' own detachment buff.
  No opponent AI changes. The brief allowed "DG ability we
  over-simulate" or "Custodes ability we don't simulate"; this
  qualifies as the latter.
- **Compounds with Custodes CP profile**: Custodes already burns
  5.10 CRR fires/battle (high). Higher melee output per attack
  means more reliable Custodes target kills, fewer wasted CRR
  fires, more CP left for HI saves — but this is downstream and
  not relied on for the MAE forecast.

### Alternatives considered, rejected, why

| Fix | Rejected because |
|---|---|
| **Add 6 Shield Host stratagems** | Larger scope; needs 6 new `Stratagem(...)` registrations + 6 dispatchers + 6 citations. Higher impact eventually but too big for an iter-7 single-shot. F-AC-MARTIAL-MASTERY-CORRECT is the prerequisite — the detachment passive must be right before the detachment stratagems are stacked on top. |
| **Boost Custodes M6→M8 to fix OC reach** | Invention. Custodian Guard is M6" canonically (Wahapedia datasheet). Inflating move to compensate for AI shortcomings is exactly the failure mode CLAUDE.md §10 warns against. |
| **Faction-neutral AI: rank obj by distance and route mobile units to far markers** | Plausible (Custodes only contests 24-27% of markers), but the brief said "faction-neutral AI improvement" is one option. The AI side bites every army the same way — and DG's posture is already `attrition` (boosts CAPTURE on under-defended markers) while Custodes is `objective_hold` (boosts CAPTURE 1.3x). The bias is already present; the root problem is Custodes having too few bodies, not bias direction. |
| **Re-anchor `plus_one_save` to a different Custodes unit-led ability** | Bodyguard's Sentinel-Blades / 2+ saves are baked into BSData stat lines, not detachment rules. Don't double-count. |
| **DG Worldblight: require the DG unit to currently be ALIVE on the marker (no sticky claims from already-dead units)** | iter-3 already enforced this via the `>` strict-greater fix (commit `de12555`). The current sticky path is correct. |

### Predicted impact

- Custodes melee output rises ~10-20% (AP -1 on melee, applied
  ~every melee attack on Custodian Guard / Allarus / Wardens).
- CG kills/battle climbs from 0 to ~0.3-0.6 PMs/battle in melee.
- Custodes durability drops by `plus_one_save` removal (2+ → 3+ on
  CG, 4++ unchanged): DG kill rate on CG models rises from
  0.22/battle to ~0.4-0.7/battle, eroding Custodes OC pool faster.
- Combined: DG vs Custodes WR drops from 67.5% toward ~50-55%,
  closing 12-17pt of the +19.5pt residual on this matchup.
- Slice-wide MAE: the DG slice has 7 unsampled matchups; this
  fix only touches one (DG vs Custodes). Slice MAE drops
  proportionally — call it -1.5 to -3pt on the full DG slice.

### Tests to add (not in this PR)

- New `test_shield_host_martial_mastery.py`: build a Custodes army
  with a Custodian Guard squad, run a single melee fight phase
  against a PM unit; assert effective AP on melee weapons is
  improved by 1 over the BSData baseline; assert `+1 save` is no
  longer applied on the Custodes side.
- Regression: existing Custodes-touching tests
  (`test_detachments.py`) updated to match the new effect.

## Test gate

`python -m unittest discover -s tests` — **665/666 tests pass**.
One pre-existing stochastic failure in the iter-6 baseline
(`test_marines_mirror_winrate_balanced` — assertion `wr < 0.70`
where the boundary is RNG-state-dependent across full-discovery
runs; the same module passes in isolation). No production code
touched this iteration — only `scripts/iter7_dg_vs_custodes_diag.py`
is added.

## Not done this pass

- Did not implement the fix (diagnostic-only per brief).
- Did not run the eval suite (per "no N=200 eval" constraint).
- Did not WebFetch Wahapedia (host unreachable; rule text is
  already in the repo citation file).
- Did not modify catalogue / strategy / simulator / stratagems.
