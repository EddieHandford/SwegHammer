# SwegHammer over-pole unit audit (wave 259, 2026-06-26)

Code-grounded diagnostic of over-credit mechanics across the four current over-pole
faction clusters: World Eaters (+13.9), Emperor's Children (+12.0), Chaos Daemons
(+10.5), and Necrons (+9.4). Conducted against the wave-259 standing anchor
`data/_anchor_sc16a_n80_log.json` (gated mean absolute error 3.48, raw 6.27, 9/22
factions in band). Every claim carries file evidence verified by an adversarial
multi-agent audit; no finding rests on research priors alone.

This audit is the over-pole counterpart to `docs/SORORITAS_UNDERPOLE_AUDIT.md`,
which fed the just-closed "all the fixes" under-pole campaign (waves 254-258). The
survivors ranked below feed the next building campaign the same way that audit fed
the closed one.

## Anchor state and faction gaps

Standing anchor: `data/_anchor_sc16a_n80_log.json`, gated mean absolute error 3.48.

| Faction | Simulator win rate | Real win rate | Gap (sim minus real) |
|---|---|---|---|
| World Eaters | (estimated) +13.9 over real | ~50% | +13.9 |
| Emperor's Children | (estimated) +12.0 over real | ~50% | +12.0 |
| Chaos Daemons | (estimated) +10.5 over real | ~50% | +10.5 |
| Necrons | (estimated) +9.4 over real | ~50% | +9.4 |

Death Guard and Adeptus Custodes also appear in the over-pole half with smaller
residuals; several over-credit candidates are scoped to those factions and are
included in this audit.

## Screening methodology

Twenty-six candidates were evaluated. Each candidate was (a) verified in code at
exact file:line location, (b) traced to a verbatim rule citation in
`data/rule_citations.json` or `data/rule_citations.d/`, and (c) independently
adversarially tested by a second agent. Three gates must all pass for a candidate
to survive:

- Gate 1 — is the over-credit real and grounded in code?
- Gate 2 — is the over-credit also grounded in a verbatim citation (the sim does
  more than the quoted rule)?
- Gate 3 — is the faithful narrowing a fidelity restoration, not a metric nerf of
  a correct mechanic? (faithful_to_remove = true)

Candidates that pass all three gates proceed to ranking. A fourth flag
(command-point reallocation risk) is tracked per the Necron Conquering Tyrant
lesson: narrowing a stratagem's effect while the command-point spend remains active
can free the point for a stronger stratagem, causing a backfire.

---

## SURVIVORS — ranked build order

Nine candidates pass all three gates (one as hold). They are ranked by
(confidence multiplied by estimated magnitude multiplied by low command-point
reallocation risk). Passive-buff removals with no command-point risk rank above
stratagem-effect narrowings with command-point risk.

---

### Rank 1 — World Eaters Blood Tithe Lethal Hits grants army-wide full-round coverage instead of one unit for one phase

**Faction:** World Eaters

**Code location:** `code/units.py:3713` (Unit.attack; flag: `army.blood_tithe_lethal_hits_round == cur_round and p.faction == 'World Eaters'`); stamp set at `code/simulator.py:9709-9711`.

**Citation key:** `simulator.blood_tithe`

**Verbatim cited rule:** "4: Until the end of the phase, weapons equipped by models in one WORLD EATERS unit from your army have the [LETHAL HITS] ability."

**Pattern:** scope-misapplied (two compounding inflations)

**Recommendation:** build

**Estimated magnitude:** high

**Why faithful to remove:** The real rule grants Lethal Hits to ONE named World Eaters unit for the PHASE in which the Blood Tithe points are spent. The simulator sets `blood_tithe_lethal_hits_round` at the army level when four Blood Tithe points are spent; every subsequent `Unit.attack` call for any World Eaters model in any phase reads this stamp and activates `effective_lethal_hits = True`. All World Eaters units — Angron, Berzerkers, Eightbound, Jakhals, daemon allies, every model with `faction == 'World Eaters'` — gain Lethal Hits for every melee and ranged attack they make for the entire battle round. The citation's `quoted_text` confirms "one WORLD EATERS unit"; the code comment at `units.py:3705-3710` acknowledges only the duration collapse ("collapses 'this phase' to 'this round'") and is silent on the army-wide scope error, which is the larger of the two inflations. Restricting to a single named unit and limiting to the phase of the spend is exactly the verbatim rule; this corrects a genuinely wrong mechanic on two independent axes, not a metric nerf. No command-point reallocation risk: the four-Blood-Tithe spend grants Lethal Hits directly, not through a stratagem firing gate.

