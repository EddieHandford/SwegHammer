# Generalize the 10e Damaged-bracket (Objective Control + Hit penalty) to every model

**Status:** plan-first, watchdog-greenlit (2026-06-05). No build until the watchdog/user
reviews this plan. Stage 1 (this branch). This is a Stage-1 simulator-fidelity change.

## Goal (plain language)

Real 10th-edition datasheets give big models a **"Damaged: 1-X wounds remaining"**
ability that degrades the model's stats once it drops to low wounds. The two
effects that matter for our metric are **subtract N from Objective Control** and
**subtract 1 from the Hit roll when this model attacks**. The simulator currently
models this rule for **Imperial / Chaos Knights only** — `_effective_oc`
(`SWEG_DMGOC`, wave 85) and the `SWEG_DMGHIT` block in `units.attack()` (wave 188),
both faction-gated with thresholds derived from an objective-control / health
heuristic.

The wave-190b even-handedness audit (task #74) found this is a **near-universal**
rule: **94 datasheets across 25 of 31 faction files** carry the offensive Hit
penalty, and the Objective-Control penalty is similarly widespread. Imperial +
Chaos Knights are only **6 of those 94**. Modelling it Knight-only is a
**faithful-but-partial** implementation that biases the simulator toward degrading
only the Knight's damaged-state offense and never its durable opponents' — a small
bias in the metric-favourable direction.

This plan **data-drives the damaged bracket from BSData for every unit that has
one** and applies the Objective-Control + Hit penalty universally, replacing the
hardcoded Knight-only logic. It is faithful by construction (it models a real rule
that is currently under-applied), **even-handed**, and **touches both poles** of
the residual: it degrades the over-shooters' damaged big models (Custodes
dreadnoughts ×6, T'au Stormsurge / Riptide ×6, World Eaters ×3, Thousand Sons ×4)
**and** the under-shooters' durable vehicles (Adeptus Mechanicus ×3, Necrons). The
net metric effect is unknown by design and is measured behind an environment gate.

Verbatim anchor (non-Knight) — **T'au Stormsurge**: *"While this model has 1-5
wounds remaining, subtract 3 from this model's Objective Control characteristic,
and each time this model makes an attack, subtract 1 from the Hit roll."* That is
the identical combined bracket the sim already models, Knight-only, across the two
existing gates.

## Why this is not metric-tuning

The win-rate-gap-is-fidelity ruling forbids re-fitting stats to move the metric.
This is the opposite: it completes a **real, cited 10e rule** that is currently
applied to 6 of ~94 datasheets, sourcing the per-unit data from BSData (rule 7).
The metric moves only as a consequence of higher fidelity, in whichever direction
the faithful rule pushes it. The wave-152 "frozen-under / inseparable" finding said
the headroom needs a *uniform faithful change touching both poles* — this is
exactly that shape.

## Current state (what exists, what is missing)

- `code/simulator.py:_effective_oc` (~1100): Knight-gated OC reduction, thresholds
  Armiger 1-5/−3, Questoris 1-9/−5, Dominus 1-10/−5, derived from `oc`/`health`.
  Gate `SWEG_DMGOC` (default ON). Cited `simulator.damaged_objective_control_bracket`.
- `code/units.py:attack()` (~1998): Knight-gated `−1` to Hit when
  `current_health <= threshold`, same heuristic. Gate `SWEG_DMGHIT` (default ON).
  Cited `simulator.damaged_hit_bracket`.
- `code/bsdata/mapper.py`: **does not extract any Damaged bracket** (grep clean);
  `parsed.json` carries flat stats only (0 "damaged" references). The bracket lives
  in the BSData abilities text and is unparsed.

So the damaged-bracket **data** is the genuinely new work; the **application**
sites already exist and only need to be made data-driven.

## Staged implementation (each stage independently testable; OFF reproduces 5.76)

**Stage 0 — Pin baseline.** OFF N=80 = gated 5.76 (current HEAD with `SWEG_DMGOC`
+ `SWEG_DMGHIT` Knight-only default-ON); `pytest -q` green count; `audit_rules`
clean; git-snapshot `parsed.json`.

**Stage 1 — Mapper extraction (DATA ONLY).** In `code/bsdata/mapper.py`, parse each
unit's `Damaged:` ability into a structured `damaged_bracket` on `MappedUnit`:
`{threshold_hi: int, oc_penalty: int, hit_penalty: int}` (None when the unit has no
bracket). Regexes, anchored to avoid the wave-190b conflation:
- wound range: `While this model has 1-(\d+) wounds remaining` → `threshold_hi`.
- OC penalty: `subtract (\d+) from this model'?s Objective Control` → `oc_penalty`
  (the model's **own** OC, not an aura).
- Hit penalty: the **offensive** form only —
  `this model makes an attack, subtract 1 from the Hit roll` → `hit_penalty = 1`.
  Explicitly **exclude** the defensive form (`attack targets that unit ... subtract
  1 from the Hit roll`), which is a different rule (the de-conflation the audit
  already proved necessary).
- Move / Attacks degradation that some brackets also carry are **out of scope for
  v1** (the sim models only OC + Hit today); record how many units carry a
  Move/Attacks-only bracket so the omission is explicit, not silent.
Serialize additively to `parsed.json`. Verify: every pre-existing key bit-identical,
the only new key is `damaged_bracket`; regenerate twice → empty `git diff`
(determinism; do not add `sort_keys`). **Record coverage**: how many units get a
bracket, split OC-only / Hit-only / both, vs the audit's ~94 offensive-hit count
(this is the cross-check that the extraction is complete, not a silent under-count).

**Stage 2 — Plumb to `UnitProfile` (DATA ONLY, gate-inert).**
- `code/bsdata/loader.py`: `CatalogEntry.damaged_bracket` (default None); `from_dict`;
  override-merge replacement allowed (so `overrides.json` can correct a mis-parse).
- `code/units.py`: `UnitProfile.damaged_bracket` as a hashable tuple
  `(threshold_hi, oc_penalty, hit_penalty)` or `None` (keeps the frozen dataclass
  `lru_cache`-able); `_build_catalog` stamps it. OFF N=80 == 5.76.

**Stage 3 — Data-driven application (BEHAVIOURAL, gated `SWEG_DMGBRACKET`).**
- `_effective_oc`: when `SWEG_DMGBRACKET` is ON **and** `profile.damaged_bracket` is
  present, apply its `oc_penalty` at its `threshold_hi` to **any** unit (no faction
  gate, no heuristic). When the new gate is OFF, the existing Knight-only
  `SWEG_DMGOC` path runs verbatim.
- `units.attack()` damaged-hit block: same shape — data-driven `hit_penalty` for any
  unit when `SWEG_DMGBRACKET` is ON; the Knight-only `SWEG_DMGHIT` path when OFF.
- The wave-85 / wave-188 Knight-only gates **remain the interim default-ON** (per the
  watchdog: do not re-gate them off — the generalization rides its **own** gate for a
  clean A/B; once `SWEG_DMGBRACKET` is flipped on it supersedes them for the Knights
  too, so guard against double-application — the generalized path must REPLACE, not
  stack with, the Knight-only path when both would fire).

**Stage 4 — Citation + audit.** Add one citation `simulator.damaged_bracket` (the 10e
datasheet "Damaged:" ability pattern; verbatim Knight Paladin + T'au Stormsurge
examples; scope `keyword-gated` / per-datasheet). Per-unit thresholds/penalties are
BSData-sourced **data** (rule 7), so no per-unit citations are required — the gate is
cited once and the data carries itself. Register the key in
`scripts/audit_rules.py:SIMULATOR_RULE_KEYS`. Run `python -m scripts.audit_rules`
(green). Keep the existing two Knight-only citation keys (still describe the OFF path).

**Stage 5 — A/B + decision.** OFF N=80 must read 5.76. ON N=80 (`SWEG_DMGBRACKET=1`):
report per-faction deltas, **Imperial Knights + the damaged-big-model over-shooters
(Custodes, T'au, World Eaters, Thousand Sons) first**, then the durable-vehicle
under-shooters (AdMech, Necrons). Faithful regardless of direction → propose a
default flip if net-neutral-or-better; if it regresses, keep gated and report the
honest result (the rule is still faithful, but a regression means another mechanism
dominates and the partial Knight-only window was masking it).

## Risks → de-risk

1. **Extraction conflation** (the wave-190b lesson): the defensive "−1 to be hit"
   must be excluded; anchor the Hit regex on `this model makes an attack`. The OC
   regex must match the model's own OC, not an aura that subtracts OC from enemies.
   Unit-test both against the Stormsurge (both penalties) and a defensive-aura unit
   (neither).
2. **`parsed.json` drift** → additive-diff check + double-regenerate-empty-diff +
   OFF == 5.76, no application change in flight during Stage 1.
3. **Double-application** when `SWEG_DMGBRACKET` and the Knight-only gates would both
   fire on a Knight → the generalized path replaces the Knight-only path (guard).
4. **Multi-tier / Move-Attacks brackets** → v1 models OC + Hit only; log the
   Move/Attacks omission count (no silent cap).
5. **Hashability / `lru_cache`** → tuple-encode the bracket + a hashability test +
   OFF == 5.76.

## Critical files

- `code/bsdata/mapper.py` (Stage 1 — `damaged_bracket` extraction + `parsed.json` regen)
- `code/bsdata/loader.py` (Stage 2 — `CatalogEntry` plumbing + override merge)
- `code/units.py` (Stage 2 `UnitProfile.damaged_bracket`; Stage 3 attack() hit penalty)
- `code/simulator.py` (Stage 3 — `_effective_oc` data-driven OC penalty)
- `data/rule_citations.d/` + `scripts/audit_rules.py` (Stage 4 — citation + register)

## Verification (each stage)

`python -m scripts.audit_rules`; `python -m pytest -q`;
`PYTHONIOENCODING=utf-8 python run.py --cli` exits 0; OFF N=80
`SWEG_DMGBRACKET` unset must read **5.76**; behavioural Stage 3/5 also run ON at N=80
(`SWEG_DMGBRACKET=1`), reporting the over-shooter (Custodes / T'au / World Eaters)
and under-shooter (AdMech / Necrons) per-faction deltas and the net headline.
