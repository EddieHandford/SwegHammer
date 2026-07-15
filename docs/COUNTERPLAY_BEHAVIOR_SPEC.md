# Counterplay behaviour spec — grounded in real battle reports

Every counterplay lever must be justified by a REAL-PLAY behaviour it reproduces,
and validated by a BEHAVIOURAL test that the sim now exhibits that behaviour —
not merely by a win-rate delta. The washes of 2026-07-15 (dev-wounds, secondary,
mobility) all moved a valuation without provably moving behaviour; this spec
closes that gap. Source: five 10e Death Guard battle reports (MiniWarGaming,
transcripts via yt-dlp) — real Death Guard went 0-5.

## Behaviour 1 (PRIMARY) — a durable army holds FEW objectives, and its control DECLINES toward round 5

REAL EVIDENCE:
- Astra Militarum vs Death Guard (Ep 87): Death Guard controlled ~2 objectives
  and its primary went **4 -> 8 -> 8 -> 8 -> 3** (rounds 1-5) — flat at 2 markers
  through R2-4, then COLLAPSING to 1 marker by R5 as it was contested off.
- Sisters / Black Templars / Harlequins / Space Wolves: same shape — Death Guard
  holds 1-2 (home + one forward), never fans across 3+, and the count declines.
- Tournament-player guide: slow (~5") Death Guard "cannot spread or relocate";
  opponents take what it can't reach and it is "contested off" every non-home marker.

SIM DEFECT (measured, scoring decomposition 2026-07-15): Death Guard's per-round
primary RISES R2->R5 (7.5 -> 11.2 -> 10.4 -> 11.6, net +4.1) while the FIELD
correctly DECLINES (7.7 -> 6.9, net -0.8). Death Guard hits the 15-VP round cap
34.4% of player-rounds vs the field's 13.5% (2.5x), and wins 74-94% of its markers
UNCONTESTED into round 5. Root cause on main: `strategy.py:4105` (x1.3 posture
capture boost) + `:4125` (x1.25 "spread onto every uncovered marker") — hardcoded,
ungated, always-on for the attrition posture (Death Guard, Thousand Sons).

TESTABLE METRICS (behavioural test `scripts/_behavior_check.py`, Death Guard vs a
spread of opponents, eval-faithful archetype build):
- **B1a — mean objectives controlled per round**: target ~1.5-2.0; a fix must move
  it DOWN from the current value toward that band.
- **B1b — round trajectory sign**: control at R5 must be <= control at R3 (the
  DECLINE the tape shows); currently it RISES.
- **B1c — 15-VP cap-hit fraction**: target ~13% (the field rate); currently ~34%.

LEVER: replace the hardcoded x1.3/x1.25 posture boosts with the measured-VP value
field (`SWEG_VALUE_MOVE`, layer branch) for the attrition/objective_hold postures.
Its documented result closes the durable trio's over-poles (Death Guard / Imperial
Knights / Chaos Knights -4 to -6.4) by honest value-pricing rather than a synthetic
+30%/+25% self-reinforcement. ASYMMETRIC by construction: honest value-pricing of
objective-approach discounts the durable side's current over-crediting; it does not
uniformly boost everyone.

PASS = B1a down + B1b flips to decline + B1c down toward 13% AND the win-rate screen
shows Death Guard deflating (63.5 -> toward 47.6) without the durable over-poles
inflating. FAIL = behaviour unmoved (the lever is inert, like the 2026-07-15 washes)
OR behaviour moves but Death Guard does not deflate (the behaviour was not the cause).

## Behaviour 2 — durability-bypass firepower is aimed at the durable target

