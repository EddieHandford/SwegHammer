# Displacement substrate — design plan (avenue 2 completion)

**Status: GREENLIT 2026-06-10.** The user authorised the build contingent on a final-pass review
against the core rules and available online strategy advice; both reviews completed 2026-06-10 and
their amendments are folded in below (Stage 1 FLY correction, Stage 2 stacked-Objective-Control
rail, Stage 3 cleared-position precision, Battle-shock and scoring-timing clarifications, ranked
future candidates). Build order: Stage 0 first, then one stage per wave.

## 1. The problem this solves (the dominant remaining residual)

On the clean standing frame (gated mean absolute error **5.99**, anchor `data/_anchor_wave228_n80_log.json`),
the biggest residuals — Astra Militarum −17.5 (under), Imperial Knights +17.2 (over), Adepta Sororitas −15.3
(under), Genestealer Cults +14.8 (over) — were all diagnosed (waves 229 + the Imperial Knights diagnostic) to
**one structural gap: displacement**. Real 10th edition displaces out-fought armies off contested objective
markers — the loser dies, is forced to Fall Back, or cannot hold under the threat of being charged. The
simulator instead resolves marker control by raw summed Objective Control, so a surviving out-fought unit
*stays* on the marker. Two consequences:

- **Under-pole** (Astra Militarum / Sororitas durable vehicles): they win their local fights but the sim does
  not let them *take* the marker the loser still nominally holds → they under-score.
- **Over-pole** (Imperial Knights): a Knight parks concentrated Objective Control on a marker and the body army
  that should swarm/displace it cannot → the Knight over-holds.

The cheap faithful-*rule* levers are harvested (Chaos Space Marines datasheet abilities were the last clean one;
the Astra Militarum over-fragility hypothesis was *refuted* — cover/spillover/bracket are all sim-correct;
Sororitas Miracle Dice is faithfully modelled). The remaining bulk of the 5.99 is this single axis.

*(Frame update 2026-06-10: after the wave-232/233 merges and canonical re-prices the standing frame is gated
mean absolute error **5.74**, anchor `data/_anchor_wave233_n80_log.json`. The displacement poles persist —
Imperial Knights +15.9 over; Astra Militarum −16.5, Chaos Space Marines −17.0, Adepta Sororitas −16.5 under —
so the diagnosis above stands on the new frame.)*

## 2. Why a scoring proxy cannot do it (the prep-#1 finding)

The displacement gap is **bidirectional**: under-pole wants *durable out-fighters to HOLD* markers they lose on
raw Objective Control; over-pole wants *cheap bodies to DISPLACE* a concentrated holder. A "combat-winner"
scoring proxy helps the under-pole but **entrenches** the Knight (it wins fights → holds more); a
"swarm/numbers" proxy does the reverse. The prep-#1 upper-bound (credit the contested marker to the local
combat-winner) confirmed the axis directionally — Imperial Knights −7.27 and Sororitas +4.10 both moved toward
real — but cratered Chaos Knights, because no single scoring shortcut captures both directions. **The ceiling is
therefore build-measured, not proxy-measurable.** The build must model the *real consequence of fights*, which
handles both poles for free.

## 3. Design principle

**Model the real board consequence of combat and pressure, not a scoring rule.** After fights resolve each
round, a unit that was out-fought at a contested marker should suffer the real-10e outcome — be destroyed, Fall
Back to preserve itself, or be unable to hold while an enemy is in engagement range and winning. The winner
consolidates onto and holds the marker. Both poles then emerge from one faithful mechanic: durable winners take
markers (under-pole up); swarms that out-fight or tarpit a Knight strip its sole control (over-pole down).

## 4. What already exists (build on, don't rebuild)

- `SWEG_COLLISION` / `SWEG_PATHFIND` / `SWEG_OCCGRID` — **default-ON** (wave 211): no-overlap collision,
  coarse-A* for big bases, occupant grid. The faithful positional substrate. **Verified on/maxed in production.**
