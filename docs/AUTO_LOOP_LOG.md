# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 69 close (2026-05-31)

Branch `claude/sim-calibration-6`. The win-win under-performer track: a 6-agent
faction-rules deep-dive (5 under-performers + an over-performer over-buff audit),
then implement each under-performer's missing rules — all verify-first against
Wahapedia/BSData (the over-performer audit's "phantom Aeldari Aspect-Warrior invuln"
claim was DEBUNKED on verification: Dark Reapers genuinely have a 5++). Five worktree
agents implemented, cherry-picked clean.

LANDED (gated 8.74 → 8.29):
- **Imperial Knights −21.8 → −16.0** (+5.8): real Valourstrike Lance detachment
  (Bold Gallantry advance→assault) + Bondsman abilities (Questoris buff Armigers each
  Command phase). Remapped off the empty Imperial-Knights `noble_lance`.
- **Chaos Daemons −19.0 → −14.6** (+4.4): per-god datasheet buffs — Tzeentch 4++
  correction (only the genuine ones, 5++ units left alone), Murderer's Cowl
  (advance+charge), Penumbral Puppetry (-1 to hit), Gloam Rot (-1 wound vs S>T).
- **TOWERING line-of-sight** (cross-faction): Obscuring/Ruins don't block LoS for
  TOWERING models — helps Knights/Wraithknight guns.
- **Chaos Knights** real Iconoclast Fiefdom detachment (Dread Tyrants aura) + **GSC**
  Patriarch/Primus leaders + Aberrant FNP.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 68 close (core-rules batch) | 12.05 | 8.74 | 5/22 |
| **Wave 69 close (faction buffs)** | **11.57** | **8.29** | **5/22** |