**Command-point reallocation risk:** no

---

### Rank 2 — World Eaters Blessings of Khorne buffs fire on daemon ally units that do not carry the ability on their datasheets

**Faction:** World Eaters

**Code location:** `code/units.py:2173` (Cleaving Blows Armour Penetration plus one gate); `code/units.py:3728` (Warp Blades Lethal Hits gate); `code/units.py:3969` (Martial Excellence Sustained Hits 1 gate) — all share: `mode == 'melee' and p.faction == 'World Eaters'`.

**Citation key:** `simulator.blessings_of_khorne`

**Verbatim cited rule:** "Once activated, each Blessing of Khorne applies to all units from your army with this ability until the end of the battle round."

**Pattern:** passive-buff-too-broad

**Recommendation:** build

**Estimated magnitude:** medium

**Why faithful to remove:** The verbatim cited rule restricts each Blessing of Khorne to "units from your army WITH THIS ABILITY" — an explicit ability gate, not a pure faction gate. BSData catalogue analysis of `data/bsdata/cache/Chaos - World Eaters.cat.gz` confirms that the daemon ally units `world_eaters_bloodletters`, `world_eaters_flesh_hounds`, and `world_eaters_bloodcrushers` do NOT carry a Blessings of Khorne infoLink in their datasheet selectionEntry blocks. Proper World Eaters infantry (Berzerkers, Angron, Eightbound, Jakhals, vehicles) all carry the infoLink. The `faction == 'World Eaters'` gate in all three Blessing legs is too broad and grants Cleaving Blows, Warp Blades, and Martial Excellence to the three daemon ally units when activated, which the codex explicitly excludes by absence of the ability. Adding a `has_blessings_of_khorne` flag to `UnitProfile` (set by the BSData mapper when the datasheet infoLink is present) and gating all three legs on both `p.faction == 'World Eaters'` and `p.has_blessings_of_khorne` excludes the daemon allies and matches the verbatim rule. This is a straightforward scope narrowing on three passive buff gates; no stratagem firing is involved.

**Command-point reallocation risk:** no

---

### Rank 3 — Death Guard Typhus Destroyer Hive Feel No Pain 5+ proxy covers ranged attacks, but the real rule is a melee-only minus one to Hit

**Faction:** Death Guard

**Code location:** `code/leaders.py:1282` (LeaderAbility `fnp=5`, `host_keys=('death_guard_plague_marines',)`); `code/units.py:4481` (tgt_fnp_buff applied in receive_damage regardless of attack mode).

**Citation key:** `LeaderAbility.The Destroyer Hive`

**Verbatim cited rule:** "While this model is leading a unit, each time a melee attack targets that unit, subtract 1 from the Hit roll."

**Pattern:** passive-buff-too-broad

**Recommendation:** build

**Estimated magnitude:** medium

**Why faithful to remove:** The verbatim cited rule applies only to melee attacks and grants a minus one to the Hit roll on the attacker — not a Feel No Pain save on the defender. The `fnp=5` in `leaders.py:1282` is a proxy for the melee-only defensive effect because the leader-aura layer does not yet expose a melee-only minus-one-to-Hit modifier on the target side (the citation itself acknowledges this: "proxy for melee-only -1-to-Hit on the target side ... intended swap to `hit_penalty_melee=1`"). The proxy is broader than the real rule on two dimensions: it applies to ranged shooting attacks as well as melee (the real rule is melee-only), and it reduces damage taken after saves rather than reducing hits scored before saves. The `receive_damage` path at `code/units.py:4481-4693` applies the Feel No Pain save against ALL incoming damage with no mode or phase gate. Removing the ranged coverage (or replacing with a melee-only minus-one-to-Hit proxy when that mechanic is available) is a fidelity restoration, not a metric nerf — the cited rule is genuinely melee-only. No stratagem firing is gated by this leader aura.

**Command-point reallocation risk:** no

---

### Rank 4 — Chaos Daemons Skarbrand Rage Embodied plus one Attack applies to ranged weapon profiles as well as melee

**Faction:** Chaos Daemons

**Code location:** `code/leaders.py:1076` (LeaderAbility `plus_one_attack=1`); `code/units.py:2249-2251` (applied inside per-weapon loop with no `mode == 'melee'` guard).

