# Balanced objective-contest AI lever (over-pole over-hold) — PLAN

**Status:** plan-first, watchdog-greenlit (2026-06-05) with the wave-95 **Stage-E
over-flood rail front-and-centre**. No build until reviewed. Stage 1 (simulator
fidelity / AI). Env-gated, default-OFF byte-identical.

## Goal (plain language)

The wave-192 OC-flip instrument (`scripts/diag_ocflip.py`) showed the Imperial /
Chaos Knights **over-HOLD** objectives because of a **general AI-not-contesting
gap**: across 650 obj-rounds where a big Knight/Titanic controls a marker, the
opponent had enough reachable Objective Control within one Normal Move to flip
**228 (35%)** of them but never committed the bodies. The Knight scores primary VP
round after round on a marker the opponent could take **without killing it** — just
by moving enough Objective Control on.

This lever makes the AI **faithfully** close that gap: bias idle/affordable bodies
to flip a **winnable** enemy-held marker, **bracket-aware** (a chipped Knight's
effective OC is 5, not 10, via the wave-191 generalization, so it is easier to
out-Control), **without** abandoning its own scoring markers and **without**
over-flooding.

## The Stage-E rail (must not repeat the rejected wave-95 Stage E)

Wave-95 **Stage E** (cluster-intent / mass bodies onto markers as a squad-hold
default) was **REJECTED as unfaithful OVER-FLOODING** — it crushed Imperial Knights
by flooding markers with cheap-OC hordes, a sledgehammer that abandoned the
flooding army's own game (see `project-fidelity-first-rebuild-authorized`). This
lever is the **balanced** version. Three hard guards, all faithful to how real
players trade markers:

1. **WINNABLE only.** Contest an enemy marker only when committing this unit would
   make our side's Objective Control there **exceed the enemy's EFFECTIVE
   (bracket-aware) OC**. If we cannot win it even by committing, the body is wasted
   — do not send it (no unwinnable flooding).
2. **AFFORDABLE only.** Do not pull a unit that is the **marginal holder** of a
   friendly scoring marker (leaving would flip our own marker to the enemy). Real
   play trades markers; it does not strip an enemy marker by suiciding its own VP.
3. **JUST-ENOUGH.** Commit only enough Objective Control to exceed the enemy's
   effective OC plus a small margin; once a marker is winnably contested by already-
   committed bodies, additional units do **not** pile on (de-prioritise a marker we
   are already going to win, so the rest of the army plays its own game).

## Current state (what exists, the integration point)

`code/strategy.py:pick_move_intent` already:
- scores every objective (~2278-2310): a_oc>b_oc → CAPTURE value 1.0; **b_oc>a_oc →
  STEAL value 3.5** (already the highest base); tie → CAPTURE 2.5; ×`round_weight`;
  distance-weighted `score = value / (1 + d/12)`.
- `SWEG_MASS` (~2357, default-ON, wave 95) sends an **idle, out-of-firing-range**
  unit holding no objective to the best CAPTURE/STEAL objective (so it does not pull
  in-range shooters off their lanes — the anti-gunline-chaos guard).
- a hold-check (~2233) keeps a unit on a friendly marker if leaving would flip it.

So the **STEAL intent already exists** but is a **flat 3.5** — it does not scale
with WINNABILITY or with the value of denying a durable over-holder, and distance-
weighting + the out-of-range gate leave winnable enemy markers (the 228) un-
contested. The lever **refines the existing STEAL scoring**, it does not add a new
movement system.

**Build detail to confirm first:** whether `_our_oc` / `_their_oc` (the per-objective
OC dicts the scorer reads) are **bracket-aware** (summed via `Battle._effective_oc`)
or raw OC. If raw, the winnability check must call the effective-OC path explicitly
so a damaged Knight reads as OC 5. (The instrument already uses `_effective_oc`.)

## Design (env-gated `SWEG_CONTEST`, default-OFF byte-identical)

In `pick_move_intent`'s objective loop, when the gate is set and `intent ==
_STEAL_INTENT` (enemy-held marker):
- compute `enemy_eff_oc` = the enemy's **effective** (bracket-aware) summed OC on
  that marker, and `our_potential` = our current OC there **+ this unit's OC**.
- **WINNABLE:** if `our_potential > enemy_eff_oc`, boost the STEAL value, scaled by
  the marker's round-weighted scoring value (denying a Knight that scores every
  round is worth more than a generic marker) — this is the faithful "go take the
  marker the durable holder is sitting on" bias. If `our_potential <= enemy_eff_oc`
  (cannot win even by committing this body), **drop** the STEAL value (do not chase
  an unwinnable contest).
- **JUST-ENOUGH:** if our side is **already** winnably contesting that marker (our
  committed-this-round OC already exceeds `enemy_eff_oc`), do not boost — let the
  unit play its own game (prevents the pile-on flood).

The **AFFORDABLE** guard reuses/strengthens the existing hold-check: a unit that is
the marginal holder of a friendly scoring marker stays (never traded for a contest).

Keep the SWEG_MASS out-of-range gate (idle bodies only; do not pull shooters off
lanes). The contest draws from the same idle-body population, just redirected toward
**winnable enemy markers** rather than the nearest own/neutral one.

## A/B and the over-flood TELL (the decider)

- OFF (`SWEG_CONTEST` unset): N=80 must read **gated 5.71** (byte-identical).
- ON: N=80, report **Imperial Knights over-HOLD falling** = IK gated + (crucially)
  IK **primary VP** down (the over-hold is a primary-VP phenomenon).
- **THE STAGE-E TELL:** also report the **contesting factions' own win rates AND
  their own primary VP**. If IK falls because the contesting armies BALANCE-trade
  (their own WR/VP hold) → faithful, keep. If IK falls because cheap-OC swarms
  over-flood + **abandon their own objectives** (the contesting factions' WR / primary
  VP **crater**) → it is **Stage-E redux → REJECT** (re-gate OFF, report honestly).
- Honour the upper-bound caveat: do **not** tune toward the 35% ceiling — many of
  those 228 bodies are genuinely needed at home or pinned.

## Citation

The lever is an AI movement heuristic that uses the already-cited core OC-contest
rules (`simulator.objective_control_strictly_greater`,
`simulator.damaged_bracket`); it does **not** implement a new 10e rule flag, so no
new `rule_citations` key is required. Run `python -m scripts.audit_rules` to confirm
it stays green. If the audit wants a key, add `simulator.objective_contest_ai`
(scope `phase-gated`) describing the heuristic.

## Verification

`python -m scripts.audit_rules` green; `python -m pytest -q` green;
`PYTHONIOENCODING=utf-8 python run.py --cli` exits 0; OFF N=80 == 5.71; ON N=80 with
the over-flood tell (IK primary VP down + contesting factions' WR/primary VP NOT
cratering). Keep-if-faithful; reject-if-Stage-E-redux.

## Critical files

- `code/strategy.py` (`pick_move_intent` objective-scoring + the SWEG_MASS gate)
- `code/simulator.py` (`_effective_oc` — the bracket-aware OC the winnability check reads)
- `scripts/diag_ocflip.py` (the instrument — re-run ON to confirm the flippable% drops)
