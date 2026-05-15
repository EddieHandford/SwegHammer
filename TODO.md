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
2. **[J] Deepstrike AI overhaul** (see Sim engine open items below).
   Strategic, not blocked on Ed.
3. **[J] Renderer: real-world base sizes** — circles / rectangles / ovals
   sized to actual Wahapedia model footprints (see Visualisation below).
   Quick UX win, not blocked on Ed.

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
- `[J]` **Dual headline metric** — split MAE-vs-real-meta from
  MAE-vs-Sweg-balanced-meta. The "minimal rule changes" design
  (alternating activation, CP-for-fewer-units) creates a structural
  floor on vs-real-meta MAE that can't be closed by adding more rules.
  Sweg-balanced-meta is what the calibration should actually converge
  toward. **Hold this until Ed's points-cost fix lands** — without GW-
  anchored points neither metric is honest. Spec lives in `ROADMAP.md`
  Goal C future considerations.

### Tactical utility (Goal D)
- `[?]` **Widen calibration anchor set** — add Spectres / Stormboyz /
  Acolytes / GSC Patriarchs so `w_move`, `w_oc`, `w_infiltrator`,
  `w_deep_strike` are no longer calibrated to 0.

### Sim engine open items
- `[J]` **Deepstrike AI overhaul.** Current behaviour brings units in
  one-at-a-time across rounds, low impact. Real-tournament deepstrike
  thinking:
  - **Massed arrival**: if multiple units can drop, coordinate them
    into the same round on the same flank — 4 units arriving together
    overwhelm the defending fire; 1 unit per round gets stripped.
  - **Tempo cost of staying off-table**: a unit in reserves contributes
    zero VP and zero damage. Holding past T3 is usually wrong unless
    the late-turn objective grab is the explicit play.
  - **Late-game objective steal**: T4/T5 deepstrikes should target
    enemy/contested objective markers, not maximum-threat enemy units.
  - **Confirmed**: arriving units CAN shoot and charge the turn they
    land (10e rule, our sim already allows this — only the move sub-
    phase is skipped). No engine change needed here, just AI.
  Implementation lives in `code/simulator.py:_arrive_from_reserves`
  and the strategy layer that picks DS targets.
- `[?]` **Transports (Embark / Disembark / Firing Deck).** Not currently
  modelled — confirmed by grep returning no matches. Big surface area;
  Marines (Rhinos / Repulsors / Impulsors), T'au (Devilfish), Custodes
  (Caladius), Aeldari (Wave Serpents) all rely on transports for 6"+
  pre-move + Firing Deck shooting. Direction-of-MAE will buff vehicle-
  mobility factions, so wait until after Ed's points fix + a calibration
  pass before landing, otherwise it'll just push T'au further off
  baseline.
- `[E]` **Per-segment movement collision** — currently only the
  destination is checked, so units can tunnel through walls.
- `[E]` **Regenerate `BASELINE.md` catalogue table** — points columns
  stale since the wound roll landed.

### Visualisation / app
- `[J]` **Real-world base sizes in the renderer.** Pull canonical base
  dimensions from Wahapedia / GW datasheets and draw shapes
  proportionally. Three shape families:
  - **Circles** — INFANTRY / most CHARACTERs. Real diameters: 25mm
    (cultists), 28mm (most), 32mm (Marines), 40mm (Terminators / big
    infantry), 50mm (heroes), 60mm (Riptide-sized), 80–170mm (monsters
    / dreadnoughts).
  - **Rectangles** — most VEHICLEs. Reference: ~6×3.5" footprint
    (Rhino-sized) but variable per-datasheet; Repulsor / Predator
    larger, Razorback smaller. Source from Wahapedia "base size" field
    or hand-curate from datasheet images.
  - **Ovals** — flying / monstrous units with elliptical bases. 60×35mm,
    75×42mm, 105×70mm, 130×85mm, 170×105mm are the GW standard sizes.
  Field `base_shape` and `base_dimensions` on UnitProfile; mapper
  pulls from BSData if available, else hand-override in
  `data/overrides.json`. Renderer (`code/renderer.py:render_frame`)
  picks the right matplotlib patch (`Circle` / `Rectangle` /
  `Ellipse`) and scales radius / width / height from world inches.
  Default fallback retains current shape variety map.
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
