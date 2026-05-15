# Remaining Work — SwegHammer

Pulled from [PROJECT.tex](PROJECT.tex) for quick reference. Compile the
LaTeX for the full picture (vision, math, architecture). This file is
the unchecked items only.

**Tags:** `[E]` Eddie's slice · `[J]` Jake's slice · `[?]` unclaimed

---

## Session pin — 2026-05-15

**Last session ended at:** Goals A/B/D substantially shipped this session
— 9 of 10 faction army rules in, ~25 stratagems / 25 detachments / 5
enhancements / 4 CP-discount HQs / 5 core 10e rules (Look Out Sir, Lone
Op, Deadly Demise, Fall Back, Desperate Escape). Equilibrium solver Phases
1–6 complete plus MC-driven C1 balance pass + cross-validation.

**Current state:**
- MAE 5.48 at N=30 / 7.01 at N=200 (target ≤ 2.0)
- 122/122 rule citations verbatim from Wahapedia
- 469 unit tests green
- 5-tab Streamlit dashboard (Statistics / Watch a battle / Efficiency /
  Equilibrium / Compare to SwegHammer)
- Catalogue: 1308 BSData units + overrides + 27 Drukhari now mapped

**Blocker.** `UnitProfile.points_cost` returns Lanchester-derived score,
not GW per-model cost. Ed's TODO (PROJECT.tex `\eddie`) — paused
cost-anchored work until landed.

**Best next pickup (pick one):**

1. **[E] Points-per-model import fix.** The bottleneck. Once landed, the
   Sweg-balancer overrides need re-anchoring and the Compare view's
   mispricing numbers become trustworthy.
2. **[?] Marines Oath of Moment retry.** Three attempts have regressed
   MAE (Marines push from baseline to +5pt). Needs a damped version
   (re-roll 1s only, not full re-roll) or concurrent re-pricing.
3. **[?] Widen Phase 4 calibration anchor set.** Adds units with diverse
   mobility (Spectres, Stormboyz, Acolytes) so `w_move` and
   `w_infiltrator` are no longer under-identified.

---

## Open follow-ups by area

### Faction army rules (Goal A — 9 of 10 shipped)
- `[?]` **[NEEDS RETRY] Marines — Oath of Moment + Combat Doctrines.**
  Three attempts; all regressed MAE because they buff Marines by ~5pt
  without concurrent re-pricing. Tasks #115, #116.
- `[?]` **[NEEDS RETRY] Aeldari Battle Focus strategy bias.** ASURYANI
  advance branch reverted — Aeldari at +13.9 are over-strong; making them
  more active worsens MAE. Land after points re-balance. Task #109.
- `[?]` **[NEEDS RETRY] Drukhari mapper rewrite.** Parser fix shifted the
  Aeldari pool composition (+0.71 MAE regression in isolation). Needs C1
  cost rebase to absorb the redistribution. Task #150.

### Cost model (Goal C, blocked on points-per-model fix)
- `[E]` **Points-per-model import fix** — see PROJECT.tex
  `\eddie` TODO. Audit `code/bsdata/mapper.py` + `loader.py`. The
  Lanchester-derived fair cost has no signal until the printed-cost
  baseline is correct.
- `[J]` **Iterative MC bisection per-faction** post-fix — current pass
  was single-shot ±10% on 10 units; needs convergent loop until MAE
  plateaus.

### Tactical utility (Goal D)
- `[?]` **Widen calibration anchor set** — add Spectres / Stormboyz /
  Acolytes / GSC Patriarchs so `w_move`, `w_oc`, `w_infiltrator`,
  `w_deep_strike` are no longer calibrated to 0.

### Sim engine open items
- `[E]` **Per-segment movement collision** — currently only the
  destination is checked, so units can tunnel through walls.
- `[E]` **Regenerate `BASELINE.md` catalogue table** — points columns
  stale since the wound roll landed.

### Visualisation / app
- `[?]` **PygameRenderer** — third button in `run.py` launcher;
  subscribes to the event stream and paints a live battle in a native
  window. Headless event-stream contract already in `code/events.py`.
- `[E]` **Per-unit cover and terrain overrides** in the Streamlit
  sidebar (current cover flag is army-wide).
- `[?]` **Army builder UI** — drag-and-drop datasheets, points
  totalled live.
- `[?]` **Calibration browser** — view most recent eval sweep, drill
  into outlier matchups.

### Datasheet ingestion
- `[J]` **Fall-back to melee weapons for ranged-less units** — ~30
  units still flagged `enabled: false`.
- `[J]` **Per-squad vs per-model `health` aggregation** — currently
  per-model wounds, but multi-model squads still emit per-model
  damage downstream.
- `[J]` **Wraithguard / Wraithblades `min_models` fix** — currently
  parsed as 1 (should be 5); makes their per-model price look like a
  full squad cost. Separate from the Lanchester-vs-GW points-cost bug.

### Documentation
- `[E]` Update PROJECT.tex when items above land. The PDF is committed
  for non-LaTeX readers; rebuild with `pdflatex PROJECT.tex`.
