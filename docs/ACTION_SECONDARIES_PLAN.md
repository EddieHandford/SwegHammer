# Implementation plan — action-economy secondaries (wave 74 build)

**Status:** Cleanse vertical slice + Cull-fix **DONE (wave 74)** — gated MAE 5.89 → 5.35,
validated by env-gated N=40 A/B and landed. Remaining (Sabotage, Recover Assets, AI
forward-projection, alternating-mode wiring) are the wave-75+ follow-ups. Companion to
`docs/SECONDARY_SCORING_ANALYSIS.md`, which established the verified rationale.

## Goal

Add the missing **action-economy** secondary family so the secondary layer
counterbalances the kill-secondary asymmetry instead of amplifying it. The faithful
real-10e mechanism that taxes low-model durable campers and rewards board-control /
horde under-shooters is the **action-vs-fight tradeoff**: a unit performing a Pariah
Nexus action gives up shooting and charging that turn. A 9-model Knight army cannot
spare a unit for an action; a horde / MSU army can. Implementing it is the real rule
pool (not a nerf) and applies even-handedly to every faction.

This is a **fidelity** change: it must be kept on its faithfulness, not its direction
on a residual (`STAGE1_AUTONOMOUS_GOAL.md`).

## Step 0 — verify the card list (BLOCKER, do first)

Wahapedia is unreachable from this environment (`project-wahapedia-dns`). Before
coding, confirm against the GW Pariah Nexus mission pack or Goonhammer the exact
mechanics + VP of the action-based Tactical secondaries. Candidates (verify each):

- **Cleanse** — a unit performs an action on an objective marker it controls; score
  VP per objective cleansed (action started end of Movement, resolves end of turn).
- **Sabotage** — action on a terrain feature, typically in enemy territory.
- **Recover Assets** — action on objectives in no man's land / enemy territory.
- **Establish Locus** — action near the centre.

Implement the verified text only. If a candidate is NOT actually action-gated, drop
it. Do NOT invent VP numbers or conditions (CLAUDE.md §10).

## Step 1 — the action-state mechanic (`code/simulator.py`, `code/units.py`)

Minimal, faithful model of a 10e action:

- Add `Unit.action_this_round: Optional[str] = None` (the action name, or None).
  Reset to None at the top of every round alongside `moved_this_round` /
  `fell_back_this_round`.
- A unit that is performing an action is **locked out of shooting and charging** that
  round: gate at the top of `_do_shoot` and `_do_fight` (`if attacker.action_this_round:
  return`), mirroring the existing Fall Back / Advance lockouts. It may still have moved
  onto the objective in the Movement phase (10e actions are declared end of Movement).
- The action **completes** (and scores) only if, at end-of-round, the unit is still
  alive and still satisfies the action's condition (e.g. still controls the objective
  for Cleanse). A unit destroyed or pushed off mid-round scores nothing — this is what
  makes actions risky on a contested board and rewards the army that can spare a body.

## Step 2 — scoring (`code/secondaries.py`)

- Add `score_action_delta(own_units, map_, own_is_army_a, round_num, chosen)` returning
  the action-secondary VP for the side this round, gated by `chosen_secondaries` and a
  per-round cap (mirroring the existing Engage/BEL structure). For Cleanse: count
  controlled objectives that had a committed, surviving action-unit on them.
- Wire it into `Battle._score_secondaries` exactly like `score_position_delta`:
  add to BOTH `_a_vp`/`_b_vp` (live total) and `_a_secondary_vp`/`_b_secondary_vp`
  (tracker), consistent with lines 925/954. **Do NOT** route through the unread
  tracker alone (that is the Finding-0 trap).
- Add the action secondaries to `ALL_SECONDARY_KEYS` / `TACTICAL_SECONDARY_KEYS` and
  the LC-2 tactical-draw rotation so they don't all score every round.

## Step 3 — AI action selection (`code/strategy.py`)

