# Displacement substrate — design plan (avenue 2 completion)

**Status: DESIGN DRAFT, user-gated. No build until the user greenlights the avenue-2 investment.**
This is prep #2 (the design) following the displacement quantification (prep #1). It exists so the
user can assess *scope* before committing, and so the build is ready to launch on greenlight.

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
- **Stage 1 — Fall-Back-only-when-wasted AI.** (Trigger re-specified per the user's 2026-06-10 steer.) A unit
  falls back ONLY when it is being *wasted* — all three conditions must hold: (1) **no control consequence** —
  its presence changes no marker's outcome at the current or next scoring check (it cannot hold, cannot flip the
  marker to contested, and denies no enemy score by standing); (2) **staying costs material for nothing** — it is
  likely to be destroyed or stays locked in engagement with its shooting forfeited while contributing nothing
  positionally; (3) **falling back buys something real** — the preserved unit has an actual use, net of the Fall
  Back move's own cost (no shooting or charging that turn, barring FLY or an equivalent ability). A unit that can
  still hold a marker, or whose presence prevents the marker being flipped, does NOT fall back even if it is
  losing the fight — dying on the marker to deny a scoring tick is the faithful competitive behaviour (the
  tarpit). Handles the under-pole (genuinely wasted defenders cede markers the durable winner then takes) without
  clearing contesting bodies off the Knight's marker — the over-pole fix belongs to Stage 2, not to Stage 1
  fall-backs. Gate `SWEG_DISPLACE_FALLBACK`. Extends `SWEG_KITE`.
- **Stage 2 — Charge-to-contest the durable holder.** AI directs affordable bodies to charge a marker held by a
  concentrated durable unit (the Knight), putting models in engagement range to contest/tarpit its Objective
  Control. Faithful (real hordes swarm Knights). Reduces the Imperial Knights over-hold. Gate
  `SWEG_DISPLACE_SWARM`. Rail: charge only when the swarm can actually contest (enough Objective Control in
  range), not a suicidal feed.
- **Stage 3 — Consolidate-onto-marker after winning.** A unit that wins a fight makes its faithful consolidation
  move onto the contested marker, cementing control. Reuses `_ring_slots` for the winning squad only. Gate
  `SWEG_DISPLACE_CONSOLIDATE`. Rail: winners only — this is the faithful slice of the parked make-way nerf, not
  the general blocker-move.
- **Stage 4 — (if needed) winner fan-onto-ring.** Promote the winning squad to fill the marker's control ring
  (the faithful `_make_way_target` slice), so a victorious squad holds the whole marker rather than single-filing.
  Gate `SWEG_DISPLACE_FAN`. Only if Stages 1–3 leave a measurable coherency-on-marker shortfall.

## 6. Rails (hard constraints)

- **Faithful only.** Every stage models a real 10e behaviour (Fall Back, charge/engagement contest,
  consolidation). NO durability/output/Objective-Control *knob*, NO horde-nerf (the parked general make-way is
  the trap), NO metric-tuning. If a stage tempts a knob, STOP and flag.
- **Instrument-first.** Stage 0 sizes the prize before any behavioural build.
- **Per-increment A/B + keep-if-faithful.** Each stage runs both arms fresh (or reuses the anchor only when
  byte-identical) at N=80 vs the 5.99 anchor; keep if faithful even if the metric is flat, but report direction.
  Re-anchor every ~3–4 waves per the cadence rule.
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
