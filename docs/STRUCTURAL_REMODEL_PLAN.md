# Structural re-model plan — the closed-matrix representation gap (2026-06-26)

> ## RESOLVED 2026-06-28 — "the per-model re-model" is retired as a pending solution
>
> A fresh end-to-end review (prompted by the project owner: "I've authorised the
> parked per-model re-model several times and each time you conclude it's not a
> thing") traced the phrase to ground. It is **not one change and not a pending
> solution.** It decomposes into three pieces, and none is an open faithful fix:
>
> 1. **Squad-frame substrate (`SWEG_FILL_SQUADS`) — DONE / INERT.** The fill path
>    already builds coherent multi-model squads (audit 2026-06-26, this document's
>    first update block). Nothing to change.
> 2. **Clustering movement ("M4-alpha", `SWEG_MOVEPLAN`+`SWEG_COLLISION`) — BUILT,
>    NEVER VALIDLY SCREENED (gate bug found+fixed 2026-06-28), predicted to wash.**
>    The code exists and is dormant: `simulator.py:11016` `_make_way_target`
>    (capturing squad models fan out to their own slots in the marker's control
>    ring) plus `:11051` `_make_way` (post-move un-jam). **Critical bug found this
>    review:** all three clustering guards (`_make_way_blocker` :10947,
>    `_make_way_target` :11026, `_make_way` :11062) tested `environ.get(
>    "SWEG_COLLISION")` with **no default**, while collision is default-on
>    everywhere else via `environ.get("SWEG_COLLISION", "1") != "0"`. So unless a
>    screen set `SWEG_COLLISION=1` *explicitly*, the clustering never fired even
>    with `SWEG_MOVEPLAN=1` — a 2026-06-28 screen with `SWEG_MOVEPLAN=1` alone
>    produced **0 flips on all 22 factions** (byte-identical, inert). This means
>    every prior "`SWEG_MOVEPLAN` washes/inert" conclusion that relied on
>    collision's default was measuring a dead gate, not a real wash. Fixed (the
>    three guards now honour the default; byte-identical with `SWEG_MOVEPLAN` off).
>    The lever is therefore **genuinely untested**: the stranding diagnostic still
>    predicts a wash (it tightens over-pole and under-pole hordes alike and does
>    not change who survives the snapshot), and the older, different `SWEG_CLUSTER`
>    (wave 94) regressed 4.15→4.30 — but `SWEG_MOVEPLAN` itself has no valid screen.
>    **Action: screen `SWEG_MOVEPLAN=1 SWEG_COLLISION=1` (both explicit) once at
>    N=80 to confirm-and-close. If it washes, it is dead — stop citing it.**
> 3. **The "fragile-army representation fix" — NEVER DEFINED.** This is the piece
>    actually quoted as "the solution." It has no spec, no code, no concrete change
>    anywhere; other candidates are described as "blocked behind" it. There is no
>    thing there. It is dropped.
>
> **Why there is no hidden faithful fix in piece 3.** Real 10th edition counts the
> Objective Control of models **within 3" of the marker**, summed. A scattered
> squad genuinely only counts its within-3" models, so the simulator's contest is
> faithful and a spread horde really does under-control. The only faithful remedy
> is to get more models within 3" — which is piece 2 (clustering), which washes.
> Crediting the 3–6" models anyway is the explicitly forbidden counting-knob. So
> the durability-in-contest over-reward has **no faithful representation fix beyond
> clustering**, and clustering does not move it.
>
> **The actual open lead is NOT a re-model — but its lever has been lost.** The
> floor declared here on 2026-06-21 was retracted the same day; the retraction
> localised the real divergence as **going-first win rate ~66% vs a real ~50%**
> plus flat round-2-to-5 trajectory (no attrition decay). The lever the ledger
> credits with moving it — `SWEG_KITE_MOVE`, a proactive objective-aware kiting
> **move** (units retreat to open ground to deny the alpha-strike) that dropped
> going-first 74%→56% — was lost in the wave-252 re-anchor (`bc9159d`). The only
> surviving kite gate was `SWEG_KITE`, a shooting-picker **target-bias** (focus the
> exposed melee threat), screened 2026-06-28 at **+0.29 WORSE** (gated 3.26→3.55;
> Aeldari −3.7, Drukhari −3.1, Grey Knights −2.6) — it backfires like the old
> `SWEG_FOCUS_MELEE`. **`SWEG_KITE_MOVE` RECOVERED + re-applied 2026-06-28** from
> git `bcceccf` (the objective-aware version): `code/strategy.py` (4 functions +
> the call-site in `pick_move_intent`) plus `tests/test_kite_move.py`. Default-off,
> byte-identical off (gate-unset ≡ `=0`), 9/9 tests pass, fires correctly (changes
> 8/8 T'au-vs-World-Eaters battles). **Important caveat for the re-screen:** when
> last screened it moved going-first 74%→56% (fixing the diagnosed faithfulness
> gap) but regressed the calibration headline **+0.70 at N=80** — because that
> headline was a compensating-errors equilibrium the going-first over-reward was
> propping up. The Feel No Pain adoptions this session shifted that balance
> (baseline 3.45→3.26), so a re-screen against `sc18a` is genuinely informative;
> and the going-first signature itself (`scripts/diag_signatures`, N≥150) is the
> faithfulness check that matters more than a compensating-errors headline. The
> Astra Militarum sticky-objective fix (wave 255) moved the under-pole +1.87 —
> proof per-faction/AI-tempo fidelity still bites.
>
> **Screen results (paired vs the adopted baseline `sc18a`, gated MAE 3.26 — itself
> down from 3.45 thanks to the Feel No Pain corrections):**
> `SWEG_KITE` +0.29 worse (dead). `SWEG_MOVEPLAN` (clustering) **SCREENED 2026-06-29
> with the gate-bug fix — REGRESSES +0.61** (gated 3.26 → 3.87, ~500 flips/faction;
> Chaos Knights crater −6.39). Not a wash — an actual regression, confirming the
> frozen-under prediction. **The clustering piece is now empirically DEAD; the
> re-model is fully closed (squad-frame done, clustering regresses, fragile-army
> fix never defined).** `SWEG_KITE_MOVE` recovered; manual games show it hurts
> gunline under-poles standalone (T'au vs Death Guard −22.5) — it fixes the
> going-first *signature* but regresses the *win rate*, a Tier-3 stack component
> only, never a standalone adopt.
>
> **Net:** stop quoting "the per-model re-model." The real residual reduces to two
> already-built gates that each need one screen — `SWEG_MOVEPLAN` (clustering,
> confirm-and-close) and `SWEG_KITE` (kiting, the going-first lead) — neither of
> which is a re-model. The sections below are kept as the historical analysis that
> reached this verdict.

**Status:** design and scoping document only. No code, no simulator run, no
evaluation has been performed for this document. It collects the faithful
structural re-model candidates that survived an adversarial faithfulness check,
ranks them, names the diagnostic to run before any build, and records the
forbidden-zone guardrails the work must respect.

---

## UPDATE 2026-06-26 — Step 1 run: rank 1 (`SWEG_FILL_SQUADS`) is INERT, closed

The Step-1 squad-composition audit (`scripts/diag_squad_audit.py`, no simulator
run) was executed on the wave-260 sc17a frame. **The random-fill path already
builds coherent multi-model squads** — `code/army_builder.py:542` calls
`army.add_squad(chosen, size)` (one shared `squad_id` per filled squad), not the
stale `add_unit`-per-model loop the synthesis cited. Body/horde factions have the
bulk of their models in coherent squads (Tyranids 7 percent in lone squads, Orks
9, Chaos Daemons 12, Drukhari 8, World Eaters 8, max squad sizes 10-21); the
high-lone factions are the ones that should be (Imperial Knights 75 percent and
Chaos Knights 100 percent are single-model walkers; Grey Knights / Necrons /
Death Guard are leader-heavy elites). Horde mean models-in-lone-squads = 21
percent, below the 25 percent inert threshold. **The rank-1 substrate re-base was
already landed by the Squad-Activation Lever-1 work — no build.** This also
satisfies M4-alpha's prerequisite (coherent squads exist to cluster), so the
ordering question in section 6 is moot. Only rank 2 (M4-alpha) remains open,
gated behind the Step-2 stranding self-veto (which needs a purpose-built wave-93
within-three-inches-versus-within-six-inches instrument — the existing
`diag_boardcontrol` / `diag_reach` / `diag_contest_faction` measure related but
different quantities).

## UPDATE 2026-06-26 — Step 2 run: stranding is OPEN (self-veto did NOT fire), but the data reinforces the wash prior

A purpose-built wave-93 instrument (`scripts/diag_stranding.py`, gated
`SWEG_STRAND_INSTR` in `code/simulator.py` `_score_objectives`, read-only,
default-off byte-identical) measured per-faction summed Objective Control within
three inches versus within six inches of markers across three matchups (Imperial
Knights vs Chaos Daemons, Astra Militarum vs World Eaters, Necrons vs Adeptus
Custodes), thirty-six battles, on the sc17a frame. **The horde six-to-three
ratios are all well above the 1.3 self-veto threshold — Chaos Daemons 2.65, Astra
Militarum 2.99, Necrons 3.01 — so the stranding is still open and M4-alpha is not
a no-op.** Two findings nonetheless weaken the M4-alpha case:

1. **The hordes already deliver the MOST on-marker control in absolute terms.**
   Chaos Daemons puts 1085 control units within three inches, more than Imperial
   Knights (764) or any elite. M4-alpha would cluster the hordes tighter — helping
   the OVER-pole Chaos Daemons as much as the under-pole Astra Militarum — so it
   does not differentially lift the under-pole. This is the frozen-under risk made
   concrete: it helps whoever already has bodies near the marker.

2. **Clustering does not touch the durability differential.** Tightening both the
   over-pole hordes (Chaos Daemons, durable) and the under-pole hordes (Astra
   Militarum, fragile) onto markers leaves the root intact — Astra Militarum's
   clustered bodies still die before the survivor snapshot while Chaos Daemons'
   survive. The actual root is durability-in-contest, which M4-alpha does not
   address.

**Measurement caveat:** the instrument uses centre-distance, so big-base factions
(Imperial Knights 3.57, Adeptus Custodes 4.66) have inflated ratios — their model
centre can sit outside three inches while the base edge is within it (the scoring
path uses base-reach when collision is on). The horde ratios, which drive the
decision, use small bases and are reliable. The "elites strand more than hordes"
reading is a base-size artifact and should not be claimed.

**Net:** the self-veto did not fire, so per the plan M4-alpha is "live" — but the
diagnostic now predicts the stack will wash (it does not address the durability
root and helps over- and under-pole hordes alike). The decision is whether to
build the authorised stack and let the N=80 screen confirm (wash-and-stop → report
the representation floor) or to accept the diagnostic's prediction and call the
floor now. This is a user decision.

---

**Who should read this first.** Anyone about to open a calibration wave aimed at
the dominant Astra Militarum under-pole or the durable-elite / melee over-pole.
Read `docs/DECISION_LEDGER.md` (the long memory of what has been landed,
reverted, parked, and forbidden) and `docs/M4_REPRESENTATION_PLAN.md` (the
user's authorisation of the anti-Knight package) before acting on anything here.

This document is written in full prose with every term spelled out, per standing
rule 11 (no acronyms in documentation).

---

## 1. The structural gap, precisely stated

### 1.1 The single load-bearing mechanism (the closed-matrix root)

The simulator represents each physical model as one independent `Unit` object
(`code/army.py:704-741`; `add_unit` calls `add_squad(profile, 1)`, so the
default per-model fielding makes every model its own one-model squad — this has
been the default since wave 210). It then decides every objective by a
strictly-greater summed-Objective-Control contest evaluated on the
**end-of-round survivor positions**. The read side is `_assign_army_oc`
(`code/simulator.py:994-1068`), the strict-greater compare and the per-round
award are in `_score_objectives` (`code/simulator.py:928-1348`), and the only
per-model modulation of Objective Control is `_effective_oc`
(`code/simulator.py:1407-1459`), which applies only the damaged-bracket penalty
and the held-Order plus-one — there is no attrition term.

The contest mathematics itself is faithful 10th-edition Level of Control. The
artifact is **representational**, not arithmetic and not a scoring-timing bug.
Two poles fall out of the same mechanism:

- **Durable elites over-hold.** An Imperial Knight, a World Eaters
  character-led blob, or an Adeptus Custodes block parks a concentrated,
  near-indestructible block of Objective Control on the marker as one model. It
  survives to the end-of-round survivor snapshot and banks the full contest.

- **Fragile hordes under-hold.** An Astra Militarum, Chaos Daemons, or Necron
  warrior army has a larger total Objective Control, but that total is split
  across N independently-removable `Unit` instances that (a) **strand in the
  three-inch-to-six-inch band outside the scoring radius** — the wave-93 drill
  measured roughly twice as much near-marker Objective Control within six inches
  as within three inches, so a body army loses the on-marker contest even at its
  own objective — and (b) are killed **piecemeal** during the round, so models
  that physically held the marker while alive contribute zero to the
  end-of-round survivor snapshot.

A real coherent ten-model squad holds an objective **as a unit**: it stays in
unit coherency on the marker and contributes its whole surviving Objective
Control until broken. The simulator cannot translate codex-level board control
into held-marker board control the way reality does. The two poles are the same
mechanism seen from both ends.

### 1.2 The quantified game-shape evidence that it is structural, not a knob-gap

This is triply confirmed as structural, not a fidelity-of-abilities gap:

1. **Wave-260 ability over-credit removal washed.** Eight faithful ability
   over-credits were narrowed or removed (World Eaters Blood Tithe scope, Death
   Guard Typhus melee-only, Chaos Daemons invulnerable fix, and five more). The
   flip counts confirm the levers fire — 133 flipped games for World Eaters, 270
   for Death Guard — yet the gated mean absolute error moved only from 3.48 to
   3.45 (a wash). The over-credits are real but not load-bearing for the win
   rate (`docs/DECISION_LEDGER.md`, wave-260 landed line; anchor
   `data/_anchor_sc17a_n80_log.json`, gated 3.45).

2. **Five artificial-intelligence play-lever families all washed or
   backfired.** Mass-bodies, mass-tanks, gunline-hold, focus-fire, and screening
   were each built and measured; each washed or moved the wrong way, because you
   cannot out-position, out-hold, out-shoot, or out-screen a melee army the
   scoring over-rewards for winning contested markers
   (`docs/DECISION_LEDGER.md`, REVERTED section, the `SWEG_SCREEN_AI` /
   `SWEG_MASS_BODIES` / `SWEG_GUNLINE_HOLD` / `SWEG_FOCUS_MELEE` lines).

3. **The secondary over-count is a load-bearing compensating error** that props
   the same Astra Militarum under-pole — removing it would deepen the under-pole,
   so it cannot be cleaned in isolation.

The dominant residual on the current frame (gated 3.45) is Astra Militarum (win
rate roughly 26.8 percent, gated component 15.27) plus the over-pole half (World
Eaters plus 13.9, Emperor's Children plus 12.0, Chaos Daemons plus 10.5, Necrons
plus 9.4). Every faithful candidate below attacks the representation directly,
not the metric.

---

## 2. The faithful survivors, ranked

Two candidates survived the adversarial faithfulness check (each is a faithful
representation re-model, not a knob, and does not enter the forbidden zone). One
candidate was rejected as already shipped; it is recorded in section 5.

Ranking criterion: load-bearing-ness of the gap closed, multiplied by
faithfulness confidence, multiplied by buildability.

| Rank | Candidate | Gate | Gap it closes | Honest metric prior |
|---|---|---|---|---|
| 1 | Squad-frame re-base of the random-fill path | `SWEG_FILL_SQUADS` | The substrate beneath BOTH poles | Direction genuinely uncertain |
| 2 | Squad-as-cohesive board-control actor (M4-alpha) | `SWEG_M4` | The three-to-six-inch stranding half | Strong frozen-under wash prior |

The ordering is deliberate and reverses the synthesis's component-first ranking,
for one reason: the random-fill squad-frame re-base is the **substrate** beneath
the M4-alpha movement change. M4-alpha clusters the models of a squad onto a
marker; but on the current default fielding, a multi-model datasheet's models are
instantiated as N independently-drifting one-model squads (each its own
`squad_id`), so M4-alpha's per-squad slot assignment has nothing coherent to
cluster. Correcting the squad frame first is the prerequisite that makes the
movement change meaningful, and it is the explicitly greenlit next lever
(`docs/DECISION_LEDGER.md` OPEN LEVERS item 2). The user has separately
authorised the M4-alpha package, so both are in scope; the substrate goes first.

### 2.1 Rank 1 — Squad-frame re-base of the random-fill path (`SWEG_FILL_SQUADS`)

**The gap it closes.** The random-fill army builder instantiates each fill model
as its own one-model squad: `code/army_builder.py:122` calls `army.add_unit(chosen)`
once per pick, and `add_unit` (`code/army.py:704-706`) calls `add_squad(profile, 1)`,
so a multi-model datasheet's models scatter as N independently-drifting one-model
squads rather than one coherent N-model squad sharing a `squad_id`. This amplifies
the per-model dispersion that strands horde Objective Control and lets durable
elites win contests they would lose to a properly coherent surviving mass.

**Faithful basis.** This is a faithful representation of how armies are actually
fielded: a ten-model Infantry Squad is one unit of ten models in unit coherency,
not ten lone models. Converting the fill loop to `add_squad(chosen, size)` groups
the models under one `squad_id` so `_assign_army_oc` (`code/simulator.py:994-1068`,
which already iterates `army.squads().values()` and credits each squad's summed
Objective Control to its single best objective) sees a real squad. Why it is not a
knob: it changes no stat, no list-composition target, no scoring weight, and no
Objective Control value — it corrects a fielding-representation artifact to match
the real datasheet unit structure. The squad machinery already exists and is used
by the archetype seeds (`code/army_builder.py:205` and `:542`); this extends it to
the fill path. Wrong-way test: armies really are fielded as coherent multi-model
units regardless of which way the metric moves.

**Code seams.** `code/army_builder.py:122` (`add_unit(chosen)`) and the other
per-model fill sites; convert to `add_squad(chosen, size)` using the datasheet's
natural squad size. The squad machinery is `code/army.py:704-741` (`add_unit` /
`add_squad` / `_add_squad_per_model`). Downstream board-control consumers
(`_assign_army_oc`, `code/simulator.py:994-1068`, and the coherency loop) already
key on `squad_id`, and the movement artificial-intelligence squad-activation in
`code/strategy.py` keys on `squad_id`, so they pick up the change for free.

**Instrument-first diagnostic.** Run a squad-composition audit before any build:
count, per faction, how many fill models are currently lone one-model squads
versus coherent multi-model squads — a simple read of `army.squads()` sizes after
the build, with no simulator run. If most horde fill is already coherent (the
archetype seeds dominate and fill is marginal), the lever is inert and that
closes it cheaply. If horde armies are largely lone-model fill, the gap is
confirmed; then re-run the wave-93 within-three-inches-versus-within-six-inches
drill with the change applied in a probe to see whether coherent squads close the
stranding before committing.

**Gated, paired A/B plan.** Gate `SWEG_FILL_SQUADS` default-off; the off path
must be byte-identical (the per-model `add_unit` loop verbatim). Prove the off
path with a fixed-seed game-log comparison that reproduces the sc17a anchor.
**Critical implementation guardrail:** prove the off-path byte-identity by a
fixed-seed army-build comparison BEFORE any game-log comparison — diff the
post-build `army.squads()` membership and the random-number-generator draw count
between the off arm and the verbatim legacy loop, because a silent perturbation of
the army-build random-number stream would change every downstream game and
invalidate the sc17a anchor pairing. Then paired N=80 versus the sc17a anchor
(`data/_anchor_sc17a_n80_log.json`, gated 3.45), same-directory common-random-number,
with `SWEG_FIRSTPLAYER_STABLE=1` on both arms. Bidirectional watch: Astra
Militarum / Chaos Daemons / Necrons must lift, not crater; Imperial Knights /
Chaos Knights / Adeptus Custodes must not re-spike. As the substrate beneath the
movement fix, a follow-on ablation pairs it with M4-alpha to test whether the
clustering lands once the squad frame is corrected.

**Risk.** Medium-to-high, but the risk is correctness, not faithfulness. The
off-path byte-identity is delicate: the per-model loadout path
(`_add_squad_per_model`) and the army-build random-number order both run through
this code, so the off path must reproduce the exact unit sequence and random
draws. The frozen-under risk is shared with M4-alpha (better coherence may help
whoever has the better army). If it lands it forces a Stage-2 re-derivation of
`data/calibrated_points.json` and the equilibrium points. Keep the pull request
small per rule 14: substrate change plus re-verification only; any secondary fix
is a separate pull request.

### 2.2 Rank 2 — Squad-as-cohesive board-control actor, M4-alpha (`SWEG_M4`)

**The gap it closes.** The three-inch-to-six-inch stranding half of the
load-bearing mechanism. A body army's near-marker Objective Control is roughly
twice as large within six inches as within three inches (wave-93 drill), so half
its near-marker models contribute zero Objective Control and it loses the
on-marker contest to a single parked Knight even at its own objective.

**Faithful basis.** A faithful representation of the printed 10th-edition rule
that a unit holds an objective as a coherent body (unit coherency: models stay
within two inches of two other models of their unit; a squad on an objective
clusters on it). The build is genuine movement: when a model's intent is
objective-seeking (CAPTURE or STEAL) and it is within roughly eight inches of the
marker, override its `target_pos` with a deterministic clustered slot at most
about two-and-a-half inches from the marker centre (concentric rings, distinct
per squad member sorted by unique identifier), and let the existing move logic
close the distance. Why it is not a knob: it invents no Objective Control,
converts no Objective Control to victory points at any tuned rate, branches on no
faction and no model count, and applies no Knight penalty — a one-model squad (a
Knight) gets the centre slot, an exact no-op. It corrects a genuine simulator
artifact (independent instances stranding in the three-to-six-inch ring because
the move logic treats arrival within three inches as done) toward the real rule.
It passes the wrong-way test, and it is the explicitly user-authorised build
(`docs/M4_REPRESENTATION_PLAN.md` section 7, choice A; full spec in
`docs/M4A_BUILD_PLAN.md`).

**Verified code-seam facts.** The artifact is real in the current code:
`_do_move` (`code/simulator.py:10799`) sets `range_threshold = 3.0` for CAPTURE /
STEAL intent (`code/simulator.py:10928`), so a model that arrives at the edge of,
or just outside, the three-inch band treats itself as arrived and never tightens
onto the marker. Across a squad, half the near-marker bodies strand in the
three-to-six-inch ring contributing zero Objective Control. The contest read side
`_assign_army_oc` (`code/simulator.py:994-1068`) genuinely scores only models
within the control radius, so the stranding genuinely loses the contest. The hook
is a new private helper `_m4_cluster_target(attacker, target_pos)` placed in
`_do_move` immediately after the move intent is picked and before the
Advance / move-toward block. **Note the M4A build plan cites line numbers
(`simulator.py:7508-7570`) that have shifted since wave 127 — verify the current
line numbers against `_do_move` at `code/simulator.py:10799` and the
`range_threshold` at `code/simulator.py:10928` before building.**

**Instrument-first diagnostic.** Run the per-matchup Imperial-Knights /
Chaos-Daemons on-marker within-three-inches versus within-six-inches Objective
Control drill (the wave-93 drill; `diag_boardcontrol` / `diag_reach` /
`diag_contest_faction` in `docs/ANALYSIS_TOOLBOX.md`) on the current wave-260
sc17a frame, to re-confirm the roughly-twice-as-much stranding ratio still holds.
It predates many waves of movement change — `SWEG_MASS`,
`SWEG_DISPLACE_FALLBACK`, and collision are all now default-on and may already
have closed it. If the three-to-six-inch ratio is now near one, the stranding is
already fixed and M4-alpha is a no-op; that result alone closes the question with
no build. Also render the standing visual board-state diagnostic
(`docs/ANALYSIS_TOOLBOX.md` section 1) on a Knight-versus-horde game to see the
stranding before building.

**Gated, paired A/B plan.** Gate `SWEG_M4` default-off; off path byte-identical
(helper returns `target_pos` unchanged — prove with a fixed-seed game-log match
reproducing the sc17a anchor exactly). Tests in `tests/test_m4_cluster.py`: a
five-model squad contesting a marker ends all five within three inches when on
versus spread when off; a one-model unit targets the centre (no-op); off returns
`target_pos` unchanged. Paired N=80 versus the sc17a anchor, same-directory
common-random-number, `SWEG_FIRSTPLAYER_STABLE=1` on both arms. Then the decisive
full-stack run (M4-alpha plus the tarpit-charge valuation `SWEG_TARPIT` plus
`SWEG_FOCUS`) on versus baseline off, with per-component ablations. Over-shooter
watch (Drukhari, Leagues of Votann, Adeptus Custodes, Chaos Knights) for the
frozen-under signature; bidirectional report (both the Astra Militarum under-pole
and the Imperial Knights over-pole movement).

**Risk.** High metric risk. The frozen-under wash prior is strong: every
single-lever positional attempt to date washed or regressed via the same
mechanism (wave-72 value-targeting, wave-79 focus-fire, wave-81 contest/deny, and
most directly wave-94 `SWEG_CLUSTER` which regressed from 4.15 to 4.30). Better
positioning helps whoever has the better army. The pre-agreed value is in the
**stack**, not M4-alpha alone. Architectural risk: if it lands it forces the same
Stage-2 re-derivation. The forbidden trap one step away is the A2
Objective-Control coherency-footprint counting shortcut (crediting
three-to-six-inch models as on-marker) — the build must remain genuine movement,
never a counting credit.

---

## 3. Recommended first step — diagnostic, before any build

**Do not build anything first.** Run two read-only, simulator-cheap diagnostics
that confirm the mechanism gap is still open on the current wave-260 sc17a frame,
because three default-on movement changes since the gap was last measured
(`SWEG_MASS`, `SWEG_DISPLACE_FALLBACK`, collision/pathfinding) may already have
closed it.

**Step 1 (no simulator run): the squad-composition audit for rank 1.** Count,
per faction, how many fill models are currently lone one-model squads versus
coherent multi-model squads — a direct read of `army.squads()` sizes after the
build. This is the cheapest possible measurement and it is self-closing: if
horde fill is already largely coherent because the archetype seeds dominate and
fill is marginal, declare `SWEG_FILL_SQUADS` inert and close it as a
representation-limit finding rather than searching for a way to make it move the
metric.

**Step 2 (one diagnostic run): the wave-93 stranding-ratio drill for rank 2.**
Run the Imperial-Knights / Chaos-Daemons within-three-inches versus
within-six-inches Objective Control drill (`diag_boardcontrol` / `diag_reach` /
`diag_contest_faction`) on the sc17a frame, and render the visual board-state
diagnostic on a Knight-versus-horde game. This is a **binding self-veto**: if the
re-measured three-to-six-inch versus within-three-inch ratio is below roughly
1.3 times, declare the stranding already closed by `SWEG_MASS` /
`SWEG_DISPLACE_FALLBACK` / collision, mark M4-alpha a no-op, and close the
question with zero build. Do not build "to be sure".

Only if step 1 shows horde fill is genuinely lone-model and step 2 shows the
stranding ratio is still roughly two times should any build begin — and the
substrate (rank 1) goes first.

---

## 4. Forbidden-zone guardrails this work must respect

These are user-ruled out of bounds (`docs/DECISION_LEDGER.md`, FORBIDDEN
section). Every candidate above is checked against them and clears them; the
rails are restated here because the near-certain wash means a build could drift
toward a forbidden rescue.

1. **No re-fitting stats, overrides, or lists to force win rates.** The win-rate
   gap is sim-fidelity, not stats; re-fitting poisons Stage 2.

2. **No gating a faithful mechanic off to protect the metric.** Fidelity-first; a
   rising headline is expected and authorised. The default-off gates above are
   for the isolation A/B only — the user-authorised stack decides the final
   default. Gating a representation FIX off by default for A/B safety is the
   opposite of the forbidden move.

3. **No declaring the simulator done by re-fitting to the target.**

4. **No make-way or horde-artificial-intelligence nerf to free Knights through
   walls.** The walls are a faithful horde strategy.

5. **The forbidden A2 shortcut specifically:** never credit three-to-six-inch
   models as on-marker via a coherency-footprint counting shortcut, never apply
   an Objective-Control-to-victory-point conversion factor, never branch per
   faction, never change `SEED_FRACTION` or the archetype lists to chase the
   number. M4-alpha must remain genuine movement.

6. **Bound the wash-and-stop criterion to the STACK, not the component.** If the
   full stack (M4-alpha plus `SWEG_TARPIT` plus `SWEG_FOCUS`) washes at N=80,
   REPORT the representation floor and STOP. The wave-93 "report the floor"
   instruction applies. Do not force it, do not reach for A2, do not re-fit.

7. **Require the bidirectional over-shooter watch even on a positive read.** On
   any positive Astra Militarum result, the over-shooter watch (Drukhari, Leagues
   of Votann, Adeptus Custodes, Chaos Knights) must still be reported, so a
   frozen-under result disguised as success (clustering merely helping whoever
   already holds the marker) is caught.

---

## 5. Rejected candidate (recorded so it is not re-attempted)

**Per-Command-phase primary scoring as the round-start contested-marker snapshot
(`SWEG_CMDSCORE` faithful timing) — REJECTED as already shipped.** The proposal
was to score primary at each player's own Command phase (turn start, before that
turn's combat removes the holding bodies), giving partial credit to hordes that
held a marker then died. The underlying rule is faithful and citable, and the
intent is a real printed-timing dynamic. But the candidate is refuted by the
current code state, which makes the build moot, not forbidden:

- `SWEG_CMDSCORE` is already **default-ON**, not default-off:
  `code/simulator.py:439` reads `os.environ.get("SWEG_CMDSCORE", "1") != "0"`,
  with the wave-210 comment "Faithful AND improved the metric (5.72 to 5.44,
  N=80)". It is the production default and is already baked into the sc17a anchor.

- The proposed build — read the true round-start board state before the active
  player's combat — already exists: `_run_round_vanilla_turns`
  (`code/simulator.py:10151`) fires `self._score_objectives(only_for=active.name)`
  at the top of the per-player turn loop (`code/simulator.py:10171`), before that
  player's movement/shooting/fight phases, crediting only the active player's own
  primary on the pre-combat board.

- The candidate's premise that this was "measured net-neutral (wave 116), gated
  default-off" is stale; it predates the wave-210 default-on flip.

The faithful timing the candidate asks for is the production default. There is no
build and no non-degenerate A/B. **Salvage:** keep only the read-only instrument
as a diagnostic, not a lever — extend `diag_displace_instr` (`SWEG_DISPLACE_INSTR`)
to record, per faction, victory points held at the active player's Command-phase
snapshot versus the end-of-round survivor snapshot. Its purpose is to confirm the
live default already credits held-but-died hordes (and to quantify any residual
leak through the Objective-Control contest or the per-round and total primary
caps), not to motivate a re-model. If that instrument shows hordes are already
dead by their own Command phase, the result points back to the per-model
representation wall — the rank 1 and rank 2 candidates above. This timing axis is
CLOSED.

---

## 6. Open questions that need a user decision

1. **Stage-2 re-derivation acceptance.** The user pre-accepted a Stage-2
   re-derivation of `data/calibrated_points.json` and the equilibrium points IF
   the anti-Knight package lands (`docs/M4_REPRESENTATION_PLAN.md` section 4).
   Does that pre-acceptance extend to the rank 1 squad-frame re-base
   (`SWEG_FILL_SQUADS`) landing on its own, since it changes board-control
   behaviour the same way and would equally move the ground Stage 2 stands on?
   Confirm before the rank 1 build, because it is the substrate and may land
   before M4-alpha is even built.

2. **Build order within the authorised package.** The user authorised the
   M4-alpha stack (M4-alpha plus `SWEG_TARPIT` plus `SWEG_FOCUS`). This document
   recommends building the `SWEG_FILL_SQUADS` substrate FIRST, before any stack
   component, because M4-alpha has nothing coherent to cluster until the fill
   path produces real squads. Confirm this re-ordering is acceptable (it does not
   change the authorised mechanics, only their sequence).

3. **The inert / floor outcomes.** If the step-1 audit shows fill is already
   coherent (rank 1 inert) and/or the step-2 drill shows the stranding ratio is
   already near one (rank 2 no-op), the finding is that the representation gap was
   already closed by the default-on movement changes, and the remaining residual
   is a representation floor. Does the user want that reported as the Stage-1
   floor and the Imperial-Knights / Astra-Militarum axis closed, per the wave-93
   instruction — or held open pending some other avenue?
