# Durability fidelity wave — audit C: the points-out side of durable platforms

Read-only audit. Base commit `215301c` (`docs(ledger): record the owner ruling — the
durability remodel must stay rules-accurate, no knobs`), branch
`origin/claude/sim-calibration-18`. No tracked files were changed to produce this
report; the only new files are this document and the scratch replay script
`scripts/_dura_audit_c_uptime_replay.py`.

## Scope and framing

The owner's diagnosis is that the simulator's durable bricks (Imperial Knights,
Chaos Knights, Death Guard vehicles and monsters) win primarily on uptime —
staying alive, shooting, and scoring every round. This audit checks the
points-out side of that channel: whether the simulator lets a brick convert
uptime into more shooting output, more Objective Control, or more victory
points than the printed tenth-edition rules allow, and whether opponents can
collect the real victory points the rules award for killing one. Six areas
were checked: Big Guns Never Tire (both directions), Objective Control,
secondary-mission harvesting, Deadly Demise, Fall Back and shoot, and a
qualitative uptime replay of four anchored Imperial Knights games.

---

## Divergence list

### 1. Big Guns Never Tire — the reciprocal "shooting into engagement" clause is not modelled at all

**Verbatim rule (Wahapedia core rules,
https://wahapedia.ru/wh40k10ed/the-rules/core-rules/, Shooting phase, Select
Targets / Big Guns Never Tire):**

> "While an enemy unit is within Engagement Range of one or more units from
> your army, you cannot select that enemy unit as a target of ranged
> weapons."

> "MONSTER and VEHICLE units are eligible to shoot in their controlling
> player's Shooting phase even while they are within Engagement Range of one
> or more enemy units. Ranged weapons equipped by MONSTER and VEHICLE units
> can target one or more of the enemy units they are within Engagement Range
> of, even if other friendly units are also within Engagement Range of the
> same enemy unit. Each time a MONSTER or VEHICLE unit makes a ranged attack,
> if that unit was within Engagement Range of one or more enemy units when it
> selected its targets, unless that attack is made with a Pistol, subtract 1
> from that attack's Hit roll."

> "You can select an enemy MONSTER or VEHICLE unit within Engagement Range of
> one or more units from your army as a target of ranged weapons. Each time a
> model from your army makes a ranged attack against such a target, unless
> that attack is made with a Pistol, subtract 1 from that attack's Hit roll."

This corroborated independently against a second source (web search of
Ruleshammer / tabletopbattles.com coverage of the same core rule), which
confirms the same general restriction and exception wording. So the rule is
genuinely two-sided: (paragraph one) a unit cannot normally be targeted by
ranged weapons while it is locked in melee with any of the shooting army's
own units, and (paragraph two, the reciprocal Big Guns Never Tire clause) an
enemy MONSTER or VEHICLE is a carved-out exception to that lock — it CAN
still be targeted, but every attack against it also suffers the same -1 to
the Hit roll.

