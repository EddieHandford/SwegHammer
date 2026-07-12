# Terrain and line of sight — build specification (Phase 1 investigation output, 2026-07-12)

This document is the Phase 1 deliverable of the terrain-and-line-of-sight program
registered in `docs/DECISION_LEDGER.md`. It is a specification grounded in
**measurement**, produced by the instrument `scripts/diag_los_blocked.py`, not a
plan written from the prior mental model. Its first job is to correct that mental
model, because the measurement overturns the premise the program was opened on.

Read alongside: `docs/TERRAIN_REALISM_PROPOSAL.md` (the make-terrain-real proposal
this revises), `docs/THREAT_LAYER_PROPOSAL.md` (the artificial-intelligence
positioning layer, where the durability hypothesis actually lives), and the
decision-ledger entries "MAKE TERRAIN REAL", "Terrain collision, ROUTING shape",
and "TERRAIN HYPOTHESIS REFUTED (THIRD CONFIRMATION)".

---

## 1. Headline finding — the premise correction

The make-terrain-real proposal and the decision-ledger entry that opened this
program both assert, in as many words, that "shooting has **no** line of sight ...
walls never block a shot." **That is false on the current code, and has been since
2026-05-16.** The instrument measures the opposite:

- **The simulator already blocks the majority of candidate shots by line of
  sight.** Across eight fixed-seed battles on the production evaluation maps, the
  simulator's own visibility check denied **73.0 percent** of in-range
  attacker-to-target candidate pairs (authoritative aggregate from the built-in
  `TERRAIN_LOS_STATS` counter; per-faction denial ran from 28 percent for Adeptus
  Mechanicus to 75 percent for Aeldari). A gun whose every in-range candidate is
  denied fires nothing that activation (`code/simulator.py` line 15455,
  `if not candidates: return`). Walls prevent shots today.
- **Resolved direct-fire shots already respect Obscuring geometry.** Of shots that
  actually fired, only **4.4 percent** of direct-fire shots had a shot line that a
  strict whole-footprint Obscuring reading would occlude — and a decomposition
  showed that residual is 0.5-inch-grid quantization, not a rules gap (the
  simulator's own engine, run on the same exact positions, agreed the shot was
  clear). Indirect-fire shots showed 94 percent occluded, which is correct: they
  are exempt from visibility and take the shooting-blind penalty.

The line-of-sight target-legality half of the proposed build **already exists,
is default-on, and is faithful.** It is wired at `code/simulator.py` line 15374 to
15384 (the default candidate filter calls `Map.has_line_of_sight`) and, byte
identically, through the shared substrate at lines 15359 to 15373 when
`SWEG_TERRAIN_LOS` is set. The visibility engine itself
(`code/map.py` `Map.has_line_of_sight`, lines 163 to 225) implements the cited
10th-edition Ruins and Woods rules exactly, including the wholly-within see-out
allowance and the aircraft and towering exceptions.

**Therefore a gate named "shots require line of sight unless indirect fire" would
be a near no-operation: the simulator already does this.** The genuinely-open
resolution gap is narrower and is about **cover**, specified in section 4.

---

## 2. What the instrument measured (the fidelity-gap quantification)

Run: `PYTHONHASHSEED=0 python -m scripts.diag_los_blocked` — eight mixed-faction
archetype battles at 2000 points, single battles, no evaluation, byte-identical to
an unpatched run (the wrappers only read state and delegate). Two map passes: the
production `_competitive_terrain` geometry and the sourced dense Games Workshop
Pariah Nexus layouts (`SWEG_TERRAIN_DENSE`, built in process).

| Reading | Production maps | Sourced dense maps |
|---|---|---|
| Candidate-stage visibility denial (aggregate) | **73.0 %** | 64.2 % |
| Resolved direct-fire shots blocked, strict Obscuring reading | 4.4 % (quantization) | 6.9 % |
| Resolved indirect-fire shots blocked (exempt, expected) | 94.1 % | 85.7 % |
| Flat cover tax fired (share of resolved shots) | 48.9 % | 37.6 % |
| Angle-aware cover would apply (approximate real reading) | 56.7 % | 53.9 % |
| False cover (tax fired, shooter in the same piece as target) | 2.3 % | 2.1 % |
| Missed cover (real intervening cover the position-only lookup ignores) | 10.1 % | 18.4 % |

