# Development Roadmap

SwegHammer is organised around **four goals**. Each goal owns a strand of
work that runs end-to-end through the simulator, the points solvers, and the
calibration harness. Progress is measured against a single headline metric —
the noise-gated mean absolute error (MAE) of the per-faction win rate vs the
May 2026 Warp Friends tournament aggregate, each faction's error counted only
beyond its per-faction noise floor — currently **gated 6.70 pts at N=80
(raw 10.05), 5 of 22 factions inside the noise band** (target: gated → 0).

This file is the high-level status board. For the human-facing checklist
with ownership tags and math, see [`PROJECT.tex`](PROJECT.tex). For Claude
operating rules, see [`CLAUDE.md`](CLAUDE.md).

## Pipeline structure

SwegHammer runs as two sequenced feedback loops, not one. See
[`OVERVIEW.tex`](OVERVIEW.tex) for the non-technical picture and
[`CLAUDE.md`](CLAUDE.md) "Project plan" for the rules-of-thumb.

- **Stage 1 — Make the simulator play like reality.** Goal A below.
  The feedback signal is the noise-gated mean absolute error vs the May 2026
  Warp Friends per-faction win rates, currently gated 6.70 pts at N=80
  against a gated-to-zero target. Stage 1 is the current focus.
- **Stage 2 — Fit the points equation.** Goals C and D below. Fits one
  master equation that prices every unit from its stats (plus small
  per-unit residuals), tuning the stat coefficients and residuals until
  the spread of per-unit win rates across the catalogue flattens. The
  loop adjusts the equation, not individual prices; per-unit costs are
  derived from the fitted formula. While Stage 1 is unconverged, Stage 2
  outputs (`data/calibrated_points.json`, `data/equilibrium_points*.json`)
  are provisional and will need redoing once Stage 1 lands.

Goal B (equal-quality faction representation) sits underneath both
stages — it is the groundwork that makes Stage 1's measurements honest
and Stage 2's solvers possible.

## Status Overview

| Goal | Status | Description |
|------|--------|-------------|
| Goal A | 🟡 9 of 10 faction army-rules shipped | Sim matches real tournament data (faction-specific mechanics) |
| Goal B | ✅ Foundation complete | Equal-quality simulation per faction (stratagems / leaders / enhancements) |
| Goal C | ✅ v1 shipped (Track 4 data-driven equation, frozen at `data/sweg_points_v1.json`) | Generate balanced SwegHammer points (two-track: balancer + equilibrium) |
| Goal D | 🟡 Phase 4 live | Price non-damaging abilities — `tactical_value(u)` overlay on Phase 2 |

Headline calibration metric:

- **Noise-gated MAE 6.70 pts at N=80** vs the Warp Friends May 2026 rolling
  aggregate (`data/warpfriends_rolling.json`, 22-faction field) — raw MAE
  10.05; 5 of 22 factions inside their noise band.
- Largest gated residuals on the standing anchor
  (`data/_anchor_sc9c_n80_log.json`): Adeptus Custodes +20.1 over, Astra
  Militarum -19.0 under, World Eaters +16.7 over, Death Guard +12.2 over,
  Emperor's Children +12.1 over.
- ~~**Blocker**: `UnitProfile.points_cost` currently returns a Lanchester-
  derived score rather than the GW per-model cost from `points_per_squad /
  min_models`.~~ Resolved across commits `a0d7702` (property now prefers
  GW canonical), `c084ba0` (squad-size extraction for shape-c units), and
  the 2026-05-17 branch `claude/fixinfequivexplorer` (leader-plus-body and
  cost-tier-implicit squad-size shapes; stale `points_override` entries
  removed). Equilibrium pipeline, Compare view, and the army builder all
  now run in GW per-model currency. Sweg-balancer overrides that were
  anchored to the old (wrong) per-model basis were dropped — re-running
  the balancer will repopulate them.
- Measured by `python -m scripts.evaluate_vs_meta` (or
  `--battles 200` for the honest reading).