**Sim behaviour.** `code/simulator.py` `_do_shoot` (candidate building,
`code/simulator.py:13817-13868`) filters candidates by range, line of sight,
Look Out Sir and Lone Operative (`can_target_for_ranged`,
`code/army.py:55-140`), the Blast-cannot-target-an-engaged-unit rule
(`code/simulator.py:13862-13866`), and — only when the ATTACKER ITSELF is
within Engagement Range of an enemy unit — a restriction to targets the
attacker is itself engaged with (`code/simulator.py:13855-13859`, correctly
modelling paragraph one's precondition and the Big Guns Never Tire -1 for the
attacker's own state at `code/units.py:3265-3268`). Nowhere in this pipeline
does the code check the OTHER direction: whether the prospective TARGET is
within Engagement Range of some OTHER unit belonging to the ATTACKER's own
army (`attacker_army.alive_units`), which is what paragraph one and two
actually gate on. `alive_units` (`code/army.py:875-878`) is a plain alive
filter with no melee-lock state at all.

Two consequences fall out of the same gap:

- **(a) The general lock-in-combat restriction is entirely unenforced for
  non-Vehicle/Monster targets.** A unit can freely shoot any enemy unit that
  is locked in melee with one of its own army's other units, when the real
  rule forbids the shot outright unless the target is a MONSTER or VEHICLE.
- **(b) The Big Guns Never Tire reciprocal -1 to hit never fires.** When a
  brick (an Imperial Knight, a Chaos Knight, a Death Guard vehicle or
  monster) is pinned in melee by an enemy unit, that enemy's OTHER ranged
  units currently hit it at full, unpenalised accuracy instead of the
  required -1.

**Direction and magnitude.** Mixed, and worth stating precisely rather than
folding into one number. Effect (a) is a universal, faction-neutral
over-permission: it lets ANY army — including a durable army's own
melee-capable elements (a Death Guard Terminator unit or a melee-profile
Knight tying up a screening unit) — convert a successful melee pin into extra,
otherwise-illegal ranged kills the same round. That is squarely the kind of
uptime-to-output conversion this audit is checking for, but because it is
symmetric (fragile hordes pinning a brick benefit from it exactly as much as
a brick's own melee benefits from pinning a horde), its net effect on the
Imperial Knights / Death Guard over-pole specifically is not determinable
from code inspection alone. Effect (b) points the other way: it currently
UNDER-values brick durability whenever a brick is pinned by enemy melee,
because the enemy's other guns hit it more reliably than the rules allow —
fixing it would make bricks MORE durable, working against the calibration
goal. Magnitude class: **moderate** for the code-path reach (it fires
whenever any unit anywhere is locked in melee while its own army still has
live ranged support, a common mid-to-late-round board state), but **minor**
per-instance (a single ±1 modifier on the Hit roll, roughly a one-in-six
swing in hit probability for a typical Ballistic Skill).

Not previously documented: searched `docs/CORE_RULES_AUDIT.md` and
`docs/DURABILITY_OVERREWARD_INVESTIGATION.md` for this specific gap. The
former's item 4 ("in-engagement shooting can target any unit") and item 5
("Blast can target units in Engagement Range") cover the ATTACKER's own
engagement state and are already fixed in the current code (verified at
`code/simulator.py:13855-13866`, both filters present and dated
"CORE-RULES-AUDIT 2026-05-31"). Neither existing document addresses the
reciprocal clause audited here.

### 2. Secondary-mission harvesting — Bring It Down / Assassination are reachability-broken, not value-broken

**Verbatim rule.** Chapter Approved 2025-26 kill secondaries
(https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/,
corroborated against Bell of Lost Souls / Goonhammer Chapter Approved 2025-26
mission-deck coverage): Bring It Down scores 2 victory points for a destroyed
enemy MONSTER or VEHICLE unit, +2 more if its Wounds characteristic is 15 or
higher, +2 again at 20 or higher, capped at 6 victory points per unit;
Assassination scores 4 victory points for a destroyed enemy CHARACTER with 4
or more Wounds, 3 for one under 4 Wounds, with no separate Warlord bonus in
this edition of the mission pack.

**Sim behaviour.** The coded values are byte-accurate to the printed card:
`code/secondaries.py` lines 203-214 encode exactly this 2/+2/+2/cap-6 and
4-vs-3 structure, and the wound-tier gating at `code/secondaries.py:314-329`
correctly reads the target's Wounds characteristic (`profile.health`), which
correctly identifies a 22-to-30-Wounds Knight as qualifying for the top
bracket. The divergence is in whether the cards are ever reachable:

- `TACTICAL_DECK_POOL` (`code/secondaries.py:144-179`) deliberately excludes
  `bring_it_down` and `assassination` — the comment at
  `code/secondaries.py:130-134` states they are "the FIXED track's pool and
  are NOT in this deck." Yet the Tactical scoring logic for both cards is
  fully implemented and reachable in code
  (`code/simulator.py:3616-3633`, the `is_tactical` branch) — it is simply
  dead, because no army on the Tactical track can ever draw the card that
  scoring logic serves.
- `_choose_secondary_track` (`code/secondaries.py:934-946`) routes an army to
  the Tactical track purely from its OWN chaff count and unit count — that
  is, exactly the broad, unit-rich army shapes (Orks, Tyranids, Astra
  Militarum) best equipped to actually grind down a durable brick. Those are
  the armies structurally barred from ever drawing Bring It Down or
  Assassination.
- Even on the Fixed track, `_pick_fixed_kill_pair`
  (`code/secondaries.py:900-931`) only picks `bring_it_down` for slot one if
  the enemy fields 3 or more MONSTER/VEHICLE units; an opponent embedding one
  or two bricks inside an otherwise different army composition falls back to
  `cull_the_horde` instead, which the brick's death does not satisfy at all.

**Direction and magnitude.** Under-rewards killing a durable brick — an
opponent that destroys an Imperial Knight, a Chaos Knight, or a Death Guard
vehicle or monster frequently collects fewer of the real printed victory
points for doing so than the rules require, which reads on the other side of
the ledger as the simulator inflating the brick's effective win-rate
contribution. Magnitude class: **moderate** — the numbers themselves are
correct; the gap is structural reachability, concentrated exactly on the
matchups and army shapes this audit is investigating.

### 3. Deadly Demise — the "2D6" value string silently collapses to 1

**Verbatim rule** (core rule, cited already in
`data/rule_citations.d/core_deadly_demise.json`): each time a model with this
ability is destroyed, roll one D6; on an unmodified 6, that model's unit
explodes and every unit — friend or foe — within 6 inches suffers a number of
mortal wounds specified per datasheet (e.g. "Deadly Demise D3", "Deadly
Demise D6", "Deadly Demise D6+2", or "Deadly Demise 2D6").

**Sim behaviour.** The mechanism itself (unmodified-6 trigger, 6-inch radius,
both-army scope, per-unit not per-model grouping) is faithfully modelled at
`code/simulator.py:15883-15968` (`_maybe_apply_deadly_demise`) and called from
every real death-detection site (`code/simulator.py:7554, 12487, 14204,
14615, 15236, 16516, 16603`). The per-datasheet expected-value string is
parsed by `_parse_demise_value` (`code/bsdata/mapper.py:3708-3746`), which
handles the literal forms `N`, `D3`, `D6`, `D3+3`, `D6+2`, and `D6+3`, but has
no branch for `2D6`. Confirmed directly against the BSData source cache
(`data/bsdata/cache/Imperium - Imperial Knights - Library.cat.gz`, the actual
`<selectionEntry name="Acastus Knight Asterius">` block, which carries
`<modifier type="append" value="2D6" field="name"/>`) and against
`data/bsdata/parsed.json`, where all four affected catalogue entries —
`imperial_knights_library_acastus_knight_asterius`,
`imperial_knights_library_acastus_knight_porphyrion`,
`chaos_knights_library_chaos_acastus_knight_asterius`, and
`chaos_knights_library_chaos_acastus_knight_porphyrion` (Toughness 13, Wounds
30 — the largest Titanic super-heavy Knight chassis in the catalogue) —
record `"deadly_demise": 1`. The unhandled `"2D6"` string fails
`_parse_demise_value` (returns 0), and `extract_deadly_demise`
(`code/bsdata/mapper.py:3749-3777`) then falls through to its "ability
present but no parseable suffix" branch, which unconditionally returns 1 —
silently substituting an expected value of 1 for the real expected value of
7 (2D6 averages 7). This is also a silent-default violation of the project's
own standing rule (`CLAUDE.md` rule 13: fail loud when data is missing) — the
fallback swallows a real, present, but unrecognised value string rather than
raising.

Two narrower, unrelated completeness gaps surfaced in the same search:
`code/simulator.py:4877` (a kill via the Leechspore Eruption stratagem) emits
`UnitKilled` without calling `_maybe_apply_deadly_demise`, so a MONSTER or
VEHICLE killed this way never rolls its demise at all. `code/simulator.py:9440`
(a unit destroyed for failing to arrive from Strategic Reserves by round
three) similarly skips the call, though this one is defensible by omission —
the unit never occupied a board position, so there is no sensible origin
point for a 6-inch mortal-wound burst.

**Direction and magnitude.** Inflates brick survivability/impunity on the
specific datasheets affected — the real punishment for standing near a dying
Acastus Knight Asterius or Acastus Knight Porphyrion (Imperial or Chaos) is
understated by roughly seven-fold. Magnitude class: **major on the four
affected datasheets** (a silent 7x understatement of a real mechanic), but
**narrow in population reach** — the Acastus chassis is a small slice of
Knights army lists, so the aggregate effect on the measured win-rate
over-pole is likely small. The two missed call sites are **cosmetic/minor**.

---

## Faithful list

**Big Guns Never Tire, attacker's own engagement precondition** — VEHICLE/
MONSTER-only gate, -1 to Hit, restriction to targets the attacker is itself
Engagement-Range of, and the Blast-weapon-cannot-target-an-engaged-unit rule
are all correctly modelled (`code/simulator.py:13771-13866`,
`code/units.py:3265-3268`). Only the reciprocal clause (divergence 1 above)
is missing.

**Objective Control characteristic values for brick chassis** — `oc`
is read directly from BSData's own "OC" stat column
(`code/bsdata/mapper.py:260`, stored on `UnitProfile` at
`code/units.py:561`), not invented or scaled by simulator logic. Verified
live against Wahapedia: Knight Errant and Knight Castellan (both TITANIC and
TOWERING) are Objective Control 10 in both the sim and the real datasheet;
Armiger-class Knights (non-Titanic) are Objective Control 6 in both;
Deathshroud Terminators are Objective Control 1 in both; Foetid Bloat-drone
and Plagueburst Crawler are Objective Control 3 in both. Note for the audit's
own framing: the brief's premise that TITANIC Knights should carry a higher
Objective Control value (12) than non-Titanic Questoris-class Knights (10) is
not current tenth-edition reality — Questoris and Dominus-class Knights share
Objective Control 10 regardless of the Titanic keyword; only the smaller
Armiger class differs. There is nothing to correct here.

**Per-marker Level of Control computation** — `_assign_army_oc`
(`code/simulator.py:1056-1197`) sums, per objective marker, the Objective
Control of every alive model within that marker's control range (the
default-on `SWEG_OC_PER_MARKER`, adopted 2026-07-02, credits every model's
Objective Control toward every marker within its own reach, matching "add
together the Objective Control characteristics of all models... within range
of that objective marker" verbatim); ties leave the marker uncontrolled via a
strictly-greater comparison (`code/simulator.py:1314-1320`).

**Battle-shocked Objective Control = 0** — enforced by excluding any unit in
`self._battleshocked_this_round` from the Objective Control sum
(`code/simulator.py:1096-1097`, mirrored at four further call sites), and that
set is populated only on a failed Leadership test
(`code/simulator.py:9907-9910`), not merely for being below half strength.
Below-half-strength is correctly used only as eligibility to test
(`code/simulator.py:10399-10457`), with no separate mechanism found that
zeroes Objective Control directly off unit strength.

**Fall Back forfeits shooting and charging, universally, for Imperial
Knights, Chaos Knights, and Death Guard.** The verbatim rule ("If you make a
Fall Back move with a unit, then until the end of the turn that unit's models
cannot shoot or declare a charge", Wahapedia core rules,
https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Fall-Back, cited at
`data/rule_citations.d/core_fall_back.json:9`) is enforced unconditionally at `code/simulator.py:13659-13661` (shoot gate) and
`code/simulator.py:14887-14889` (the equivalent charge gate), both consulted
the same round the `fell_back_this_round` flag was set
(`code/simulator.py:12460`) and before it is cleared at the following round's
start (`code/simulator.py:11135`). The FLY keyword does not lift this
lockout in the current rules and the sim correctly does not model any such
lift (the stale ninth-edition carve-out is explicitly called out as removed
in the code comment at `code/simulator.py:13649-13653`). The one wired
exception — Gladius Task Force Tactical Doctrine — is gated by
`is_marine_faction` (`code/factions.py:172-181`), a pure set-membership
check with no substring matching, so it structurally cannot fire for
Imperial Knights, Chaos Knights, or Death Guard. No brick chassis was found
that can Fall Back and still shoot or charge.

**Deadly Demise mechanism** (trigger, radius, both-army scope, per-unit
grouping) — faithful; see divergence 3 above for the one narrow value-parsing
exception.

---

## Uptime instrumentation

Four anchored games from the standing anchor (`data/_anchor_sc50a_n80_log.json`,
copied into this worktree) were replayed byte-for-byte using the same
reconstruction `scripts/evaluate_vs_meta.py` used to produce them
(`scripts/_dura_audit_c_uptime_replay.py`, scratch, read-only): the Adeptus
Astartes versus Imperial Knights cell at seeds 0-3. All four replays
reproduced the anchor's recorded winner exactly, confirming the
reconstruction is faithful.

| Seed | Winner | Knights shooting activations by round (activated/alive) | Knights running victory points vs opponent by round 5 |
|---|---|---|---|
| 0 | Adeptus Astartes (Knights lost) | 1/7, 2/7, 3/7, 1/5, 1/4 | 43 vs 84 |
| 1 | Imperial Knights | 0/7, 2/7, 3/7, 0/6, 3/6 | 55 vs 27 |
| 2 | Imperial Knights | 0/7, 2/7, 3/6, 4/6, 3/5 | 66 vs 39 |
| 3 | Imperial Knights | 3/8, 7/8, 6/8, 4/7, 3/6 | 52 vs 34 |

Qualitatively, this is consistent with the owner's uptime diagnosis rather
than contradicting it: activation rates are never close to "every surviving
Knight fires every round" (round one is frequently 0 activations across the
board, and even in the strongest win, seed 3, activation peaks at 7/8 and
drifts back down as units die or run out of legal targets), so the sim is
not obviously granting bricks unlimited free shooting. What tracks with the
win/loss split is survival: in the one lost game (seed 0), the Knights side
takes two losses in round three and its shooting activation count collapses
from there (3/7 to 1/5 to 1/4) while the opponent's victory-point total pulls
sharply away (37 to 57 to 84); in the three won games, Knights units stay
substantially alive through round five and their victory-point lead widens
steadily rather than being front-loaded. This is descriptive only — it
supports the uptime framing qualitatively but does not by itself attribute
the over-pole to any specific mechanism beyond what is itemised above.

---

## Summary

Three genuine divergences were found, none of them a durability-statistic
nerf and none branched by faction or model count:

1. The Big Guns Never Tire reciprocal clause (shooting at an enemy Vehicle or
   Monster engaged with a friendly unit) is entirely unmodelled — moderate
   reach, minor per-instance, mixed direction (this specific clause slightly
   under-values brick durability rather than over-valuing it; the sibling gap
   in the general lock-in-combat restriction is direction-ambiguous without
   a dedicated measurement).
2. Bring It Down and Assassination are byte-accurate on value but
   structurally unreachable for exactly the army shapes and matchups most
   relevant to killing a durable brick — moderate, under-rewards killing
   bricks (inflates their effective win-rate contribution).
3. A "2D6" Deadly Demise value silently parses to 1 instead of 7 on the four
   Acastus Knight datasheets (Imperial and Chaos) — major on those four
   datasheets, narrow in population reach, inflates brick impunity and
   violates the project's own fail-loud standing rule.

Everything else audited — the attacker-side half of Big Guns Never Tire,
Objective Control characteristic values and the per-marker Level of Control
computation, battle-shocked Objective Control zeroing, and the Fall Back
shoot/charge lockout — is faithful to the printed tenth-edition rules with no
divergence found.