Three conclusions fall out:

1. **Visibility blocking is real and substantial** — this refutes the "no line of
   sight" premise decisively.
2. **Terrain density is already faithful.** The production maps block *more* than
   the sourced dense Games Workshop layouts (73.0 versus 64.2 percent), because the
   production layout carries about seventeen small pieces where the sourced layout
   carries about ten large ones. The published Games Workshop Pariah Nexus
   Tournament Companion standard is twelve pieces on a 44 by 60 inch board (four of
   roughly six by four inches, two of roughly ten by five inches, six of roughly
   twelve by six inches — the large blockers are bigger than either simulator
   layout, but fewer, so the raw candidate-denial fraction is comparable). This is
   the **third independent confirmation** of the density verdict already in the
   ledger ("TERRAIN HYPOTHESIS REFUTED"). Density is not the under-faithful axis.
3. **The cover model is roughly right in magnitude but position-only.** The flat
   tax fires on 48.9 percent of shots — closely matching the "roughly forty-six
   percent symmetric cover tax" the earlier audit recorded and the proposal cites.
   The angle-independence *error* is small: false cover is 2.3 percent (the flat
   tax grants cover where a shooter standing in the same piece means there is no
   real occlusion). The larger discrepancy is *missed* cover — 10 percent of shots
   where terrain genuinely intervenes on the shot line but the target's own
   position is in the open, so the position-only lookup grants nothing. Net, the
   simulator slightly **under-grants** cover relative to an angle-aware reading
   (48.9 versus 56.7 percent).

---

## 3. What is already faithful or already rejected — do not rebuild

- **Line-of-sight target legality** (`Map.has_line_of_sight`, wired in
  `_do_shoot`): present, default-on, faithful. Citations `terrain.ruin_infantry_los`
  and `simulator.towering_los` in `data/rule_citations.d/core_terrain_ruins.json`;
  the gate route is `simulator.terrain_los_gate` in
  `data/rule_citations.d/terrain_realism.json`.
- **Terrain density**: the sourced Games Workshop layouts already exist behind
  `SWEG_TERRAIN_DENSE` (`code/maps.py` `_dense_competitive_terrain`, citation
  `terrain.competitive_density`) and were screened at 2026-07-02 as a metric wash
  (Chaos Knights moved minus 0.4 at sample size twenty, noise). The instrument here
  confirms the geometry reason: density is not the gap. **Do not re-propose a
  layout upgrade as a fix.** Keep the dense layouts as a faithful option.
- **Movement wall collision**: both shapes were built and rejected empirically in
  2026-07-09 (`SWEG_TERRAIN_COLLISION` clamp shape and the route-around rebuild) —
  gated plus 2.24 and plus 4.59 respectively, with Imperial Knights and Chaos
  Knights driven decisively below their real rates, because movement-blocking
  terrain without terrain-aware deployment and approach planning is a pure detour
  tax on ground forces (the artificial-intelligence cannot yet route around ruins).
  The substrate (`code/sim/los.py` `path_blocked` and `wall_clamp`) is retained but
  the gates stay off. **Reopen only after the positioning layer provides
  deployment-and-approach planning.**

---

## 4. The genuinely-open resolution change — angle-aware Benefit of Cover

Because the visibility half is already shipped, the resolution change this program
should actually build is the **cover** half the proposal names in one clause
("Benefit of Cover replaces the flat tax where the real rule grants it"). Proposed
gate name: **`SWEG_COVER_ANGLE`** (default-off, byte-identical off). It replaces the
position-only cover lookup with an attacker-relative one.

### The real rule being restored (citable, verbatim)

- **Determining visibility** (Wahapedia core rules,
  `https://wahapedia.ru/wh40k10ed/the-rules/core-rules/`): "Warhammer 40,000 uses
  true line of sight to determine visibility between models." A model is *visible*
  "If any part of another model can be seen from any part of the observing model";
  a model is *fully visible* if "every part of another model that is facing the
  observing model can be seen ... without any other models or terrain features
  blocking visibility to any of those parts."