**Citation key:** `LeaderAbility.Rage Embodied`

**Verbatim cited rule:** "While a friendly KHORNE Legiones Daemonica unit is within 6\" of this model, add 1 to the Attacks characteristic of melee weapons equipped by models in that unit."

**Pattern:** scope-misapplied

**Recommendation:** build

**Estimated magnitude:** low

**Why faithful to remove:** The codex text restricts the plus one Attacks to MELEE weapons only. The `plus_one_attack` field is added to `n_attacks` for every weapon profile iterated in the per-weapon loop at `code/units.py:2249-2251` with no `mode == 'melee'` check. Sibling melee-only buffs in the same loop carry the guard (line 2359: `plus_one_to_hit_melee_only ... and mode == 'melee'`; line 2369: `plus_one_to_wound_melee_only ... and mode == 'melee'`), confirming the guard's absence here is a genuine scope error. The Skull Cannon (`chaos_daemons_library_skull_cannon`) and Khorne Soul Grinder (`chaos_daemons_library_khorne_soul_grinder`) are both in `_KHORNE_DAEMON_HOSTS` in `code/leaders.py:267-268` and both carry real ranged profiles, so the over-credit is live. The citation's `effect` field explicitly flags this: "plus_one_attack in SwegHammer applies the +1 to every weapon profile carried by the attacker, which over-includes the ranged profiles on Skull Cannon / Khorne Soul Grinder." Adding `and mode == 'melee'` to line 2250 narrows the sim to the cited rule, matching the established pattern used throughout the attack loop.

**Command-point reallocation risk:** no

---

### Rank 5 — Death Guard Lord of Contagion plus one to wound proxy fires in the ranged phase, but the real Vector of Disease rule is melee weapons only

**Faction:** Death Guard

**Code location:** `code/leaders.py:1278-1281` (LeaderAbility `plus_one_to_wound=True`, `host_keys=('death_guard_blightlord_terminators', 'death_guard_deathshroud_terminators')`); `code/units.py:2361` (`if att_buffs["plus_one_to_wound"]: wound_mod_delta += 1` — no mode guard).

**Citation key:** `LeaderAbility.Plague-Ridden Champion`

**Verbatim cited rule:** "Vector of Disease: While this model is leading a unit, melee weapons equipped by models in that unit have the [SUSTAINED HITS 1] and [LANCE] abilities."

**Pattern:** scope-misapplied

**Recommendation:** build

**Estimated magnitude:** low

**Why faithful to remove:** The verbatim rule grants Sustained Hits 1 and Lance on melee weapons of the led unit only. The proxy `plus_one_to_wound` is documented in the citation as a substitute for Sustained Hits 1 plus Lance on melee (neither keyword was modelled at the time); however the unconditional branch at `code/units.py:2361` fires in both the Shooting and Fight phases. Both Blightlord Terminators (`death_guard_blightlord_terminators`) and Deathshroud Terminators (`death_guard_deathshroud_terminators`) carry ranged weapons (Combi-weapon 24-inch range, Plaguespurt gauntlet 12-inch range respectively), so the spurious plus-one-to-wound fires on ranged attacks every Shooting phase the led unit activates. The melee-only siblings at `code/units.py:2359` and `2369` already carry the `and mode == 'melee'` guard; switching the Lord of Contagion to `plus_one_to_wound_melee_only` (which reads that guarded field) removes the ranged over-credit while retaining the faithful melee proxy. No stratagem firing is gated by this leader aura.

**Command-point reallocation risk:** no

---

### Rank 6 — Emperor's Children Lucius the Eternal carries mapper-generated Feel No Pain 5+ with no real codex source and no override correction

**Faction:** Emperor's Children

**Code location:** `data/bsdata/parsed.json` (unit key `emperor_s_children_lucius_the_eternal`, field `fnp=5`, confirmed at line 94752); `data/overrides.json:1097-1100` (override carries only `invuln_save=4`, no `fnp` key — so `fnp` falls through to 5 via the override merger at `code/bsdata/loader.py:656`).

**Citation key:** NONE — no entry in `data/rule_citations.json` or any file in `data/rule_citations.d/` covers a Feel No Pain 5+ ability on Lucius the Eternal.

**Pattern:** fabrication-no-citation (mapper prose-walk artifact)

**Recommendation:** build

