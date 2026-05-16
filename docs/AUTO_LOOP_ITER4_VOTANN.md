# Iter 4 — Leagues of Votann diagnostic (+5.7 root cause)

Sim 51.7% vs real-meta 46.0% (Δ +5.7). Votann is the first faction to drift
upward across the auto-loop (+4.0 → +5.7) without ever being touched directly.

This is a diagnostic-only investigation. No code changed. Driver:
`scripts/iter4_votann_diag.py` — 30 vanilla 10e battles per opponent (Marines,
Death Guard, Necrons), 1000pt, default RulesConfig.

## Hypotheses captured

| Code | Hypothesis | Result |
|------|------------|--------|
| H1 | Per-round damage output | Event attribution gap — UnitShot/UnitFought attacker_uids did not intersect the captured uid set in this collector. Not pursued; H4 dominant. |
| H2 | Stratagem firing / CP usage | Votann CP-spent 7.72 vs opp 7.19 — Votann spend slightly MORE CP, not less, but exclusively on universal Core stratagems. |
| H3 | Survival (tanky dwarves) | First-death and deaths counters didn't fire in collector. The token rate is itself the proxy: 12.86 token-awards/battle ⇒ ~13 Votann model deaths/battle. Survival not the dominant lever. |
| H4 | **Judgement Tokens** | **12.86 tokens/battle, max 3.83 on any single target.** Tier-3 (`reroll all hits + reroll wound 1s`) activates in essentially every game. |

## Findings

### Aggregate (30 battles × 3 opponents)

```
WR mean (Votann side A):     40.00%
CP spent Votann mean:         7.72
CP spent Opp mean:            7.19
Tokens awarded / battle mean:12.86
Max tokens on any target:     3.83
Total rounds mean:            5.00
```

### Per-opponent WR

- Votann vs Marines: 30.0% W (9/20/1)
- Votann vs DG:      30.0% W (9/21/0)
- Votann vs Necrons: 60.0% W (18/12/0)

The Marines / DG numbers are below real-meta, but the Necrons number is way
above. In aggregate the sim is +5.7 across all 9 opponents — this 3-opponent
slice happens to look low because Marines (+12.6) and DG (+15.3) themselves
over-perform, dragging Votann's relative WR down vs them.

### Stratagem firing (aggregate, 30 × 3 = 90 battles)

Votann fires only the four UNIVERSAL_STRATAGEMS:
```
Command Re-Roll       x486
Heroic Intervention   x179
Counter-Offensive     x15
```
Opponents fire their full detachment-stratagem suites (DG: Creeping Blight,
Overwhelming Generosity, Leechspore Eruption, Disgustingly Resilient, Plaguesurge,
Putrid Detonation; Necrons: Protocols x4 + Command Re-Roll + Heroic Intervention).
Despite this, Votann's higher CP-spend volume reflects that they have nowhere
else to put CP — they pump Command Re-Roll on hits and saves. The cumulative
re-roll volume over a battle is non-trivial WR uplift on top of EotA tokens.

## Dominant mechanism

**Eye of the Ancestors tier-3 trigger threshold is too low under SwegHammer's
model-as-Unit representation.** The simulator stores one Unit per model
(squads are N single-model Unit instances). Real Wahapedia rule fires "when an
enemy unit destroys a LEAGUES OF VOTANN unit" — once per multi-model squad
destroyed. SwegHammer fires once per model-Unit destroyed because every model
is its own Unit. In a 9-model Hearthkyn squad, the simulator can hand out 9
tokens to the killer in a battle where the canonical rule would hand out 1
(when the whole squad finally folds).

Result: max-tokens-on-any-target mean 3.83 ⇒ tier-3 buff
(`att_reroll_all_hits = True; att_reroll_wound_ones = True`) activates in the
median game. Real-rule tier-3 (≥3 tokens, requires three separate Votann squads
to die to the same enemy unit) almost never fires in actual play.

The citation file
(`data/rule_citations.d/judgement_tokens.json`) already flags this
exact failure mode:

> SwegHammer models squads as single Unit instances, so 'destroys a Votann
> unit' fires once per model-Unit killed (not per multi-model squad
> destroyed); this matches expected-value behaviour but awards tokens at a
> **higher frequency** than the canonical rule when the Votann army contains
> true multi-model squads.

Empirically that "higher frequency" caveat is doing massive WR work — the
tier-3 buff is supposed to be a payoff for sustained losses across multiple
squads, and instead it's a near-guaranteed mid-game upgrade.

## Top fix candidate (highest MAE leverage)

**Gate token awards to once-per-squad, not once-per-model.** Two reasonable
implementations:

1. **Divide token count by squad size at lookup time.** In `Unit.attack`
   (`code/units.py:939`), change
   `tokens = own_army.judgement_tokens.get(target.uid, 0)` to apply the
   thresholds against `tokens // squad_size_estimate` for the killer's unit
   profile.
2. **Probabilistic award gate.** In `_maybe_award_judgement_token`
   (`code/simulator.py:3678`), award a token with probability
   `1 / victim_unit_min_models` per model death.

Option 2 is cleaner and preserves the citation's "matches expected-value
behaviour" intent more honestly. With Hearthkyn min_models=9 and Cthonian
Beserks min_models=5, this would drop token-awards/battle from ~13 to ~2 and
move max-tokens-on-any-target from ~4 (mid tier-3) to ~1.4 (well below tier-3).

**Wahapedia citation** (already in repo):
`https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/#Faction-Rules`

Quoted rule (from `data/rule_citations.d/judgement_tokens.json`):
> Each time an enemy unit destroys a LEAGUES OF VOTANN **unit** from your
> army, that enemy unit gains a Judgement token.

(Emphasis added — the rule says "unit", not "model".)

### Expected MAE delta

Removing tier-3 reroll-all-hits activation in the median game eliminates the
strongest of three buff tiers from nearly every Votann attack sequence. Crude
estimate: tier-3 is ~50% bigger than tier-1 (full-failure rerolls vs nat-1
rerolls × adds wound rerolls). If tier-3 fires in ~50% of games and tier-1 in
~90% post-fix, total Votann offensive output drops ~7-12%. Maps to
approximately **−2.5 to −4.0pt on Votann WR** (i.e. +5.7 → ~+2.0 to +3.0pt),
contributing **−0.25 to −0.40pt to overall MAE**.

This is the highest single-faction lever identifiable from this diagnostic.

## Alternative fixes considered but lower-leverage

- **Wire real Oathband stratagems** — Votann's CP-spend is already higher
  than opponents (7.72 vs 7.19); adding more spend targets would shift CP
  utilisation patterns but unlikely to drop WR. Likely a wash or small
  upward push.
- **Replace EotA with Prioritised Efficiency (Yield Points / Hostile
  Acquisition)** — correct per current codex, but high-infra rewrite of an
  entire army rule. Defer until token gating is fixed; if token-gated EotA
  still drifts, then revisit.
- **Re-tune Hearthkyn / Hearthguard points overrides** — the existing
  overrides already reduce Hearthkyn 100→90 and Sagitaur 115→103.5. Further
  drops would mask the token-frequency bug rather than fix it.
