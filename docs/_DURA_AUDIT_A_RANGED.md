# Durability Audit A — the ranged damage pipeline into durable platforms

**Scope.** Verify every step of the simulator's ranged attack sequence
(`code/units.py::Unit.attack` and the shooting path in
`code/simulator.py::Battle._do_shoot`) against the printed 10th-edition rules,
specifically for attacks into high-Toughness / high-Wounds targets (Knights,
Death Guard vehicles, Monoliths: Toughness ≥ 10 or Wounds ≥ 15). Read-only; no
tracked source changed. Motivating evidence: sim Knights / Death Guard over-pole
+14 to +15, and roughly 73 % of shooting into Knights deals zero, where real
tournament rates say interacting with bricks should be roughly break-even.

**Base.** Branch `worktree-agent-a7b12f73f42023747`, reset to
`origin/claude/sim-calibration-18` @ `215301c`
("docs(ledger): record the owner ruling — the durability remodel must stay
rules-accurate, no knobs").

**Method.**
1. Static verification of every line of the ranged path in `Unit.attack` and
   `_do_shoot` against verbatim rule text (Wahapedia core rules and the BSData
   v10.6.0 cache, quoted below with URLs).
2. Dynamic instrumentation of 12 replayed anchor games (Astra Militarum and
   T'au Empire versus Chaos Knights and Imperial Knights, seeds reconstructed
   byte-exactly from `data/_anchor_sc50a_n80_log.json`), via
   `scripts/_dura_audit_a_probe.py`. That script (a) turns on the built-in
   `SWEG_DURABILITY_INSTR` hook to record realized effective saves / cover /
   invuln rates per target class, and (b) monkeypatches `Unit.attack` (from the
   scratch script only) to log every ranged attack sequence into a Knight and
   independently re-derive the rule-correct wound target and save target,
   comparing them to what the simulator's own helpers produced.

---

## HEADLINE RESULT — the ranged pipeline is rules-faithful (zero hard divergences)

Across **695 logged ranged attack sequences into Knight bricks** in the replayed
games, the simulator's wound target matched an independent hand-derivation of
the printed Strength-versus-Toughness chart on **every single call (0
mismatches)**. Every save, cover, invulnerable-save, damage, Feel-No-Pain and
damaged-bracket step verified clean against the printed rule text. The high
zero-damage rate into Knights that the probe reproduces (67.6 % of activations
in this sample) is the **correct consequence of the printed rules** applied to
the actual weapon/target matchups — most weapons that fire into a Knight are
light guns that genuinely cannot hurt Toughness 11–13 behind a 3+/5++ — not a
mis-modelled attack sequence.

**Conclusion for the owner's question: the durability over-pole is NOT located
in the ranged attack sequence. This surface is closed.** Any rules-accurate
correction to brick durability must be sought elsewhere (target selection /
focus-fire allocation, melee into bricks, objective and secondary scoring, or
army composition), not in the shoot-into-brick mechanics audited here.

---

## DIVERGENCE LIST

**No hard divergences found in the ranged attack sequence.** One soft
approximation is recorded below for completeness; it is not a clean single-line
rules violation and it is not brick-specific.

### A-1 (approximation, not a hard divergence) — Benefit of Cover granted by point-containment

- **Rule (verbatim, Wahapedia core rules — Terrain / Benefit of Cover):**
  "Each time a ranged attack is allocated to a model that has the Benefit of
  Cover, add 1 to the saving throw made for that attack (excluding invulnerable
  saving throws). Models with a Save characteristic of 3+ or better cannot have
  the Benefit of Cover against attacks with an Armour Penetration characteristic
  of 0." (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/)
- **What the sim does:** `_do_shoot` sets `in_cover` when the target model's
  single position point lies inside a cover-terrain polygon
  (`code/simulator.py:14140`, via `Map.cover_at`), and `Unit.attack` then adds
  the +1 (`code/units.py:3498-3509`). The arithmetic itself is faithful (armour
  only, single pip, 2+ floor, and the AP0/3+ exception at
  `code/units.py:3472-3478`, all verified firing in the replay — a Lasgun
  (Strength 3, AP 0) versus a 3+ Knight correctly gained nothing from cover).
- **Why it is only an approximation:** in the replay, Knights (TOWERING /
  TITANIC) received the Benefit of Cover on **56.8 %** of ranged hits — very
  close to the **60.2 %** rate for INFANTRY, i.e. the sim does not preferentially
  over-cover bricks. There is no core-rules clause that denies Benefit of Cover
  to TOWERING models (TOWERING alters visibility, not cover eligibility;
  confirmed against the core rules and Goonhammer's Ruleshammer terrain guide),
  and a Knight standing within area terrain legitimately gains cover in real
  10e. The point-containment proxy can over- or under-grant at the margins
  versus the real base-overlap-and-obscuration test, but it is a documented,
  symmetric terrain approximation, not a brick-specific rules error.
- **Direction / magnitude:** where it does fire on a Knight, cover only bites
  against AP-1 / AP-2 weapons (against AP-3+ the 5++ invulnerable already
  dominates, so cover changes nothing — confirmed: mean effective save vs the
  VEHICLE class was 4.08 with the invulnerable used on 93.3 % of hits). Net
  effect on brick durability is at most ~0.3 of a save pip on the AP-1/-2 slice,
  and is not clearly in excess of the printed rule. **Inflates brick durability
  marginally and only conditionally; not a hard divergence.**

---

## FAITHFUL LIST — every step verified clean

### 1. Hit roll
- **Ballistic-skill source & base target** — `hit_probability` → `_prob_to_target`
  (`code/units.py:52-58, 2378-2379`). Clamped to [2,7]; `int(round(7-p*6))`.
- **±1 net modifier cap** — "A Hit roll can never be modified by more than -1 or
  +1." (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/). Implemented by
  accumulating each source into `hit_mod_delta` then
  `hit_mod_clamped = max(-1, min(1, hit_mod_delta))` (`code/units.py:3397-3399`).
- **Unmodified 1 always fails / unmodified 6 always hits** — even when a
  modifier pushes the target to 7+, a natural 6 still hits
  (`code/units.py:4719`: `if unmodified_roll != 6 and roll < hit_target: continue`),
  and a natural 1 always misses (target floored at 2). Critical Hit gated on the
  **unmodified** die (`code/units.py:4739`).
- **Big Guns Never Tire** — "MONSTER and VEHICLE units are eligible to shoot …
  even while they are within Engagement Range …" with -1 to the Hit roll
  (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/). Gated to VEHICLE /
  MONSTER at `code/simulator.py:13840-13848`; the -1 applied at
  `code/units.py:3267-3268`. Pistols shoot in engagement with no penalty.
- **Heavy** — +1 to hit only when the shooter did not move, ranged, not indirect
  (`code/units.py:3257-3263`).
- **Indirect Fire** — -1 to hit, cannot benefit from Heavy, cannot score
  Critical Hits, an unmodified 1-3 always fails, and the target gains the
  Benefit of Cover (`code/units.py:3238-3240, 3271-3272, 4712-4713, 4736-4737,
  3498-3500`). Matches the current 10e Indirect Fire wording
  (docs/CORE_RULES_AUDIT.md #3).
- **Fire Overwatch** — only an unmodified 6 hits, modifiers dropped
  (`code/units.py:3395-3396, 4704-4705`).
- **Torrent** — auto-hits, no crit (`code/units.py:4550-4552`).
- **Towering / visibility** — TOWERING and AIRCRAFT see over OBSCURING (Woods);
  TOWERING does not see through RUIN walls except when within
  (`code/map.py:163-212`), matching the core Woods / Ruins wording.

### 2. Wound roll
- **Strength-versus-Toughness chart** — S≥2T on 2+; S>T on 3+; S=T on 4+; S<T on
  5+; 2S≤T on 6+ (`code/units.py:31-49`, `wound_probability`). **Empirically
  confirmed with 0 mismatches over 695 real weapon/target pairs**, including the
  spot-checks: Heavy Rail Rifle Strength 12 vs Toughness 12 Knight = 4+ (S=T);
  Lascannon Strength 12 vs Toughness 11 Questoris = 3+ (S>T); Demolisher
  Strength 14 vs Toughness 9 = 3+. (The task's "Lascannon Strength 12 vs
  Toughness 12 must be 4+" is the Knight Castellan/Valiant case, Toughness 12,
  and is satisfied; the Questoris chassis are Toughness 11 per BSData/Wahapedia,
  where Strength 12 correctly wounds on 3+.)
- **Anti-X** — an unmodified Wound roll of x+ scores a Critical Wound
  (auto-success), read on the **unmodified** die
  (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#ANTI-X);
  `code/units.py:4813-4832`.
- **Lethal Hits** — a critical hit auto-wounds; only the original crit, not its
  Sustained extras (`code/units.py:4743-4745`).
- **Twin-linked** — re-roll a failed wound once (`code/units.py:4785-4789`).
- **±1 wound modifier cap** — "A Wound roll can never be modified by more than -1
  or +1." Implemented at `code/units.py:3398, 3400`.
- **Unmodified 6 always wounds** — even at a 7+ target, `unmodified_wroll >= 6`
  forces a successful Critical Wound (`code/units.py:4828-4830`).

### 3. Allocation and saves
- **Armour save vs AP arithmetic** — `save_after_ap = save - ap` with AP a
  non-positive int (`code/units.py:3447`).
- **Benefit of Cover** — +1 to the armour save only (not invulnerable), single
  pip, 2+ floor, plus the "3+ or better save gets nothing versus AP 0"
  exception (`code/units.py:3472-3509`). Verbatim rule quoted in A-1 above.
  Empirically respected in the replay.
- **±1 save modifier cap** — ability-sourced +1-save buffs clamp to a single net
  +1; AP is not a modifier and stacks freely (`code/units.py:3510-3536`).
- **Invulnerable save substitution** — effective save is the better (lower) of
  the AP-modified armour and the invulnerable (`code/units.py:3570`,
  `min(save_after_ap, invuln)`). The **per-attack-type split** is honoured for
  ranged: `invuln = target.profile.invuln_save_ranged` in ranged mode
  (`code/units.py:3545-3547`), and `SWEG_INVULN_SPLIT_FIX`
  (`code/bsdata/loader.py:807-838`) preserves the BSData ranged-only split so a
  Knight's "5+ invulnerable save against ranged attacks" is applied at 5++ for
  ranged. Verified: Lascannon (AP-3) vs a 3+ Knight resolves to a 5+ save
  (armour 6+ → invulnerable 5++), and the built-in instrument shows the
  invulnerable used on 93.3 % of ranged hits into the VEHICLE class — the
  correct result of anti-tank AP outrunning the 3+ armour.

### 4. Damage application
- **Flat and variable damage** — real per-shot dice rolled via
  `roll_damage` (`code/units.py:129-167, 4510-4516`); mean fast-path when the
  gate is off (byte-identical).
- **Melta X in half range** — `per_shot_dmg += p.melta` when
  `distance <= range/2` (`code/units.py:2326-2331`); `distance` is computed and
  passed by `_do_shoot` (`code/simulator.py:14154, 14174`).
- **No spill between models** — overkill is lost: `current_health = max(0,
  current_health - amount)` (`code/units.py:1560`); the allocation pointer only
  advances to a sibling model when the current model dies, and a lone model's
  excess is simply lost (`code/units.py:4440-4490`).
- **Damage-reduction (-1 damage class)** — Disgustingly Resilient etc. via
  `transient_minus_one_damage_taken` with a floor of 1
  (`code/units.py:1508-1509`); C'tan Necrodermis -1 (`code/units.py:5093-5100`,
  and on the devastating path `4968-4975`).
- **Feel No Pain sequencing** — one d6 per point of damage, ignore on X+; applies
  to mortal wounds too (`code/units.py:1553-1559`).
- **Devastating Wounds** — **current 10e:** "if that attack scores a Critical
  Wound, no saving throw of any kind can be made against that attack (including
  invulnerable saving throws)." (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/).
  The sim skips the save on a critical wound and deals **normal damage** to the
  allocated model with Feel No Pain still applying
  (`code/units.py:4952-4980`) — i.e. the **current** save-bypass rule, not the
  retired launch-day mortal-wound conversion. (The audit brief's phrasing
  "devastating wounds as mortal wounds" describes the legacy rule; the sim is
  correct for the current rule and no divergence exists.)
- **Deadly Demise on death** — "When such a model is destroyed, roll one D6 …
  On a 6, each unit within 6\" of that model suffers a number of mortal wounds
  denoted by 'x'." (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/).
  Implemented at `code/simulator.py:15920-15990`: d6 on death, on a 6 deal X
  mortal wounds to each distinct unit within 6", routed through Feel No Pain and
  mortal-wound spillover; called from every death-detection site.

### 5. Damaged brackets
- **Rule (verbatim, Wahapedia, Knight Paladin datasheet — representative
  Questoris):** "DAMAGED: 1-9 WOUNDS REMAINING — While this model has 1-9 wounds
  remaining, subtract 5 from this model's Objective Control characteristic and
  each time this model makes an attack, subtract 1 from the Hit roll."
  (https://wahapedia.ru/wh40k10ed/factions/imperial-knights/Knight-Paladin)
- **What the sim does:** data-driven from `damaged_threshold` /
  `damaged_hit_penalty` (BSData v10.6.0), applying -1 to the Hit roll to the
  Knight's own attacks (ranged and melee) when `current_health <= threshold`
  (`code/units.py:2450-2474`, `SWEG_DMGBRACKET` default-on).
- **Verified against three real datasheets** (fires at exactly the printed
  threshold, not one wound early or late):
  - Knight Paladin — Wounds 26, damaged at 1-9 → -1 Hit. Matches Wahapedia.
  - Knight Castellan — Wounds 28, damaged at 1-10 → -1 Hit. Matches datasheet.
  - Armiger Warglaive — Wounds 14, damaged at 1-5 → -1 Hit. Matches datasheet.
  The BSData statlines the sim loads (Knight Paladin Toughness 11 / Save 3+ /
  Wounds 26 / 5++ ranged-only invulnerable; Castellan Toughness 12 / Wounds 28)
  match Wahapedia exactly — the catalogue's brick statlines are faithful.
  Note the bracket penalty degrades the **Knight's own offence** as it takes
  damage (correct direction — it pulls Knights down, not up).

---

## Artifacts
- `scripts/_dura_audit_a_probe.py` — replay + instrumentation (read-only;
  prints the durability instrument table, the 0-mismatch wound cross-check, and
  the per-weapon zero-rate / cover summary).

## Bottom line
Every step of the ranged attack sequence into bricks is rules-accurate. The only
noted item (A-1) is a symmetric terrain-cover approximation, not a hard
divergence and not brick-specific. The ranged-into-brick surface is closed; the
durability over-pole must be pursued in a different subsystem.
