# M4 — the one-Unit-per-model board-control representation: plan + the user fork (wave 123)

**Date:** 2026-06-02. **Status:** plan only, no code. **Hard-gated** by the watchdog and the user:
the build is too architectural and too coupled to Stage 2 to start autonomously. This document is the
"plan-first" half; it ends with the decision that must go to the user before any build wave.

This supersedes the framing of `docs/RESIDUAL_CONVERGENCE_2026-06-02.md` (its "(iii) un-interleaving is
the lever" conclusion was corrected in wave 116 — see §2) and builds on `docs/POSITIONAL_REMODEL_PLAN.md`
(wave 93, the original two-candidate movement/geometry plan).

---

## 1. What M4 is, and what is already done

**The residual, in one line.** Across all fourteen out-of-band factions the win is decided on primary
board control: durable / elite armies (Imperial Knights +27, Thousand Sons, Votann +13.8, Sororitas +11)
OVER-hold the objective markers; mobile-melee and out-massed armies (Chaos Daemons, Necrons, Chaos Space
Marines, World Eaters) UNDER-hold them. Tabling never differentiates (0 tablings in hundreds of games);
secondary is always a 40-cap wash. **Primary-VP delta predicts every faction's win rate one-to-one.**
(Full table: `RESIDUAL_CONVERGENCE_2026-06-02.md`.)

**The mechanism (verified, waves 84 / 93 / 109–115).** A Knight is ONE durable model parking a
concentrated Objective Control of ~10 on a marker that never dies. A body army has a huge TOTAL Objective
Control (Astra ~95, Tyranids ~185, Daemons ~111) but gets almost NONE of it within the 3" scoring radius
of a marker — and the bodies it does get there are individual `Unit` instances that the Knight removes
piecemeal. The summed-Objective-Control contest itself is FAITHFUL (wave 84: credited `a_oc`/`b_oc` ==
the raw per-model Objective Control within 3"). So this is **not** an Objective-Control-math bug and
**not** a scoring-timing bug — it is the one-Unit-per-model REPRESENTATION: a multi-model squad cannot
translate its codex-level board control into held-marker board control the way it does in real 10e.

**Everything faithful that could be built around this has been built — and it is exhausted:**

| Lever | What it was | Outcome |
|---|---|---|
| **Candidate B — `SWEG_MASS`** | move AI: idle, out-of-firing-range bodies mass onto holdable markers | **LANDED wave 95, default-ON.** Gated 4.15 → 3.81; Daemons −22.7 → −16.4; IK +27 → +25.5. The faithful movement half of M4. **Already in the current baseline.** |
| Candidate A — `SWEG_CLUSTER` | geometry: cluster on-objective models into the 3" band | Built wave 94, **REGRESSED 4.15 → 4.30, reverted** — helped only units already holding markers (frozen-under); also an unfaithful counting shortcut. |
| A2 — OC coherency-footprint counting | credit 3"–6"-band models as on-marker | **Forbidden** (user, knob-in-disguise); never committed. |
| M1 — primary 50-VP total cap | real Chapter-Approved rule | Net-neutral (metric-inert), kept as fidelity. |
| M2 — real 2-card Tactical secondary deck (`SWEG_TAC_DECK`) | replace ~9–11 secondary sources with a real 2-card hand | N=40 −0.28 **washed to −0.07 at N=80**; gated default-OFF. |
| M3 — per-Command-phase scoring (`SWEG_CMDSCORE`) | score primary at each Command phase, not once after combat | Net-neutral. |
| Pursuit — `SWEG_TAC_PURSUE` | move spare chaff to achieve held Tactical cards | Ineffective (achieve rates unchanged); −0.02 at N=80; decoupled default-OFF (wave 122). |

**Current headline:** N=80 gated **3.69** (with `SWEG_MASS` on, all experimental gates off); N=40 gated
4.41. Down from a campaign start of ~9.3 and ~5.98 this session. Target: below the per-faction noise floor
(noise-gated MAE → 0). Still ~3.7 points of real per-faction error remain — **not converged.**

## 2. Why the mission/scoring layer turned out neutral (the wave-116 correction)

The wave 109–115 convergence concluded the lever was "(iii) un-interleaving to real per-player turns +
per-Command-phase scoring," user-gated. **Wave 116 corrected this:** the evaluation harness ALREADY runs
IGOUGO (`RulesConfig.vanilla_10e()` → `_run_round_vanilla_turns`; verified empirically — zero alternating
calls). So "un-interleaving" was a misnomer, and the only real content of (iii) — scoring primary at each
Command phase rather than once per round — was built (M3) and came back **net-neutral**. Combined with the
50-cap (M1) and the secondary-deck (M2) both net-neutral, the conclusion sharpens: **the residual is not in
WHEN or HOW primary/secondary is scored. It is in WHO is standing on the marker when it is scored** — i.e.
the representation, the only remaining root.

## 3. The architectural M4 — the deep change (what a build would be)

The faithful movement and scoring fixes are spent. The remaining gap is structural: a body army's board
control is held by N fragile, independently-removable `Unit` instances, so it (a) gets out-contested at the
marker it reaches because the within-3" subset is below a Knight's OC-10, and (b) bleeds off the marker
model-by-model under fire. In real 10e a 10-model squad holds an objective AS A UNIT — it stays in
coherency on the marker and contributes its whole surviving Objective Control until broken.

**Option M4-α — Squad-as-cohesive board-control actor (the principled change).** Represent a multi-model
squad, for board-control purposes only, as one coherent actor that holds/contests a marker with the summed
Objective Control of its living models, and whose models stay massed in the 3" band while it holds (rather
than each model independently drifting / being the spread the geometry fix tried to paper over). Combat
stays per-model (each model still rolls its own attacks and dies independently — no change to the firefight
or to `_alloc_target`); only the *board-control footprint* of a holding squad becomes coherent. The
`squad_id` substrate from the per-model loadout work already groups the instances; this would add a
squad-level board-control aggregation at the scoring/positioning layer.

- **Why it is faithful, not a knob:** it does not invent Objective Control, does not convert OC→VP at a
  tuned rate, does not branch on faction or model count, and does not penalise Knights. A 1-model Knight is
  a 1-model squad — unaffected. It corrects a genuine sim artifact (independent instances scattering a
  squad's board control out of the scoring radius) toward the real rule (a unit holds an objective as a
  coherent body). The wrong-way test passes: if it moved the metric the wrong way it would still be the
  more faithful representation.
- **The risk (why it is hard-gated):** the geometry candidate (A, `SWEG_CLUSTER`) already tried the
  "recover the 3"–6" band" idea via clustering and REGRESSED — because pulling models tighter helped
  whoever already held the marker (the over-shooters), the frozen-under signature. M4-α must be designed to
  help the NON-reachers (the under-shooters that mass via Candidate B) without re-inflating the
  over-shooters — and there is real risk it lands in the same frozen-under trap and washes. The honest
  prior, from every positional attempt (w72/79/81/94), is **likely wash**.

**Option M4-β — none.** It is genuinely possible there is no further faithful lever: the contest math is
faithful, the timing is faithful, the secondary economy is faithful, the movement-massing is landed, and
the geometry shortcut is unfaithful. In that case the remaining ~3.7-point residual is a hard one-Unit-per-
model representation FLOOR, and the wave-93 plan's own instruction applies: **REPORT it as the finding and
STOP chasing the IK/Daemons axis — do not force it, do not reach for a knob.**

## 4. The Stage-2 tie-in (why this is not a quiet Stage-1 tweak)

Stage 2 prices every unit FROM the simulator (`code/balancer.py` Monte-Carlo bisection and
`code/equilibrium.py` log-least-squares both read sim outcomes). Board-control representation feeds unit
value: if M4-α makes a 10-model squad hold objectives materially better, the *relative price* of bodies vs
durable single models shifts, and the Stage-2 outputs (`calibrated_points.json`,
`equilibrium_points*.json`) must be re-derived against the changed sim. This is why M4 cannot be slipped in
as a gated Stage-1 experiment and forgotten — it is the largest single sim-behaviour change still on the
table, and it moves the ground Stage 2 stands on. It needs the user's explicit decision, not the loop's.

## 5. The decision for the user (this is the fork)

The loop has driven the headline from ~5.98 to gated 3.69 (N=80) this session and has now exhaustively
built and measured every faithful mission/scoring/movement lever; the residual is localised to one
architectural axis. The choice is genuinely the user's:

- **(A) Authorise the M4-α build** — the squad-as-cohesive board-control representation — as a multi-wave,
  env-gated, plan-measured effort, accepting (i) a real likelihood it washes (frozen-under), and (ii) that
  if it lands it forces a Stage-2 re-derivation. Faithful by construction; the only remaining lever with
  any headroom on the dominant residual.
- **(B) Declare the representation floor** — accept gated ~3.69 (N=80) as the faithful Stage-1 floor under
  the one-Unit-per-model representation, report the convergence as the finding (the wave-93-authorised
  outcome), and stop chasing the IK/Daemons axis. Stage 1 is then as faithful as this representation
  allows; remaining work is faithful hygiene only.

**Recommendation (orchestrator):** surface both to the user. M4-α is the only path with headroom and is
faithful, so it is worth ONE carefully-designed, env-gated attempt with the explicit pre-agreement that a
wash is reported and abandoned (not forced) — but it must be the user's call because of the Stage-2 tie-in
and the strong frozen-under prior. Do not begin coding M4 until the user picks (A) or (B).

## 6. Hard-rails self-check (must hold for any M4-α build wave)

1. Faithful representation of a real rule (a unit holds an objective as a coherent body), verified against
   a genuine sim artifact (the independent-instance spread), not invented.
2. Even-handed: no per-faction branch, no per-model-count weighting; a 1-model unit is affected only as the
   coherence rule affects any 1-model unit (i.e. not at all).
3. No Objective-Control→victory-point conversion factor, no body-army boost, no Knight penalty. Wrong-way
   test: still correct if it moved the metric the wrong way.
4. Env-gated, A/B at N=40 then N=80, per-matchup Imperial-Knights / Chaos-Daemons on-marker drill, with a
   watch on the over-shooters (Drukhari, Votann, Custodes) for the frozen-under signature.
5. If it washes or regresses, REPORT it as the representation floor and STOP — do not force it, do not reach
   for A2 or any knob.
