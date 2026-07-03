# Squad-based re-architecture — implementation plan (2026-06-03)

**Status:** PLAN ONLY (no code). User is "not opposed" and asked for the plan; the BUILD is a separate
explicit go. This is the most-faithful fix for the one-model-per-Unit **representation floor** (the Knight
over-hold / broad-army under-hold and the secondary over/under-generation all bound by it).

## Framing — it is an OVERLAY, not a rewrite

10e is **hybrid**, and the sim is already correctly per-model for what 10e resolves per-model. KEEP per-model:
**movement** (each model moves individually within coherency), **wound allocation**, **positions**
(range / line-of-sight / Objective-Control-within-3" / wholly-within / blast), and **split-fire** (a unit's
models/weapons may legally target different enemy units). The bug is the missing **unit-level orchestration**.
Make UNIT-level: **activation** (once per squad), mid-game **coherency** enforcement, **once-per-unit** effect
budgets, charging/fighting as a unit, leader/aura/battle-shock, destruction, cohesive objective holding.

A partial squad layer already exists and is the Stage-0 scaffolding: `squad_id` grouping (`Army.squads()`,
`Army.add_squad`), per-squad charge/advance rolls (waves 76/77), damage spillover (wave 65), squad-gated
abilities (Acts of Faith / Strands of Fate), deployment + OC coherency, per-squad battleshock. The rebuild
COMPLETES this layer. Coherency is the missing piece mid-game (models drift = the scatter behind the floor).

## The `Squad` actor — lightweight, no two-source-of-truth

Do NOT add a heavyweight Squad class that owns models (positions/wounds MUST stay on the per-model `Unit`).
Instead: (a) the grouping view `Army.squads()` (exists), (b) a lightweight `SquadView` read-wrapper
(`squad_id`, alive `members`, `profile`, `centroid()`/`anchor()`, `total_oc`, `start_count`, role — delegates
to existing helpers, holds NO mutable state), (c) per-round mutable squad state in `Battle`-owned dicts keyed
by `squad_id` (exactly like `_squad_charge_roll`): `_squad_move_intent`, `_squad_shoot_plan`,
`_squad_charge_target`, `_squad_activated_this_phase`, a generalized once-per-unit budget.

## Stages (each ENV-gated, OFF path byte-identical, zero extra RNG draws on OFF)

- **Stage C — generalize the once-per-unit budget** (gate `SWEG_ONCEUNIT` or fold into squad-act). Pure infra:
  replace the four bespoke aof/fate squad-gate sets with one `unit_budget_available/mark_used(effect, squad_id,
  profile_name)`, identical keying (so OFF byte-identical). Ships FIRST (unblocks the activation gate). LOW risk.