**All 22 factions now have real Warp Friends tournament data (as of pull
request 32, 2026-05-23).** `APPROX_FACTIONS` in
`scripts/evaluate_vs_meta.py` is now empty. The headline mean absolute
error is still anchored to the original 10-faction subset for historical
continuity; the all-22 figure is reported alongside it. All 22 faction
multipliers in the data-driven equation fit are now active (previously
only 10 were real; the remaining 12 defaulted to a 1.0× no-correction
multiplier).

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

**Target.** All 22 factions inside their per-faction noise band — `mean(max(0, |sim - target| - noise_floor))` reaches 0. The legacy "raw MAE ≤ 2.0" target was below the natural noise floor of the underlying tournament aggregate (mean noise floor 3.67 pts across the 22 factions); the structural endpoint is now "no faction sits outside sampling variance of real meta", not a single absolute MAE number.

**What's done.**

- **Faction army rules** (10e codex army-rule level):
  - Orks: WAAAGH! once-per-battle + Mob Rule (10+ auto-pass BS)
  - Tyranids: Synapse Imperative (auto-pass within 6") + Shadow in the Warp (-1 BS within 12")
  - Drukhari: Pain Tokens / Power From Pain (Lethal Hits + FNP 6+ while held)
  - Adeptus Mechanicus: Doctrina Imperatives (Protector / Conqueror per Command phase)
  - Genestealer Cults: Cult Ambush (army-wide turn-1 redeploy)
  - World Eaters: Blood Tithe (escalating BT spends, Lethal Hits at 4 BT)
  - Death Guard: Disgustingly Resilient (the real 10e rule is the Virulent Vectorium 2-command-point stratagem, -1 Damage — there is NO army-wide Feel No Pain in the 10th-edition codex; a fabricated fnp=5 override citing a non-existent army-wide rule was removed from data/overrides.json on Plague Marines / Blightlord Terminators / Typhus, DURA-AUDIT-D4 — live behaviour was already faithful, the loader's fabrication-removal gates had neutralised it since iter-15) + Contagions of Nurgle / Nurgle's Gift, rebuilt across the durability fidelity audit D fixes: Contagion Range escalates 3"/6"/9" by battle round per the printed schedule (DURA-AUDIT-D1); always-on Afflicted -1 Toughness from round 1 (DURA-AUDIT-D2); one chosen Plague active from round 1 for the whole battle — Skullsquirm Blight (-1 to the Afflicted unit's own Hit roll), Rattlejoint Ague (-1 Save characteristic), or Scabrous Soulrot (-1 Move / -1 Leadership / -1 Objective Control, floored at 1) — picked by an artificial-intelligence heuristic reading the opposing roster at battle start, not a player decision (DURA-AUDIT-D3, `Battle._choose_dg_plague`)
  - Thousand Sons: All Is Dust (Rubricae Phalanx detachment, +1 save vs unmodified D1 on RUBRICAE units) + Rites of Coalescence (Scarab Occult Terminators datasheet ability, -1 to wound on any-D attacks while a PSYKER is present)
  - Necrons: Reanimation Protocols + Awakened Dynasty buffs
  - Leagues of Votann: Prioritised Efficiency army rule (env-gated `SWEG_VOTANN_PRIORITISED_EFFICIENCY`, default OFF) — the current 10e codex army rule, re-introduced after the launch-day Eye of the Ancestors mechanic was retired and zeroed out (which had left Leagues of Votann running with no army-wide combat buff at all). The implemented clause is Hostile Acquisition: a Leagues of Votann attacker adds 1 to the Hit roll when the target is within range of an objective marker, the same near-objective +1-to-Hit shape as Necrons Relentless Onslaught. The condition (target near an objective, not a blanket army-wide +1) is what keeps the buff moderate, avoiding a repeat of the +16.8-point over-performance the retired rule caused. Approximation: only the Hostile Acquisition state is modelled — the Yield-Point economy, the Fortify Takeover switch at 7 Yield Points, and the Advance-and-Charge re-roll are not. Also the Hearthband detachment (env-gated `SWEG_VOTANN_HEARTHBAND`, default OFF — the real codex detachment covering roughly 45 percent of the 2026 tournament Leagues of Votann meta, previously entirely absent from the simulator's generic "Oathband" stub): Methodical Annihilation re-rolls a Wound roll of 1 on melee attacks, modelled exactly because a Fight-phase attack is always within Engagement Range under the 10e core rules; the ranged half of the same clause (restricted to the closest eligible target) and the Armour Penetration bonus for Kâhl, Einhyr Hearthguard and Ûthar the Destined units are honestly left un-modelled rather than approximated, since neither has a faithful expression with the simulator's existing accumulators. Byte-identical to the pre-existing Oathband default when the gate is off.
  - Imperial Knights: Code Chivalric army rule (re-roll ONE Hit roll and ONE Wound roll per activation — the real "martial valour" Quality; wave 71 corrected this from the over-scaling "re-roll all natural 1s") + Ion Shield (5+ invulnerable save against ranged attacks ONLY — wave 72 fidelity fix: big Imperial Knights have no invulnerable save in melee, only their 3+ armour; Chaos Knights' Ion Shield is ranged and melee; durability fidelity wave, audit B fix 1, extended the ranged-only correction to five more chassis that shared the same BSData shape but had been missed — Knight Destrier, Acastus Knight Asterius, Acastus Knight Porphyrion, Cerastus Knight Castigator, Knight Defender — and, fix 2, restored the Cerastus Knight Acheron's own 5+ ranged-only invulnerable save, which BSData authors under a profile named after the unit itself rather than "Invulnerable Save", so it had been carrying no invulnerable save at all) + Valourstrike Lance detachment: Bold Gallantry ([ASSAULT] on IK ranged weapons when any IK unit Advances) + Bondsman abilities (each TITANIC+CHARACTER IK knight buffs one Armiger per Command phase with Paladin's Duty: Lethal Hits + Lance)
  - Chaos Knights: Harbingers of Dread army rule (Deathly Terror Battle-shock aura + Doom wound-roll bonus vs Battle-shocked targets) + Iconoclast Fiefdom detachment: Dread Tyrants Aura (War Dog units re-roll hit and wound 1s while a friendly TITANIC Chaos Knights unit is within 9")
  - Astra Militarum: Voice of Command Orders (Officers issue per-datasheet Order counts to REGIMENT / SQUADRON / TITANIC units — wave 243 made REGIMENT and SQUADRON first-class unit keywords from the BSData categoryLink entries, replacing a BATTLELINE proxy that silently blocked nearly the whole faction; "First Rank, Fire! Second Rank, Fire!" is only issued to units that actually carry a Rapid Fire weapon, since the rule text buffs Rapid Fire weapons exclusively — tanks receive Take Aim! instead) + Flexible Command stratagem (widens a REGIMENT-only Officer's eligible set to SQUADRON for the round) + Grizzled Company detachment (env-gated `SWEG_AM_GRIZZLED`, default OFF — the real top-performing Astra Militarum detachment released Grotmas December 2025, previously entirely absent from the simulator: Ruthless Discipline gives +1 Order per Officer and re-rolls Hit rolls of 1 for attacks made by a unit affected by an Order; byte-identical to the pre-existing Combined Arms default when the gate is off)
  - Adeptus Astartes: **[pending — needs retry]** Oath of Moment + Combat Doctrines
  - Emperor's Children: Coterie of the Conceited detachment (env-gated `SWEG_EC_DETACHMENT`, default OFF — the confirmed competitive go-to detachment, previously entirely absent so the faction ran with no detachment at all: Slaanesh's Due grants four cumulative attack bonuses keyed to a running Pact-point total that accrues one point per enemy unit destroyed while the Warlord lives — 1+ re-roll Hit rolls of 1, 3+ re-roll Wound rolls of 1, 5+ melee weapons gain [LETHAL HITS] and [SUSTAINED HITS 1], 7+ a Critical Hit on an unmodified Hit roll of 5+; the player-chosen pledge is idealised as competent play and the missed-pledge mortal-wound downside honestly omitted; byte-identical to the pre-existing no-detachment path when the gate is off)
- **Core 10e mechanics**: Hit/Wound/Save w/ crits, AP+invuln+FNP, 18 weapon
  keywords, Cover (light/heavy/obscuring), Big Guns Never Tire (both
  directions — the attacker's own in-engagement -1 and the reciprocal
  shooting-into-engagement clause, gate `SWEG_BGNT_RECIPROCAL`: an enemy
  pinned in melee by a friendly unit can only be shot if it is a
  MONSTER/VEHICLE, at -1; Blast can never target an engaged unit),
  Sticky Objectives, Deep Strike / Scouts / Infiltrators, Battleshock with
  Mob Rule auto-pass, Heroic Intervention + Counter-Offensive stratagems,
  CP economy (3 start, +2/round from the two Command phases — both players
  gain 1 command point at the start of EACH Command phase, capped at 6;
  secondary-economy audit fix D4, 2026-07-03, corrected from the previous
  +1/round; env-gated `SWEG_CP_PER_COMMAND_PHASE`, default ON).
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
- Aeldari Battle Focus VEHICLE gate fixed (wave 59, AELDARI-BATTLE-FOCUS-V1):
  the Star Engines Agile Manoeuvre token spend now correctly requires both
  ASURYANI and VEHICLE keywords, reducing Aeldari overperformance by ~4 pts
  (pre-fix +18.5, post-fix +14.4 vs real 44.4%). Remaining overperformance
  driven by Strands of Fate and Yncarne/Avatar strength — further waves
  needed to close the residual.
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
- **Detachments**: 26 total (was 21). Each faction now has at least
  one canonical detachment (Emperor's Children's Coterie of the Conceited,
  the 26th, is env-gated `SWEG_EC_DETACHMENT` default-off pending its
  adoption screen); 4 majors (Marines, Necrons, Aeldari, DG) have
  a second:
  - Marines: Gladius + Ironstorm Spearhead
  - Necrons: Awakened Dynasty + Canoptek Court
  - Aeldari: Battle Host + Saim-Hann Wild Host
  - Death Guard: Plague Company + Plague Marines Onslaught
- **Enhancements** (10e Warlord upgrades, 5 shipped post-LC-4):
  Champion of Humanity (Gladius), Hyperphasic Fulcrum + Phasal Subjugator
  (Awakened Dynasty), Veiled Blade (Shield Host), Puretide Engram Neurochip
  (Mont'ka). Auto-assigned at army build to the highest-points CHARACTER,
  one per army, points subtracted from budget. LC-4 also corrected
  Hyperphasic Fulcrum's mapping from +1 to hit (misread) to reroll-wound-1s
  (BSData v10.6.0 verbatim). Auric Champions has no wired enhancement —
  all four codex picks (Superior Creation revive-on-death, Champion of the
  Imperium range extension, Inspirer battle-shock immunity, Radiant Mantle
  hit-roll debuff) require simulator schema that doesn't exist yet.
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

**Blocker** ~~`UnitProfile.points_cost` returns a Lanchester-derived score,
not GW per-model cost.~~ Resolved — see the Status header above. Stale
Sweg-balancer `points_override` entries (Crisis Fireknife / Sunforge,
Deathshroud, Plague Marines, Rubric Marines, Scarab Occult Terminators,
Hearthkyn Warriors) calibrated against the pre-fix model counts were
dropped from `overrides.json` on 2026-05-17 and need re-running.

**Track 3 — Sim-driven calibrated equation (new, 2026-05-21).**

A third fitting path uses the simulator itself — not the closed-form
damage matrix — as the oracle for unit value. This makes faction rules,
detachment passives, leader auras, cover, and movement all feed through
to the prices. The pipeline has two steps:

1. **Fit**: `scripts/fit_equation_calibrated.py` reads
   `data/meta_comparison_snapshot.json`, selects factions whose MAE
   vs tournament data is within a configurable threshold (default 10 pts),
   measures pairwise win rates for a representative unit sample from those
   factions, and fits Bradley-Terry log-LSQ to produce per-unit
   `price_per_model`. Units outside the trusted set inherit closed-form
   Phase 1 fallback prices. Output: `data/equation_calibrated_points.json`.

2. **Evaluate**: `scripts/evaluate_vs_meta.py --equation-prices
   data/equation_calibrated_points.json --out data/equation_vs_meta_snapshot.json`
   runs the full faction matrix with equation prices injected via
   `UnitProfile.points_override`, producing "hypothetical win rates" for
   every faction — including uncalibrated ones (extrapolation).

Both steps are launchable from the Calibration tab in the graphical user
interface (Step 1 / Step 2 expanders) without touching the terminal.

**Windows / subprocess note.** `scripts/fit_equation_calibrated.py` and
`scripts/evaluate_vs_meta.py` both contain a PYTHONHASHSEED re-exec guard
(they call `os.execvpe` to restart themselves with `PYTHONHASHSEED=0` if
the variable is not already set). Launching via PowerShell's `Start-Process`
or piping stdout loses the output after the re-exec because the new process
gets a fresh stdout handle. The graphical user interface launcher avoids
this by setting `PYTHONHASHSEED=0` in the subprocess environment dict
before starting the child process, so the guard never fires. If running
manually from a terminal: prefix with `set PYTHONHASHSEED=0 &&` in cmd.exe
or `$env:PYTHONHASHSEED="0";` in PowerShell.

**Current status (2026-05-21).** First equation fit completed: 61 units
from 4 trusted factions (Necrons, Orks, T'au Empire, Thousand Sons),
1,830 pairs, 5 battles/pair, 11 workers, 97 seconds. 1,422 remaining
catalogue units priced via Phase 1 fallback. Stage 1 is still
unconverged (MAE ~7 pts), so this output is provisional.

**Track 4 — Data-driven equation fit (new, 2026-05-22).**

After the simulator-driven Track 3 ran into a Stage 1 ceiling (premium
units like Magnus and the C'tan shards collapsed to single-digit prices
under every army-build variation we tried — homogeneous, archetype-seed
at 20 percent of budget, archetype-seed capped at one squad — because
the simulator's body-count bias bleeds through every layer), we
pivoted to a regression approach that fits the equation directly on
real data rather than on simulator outputs.

The model is a Generalized Additive Model: for every unit, each numeric
feature (Wounds, Toughness, Save, Strength, Damage, Attacks, OC, Move,
Range, keyword flags, interaction terms, plus utility derivatives like
expected damage per turn and effective wounds) gets a per-feature
transform — linear, log, quadratic, cubic, or sqrt. The transformed
features sum to predict ``log(GW points per model)``. The fit produces
per-feature coefficients plus per-unit residuals. A per-faction
multiplier derived from the Warp Friends tournament win-rate snapshot
then scales the equation output per faction. All 22 factions now have
real win-rate data and receive a non-trivial multiplier (see pull
request 32, 2026-05-23).

Runtime is seconds, not hours — no simulator involvement. The
simulator becomes a validator (Stage 2 evaluate-vs-meta sees whether
cross-faction win rates equalise under the new prices) rather than
the source of pricing signal.

A new Streamlit tab ("Equation Fit") visualises the regression: a
toggle panel for which features to include, a form selector per
feature, R-squared and mean absolute error metrics, a predicted-vs-GW
scatter, a 3D surface plot (pick two features for the axes, the
surface is the fit, the points are real units, colour by faction,
point size by mispricing), and a top-20 outlier table. The iteration
loop is to change a feature's functional form, refit, see the surface
shift, watch which units come back inside the residual band.

Output schema reuses ``data/equation_calibrated_points.json`` so the
existing Equilibrium tab visualisation keeps working unchanged.

Implementation lives in ``code/equation_data_fit.py``,
``scripts/fit_equation_data_driven.py``, and the new "Equation Fit"
tab in ``app.py``. The sim-driven Track 3 (``code/equilibrium_simdriven.py``
and ``scripts/fit_equation_calibrated.py``) remains in the tree for
comparison and possible future use once Stage 1 converges and its
body-count bias clears.

**Known limitations of Track 4 (accepted):**

- The cleanest validation — "do winning tournament lists sum to
  more equation-points than 2000?" — is blocked on getting real
  per-list tournament data into the repo. We currently only have
  per-faction aggregates. The Equation Fit tab includes an
  archetype-proxy section that uses the 22 curated
  ``code/archetypes.py`` lists as one-list-per-faction substitutes,
  flagged as directional only. See ``TODO.md`` "MASSIVE TODO — Real
  tournament list data ingestion" for the data-collection plan.
- Faction multipliers are coarse — every unit in a faction gets the
  same correction. We have no per-unit tournament data to
  differentiate within a faction.
- The equation inherits any systematic biases in GW's own pricing.
- Super-heavy units (500+ points per model — Titans, Thunderhawks,
  Forgeworld Legends) have a structural mean absolute error around
  344 points per model. The stats-only equation cannot price these
  accurately; they are out-of-scope for the equation's primary use
  case (competitively-played units in the 15–500 points range).
- Faction rules, detachments, and leader auras do not appear in the
  regression unless explicitly feature-engineered (a follow-up
  iteration would add boolean features like "has Awakened Dynasty
  access" or "is led by a CHARACTER with an aura").

**What's next.**

- Once Stage 1 MAE reaches ~4 pts, refit the equation with more trusted
  factions, higher battle count (20+), and max-per-faction raised to 25–30.
- Run the evaluation step and inspect the "hypothetical win rates" chart
  in the graphical user interface to see how well the equation prices across
  uncalibrated factions.
- Re-run Sweg-balancer MC against the corrected GW per-model baseline and
  cross-validate vs Phase 5 — should converge to many fewer disagreements
  now that the cost basis is right.
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

**What's next.** Widen the anchor set; re-enable `w_deep_strike` — the
points-per-model import is now resolved (see Status), so the anchor's GW
cost can be trusted for the grid-search target.

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

- **2026-05-25** — **Equation expansion + family rollups + super-heavy
  fallback removed.** Added ~75 new features to
  `code/equation_data_fit.py::default_feature_specs()` across four
  rounds: leader-aura buffs (16 features sourced from `code.leaders.
  _REGISTRY` via `lookup_ability`), direct stats and weapon-keyword
  features (hit probabilities, secondary weapon profile, pistol /
  precision / hazardous / assault / heavy / lance / indirect_fire /
  one_shot / fights_first / firing_deck / Anti-X / deadly_demise /
  leadership / reanimates_with_army), polynomial transforms (quadratic /
  cubic toughness, squared wounds / AP / damage), and cross-stat
  interactions (attacks × strength, attacks × damage, save × wounds,
  is_X × wounds for monster / vehicle / character, move × OC, keyword ×
  volume terms, log/sqrt transforms on attacks and damage). Net: 35
  features → 111 features, R² 0.9499 → 0.9617, mean absolute error
  21.96 → 16.95 pts/model. Leaders-only R² 0.9033 → 0.9404. Eldrad-class
  characters (Yvraine, Farseer, Hive Tyrant) now within 5-15 pts of GW.

  Added `FEATURE_FAMILIES` mapping and `compute_family_contributions`
  helper to `code/equation_data_fit.py` so display layers can roll
  per-feature contributions up to per-family bars and sidestep the
  multicollinearity that makes individual coefficients flip signs in
  visually confusing ways (signs survive aggregation, families are
  interpretable). `bake_swegpoints_v1.py` now writes
  `family_contributions_avg` into the JSON payload.

  Removed super-heavy fallback in `bake_swegpoints_v1.py`. Previously
  units above 500 GW points per model fell back to GW's printed cost
  (27 Titans / Knights / Apocalypse pieces). They now go through the
  equation like everything else — predictions carry more uncertainty at
  this weight class but playtesters can field cool stuff at
  math-fitted prices. Removed `--super-heavy-threshold` CLI flag and
  `super_heavy_threshold_pts_per_model` / `super_heavy_fallback` count
  fields from the payload.

  `docs/sweghammer_points.html` rewritten as a single-page-scroll
  playtester handout: sticky top nav, hero with stats grid + math-only
  v1 callout, formula display, family rollup bars, faction multipliers
  grid, methodology section (placed above the unit table so playtesters
  read the "how" before scanning prices), then the existing searchable
  table. `app.py::_render_equation_lite` updated to mirror the same
  family-rollup view in the dashboard.

- **2026-05-24** — **v1.0 release: SwegHammer — Recalibrated.** Track 4
  data-driven equation frozen as a per-unit prices dataset at
  `data/sweg_points_v1.json` (1,483 units priced — 1,456 via the
  equation, 27 super-heavy GW fallback — superseded 2026-05-25). New `code/sweg_points.py`
  loader and `--swegpoints` flag in `scripts/evaluate_vs_meta.py` swap
  the v1 prices into the catalogue. The Streamlit dashboard gained a
  sidebar **Player / Calibration** mode toggle: Player view exposes
  five curated tabs (Home, Unit Browser, Army Compare, Faction
  Overview, The Equation) for hobbyist use; Calibration view keeps the
  existing nine-tab technical dashboard with a new Home banner showing
  headline calibration metrics and a MAE history mini-chart. Cross-
  validation review against the Equilibrium Phase 5 solver lives at
  `docs/SWEG_V1_REVIEW.md` — every top-20 disagreement was traced to a
  known method-bias difference, none required dataset regeneration.
  `code/__init__.py` now exposes `__version__ = "1.0.0"`.

- **2026-05-23** — Equation fit (Track 4) improvements. Regenerated
  `data/equation_vs_meta_snapshot.json` with all 22 factions carrying
  real Warp Friends May 2026 win-rate targets (`APPROX_FACTIONS` now
  empty), activating faction multipliers for all 22 factions in the
  Equation Fit tab (previously only 5 of 22 were real; 17 rode a 1.0×
  no-correction default). Added two interaction features to
  `code/equation_data_fit.py` and `default_feature_specs()`:
  `log(toughness × wounds/model)` and `log(total_wounds)`. Together
  these raise R² from 0.946 to 0.950 and reduce overall price mean
  absolute error from 23.5 to 21.6 points per model, with vehicle mean
  absolute error falling from 41.9 to 37.3. A new "Interactions"
  expander in the Equation Fit tab exposes both features.

- **2026-05-19** — Simulator hot-path performance: three tiers of optimisation
  reduced per-battle wall time from ~117 ms to ~32 ms (73% reduction) on a
  30-battle benchmark across three representative matchups. Changes shipped
  across three commits: Tier 1 added `functools.lru_cache` to the save-
  probability and wound-probability pure functions plus a benchmark harness
  (`scripts/bench_simulator.py`); Tier 2 added an alive-units cache to avoid
  per-phase list rebuilding and vectorised the deep-strike objective scoring;
  Tier 3 added a discretised line-of-sight cache (keyed by 0.5-inch-grid
  endpoint pair + ruin-pass flag, with a terrain-epoch counter to prevent
  garbage-collector identifier reuse), a cover-priority cache (keyed by
  grid-discretised position), a `_unsaved_fraction` cache eliminating
  ~200-combination recomputation, precomputed trigonometric constants for
  the cover-candidate search, and replaced the cover-point search candidate
  list with a running-best comparison that reuses the cover-priority cache
  rather than calling `is_blocked()` separately. Stage 1 work: faster
  calibration iteration cycles.

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

### ~~Points-per-model import fix (Eddie)~~ — closed 2026-05-17

Per Ed's TODO in PROJECT.tex (commit `a0d7702`): the BSData → UnitProfile
pipeline read `points_per_squad` correctly but `points_cost` returned a
Lanchester-derived score, so all sim-side army budgets were wrong-currency.
Resolved in three passes — `a0d7702` made the property prefer GW canonical;
`c084ba0` and the 2026-05-17 mapper-shape fixes (branch
`claude/fixinfequivexplorer`) corrected `min_models` extraction for the
shape-c, leader-plus-body, and cost-tier-implicit squad encodings; stale
balancer overrides anchored to the old basis were dropped. See PROJECT.tex
"Points-per-model cost is imported wrong" item for the per-pass history.

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
