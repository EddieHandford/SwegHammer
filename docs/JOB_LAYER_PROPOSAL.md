# Job/commitment layer — design proposal and retirement register (owner-originated, 2026-07-10)

Owner's framing, verbatim in spirit: the combination of the layers should let
units dynamically adapt to the changing battlefield, plan ahead, and position
efficiently for their specific goal; each faction has its own definition of
those goals, and different units have different priorities of "not die" versus
"kill stuff".

## Why this is the missing element (the measured argument)

The 2026-07-10 screen program proved the three substrate fields are
individually sound and jointly insufficient:

- Value field alone (global): fixes the durable trio (Death Guard, Imperial
  Knights, Chaos Knights close −4 to −6.4 in every configuration) and breaks
  the five kill-tempo factions — their win condition is output positioning,
  which the field prices at zero.
- Value + offense (global, both pricings): the terms CANCEL — the offense term
  hands the durable trio their kill-play back, erasing the trio closure, while
  the kill-tempo five recover. Headline worse than anchor both iterations.
- Per-faction enable masks: only the exact five-faction mask reads sub-target
  (1.95/1.79) and it does so through a compensating pair (World Eaters'
  self-handicap offsetting soft masked opponents) — pole-trading, not fidelity.

Mechanism: every configuration gives EVERY unit in EVERY faction the same
utility function. Real armies are heterogeneous — a cheap high-objective-control
infantry squad's expected victory-point contribution comes from holding; an
Eradicator squad's comes from killing; a 400-point centrepiece prices its own
survival differently than 60-point chaff. The missing element is per-unit
CHANNEL WEIGHTING derived from the unit's own capabilities, plus army-level
job assignment so labour divides instead of duplicating.

## Design

**Channels.** For each unit, per activation, price its candidate contribution
in the field currency (points/victory-points, the existing
`_trade_vp_per_wound` exchange — no new constants):

- HOLD: the value field V(p) over reachable markers (built: `value_projection`).
- KILL: the offense term over reachable positions (built: `SWEG_VALUE_OFFENSE`
  iteration 2, best-single-target, move-class-conditional with the full
  eligibility exemption web).
- SURVIVE: the threat field T(p) priced against the unit's own remaining value
  (built: `_threat_field_at` + frac-at-risk).
- (Later: ACTIONS — secondary/action economy as a fourth channel; the existing
  `_unit_can_perform_action` opportunity-cost predicate is the prototype.)

**Specialisation.** A unit takes the job it is best at — argmax over channels
of its own expected contribution — instead of the equal-weight sum that
measurably cancels. Role priors come from the same arithmetic (objective
control per point, damage per point, wounds per point), NOT from the
`classify()` labels: the tank-screen rejection is the recorded precedent that
the coarse labels misclassify centrepiece melee monsters (Mortarion classifies
DUAL/HEAVY, not MELEE).

