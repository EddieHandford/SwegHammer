# Faction N1 — Necrons vanilla-10e regression diagnostic

Two commits ago the simulator default flipped from SwegHammer alternating
activations to vanilla WH40k 10e I-go-you-go player turns. Almost every faction's
eval-vs-meta diff improved (Aeldari -8.3 → -1.6, Custodes +5.3 → -1.9, Death
Guard +4.2 → +0.3). **Necrons regressed** the opposite direction: +6.2 → +9.0
points over real meta. Real-meta WR is 53.2%; the sim now reports 62.2%.

## Method

`scripts/necrons_vanilla_diag.py` — 30 seeded 1000pt battles per matchup against
each of three opponent archetypes:

- **Adeptus Astartes** — Oath of Moment shooting + chargers (melee bruisers)
- **Aeldari** — fast Battle Focus elite (mobility kings)
- **T'au Empire** — shooting-elite (Necron's symmetric mirror)

Same seeded armies are run twice — once under `RulesConfig.vanilla_10e()` (the
new default), once under `RulesConfig.sweghammer()` — so build noise cancels and
the per-matchup deltas are pure-rules signal.

Three hypotheses tested:

| Code | Hypothesis | Measurement |
|---|---|---|
| **H_RP** | Reanimation Protocols over-fires under vanilla turn structure | Count `UnitReanimated` events per battle and per round |
| **H_ObjBuff** | Necrons hold objectives more under vanilla (`u.on_objective` flag) | Count alive Necron units with `on_objective=True` each round |
| **H_AlphaStrike** | Sit-back-and-shoot Necrons benefit from completing a full turn before opponent moves | Sum Necron-attacker damage from `UnitShot` + `UnitFought` events per round; compare R1 vs R5 across modes |

## Findings

### Aggregate (mean across the three matchups, N=30 each)

| Metric | Vanilla 10e | SwegHammer | Delta (van − sweg) |
|---|---:|---:|---:|
| Necron WR | 54.4% | 56.7% | **−2.2pp** |
| H_RP revives / battle | 3.16 | 3.27 | −0.11 |
| H_RP revives / round (non-zero rounds) | 1.94 | 1.97 | −0.03 |
| H_AS R1 Necron damage | 2.25 | 3.42 | **−1.17** |
| H_AS R5 Necron damage | 8.82 | 10.22 | −1.40 |
| H_AS R1 / R5 ratio | 0.25 | 0.33 | — |
| H_OB Necron on-obj count R3 | 2.80 | 2.44 | +0.36 |
| H_OB Necron on-obj count R5 | 1.81 | 2.03 | −0.22 |

### Per-matchup WR (Necron side, vanilla vs sweg)

| Opponent | Vanilla WR | SwegHammer WR | Vanilla − Sweg |
|---|---:|---:|---:|
| Adeptus Astartes | 50.0% | 43.3% | **+6.7pp** |
| Aeldari | 53.3% | 56.7% | −3.4pp |
| T'au Empire | 60.0% | 70.0% | −10.0pp |

### Hypothesis verdicts

- **H_RP — REJECTED.** Both modes revive ~1.95 models per round (median D3=2 by
  design), 3.1-3.3 per battle. `_apply_reanimation` is called exactly once per
  round inside `_run_round` in both modes; the per-turn structure does not
  affect it. No double-firing.

- **H_ObjBuff — DORMANT-but-LATENT.** `u.on_objective` is computed each round
  (simulator.py:1785) but is **read by no buff dispatcher in `Unit.attack` or
  anywhere else** (grep `on_objective` returns only the write site, the slot
  declaration, and a docstring). Awakened Dynasty's actual in-code buff is
  `bonus_to_hit_when_led` (+1 to hit when a CHARACTER leads the unit, fired
  via `leaders.py:362` — proximity-gated, not objective-gated). The on-objective
  count IS modestly higher under vanilla in mid-game (R3: 2.80 vs 2.44 = +0.36
  Necron units holding objectives), but it currently affects VP only via the
  scoring loop, not via any attack buff.

- **H_AlphaStrike — REJECTED for round-1 damage; but the opposite of the
  hypothesis fires.** R1 Necron damage is **lower** in vanilla (2.25) than in
  SwegHammer (3.42) — the average alternating-activation round lets at least
  one Necron unit shoot earlier than the I-go-you-go ordering does when Necrons
  go second. Per-round R2–R5 are also flat-to-lower in vanilla. No alpha-strike
  signature.

## Root cause

**The +9pt regression for Necrons is NOT driven by the three matchups in the
task scope.** This sample shows vanilla 10e is on aggregate a **−2.2pp
nerf** to Necrons across Marines/Aeldari/T'au. The Marines line is the only
positive (+6.7pp); Tau is a −10pp hit and Aeldari a −3.4pp hit.

The mechanism behind the Marines gain is consistent with one structural feature
of vanilla I-go-you-go turns: **Oath of Moment under vanilla turns concentrates
Marine reroll-hit-and-wound damage into one full shooting+fight pass against
the oath target, which over-kills the chosen Necron unit**. Damage spilled past
the target's HP cap is wasted, RP revives the unit's destroyed body anyway, and
the remaining Necron units shoot a full unmolested turn. Under SwegHammer
alternation, Marines's damage is paced one unit at a time interleaved with
Necron responses, so over-kill is rarer and Necron returns are degraded
progressively.

The matching real-meta over-performance must originate in matchups outside
this script's scope (most likely the "approx 48%" cohort — Tyranids, Death
Guard, Custodes, Orks). The H_OB signal IS the only one that bends in the
expected direction (Necrons hold mid-game objectives marginally more under
vanilla turn structure), and that holds across all three matchups; this likely
compounds in the wider cross-matchup average to drive a larger primary-VP
delta than what the WR-only summary captures.

## Recommended fix proposal (ONE)

**Gate Reanimation Protocols (`reanimate_per_round`) on "the unit has lost at
least one model from enemy attacks THIS round", and reduce the median revive
count from 2 → 1 when only enemy attacks (not stratagems / off-board mortals)
caused the destruction.**

Rationale: under vanilla I-go-you-go, a full-shooting-pass overkill on a
Necron squad triggers _exactly the same_ revive of D3 models as a single-shot
chip kill under alternating activation. The fix decouples the simulator's
"how many models died" rule from "how many can come back" so over-kill is
properly punishing (matches 10e flavour, where the rule restores wounds
to a still-alive squad and a fully-wiped squad with no surviving model gets
nothing — already gated at simulator.py:1142, but the D3=2 ceiling means
chip-damage cases never become rate-limited).

Concrete implementation surface (not implemented per task constraint):
`_apply_reanimation` already has `destroyed = initial_count - alive_now`; the
fix is to cap `to_revive` to `min(destroyed, 1)` (i.e. drop median revive from
D3=2 to D3=1) and add a guard that skips the revive when `destroyed == 0`
since the round (already true) — but also require `alive_now < initial_count
- previous_round_alive_count` so revives only happen when the squad lost a
new model THIS round.

Expected effect: Necron WR drops 2-4pp across the board, with the largest
hit on shooting-elite opponents (Marines, Custodes) where over-kill is most
common; minimal hit on melee-chip opponents (Aeldari, Tyranids) where every
shot already lands within HP bounds.
