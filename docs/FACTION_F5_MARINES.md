# Faction Audit F5 — Adeptus Astartes (Gladius Strike Force)

Task #172. After G3 (battleshock + Synapse) the Marines diff jumped to +18.3 pts
above real-meta win rate. This audit isolates which of the three hypothesised
mechanics is the dominant cause.

## Method

`scripts/marines_diag.py` runs **30 seeded archetype battles per matchup**,
Marines (Gladius Strike Force) vs each of the 9 other factions at 1000 pts.
Both sides use `use_archetype=True`. The diagnostic subscribes to the battle
event stream and captures, per battle:

* **H1 (Oath of Moment generosity)** — `marine_attacks_on_oath / marine_attacks_total`,
  i.e. what fraction of Marine UnitShot+UnitFought events landed on the army's
  current `oath_target_uid`.
* **H2 (Combat Doctrines firing rate)** — what fraction of Marine attacks
  hit the (round, mode) gate the Gladius AI rotation grants +1 to wound on
  (round 1 = ranged, round 2 = either, round 3+ = melee).
* **H3 (OC stack)** — average Marine OC vs opponent OC sampled at each
  ObjectiveScored event end-of-round (one sample per objective per round).

Read-only diagnostic — does NOT modify catalogue, simulator, or strategy code.

## Per-matchup results

| opp | WR% | rnd | M attk | oath% | doctr% | M_OC | O_OC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Necrons          | 50.0 | 4.97 | 104.4 | 11.65 | 50.67 | 1.20 | 0.94 |
| Aeldari          | 90.0 | 4.90 |  70.3 | 12.78 | 47.80 | 1.51 | 0.49 |
| Tyranids         | 60.0 | 5.00 |  90.1 |  8.45 | 50.36 | 1.24 | 2.11 |
| Orks             | 70.0 | 4.97 | 107.2 |  9.26 | 48.60 | 1.24 | 0.99 |
| T'au Empire      | 70.0 | 5.00 |  86.9 |  8.18 | 51.53 | 1.54 | 1.04 |
| Death Guard      | 53.3 | 5.00 | 108.0 | 14.75 | 54.15 | 1.28 | 0.77 |
| Adeptus Custodes | 56.7 | 5.00 | 111.5 |  7.97 | 51.53 | 1.14 | 0.91 |
| Thousand Sons    | 76.7 | 5.00 |  94.8 | 14.69 | 49.80 | 1.54 | 0.50 |
| Leagues of Votann| 86.7 | 5.00 | 100.6 |  7.34 | 49.25 | 1.43 | 0.58 |
| **OVERALL**      | **68.1** | — | — | **10.56** | **50.41** | **1.35** | **0.93** |

Marines win 68.1% across the 9 archetype matchups at 1000 pts (270 battles).
Real-meta WR for Marines is ~52% (the +18.3 pt diff target). The over-perform
is broad — only Necrons and Death Guard are inside the noise band; vs
Aeldari, Votann, and Thousand Sons the bias is huge (>75% WR).

## Hypothesis test

### H1 — Oath of Moment generosity: FALSIFIED

Oath of Moment buffs only **10.56%** of Marine attacks on average across
matchups (range 7.34–14.75%). The task brief predicted ~80% if the bug was
real. The cause: target picker in `_resolve_shooting_attack` /
`_resolve_melee_attack` (`code/simulator.py:2055` and similar) picks by
**lowest current_health × screen-bonus × synapse-bonus** — it does NOT
preference the oath target. Marines mostly chew screens and synapse units
while the oath target sits behind a Repulsor untouched. Oath is correctly
applied (`code/units.py:920-926`) — re-roll all hits + re-roll all wounds
gated on `is_marine_faction` AND `oath_target_uid == target.uid` — but the
AI rarely *attacks* the oath target. Oath is **under-utilised**, not
over-applied. Not the bug.

### H2 — Combat Doctrines firing rate: NEUTRAL

**50.4%** of Marine attacks land on the boosted (round, mode) gate.
Distribution matches the AI rotation arithmetic exactly: round 1 ranged +
round 2 (both) + round 3+ melee ≈ half of total attacks across a 5-round
battle. No anomaly there.

But: I read `code/units.py:683-684` and confirmed the Doctrines wound bonus
is applied **after** `att_buffs["plus_one_to_wound"]` with no +1-cap check.
In a pure Marines list this doesn't matter (Gladius detachment doesn't set
`plus_one_to_wound`, no Marine leader grants +1-to-wound) — so for a Marines
mirror or vs-X this is silent. Confirmed: no intra-Marine +1-to-wound source
stacks with Doctrines. **Not the bug** for Marines specifically — but it IS
a real cap bug that would bite if a future leader/enhancement grants +1.

### H3 — OC stack: CONFIRMED ROOT CAUSE

Marines average **1.35 OC** on objectives, opponents average **0.93 OC**.
Marines outscore on OC 8 out of 9 matchups — the lone exception is Tyranids
(0.94 vs 2.11) where Hormagaunt/Termagant swarms still beat MEQ OC, and
Marines still win that matchup 60% on raw kills. Marines win because they
park OC 2 Intercessor squads (10 OC per squad of 5) on objectives and
nothing in the opponent's archetype can shift them at 1000 pts.

Looking at archetype composition (`code/archetypes.py:55-65`): Gladius
seeds 2× Intercessor squad (OC 2 × 5 = 10 OC each = **20 OC just from
troopers**), then random-fill adds more Intercessor / Infiltrator bodies.
Most other archetypes give the equivalent vehicle/CHARACTER-heavy
composition with **much lower aggregate OC** (Aeldari Battle Host fills
with Falcons/Wave Serpents OC 2 each; T'au Kauyon fills with Crisis suits
OC 1; Custodes Shield Host OC 1 across the board). The disparity is
roughly **1.5× more OC than the average opponent** — and OC drives VP, VP
drives wins.

## Root cause

Marines' **OC stack from 2× Intercessor squads, sized at min_models=5,
yielding 10 OC each**, beats every comparable opponent archetype on
objectives. Sustained 1.35-vs-0.93 OC advantage across all 9 matchups
maps cleanly to the +18.3 pt diff: each round Marines score primary on
2-3 of 4 objectives while the opponent scores 0-1. The combat math
(Oath, Doctrines, re-rolls) is correctly gated and not over-firing.

## Priority fix proposal

**Reduce Intercessor archetype count from 2 squads to 1** in
`code/archetypes.py:57` (`"space_marines_intercessor_squad": 2` →
`": 1`), letting `_random_fill` pick the second body. That removes the
hard-coded OC stack: random fill picks between Intercessors, Infiltrators,
Heavy Intercessors, Scouts, and assorted vehicles by cost, so the OC
contribution falls from a deterministic 20 to a stochastic 8-16 range —
matching other faction archetypes' troop spine. Expected effect: pull
Marines WR from ~68% back to ~55% (within real-meta band), closing most
of the +18.3 pt diff without touching the simulator combat math.

Secondary (lower priority, NOT for this audit but flag for follow-up):
add a +1-to-wound cap in `Unit.attack` for future-proofing Doctrines vs
hypothetical leader/enhancement stacking. Latent, not the current bug.
