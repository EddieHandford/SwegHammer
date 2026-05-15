# Faction Audit F5b — Adeptus Astartes under Vanilla 10e Default

Re-run of F5 (`FACTION_F5_MARINES.md`) after `ddb44db Flip simulator default to
vanilla WH40k 10e`. The simulator now runs I-go-you-go player turns, no
alternating activations, coordinated army-plan disabled, CP catch-up off, no
simultaneous movement. Marines diff vs real-meta was +18.1pt in SwegHammer
mode, +16.4pt in vanilla — only marginally improved. This audit re-tests
whether the OC-stack hypothesis still holds under the new combat model.

## Method

Same as F5 — `scripts/marines_diag.py`, 30 seeded archetype battles per
matchup, Marines (Gladius Strike Force) vs each of 9 opponents at 1000 pts,
`use_archetype=True` both sides. No script edits; vanilla default is picked up
automatically via the `Battle` ctor.

## Per-matchup results

| opp | WR% | rnd | M attk | oath% | doctr% | M_OC | O_OC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Necrons          | 13.3 | 5.00 | 47.4 | 10.37 | 43.19 | 1.04 | 1.28 |
| Aeldari          | 66.7 | 4.87 | 38.7 | 13.53 | 40.06 | 1.00 | 0.52 |
| Tyranids         | 43.3 | 5.00 | 45.9 |  9.76 | 42.96 | 0.95 | 1.35 |
| Orks             | 63.3 | 5.00 | 58.4 |  9.59 | 41.40 | 1.08 | 1.00 |
| T'au Empire      | 76.7 | 4.87 | 42.5 | 23.21 | 42.76 | 0.95 | 0.40 |
| Death Guard      | 46.7 | 5.00 | 48.0 | 14.12 | 42.80 | 1.05 | 0.69 |
| Adeptus Custodes | 56.7 | 5.00 | 57.6 | 13.96 | 42.63 | 1.14 | 0.88 |
| Thousand Sons    | 80.0 | 5.00 | 49.7 | 19.26 | 38.99 | 1.22 | 0.50 |
| Leagues of Votann| 73.3 | 5.00 | 49.5 | 11.31 | 38.03 | 1.11 | 0.57 |
| **OVERALL**      | **57.8** | — | — | **13.90** | **41.42** | **1.06** | **0.80** |

## Comparison: F5 (SwegHammer) vs F5b (Vanilla)

| Metric | F5 SwegHammer | F5b Vanilla | Delta |
|---|---:|---:|---:|
| Overall WR | 68.1% | 57.8% | -10.3pt |
| Marine attacks / battle | ~91 | ~48 | -47% |
| Oath% | 10.56 | 13.90 | +3.34 |
| Doctrines firing % | 50.41 | 41.42 | -8.99 |
| Marine OC mean | 1.35 | 1.06 | -0.29 |
| Opponent OC mean | 0.93 | 0.80 | -0.13 |
| **OC gap** | **+0.42** | **+0.26** | **-0.16** |

WR dropped 10.3 pts. Real-meta Marines WR is ~52%, so diag shows +5.8pt over
real-meta; the briefed +16.4pt diff is from the wider calibration run, not the
9-archetype N=30 subset (consistent with F5 — diag undershoots full-meta diff).

## Hypothesis re-test

### H1 — Oath generosity: still FALSIFIED

Oath% rose 10.56 → 13.90 (Marines target the oath unit slightly more often
under vanilla — likely because fewer activations per side means Marines blow
their attacks on the high-value target rather than chewing screens), but
still nowhere near the ~80% predicted if oath were over-firing. T'au matchup
spikes to 23.2% — Crisis suits become the natural lowest-health target AND
the oath target — but no systematic over-application. Not the bug.

### H2 — Doctrines firing rate: still NEUTRAL

41.4% (down from 50.4%) of Marine attacks land on the boosted (round, mode)
gate. The drop is mechanical: under I-go-you-go, more Marine attacks happen
in later rounds after attrition, so the round-1 ranged window contributes a
smaller fraction. No anomaly — the gate is firing at the expected arithmetic
rate given the new round distribution.

### H3 — OC stack: STILL CONFIRMED, but ATTENUATED

Marines still outscore on OC in 7 of 9 matchups (vs 8 of 9 under SwegHammer
mode). Necrons (1.04 vs 1.28) and Tyranids (0.95 vs 1.35) now beat Marines on
OC — Necron Warriors and Tyranid swarms get more uninterrupted objective
time under vanilla because Marines no longer rip them off objectives via
alternating activations. OC gap halved (+0.42 → +0.26) but is still the
dominant driver: vs Thousand Sons (1.22 vs 0.50) and T'au (0.95 vs 0.40)
Marines park MEQ OC where the opponent has Crisis suits / Rubric Marines
that can't shift Intercessors.

The 2× Intercessor archetype seed (`code/archetypes.py:57`) is still the
mechanical root cause — losing alternating activations attenuated but did not
remove its impact, because what Intercessor stacking buys is **survival on
objectives across a 5-round game**, which is independent of activation order.

## Root cause statement

**Unchanged from F5**: Marines' OC stack from the 2× Intercessor archetype
seed (10 OC per squad × 2 squads = 20 OC deterministic floor) drives the
sustained primary-objective scoring. Vanilla mode halved the magnitude of
the OC gap but Marines still over-win the 7 matchups where opponents lack
comparable troop OC (Aeldari Falcons OC 2 but only 1-2 of them; Custodes
OC 1 across the board; T'au Crisis OC 1; Thousand Sons Rubric OC 1).

## Proposed next fix

**Task #179 (Marines random_fill Intercessor cap) is still the right move.**
The mechanical lever — the deterministic 2-Intercessor seed — is unchanged
by the vanilla flip. Drop the Gladius archetype seed from 2 to 1
Intercessor squad and add a random-fill cap so the second Intercessor isn't
re-picked stochastically. Expected effect under vanilla: pull Marines from
57.8% WR to ~52% (parity with real-meta), and pull full-meta diff from
+16.4 to within the ±5pt band.

Secondary observation (not for this fix): Necrons now BEAT Marines (13.3%
WR). Necron OC is 1.28 vs 1.06 — Warrior squads + Reanimation Protocols
under vanilla I-go-you-go gives Necrons multiple turns to recover bodies
on objectives. Flag for future Necrons audit, but Marines' #179 takes
priority.
