# Auto-loop iter 1, Cluster C — strategy AI gap audit (faction-neutral)

Diagnostic on 30 mixed-faction vanilla-10e battles. All findings here are
applied via universal heuristics, never per-faction biases. Per-area
quantitative results from `scripts/strategy_ai_audit.py`.

## Audit method

`scripts/strategy_ai_audit.py` runs N=30 vanilla battles across all 10
factions (random pairs, deterministic seeds), subscribes an `EventLog`,
and counts the role-distribution / round-distribution of every
`UnitShot` / `UnitFought` / `UnitCharged` / `UnitActivated` /
`StratagemFired` event. The aim is to surface decision points where
the AI's choice is observably worse than an alternative the simulator
already exposes.

## Per-area findings

### 1. Target priority — shooting (1529 picks)

```
DUAL    29.5%   MELEE   24.7%   HEAVY   18.3%   SHOOTY  13.8%
HORDE    8.1%   SUPPORT  5.6%
```

Mean target HP-frac AFTER shot = 0.56 — the shoot picker over-shoots
healthy bricks because `_do_shoot` picks **lowest-HP among objective
contesters**, which collapses to "shoot wounded targets" rather than
"shoot the unit whose death matters most this round". Screen + synapse
bonuses exist but are only `*1.4` / `*1.5` on the inverse-HP score.

**Gap:** picker does not look at OC contribution to next-round primary.
A 1HP Termagant on an objective contesting OUR primary is worth more
than a 3HP Carnifex elsewhere — sometimes the picker gets that right,
but the bonus is HP-driven, not contribution-driven.

### 2. Target priority — fight phase (469 fights)

`_do_fight` is `min(enemies, key=distance)` — nearest enemy,
unconditionally. **No** screen / synapse / gunline / threat-back
scoring. The `_melee_target_score` helper exists for the MOVE planner
but is never called from the fight picker.

```
MELEE/DUAL hitting HORDE-role targets in melee: 3.4%
```

This 3.4% looks low but the fights themselves are dominated by
"whichever was the only enemy in 1.5"" — by the time melee resolves,
the MOVE planner has usually narrowed candidates. The real cost is
when 2+ enemies are in engagement and the simulator picks the
geometrically-nearest rather than the one whose death actually breaks
the lock.

### 3. Target priority — charges (831 picks)

```
DUAL    30.4%   HEAVY   29.8%   MELEE   17.0%   SHOOTY  13.1%
HORDE    5.8%   SUPPORT  3.9%
```

**27.8% of charges target a T8+ save-3+ brick.** `pick_charge_target`
weights `kill_potential / (1 + threat_back)` so a Marine bike charging
a Carnifex still scores positive if alternatives are weaker — but in
practice the picker repeatedly throws light melee into T9 monsters
that won't crack open before fight phase reverses on them. The
`_durability` helper folds in saves but the score isn't penalised for
"target won't die this round" specifically.

### 4. Activation order

First-activated role per army-turn:
```
HEAVY  36.3%   DUAL  24.0%   MELEE  15.7%   SHOOTY  15.7%
HORDE   4.3%   SUPPORT  4.0%
```