**Estimated magnitude:** low

**Why faithful to remove:** The real Emperor's Children Lucius the Eternal datasheet (confirmed from BSData) carries the Armour of Shrieking Souls (4+ invulnerable save, wired correctly at `data/overrides.json:1097`) and Blissful Agony (retaliation mortal wounds on death) — no Feel No Pain ability of any threshold appears on his datasheet. The `fnp=5` in `parsed.json` is a mapper prose-walk artifact of the same class as already-corrected entries for Lion El'Jonson, Azrael, Saint Celestine, Celestian Insidiants, and others — all reset to 7 (no effective Feel No Pain) via overrides when it was discovered the mapper was pulling conditional or referenced Feel No Pain text from ability descriptions into the static unit profile. An exhaustive search of all `rule_citations` files found no citation for Lucius or any Emperor's Children Feel No Pain. The fix is to add `"fnp": 7` to the existing Lucius override at `data/overrides.json:1097`, matching the sibling mapper-sweep pattern and note style. No stratagem firing is gated by this static profile field.

**Command-point reallocation risk:** no

---

### Rank 7 — Chaos Daemons Daemonic Invulnerability stratagem grants a flat 4+ invulnerable save for the full round instead of a single re-roll of one failed invulnerable save

**Faction:** Chaos Daemons

**Code location:** `code/simulator.py:5639-5662` (`_try_daemonic_invulnerability`, fires at round start, calls `_set_transient_squad(target, "transient_invuln_4")`); `code/units.py:3350-3351` (`if target.transient_invuln_4 and invuln > 4: invuln = 4` — applied round-wide against all damage).

**Citation key:** `Stratagem.Daemonic Invulnerability`

**Verbatim cited rule:** "When: any phase, just after an invulnerable saving throw is failed for a model in a LEGIONES DAEMONICA unit from your army. Effect: re-roll that saving throw."

**Pattern:** passive-buff-too-broad

**Recommendation:** build

**Estimated magnitude:** medium

**Command-point reallocation risk:** yes — this gates a 1 command-point stratagem spend. The build MUST follow the Aeldari Fire and Fade pattern (keep the command-point spend active; replace or remove only the over-broad 4+ effect) so the command point is still consumed and cannot reallocate to a stronger stratagem.

**Why faithful to remove:** The real rule is reactive: it fires just after a single failed invulnerable save on one model and re-rolls that save (expected survival improvement roughly plus 8% on a 5+ invulnerable save, which describes standard Daemonettes and Plaguebearers). The simulator grants a flat 4+ invulnerable save for the entire round to the most vulnerable Chaos Daemons unit, proactively at round start — a roughly 25 percentage-point reduction in failed saves against the 5+ base, applied to all incoming damage. The citation's own `effect` field states the proxy is "strictly stronger than a failed-invuln-reroll on a typical 5+ Daemon invuln." The faithful remedy (established Aeldari Fire and Fade precedent from `SWEG_AELDARI_FNF_FAITHFUL`) is to keep the command-point spend firing but replace the over-broad transient with a faithful re-roll proxy (or drop the effect entirely, leaving only the spend), so the calibration economy remains honest. Not previously settled in `docs/DECISION_LEDGER.md`.

---

### Rank 8 — Death Guard Plague Company detachment has no real stratagem citation — the Awakened Dynasty Protocols placeholder has no Death Guard rule citation entry

**Faction:** Death Guard

