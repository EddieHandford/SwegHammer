# Secondary-scoring structural analysis (wave 73 investigation)

**Date:** 2026-05-31. **Status:** investigation only — no code changed (per the
"report first" directive in `STAGE1_AUTONOMOUS_GOAL.md`).

## Why this investigation

The goal brief named a "first structural lever": the Pariah Nexus secondary VP is
"computed every round into `_a_secondary_vp` / `_b_secondary_vp` and never read, so
`_decide_winner` picks the winner on primary objective VP only." On verification
**that premise does not hold** — see below — so the investigation widened to *why*
the over/under split persists, since secondaries ARE counted.

## Finding 0 — the named premise is incorrect; secondaries are already counted

`_a_secondary_vp` / `_b_secondary_vp` are a **redundant unread tracker**, BUT the
same secondary VP is also added to `_a_vp` / `_b_vp` (the accumulators
`_decide_winner` actually reads) at `code/simulator.py:925` and `:954`. Wired in on
**2026-05-20** (`54e41427`, `dc07dc39`); the caps in `secondaries.py` were "tuned
2026-05-20" — i.e. tuned *while connected*. Empirically, in an Astra-vs-IK battle
`_a_vp`=61 = primary 35 **+ secondary 26**, and `_decide_winner` compares 61 vs 64.
Adding `_a_secondary_vp` into the decision (the named fix) would **double-count**.

## Finding 1 (the real driver) — the kill-secondary asymmetry

The over/under split is driven by the **kill-based** secondaries, not the position
ones. Per-secondary VP, averaged per game (Imperial Knights = A):

| Matchup | Side | BringItDown | NoPrisoners | Cull | Assassinate | Engage | BEL |
|---|---|---:|---:|---:|---:|---:|---:|
| IK vs Astra | **IK** | 12.8 | 0 | 0 | 7.2 | 10.3 | 1.3 |
| IK vs Astra | Astra | 4.0 | 0 | 0 | 0.5 | 8.7 | 5.3 |
| IK vs Tyranids | **IK** | 0.5 | **18.5** | 0 | 3.7 | 9.8 | 2.7 |
| IK vs Tyranids | Tyranids | 6.0 | 0 | 0 | 0.5 | 7.3 | 4.7 |

- **Position secondaries are roughly even or favour the opponent** (Engage ~10 vs
  ~8; Behind Enemy Lines favours the opponents). They are NOT the over-credit.
- **Kill secondaries are wildly asymmetric.** The killy durable army racks up
  Bring It Down / No Prisoners / Assassinate against its victims, while the victims
  score ~0 back — because nine durable Knights almost never die *as units* under the
  one-Unit-per-model representation, so the opponent never satisfies "destroy a
  unit". Tyranids score **0** No Prisoners against IK; IK scores **18.5** against
  Tyranids (capped, ~6 units wiped/round).

So the secondary layer **amplifies** the kill-centric bias rather than
counterbalancing it: the durable killer wins primary (camping) AND kill-secondaries
(killing), and its victims can reciprocate on neither.

## Finding 2 — the real counterbalance is missing: no action-economy secondaries

Real Pariah Nexus has a much larger tactical pool (the goal brief cites "only 2 of 9
implemented"); the sim implements **2** (Engage on All Fronts, Behind Enemy Lines)
plus the 4 fixed kill secondaries. The missing tacticals include the **action-based**
family (Cleanse, Area Denial, Sabotage, and the other "perform an action" cards —
exact card list to be confirmed against the Pariah Nexus pack before implementing).
These:

- reward **unit availability and board control**, not kills — the exact currency the
  durable army's victims (hordes, MSU board-control armies) have and the camper lacks;
- impose an **action-economy tradeoff** — a unit doing an action cannot shoot/charge
  that turn. A low-model durable army (9 Knights) cannot spare a unit for an action;
  a horde/MSU army can. This is the real-10e mechanism that taxes low-model armies and
  rewards the board-control under-shooters.

The sim models **no actions at all** (`grep` for action mechanics finds only
stratagem helpers, no Pariah Nexus action). So the one secondary family that would
counterbalance the kill asymmetry is entirely absent — and the AI has no
action-vs-fight tradeoff to play.

## Finding 3 (bonus dead-mechanic) — Cull the Horde never fires

`secondaries._is_horde_unit` reads `profile.starting_strength` / `squad_size` /
`count`, all of which are **`None`** for every horde unit (the populated field is
`max_models` — Termagants 20, Boyz 20, Poxwalkers 20). It therefore always returns
`False`, and Cull the Horde scores **0 for every army every game** (confirmed in the
table above). NOTE: fixing it in isolation rewards *killing* 10+-model squads, i.e.
it would feed the kill-secondary asymmetry (help the over-shooters) — so it is a
fidelity fix that moves the metric the *wrong* way, and must not be pulled alone as a
"lever". Fix it only as part of the even-handed secondary rebuild, or keep it flagged.

## Recommended lever (even-handed, faithful, structural)

**Implement the action-economy secondary family + a minimal action mechanic + AI that
plays toward it.** This is the faithful real-rule pool (not a nerf), applies to all
factions, and directly corrects the over/under split by giving board-control/horde
armies a scoring path that does not require killing the un-killable, while taxing the
low-model durable camper with an action-vs-fight tradeoff it cannot afford. It is a
multi-part structural wave (action state on units, 2-3 action secondaries scored from
it, AI action selection, secondary-picker + caps update, full N=40 eval), which is
why it is reported here for direction before coding.

Alternative / complementary root-cause lever: the **per-model durability tax** —
make durable low-model armies killable *as units* so opponents can score kill
secondaries against them (addresses the asymmetry from the other side). Bigger and
riskier (touches the representation core).