- `SWEG_KITE` — Fall-Back-and-reshoot vs melee threats (a partial Fall-Back AI to extend).
- `_make_way` / `_make_way_target` / `_ring_slots` (`SWEG_MOVEPLAN`) — the in-move distinct-slot fan-onto-marker.
  Currently **OFF as the forbidden horde-nerf** (it was a general make-way that moved any blocker). The faithful
  *winner-only consolidation* below reuses `_ring_slots` but must NOT resurrect the general nerf.
- `_score_objectives` — the per-marker Objective Control contest (the read side; unchanged by this plan).

## 5. Staged plan (gated, instrument-first, A/B-per-increment vs the 5.99 anchor)

Each stage is one faithful mechanic, behind its own env gate (default-OFF → byte-identical), landed only if its
A/B is faithful-and-not-cratering. Render per the standing visual diagnostic on every behavioural stage.

- **Stage 0 — FIGHT-OUTCOME instrument (no behaviour change).** At each contested marker, record who out-fought
  locally (unsaved wounds dealt) and whether the out-fought loser *survived-and-held* (today's unfaithful
  outcome). Sum the displacement-addressable victory points per game. This is the ceiling estimate the scoring
  proxy could not give — it reads real fights, not a shortcut. Gate `SWEG_DISPLACE_INSTR`. Deliverable: a
  per-faction "displacement-addressable VP" number to size the prize honestly.

  **Stage 0 RESULT (2026-06-11, 40 games — 4 matchups both orders × seeds 3–7, 2000 points): GO.**
  Per-faction mean victory points per game (under-pole = out-fought loser survived-and-held; over-pole =
  uncontested hold the opponent never contested; tarpit = out-fought loser held while *engaged*, the faithful
  outcome that is NOT addressable):

  | Faction | under-pole | over-pole | tarpit |
  |---|---|---|---|
  | Adeptus Astartes | 6.50 | 25.00 | 9.50 |
  | Adeptus Mechanicus | 6.00 | 10.50 | 13.00 |
  | Astra Militarum | 4.00 | 12.50 | 3.50 |
  | Chaos Space Marines | 6.00 | 23.50 | 7.00 |
  | Imperial Knights (20 games) | 6.00 | 24.25 | 0.75 |
  | Orks | 9.00 | 11.50 | 13.50 |
  | Tyranids | 13.00 | 9.50 | 13.50 |

  Verdict: the addressable pool is large — 10 to 25 primary victory points per game per side against a mean
  primary haul of roughly 29.6 — and the **over-pole dominates**. The Imperial Knights signature (24.25
  uncontested-hold against only 0.75 tarpit) directly confirms the hypothesis: the Knight parks on a marker and
  the body army never plays the contest game back, so Stage 2 (swarm charge-to-contest) carries most of the
  over-pole prize. Astra Militarum's own under-pole is small (4.00), so its calibration gain rides on the
  matchup differentials — both banked poles point toward-target. Raw per-game records:
  `data/wf_wave235_displace_instr_stage0.txt`. Stage 1 is next, one stage per wave.