Reasonable distribution (HEAVY anchors first). **But:** in vanilla mode,
`_run_round_vanilla_turns` iterates `active.units` directly (army-build
order), **not** `activation_queue()` — `activation_queue()` is only
called from alternating mode! The vanilla path therefore activates in
**list-construction order** (random per faction-builder's order), not
by Lanchester score. The 36.3% HEAVY-first is luck-of-the-draw from
how `build_faction_random_army` walks the pool, not a deliberate
ordering.

**Leader-led composition: 62.6% before, 37.4% after.** A leader that
activates AFTER its led teammate squad cannot pump the squad's
aura-buffed shooting because the squad already shot — wasted leader.

### 5. Stratagem firing cadence

```
R1   9.3%   R2  40.0%   R3  19.8%   R4  18.4%   R5  12.6%
```

R2 firing rate is healthy (`_predict_pivotal_turn` defaults to T2). But
60% of stratagems fire R3+, and Command Re-Roll (the highest-impact
universal) shows `R1=9, R2=105, R3=39, R4=40, R5=18`. R4/R5 firings on
Command Re-Roll are mostly **expired reservation** — pivotal-turn
deferral held CP through T2 but the army hadn't reached the trigger
condition by then, so CP "leaks" to less-pivotal late rounds.

### 6. Move intent

The move planner (`pick_move_intent`) has a 1-D round_weight
(`1.0 + 0.15*(cur_round-1)`) for objective value. It does NOT consider
opponent primary scoring potential — a unit currently outside enemy
control radius makes the planner think "no urgency", even when the
opponent is poised to flip primary next round.

## Top 5 ranked AI fixes (highest leverage first)

Predictions are pre-implementation estimates: each is an opinion on
whether the fix moves the loop's MAE-vs-real signal, not a guarantee.
The auto-loop budget would burn these in this order.

### Fix 1 — Fight target picker uses `_melee_target_score`

**Current:** `_do_fight` picks `min(enemies, key=distance)` (nearest).

**Proposed:** in fight phase, score every enemy in engagement-range
(1.5") with `_melee_target_score(attacker, enemy)` and pick the
highest. The helper already exists and bakes in
gunline / support / screen / synapse bonuses.

**Expected MAE-vs-real delta:** −0.5 to −0.8 pt.

**Faction-neutral because:** `_melee_target_score` is faction-agnostic
— it composes universal heuristics (`_gunline_charge_bonus` is
asymmetric only to keep T'au's own melee from gaming the bonus, which
is the same asymmetry already in `pick_charge_target`). Every faction's
melee bricks benefit equally from "fight the squishy one in front of
you, not the closest brick".

### Fix 2 — Charge picker adds a "won't-crack" penalty

**Current:** `pick_charge_target` scores `kill_potential` via
`_durability` (folds in saves + T + HP) but a low score still wins if
no alternatives exist. 27.8% of charges go into T8+ S<=3 bricks.

**Proposed:** add a multiplicative penalty when
`kill_potential * a_melee_dpa < 0.20 * target.current_health` — the
attacker can't expect to remove more than 20% of the target this turn.
That charge is a tarpit-trade, not a kill — let the planner choose
HOLD or an objective move instead.

**Expected MAE-vs-real delta:** −0.4 to −0.7 pt. Reduces wasted
charge-pile-ins that get counter-killed next turn.

**Faction-neutral because:** penalty triggers on the universal
DPA-vs-HP ratio. Knights and Tyrants get penalised identically to
Wraithlords and Custodian Guard. No faction-specific stat or keyword
gate.

### Fix 3 — Vanilla mode uses `activation_queue` for ordering

**Current:** `_run_round_vanilla_turns` iterates `active.units`
directly; `activation_queue()`'s score-only sort is alternating-only.

**Proposed:** in vanilla mode, also iterate
`active.activation_queue(set())` per sub-phase. This sorts by
Lanchester `profile.score` descending, which is faction-neutral.

**Expected MAE-vs-real delta:** −0.3 to −0.5 pt. Mostly affects
factions whose builder happens to put HEAVIES last in the list
(consistent activation ordering across factions reduces composition
luck).

**Faction-neutral because:** `profile.score` is the universal
Lanchester score and applies identically to every faction's roster.

### Fix 4 — Leader-before-led composition gate

**Current:** 37.4% of leader activations happen after their led
teammate squad's activation, wasting one round of aura buffs.

**Proposed:** in `activation_queue`, give CHARACTER units with a
registered `LeaderAbility` a priority lift equal to the score of the
heaviest INFANTRY squad in their army (so the leader sorts adjacent to
its led teammate or just ahead). The fix preserves the score-only
behaviour for non-leader units.

**Expected MAE-vs-real delta:** −0.3 to −0.5 pt. Higher impact on
faction-pairings whose leader auras carry real DPA uplift (Marines
Captain re-roll 1s, Aeldari Farseer Doom, T'au Cadre Fireblade markerlight).

**Faction-neutral because:** the rule fires on any CHARACTER + leader
ability — Marine captains, Necron Overlords, Eldar Farseers and DG
Lord of Contagion all benefit. The lookup is via the existing
`lookup_ability` registry which is faction-blind to the algorithm.

### Fix 5 — Stratagem CP-leak cleanup (T2 spend or skip)

**Current:** `_should_hold_for_pivotal_turn` defers Command Re-Roll
until T2, but if the army doesn't hit the firing condition in T2 the
CP rolls forward — observed R4/R5 firing on stratagems whose pivotal
turn was T2. Net effect: CP burned late on stratagems whose marginal
value at T4/T5 is < their MIN_EXPECTED_SWING_PTS bar.

**Proposed:** track `cp_reserved_for_pivotal` per stratagem class.
When the current round equals the pivotal turn AND the trigger is
unmet, demote the reservation — let any subsequent trigger fire it
regardless of pivotal-turn deferral. This both empties reserve
correctly and avoids the spurious "we held for T2 so now it's free
for T4" leak.

**Expected MAE-vs-real delta:** −0.2 to −0.4 pt. Smaller because
stratagems are only ~10% of total DPA swing, but the late-round leak
disproportionately hurts factions with cheap stratagems
(DG Plague Weapons, TSons Doombolt) — which are over-rated in the
baseline, so plugging the leak pulls those down.

**Faction-neutral because:** the bookkeeping change applies to every
stratagem's deferral, not to one army's CP economy. The trigger
gates per stratagem are unchanged.

## Combined ranked fix list (table)

| Rank | Area | Fix | Est. MAE Δ | Cost |
|----|----|----|----|----|
| 1 | Fight pick | Use `_melee_target_score` in `_do_fight` | −0.5 to −0.8 | small |
| 2 | Charge pick | "Won't-crack" penalty in `pick_charge_target` | −0.4 to −0.7 | small |
| 3 | Activation order | Vanilla mode uses `activation_queue` | −0.3 to −0.5 | small |
| 4 | Activation order | Leader-before-led priority lift | −0.3 to −0.5 | small |
| 5 | Stratagem CP | Pivotal-turn leak cleanup | −0.2 to −0.4 | small |

Combined upper-bound delta: **−1.7 to −2.9 pt** of MAE-vs-real (6.72 →
3.8-5.0 range). The fixes compose because each touches an independent
decision point (move / charge / fight / activation / strat).

## What was rejected

- Faction-tuned target priorities (e.g. "Tyranid charges downweight
  Custodes targets") — rejected; cannot be expressed as a universal
  heuristic.
- Posture-specific shoot picker overrides — rejected; the existing
  `FACTION_POSTURE` lookup already lives in the move planner and
  adding another layer doesn't satisfy the iter-1 faction-neutral gate.
- Archetype seeding sort changes — investigated; the G5 anchor-first
  sort applies only to `use_archetype=True`, which is **not** the path
  the calibration eval uses (eval calls `build_faction_random_army` with
  the default `use_archetype=False`). Changing it would not move
  MAE-vs-real for the calibration loop.
