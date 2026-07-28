# Astra Militarum order coverage — the measurement defect

**Date:** 2026-07-24
**Frame:** standing anchor `data/_anchor_sc67a_n80_log.json` (gated mean absolute
error 2.76 A-frame / 2.77 symmetrized). Astra Militarum sits at 33.8 percent
against a real 45 percent — gated residual 8.65, the deepest under-pole and the
number two residual behind Death Guard.
**Instrument:** `scripts/_am_order_coverage.py` (read-only; it monkeypatches
`code.orders.dispatch_orders` to observe and changes nothing).

---

## 1. Why this thread was reopened

The decision ledger's 2026-07-02 entry on the Grizzled Company screen closes with
a question that was registered and never run:

> the blocker is ORDER COVERAGE (the recorded old finding: ~1.4 Orders/round
> reach ~9% of squads; real players stack multiple officers' Orders on key
> shooters). Grizzled's reactivation condition: an order-coverage fidelity
> investigation (does the sim under-issue Orders vs the real officer economy?)
> — queued.

Every other Astra Militarum axis has been worked to exhaustion — datasheets,
Orders dispatch logic, three list shapes, five piloting channels, three
realization shapes, the deployment and cover thread (three rejects), and the
Assassination bleed (fixed by modelling 10e Leader attachment). This one was
never measured.

## 2. The measurement

Thirty games, Astra Militarum versus five opponents, one hundred and fifty
Command phases, on the current frame:

| quantity | measured |
|---|---|
| live Officer units per round | 4.04 |
| rules-legal Order allowance per round | 8.77 |
| **Orders actually issued per round** | **2.93 — 33 percent of the legal ceiling** |
| unissued for want of a target | 5.83 |
| orderable squads per round | 10.11 |
| of those, inside some Officer's aura | 3.51 |

The dispatcher is not the bottleneck: of the squads that *are* in aura, 84
percent get an Order. The bottleneck is that only about a third of the army is
ever inside an Officer's 6-inch aura.

## 3. The cause is a measuring bug, not a piloting one

`code/orders.py` tested the aura as a raw centre-to-centre distance:

```python
_distance(officer.position, m.position) <= OFFICER_AURA_RANGE   # 6.0
```

The 10e core rule, already cited in this repository at
`data/rule_citations.d/keywords_and_mechanics.json`, is:

> When measuring the distance between models, measure between the closest
> points of the bases of the models you're measuring to and from.

The simulator already applies exactly that measurement in two other places —
Engagement Range (`code.sim.geometry._er_gap`, cited
`simulator.engagement_range_base_edge`, default-on since wave 240) and objective
control (`Battle._assign_army_oc`, control radius = centre distance minus base
radius). The Voice of Command aura was the one range test still measured
centre-only.

Base radii on the built Astra Militarum archetype (`_bc_model_radius_in`):

| model | base radius | legal reach from a foot Officer | measured reach |
|---|---|---|---|
| Leman Russ / Rogal Dorn / Manticore / Basilisk / Chimera / Taurox | 2.37" | **9.00"** | 6.00" |
| Lord Solar Leontus, Attilan Rough Riders | 1.15" | 7.78" | 6.00" |
| Cadian Shock Troops, Kasrkin, Krieg, Command Squads | 0.63" | 7.26" | 6.00" |

The worst case is the one that matters most: a foot Officer ordering a Leman
Russ was reaching 67 percent of its legal radius, which is **44 percent of its
legal area** — and Lord Solar Leontus to the same tank is 9.52 inches legal
against 6.00 measured. Astra Militarum is the faction this hurts most because
its Order recipients are the largest bases any infantry army fields, and because
the whole army rule is the Order economy.

## 4. The fix and its measured effect

`SWEG_ORDER_AURA_BASEEDGE` (default-off, byte-identical off — the deterministic
twelve-battle event-log digest is unchanged at `db13417fb7e3b2d47cef9867`).
`code.orders._aura_gap` measures the aura base-edge to base-edge; the three call
sites are the per-Officer target search, the Ursula Creed led-squad resolution,
and the Inspired Command stratagem pairing. Cited as
`simulator.order_aura_base_edge`.

| | off | on |
|---|---|---|
| Orders issued per round | 2.93 | **4.20** |
| percent of legal ceiling | 33% | **47%** |
| squads receiving an Order | 29% | 42% |
| Take Aim! share of the Order mix | 36.6% | **52.5%** |

