# Remaining Work — SwegHammer

Pulled from [PROJECT.tex](PROJECT.tex) for quick reference. Compile the
LaTeX for the full picture (vision, math, architecture). This file is
just the unchecked items.

**Tags:** `[E]` Eddie's slice · `[J]` Jake's slice · `[?]` unclaimed

---

## Session pin — 2026-05-13

**Last session ended at:** Phase B shipped — Streamlit "Watch a battle"
replay tab with matplotlib scrub-through, three stock maps, LoS gating
on obscuring terrain, terrain-aware cover, move-then-shoot sub-phase
refactor, nearest-enemy movement targeting.

**Best next pickup (pick one):**

1. **Phase C — Pygame live demo.** Third button in the launcher, opens
   a native window, animates one battle in real time by subscribing to
   the existing event stream. Headless core already supports it; this
   is just a new renderer.
2. **Recalibrate cross-faction matchups.** Marines vs Orks and Marines
   vs Terminators flag `[!] IMBALANCED` in the sweep. Regenerate
   `BASELINE.md`, then tune. Phase-3 work in the original roadmap.
3. **Investigate the ±10% mirror-match bias on symmetric terrain.**
   May resolve once charge/melee phases land — depends on whether
   that's worth doing alone.

---

## Simulation core (Eddie)

### Phases
- `[E]` **Command phase** — add a `CommandPhase` step at activation
  start; move existing CP bonus logic out of `Battle._run_round`
  into it.
- `[E]` **Movement phase** — objective-aware play, kiting when
  outranged, segment-vs-impassable-terrain collision (currently only
  the destination is checked, so units can tunnel through walls).
- `[?]` **Movement phase** — Advance roll (`+d6`, no shooting) and
  Fall Back logic.
- `[?]` **Charge phase** — declaration, `2d6` roll, move into base
  contact; "engaged in melee" flag that suppresses shooting next
  turn.
- `[?]` **Melee phase** — `attacks_melee` and `weapon_skill` on
  `UnitProfile`; resolve units in fight-priority order
  (chargers first).
- `[?]` **Morale / battleshock** — `leadership` on `UnitProfile`;
  decide between classic morale and 10e battleshock and document the
  choice.

### Math / catalogue
- `[E]` **Regenerate `BASELINE.md` catalogue table** — points columns
  there are stale since the wound roll landed.
- `[E]` **Recalibrate cross-faction matchups** — Marines vs Orks and
  Marines vs Terminators are flagged `[!] IMBALANCED` in the
  calibration sweep. Phase 3 work.
- `[E]` **Mirror-match terrain bias** — terrain-symmetric maps now
  sit at ±10% of 50/50 over 400 battles. The residual probably comes
  from the focus-fire / movement heuristic on asymmetric kill-rate
  pockets. Investigate once charge/melee phases land (they may change
  the dynamics enough that this resolves itself).

### Terrain
- `[?]` **Objective markers** on `Map` (currently only deployment
  zones).

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

## Datasheet ingestion (Jake)

- `[J]` **Pick a source format** — Wahapedia CSV / JSON dump,
  BattleScribe XML, or hand-rolled YAML.
- `[J]` **Define a target schema** that maps cleanly onto
  `UnitProfile`. Note: `UnitProfile` now has `strength`, `toughness`,
  `move`, `range_inches` in addition to the original fields.
- `[J]` **Build a loader** that yields `UnitProfile` instances, with
  a round-trip test against a hand-coded expected unit (e.g.
  Intercessor squad).
- `[J]` **Multi-weapon flattening** — decide how units with multiple
  weapons (bolter + chainsword) are represented: single averaged
  profile vs. list of weapons resolved separately.

---

## Documentation

- `[E]` Update PROJECT.tex when the items above land. The PDF is
  committed for non-LaTeX readers; rebuild with `pdflatex PROJECT.tex`.
