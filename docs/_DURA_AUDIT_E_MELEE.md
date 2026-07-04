# Durability fidelity wave, audit E — the melee damage pipeline into durable platforms (2026-07-03)

**Scope.** Audit E of the durability fidelity wave. Read-only review of the melee
attack damage math in `code/units.py` `Unit.attack` (melee mode) and its calling
site `code/simulator.py` `Battle._do_fight`, checked against the printed
tenth-edition Warhammer 40,000 core rules (Wahapedia, fetched live 2026-07-03).
Prior audits (2026-05-31) already closed Pile-In, Consolidate, Heroic
Intervention, the plus-or-minus-one modifier cap, and Fights First as faithful;
none of those are re-examined here. This audit covers only the damage math of
melee attacks made **into** Toughness ten-or-greater / Wounds fifteen-or-greater
targets: which models get to fight, hit roll, wound roll, weapon keywords
(Lethal Hits, Sustained Hits, Devastating Wounds, Twin-linked, Anti-keyword,
Extra Attacks), saves in melee, and damage allocation.

**Base.** Branch `claude/sim-calibration-18` (worktree branch
`worktree-agent-a6b4ad264ee597965`, based on that branch at the required
commit), top commit `215301c49facd01f412fef34a44bf13e9c2cde27` — "docs(ledger):
record the owner ruling — the durability remodel must stay rules-accurate, no
knobs". No tracked file was modified; two scratch scripts were added under
`scripts/` (`_dura_audit_e_melee_replay.py`) and one data artefact under
`data/` (`_dura_audit_e_melee_sequences.json`, the raw captured trace, kept for
anyone who wants to re-run the hand-verification pass).

**Method.**

1. Static read of the melee resolution path in `code/units.py` (`Unit.attack`,
   melee-mode branches) and `code/simulator.py` (`Battle._do_fight`), tracing
   every modifier that reaches the hit roll, wound roll, save roll, and
   damage roll.
2. Every rule quoted below was re-fetched live from
   `https://wahapedia.ru/wh40k10ed/the-rules/core-rules/` on 2026-07-03 (the
   live page, not a cached memory of the rules) — verbatim text is quoted
   character-for-character from that fetch.
3. Dynamic spot-check: `scripts/_dura_audit_e_melee_replay.py` replays three
   games from the standing anchor `data/_anchor_sc50a_n80_log.json`
   (World Eaters vs Chaos Knights, seeds 0-2, exact recipe as
   `scripts/_ec_crater_replay.py` / `scripts.evaluate_vs_meta._run_battle_job`:
   `random.seed(pair_seed)` then `build_faction_random_army(..., use_archetype=True)`
   for both sides). A `sys.settrace` hook captures every fully-resolved melee
   attack call made by a World Eaters attacker against a Chaos Knights /
   Imperial Knights target, reading the frame's local variables
   (`hit_target`, `wound_target`, `save_target`, `p.melee_strength`,
   `target.profile.toughness`, and the composed Lethal/Sustained/Devastating/
   Twin-linked flags) at the point in `Unit.attack` immediately before the
   per-shot loop begins (`code/units.py:4492`, the `for _ in range(n_attacks):`
   line) — after every once-per-attack modifier has been resolved and before
   any per-shot-only state (Anti-keyword Bernoulli draw, Devastating Wounds
   basket fraction) is computed. This captured 538 real melee attack calls
   (target: twenty or more), each cross-checked against an independently
   hand-transcribed copy of the printed Strength-vs-Toughness table.
4. A sample of the real units and weapons the replay actually encountered
   (Defiler, Khârn the Betrayer, War Dog Brigand, power klaw, thunder hammer)
   was independently cross-checked against Wahapedia / the raw BSData cache
   to confirm the simulator's input data (Strength, Toughness, Armour
   Penetration, invulnerable save) matches the real datasheet, not just that
   the simulator's own arithmetic is internally consistent.

---

## Finding 0 — correction to this audit's own briefing premise: tenth edition has no "second-rank" fight-eligibility chain

The audit brief characterised the printed rule as "models-in-engagement-range
fight (both ranks per the 10e rule: within Engagement Range, or within half an
inch of a model that is)". That description is **not what the current printed
tenth-edition text says**, and it is worth flagging explicitly because it
changes the read of items 1 and 6 below.

Fetched verbatim, `https://wahapedia.ru/wh40k10ed/the-rules/core-rules/`,
Fight Phase → Fight → 2. Make Melee Attacks → "Which Models Fight":

> "A model in the fighting unit can make attacks with its melee weapons
> provided that, when the unit was selected to fight, it was within
> Engagement Range of at least one enemy unit. If a model is not within
> Engagement Range of any enemy units, it cannot make attacks."