- **Stage A — per-squad activation** (gate `SWEG_SQUADACT`). Re-route `_run_round_vanilla_turns` (and the
  alternating path) so each squad activates once: compute the squad decision once, execute per-model. Safest
  shape: on the first model of a squad this phase, compute+cache the squad decision in the Battle dicts;
  subsequent models read the cache. Emit one `UnitActivated` per squad. By itself a no-behavior-change scaffold
  (decisions cached, execution unchanged) — the behavior lands when B/D/E read the cached decision. LOW-MED risk
  (cross-squad activation ORDERING shifts RNG sequencing — validate it's noise).
- **Stage B — mid-game coherency enforcement** (gate `SWEG_COHERE`). After a squad moves, `_enforce_squad_
  coherency` nudges stragglers (>2" from nearest squadmate) toward the centroid within their remaining move
  (deterministic, no RNG). MED risk — first intentional behavior change; tighter clustering raises effective OC.
- **Stage D — unit-orchestrated shooting WITH split-fire** (gate `SWEG_SQUADSHOOT`). `_plan_squad_fire` assigns
  targets across the squad's models: anti-armour concentrates on the focus target (reuse `_nominate_focus_target`
  / `_is_antiarmour_weapon` / `_ranged_expected_wounds`), anti-infantry SPLITS across chaff. `_do_shoot` keeps
  the per-model legal-candidate filter (range/LoS/blast/engagement stay per-model) and fires the assigned target
  if legal, else falls back to the existing per-model pick — preserving split-fire legality while orchestrating
  at the unit level. MED-HIGH risk (largest shooting behavior change; plan computed before any model fires;
  re-fallback when a target dies mid-squad).
- **Stage E — cohesive objective holding** (reuse `SWEG_COHERE`, depends on B). The HOLD decision becomes
  squad-level (the whole squad commits to one marker, not models drifting to nearby cover); promote the existing
  `_m4_cluster_intent` from gated experiment to the squad-hold default. `_score_objectives`/`_assign_army_oc`
  are ALREADY squad-correct — Stage E just feeds them better-clustered positions. LOW-MED risk.

## The AI refactor (the hard part — but CONCENTRATED, not diffuse)

`code/strategy.py` makes per-model decisions; the deciding granularity becomes per-squad while EXECUTION stays
per-model. Only TWO decision entry points convert (~540 lines):
- `pick_move_intent` (~390 lines, `:2063`) → `pick_squad_move_intent(squad_view, ...) → (target_pos, intent)`.
  Most transfers cleanly (squad profile + anchor/centroid). Genuine squad logic only in the Fall-Back,
  objective-hold, and melee-engage branches. The card-pursuit/dedication/sacrificial-chaff overrides are ALREADY
  unit-stamped pre-loop — just move the stamp to squad granularity.
- `pick_charge_target` (~150 lines, `:1474`) → `pick_squad_charge_target(squad_view, enemy)`. Distance gate
  measures from the nearest member; the whole profile-keyed bonus stack transfers unchanged. The `_squad_charge_
  roll` already makes the ROLL per-squad — this makes the TARGET per-squad.
- The `_do_shoot` / `_do_fight` inline pickers become `_plan_squad_fire` (Stage D) / a squad-biased melee pick.

**~3600 lines of strategy.py are REUSED AS-IS** — all the scoring/bonus helpers (`_durability`,
`_kill_potential_wounds`, `_melee_target_score`, the per-faction tarpit/charge/target bonuses) are pure
`(profile, profile)` functions called BY the squad deciders. `pick_army_plan` is already army-level — the
precedent that proves squad-level deciding fits. **Implement the squad deciders as NEW wrapper functions
(never mutate the per-model ones) → OFF byte-identical by construction**; the wrapper can call the per-model
function on a representative for branches that need no squad logic.

## Migration order

C (infra, ships first) → A (scaffold, ~no-op) → then two independent behavioral landings: **(B+E+squad-move-AI)**
together (coherency + cohesive hold + per-squad move intent are one unit), and **(D)** separately
(split-fire shoot planner). Charge-target lands with the existing per-squad charge roll. Each gate isolates its
win-rate/points delta in the eval harness.

## Stage-2 tie-in

`code/balancer.py` is the ONLY simulation→price coupling (`measure_win_rate` → `Battle(...).run()`;
`find_balanced_points` binary-searches to a target win rate). Any landed squad stage changes `Battle.run()`
outcomes, so the empirical prices move and the catalog re-prices. No balancer code changes needed — it just
re-runs. Because every stage is env-gated, run the balancer gate-OFF (current prices) vs gate-ON to QUANTIFY
each stage's pricing impact before flipping the default. `code/equilibrium.py` is analytic (reads `UnitProfile`
stats + LP, never builds `Battle`) → NOT directly coupled.

## Honest caveats

1. **The M4-α inseparability stands.** Even faithful coherency-driven cohesion helps ALL body armies hold —
   it fixes the Knight over-hold AND inflates the body over-shooters. The rebuild does the GRANULARITY
   faithfully but does NOT by itself resolve why over-shooters over-perform (a separate question). Judge it in
   the combined faithful picture (alongside the abilities + detachment dives), not on the aggregate alone.
2. **It re-prices Stage 2** — accept this if it lands.
3. **It is large** — but concentrated (the AI refactor is ~540 lines + ~100 lines of simulator glue, not a
   diffuse rewrite). Build it stage-by-stage, env-gated, A/B each, keep-if-faithful.
