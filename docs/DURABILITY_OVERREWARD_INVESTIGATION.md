# Durability over-reward investigation

> ## RESOLVED 2026-06-28 — the "representation re-model" is not an open solution
>
> See `docs/STRUCTURAL_REMODEL_PLAN.md` top block for the full verdict. In short:
> the representation root described below is **real but has no faithful fix**. The
> contest math is faithful (10th edition counts only models within 3" of a marker),
> so a scattered horde genuinely under-controls; the only faithful remedy is
> clustering models onto the marker (`SWEG_MOVEPLAN`, already built), and the
> project's own stranding diagnostic predicts that washes because it helps the
> over-pole and under-pole hordes alike without changing who survives the snapshot.
> The "fragile-army representation fix" this document's section 3 keeps deferring to
> was never defined and is dropped. The genuinely open lead is the going-first /
> tempo over-reward (`SWEG_KITE`), **not** a representation re-model. Treat the
> sections below as the diagnosis that reached this conclusion, not as a live work
> queue.

This document records where the simulator over-rewards durable, low-model armies
(Imperial Knights, Chaos Knights, and the wider elite or vehicle over-pole), the
precise mechanism with code evidence, the faithful surviving candidate corrections
after a knob-check pass, the diagnostic that must be run before any build, and the
forbidden-zone guardrails that bound the whole investigation. Every term is written
out in full per standing rule eleven; no acronyms, no invented numbers.

The calibration target is real-game win rates under the real printed tenth-edition
rules. By the project's own standing principle (decision ledger line twenty-six) a
residual is always a missing or mis-modelled mechanism, never a "floor", as long as
a faithful mechanism that corrects it can still be identified. That principle frames
everything below.

---

## 1. Root verdict

**The durability over-reward lives in the representation layer, not in the combat
damage model. The combat damage model is a genuine faithful floor and must not be
touched. A global Stage-one floor cannot yet be honestly declared, because the
representation axis is not yet exhausted.**

Three separate sub-verdicts, in order of confidence:

1. **Combat damage model — faithful floor, closed.** Feel no pain
   (`code/units.py:1498-1504`), best-of save versus invulnerable save
   (`code/units.py:3289-3413`), excess-damage-lost allocation with current health
   clamped at zero (`code/units.py:4148-4198`), and rolled per-shot damage
   (`SWEG_ROLLDMG`, default-on) all match the printed rules. Direct experiments
   confirm this is not load-bearing: the wave-two-hundred-fifty-three combat sweep
   washed or regressed, and the wave-two-hundred-sixty ability accuracy audit removed
   eight genuine over-credits yet the metric washed from three point four eight to
   three point four five. The only live combat-path inaccuracy found is at
   `code/units.py:4806` (the `total_damage` accumulator over-counts phantom damage on
   a lethal shot); it is confined to `UnitShot` logging and displacement-tap
   instrumentation and never reaches scoring, victory points, or kill awards (a kill
   is decided by `is_alive` / `current_health > 0` at `code/simulator.py:12009`).
   Durability statistics — toughness, wounds, saves, invulnerable saves, feel no pain
   — are forbidden to nerf and correctly so.

2. **Scoring layer — the one clean over-reward already removed.** The
   surviving-points tiebreaker (a durable survivor winning an equal-victory-point game
   on points-on-the-board) was the single clean scoring-layer over-reward, and it was
   already removed by `SWEG_VP_TIE_DRAW` for a gain of zero point six six.

3. **Representation layer — the live, un-exhausted root.** This is where the
   over-reward currently lives. It is not a single bug but the interaction of two
   pieces, each faithful in isolation, that together diverge from real tenth-edition
   primary scoring. See section two.

The real meta is the proof that this is a missing mechanism and not a floor: the Warp
Friends aggregate has Imperial Knights at roughly forty-seven point seven percent and
Chaos Knights at roughly forty-four point seven percent. Durability does **not**
dominate reality, so the simulator's durable over-pole is a missing-mechanism
signature, not an irreducible floor.

---

## 2. The mechanism, with code evidence

Two faithful-in-isolation pieces combine into the over-reward.

### 2.1 The one-Unit-per-model substrate

`code/army.py` builds every physical model as its own `Unit` with a distinct squad
identifier. A ten-model squad becomes ten independently-removable contestants rather
than one cohesive body. This is confirmed and deliberately kept design, not a misread:
decision ledger line twenty-one records the triple-check verifying that one-Unit-per-model
is true and that the summed-per-model contest is faithful tenth-edition "Level of Control".

### 2.2 The survivor-snapshot objective contest

`code/simulator.py:995-1069` (`_assign_army_oc`) sums the effective Objective Control
of only the models currently alive and within base-reach of a marker. The marker is
then awarded to the strictly-greater sum at `code/simulator.py:1186-1190`
(`a_oc > b_oc`). Both the contest math and the per-Command-phase scoring timing are
individually faithful: primary victory points are scored at the start of each player's
turn on the objectives controlled then (`code/simulator.py:10209`, `SWEG_CMDSCORE`,
default-on), which is the real tenth-edition timing.

### 2.3 Why the two faithful pieces over-reward durability together

The snapshot is evaluated on a board where fragile models have **already** been removed
model-by-model during the preceding player's full turn — movement, shooting, charge,
and fight all resolve before the next scoring window
(`code/simulator.py:10198-10210`). A durable single-model unit (an Imperial Knight,
Objective Control nine to ten) is alive and on the marker at every snapshot and banks
its full Objective Control unopposed. A fragile horde that physically held the marker
contributes zero the instant its models die, with no fractional credit for the time it
held. The wave-ninety-three stranding drill measured six-inch-versus-three-inch
Objective Control ratios of two point six five (Chaos Daemons) to three point zero one
(Necrons): roughly half to two-thirds of a horde's near-marker Objective Control is
stranded in the three-to-six-inch ring and never enters the contest — a gap that does
not exist for a single base parked on the marker centre.

### 2.4 Three experiments that pin the root to representation

- **Wave two-hundred-sixty (ability fidelity not load-bearing):** removed eight genuine
  ability over-credits; levers fired heavily (World Eaters one hundred thirty-three
  flips, Death Guard two hundred seventy) yet the metric washed three point four eight
  to three point four five.
- **Wave two-hundred-fifty-three (on-table levers all wash):** five on-table levers
  (mass-bodies, mass-tanks, gunline-hold, focus-fire, screening) and the combat-math
  levers (melee wound allocation, variable attacks, fight-phase alternation) all washed
  or regressed. You cannot out-position, out-shoot, or out-fight an over-reward that
  lives in the contest snapshot.
- **Pilot-review experiment (good play is durability-biased):** making the artificial
  intelligence faithfully better move-by-move regressed the metric three point four five
  to six point zero five, with the gain concentrated on durables (Imperial Knights plus
  eighteen point four, Chaos Knights plus twenty-one point one, versus Astra Militarum
  plus eight point nine). A durable unit that reaches a marker holds it through the
  snapshot; a fragile one that reaches it dies before the snapshot fires.

This is why the gated three point four five is a **compensating-errors equilibrium**:
the production simulator's deliberately crude artificial intelligence under-delivers all
armies to markers symmetrically, masking the structural over-reward. Every faithful play
improvement un-masks it.

---

## 3. Surviving candidate corrections (after knob-check)

Each candidate was passed through the knob-check, which asks: (a) does it correct a
genuine modelling divergence derivable without reference to the target win rates, and
(b) does it reduce a faithful durability statistic or gate off a faithful mechanic. None
of the four is a disguised durability nerf, so none is dropped on that ground. The
verdicts below are **proceed / revise** with the revisions applied; the practical effect
is that no candidate is cleared to build standalone today, and two are blocked behind a
diagnostic or an upstream fix.

### 3.1 Squad-as-cohesive board-control actor (the M4-alpha clustering fix) — REVISE; do not build, run the self-veto diagnostic first

- **Faithful basis:** in real tenth edition a multi-model squad holds an objective as a
  coherent body, contributing its whole surviving Objective Control until broken. The
  simulator scatters the squad into independent `Unit` instances that drift into the
  three-to-six-inch stranding ring and contribute zero. The fix overrides each member's
  move target to a deterministic clustered slot near the marker centre when its intent is
  capture or steal and it is within reach. It invents no Objective Control, applies no
  Objective-Control-to-victory-point conversion factor, and branches on neither faction
  nor model count. A one-model Knight squad gets the centre slot — an exact no-op. Not a
  durability nerf.
- **Critical knob-check finding:** the mechanism is **already built** and only dormant
  behind a default-off gate (`SWEG_MOVEPLAN`); `code/simulator.py:_make_way_target`
  (around line 10734) already sends each capturing squad model to a coherent ring slot.
  So this is an A/B of an existing gate, not a build wave.
- **Strong negative prior:** the wave-ninety-four clustering candidate (`SWEG_CLUSTER`)
  tried exactly this and regressed four point one five to four point three zero, because
  pulling models tighter helped whoever already held the marker (the over-shooters / the
  durable pole), not the non-reachers. Worse, even on geometric success the durability
  root survives: clustered fragile bodies still die before the next snapshot fires, so
  the recovered Objective Control evaporates. The plan's own pre-agreement is that
  M4-alpha alone is expected to wash; its value exists only stacked.
- **Revision applied:** do not flip the gate as a standalone build. Run the binding
  self-veto diagnostic first (section four). If the stranding ratio is already near one
  (closed by `SWEG_MASS`, the displacement fallback, and collision), the geometry gap is
  not live and the candidate is moot.

### 3.2 Tarpit-charge valuation (`SWEG_TARPIT`) — REJECTED (dropped)

- **Why kept out of the build set:** faithful in construction (Big Guns Never Tire is
  correctly modelled at `code/simulator.py` around lines 11669-11710; the won't-crack
  penalty at `code/strategy.py:1577` genuinely suppresses a pin-charge) and **not** a
  durability nerf. But it is already built (`SWEG_TARPIT`, default-off) and was screened
  inert at wave one-hundred-twenty-nine: tarpit alone washed (gated four point three four
  to four point four three) with Imperial Knights unchanged, and M4-plus-tarpit equalled
  M4-alone, clawing back none of the over-pole. The recorded reason is the answer to this
  whole investigation: games are decided on primary board control, not combat output, so
  denying a Knight's shooting cannot move the durable over-pole. Re-attempting it would
  re-burn a settled result. The shipped code is also thinner than described — it adds a
  pin-value term to the charge valuation but does not model the engaged Knight's
  Fall-Back-versus-shoot-at-minus-one decision.

### 3.3 Missing anti-durability primary missions and Tactical action cards (`SWEG_SECONDARY` plus three missing cards) — REVISE; blocked behind a fragile-army representation fix

- **Faithful basis:** the three unimplemented Chapter Approved twenty-twenty-five to
  twenty-twenty-six Tactical action cards (Establish Locus, Recover Assets, A Tempting
  Target) are real printed cards with a self-documented gap
  (`code/secondaries.py:123-128`). The action-economy taxes a nine-unit Knight army
  cannot pay while a twenty-unit horde can — an emergent unit-count pinch with no faction
  branch and no statistic change. Not a durability nerf.
- **Factual correction applied:** the candidate's claim that the primary deck "falls back
  to Take-and-Hold for seven of ten missions" as an unaddressed divergence is wrong about
  production state. The primary-mission deck rotation (`SWEG_PRIMARY_DECK`) is already
  default-on and **is** the production frame; the seven-mission fallback is labelled an
  honest partial in the code (`scripts/evaluate_vs_meta.py:227-229`). The only real work
  is to model the seven missing missions — a large faithful build, not a quick correction.
- **Hard block:** the secondary half is a confirmed compensating error
  (`data/_secondary_vp_diagnosis.md`): the faithful two-card secondary fix regressed the
  gated metric by one point five five at eighty games, cratering Astra Militarum from
  twenty-six point eight to fifteen point five and spiking Imperial Knights from
  fifty-seven point eight to seventy-two point eight, because the secondary over-count is
  a net-positive compensating error propping the fragile under-pole. The ledger rules this
  closed: do not reattempt the faithful fix standalone; it is blocked behind an
  Astra-Militarum / low-model-fragile representation fix.
- **Revision applied:** pursue the three action cards purely as fidelity (cited per rule
  ten, default-off, byte-identical) if at all; never flip `SWEG_SECONDARY` on standalone;
  build only jointly with, or strictly after, the fragile-army representation fix.

### 3.4 Confirm-and-close the going-first over-reward residual — REVISE; run the measurement, do not pre-authorise a build lever

- **Faithful basis:** the cleanest faithful-target class — an external real-meta
  reference. `docs/REAL_META_SIGNATURES.md` signature two gives a real going-first win
  rate of forty-nine to fifty-two percent; the simulator measured sixty-six percent at the
  wave-two-hundred-fifty-two diagnosis. A going-first rate above the real band biases
  toward durable armies, which both deliver an effective alpha strike and survive the
  counter-alpha better than fragile hordes — a residual durability over-reward sourced in
  turn tempo, not in any statistic. The first-turn roll-off is faithfully modelled
  (`code/simulator.py:9982-10001`, `SWEG_ROLLOFF_ONCE`). Not a durability nerf.
- **Why the measurement is fresh:** the residual has never been re-read on the current
  frame after the challenger-cards adoption (`SWEG_CHALLENGER_CARDS`, wave two-hundred-
  fifty-two) that directly attacked it; the sixty-six-percent figure predates that
  adoption.
- **Revision applied:** run the measurement leg only. Do not pre-authorise the unspecified
  "tempo mechanism" build leg — every concrete tempo realisation tried so far is refuted
  (kiting `SWEG_KITE_MOVE` moved going-first seventy-four to fifty-six but cost zero point
  seven zero to the headline; the round-five going-second scoring `SWEG_R5_SECOND_LAST`
  screened zero point three five worse and is a load-bearing compensating error; the
  companion `SWEG_FIRSTPLAYER_STABLE` is a screening-robustness tool, itself roughly plus
  zero point seven to the headline because going-first is over-rewarded, and adopts only
  alongside a working fix that does not exist). If the rate is already in band, the
  residual is closed and nothing follows. If it is still high, the finding is diagnostic:
  it localises the over-reward back in the representation snapshot (the alpha-striker
  removes fragile bodies before their first scoring window), confirming the structural
  root rather than yielding an independent lever.

### 3.5 Surviving candidate set

After the knob-check, the surviving faithful candidates (none cleared to build
standalone, each gated as above) are:

1. Squad-as-cohesive board-control actor (M4-alpha clustering) — diagnostic-gated.
2. Missing anti-durability primary missions and Tactical action cards — blocked behind a
   fragile-army representation fix.
3. Confirm-and-close the going-first over-reward residual — measurement only.

The tarpit-charge valuation is **dropped** (already screened inert; re-burning settled
ground).

---

## 4. Recommended first diagnostic (instrument-first, before any build)

**Do not build anything first. Confirm the over-reward is a live, contested-concentration
gap, not an already-closed or uncontested one.** Three read-only instruments already exist
in the repository (`scripts/diag_stranding.py`, `scripts/diag_overscore.py`,
`scripts/diag_signatures.py`). Run them in this order.

1. **Stranding ratio (`scripts/diag_stranding.py`, `SWEG_STRAND_INSTR`).** Record, per
   faction per round, the on-marker (within-three-inch) Objective Control delivered versus
   the within-six-inch Objective Control. Confirm the horde six-inch-to-three-inch ratio is
   still above roughly one point three — that the geometry gap is real and not already
   closed by the default-on `SWEG_MASS`, the displacement fallback, and collision. **If the
   ratio is already near one, the geometry is not the live gap and the M4-alpha candidate is
   moot** — this is the binding self-veto.

2. **Contested-versus-uncontested durable wins (`scripts/diag_overscore.py`,
   `SWEG_OVERSCORE_INSTR`).** Confirm whether durable wins are contested (an opponent was on
   the marker and lost the count — a concentration over-reward that clustering would address)
   or uncontested (the opponent never arrived — a different, movement gap that clustering
   does not touch). This decides whether the representation candidate is even pointed at the
   right gap.

3. **Going-first signature (`scripts/diag_signatures.py`, signature two, at least one
   hundred fifty games on the current frame).** Read the going-first win rate directly
   against the forty-nine-to-fifty-two-percent real target. This is both the diagnostic and
   the gate for candidate 3.4: in band means the tempo residual is closed; still above
   fifty-two percent means the over-reward is live in tempo, which most likely routes back to
   the same representation snapshot.

A concrete combat-throughput sanity check is also worth recording while the instruments run,
to keep the combat-floor verdict honest: measure the simulator's damage-to-kill-an-Imperial-
Knight against the real expected anti-tank throughput a meta list brings, and confirm the
simulator is not under-killing the durable unit relative to reality. The combat sweeps say it
is faithful; this check makes that claim auditable rather than asserted. It is a measurement
only — it authorises no statistic change (section five).

**Decision rule after the diagnostics.** If the stranding self-veto or the overscore check
shows the gap is already closed or uncontested, stop — the representation candidates are moot
and the gated metric near three point four five stands as the one-Unit-per-model floor;
report it. If the gap is live and contested, the user-authorised path is to A/B the existing
M4-alpha gate (and only then consider the stacked package), measure at eighty games, and if it
washes — the strong frozen-under prior — then the representation floor is genuine and gated
three point four five stands; report it and stop. Until that stack is measured, declaring three
point four five a floor would repeat the premature-floor error the project already retracted
once (decision ledger lines twenty-five to twenty-six).

---

## 5. Forbidden-zone guardrails

These bound the entire investigation. They are the difference between a faithful correction and
a tune-to-win-rate dial.

- **Never nerf a faithful durability statistic.** Toughness, wounds, saves, invulnerable saves,
  and feel no pain are faithful to the printed rules and must not be reduced to lower the durable
  factions' win rate. The combat damage model is a closed faithful floor.
- **No Objective Control knob.** Do not invent Objective Control, do not scale it, and do not
  apply any Objective-Control-to-victory-point conversion factor. The summed-per-model contest is
  faithful; corrections must move models, not multiply their contribution.
- **No faction or model-count branch.** A correction that fires only for Knights, or only for
  low-model armies, is fitting the list rather than modelling the rule. Every candidate above is
  emergent (a one-model unit is a no-op; a horde benefits because it has more bodies), never
  branched.
- **No rate dial without an external real-meta reference.** Battle-shock application rate and melee
  lethality have no external reference, so adjusting either "rate" is forbidden — this is the
  retracted-then-reinstated tension in the decision ledger. Going-first win rate is the exception:
  it has a published external target (forty-nine to fifty-two percent), so measuring against it is
  faithful.
- **Do not gate a faithful mechanic off to chase the metric.** The reverse — turning on a faithful
  mechanic that is a confirmed compensating error in isolation — is equally forbidden standalone:
  the secondary layer makes the metric worse alone because it un-masks the fragile under-pole, so it
  ships only jointly with the representation fix.
- **Cite every rule (standing rule ten).** Any new action card, mission, or rule-bearing gate needs
  a verbatim Wahapedia citation and a `data/rule_citations.json` entry. If a citation cannot be
  found, stop and ask the user — do not approximate.
- **Do not re-burn settled levers.** The tarpit valuation, the wave-ninety-four clustering, the
  round-five going-second scoring, and the standalone secondary fix are all screened and reverted;
  re-running them as new work is wasted effort.
- **Report the floor, do not force it.** If the representation stack washes, the residual near three
  point four five is the genuine one-Unit-per-model floor on the measured axis — report it; do not
  reach for a knob to move it.

---

## 6. Open questions for the user

1. **A/B the existing M4-alpha gate, or hold?** The clustering mechanism is already built and
   dormant behind `SWEG_MOVEPLAN`. Given the strong frozen-under prior (wave ninety-four regressed)
   and the standing pre-agreement that M4-alpha alone is expected to wash, do you want it A/B-tested
   in isolation after the stranding self-veto passes, or held until it can be screened as the stacked
   package the representation plan envisions?

2. **Sequencing the fragile-army representation fix.** The secondary and primary-mission candidates
   are blocked behind an Astra-Militarum / low-model-fragile representation fix that does not yet
   exist. Is closing the fragile under-pole the priority before any anti-durability secondary work,
   and if so should that be scoped as its own investigation?

3. **Floor declaration authority.** If the representation stack washes at eighty games, the gated
   metric near three point four five becomes the defensible one-Unit-per-model floor on the measured
   axis. Do you want a floor declared at that point, given the project has retracted one premature
   floor already, or do you want a further axis surveyed first?

4. **Cost of the seven missing primary missions.** Modelling the seven fallback missions faithfully
   is a large, citation-heavy build that pays out only after the fragile-army fix. Is that build worth
   scheduling now, or deferred until the representation root is closed?