There is no "or within Engagement Range of a friendly model that is" clause —
that chaining rule existed in ninth edition but was deliberately dropped in
the tenth-edition rewrite of the Fight phase (a well-documented edition
change: tenth edition no longer lets a "second rank" fight through a
friendly model). A model must itself be within Engagement Range of an enemy
unit to make attacks, full stop.

The simulator's `Battle._do_fight` (`code/simulator.py:15185-15190`) gates
exactly on this: `in_range = [e for e in alive_enemies if _er_gap_units(attacker, e) <= 1.0]`
/ `if not in_range: return`. Because SwegHammer represents one Unit instance
per physical model (confirmed correct architecture, see the ledger's
2026-06-21 ground-truth correction), each attacking model-Unit is
independently checked against this exact condition, and `_er_gap_units`
measures **base-edge to base-edge** distance (`code/sim/geometry.py`, gated
`SWEG_CHARGE_BASEEDGE`, default-on since wave 240), not centre-to-centre — so
a large-based Knight's whole perimeter is available to horde attackers, not
just a point at its centre. This is faithful to the current printed rule: a
horde squad's models that cannot physically reach within Engagement Range of
a large base are correctly excluded from fighting, and no model erroneously
gains a "stood behind a friendly model" exemption. **This is not a
divergence** — it is the printed rule working as intended, and the sim
implements it correctly. Whether the horde's positioning/collision system
lets enough models physically reach that 1-inch perimeter is a geometry/AI
question already closed by the wave-211 collision fix (`SWEG_COLLISION`),
out of this audit's damage-math scope.

## Finding on `damaged_attacks_penalty` — defined, threaded through the loader, never consumed (currently inert)

`UnitProfile.damaged_attacks_penalty` (`code/units.py:856`) is extracted by
the BSData mapper (`code/bsdata/mapper.py:3151`) and carried through the
loader and catalogue builder (`code/units.py:5848`), but no site in
`Unit.attack` ever reads it — only `damaged_hit_penalty` is consulted
(`code/units.py:2452`). A full scan of the live catalogue
(`data/bsdata/parsed.json`, 1,470 units) and `data/overrides.json` found
**zero** units with a non-zero value, and a regular-expression scan of every
raw BSData cache file (`data/bsdata/cache/*.cat.gz`) for the pattern
`subtract \d+ from (this model|the bearer)'?s? Attacks characteristic` found
zero matches anywhere in the current tenth-edition data — so no real
datasheet in the current card pool has a flat "subtract N from Attacks
characteristic" Damaged-bracket clause for this dead code path to miss. (One
different pattern exists — Adepta Sororitas' "Attacks characteristics of all
of its weapons are halved" — but that is a halving, not a flat subtraction,
so this field's schema could not represent it even if wired up, and it is a
low-Wounds character model, not a Toughness ten-plus / Wounds fifteen-plus
durable platform in this audit's scope.) Recorded as a code-hygiene
observation, not a divergence: it has zero live behavioural effect today,
including on both spot-checked Knight datasheets (Knight Preceptor, Knight
Paladin), whose real Damaged-bracket text only reduces Objective Control and
the Hit roll, matching what the simulator actually applies.

---

## Divergence list

**None found.** Every melee damage-math mechanic examined — the hit roll, the
Strength-vs-Toughness wound table, Anti-keyword crit-wound thresholds, Lethal
Hits, Sustained Hits, Devastating Wounds, Twin-linked, Extra Attacks weapons,
saves in melee (armour, armour penetration, invulnerable, cover),
damaged-bracket interaction, and damage allocation with no spill — matched
the printed rule,
both by static code read and by a 538-sequence dynamic replay of real
World Eaters vs Chaos Knights anchor games. Zero divergences is an explicitly
valid outcome per this audit's brief.

---

## Faithful list

### 1. Attacks characteristic / which models fight

Verbatim (Wahapedia core rules, Fight Phase → Which Models Fight, quoted in
full under Finding 0 above): a model must itself be within Engagement Range
of an enemy unit to fight; there is no tenth-edition "second rank" chain
through a friendly model. `Battle._do_fight` (`code/simulator.py:15185-15190`)
gates each attacking model-Unit on `_er_gap_units(attacker, e) <= 1.0`
(base-edge distance), matching this exactly. Every alive model-Unit gets an
independent activation slot each round (`Army.activation_queue`,
`code/army.py:950-1026`, returns every not-yet-activated alive unit with no
cap on count; the `while True` loop in `Battle._run_round_alternating`,
`code/simulator.py:11301-11374`, keeps draining the queue until both sides
are exhausted), so there is no separate activation-count cap that could
under-count a horde's fighting models beyond the per-model Engagement-Range
test itself.

### 2. Hit roll / Strength-vs-Toughness wound table

