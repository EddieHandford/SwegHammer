# Development Roadmap

SwegHammer is organised around **four goals**. Each goal owns a strand of
work that runs end-to-end through the simulator, the points solvers, and the
calibration harness. Progress is measured against a single headline metric —
the mean absolute error (MAE) of the per-faction win rate vs the May 2026
Warp Friends tournament aggregate — currently **MAE ≈ 5.48 pts at N=30 /
7.01 pts at N=200** (target ≤ 2.0 pts).

This file is the high-level status board. For the human-facing checklist
with ownership tags and math, see [`PROJECT.tex`](PROJECT.tex). For Claude
operating rules, see [`CLAUDE.md`](CLAUDE.md).

## Status Overview

| Goal | Status | Description |
|------|--------|-------------|
| Goal A | 🟡 9 of 10 faction army-rules shipped | Sim matches real tournament data (faction-specific mechanics) |
| Goal B | ✅ Foundation complete | Equal-quality simulation per faction (stratagems / leaders / enhancements) |
| Goal C | 🟡 Phases 1–6 shipped; needs cost rebase | Generate balanced SwegHammer points (two-track: balancer + equilibrium) |
| Goal D | 🟡 Phase 4 live | Price non-damaging abilities — `tactical_value(u)` overlay on Phase 2 |

Headline calibration metric:

- **MAE 5.48 pts at N=30** vs Warp Friends May 2026 (10-faction matchup matrix).
- **MAE 7.01 pts at N=200** — the true number; N=30 readings have ~3pt noise.
- Persistent residual outliers at N=200: Necrons -15.2, Aeldari +13.9, TSON
  -11.6, T'au +10.3.
- **Blocker**: `UnitProfile.points_cost` currently returns a Lanchester-
  derived score rather than the GW per-model cost from `points_per_squad /
  min_models`. Until this is fixed (Eddie's TODO, see PROJECT.tex), every
  sim-side army budget runs in wrong-currency. Equilibrium pipeline + Compare
  view already use GW costs correctly; calibration work below the fix is
  signal-correct but anchored to bad baselines.
- Measured by `python -m scripts.evaluate_vs_meta` (or
  `--battles 200` for the honest reading).

---

## Sprint plan: May 2026 (Ed/Jake handover)

Captured from the Ed/Jake conversation on 2026-05-15. See
[`PROJECT.tex` §"Sprint plan: May 2026 handover"](PROJECT.tex) for the
full ownership-tagged checklist.

**Architecture clarification.** SwegHammer is two systems:

- **Equilibrium model** (`code/equilibrium.py`) — Lancaster-derived,
  multi-dimensional, non-linear closed-form solver. **This is what
  ships in the final product.**
- **Simulator** (`code/simulator.py`) — exists to tune the utility
  factors (deep strike, sticky objectives, scout, re-deploy, etc.)
  that feed back into the equilibrium model. Slow and iterative; only
  needed for calibration and for pricing newly-released models whose
  utility weights are not yet known.

**Calibration constraint.** Tournament data is sparse — even the Las
Vegas Open produces only a few thousand games across roughly twenty
factions, which is too thin for faction-vs-faction matchup matrices on
its own. The simulator covers the gap by generating synthetic matchup
volume.

**Near-term sequence (priority order).**

1. **Speed up the user interface for faster iteration** (Eddie). The
   convergence tab is the right shape; extend the same live-streaming
   pattern to the calibration sweep so a tuning loop does not block on
   a multi-minute wait.
2. **Get the simulator's mean absolute error down to 2–4 %** (Jake,
   in progress). Headline metric for this sprint; everything
   downstream blocks on it.
3. **Generate a trial balanced points dataset.** Once the mean
   absolute error is in the 2–4 % band, run the two-track points
   solvers (`code/balancer.py` and `code/equilibrium.py`, see Goal C
   below) and cache the output as a candidate full-catalogue
   re-pricing.
4. **Sanity-check the trial dataset, then play-test in person.** After
   `scripts/cross_validate_pricing.py` clears the obvious outliers,
   approach local game groups for a structured blind play-test round
   — unit costs swapped in without telling players which units have
   been re-priced, then a post-game survey on perceived fairness.

**Final product vision.** When this sprint lands, the shipped product
is the front end running the equilibrium equation on the
trial-balanced points dataset, with the simulator preserved as a
calibration utility for future Games Workshop releases.

---

## Goal A — Sim matches real tournament data 🟡

**Intent.** Drive the per-faction MAE down by implementing the
faction-specific mechanics that distinguish Necrons from Tyranids from Orks
in real play.

