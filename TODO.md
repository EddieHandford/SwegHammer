# Remaining Work — SwegHammer

Pulled from [PROJECT.tex](PROJECT.tex) for quick reference. Compile the
LaTeX for the full picture (vision, math, architecture). This file is
just the unchecked items.

**Tags:** `[E]` Eddie's slice · `[J]` Jake's slice · `[?]` unclaimed

---

## Session pin — 2026-05-14

**Last session ended at:** Charge / Melee / Battleshock / Objectives /
Detachments (partial) / Strategy layer / Role classifier all shipped.
Catalogue now sits at ~1294 units. Detachment scaffolding lives but
only 2 of 10 modifier flags are wired into combat.

**Best next pickup (pick one):**

1. **Wire the remaining 8 detachment flags.** `reroll_hit_ones`,
   `reroll_wound_ones`, `plus_one_to_hit`, `plus_one_to_wound`,
   `plus_one_attack`, `plus_one_save`, `extra_invuln`, `ld_bonus`
   parse and store but don't compose into `Unit.attack()` yet.
2. **Phase E — Stratagems.** One-shot in-phase CP-priced effects.
   Touches activation context + the existing detachment registry.
3. **Recalibrate cross-faction matchups.** Marines vs Orks and Marines
   vs Terminators still flag `[!] IMBALANCED` in `python run.py --cli`.
   Run the balancer over the full catalogue and refresh
   `data/calibrated_points.json`.
4. **Investigate the ±10% mirror-match bias on symmetric terrain.**
   Did not resolve once charge/melee landed; objective-contest jitter
   plus movement-heuristic asymmetries are the most likely cause.

---

## Done since last sweep

- `[x]` **Objective scoring + VP win condition** (Phase 0) — `Objective`
  on `Map`, 5-objective quincunx on every stock map, end-of-round VP
  scoring, win condition rewritten around Primary VP.
- `[x]` **Charge phase** — declaration, 2d6 roll, move into 1"
  engagement (`Battle._do_charge`).
- `[x]` **Melee phase** — `melee_*` fields on `UnitProfile`,
  `Unit.attack(..., mode="melee")`, `Battle._do_fight`, chargers first.
- `[x]` **Battleshock** — Ld + OC on `UnitProfile`, 2d6 vs Ld from
  Round 2 for units below half HP; battleshocked → OC 0 for scoring.
- `[x]` **Role classifier** — `code/roles.py` labels each unit
  SHOOTY / MELEE / DUAL / HORDE / HEAVY / SUPPORT; consumed by the
  charge-desire heuristic and the strategy layer.
- `[x]` **Strategy layer** — `code/strategy.py` picks HOLD / CAPTURE
  / STEAL / ENGAGE / REPOSITION per activation; movement no longer
  marches at the nearest enemy.
- `[x]` **Weapon keywords + FNP** (Phase A2/A3) — Rapid Fire, Melta,
  Ignores Cover, Anti-X, Heavy (parsed, not yet applied), Assault,
  Torrent, Hazardous, Blast, Feel No Pain.
- `[~]` **Detachment rules** (Phase D, partial) — scaffolding +
  5 canonical detachments + 2 live effects (reanimate, enemy Ld
  penalty). 8 of 10 modifier flags still parse but produce no in-game
  effect; see Phase D follow-ups below.

---

## Simulation core (Eddie)

### Phases
- `[E]` **Command phase** — add a `CommandPhase` step at activation
  start; move existing CP bonus logic out of `Battle._run_round`
  into it.
- `[E]` **Movement phase** — segment-vs-impassable-terrain collision
  (currently only the destination is checked, so units can tunnel
  through walls). Fall Back logic still unimplemented (Advance is
  done).

### Detachments (Phase D follow-ups)
- `[E]` **Wire the 8 unwired modifier flags** into `Unit.attack()`
  composition: `reroll_hit_ones`, `reroll_wound_ones`,
  `plus_one_to_hit`, `plus_one_to_wound`, `plus_one_attack`,
  `plus_one_save`, `extra_invuln`, `ld_bonus`.

### Math / catalogue
- `[E]` **Regenerate `BASELINE.md` catalogue table** — points columns
  there are stale since the wound roll landed.
- `[E]` **Recalibrate cross-faction matchups** — Marines vs Orks and
  Marines vs Terminators are flagged `[!] IMBALANCED` in the
  calibration sweep. Phase 3 work.
- `[E]` **Mirror-match terrain bias** — symmetric maps still sit at
  ±10% of 50/50 over 400 battles after the charge/melee/objective
  layers landed. Investigate the residual (objective-contest jitter
  + movement-heuristic asymmetries are the most likely drivers).

---

## Visualization (Eddie / shared)

- `[?]` **PygameRenderer** — third button in `run.py` launcher;
  subscribes to the event stream and paints a live battle in a native
  window. The headless event-stream contract is already in
  `code/events.py`.
- `[E]` **Per-unit cover and terrain overrides** in the Streamlit
  sidebar (current cover flag is army-wide; terrain cover now applies
  per-shot from `Map.cover_at`, but there's no UI override).

### Longer-term
- `[?]` **Army builder UI** — drag-and-drop datasheets, points
  totalled live in the Streamlit app.
- `[?]` **Calibration browser** — view the most recent sweep, drill
  into outlier matchups.

---

## Datasheet ingestion (Jake) — v1 complete

All of the original pickup items shipped under Phase 1.6:

- `[x]` **Source format** — BSData WH40k 10e (pinned to `v10.6.0`)
- `[x]` **Target schema** — `MappedUnit` lowers to `UnitProfile`
- `[x]` **Loader** — `code/bsdata/loader.py` merges
  `parsed.json` + `data/overrides.json` at import time
- `[x]` **Multi-weapon flattening** — best-legal-loadout optimiser
  by expected damage through baseline Marine armour; alternates kept
  on `MappedUnit.loadout`
- `[x]` **Melee profile extraction** (Phase B follow-up) — 1261/1291
  enabled units carry a usable melee profile
- `[x]` **Audit tool** — `python -m code.bsdata.audit` flags
  unmapped codices and stat drift between successive parses

### Open follow-ups
- `[J]` **Fall-back to melee weapons for ranged-less units** — ~30
  units still flagged `enabled: false` because the mapper couldn't
  resolve a melee profile either.
- `[J]` **Per-squad vs per-model `health` aggregation** — currently
  per-model wounds, but multi-model squads still emit per-model
  damage downstream.

---

## Documentation

- `[E]` Update PROJECT.tex when the items above land. The PDF is
  committed for non-LaTeX readers; rebuild with `pdflatex PROJECT.tex`.