CAUGHT + REVERTED: **CSM Dark Pacts per-unit** auto-gamble crashed CSM 45.8→24.8%
(self-inflicted D3 mortal wounds on every squad every round outweigh the buff; real
players are selective — task #36). **Chaos Knights** barely moved from the detachment
alone (+0.5) — its −38 is AI-positional (the reverted durable-objective diagnostic
moved CK −38→−8.8), so CK needs the objective AI (#12). GSC's small −2.1 is
redistribution from the IK/Daemons buffs (verified-correct, not a bug). 926 tests
green; audit 288/288. Eval `data/wf_wave69b_n40.json`.

## Wave 68 close (2026-05-31)

Branch `claude/sim-calibration-6`. Fidelity-first wave from the full 10e core-rules
audit (`docs/CORE_RULES_AUDIT.md`). Rule correctness prioritised over the headline.

- **Heroic Intervention REMOVED** (`simulator.py` `_do_heroic_intervention` + call
  + citation + audit key + test file): not a 10e rule (9e mechanic deleted at 10e
  launch). It fired free for every defending CHARACTER within 6" of a charger.
- **Fall Back Desperate Escape gated**: only when the unit is Battle-shocked OR its
  path crosses an enemy model (new `_fall_back_crosses_enemy` point-to-segment
  helper); a clean disengage now takes no test (was ~1/3 model loss every time).
- **Indirect Fire**: added the unmodified-1-3-always-fails and the auto-Benefit-of-
  Cover (was only applying the -1 to hit).
- **In-engagement + Blast targeting**: a Pistol/Big-Guns shooter in engagement may
  only target units it is engaged with; Blast can't target a unit within ER of the
  bearer.
- **Unmodified Hit 6 always hits** (was missing under -1 on a 6+ profile; wound side
  already correct). **Disembark** skips points within 1" of an enemy. **Battle-shocked
  units** fight at the start of Remaining Combats.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 67 close (per-unit batch ×6) | 11.11 | 7.80 | 5/22 |
| **Wave 68 close (core-rules batch)** | **12.05** | **8.74** | **5/22** |

Headline rose +0.94 (deliberate fidelity-first): Chaos Daemons −13.7→−19.0 (HI
removal correctly weakened a Character-heavy melee army the fabrication propped up),
Aeldari/Sororitas further over (Fall Back fix lets them disengage + keep firing).
919 tests green; audit 280/280. The archetype re-fit (task #22) is the gating next
step. Eval `data/wf_wave68_corerules_n40.json`. CP economy (3-start/6-cap) and
movement coherency left as open audit items (#7, #8).

## Wave 67 close (2026-05-31)

Branch `claude/sim-calibration-6`. Six per-unit-mechanics fixes from the wave-66
audit, built in parallel (one worktree agent each) and cherry-picked to `ba2a8b4`:

- **Unit coherency** (`971348d`): `_deploy_line` clusters each squad at one slot;
  `_score_objectives` credits each squad's Objective Control to a single objective
  (was per-model multi-objective). New `simulator.unit_coherency` citation.
- **Per-unit secondaries** (`c068f47`): No Prisoners / Cull the Horde count
  destroyed UNITS via squad_id last-model, not models.
- **Reanimation / Undying Legions** (`a4d091d`): group alive/dead by squad_id; a
  wiped squad can't revive off a same-name squad.
- **Stratagem transient buffs** (`2d07062`): `_set_transient_squad` fans the buff
  to the whole squad (60 sites) instead of one model.
- **Per-squad battleshock + Mob Rule** (`c2bdc96`): one test per squad,
  below-half-strength by squad model count, Mob Rule by squad_id.
- **Once-per-unit gate re-keys** (`f5f8834`): Oath, Acts of Faith, Strands,
  Miracle die, Markerlight, Blood Surge, Beacons → squad_id.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 66 close (mortal+demise+blast) | 11.08 | 7.56 | 3/22 |
| **Wave 67 close (per-unit batch)** | **11.11** | **7.80** | **5/22** |

Rules-correct; 922 tests green; citation 281/281. Gated +0.24 but in-band 3→5;
Necrons +4.2→−1.3 (reanimation), Drukhari +30.1→+27.8 (coherency). The headline
rise is one faction — **Adepta Sororitas +10.1→+17.2** (gated 6.3→13.4): stratagem
+ Acts-of-Faith now correctly buff the whole squad, past a list tuned on the old
bugs. Next: archetype-list re-fit (task #22), Sororitas first. Eval
`data/wf_wave67_perunit_n40.json`.

## Wave 66 close (2026-05-31)

Branch `claude/sim-calibration-6`. The mortal-wound half of the damage-allocation
rule, plus two per-unit fixes a user question surfaced, plus a full per-unit
mechanics audit.

- **Mortal-wound spillover** (`Battle._apply_mortal_wounds`, cited
  `simulator.mortal_wound_spillover`): unlike normal damage (excess lost),
  mortal wounds carry to the next model of the unit until spent or the unit dies
  (Feel No Pain per wound). Routed Doombolt, psychic-detachment payload,
  Bloodthirster, Tank Shock, Dark Pact, Leechspore.
- **Deadly Demise per-unit**: "each unit within 6\" suffers X" was being dealt to
  each MODEL (over-dealing by squad size). Now grouped by `squad_id`, dealt once
  per unit.
- **Blast scoping**: counts models in the targeted UNIT via `squad_id`, not every
  same-`profile.name` model across the army.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 65 close (spillover+docs) | 11.15 | 7.78 | 2/22 |
| **Wave 66 close (mortal+demise+blast)** | **11.08** | **7.56** | **3/22** |

Small, rules-correct net positive. 912 tests green; citation 280/280 (new
`simulator.mortal_wound_spillover`). Eval `data/wf_wave66_mortal_n40.json`.

**Per-unit-mechanics audit** (`docs/PER_UNIT_MECHANICS_AUDIT.md`, four parallel
read-only agents): the one-Unit-per-model representation mis-applies many per-unit
10e rules; `squad_id` is the fix key. Top open items → tasks #23-28: coherency wave
(deployment clustering + OC-per-unit, likely the remaining horde-overshoot lever),
per-unit secondary scoring (No Prisoners / Cull count models not units), Reanimation
profile.name→squad_id pooling (over-revives wiped Necron squads — Necrons drifted
+0.6→+4.2 this wave), stratagem transient-buff propagation, per-squad battleshock.

## Wave 65 close (2026-05-31)

Branch `claude/sim-calibration-6`. The biggest fidelity fix in many waves, found
by a user question about how a Knight's shots resolve into a multi-model unit:
**damage-allocation spillover**. The engine was dumping a whole volley into ONE
model of the target unit and wasting the overkill — so a high-volume anti-horde
gun killed one model and the rest was lost. Now `Unit.attack` allocates each
unsaved wound to the next surviving same-`squad_id` model (10e core rule), with a
destroyed model's excess damage lost; kills are bounded by unsaved-wound count,
not damage total. Built on the same-session P1 `squad_id` infrastructure
(behaviour-neutral). The contained activation-overlay experiment (P3) was a wash
(+0.03) and was reverted — the firepower/allocation rule was the real lever, as
the wash predicted. Devastating Wounds is correctly treated as normal allocation,
NOT a mortal wound (per user correction).

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |
| **Wave 65 close (spillover+docs)** | **11.15** | **7.78** | **2/22** |

Moved exactly the structural-residual factions: Tyranids +16.8→+6.4 (−10.4),
Imperial Knights −27.1→−19.1 (+8.0), Orks +12.5→+5.3, Drukhari +36.2→+29.0,
Chaos Knights −41.3→−36.5, AdMech +11.9→+7.3. Second-order: elite/MEQ armies
(Custodes, Marines, Thousand Sons, Aeldari) drifted further over — re-fit
candidates. 912 tests green; citation audit 279/279 (new
`simulator.damage_allocation_spillover`). Eval artifact
`data/wf_wave65_spillover_n40.json`.

Next: archetype-list re-fit for the new elite over-shoots; mortal-wound spillover
(separate rule, not yet done); per-kill trigger emission under spillover.

## Wave 64 close (2026-05-30)

Branch `claude/sim-calibration-6`. First wave of the AI-tactics-implementation
campaign — a 16-tactic audit (research real competitive 10e tactics, verify
each against the sim AI) found the AI can organically do NONE fully (11 CANNOT,
5 PARTIAL); the gaps became tasks #12-16. This wave lands the first: a
rules-correct AI capability, consolidate-onto-objective.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 63 close (`96fd68e`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |

**FIGHT-AI-CONSOLIDATE-OBJECTIVE** (`3203e35`): the 10e Consolidate move now
goes up to 3" onto the nearest objective marker when combat clears (no enemy
reachable) — previously a no-op in that case. Audit 278/278 (new
`simulator.consolidate_objective` key + citation). Headline UNCHANGED — the
trigger (combat fully cleared with an objective within 3") is low-frequency,
below the N=40 noise floor; the effect surfaces at higher N. Rules-correct,
zero regression, pytest 912 → landed.

Campaign progress: #14 done. Next #16 (Heroic Intervention already-engaged
gate + Counter-Offensive firing), #15 (target priority by VP-plan), #13
(repulsion/denial positioning), #12 (plan-level + lookahead objective function).

## Wave 63 close (2026-05-30)

Branch `claude/sim-calibration-6`. One rules-correct fix: World Eaters Blood
Tithe was over-accruing. Notable as a verify-first save and as the second
rejected→corrected attempt at the WE over-shoot.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |
| Wave 63 close (`96fd68e`+docs) | 12.80 | **9.27** | 2/22 |

-0.12 gated. Clean: World Eaters down toward target, ZERO cross-faction
regression (only WE accrual touched).

### WE-BLOODTITHE-PERUNIT (`96fd68e`)

World Eaters over-shot (sim 56.4, target 47.0, gated 6.01) — a wave-61
fall-back-gate side effect that turned out to expose a real bug.
`_maybe_award_blood_tithe` awarded +1 Blood Tithe on every `UnitKilled`, but
in the one-Unit-per-model representation that fires per MODEL, while the codex
awards per UNIT destroyed. A WE squad wiping a 10-model enemy unit over-accrued
+10 BT instead of +1 — the **8th catalogued instance of
`project-one-unit-per-model-amplification`**. Fixed with the standard
last-living-model dedup (award only when no sibling sharing the victim's
profile.name survives in its army).

Result (N=40): WE gated 6.01 → 4.46 (-1.55, toward target); Emperor's Children
-0.48 and Marines -0.48 (collateral improvement — WE's opponents win their
matchups more); NO regressions. Headline 9.39 → 9.27.

### Verify-first save

The read-only WE diagnostic proposed a much larger "fix": add a D6 3+ accrual
gate, remove the friendly-WE-death trigger, and rewrite the spend table —
claiming Blood Tithe is a Khorne Daemonkin *detachment* rule. ALL THREE
contradict the sim's own cited Wahapedia rule (`world_eaters.json`): the WE
**army** rule awards on friendly death AND enemy kill, with NO dice roll, and
the spend table the sim implements (4 = Lethal Hits, 3 = +1 Command point) is
correct. The agent conflated two different rules. Checking the proposed change
against the existing citation before applying caught it — only the narrow
per-model amplification was real.

### Process — a rejected attempt first

The first wave-63 attempt (a "critically-wounded melee units may Fall Back
below 35% HP" gate, commit `88c4920`) was REJECTED: it helped WE (-1.90) and
Emperor's Children (-1.19) but regressed exactly the horde/monster factions
wave 61 had calibrated (GSC +1.91, Tyranids +1.19, Orks +0.95), net headline
9.39 → 9.52. Lesson: a faction-neutral AI gate ripples across every melee
faction; run the full per-faction gated diff before landing, not just the
headline. pytest 912 passed; audit well-formed. Eval `data/wf_wave63_n40.json`.

### Open carry-forwards into wave 64

1. **Necrons detachment fabrications** (task #9) — rules-correct but
   MAE-negative (Necrons under-shoots); handle with care.
2. **Detachment citation/comment fixes + Grey Knights deep-strike gate** (#10).
3. **Strategy roadmap #1** (task #6 review) — a plan-level objective function;
   the next big systemic lever, like the wave-61 fall-back fix.

## Wave 62 close (2026-05-30)

Branch `claude/sim-calibration-6`. One fix — the first item from the
detachment-fabrication sweep. Recovered from a stalled background agent: its
work was already committed (`91e0e33`) and cherry-picked as `e1346a1`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |

Headline flat (within noise) — a single-detachment correctness fix, not a
systemic one like wave 61.

### CUSTODES-AURIC-CHAMPIONS (`e1346a1`)

The default Custodes eval detachment carried `melee_sustained_hits_army_wide
=True` citing "Trail of Glory" — a fabrication on two counts: the cited rule
name is wrong (the real rule is "Assemblage of Might"), AND an army-wide
Sustained Hits proxy doesn't match it. Assemblage of Might designates one
enemy unit per Command phase and grants +1 wound to ADEPTUS CUSTODES
CHARACTER units against only that target — a designate-one-target +
CHARACTER-only mechanic the Detachment schema cannot proxy without
fabricating. The flag was REMOVED (a no-op is more rules-correct than a
fabrication) and its citation deleted; the shared Orks War Horde consumer of
the same flag is untouched (its gate logic is unchanged).

Custodes over-shoots, so removing the buff is direction-correct AND
MAE-positive: Custodes sim 57.1 → 56.5 (target 52.1), gated 2.39 → 1.80 —
now near in-band. The headline didn't move because one faction's -0.59 gated
averages to ~-0.03 across 22 factions.

### Process

- Recovered a stalled async agent — its fix was committed but it never
  reported back. Cherry-picked the commit directly rather than re-running.
- pytest 912 passed; audit 277/277 (one fewer required key — the removed
  fabrication flag). Eval `data/wf_wave62_n40.json`.

### Open carry-forwards into wave 63

1. **World Eaters / CSM over-shoot** from the wave-61 fall-back gate — re-tune.
2. **Necrons detachment fabrications** (task #9) — rules-correct but
   MAE-negative (Necrons under-shoots); handle with care, don't blind-remove.
3. **Detachment citation/comment fixes** (task #10) — low-risk.
4. **Strategy roadmap #1** (task #6 review) — a plan-level objective function;
   the big systemic lever, like the wave-61 fall-back fix.