**Target.** MAE ≤ 2.0 pts vs Warp Friends aggregate.

**What's done.**

- **Faction army rules** (10e codex army-rule level):
  - Orks: WAAAGH! once-per-battle + Mob Rule (10+ auto-pass BS)
  - Tyranids: Synapse Imperative (auto-pass within 6") + Shadow in the Warp (-1 BS within 12")
  - Drukhari: Pain Tokens / Power From Pain (Lethal Hits + FNP 6+ while held)
  - Adeptus Mechanicus: Doctrina Imperatives (Protector / Conqueror per Command phase)
  - Genestealer Cults: Cult Ambush (army-wide turn-1 redeploy)
  - World Eaters: Blood Tithe (escalating BT spends, Lethal Hits at 4 BT)
  - Death Guard: Disgustingly Resilient (FNP 5+ army-wide) + Contagions of Nurgle (escalating -1 T / -1 Ld / -1 hit aura)
  - Thousand Sons: All Is Dust (-1 to wound on D=1 attacks)
  - Necrons: Reanimation Protocols + Awakened Dynasty buffs
  - Adeptus Astartes: **[pending — needs retry]** Oath of Moment + Combat Doctrines
- **Core 10e mechanics**: Hit/Wound/Save w/ crits, AP+invuln+FNP, 18 weapon
  keywords, Cover (light/heavy/obscuring), Big Guns Never Tire,
  Sticky Objectives, Deep Strike / Scouts / Infiltrators, Battleshock with
  Mob Rule auto-pass, Heroic Intervention + Counter-Offensive stratagems,
  CP economy (3 start, +1/round capped at 6).
- **New core 10e mechanics shipped this session**: Look Out Sir (CHARACTER
  protection within 3" of bodyguard, 12" range cap), Lone Operative (12"
  targeting restriction on solo characters), Deadly Demise X (vehicle/monster
  death AoE on a 6+), Fall Back + Desperate Escape Test (disengage from
  melee at the cost of shooting/charging that turn + d6-per-model attrition).
- **Mapper fixes**: Recovered 98 invuln_save fields (Custodes 4++, AdMech
  5++, Terminator 4++, etc.); read FNP from datasheet infoLink modifier-
  append for 81 units (Poxwalkers 5+, Wracks 5+, Death Company 6+, Wulfen
  6+, Repentia 5+); Drukhari codex now picks up 27 units via cross-library
  import resolution.
- **List builder**: 10 curated per-faction archetypes (Gladius, Awakened
  Dynasty, Battle Host, Kauyon, etc.) shipped as opt-in (`use_archetype=True`).
  Default OFF — preserves current MAE baseline while infrastructure is
  available for post-cost-recalibration use.
- **Validation harness**: `tests/test_faction_mechanic_smoke.py` confirms
  all 19 implemented mechanics actually fire in a real battle. 469 total
  unit tests, 122/122 rule citations.

**What's next.**

- Land Marines (Oath of Moment + Combat Doctrines) without overshooting the
  +5pt buff that wrecked the previous two attempts. Needs new approach —
  either a damped version of Oath (re-roll 1s only, not full re-roll) or
  concurrent Marine points re-calibration.
- Aeldari Battle Focus strategy bias retry — currently the ASURYANI advance
  branch is inert because Aeldari at +13.9 are over-strong; making them more
  active worsens MAE. Needs to land after points re-balance.
- Drukhari mapper rewrite retry — parser fix shifted the Aeldari pool
  composition (+0.71 regression). Needs C1 cost rebase to absorb the
  redistribution.

---

## Goal B — Equal-quality simulation per faction ✅ Foundation

**Intent.** Bring every faction to the same depth of in-game representation
so cross-faction matchups aren't biased by which factions had their abilities
modelled first.

**What's done.**

- **Stratagems**:
  - 4 universal core stratagems (Command Re-Roll, Counter-Offensive,
    Tank Shock, Heroic Intervention)
  - 3 original detachment stratagem sets (Cult of Magic, Plague Company,
    Battle Host)
  - 5 new per-faction stratagems shipped this session: Implacable Onslaught
    + Methodical Destruction (Necrons), Cabbalistic Empowerment (TSON),
    Spirit Stones (Aeldari/Saim-Hann), Strike Swiftly (T'au/Mont'ka).
- **Detachments**: 25 total (was 21). Each faction now has at least
  one canonical detachment; 4 majors (Marines, Necrons, Aeldari, DG) have
  a second:
  - Marines: Gladius + Ironstorm Spearhead
  - Necrons: Awakened Dynasty + Canoptek Court
  - Aeldari: Battle Host + Saim-Hann Wild Host
  - Death Guard: Plague Company + Plague Marines Onslaught