**Assignment (plan ahead).** An army-level pass allocates jobs before units
move: one holder per marker where one suffices (the pile-on failure), kill
jobs de-duplicated toward collective cracks (the adopted `SWEG_FOCUSFIRE`
nomination is the prototype), assignments persistent across activations unless
strictly dominated (no hysteresis constant — re-assign only when another
channel's priced value strictly exceeds the committed one). Deterministic
greedy assignment, zero random draws.

**Faction identity is emergent.** No faction names anywhere in the layer.
Playstyle differences must fall out of list composition (Guard = cheap
high-objective-control bodies + artillery → screen/hold/shell). The existing
`FACTION_POSTURE` table (strategy.py:77) is the enumerated stand-in this
replaces — its retirement is the doctrinal heart of the build.

**Open design question (owner input taken 2026-07-10).** World Eaters'
`_we_glory_charge_bonus` encodes non-expected-value commitment doctrine ("charge
anything") that pure channel arithmetic cannot express — and World Eaters'
pole instability was the mask grid's central artifact. v1 keeps that reflex
(category KEEP-for-now below) and the screen will show whether derived kill-
channel weighting suffices for World Eaters or whether doctrine-weighted
commitment needs a designed home.

## Retirement register (two-agent survey, 2026-07-10, both files read in full)

Categories: **A** = retire when layer on (bypass behind the layer gate);
**B** = keep (the fields cannot express it); **C** = the layer must answer a
design question before it can absorb this; graveyard = already deleted.

### A. Movement/positioning reflexes (the reflex museum the layer's move consumer replaces)

| Item | Status | Subsumed by |
|---|---|---|
| Ranged-hold family: `SWEG_AM_ADVANCE_DISCIPLINE`, `SWEG_CK_RANGED_HOLD`, `SWEG_VOTANN_RANGED_HOLD`, `SWEG_TSONS_RANGED_HOLD`, `SWEG_SOROR_RANGED_HOLD`, `SWEG_ARTILLERY_HOLD`, `SWEG_AM_FIRE_SUPPORT_HOLD` (adopted); `SWEG_ADVANCE_DISCIPLINE`, `SWEG_TYRANIDS_RANGED_HOLD`, `SWEG_ASTARTES_RANGED_HOLD`, `SWEG_EC_RANGED_HOLD` (held) | mixed | offense term (its textbook derivation) |
| Staging family: `SWEG_AM_STAGING` (adopted), `SWEG_STAGING`, `SWEG_AM_CHAFF_STAGING` (held — `SWEG_STAGING`'s own ledger entry predicts this fold) | mixed | threat field at destination |
| Kiting family: `SWEG_KITE_MOVE`, `SWEG_KITING`, `SWEG_KITE` (all held; retire as a chained pair with fall-back) | held | threat + value |
| Fall-back family: legacy branch, `SWEG_DISPLACE_FALLBACK` (adopted), `SWEG_SQUAD_ESCAPE` (adopted), melee-class exclusion | mixed | threat + value + offense |
| Objective cluster: `SWEG_MASS`, `SWEG_FREECONTEST`, `SWEG_CONTEST` (adopted), `SWEG_M4`, `SWEG_DISPLACE_SWARM`, `SWEG_MELEE_HOLD_OBJECTIVE` (held) — four adopted levers solving one V(p) argmax from four trigger conditions | mixed | value field + assignment |
| Posture machinery: `FACTION_POSTURE` table, shimmy-step, alpha/fast-strike round-1 scripts, posture objective multiplier, attrition spread tie-break | baseline | emergent from channels (doctrinal centrepiece) |
| `classify()` role dispatcher in `pick_move_intent` + charge-desire role partition (`_wants_to_charge`, MELEE/DUAL/SHOOTY gating) — highest-leverage single retirement | baseline | channel arithmetic |
| `_wounded_seek_obscuring`, wounded-retreat branch, AI-9 sacrificial chaff, DUAL engage block, marginal-holder hold | baseline | threat/value/assignment |
| Deep-strike placement scoring (`_pick_arrival_point`, drop-anchor weights) — timing schedule stays | baseline | threat + value at candidate cells |
| Transport voluntary disembark (`_maybe_disembark_before_move` base + `SWEG_TRANSPORT_PLAY` held) | mixed | offense (ride vs act pricing) |
| Activation-order score baseline (`activation_queue`) | baseline | assignment (highest marginal value first) |

### A2. Targeting terms that are early hand-built field instances (fold directly)

`SWEG_THREATPRIO`, `SWEG_TARGET_ECONOMICS`, `SWEG_AM_CHASE_VP`, `SWEG_FOCUS_FIRE`
(all held; their docstrings self-identify as field prototypes); `#C2` won't-crack
penalty; `SWEG_TARPIT` + the Ork/Tyranid/Daemon tarpit bonuses; the faction
charge biases (`_custodes_horde_penalty`, `_drukhari_*` pair,
`_knight_melee_commitment_bonus`, `_gunline_charge_bonus`);
`_screen_target_bonus`, `_transport_target_bonus`, `_drukhari_fragile_flyer_bonus`
(need the threat field as a counterfactual: threat-with vs threat-without the
target alive); stratagem-target helpers (`_highest_threat_enemy`,
`_highest_dpa_unit`, `_most_vulnerable_unit` — the reverse-coupling refinement).
`SWEG_FOCUSFIRE` (adopted) and `SWEG_SQUADSHOOT` (adopted) graduate into the
assignment pass rather than retiring. `SWEG_PERSISTENT_NOMINATION` family (held)
is the commitment-memory prototype.

### B. Keep — the fields cannot express these

- Rule-grounded synergy target biases: `_astartes_oath_target_bonus`,
  `SWEG_VOTANN_PE_TARGET_BIAS`, `SWEG_CK_DREAD_FOCUS` (codex triggers that
  compound on a specific target — not retirement candidates).
- Make-way / collision deconfliction (`SWEG_MOVEPLAN`/`SWEG_COLLISION` family)
  — spatial legality plumbing the layer sits on top of.
- Transport forced-disembark charge-lock (rules citation, not a choice).
- AI-lab pilot hooks (`_pilot_move`/`_pilot_charge`/`_pilot_focus`) — infrastructure.
- `SWEG_MELEE_CAGING` (held; verified present in code) — encirclement angular
  geometry a scalar T(p) does not carry; preserve, possibly later as a T(p)
  extension.

### C. Design questions the layer must answer before absorbing

- `_we_glory_charge_bonus` (non-expected-value doctrine — see open question).
- `_synapse_target_bonus` (army-wide battleshock cascade — needs an army-scope
  term).
- Aeldari Battle Focus advance trigger (real token state embedded in a
  movement reflex — the mechanic must be re-homed, not deleted).
- Pregame transport embark selection (no positions exist yet — needs a
  pre-deployment value proxy).
- Flank-coordinated activation plan (`coordinated_army_plan`, off in vanilla)
  — genuine multi-unit sequencing beyond v1 scope.

### Known reflex fights the layer fixes by construction

1. `SWEG_ARTILLERY_HOLD` early-returns before the kite branch: artillery can
   never kite out of a lethal charge regardless of the kite gate (ordering bug).
2. The four-lever objective cluster: four disjoint trigger conditions for one
   V(p) argmax.
3. `SWEG_MELEE_CAGING` and `SWEG_DISPLACE_FALLBACK` both narrow the same
   fall-back branch from different justifications; caging's angular information
   must be preserved at its fold.
4. `SWEG_KITE` is causally downstream of fall-back firing — retire as a pair.

## Fold discipline

Gate `SWEG_JOB_LAYER`, default off, byte-identical off. When ON, the move
consumer routes through channel-pricing + assignment and BYPASSES category-A
movement reflexes (they stay in the code untouched; the gate chooses the
path), so every screen measures "job layer versus the reflex museum" on one
frame. Nothing is deleted until the layer beats the museum on the standing
metric AND the pilot boards. Category-A2 targeting folds are v2 scope —
v1 is movement only, plus the assignment pass. Retiring adopted reflexes
changes committed defaults — the whole package screens as one lever with the
usual reproduction check at adoption time.

## Pre-registration (v1 screen, N=40 vs sc62a, global — no faction names in code)

EXPECTATIONS: Astra Militarum moves toward real (role division is the first
mechanism aimed at its intra-army structure: infantry holds/screens while
artillery kills); the durable trio's closure survives via derived holder roles
(their units really are holders) WITHOUT the offense term handing their
kill-play back (specialisation prevents the cancellation); the kill-tempo five
stay at anchor or better (their units derive kill roles); World Eaters is the
acid test — stable near real without any mask.
FALSIFIERS (any one fails the cell): any calibrated faction breaks beyond
noise; the trio re-opens; Astra Militarum decisively away; headline above the
anchor's 2.60. MECHANISM INSTRUMENTS: job distribution per faction (holders /
killers / survivors as fractions — Guard must split, Knights must not),
pile-on rate (markers with >1 assigned holder — must fall), and the
walked-into-it rate (the threat proposal's falsifier, finally with a fair
shot: movement is where exposure lives).
STOP RULE: v1 as specified, at most one pre-registered pricing correction of
the same kind as the offense lane's (a flagged convention deviation), then the
lane stops and the owner decides.