The mix shift is the tell that the diagnosis is right: Take Aim! is the Order the
dispatcher wants to give the tanks, and the tanks are exactly the models the
centre-only measurement was cutting out of range.

## 5. The residual, and a second (thin) lever

Even with the measurement corrected, 4.75 Orders per round still go unissued.
Per-Officer, the shortfall is concentrated in the three-Order Officers:

| Officer | Order allowance | distinct eligible squads in aura | unplaceable |
|---|---|---|---|
| Lord Solar Leontus | 3.00 | 1.88 | 1.33/round |
| Ursula Creed | 3.00 | 2.14 | 1.14/round |
| Cadian Castellan | 2.00 | 3.34 | 0.38/round |
| Cadian Command Squad | 1.00 | 2.67 | 0.14/round |

The existing `SWEG_OFFICER_FOLLOW` hook seeks the *nearest* squad whose
catalogue key is in the Officer's LeaderAbility host keys and stops as soon as
one is inside the aura — correct for a one-Order Officer, wrong for a
three-Order one, since each Order needs its own distinct unit and a unit can only
be affected by one Order at a time.

`SWEG_OFFICER_COVERAGE` (default-off, byte-identical off, cited
`simulator.officer_coverage_piloting`) picks instead the eligible-squad centroid
that puts the most *distinct* orderable squads in aura, capped at the Officer's
own allowance, restricted to candidates reachable this Movement phase, ties
broken toward the nearer.

**It is thin and should not consume a screen slot yet.** Measured at twenty
games it moves Orders per round 4.49 → 4.61 (and 4.73 without the reachability
filter — the two are inside each other's noise). The reachability filter is kept
because without it the hook fired on 92 percent of Lord Solar's move decisions
and made his coverage *worse* (1.88 → 1.73): he spent the game walking toward a
centroid that had moved on, permanently in transit instead of ever standing in
the cluster. Verdict: built, cited, held default-off, does not clear the
behavioural bar in `docs/LEVER_PROTOCOL.md`.

## 6. Registered finding — the defect is global, and double-edged elsewhere

The Order aura is not the only centre-to-centre range test. The same pattern
appears at, among others:

- Tyranids Synapse (6") and Shadow in the Warp (6") — `simulator.py` ~11018/11028
- Death Guard Contagion Range — `simulator.py` ~11037
- Chaos Daemons Shadow of Chaos (18") — `simulator.py` ~11049
- Chaos Knights Harbingers of Dread (9") — `simulator.py` ~11057
- T'au markerlight range — `simulator.py` ~18149/18205

Correcting those is the same faithfulness argument, but the direction is not the
same: Contagion and Harbingers are debuff auras belonging to Death Guard and
Chaos Knights, the number one and a large over-pole. Widening them to their legal
base-edge reach would inflate two over-poles while the Order-aura correction
deflates the deepest under-pole. This is registered as a finding for the owner,
not folded into this change — fidelity-first says adopt it, but it is a separate
decision with its own screen and should not ride along on the Astra Militarum
result.

## 7. Status

- `SWEG_ORDER_AURA_BASEEDGE` — built, cited, byte-identical off, **SCREENED
  DECISIVE**. Run jointly with `SWEG_AM_INFANTRY_FIRE` (see
  `docs/AM_INFANTRY_NEVER_FIRES.md`) as a matchup-scoped N=80 arm over Astra
  Militarum's row and column, joined with `paired_delta --scoped` against
  `data/_anchor_sc67a_n80_log.json`:

  ```
  Astra Militarum   33.8 -> 37.6   pairedD +3.76   ci95 3.14   334 flips   UP*
  gated mean absolute error: OFF 2.76 -> ON 2.56  (-0.20)
  ```

  Every other faction flat (−0.42 to +0.51, all inside noise); the only decisive
  mover is the target. Arm log `data/_scr_amfire_scoped_log.json`. The two gates
  are not yet separated from each other, and the arm did NOT carry
  `SWEG_SQUAD_DAMAGE_FLOOR`, without which the infantry-fire half is only partly
  effective — so this is a lower bound on the package.
- `SWEG_OFFICER_COVERAGE` — built, cited, byte-identical off, held (thin).
- The global aura measurement question — registered, unbuilt.
