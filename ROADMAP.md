# Development Roadmap

SwegHammer is organised around **four goals**. Each goal owns a strand of work
that runs end-to-end through the simulator, the points solvers, and the
calibration harness. Progress is measured against a single headline metric —
the mean absolute error (MAE) of the per-faction win rate vs the May 2026
Warp Friends tournament aggregate — currently **MAE 5.11 pts** (target
≤ 2.0 pts).

This file is the high-level status board. For the human-facing checklist with
ownership tags and math, see [`PROJECT.tex`](PROJECT.tex). For Claude
operating rules, see [`CLAUDE.md`](CLAUDE.md).

## Status Overview

| Goal | Status | Description |
|------|--------|-------------|
| Goal A | 🔲 Active | Sim matches real tournament data (faction-specific mechanics) |
| Goal B | 🔲 Active | Equal-quality simulation per faction (stratagems / leaders / enhancements) |
| Goal C | 🔲 Active | Generate balanced SwegHammer points (two-track: balancer + equilibrium) |
| Goal D | 🔲 Planned | Price non-damaging abilities (collapsed into Equilibrium Phase 4) |

Headline calibration metric:

- **MAE 5.11 pts** vs Warp Friends May 2026 (10-faction matchup matrix).
- Trajectory: range bounces as Goal A fills in — each new faction-specific
  mechanic perturbs the matrix until the next mechanic lands.
- Measured by `python -m scripts.evaluate_vs_meta`.

---

## Goal A — Sim matches real tournament data 🔲

**Intent.** Drive the per-faction MAE down by implementing the
faction-specific mechanics that distinguish Necrons from Tyranids from Orks
in real play. The premise: a faction-blind simulator can never reproduce a
tournament meta where Necrons hit 53% and Aeldari hit 44%.

**Target.** MAE ≤ 2.0 pts vs Warp Friends aggregate. Currently 5.11 pts.

**Key references.**

- `scripts/evaluate_vs_meta.py` — the matchup-matrix harness; runs N
  battles per (faction_a, faction_b) pair and reports per-faction sim WR
  next to the tournament target.
- `code/detachments.py` — army-wide passive flags; 10 modifier fields,
  registered detachments per faction.
- `code/leaders.py` — character-attached aura abilities.
- `code/simulator.py` — gate where faction-specific rules fire
  (Mob Rule, WAAAGH!, Reanimation Protocols, Shadow in the Warp, etc.).

**What's done.**

- 18 canonical detachments registered with Wahapedia-cited rule effects.
- Faction-specific gates: Reanimation Protocols (Necrons), Shadow in the
  Warp (Tyranids), WAAAGH! once-per-battle window + Mob Rule (Orks).
- Faction-blind core combat: hit / wound (S vs T) / save (AP) / cover /
  invuln / FNP / a dozen weapon keywords (Lethal Hits, Sustained Hits,
  Twin-Linked, Devastating Wounds, Anti-X, Melta, Rapid Fire, etc.).
- Stochastic damage; Battleshock from Round 2; objective scoring; CP economy.

**What's next.**

- Audit which factions still wash out — Aeldari and Death Guard are the
  current outliers. Their detachments parse but the simulator-side gates
  are thin (most flags compose into `Unit.attack()` only when led).
- Wire the remaining 8-of-10 Detachment modifier flags into the per-attack
  resolution path (`reroll_hit_ones`, `reroll_wound_ones`, `plus_one_to_hit`,
  `plus_one_to_wound`, `plus_one_attack`, `plus_one_save`, `extra_invuln`,
  `ld_bonus`). Most parse and store today but produce no in-game effect.
- Re-run `evaluate_vs_meta` after each mechanic lands; aim for monotone
  MAE decrease.

---

## Goal B — Equal-quality simulation per faction 🔲

**Intent.** Bring every faction to the same depth of in-game representation
so cross-faction matchups aren't biased by which factions had their abilities
modelled first. The two big knobs are stratagems (CP-priced effects) and
leader auras (CHARACTER attached to bodyguard unit).

**Key references.**

- `code/stratagems.py` — `Stratagem` dataclass + universal core stratagems +
  detachment-specific stratagems wired onto `Detachment.stratagems`.
- `code/leaders.py` — `LeaderAbility` registry; `_REGISTRY` keyed per
  CHARACTER unit; aura wiring composes into the attached squad's
  `Unit.attack()`.