**Code location:** `code/detachments.py:1522-1547` (PLAGUE_COMPANY `stratagems=AWAKENED_DYNASTY_STRATAGEMS`, verbatim comment: "Stratagem set kept as the Awakened Dynasty placeholder pending a real Plague Company stratagem pull"); `code/simulator.py:3329-3426` (dispatcher builds `strat_names` from the active detachment's stratagems with no faction filter and dispatches each Protocol by name).

**Citation key:** NONE — no entry in `data/rule_citations.d/death_guard.json` or any citation file covers any Plague Company stratagem. All Awakened Dynasty Protocol citations in `data/rule_citations.d/stratagems.json` target "NECRONS unit" explicitly.

**Pattern:** fabrication-no-citation

**Recommendation:** build

**Estimated magnitude:** high

**Command-point reallocation risk:** yes — each Protocol helper spends a command point through `_fire_stratagem` (`code/simulator.py:3784-3786`). Removing the firing frees those command points, which the AI may redirect into generic stratagems (Command Re-Roll, Counter-Offensive, Tank Shock). The expected magnitude reduction will be smaller than the gross buff value. The canonical faithful fix is to assign an empty stratagem tuple (pending a real Plague Company stratagem pull), not to add proxy Death Guard effects without citations. The eval expectation should reflect the reallocation caveat.

**Why faithful to remove:** The code comment at `code/detachments.py:1540-1542` is self-indicting: "Stratagem set kept as the Awakened Dynasty placeholder pending a real Plague Company stratagem pull." The Protocol dispatchers at `code/simulator.py:4414, 4441, 4470, 4492` each first seek a `keyword="NECRONS", faction="Necrons"` unit; when that returns None (as it always does on a Death Guard army), they fall back to an unfiltered `_highest_dpa_unit(army)` or `_most_vulnerable_unit(army)` call (the Rule-13 silent-fallback failure mode). Death Guard units then receive: transient wound regeneration (Protocol of the Undying Legions), plus one to wound in melee (Protocol of the Hungry Void), Assault keyword on ranged weapons (Protocol of the Sudden Storm), and reroll hit rolls (Protocol of the Conquering Tyrant). None of these are real Death Guard rules; there is no Death Guard citation for any of them anywhere in the repository. Plague Company is selected in roughly 40% of Death Guard games (confirmed by `DEFAULT_DETACHMENT_BY_FACTION` and `pick_detachment_for_army` at `code/detachments.py:2181-2228`). Assigning an empty stratagem tuple removes fabricated effects that have no Death Guard citation; this is a Rule 10 fabrication removal, not a metric nerf of a faithful mechanic. The sister candidate (code-angle, candidate 16 in the input) was refuted on command-point reallocation grounds; this candidate (citation-angle) was independently verified as a real fabrication and recommended for build with the reallocation caveat explicitly carried into the eval expectation.

---

### Rank 9 (hold) — Adeptus Custodes Arcane Genetic Alchemy grants Feel No Pain 5+ against all damage types for the full round, but the real rule is Feel No Pain 4+ against mortal wounds only until the end of the phase

**Faction:** Adeptus Custodes

**Code location:** `code/simulator.py:4701-4724` (`_try_arcane_genetic_alchemy` — fires at round start, sets `transient_fnp_5`); `code/units.py:1458-1459` (`if self.transient_fnp_5: effective_fnp = min(effective_fnp, 5)` — applied against ALL damage in the general damage-allocation path).

**Citation key:** `Stratagem.Arcane Genetic Alchemy`

**Verbatim cited rule:** "After a Mortal wound is allocated to one of your ADEPTUS CUSTODES units, until the end of the phase, models in that unit have a Feel No Pain 4+ against mortal wounds."

**Pattern:** passive-buff-too-broad

**Recommendation:** hold (requires paired A/B verification before landing, given command-point reallocation risk)

**Estimated magnitude:** low

**Command-point reallocation risk:** yes — this is a 1 command-point Battle Tactic stratagem (`code/simulator.py:3492-3505`). Narrowing the effect's value while leaving the firing gate active risks command-point reallocation into Archaeotech Munitions or Arcane Genetic Alchemy on a different unit.

**Why faithful to remove:** The simulator grants Feel No Pain 5+ against all damage types for the full round, proactively. The real rule is reactive (fires after a mortal wound lands), restricted to mortal wounds only, lasts only until the end of the current phase, and the threshold is Feel No Pain 4+ (strictly better than 5+). The scope broadening (all damage versus mortal-wound-only) dominates the magnitude weakening (5+ is weaker than 4+) because mortal wounds are a minority of incoming damage in typical Adeptus Custodes matchups. The citation's own `effect` field documents both the magnitude error and the scope error, and marks the entry as an approximation. Narrowing the Feel No Pain to mortal-wound damage only moves toward the cited rule and is faithful. Not settled in `docs/DECISION_LEDGER.md` for this specific entry. Held because the command-point reallocation risk means the metric direction may not land as expected; a paired A/B test scoped to Adeptus Custodes should confirm before adopting.

---

## REFUTED / SKIPPED (17 candidates not surviving)

| Candidate | One-line reason |
|---|---|
| World Eaters Apoplectic Frenzy targets highest-damage-per-activation unit instead of Khorne Berzerkers | Settled in `docs/DECISION_LEDGER.md` line 131 as user-reserved list-zone work (SWEG_WE_REALISM gate); faithful_to_remove=false; command-point reallocation risk. |
| World Eaters Beacons of Rage army-wide instead of 6-inch aura | The 6-inch-to-army-wide substitution is the project-wide universal aura abstraction applied identically to every faction aura; narrowing World Eaters alone would be an unfaithful selective nerf; faithful_to_remove=false. |
| Emperor's Children Keeper of Secrets cross-faction collision | Not an over-credit: the Emperor's Children Keeper of Secrets has its own independent codex aura (Legions of Excess keyword) that applies to exactly the same three units the simulator buffs; the sim reaches the codex-correct outcome via name-collision shortcut; is_real_overcredit=false. |
| Emperor's Children Chaos Spawn Feel No Pain 5+ | Not a mapper artifact: the BSData catalogue at `data/bsdata/cache/Chaos - Emperor's Children.cat.gz` carries a canonical Feel No Pain 5+ infoLink with modifier on the Chaos Spawn entry; fnp=5 is the real datasheet value; is_real_overcredit=false. |
| Chaos Daemons Shadow of Chaos Round 1 firing | Not an over-credit: the simulator previously skipped Round 1 and the fix that re-enabled it (simulator.py:9097-9099, iter-13) was deliberate; the always-on deployment-zone leg and Greater Daemon aura are live in Round 1 under the real rule; the 18-inch midboard proxy is a blended approximation of the always-on leg plus contested mid-board; gating to Round 2+ would be a fidelity regression; is_real_overcredit=false. |
| Chaos Daemons Warp Surge Shadow gate dropped | Real over-credit but faithful_to_remove=false (selective narrowing of one of ten sibling advance-and-charge proxies that all share the same always-on approximation); command-point reallocation risk (frees command point to Daemonic Invulnerability or stronger stratagem). |
| Necrons Protocol of the Conquering Tyrant led-branch melee bleed | Real over-credit but settled/wrong-direction: the Conquering Tyrant mechanism is a documented suboptimal command-point sink; narrowing its value reallocates the command point to a stronger stratagem and makes Necrons stronger (DECISION_LEDGER.md line 99, built-rejected-reverted 2026-06-15). |
| Necrons all detachments share Awakened Dynasty Protocol stratagems | Real over-credit (Cursed Legion, Annihilation Legion) but the same command-point reallocation backfire as the Conquering Tyrant lesson; removing the Protocol pool from Cursed Legion frees command points for generic stratagems and makes Necrons stronger. |
| Necrons Protocol of the Conquering Tyrant unled-branch full-range instead of half-range | Settled/wrong-direction: this is the exact `SWEG_NECRON_CT_HALFRANGE` gate that was built, rejected, and reverted 2026-06-15 (Necrons 60.9 -> 63.3, decisive worse); per-shot range infrastructure does not exist; faithful_to_remove=false for any buildable form. |
| Necrons Protocol of the Hungry Void plus one to wound instead of plus one Strength | Real over-credit but faithful_to_remove=false: a truly faithful fix requires building a per-attack Strength-versus-Toughness comparison slot that does not exist; the dropped plus one Armour Penetration if-led leg partially compensates the overshoot; command-point reallocation risk; recommendation=hold. |
| Death Guard Plague Company Necron Protocol stratagems (code-angle candidate) | Real over-credit but command-point reallocation risk explicitly refutes it via the Conquering Tyrant lesson; the empty-tuple removal frees command points for generic stratagems; refuted by the verifier on cp_reallocation_risk grounds. Note: the citation-angle twin (Rank 8 above) was independently verified as build with the reallocation caveat carried in the eval expectation. |
| Adeptus Custodes Multipotentiality fires every round, not just after fell-back | Real over-credit but faithful_to_remove=false: the simulator has no opponent-phase reactive fell-back hook; the round-start dispatcher cannot observe a "just Fell Back" event; narrowing to require a fell-back-this-round trigger would never fire and would effectively delete a real stratagem; command-point reallocation risk. |
| Adeptus Custodes Auric Champions uses Shield Host stratagems it does not own | Real over-credit but faithful_to_remove=false: Auric Champions is a real detachment with its own stratagem pool (not yet wired); the canonical fix is to build and cite the real Auric Champions stratagems, not remove them (which would zero out a real stratagem economy and trigger command-point reallocation into generic stratagems). |
| Shield Host Ka'tah always picks offensive Rendax Armour Penetration plus one, never defensive Kaptaris | Not an over-credit: the sim is a strict subset of the codex (applies Rendax on odd rounds only, at most 3 of 5, never always); the Kaptaris stance being absent is a completeness gap not a scope excess; is_real_overcredit=false. |
| Disgustingly Resilient duration broadened from one phase to full round | Not an over-credit: the phase-to-round duration extension is the project-wide universal transient-flag convention applied identically to approximately forty other stratagem sites across all factions; narrowing only the Death Guard instance is a forbidden selective metric nerf; is_real_overcredit=false (the over-broadening is architecturally uniform). |
| Contagions of Nurgle Round 3-plus hit penalty fires on melee attacks, but real rule is Ballistic Skill (ranged) only | The in-repo citation (`data/rule_citations.d/death_guard.json`, `simulator.contagions_of_nurgle`) describes Fulminating Plague as a generic minus one to Hit with no ranged-only restriction; the candidate's Ballistic-Skill-only claim is an external Wahapedia paraphrase that contradicts the in-repo citation; grounded_in_citation=false per the project's citation-primary standard; is_real_overcredit=false against the in-repo source. |
| Beacons of Rage cross-faction duplicate (cross-faction candidate list entry) | Same as the World Eaters Beacons of Rage candidate above: the army-wide-alive substitution is the universal aura-position abstraction; faithful_to_remove=false; also the subject of the World Eaters stand-alone candidate already adjudicated. |

**Total refuted or skipped: 17**

---

## Recommended build order for the next campaign

The nine survivors divide into two natural waves based on command-point reallocation risk.

**Wave A — passive-buff removals (no command-point risk, build confidently):**

Build Ranks 1 through 6 as bundle-of-one agents on separate worktrees. Each is a
data-only or small code edit with no stratagem firing gated by the change:

1. World Eaters Blood Tithe Lethal Hits — scope to one named unit + one phase
   (two code edits in `code/units.py` and `code/simulator.py`)
2. World Eaters Blessings of Khorne — add `has_blessings_of_khorne` flag to
   `UnitProfile`, set from BSData infoLink presence in the mapper, gate all three
   Blessing legs on the new flag
3. Death Guard Typhus Destroyer Hive — replace `fnp=5` on Plague Marines led by
   Typhus with a melee-only minus-one-to-Hit proxy (or gate `tgt_fnp_buff`
   application to `mode == 'melee'` as an interim while the `hit_penalty_melee`
   mechanic is built)
4. Chaos Daemons Skarbrand Rage Embodied — add `and mode == 'melee'` guard to the
   `plus_one_attack` branch at `code/units.py:2250`
5. Death Guard Lord of Contagion — switch the `plus_one_to_wound` field to
   `plus_one_to_wound_melee_only` at `code/leaders.py:1278` (the mode-gated variant
   already exists at `code/units.py:2369`)
6. Emperor's Children Lucius the Eternal — add `"fnp": 7` to the override at
   `data/overrides.json:1097`, matching the existing mapper-sweep sibling pattern
   (Lion El'Jonson, Azrael, Saint Celestine citations)

Screen all six together in one Adeptus Custodes-and-over-pole-scoped paired run
versus the sc16a anchor before adopting.

**Wave B — stratagem-effect narrowings (command-point reallocation risk; build
with mandatory paired verification):**

7. Death Guard Plague Company empty stratagem set — assign an empty stratagem
   tuple to `PLAGUE_COMPANY` at `code/detachments.py:1544`, pending a real Plague
   Company stratagem pull with proper citations; screen paired, scoped to Death Guard,
   vs sc16a; carry the reallocation caveat in the eval expectation (expect a smaller
   improvement than the gross buff value suggests)
8. Chaos Daemons Daemonic Invulnerability — follow the Aeldari Fire and Fade
   pattern: keep the 1 command-point spend firing but replace `transient_invuln_4`
   with a faithful re-roll proxy (or drop the transient effect entirely); screen
   paired, scoped to Chaos Daemons, vs sc16a

**Wave C — hold (verify before adopting):**

9. Adeptus Custodes Arcane Genetic Alchemy — implement mortal-wound-only scoping
   of the Feel No Pain; run a paired A/B test scoped to Adeptus Custodes vs sc16a;
   adopt only if the direction is confirmed positive at the scoped N before running
   the campaign-end full re-anchor