- **Benefit of Cover** (Wahapedia core rules; datacard.app 10th-edition reference):
  "Each time a ranged attack is allocated to a model that has the Benefit of Cover,
  add 1 to the saving throw made for that attack (excluding invulnerable saving
  throws)." And the pip cap: "models with a Save characteristic of 3+ or better
  cannot have the Benefit of Cover against attacks with an Armour Penetration
  characteristic of 0." The angle condition, for area terrain such as Ruins and
  Woods, is that the model is within the terrain feature and at least partially
  obscured from the firing model, **or** the terrain feature lies between them.
- **Ruins and Woods as sight and cover terrain**: already captured verbatim in
  `data/rule_citations.d/core_terrain_ruins.json` (`terrain.ruin_infantry_los`,
  `simulator.towering_los`). Note that in 10th edition the word "Obscuring" is not a
  standalone core trait — the Pariah Nexus Ruins carry the "cannot see over or
  through this terrain feature" rule, which is the functional Obscuring behaviour,
  plus the Area rule that grants Benefit of Cover to models within.

New citation key to add when the gate is built: `simulator.benefit_of_cover_angle`
(scope `army-wide`), quoting the Benefit of Cover rule and its area-terrain angle
condition.

### Exact code points that change

1. **`code/map.py` — a new attacker-aware cover query.** Add
   `cover_between(attacker_pos, target_pos, keywords...)` beside the existing
   `cover_at` (lines 140 to 161). It returns Benefit of Cover when the target
   stands within a cover-granting piece the **attacker is not also within**, or a
   cover-granting piece lies on the shot segment between them. `cover_at` stays for
   any position-only caller; the new query is the single shared geometry helper
   (see section 5). Two sub-fixes fold in here:
   - **Woods currently grant no cover.** `cover_at` ranks `OBSCURING` in its
     priority table but `_do_shoot` grants Benefit of Cover only for
     `LIGHT_COVER`, `HEAVY_COVER`, `RUIN` (`code/simulator.py` line 15731) —
     so a unit standing in Woods gets none, contrary to the 10th-edition Area rule.
     The new query includes `OBSCURING` in the cover-granting set.
   - The 3+ save pip cap already lives in `save_probability`
     (`code/units.py` lines 361 to 394) and is unchanged.
2. **`code/simulator.py` `_do_shoot` — the cover application** (lines 15728 to
   15736). Replace `cover_type = self.map.cover_at(math_target.position)` with the
   attacker-aware query keyed on `attacker.position` and `math_target.position`.
   The stratagem and ability cover grants immediately below (Go To Ground,
   Smokescreen, Knight Defender Selfless Protector, lines 15737 to 15757) are
   independent of terrain and are untouched.
3. **`code/simulator.py` Fire Overwatch — the same cover application** (lines 16723
   to 16729). The identical substitution, keyed on the overwatching unit's position.
4. **No change** to the candidate filter (lines 15374 to 15384) or to
   `Map.has_line_of_sight`: visibility is already faithful.

Measured expectation for this gate, stated in advance and honestly: net it grants
**slightly more** cover (the missed-intervening-cover cases outweigh the false-cover
cases, 10 versus 2 percent), so on average incoming ranged damage falls a little,
weighted toward whichever side is advancing across open ground under fire — which
is the fragile army. Direction is therefore *plausibly* toward the two poles
closing (Astra Militarum up, gunline over-poles down), but the magnitude is small
and the sign is **not** guaranteed: durable armies also stand in cover, and the
durability wall has absorbed every play-quality improvement so far.

---

## 5. Artificial-intelligence consequence — one geometry, both consumers

The positioning layer must read the **same** cover-and-occlusion geometry the
resolution uses, or it plans against a board the resolution does not enforce. Today
there are two separate cover notions: the resolution's `cover_at`, and the
threat-projection field's cover-attenuation term in `code/strategy.py` (gate
`SWEG_THREAT_CHARGE`, citation `simulator.threat_projection_charge`), whose version
one deliberately uses the flat cover-attenuation form and **no** occlusion, per the
honest caveat in `docs/THREAT_LAYER_PROPOSAL.md` section on refinement 2.