- `data/rule_citations.d/` — every Stratagem, Detachment, Leader needs a
  matching Wahapedia citation entry (CLAUDE.md §10).
- `scripts/audit_rules.py` — enforces the citation requirement; currently
  95/95 active rules cited.

**What's done.**

- Universal Core Stratagems (4): Command Re-Roll, Counter-Offensive,
  Tank Shock, Heroic Intervention.
- Three detachment stratagem sets: Cult of Magic (Thousand Sons), Plague
  Company (Death Guard), Battle Host (Aeldari).
- 32 leader abilities registered with Wahapedia citations.
- Citation audit enforces coverage on every commit that touches a rule.

**What's next.**

- The remaining ~18 detachments still have empty `stratagems` tuples —
  Awakened Dynasty, Gladius Task Force, WAAAGH! Tribe, Noble Lance, etc.
- Per-faction enhancement system (the four-points-each character upgrades
  that further differentiate detachments). Not yet scaffolded.
- Leader-auditing pass: confirm every leader's ability fires through the
  same `Unit.attack()` keyword path used by Detachment flags, so the buffs
  compose rather than override.

---

## Goal C — Generate balanced SwegHammer points 🔲

**Intent.** Replace GW's commercially-driven points with empirically-derived
costs that produce 50/50 matchups at equal points. Two independent solvers
run in parallel; the divergence between them is itself a calibration signal.

**Track 1 — Sweg-balancer (Monte Carlo bisection).**

- Lives in `code/balancer.py`; writes `data/calibrated_points.json`.
- For each unit: bisect its points-per-model UP/DOWN until armies-of-U vs
  armies-of-baseline-peer land at 50% ± 5% win rate over N battles.
- Slow (N × bisection steps per unit) but exercises **every** rule in the
  simulator: movement, range, terrain, charge probability, objective
  contests, CP economy. The Monte Carlo is honest about coupling.
- Modes: homogeneous (same-role peer baseline), `--leader-attached`
  (CHARACTER + host vs host alone), `--aura-uplift` (delta-WR for SUPPORT
  characters whose value is buffs rather than direct damage).

**Track 2 — Equilibrium solver (closed-form log-LSQ on time-to-kill).**

- Lives in `code/equilibrium.py`; writes `data/equilibrium_points.json` and
  `data/equilibrium_points_phase2.json`.
- Solves the symmetric zero-sum game over the catalogue: build a pairwise
  time-to-kill matrix `T[i,j]`, derive log advantage `R[i,j] = ½·log(T[j,i]/T[i,j])`,
  closed-form log-LSQ for `log(p_i)`. See file docstring for derivation.
- Fast (one analytic damage call per pair, no simulation), exposes the
  Bradley-Terry pairwise structure (best/worst matchups for any unit).
- Ed's solver; landed in phases.

**Two-track rationale.** Balancer captures emergent dynamics the analytic
solver can't see (terrain, objective contest, charge variance, CP).
Equilibrium captures pairwise rock-paper-scissors structure the bisection
hides (a unit that beats average opponents but loses hard to one matchup is
priced correctly by the equilibrium and incorrectly by the bisection). The
divergence is the calibration signal — see PROJECT.tex §"Two-track points
calibration".

**Key references.**

- `code/balancer.py`, `data/calibrated_points.json`
- `code/equilibrium.py`, `data/equilibrium_points.json` (Phase 1),
  `data/equilibrium_points_phase2.json` (Phase 2)
- `BASELINE.md` — points formula and baseline-Marine definition.

**What's done.**

- **Balancer**: homogeneous bisection, leader-attached mode, aura-uplift mode,
  detachments wired into calibration builders (audit in `BALANCER_AUDIT.md`).
- **Equilibrium Phase 1** (shooting): analytic shooting damage with
  hit / wound / save / invuln / FNP / Lethal / Sustained / Twin-Linked /
  Devastating / Anti-X.
- **Equilibrium Phase 2** (shoot + melee): per-attacker role-weighted blend
  of shooting and melee matrices. Pure-melee units rejoin the fit.

**What's next.**

- **Equilibrium Phase 3** — Defensive integration audit (high-FNP low-wound
  edge cases, MW-vulnerability).
- **Equilibrium Phase 4** — Tactical-utility term `tactical_value(u)` for
  non-damaging abilities (move, OC, deep strike, scout, infiltrator,
  sticky objective). **This is Goal D — see below.**