- **Stage 1 — Fall-Back-only-when-wasted AI.** (Trigger re-specified per the user's 2026-06-10 steer.) A unit
  falls back ONLY when it is being *wasted* — all three conditions must hold: (1) **no control consequence** —
  its presence changes no marker's outcome at the current or next scoring check (it cannot hold, cannot flip the
  marker to contested, and denies no enemy score by standing); (2) **staying costs material for nothing** — it is
  likely to be destroyed or stays locked in engagement with its shooting forfeited while contributing nothing
  positionally; (3) **falling back buys something real** — the preserved unit has an actual use, net of the Fall
  Back move's own cost. That cost is universal: a unit that Falls Back cannot shoot or declare a charge that
  turn, with **no FLY exemption** (corrected per the 2026-06-10 rules review — FLY exempts only the Desperate
  Escape tests for moving over enemy models; the lockout is bypassed only by specific faction stratagems, which
  this abstract cost model ignores). The cost model must also price Desperate Escape itself: falling back
  through enemy models, or while Battle-shocked, rolls one six-sided die per affected model and destroys one
  model per roll of 1–2 (TITANIC and FLY models exempt from the tests). Two clarifications from the review: a
  Battle-shocked unit (Objective Control 0 until the start of its next Command phase) trivially passes condition
  (1) — it can hold nothing and denies nothing by standing; and scoring checks happen at the end of each
  player's own Command phase from battle round two, so "current or next scoring check" means both players'
  Command-phase ticks. A unit that can still hold a marker, or whose presence prevents the marker being flipped,
  does NOT fall back even if it is losing the fight — dying on the marker to deny a scoring tick is the faithful
  competitive behaviour (the tarpit). Engaged models keep their full Objective Control (verified: Battle-shock
  is the only mechanic that zeroes it), so an engaged contester on a marker is still contesting. Handles the under-pole (genuinely wasted defenders cede markers the durable winner then takes) without
  clearing contesting bodies off the Knight's marker — the over-pole fix belongs to Stage 2, not to Stage 1
  fall-backs. Gate `SWEG_DISPLACE_FALLBACK`. Extends `SWEG_KITE`.

  **Stage 1 BUILT (2026-06-11, gated default-OFF, awaiting the orchestrator's A/B).** The
  Fall-Back-only-when-wasted decision sits at the existing eager Fall Back branch in
  `code.strategy.pick_move_intent` (the SHOOTY/HEAVY in-engagement disengage). When
  `SWEG_DISPLACE_FALLBACK=1`, that branch now fires only when all three conditions hold, evaluated
  by three new helpers in `code/strategy.py`: `_displace_no_control_consequence` (condition 1 —
  the unit is the swing keeping the enemy off no marker; a Battle-shocked unit at Objective Control
  0 trivially passes), `_displace_staying_costs_for_nothing` (condition 2 — likely destroyed in
  place, or a pinned gun platform whose shooting is forfeited for nothing positional), and
  `_displace_fall_back_buys_something` (condition 3 — a clear destination exists AND the Desperate
  Escape cost does not make the move net-negative; TITANIC/FLY skip the Desperate Escape arm). The
  OFF path is the legacy two-line branch verbatim — byte-identical. New tests:
  `tests/test_displace_fallback_wave236.py` (gate-OFF byte-identical; each condition blocks
  individually; the tarpit rail — a losing unit on a marker stays; Desperate Escape priced into
  condition 3). No new rule citation — this is an AI-piloting heuristic that PRICES the already-cited
  `simulator.fall_back` lockout and `simulator.desperate_escape` test, it does not add a rule.
- **Stage 2 — Charge-to-contest the durable holder.** AI directs affordable bodies to charge a marker held by a
  concentrated durable unit (the Knight), putting models in engagement range to contest/tarpit its Objective
  Control. Faithful (real hordes swarm Knights). Reduces the Imperial Knights over-hold. Gate
  `SWEG_DISPLACE_SWARM`. Rail (amended per the 2026-06-10 strategy review): charge only when the swarm can
  actually contest — and evaluate the contest against the **full stacked Objective Control of every defending
  model within marker range** (a Knight is routinely supported by Armigers; two Armigers add Objective Control
  16 to the cluster), never the lone holder. Not a suicidal feed. Two rule interactions verified by the rules
  review work in the swarm's favour: engaged models keep their full Objective Control, and once the bodies are
  locked in combat the defending VEHICLE or MONSTER cannot use Fire Overwatch against them (the Rules Commentary
  bars Locked-in-Combat units from out-of-phase shooting), so arrival is safer than raw threat arithmetic
  suggests — the simulator's existing overwatch implementation already respects this.
- **Stage 3 — Consolidate-onto-marker after winning.** A unit that wins a fight makes its faithful consolidation
  move onto the contested marker, cementing control. Reuses `_ring_slots` for the winning squad only. Gate
  `SWEG_DISPLACE_CONSOLIDATE`. Rail: winners only — this is the faithful slice of the parked make-way nerf, not
  the general blocker-move. Precision (per the 2026-06-10 rules review): the consolidation rule's
  objective-marker fallback fires only when the unit CANNOT end within Engagement Range of any enemy — in
  practice, when the fight cleared the position. If enemies survive, each model must instead end closer to the
  nearest enemy model (which may still carry it onto the marker). The implementation must branch on cleared
  versus partially-cleared positions, not consolidate-to-marker unconditionally.
- **Stage 4 — (if needed) winner fan-onto-ring.** Promote the winning squad to fill the marker's control ring
  (the faithful `_make_way_target` slice), so a victorious squad holds the whole marker rather than single-filing.
  Gate `SWEG_DISPLACE_FAN`. Only if Stages 1–3 leave a measurable coherency-on-marker shortfall.

### Future candidates (ranked by the 2026-06-10 strategy review; not yet staged, queue after Stage 4)

1. **Proactive trade — contest the opponent's marker with cheap bodies.** Competitive play deliberately spends a
   cheap unit to flip an enemy-held marker to contested at the scoring check, even when the unit dies for it.
   Distinct from Stage 2 (which targets the durable-holder over-pole); this one helps the under-pole score.
2. **Re-task to claim EMPTY markers.** New finding from the 2026-06-10 visual diagnostic: late-game markers sit
   at Objective Control 0/0 — uncontested free victory points — and no unit is ever re-tasked to walk onto them.
   The inverse of the Stage 1 wasted rule: a unit with nothing better to do should take free ground.
3. **Deep-strike screening near markers** (denial placement; possibly cheaper to build than Stage 4).
4. **Heroic Intervention to deny the winner's consolidation** (a Stage 3 extension).
5. **Staging-then-committing** (hold units out of threat range, commit on the scoring turn — long-term AI work).
6. **Wrap-to-lock** (surround a faller-back so it cannot legally leave — low priority).

## 6. Rails (hard constraints)

- **Faithful only.** Every stage models a real 10e behaviour (Fall Back, charge/engagement contest,
  consolidation). NO durability/output/Objective-Control *knob*, NO horde-nerf (the parked general make-way is
  the trap), NO metric-tuning. If a stage tempts a knob, STOP and flag.
- **Instrument-first.** Stage 0 sizes the prize before any behavioural build.
- **Per-increment A/B + keep-if-faithful.** Each stage runs both arms fresh (or reuses the anchor only when
  byte-identical) at N=80 vs the standing anchor (currently `data/_anchor_wave233_n80_log.json`, gated mean
  absolute error 5.74); keep if faithful even if the metric is flat, but report direction. Re-anchor every ~3–4
  waves per the cadence rule.
- **Bidirectional check.** Each behavioural stage reports both the under-pole (Astra Militarum / Sororitas) and
  the over-pole (Imperial Knights / Genestealer) movement — the mechanic should help both, not trade one for the
  other.

## 7. Effort & risk

Multi-wave (≈ one stage per wave, 5 waves). Lower novelty risk than it looks: collision/pathfind/occupant-grid
already exist; Stages 1–4 are AI-movement increments on that substrate, each small and gated. The main risk is
the make-way-nerf trap (Stage 3/4) — mitigated by scoping to *winners only*. The honest unknown is the size of
the gain (Stage 0 measures it before the behavioural waves commit).

See also: `[[project-physical-board-control-avenue2]]`, `[[project-oc-contest-faithful]]`,
`[[project-positional-remodel-movement-not-oc-chain]]` in auto-memory.