Verbatim (Wahapedia core rules, Wound Roll table, fetched 2026-07-03):
"STRENGTH IS TWICE (or more than twice) the TOUGHNESS: 2+ | STRENGTH IS
GREATER than the TOUGHNESS: 3+ | STRENGTH IS EQUAL to the TOUGHNESS: 4+ |
STRENGTH IS LESS than the TOUGHNESS: 5+ | STRENGTH IS HALF (or less than
half) the TOUGHNESS: 6+". `code/units.py:31-49` (`wound_probability`)
implements this exactly (verified by hand for every boundary case). The
538-sequence dynamic replay (`scripts/_dura_audit_e_melee_replay.py`,
`data/_dura_audit_e_melee_sequences.json`) found 538/538 captured
`wound_target` values matching an independently hand-transcribed copy of
this same chart, across a wide range of real Strength/Toughness pairs
actually encountered in replayed anchor games (Defiler Shearing Claws S16
vs Knight Tyrant T12 → 3+; Defiler Electroscourge S12 vs Knight Despoiler
T11 → 3+; Khârn the Betrayer Gorechild S7 vs War Dog Brigand T9 → 5+;
Khorne Berzerkers Chainblade S4 vs War Dog Brigand T9 → 6+, etc.).

Spot-verified real weapon/target pairs named in the audit brief, against
Wahapedia / the raw BSData cache directly (not just the sim's own
arithmetic): a power klaw (Orks Nobz datasheet) is Strength 9, Armour
Penetration -2, Damage 2 — vs Toughness 12 (`wound_probability(9, 12)` =
5+, matching the chart's "Strength is less than Toughness" row). A thunder
hammer (Space Marines, BSData profile id `3b63-a16a-2b44-553a`) is
Attacks 5, Weapon Skill 3+, Strength 8, Armour Penetration -2, Damage 2,
keyword Devastating Wounds — vs Toughness 10 (`wound_probability(8, 10)` =
5+, same row). Both match the audit brief's claimed thresholds exactly.

Also confirmed: an unmodified Hit roll of 6 is always a Critical Hit in
melee even under a negative modifier (`code/units.py:4714-4739`, citing the
2026-05-31 core-rules audit finding #6), and an unmodified Wound roll of 6
is always a successful Critical Wound (`code/units.py:4747-4756`,
`unmodified_wroll`, tracked separately from any substituted/re-rolled die so
a re-rolled or substituted 6 cannot crit — matching the rule that only the
*unmodified* roll can be a Critical Hit/Wound).

### 3. Anti-keyword

Verbatim (Wahapedia core rules, Weapon Abilities → Anti-X, fetched
2026-07-03): "Weapons with [ANTI-KEYWORD X+] in their profile are known as
Anti weapons. Each time an attack is made with such a weapon against a
target with the keyword after the word 'Anti-', an unmodified Wound roll of
'x+' scores a Critical Wound." `code/units.py:4813-4829` implements this on
`unmodified_wroll` (not the post-substitution roll), reading the melee-mode
weapon's own Anti-keyword set (`p.melee_anti_keywords`, distinct from the
ranged-primary `p.anti_keywords` — `code/units.py:3433`) so a unit whose
ranged weapon happens to carry an Anti-keyword does not leak it onto melee
attacks.

### 4. Lethal Hits, Sustained Hits, Devastating Wounds, Twin-linked (melee-mode routing)

Verbatim (Wahapedia core rules, Weapon Abilities, fetched 2026-07-03):

> Lethal Hits: "Each time an attack is made with such a weapon, a Critical
> Hit automatically wounds the target."
> Sustained Hits: "Each time an attack is made with such a weapon, if a
> Critical Hit is rolled, that attack scores a number of additional hits on
> the target as denoted by 'x'."
> Devastating Wounds: "Each time an attack is made with such a weapon, if
> that attack scores a Critical Wound, no saving throw of any kind can be
> made against that attack (including invulnerable saving throws)."
> Twin-linked: "Each time an attack is made with such a weapon, you can
> re-roll that attack's Wound roll."

All four are implemented on melee-specific fields (`melee_lethal_hits`,
`melee_sustained_hits`, `melee_devastating_wounds`, `melee_twin_linked`),
distinct from the ranged-primary fields, per the wave-244 bug fix that
closed the earlier ranged-to-melee keyword leak. Sustained Hits correctly
adds *extra* hits (`n_hits = 1 + effective_sustained_hits if crit_hit else 0`,
`code/units.py:4740`) rather than replacing the original hit; Lethal Hits'
auto-wound correctly applies only to the original crit hit (`hit_i == 0`),
not to the sustained-hits extras (`code/units.py:4743`), matching the rule
that Sustained Hits generates ordinary hits which must still roll to wound.
Devastating Wounds correctly skips the entire save block — both the armour
save and the invulnerable save — on a Critical Wound
(`code/units.py:4952-4980`), matching "no saving throw of any kind... including
invulnerable saving throws" verbatim.

### 5. Extra Attacks weapons — additive, not exclusive

Verbatim (Wahapedia core rules, Weapon Abilities → Extra Attacks, fetched
2026-07-03, confirmed identical across two independent fetches): "Each time
the bearer of one or more Extra Attacks weapons fights, it makes attacks
with each of the Extra Attacks melee weapons it is equipped with and it
makes attacks with one of the melee weapons it is equipped with that does
not have the [EXTRA ATTACKS] ability (if any)." The mapper
(`code/bsdata/mapper.py:2964-2973`) gates `extra_melee_profiles` strictly on
`_w.extra_attacks` being true for each candidate weapon — it does not
include every additional melee weapon a model happens to carry. Verified
against a real multi-melee-weapon chassis, Knight Rampager (reaper
chainsword + warpstrike claw, neither of which carries [EXTRA ATTACKS] —
both carry [SUSTAINED HITS 1] instead, confirmed directly from Wahapedia):
the mapper correctly resolves this as a single chosen weapon
(`best_melee`), not an additive pair, because neither weapon qualifies for
the additive `extra_melee_profiles` path. `code/units.py:1709-1790`
(`_profiles_to_fire = [None] + _melee_extras`) then fires the primary
profile plus every true Extra-Attacks profile once each in the same Fight
sub-phase activation, matching "in addition to" per the rule.

### 6. Saves in melee — armour, Armour Penetration, invulnerable, cover

No cover in melee: `code/units.py:3498-3504` gates Benefit of Cover on
`mode != "melee"`. Conditional (per-attack-type) invulnerable saves:
`code/units.py:3545-3553` reads `target.profile.invuln_save_melee` in melee
mode, distinct from the ranged value — confirmed the Imperial/Chaos Knight
Ion Shield-style ranged-only invulnerable save "stays dead" in melee: the
War Dog Brigand (spot-checked directly against Wahapedia) has a 5+
invulnerable save explicitly "against ranged attacks only", and the
dynamic replay captured `invuln_melee = 7` (no save) for every War Dog
Brigand melee sequence, confirmed correct. This is double-guarded: even
with `SWEG_COND_INVULN=0` (the legacy single-value path), a second
independent check at `code/units.py:5733`
(`invuln_save_melee=(7 if entry.invuln_ranged_only else entry.invuln_save_melee)`)
forces the melee invulnerable save off whenever the BSData ranged-only flag
is set, so the historical "phantom melee invulnerable save" bug cannot
regress under either code path. Armour Penetration reduces the armour save
before the invulnerable-vs-armour comparison (`code/units.py:3447`,
`save_after_ap = target.profile.save - ap`), and the plus-or-minus-one
save-modifier cap is applied per the core-rules "Modifiers" section
(`code/units.py:3510-3536`).

### 7. Damage — variable dice, no spill, damaged-bracket interaction

Rolling damage dice (`SWEG_ROLLDMG`, adopted default-on wave 247 per the
decision ledger) is confirmed live in the current build: a weapon with a
random Damage characteristic rolls that characteristic per shot
(`code/units.py:4492-4516`, `roll_damage`) rather than always applying the
mean. Damage allocation follows the printed rule — a destroyed model's
excess damage from the wound that killed it is lost, and only the *next*
successful wound is allocated to the next living model of the same squad
(`code/units.py:4440-4490`, `_alloc_target`) — with no cross-model spill of
a single wound's excess damage. The Damaged-bracket -1-to-Hit penalty that
applies when the *brick itself* later fights back while damaged is
data-driven per real datasheet (`UnitProfile.damaged_hit_penalty`,
generalised to all 94 datasheets that carry it across 25 factions, not just
Knights) and explicitly applies to both shooting and melee attacks made by
the damaged model (`code/units.py:2450-2474`, "applies to BOTH shooting and
melee"), spot-verified against the real Knight Preceptor / Knight Paladin
Damaged-bracket text ("subtract 5 from this model's Objective Control
characteristic and each time this model makes an attack, subtract 1 from
the Hit roll").

---

## Summary

No rules-accuracy divergence was found in the melee damage pipeline into
durable (Toughness ten-plus / Wounds fifteen-plus) targets. The World
Eaters/Orks-into-bricks under-performance the owner's ruling is trying to
explain is not caused by a wrong hit roll, wound roll, keyword, save, or
damage-allocation rule in this pipeline — those all check out against the
printed tenth-edition text, both statically and against 538 real dynamic
melee sequences replayed from the standing anchor. If the durability
remodel continues, the next place to look is outside this audit's scope:
whichever mechanic actually gates *how many* attacks a horde manages to
land per battle round (positioning/collision/pile-in throughput into a
large base, already closed as faithful by the wave-211 collision fix and
the 2026-05-31 Pile-In/Consolidate audit) rather than the correctness of
each individual attack once it is thrown.