REAL EVIDENCE: Harlequins beat Death Guard with devastating wounds ("that was all
it was"); AM used multi-melta AP-4 through 2+ saves. TESTABLE: fraction of a
dev-wounds/high-AP army's damage-into-a-brick that comes from bypass weapons rises.
(The dev-wounds VALUATION fix washed; the roadmap's better form is a weapon-keyword
target-priority BONUS in `_do_shoot` — build only after Behaviour 1.)

## Behaviour 3 — a fragile army denies a durable army's reserve/landing space

REAL EVIDENCE: opponents take objectives the slow blob can't reach; force it to
over-extend. TESTABLE: `SWEG_JOB_DENY` fires for the mobile side and not the static
gunline (its input is the opponent's legal-landing-cell footprint × pending reserve
— inherently unequal across matchup shapes). Re-test on the fixed layer foundation.

## Behaviour 4 — trade cheap to deny/contest, accept an unfavourable-looking trade

REAL EVIDENCE: Sisters "throw cheap garbage, take out more than its value"; win on
objectives/trades, never killing the durable bodies. TESTABLE: a cheap unit commits
to a TIE-or-better contest on a durable holder's marker (denying its tick) at a rate
> 0 in can't-out-kill matchups and ~0 in shooting-vs-shooting. Hard gate before any
screen.

---

BUILD ORDER: Behaviour 1 first (the primary, highest-leverage, already has a measured
asymmetric lever). Behaviours 2-4 only after B1's behavioural test passes — each with
its own behavioural test written BEFORE the lever, per this spec.

---

## RESULTS — Behaviour 1 (2026-07-15)

Baseline (main, dense terrain, N=24-40 games): mean Death Guard objectives/round ~1.95,
trajectory RISES toward round 5 (R5 ~2.15 > R3 ~1.95), 15-VP cap-hit ~22%. The defect
is confirmed and measurable — Death Guard's control RISES where the tape DECLINES, and
it hits the 3-objective cap ~1.7x the field rate.

Two candidate levers were built and BOTH FALSIFIED by the behavioural test, cheaply
(~40-50 games each, no full-frame screen needed):

- **`SWEG_VALUE_MOVE` (the layer program's value field, tested on its branch, N=48):**
  moved the behaviour the WRONG way — mean objectives/round +0.06, cap-hit 27%->31%,
  trajectory still rising. Mechanism (as the layer program's own terminal experiment
  predicted): honest measured-VP pricing tells the durable side it CAN hold, so it
  commits and holds MORE. The value-move fold-in does NOT create Behaviour 1. This
  falsifies the "fold the posture boosts into the value field" plan as a Behaviour-1
  fix (it may still matter for win-rate via other channels, but not this behaviour).

- **`SWEG_GANG_DENY` (asymmetric: out-durabilitied side throws cheap bodies to contest
  a durable holder's marker, N=40):** also moved it the WRONG way — mean +0.07, cap-hit
  22%->33%. Mechanism: the boost redirects the fragile army's spare bodies onto Death
  Guard's markers, but those contests are UNWINNABLE (a cheap gang cannot out-Control
  Death Guard's stacked Objective Control before it dies), so the bodies die there AND
  vacate their own objectives, which Death Guard then takes. The "throw cheap garbage to
  deny" tape tactic BACKFIRES in the sim. Reverted (byte-identical, not a fidelity fix).

## WORLD-MECHANICS EXPERIMENT (2026-07-15) — answered: there is no broken mechanic

The falsifications above pointed to the world. The instrumented experiment (owner-approved)
asked: does the sim's Objective-Control / scoring world PERMIT a fragile side to deny a
durable Death Guard holder? Three findings, from reading the scoring code + citation and
measuring 40 baseline Death Guard games:

1. **Death Guard's sticky objectives (Virulent Vectorium "Worldblight") are FAITHFUL, not
   an implementation mistake.** The Wahapedia text: an objective Death Guard controls
   "remains under your control UNTIL your opponent's Level of Control ... is GREATER than
   yours" — a tie does not flip it; you must strictly out-Control (or kill the holder so
   its Level of Control drops). This is exactly why `SWEG_GANG_DENY` (which aimed at a TIE)
   was futile.
2. **But sticky is MINOR: only 7% of Death Guard's scores** are Worldblight-enabled (on a
   marker the enemy tied/out-OC'd). The other 93%, Death Guard wins by genuinely holding
   more Objective Control. Removing sticky would move Death Guard ~0.7 primary VP/round.
3. **The world already PERMITS eviction:** opponents out-Controlled (broke) a Death Guard
   marker ~1x/game (35 across 40 games), roughly balanced with Death Guard taking enemy
   markers (32x). The contest is not frozen.

CONCLUSION — there is NO broken world-mechanic and NO missing counterplay CHANNEL to add.
Death Guard over-holds because its DURABILITY is faithful and expresses itself as
Objective-Control persistence: durable high-OC bodies survive to hold more OC than the
opponent can cheaply muster, and evicting them needs MASS out-Control that dies to Death
Guard first. Every deny/tie lever backfires for the same reason — you cannot cheaply evict
a durable holder, and trying donates bodies and vacates your own markers. The tape's actual
counterplay is a WHOLE-GAME strategy (don't fight Death Guard; out-race on secondary and
take the markers it cannot reach) that the greedy per-unit sim AI does not execute — and
the secondary-economy half of that was already explored and washed (SWEG_SECONDARY_POSFIX;
the kill-card gap ruled rules-faithful). No lever remains; the realistic options are a
whole-game strategic planner (a research build, not a lever) or accepting Death Guard's
+16 as the Stage-2 pricing floor. See [[sim-counterplay-frontier]].

## COORDINATION EXPERIMENT (2026-07-15) — "what happens if units coordinate?"

Built `SWEG_COORD_CONTEST`: real all-or-nothing coordination (commit toward an enemy
marker ONLY when the army can COLLECTIVELY out-Control it — summed reachable friendly
Objective Control > the enemy's — and send nobody otherwise; the anti-donate guard the
reverted gang-deny lacked). Behavioural test, N=40:

- Byte-identical off. ON: mean −0.02, cap-hit unchanged (22%), **lock-breaks unchanged
  (35 → 35)** — coordination added ZERO successful evictions of a Death Guard marker.
- It did NOT backfire (sticky 7%→5%, no cap-hit rise): the anti-donate guard correctly
  DECLINED the unwinnable evictions instead of donating bodies.

VERDICT: coordination is inert. The binding constraint was never the AI's coordination —
it is that the fragile army cannot muster enough SURVIVING Objective Control to out-Control
Death Guard even all-together (and committing everything loses its own markers). This is
the THIRD independent confirmation that the bottleneck is faithful DURABILITY, not the
decision architecture. Reverted.

IMPLICATION for the whole-game planner (element 2): its value is NOT "coordinate to evict
Death Guard" (proven useless) — it is STRATEGIC ABANDONMENT: the fragile side deliberately
does NOT contest Death Guard's markers and instead maximises total victory points
everywhere else (secondary + the objectives Death Guard cannot reach), the tape's actual
counterplay ("your bodies were untouchable; I won on trades and objectives elsewhere").
That is a different OBJECTIVE FUNCTION (maximise whole-game victory points, choosing which
fights to decline), not a better contest heuristic — which is why only a whole-game planner
can express it and no per-turn lever ever will.