- **Equilibrium Phase 5** — Meta-weighting (weight residuals by tournament
  matchup frequency, so over-priced units that nobody actually faces don't
  dominate the fit).
- **Equilibrium Phase 6** — Solve the actual two-player zero-sum game
  (mixed strategies on the simplex) to handle rock-paper-scissors mispricing.
- **Cross-track validation**: walk the catalogue, find units where
  balancer and equilibrium disagree by > 30%, dig in.

---

## Goal D — Price non-damaging abilities 🔲

**Intent.** Speed, deep strike, scout, sticky objective, OC bonuses,
re-deploy, and similar "I move better" abilities don't show up in the
pairwise damage matrix `D[i,j]` but are real points value. A 6" move
INFANTRY squad and an 8" move JUMP PACK squad with identical stats are
*not* equally valuable; the JUMP PACK reaches objectives a round earlier.

**Status.** Collapsed into **Equilibrium Phase 4** — see
`code/equilibrium.py` bottom-of-file TODO stub. The plan is a
`tactical_value(u)` term added to `log(p_i)` after the LSQ solve, fit
against the empirical balancer numbers (which DO see speed advantage
because they run real battles).

**Key references.**

- `code/equilibrium.py` — `tactical_value()` TODO stub.
- `code/strategy.py` — the per-unit move intent layer that exercises
  speed/scout/objective-pressure value in the balancer.
- `code/roles.py` — coarse role labels (SHOOTY / MELEE / DUAL / HORDE /
  HEAVY / SUPPORT) used as a feature in both solvers.

**What's done.** Movement, scout distance, deep strike, infiltrator flags
recorded on every `CalibrationResult` (diagnostic only — not yet folded
into the cost).

**What's next.** Define the basis (move, OC, deep_strike, scout,
infiltrator, sticky_obj, re-deploy) and fit `tactical_value(u)` such that
equilibrium and balancer converge.

---

## Foundation work (delivered) ✅

The 2025–early-2026 phase-based work that built the substrate Goals A–D
run on top of. Retained as a historical record; the phase numbering is
**no longer the current organising structure** (see Changelog).

- **Phase 0** — Objectives + Primary VP win condition (5-objective quincunx,
  end-of-round scoring, OC-majority banks the marker, VP > points > draw).
- **Phase 1** — Deterministic simulator and the initial 18-unit hand-rolled
  catalogue.
- **Phase 1.5** — Stochastic damage, armour saves, AP, cover.
- **Phase 1.6** — BSData WH40k 10e ingestion (~1294 units), override layer.
- **Phase A2/A3** — Ten weapon keywords + Feel No Pain.
- **Phase B** — Charge + Fight (melee) phases.
- **Phase C** — Battleshock + Ld/OC on `UnitProfile`.
- **Phase D** — Detachment scaffolding (5 → 18 canonical detachments,
  10 modifier fields, faction defaults).
- **Phase E** — Stratagem framework (4 universals + 3 detachment-specific).

---

## Changelog

- **2026-05-15** — Reorganised around **Goals A–D**. The previous
  Phase 0 / 1 / 1.5 / 1.6 / 2 / 3 / 4 numbering plus the parallel
  Phase A2 / B / C / D / E / F / G strand had drifted into something
  nobody could navigate. The shipped foundation phases are retained as
  a historical record above. New work tracks against goals.
- **2026-05-14** — Orks Mob Rule + WAAAGH! window landed.
- **2026-05-11** — Equilibrium Phase 2 (melee damage matrix) landed.
- **2026-05-?? to 2025** — Phases 0–E shipped; see git log for detail.

---

## Future Considerations

### Faction-level balance

Once individual units are well-priced (Goal C settled), the next question
is whether **faction army special rules** create systemic advantages that
the matchup matrix can't decompose into unit prices. This is deferred
until Goal A's MAE target is hit.

### Web interface

Streamlit dashboard (`app.py`) already exists with attrition curves,
survivor histograms, points-vs-winrate sweep, and a scrub-through battle
replay. Future work: army-builder UI, calibration browser (drill into
outlier matchups from `evaluate_vs_meta`).

### Community calibration

Open simulation runs where players submit battle logs to feed the
calibration dataset, replacing pure-simulation data with real-world
outcomes. Deferred until the cost model is stable.