The crux — the tradeoff must be faithful, not a free bonus:

- In the move/intent layer, a unit chooses to perform an action ONLY when it is
  **surplus to the firefight**: it is on (or can reach) an objective its army
  controls, it is NOT the army's high-value firepower / a unit a critical enemy
  target depends on, and the army has the relevant action secondary in
  `chosen_secondaries`. Prefer cheap/expendable / already-safe units.
- Consequence (the intended faithful asymmetry): a low-model durable army (every
  Knight is needed to shoot) almost never has a surplus unit, so it rarely scores
  action secondaries; a horde / MSU army routinely has spare bodies on objectives, so
  it does. No per-faction gating — the asymmetry falls out of unit count + roles.
- Keep it bounded: cap the number of units an army commits to actions per round (a
  unit doing an action is not fighting; over-committing should cost the firefight, and
  the AI should feel that cost rather than dodge it).

## Step 4 — picker + caps (`code/secondaries.py`)

- Extend `pick_secondaries` so an army with surplus board-control capacity (objective
  holders / many cheap units) can bring an action Tactical, while a low-model army
  defaults away from it (it cannot satisfy it). Keep the heuristic simple and
  deterministic (reproducible N=40).
- Add per-round caps tuned to real Pariah Nexus magnitudes (verify in Step 0); keep
  total secondary VP ~40/game vs ~75 primary, per the existing calibrated ratio.

## Step 5 — citations

Each action secondary needs a `data/rule_citations.d/*.json` entry
(`simulator.secondary_cleanse`, etc.) with verbatim Pariah Nexus text. The audit is
enforcing.

## Step 6 — validation / A/B

- Env-gate the whole feature (`SWEG_ACTIONS=1`) so it is a clean A/B at N=40 against
  the wave-72 baseline (gated 5.89).
- Expectation (faithful, to be confirmed not engineered): board-control / horde
  under-shooters (Chaos Daemons, Astra, Tyranids, AdMech, GSC, Necrons) rise as they
  gain a scoring path that does not require killing durable units; durable low-model
  campers (Imperial Knights, Custodes) ease down as they cannot spare units for
  actions. Decide by fidelity: keep if it is the faithful reading even if a faction
  moves the "wrong" way; hunt the compensating error rather than reverting a correct
  change.
- Full pytest sweep + `run.py --cli` + citation audit. Then remove the env-gate and
  land if validated.

## Bundled fidelity fix (do alongside, flagged in the analysis)

`secondaries._is_horde_unit` reads `starting_strength`/`squad_size`/`count` (all
`None`); it should read `max_models` (Termagants 20, Boyz 20, …). Currently Cull the
Horde scores 0 for everyone — a dead mechanic. Fix it as part of this wave (it is a
correctness fix), but note it feeds the kill-asymmetry on its own, so it must land
together with the action secondaries, not before them.

## Risk assessment

- **Highest risk: AI mis-allocation.** If units do actions when they are needed to
  fight, the army loses the firefight and the feature over-corrects. Mitigation:
  strict "surplus only" gate + per-round action cap + env-gated A/B; start with
  **Cleanse only**, measure, then add Sabotage/Recover Assets.
- **Double-count / primary interaction:** Cleanse rewards holding an objective the
  army already scores primary on — make sure it is a distinct secondary award, not a
  primary multiplier.
- **Over-correction of hordes:** if hordes score too much, the per-round cap is the
  dial (faithful magnitude, not a faction knob).
- **Scope creep:** this is multi-file (units, simulator, secondaries, strategy,
  citations). Land Cleanse end-to-end first as a vertical slice; defer the other
  actions to follow-up waves.

## Sequencing recommendation

Wave 74: Step 0 verify → Cleanse vertical slice (Steps 1-3,5) + the `_is_horde_unit`
fix → env-gated N=40 A/B → land if faithful. Waves 75+: add Sabotage / Recover Assets
and the AI-plays-toward-secondaries refinements.