The rule for this program: when `SWEG_COVER_ANGLE` lands, the threat field's ranged
attenuation must call the **same** `cover_between` helper (and, for the occlusion
term the threat layer's later consumers want, the same `code/sim/los.has_los`), so
planning and resolution agree. One function, both consumers. This is the substrate
alignment the make-terrain-real Stage T4 and the threat-layer refinement 2 both
already ask for; this specification names the function.

**Crucially, the durability hypothesis lives on this side, not in resolution.** The
make-terrain-real proposal hypothesised that "true line of sight is how fragile
armies survive shooting." The instrument shows the *geometry* is already present:
fragile units *can* be made non-targetable behind the existing blocking terrain.
Whether they *are* is an artificial-intelligence positioning question — does the
mover hide its squishy objective-holders behind the ruins the resolution already
respects? That is the threat-layer move-intent consumer (consumer two in
`docs/THREAT_LAYER_PROPOSAL.md`), currently parked behind a movement-resolution
worktree. **The single highest-value terrain-adjacent lever is not a resolution
gate at all; it is teaching the positioning layer to consume the occlusion geometry
that already exists.**

---

## 6. Phasing

1. **Phase 1 (this document): investigation and instrument.** Done. Premise
   corrected; `scripts/diag_los_blocked.py` committed as the standing
   saturation-quantification instrument.
2. **Phase 2: the cover-fidelity gate `SWEG_COVER_ANGLE` at the current maps.**
   Small, self-contained, one subsystem (section 4). Screen full-frame. This is the
   only genuinely-open *resolution* change.
3. **Phase 3: positioning consumes the geometry.** The threat-layer move-intent and
   arrival-placement consumers reading the shared occlusion-and-cover geometry —
   owned by `docs/THREAT_LAYER_PROPOSAL.md`, cross-referenced here, gated
   separately, and blocked on the movement-resolution worktree. This is where the
   durability-pole hypothesis is actually tested.
4. **Not a phase: a layout upgrade or a movement-collision gate.** Both are settled
   (section 3). Keep `SWEG_TERRAIN_DENSE` available; keep the collision gates off.

---

## 7. Falsifiers and re-anchor protocol

- **Byte-identical off** for `SWEG_COVER_ANGLE`: the position-only `cover_at` path
  must run unchanged when the gate is unset (zero flipped games in a paired
  common-random-number validation), per `docs/EVAL_PROTOCOL.md`.
- **The durability-wall poles are the registered watch-list.** Judge the cover gate
  by whether the two remaining poles (Astra Militarum under, Death Guard over, with
  Imperial Knights and Chaos Knights the durable over-pole cluster) move toward
  their real Warp Friends rates, read on the symmetrized column
  (`scripts/diag_frame.py`), **not** the headline mean absolute error alone. If the
  poles do not move, the cover refinement is a fidelity-correct wash and should be
  adopted on faithfulness grounds only, exactly as the density and ability-fidelity
  batches before it.
- **The instrument is the geometry falsifier.** `scripts/diag_los_blocked.py`
  re-run after the gate must show the flat-tax cover rate rising toward the
  angle-aware rate (48.9 toward 56.7 percent) and the false-cover rate falling
  toward zero, on both map passes. If it does not, the gate does not implement the
  rule it claims.
- **Re-anchor protocol — this is a frame change.** A cover-model change touches
  every matchup's shooting arithmetic, so adoption requires a fresh full sample-size
  eighty anchor and re-validation of every held cover-interacting lever whose screen
  predates it (Smokescreen `SWEG_SMOKESCREEN`, Go To Ground, Knight Defender cover
  `SWEG_IK_DEFENDER_COVER`, Death Guard Tank Hunters, and the `SWEG_TERRAIN_DENSE`
  option), per the frame-change discipline in `docs/EVAL_PROTOCOL.md`. Batch the
  screen with a single re-anchor.

---

## 8. The honest summary for the owner

The terrain-and-line-of-sight program was opened as "the last big unfaithful
subsystem." The measurement says the subsystem is **substantially faithful
already**: line-of-sight blocking is real (73 percent candidate denial) and
resolved-shot faithful (4 percent quantization residual on direct fire), terrain
density is at or above the real competitive standard, and movement collision is a
settled rejection. The one genuinely-open *resolution* refinement is angle-aware
Benefit of Cover, and the instrument sizes it as small and uncertain in sign. The
large prize the proposal hoped for — fragile armies surviving by hiding — is real,
but it is an **artificial-intelligence positioning** prize (the threat layer
consuming the geometry that already exists), not a resolution-rules prize. This
specification recommends building the small cover gate on its own faithfulness
merits and re-pointing the durability hypothesis at the positioning layer.