- **Enhancements** (10e Warlord upgrades, 5 shipped): Champion of Humanity
  (Gladius), Hyperphasic Fulcrum (Awakened Dynasty), Arcane Vortex
  (Cult of Magic), Living Plague (Plague Company), Puretide Engram
  Neurochip (Mont'ka). Auto-assigned at army build to highest-points
  CHARACTER, one per army, points subtracted from budget.
- **CP-discount HQs**: 4 named Warlords with stratagem-economy effects:
  Belisarius Cawl (+1 CP once/battle), Roboute Guilliman (+1 CP/round),
  Trazyn the Infinite (1x refund), Lord of Contagion (1st strat/round free).
- **Leader abilities**: 32 registered with verbatim Wahapedia citations.
  Audit confirmed all 31 `LeaderAbility.*` citations are verbatim (the
  "approximation" markers exist only on `effect` fields by design).
- **Citation coverage**: 122/122 active rules cited, gated by
  `scripts/audit_rules.py` on every commit.
- **Mechanic-fire validator**: `tests/test_faction_mechanic_smoke.py` runs
  19 mechanics through seeded battles to confirm each one actually triggers
  (no silent dead code).

**What's next.** B-tier is feature-complete for the current scope.
Future depth (a second enhancement per detachment, more stratagems per
detachment) is a polish layer not gated on Goal A.

---

## Goal C — Generate balanced SwegHammer points 🟡

**Intent.** Replace GW's commercially-driven points with empirically-
derived costs that produce 50/50 matchups at equal points. Two independent
solvers run in parallel; the divergence between them is itself a
calibration signal.

**Track 1 — Sweg-balancer (Monte Carlo bisection).**

- Lives in `code/balancer.py` (homogeneous + leader-attached + aura-uplift
  modes) and `scripts/sweg_balance_mc.py` (per-faction targeted bisection
  on win-rate residuals).
- Latest run (this session, commit `5d28049`) shifted 10 units: T'au
  Crisis/Riptide +10%, Aeldari Wraithguard/Falcon +10%, Necron Lokhust
  Destroyers/Tomb Blades -10%, TSON Rubric Marines/Scarab Occult -10%.
  Direction-correct but magnitude small relative to N=30 noise.

**Track 2 — Equilibrium solver (closed-form log-LSQ on time-to-kill).**

- Lives in `code/equilibrium.py`. All 6 phases shipped:
  - **Phase 1** (shooting only) — Ed's foundational solver, log-LSQ on
    `T[i,j] = wounds(j) / D[i,j]`.
  - **Phase 2** (shoot + melee) — per-attacker role-weighted blend.
  - **Phase 3** (defensive audit) — flagged 69 high-FNP / 21 invuln-cliff
    / 819 multi-wound units; surfaced the BSData mapper FNP/invuln drop
    bugs that #142 and #151 then fixed.
  - **Phase 4** (tactical utility) — `tactical_value(u)` overlay on Phase 2;
    grid-search calibrated on 9 anchors (held-out RSS 38932 → 33666).
    This is also Goal D.
  - **Phase 5** (meta-weighting) — re-weighted LSQ using May 2026 Warp
    Friends faction shares. High-meta-share factions price up.
  - **Phase 6** (Nash mixed-strategy) — antisymmetric trade-ratio payoff
    matrix solved via `scipy.optimize.linprog`. Pearson r 0.968 vs Phase 5
    (Nash collapses on Warlord Titan as universal dominant — mathematically
    right, pricing-wise extreme).

**Cross-validation.** `scripts/cross_validate_pricing.py` (commit `ff48072`)
compares Phase 5 mispricing % vs MC bisection shifts. On the live catalogue:
2 disagreements (Wraithguard, Crisis Sunforge — both have faction-rule
synergies Phase 5 disregards), 5 confirmations. The disagreement
methodology is the long-term calibration loop.

**Key references.**

- `code/balancer.py`, `scripts/sweg_balance_mc.py`,
  `data/calibrated_points.json`, `data/overrides.json`
- `code/equilibrium.py`, `data/equilibrium_points_phase{1,2,4,5,6}.json`
- `BASELINE.md` — points formula and baseline-Marine definition.
- `code/compare_view.py` + Compare tab in `app.py` — drill into per-unit
  mispricing across phases.

**Blocker.** `UnitProfile.points_cost` returns a Lanchester-derived score,
not GW per-model cost. Every sim-side army budget is wrong-currency until
Ed lands the points-per-model import fix flagged in PROJECT.tex `\eddie`
TODO. Sweg-balancer outputs (and the 10-unit overrides shipped in `5d28049`)
will need re-anchoring once the cost basis is correct.

**What's next.**

- Wait for Ed's points-per-model import fix.
- After fix: re-run Sweg-balancer MC + cross-validate vs Phase 5 — should
  converge to many fewer disagreements when the baseline is right.
- Iterative MC passes per-faction to converge MAE; each pass capped at
  25% per unit, full catalogue sweep target.

---

## Goal D — Price non-damaging abilities 🟡 Phase 4 live

**Intent.** Speed, deep strike, scout, sticky objective, OC bonuses,
re-deploy, and similar "I move better" abilities don't show up in the
pairwise damage matrix `D[i,j]` but are real points value.

**Status.** Phase 4 of the equilibrium solver implements the
`tactical_value(u)` term — a multiplicative overlay on the Phase 2 result.
Weights calibrated by 5-level grid search on 9 anchors.

**Limitations of current calibration.**
- `w_move`, `w_oc`, `w_infiltrator`, `w_deep_strike` calibrate to 0 against
  the current anchor set (under-identification).
- Single-anchor traits can't constrain — needs wider anchor set with
  diverse mobility profiles (Spectres, Stormboyz, Acolytes).

**Key references.**

- `code/equilibrium.py` — `tactical_value()`, `TacticalWeights`,
  `compute_phase4()`, `_calibrate_weights()`.
- `code/strategy.py` — exercises speed / scout / objective value in
  the balancer.

**What's next.** Widen the anchor set; re-enable `w_deep_strike` after Ed
fixes the points-per-model import (the anchor's GW cost matters for grid
search target).

---

## Foundation work (delivered) ✅

The 2025–early-2026 phase-based work that built the substrate Goals A–D
run on top of. Retained as a historical record.

- **Phase 0** — Objectives + Primary VP win condition.
- **Phase 1** — Deterministic simulator + initial hand-rolled catalogue.
- **Phase 1.5** — Stochastic damage, armour saves, AP, cover.
- **Phase 1.6** — BSData WH40k 10e ingestion (~1308 units), override layer.
- **Phase A2/A3** — Ten weapon keywords + Feel No Pain.
- **Phase B** — Charge + Fight (melee) phases.
- **Phase C** — Battleshock + Ld/OC on `UnitProfile`.
- **Phase D** — Detachment scaffolding (5 → 18 → 25 detachments).
- **Phase E** — Stratagem framework + universal stratagems.

---

## Changelog

- **2026-05-15** — Goals A/B/C/D goal-driven structure mature. Session
  shipped 25+ integrations: Tyranids/Drukhari/AdMech/GSC/WE army rules,
  DG FNP + Contagions, TSON All Is Dust, Look Out Sir + Lone Op, Deadly
  Demise X, Fall Back + Desperate Escape, Mapper FNP/invuln fixes,
  Equilibrium Phases 3-6, MC-driven C1 balance pass, Cross-validation,
  Curated archetypes (opt-in), Enhancements, CP-discount HQs, Z2 CSV
  export, Z3 Compare view. Cumulative MAE shift 4.96 → 5.48 at N=30
  (8.33 → 7.01 at N=200, the honest reading).
- **2026-05-15** — Reorganised around **Goals A–D**.
- **2026-05-14** — Orks Mob Rule + WAAAGH! window landed.
- **2026-05-11** — Equilibrium Phase 2 (melee damage matrix) landed.

---

## Future Considerations

### Points-per-model import fix (Eddie)

Per Ed's TODO in PROJECT.tex (commit `a0d7702`): the BSData → UnitProfile
pipeline reads `points_per_squad` correctly but `points_cost` returns a
Lanchester-derived score, so all sim-side army budgets are wrong-currency.
This is the bottleneck blocking the next calibration iteration. Ed has
claimed this task; Claude work pauses cost-anchored changes until it lands.

### Faction-level balance

Once individual units are well-priced (Goal C settled), the next question
is whether faction army special rules create systemic advantages.

### Web interface

Streamlit dashboard (`app.py`) has 5 tabs (Statistics, Watch a battle,
Efficiency, Equilibrium, Compare to SwegHammer). Future work: army-builder
UI, calibration browser drilling into outlier matchups.

### Community calibration

Players submit battle logs to feed the calibration dataset. Deferred
until the cost model is stable.
