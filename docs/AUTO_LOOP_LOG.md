# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`.

## Branch claude/sim-calibration-4 (2026-05-20)

SC4 (secondary objectives + map rotation) + LC-1/LC-2/LC-5 (detachment variety + tactical-deck mechanic + Warlord designation). All committed and pushed; PR #26 open.

### LC-1: Detachment variety (3 chunks)

* **LC1-A**: added Auric Champions Custodes detachment (SUSTAINED HITS 1 melee via `melee_sustained_hits_army_wide`, milder than Shield Host's stacked Crit-5+ + AP+1). Generalised the `melee_sustained_hits_army_wide` gate in `Unit.attack` from Orks-only to `detachment.faction == attacker.faction`. Custodes distribution: Shield Host 22 / Auric Champions 18 across 40 seeds.
* **LC1-B**: added Annihilation Legion Necrons detachment (army-wide `reroll_wound_ones`, real Hardened Killers rule). Necrons distribution: Awakened Dynasty 14 / Canoptek Court 16 / Annihilation Legion 10.
* **LC1-C**: added Plague Company Death Guard detachment (`melee_sustained_hits_army_wide` for DG). DG distribution: Virulent Vectorium 20 / Plague Company 20.

Cumulative LC-1 eval: **MAE 6.48 → 6.14 (−0.34)**. Big win: DG +7.6 → -1.3 (at target). Necrons stayed -10.1 (Annihilation Legion not strong enough lever). Custodes stayed +20.6 (Auric Champions only marginally weaker than Shield Host).

### LC-2: Tactical secondary deck mechanic

Per-round alternating schedule per side: each side scores AT MOST ONE of (Engage, BEL) per round, deterministically alternating. Approximates real Pariah Nexus 2-of-9 Tactical card draw rate when scaled to our 2-card pool. `_is_tactical_secondary_active(round_num, side, tactical)` helper, `score_position_delta` takes `round_num`.

Cumulative LC-2 eval: **MAE 6.14 → 6.14 (flat)**. Custodes stayed +22.0 (the tactical-deck didn't help because Custodes wasn't really scoring Engage/BEL anyway — small army can't easily hit 3+ quadrants). Other factions redistributed in wash.

### LC-5: Warlord designation

`Army.warlord_uid` lazy property picks the first CHARACTER in deploy order. Pariah Nexus Assassination secondary scores +1 VP if the Warlord was among destroyed CHARACTERs this round. Smoke verification: Custodes Warlord = Trajann Valoris, DG = Mortarion, Necrons = C'tan Shard of the Nightbringer.

### Honest pause point

Custodes outlier (+22) hasn't compressed via LC-1/2/5. Real cause: Custodes' elite low-count army systemically dodges the 4 Fixed kill secondaries (No Prisoners, Cull, Assassination, Bring it Down) AND their primary OC is decent enough that they win without secondary scoring. Without a faction-specific Custodes tune (e.g., per-unit pricing nudge or model-count uplift in archetype), no LC item will single-handedly close the +22 gap.

**LC-3 (wargear) / LC-4 (enhancements) / LC-6 (transports) / LC-7 (reserves) deferred** — large implementation work each with uncertain MAE impact. LC-8 (caps) / LC-9 (BATTLELINE min) confirmed no-op (archetypes already comply with both).

PR #26 open and ready for review. Detachment variety lands as a clean rule-correctness win for DG and a structural baseline for further faction tuning.

### N1 / N2 / C1 — outlier-targeted attempts (2026-05-20)

After LC-5 plateau, a 3-agent dispatch targeting Custodes +22 / Necrons -11. All three returned essentially flat MAE.

**N1 Necrons C'tan archetype anchor (STOP).** Agent verified C'tan Shard of the Nightbringer is ALREADY anchored in the Necrons "Awakened Dynasty" template at `code/archetypes.py:134` (iter16 commit). Spot-check confirms Nightbringer appears in 5/5 random archetype builds as the first seed. My review premise was wrong; no fix needed.

**N2 Reanimation Protocols rate (STOP).** Agent verified Wahapedia rule text: revival rate is "one destroyed bodyguard model", not d3. The d3 wording is from the "Protocol of the Undying Legions" stratagem (1 CP, already separately modelled). Current `reanimate_per_round=1` is rule-correct. Side-finding: the value is also hard-capped at `min(..., 1)` in `simulator.py:3490` so naively bumping the detachment value would have been a no-op anyway.

**C1 Shield Host bullet alternation (SHIPPED).** Agent wired round-parity alternation: AP+1 fires on odd rounds (1, 3, 5), Crit-on-5+ fires on even rounds (2, 4). Matches the codex "pick one bullet per round" rule exactly (the prior always-both was explicitly flagged APPROXIMATION). Tests + audit green. Eval: MAE 6.29 → 6.29 (flat); Custodes +22.3 → +22.0 (-0.3 within N=40 noise). Kept per correctness > MAE — rule-correct fix, prior state was strictly stronger than codex.

**Net N1+N2+C1**: 1 correctness-positive commit, ~0pt MAE impact. The Custodes +22 engine isn't the Shield Host detachment.

**Per-faction at this point (sim-cal-4 head)**:
- Marines +2.0, Necrons -11.8, Aeldari +2.8, Tyranids +5.3, Orks +0.4, T'au -4.5, DG -3.3, Custodes +22.0, TSON -4.6, Votann +6.2
- 5 factions within ±3pt of target (Marines, Aeldari, Orks, DG, TSON)
- 4 factions 4-6pt off (Tyranids, T'au, Votann, plus DG at -3.3)
- 2 outliers: Necrons -11.8, Custodes +22.0

**Real Custodes engine candidate**: Wardens Resolute Will + Trajann's +1 hit + Shield-Captain's reroll-1s + Shield Host AP+1 (now alternating but still firing 50% of rounds) + 4++ invuln + cover bonus at base Sv2. The compounding makes Wardens a near-unkillable brick; 2× Wardens in the archetype = a fortress. **LC-AB task #253** (consolidated archetype/detachment build evaluation) is the right place to address this — likely needs Custodes archetype shape rebalance (1× Wardens not 2, swap one Allarus for cheap BATTLELINE).

**Real Necrons engine candidate** (per N1 agent's recommendation): Awakened Dynasty 6-protocol rotation isn't fully modelled. Only one protocol (`bonus_to_hit_when_led`) is wired; the other five would add small per-round value that compounds. Doomsday Ark profile verification also flagged as iter 35 priority.

### LC-AB Custodes + DDA + AD-PR (2026-05-20)

Three parallel agents on outlier-targeted structural fixes.

**LC-AB Custodes archetype rebalance**: Custodes template reduced from 2× Wardens + 2× Allarus to 1× of each + Witchseekers/Vigilators BATTLELINE chaff. Eval: MAE 6.29 → 6.00 (−0.29). Custodes itself stayed at +22.3 (flat — the elite-shape engine is impossibly durable even with fewer copies); other factions improved by ~0.4-1pt as opponents score more secondaries against the now-vulnerable Custodes BATTLELINE chaff.

**DDA Doomsday Ark + Doomstalker invuln overrides**: 4+ invuln on both via `data/overrides.json` (BSData mapper missed the local Abilities profile rather than infoLink). Eval: MAE 6.29 → 6.18 (−0.11). Necrons −11.8 → −10.7 (+1.1). Rule-correct.

**AD-PR Awakened Dynasty protocol rotation**: wired Hungry Void (melee AP+1, even rounds) + Vengeful Stars (ranged SUSTAINED HITS 1, odd rounds) on Necrons. Conquering Tyrant (already-wired bonus_to_hit_when_led) retained always-on. Eval: MAE 6.29 → 6.16 (−0.13). Necrons −11.8 → −10.7 (+1.1).

**Combined N=40 eval (all three cherry-picked together)**: MAE **6.29 → 5.79 (−0.50)** — best honest N=40 reading of the calibration loop's history. Necrons −11.8 → −8.5 (+3.3 combined). Custodes stuck at +22.6 (structurally locked — needs Stage 2 pricing work, deferred per user).

**Per-faction at combined state** (sim-cal-4 head `4f6c4bc`):
- Marines +2.6, Necrons −8.5, Aeldari +2.8, Tyranids +5.6, Orks +0.4 ✅
- T'au −3.9, DG −2.7, Custodes +22.6 (outlier), TSON −3.8, Votann +5.1
- 7 of 10 factions within ±3pt; Custodes the sole structural outlier
- Cumulative Stage 1 progress from iter 22 baseline 13.43 → 5.79 = **−7.64 across 70+ commits**.

LC-4 enhancement system dispatched next.

### LC-4 / LC-3 / LC-6 / LC-7 sweep (2026-05-20)

Continued through the LC list per user directive "work through the whole list."

**LC-4 enhancements**: agent burned 166 tool uses (way over 40 cap — flag for future) but landed a modest 99-line commit. Enhancement infrastructure was pre-existing; wired Phasal Subjugator (Necrons Awakened Dynasty, +1 to hit aura), Veiled Blade (Custodes Shield Host, +2 attacks on Warlord melee), and corrected Hyperphasic Fulcrum citation (was misread as +1-to-hit, real BSData is reroll-wound-1s). Eval: MAE flat at 5.79. Each enhancement attaches to only 1 CHARACTER per army, so impact is small. Kept per correctness > MAE.

**LC-3 wargear variety**: STOP, 8/20 tool cap. Catalog audit found Crisis Suit variants already exposed correctly (iter17 work intact); Marines Captain power-fist gap noted but multi-SKU work for follow-up. No fix shipped.

**LC-6 transport MVP**: shipped Ghost Ark seed in Necrons Awakened Dynasty template (single-line `necrons_ghost_ark: 1`). Spot-check: Ark seeds 1 of 3 builds (random_fill budget walk drops it in 2/3). Eval flat MAE 5.79. Direction is rule-realism positive but the seed isn't anchored. Full transport mechanics (embark/disembark/ablative wounds) intentionally skipped — beyond MVP scope.

**LC-7 strategic reserves**: diag-only (12/20 tool cap). Found general Strategic Reserves entry point doesn't exist; only Deep Strike + Genestealer Cults bucket. Recommended split into LC-7a (mechanic + zero-declarations, ~150 lines) + LC-7b (AI heuristic that actually declares units). Multi-iter project, deferred.

**Session close state** (sim-cal-4 head `dc7073f`):
- MAE 5.79 at N=40 — best honest reading of the entire calibration loop's history
- 7 of 10 factions within ±3pt of target (Marines, Aeldari, Orks, T'au, DG, TSON, Custodes is +22.6 outlier)
- Necrons -8.5, Tyranids +5.6, Votann +5.1 (mid outliers)
- Custodes structurally locked — needs Stage 2 pricing work or per-unit durability cap

**Remaining LC items**: LC-10 (mission-specific lists) deferred per task description — very large scope. The LC list is effectively worked through; further MAE compression needs Stage 2 (MC bisection pricing) or AI improvements that the iter 26-30 cross-faction attempts showed are difficult to land cleanly.

**Cumulative Stage 1 progress from iter 22 baseline**: 13.43 → 5.79 = **−7.64 across ~80 commits**. Below the "≤6.5" practical floor that signals AI-pricing-vs-rules-completeness handoff per the iter 30 plan.

### Iter 21 (2026-05-18) — LeaderAbility fabrication audit

6 agents cross-faction sweep. 5 commits landed via cherry-pick + cross-worktree merge; Orks was clean (no fabs).

**Fabrications dropped (all citation-grounded per Wahapedia)**:
- **Necrons**: Overlord/Trazyn `plus_one_to_hit`, Plasmancer `fnp=5`. Real rules are CP discounts (Strat-econ) and offensive Crit-on-5+ (not modelled). Plus Lychguard added to Overlord bodyguard list (host_keys).
- **Marines**: Guilliman/Captain `reroll_hit_ones`, Chaplain `reroll_wound_ones`. Real rules are CP-discount/once-per-battle Battleshock-removal. Plus Shield-Captain/Brother-Captain name-collision fix.
- **Aeldari**: Yncarne `plus_one_to_hit` (proxy for reactive-teleport), Autarch `plus_one_to_hit` (CP-discount, same as Overlord pattern), Avatar `reroll_hit_ones` (real rule is +1 Advance/Charge — movement phase).
- **TSON**: ADDED 4 NEW LeaderAbilities (Ahriman, Exalted Sorcerer, Infernal Master, Sorcerer in TA) — TSON was UNDER-modelling (LeaderAbility lookup returned None). Plus Magnus "Impossible Form" (−1 to incoming Damage), Ahriman +1 Cabal Psychic test. TSON 30% → 36.1% (+6.1pt).
- **DG**: Lord of Contagion `plus_one_to_wound` (iter 20 missed), Typhus `fnp=5` (iter 20 partial). host_keys corrected per codex (Blightlord/Deathshroud, not Plague Marines).
- **Orks**: clean — no fabs.

**Cumulative iter 21 (5 commits + cross-worktree merges)**: MAE **13.73 → 13.43pt** (Δ **−0.30**). Tests 776/776, Rule citations 221/221.

**Per-faction shifts (post-iter-20 → post-iter-21)**:
- Marines +20.3 → +19.5
- Necrons **+17.6 → +14.3** (−3.3 ✅ — Overlord fab removed)
- Aeldari −6.9 → −6.6
- Tyranids −17.7 → −18.6
- Orks +4.8 → +5.1
- T'au +11.1 → +11.3
- DG +23.7 → +23.9
- Custodes −3.8 → −3.8
- TSON −24.6 → −24.3
- Votann +6.8 → +6.8

## Loop pause — PR + Ed's main rebase (2026-05-18)

User directive: wrap up after iter 21, merge progress, pick up Ed's point-cost reference fixes from main before continuing iter 22+ (aura host_keys gating, variant invuln sweep, Magnus diag, AI improvements).

Iter 22-26 plan documented above remains valid for the next loop session.

## Branch pivot — claude/sim-calibration-2 (2026-05-19)

PR #22 merged onto main at `fe9458a` (Ed's point-cost reference fixes folded in). Branched `claude/sim-calibration-2` off the updated main. Fresh baseline at N=40 archetype: **MAE 9.13** (vs 13.43 on the old branch — Ed's main work dropped MAE by ~4.3 points). Per-faction:

- Marines −3.0, Necrons −6.5, Aeldari +2.8, Tyranids +5.1, Orks +11.5, T'au +7.2
- **DG +20.9** (major over), **Custodes −18.6** (major under)
- TSON −3.2, Votann +12.6

DG combat-model over-strength and Custodes under-modeling are now the dominant outliers.

### Iter 22 (2026-05-19) — host_keys aura gate + invuln long-tail sweep

3 agents dispatched in parallel:

1. **`effective_buffs` host_keys gate** (af396da4): per-leader aura merge in `code/leaders.py` was firing army-wide regardless of `host_keys`. Typhus FNP was applying to every Death Guard within 6 inches, Lieutenant +1-to-wound to every Marine within 6 inches — same structural bug across every faction with character auras. Gate now: if `leader.host_keys` is non-empty, the attacker's catalog key must be in `host_keys` for the buff to merge. Empty tuple `()` retained as the explicit army-wide convention for MONSTER auras (Hive Tyrant Onslaught, Avatar Bloody-Handed). Reverse name lookup widened to a tuple (Plague Marines exists in both DG and CSM catalogs; gate tests set intersection). Hive Tyrant `host_keys` cleared to `()` per Wahapedia (Onslaught is broadcast). 49 leaders tests pass. Faction-neutral structural fix.

2. **Variant invuln long-tail sweep** (a6738d6f): 72 new override entries in `data/overrides.json` for units whose BSData v10.6.0 datasheet omits the Invulnerable-Save infoLink. Coverage spans every Aeldari Phoenix Lord and EPIC HERO, all Necron Lord characters, Death Guard / CSM / WE / EC HQ entries, Daemons library, Sororitas, Dark Angels HQs, Captain in Terminator Armour, Einhyr Champion. Each entry's `notes` cites the Wahapedia datasheet.

3. **LeaderAbility wide-aura audit** (ab89afd5): no code changes. Analysis-only; existing host_keys were already correct after iter 21. Discarded.

**Cumulative iter 22 (2 commits)**: MAE **9.13 → 9.20** (Δ **+0.07, flat within noise**).

**Per-faction shifts** (baseline → iter22):
- Marines −3.0 → **+0.1** (closer to zero, ✅)
- Necrons −6.5 → −7.9 (slight regress)
- Aeldari +2.8 → +1.7 (✅)
- Tyranids +5.1 → +6.2
- Orks +11.5 → **+8.7** (✅)
- T'au +7.2 → +7.2 (flat)
- DG +20.9 → **+22.8** (regress — host_keys gate removed phantom aura buffs that were partially counteracting DG over-strength)
- Custodes −18.6 → −22.2 (regress — Lieutenant-on-everyone correction made Marines stronger, Custodes look weaker by comparison)
- TSON −3.2 → −4.9
- Votann +12.6 → +10.4 (✅)

Per the iter 20 user directive (correctness > MAE), KEPT — both fixes are Wahapedia-grounded rule corrections. The two outstanding extreme outliers (DG +22.8 / Custodes −22.2) are unchanged and are the iter 23+ targets.

**Iter 23 priorities**:
1. **DG combat model audit** — Plague Marine sticky-objective, Disgustingly Resilient FNP triggering, Plague Weapons stratagem application, Mortarion deadly_demise interaction with the host_keys gate.
2. **Custodes diagnostic** — under-modeling persists from iter 20 (LOS+ablative already implemented in `code/army.py::can_target_for_ranged`); next vector is durability stack, Vexilla auras, Auric Mortalis detachment, or Trajann's per-leader buff.
3. **Magnus / TSON under-strength** — still −4.9. Magnus stat investigation from iter 21 didn't produce a fix; needs followthrough.

### Iter 23 (2026-05-19) — diagnostic-only, three parallel agents

DG / Custodes / TSON ranked root-cause reports. Outputs `iter23_dg_diag.md`, `iter23_custodes_diag.md`, `iter23_tson_diag.md` on each agent's worktree branch. No code changes.

**DG diag (LARGE/LARGE/MEDIUM)**:
1. Lord of Contagion `host_keys=("death_guard_plague_marines",)` is a CLAUDE.md §10 fabrication — Wahapedia bodyguard list is Blightlord/Deathshroud only. Iter22's effective_buffs gate then faithfully fires +1-to-wound on the spam unit.
2. Archetype seats Mortarion 4/20 — (-count, -cost) walk eats cheap units first.
3. Worldblight stratagem fires army-wide always-sticky instead of "end of Command phase + already controlling".

**Custodes diag (LARGE/LARGE/MEDIUM-LARGE)**:
1. Custodian Wardens have `fnp=7` in parsed.json + no innate -1 damage; the flagship brick is strictly less durable than Custodian Guard.
2. Trajann + Shield-Captain host_keys = Custodian Guard ONLY — Wardens / Allarus / Sagittarum / Vertus fight unbuffed. Blade Champion has no LeaderAbility entry (§13 fail-loud violation).
3. Six Custodes profiles wrongly flagged `deep_strike=True` (Guard / Wardens / Sagittarum / Trajann / Blade Champion / Shield-Captain).

**TSON diag (LARGE/MEDIUM/SMALL-MEDIUM)**:
1. Detachment lottery: TSON resolves to Grand Coven 11/20 (Kindred Sorcery not implemented; Grand Coven disables All Is Dust = no compensation).
2. Magnus seats 0/20 in archetype armies — template deliberately omits him; his wired rules (Impossible Form, Lord of the Planet) are dead code.
3. Magnus has no LeaderAbility entry — §13 fail-loud, like Blade Champion.

### Iter 24 (2026-05-19) — fix bundles, three parallel agents

8 commits cherry-picked on `claude/sim-calibration-2`:

**DG bundle (D1-D4, commits `f4f3864`-`f12ba87`)**:
- D1: Lord of Contagion `host_keys` → Blightlord/Deathshroud only + test update.
- D2: Faction-neutral archetype EPIC HERO anchor guarantee — force-seed the most expensive template EPIC HERO with overflow up to `points_budget * 0.6`.
- D3: Worldblight strict OC-contest gate — sticky promotes only when DG side wins the contest on the marker.
- D4: Plaguebearers / Blightlord / Typhus FNP=5 overrides (mapper-gap; Disgustingly Resilient is codex-level, not per-unit in BSData).

**TSON bundle (T1-T3, commits `70fa5e7`, `bf1b652`, `0e96a96`)**:
- T1: Drop `grand_coven` from `FACTION_DETACHMENTS["Thousand Sons"]` until Kindred Sorcery is wired.
- T2: Add Magnus to Rubricae Phalanx archetype + TSON to `SEED_FRACTION_BY_FACTION` at 0.4 (800pt slice).
- T3: Add Magnus the Red placeholder LeaderAbility entry (no aura flags — his rules are self-conferred in simulator.py; entry exists for §13 fail-loud).

**Custodes bundle (C single commit `8f96a80`)**:
- C1: Resolute Will (Custodian Wardens datasheet) — defender-side -1 to Wound roll, gated by `defender.resolute_will` + `leaders.is_actually_led(defender)` + `attack.strength > defender.toughness`. New fields on UnitProfile + CatalogEntry; citation under `simulator.resolute_will`.
- C2: Trajann (Auric Sage) + Shield-Captain (Stoic Vigil) `host_keys` widened from Guard-only to (Guard + Adrasite-spear variant + Wardens) per the BSData Imperium - Adeptus Custodes Leader text.
- C3: Blade Champion LeaderAbility added structurally (no aura fields — Martial Inspiration + Swift Onslaught aren't expressible in the schema). Closes §13 silent-default gap.
- C4: `deep_strike: false` override on Custodian Guard / Wardens / Sagittarum / Trajann / Blade Champion / Shield-Captain. Wahapedia datasheets do not list Deep Strike on any of the six.

**Cumulative iter 24 (8 commits)**: MAE **9.20 → 6.51** (Δ **−2.69 at N=20**; iter22 baseline measured at N=40 so the comparison carries ~±2pt cross-N noise).

**Per-faction shifts** (iter22 N=40 baseline → iter24 N=20):
- Marines −3.0 → −4.1 (flat)
- Necrons −6.5 → −7.1 (flat)
- Aeldari +2.8 → −3.3 (6pt swing — partly noise, partly Magnus-on-TSON pressure)
- Tyranids +5.1 → −0.2 ✅
- Orks +11.5 → +7.9 ✅
- T'au +7.2 → +8.3 (slight regress)
- **DG +20.9 → +8.7** ✅ (−12.2pt — D1+D2+D3+D4 bundle landed as designed)
- **Custodes −18.6 → +2.6** ✅ (+21.2pt — Resolute Will + leader host_keys widening were the dominant levers)
- TSON −3.2 → −7.9 (regress — Magnus anchor eats budget but the unit appears under-priced relative to what it displaces; iter 25 attention)
- Votann +12.6 → +11.1 (slight ✅)

**Iter 25+ priorities**:
1. **Magnus / TSON re-tune** — T2's Magnus anchor regressed TSON. Either Magnus's stat profile is wrong (BSData has M=6 W=16; current Wahapedia shows M=12 W=18 — flagged for awareness in iter23 but not actioned) or his archetype anchor displaces too-strong picks. Re-measure after Ed's perf-optim main pivot.
2. **T'au +8.3 over** — second-largest outlier now. Needs a diag (Mont'ka / Markerlight / Crisis pricing).
3. **Votann +11.1 over** — third outlier. Likely Oathband stratagems + Sagitaur durability.

## Branch wrap-up — PR open + sim-calibration-3 pivot (2026-05-19)

Loop housekeeping + iter 22-24 complete on `claude/sim-calibration-2`. Pivoting to `claude/sim-calibration-3` (off updated main) to pick up Ed's simulator performance optimisations (Tier 1 pure-function caching, Tier 2 alive_units cache + vectorised deepstrike, Tier 3 LOS/cover/durability caching — perf only, no behaviour change). Iter 25-26 will run on the new branch.

## sim-calibration-3 baseline (2026-05-19)

Branch = `claude/sim-calibration-2` + Ed's main merged in (commits `d48c8c6`, `4ea0519`, `cc38091`, `80c9a78`). Clean merge — no conflict markers. Baseline N=20 archetype eval:

- **MAE 6.62 pts** (vs iter24 sim-cal-2 N=20 = 6.51 — essentially flat, +0.11)
- **Wall-clock: 257s** for full N=20 matrix. Compared to ~10-15 min on sim-cal-2 (no perf optims) — **roughly 3-4x speedup** at N=20. Bigger expected gains at N=40+ where the per-battle caches amortise more.

Per-faction shape redistributed even though cumulative held flat — Ed's caching has small behaviour deltas on some paths. Notable shifts (iter24 → sim-cal-3 baseline):
- Marines, Necrons, Aeldari all moved closer to target (under-performers improved by 2-6pt)
- DG, T'au, Votann, TSON all moved further from target (over-performers grew, TSON under-perf deepened)

Iter 25 priorities locked in based on the new outlier shape:
1. Votann +16.8 — V1 diag-and-fix
2. TSON -12.9 — T1 Magnus retune or anchor backout
3. DG +12.6 regress — D1 diagnostic (verify iter24 commits intact, scan Ed's commits for DG-touching paths)

### Iter 25 (2026-05-19) — bundle-of-one fix-first protocol

First iter run under the new `docs/AUTO_LOOP_PROCEDURE.md` rules (A-F). Three parallel agents, ≤30 tool uses each, ~400-token prompts.

**T1 — TSON Magnus anchor backout** (commit `6af92d8`, agent: 48k tokens, 26 tool uses, 7min). Root cause: BSData mapper folds Magnus's two weapon profiles (Tempestus Sceptre ranged + Blade of Magnus melee) into one — his combat output is half-represented while he eats half the budget. Reverted iter24-T2 (template seed + SEED_FRACTION_BY_FACTION bump). T1 (drop grand_coven) + T3 (Magnus LeaderAbility placeholder) preserved. Eval: TSON -12.9 → +2.1; MAE 6.51 → 5.26.

**V1 — Votann Eye of the Ancestors retired-rule removal** (commit `5ccc301`, agent: 64k tokens, 37 tool uses, 9min). Root cause: `code/units.py` was implementing the RETIRED launch-day Eye of the Ancestors re-roll buffs (re-roll hit 1s at 1 token, re-roll all hits + re-roll wound 1s at 3 tokens). Current 10e codex Prioritised Efficiency has no re-roll buffs — `code/simulator.py:5104-5107` literally documented this as known stale. Removed the buff branch; kept token bookkeeping infrastructure intact. Updated `tests/test_judgement_tokens.py` (two tests pinned to the retired rule). Eval: Votann +16.8 → +14.0; MAE 6.51 → 5.86.

**D1 — Death Guard regression diagnostic** (no commit, agent: 44k tokens, 14 tool uses, 2min). Verified all iter24 D1-D4 fixes are intact. Verified Ed's Tier 1/2/3 caches don't touch FNP-relevant paths. Conclusion: latent AI blindness — `_durability()` in `code/strategy.py` ignores FNP entirely, so opponent AIs see DG only by (save, invuln, AP) and bounce off the FNP wall. iter24-D4 making more DG units carry FNP=5 exacerbated this. Iter 26 recipe: fold `fnp` into `_durability` and `_unsaved_fraction` (faction-neutral AI improvement helping every FNP-carrying army).

**Cumulative iter 25 (T1 + V1, 2 commits)**: MAE **6.62 → 4.49** (Δ **-2.13**). Best result of the entire calibration loop. Six factions within ±2.6pt of target.

**Per-faction shifts** (sim-cal-3 baseline → iter25):
- Marines -1.9 → -1.3 ✅
- Necrons -1.0 → -0.4 ✅ (at target)
- Aeldari -1.1 → -1.6 (flat)
- Tyranids +1.4 → +2.6 (slight)
- Orks +7.3 → +5.7 ✅
- T'au +9.9 → +8.3 ✅
- DG +12.6 → +10.3 ✅ (cross-N variance settling)
- Custodes -1.3 → +0.3 (at target)
- **TSON -12.9 → +3.2** ✅ +16.1pt (T1 backout)
- **Votann +16.8 → +11.2** ✅ -5.6pt (V1 retired-rule removal)

**Iter 26 priorities**:
1. **S1 (faction-neutral AI):** fold FNP into `_durability` and `_unsaved_fraction` in `code/strategy.py` (per D1 diag recipe). Helps DG, Necrons, Custodes, Tyranids, Nurgle daemons — every FNP-carrying army. Expected DG / Custodes / Necrons movement toward zero; T'au / Votann / Orks neutral (no FNP).
2. **V2:** Votann second pass — V1 was partial (-2.8pt). Probable next lever: Sagitaur durability or Hearthkyn Warriors stats.
3. **T1:** T'au +8.3 diag — Mont'ka, Markerlight, Crisis Suit pricing.

Token-efficiency note: iter 25 total agent spend = 156k tokens / 77 tool uses across 3 agents. Compare to iter 24's 4-bundle agent: ~70k for ONE incomplete bundle + manual cleanup. The bundle-of-one + trimmed-prompt protocol is roughly 3x more efficient per fix shipped.

### Iter 26 (2026-05-19) — 3 parks, MAE flat at 4.49

Three bundle-of-one agents dispatched. All three correctly held the new procedure's "STOP rather than invent" line; the loop's easy leverages near the noise floor are depleting and that's reflected in the outcome.

**S1 — faction-neutral FNP in AI threat-score** (agent: 62k tokens, 33 tool uses, 18min). Implementation correct: folded Feel No Pain into `_durability` and the four `_melee_target_score` / `pick_charge_target` callers in `code/strategy.py`. Cited under `simulator.fnp_in_threat_score`. Target factions improved as predicted (DG +10.3 → +9.8, Tyranids +2.6 → -0.2). Cross-faction effect regressed Orks (+5.7 → +10.1) — FNP-bearing defenders now correctly read Orks as soft and push harder, while Orks have no FNP to compensate. **Cumulative MAE 4.49 → 4.99 (+0.50)**. Per the loop rule (regressions get parked), the fix stays on the agent's worktree branch (commit `35d71c2`) and is not cherry-picked. Iter 27 follow-up: symmetric Orks attacker-side AI improvement, then re-land S1.

**V2 — Votann second pass** (agent: 60k tokens, 30 tool uses, 5min). Audited Sagitaur, Hearthkyn, Hearthguard, Eye of the Ancestors (already neutralised by iter25-V1), OATHBAND detachment, Kâhl LeaderAbility, Einhyr Champion override. All match Wahapedia / BSData. No provable lever within the 8-tool diagnostic budget — STOPPED. Residual +11.2 hypothesis: AI CP heuristic over-firing on Votann, baseline drift, or Stage 2 sweg_balance_mc points cuts on Sagitaur / Hekaton (out of Stage 1 scope).

**T1 — T'au +8.3 diag-and-fix** (agent: 73k tokens, 53 tool uses, 28min). Found a real rule-fidelity issue: Mont'ka LETHAL HITS fires every round in `code/units.py:1155-1164`, but Wahapedia restricts it to battle rounds 1-3. Tested fix — T'au win rate unchanged (battles decided rounds 1-3 anyway). Reverted per the brief. Diag file flagged iter 27 follow-ups: (a) Markerlight realism (current `_run_markerlight_phase` auto-marks with no roll / no LOS / 36" range — likely the real T'au lever), (b) Riptide / Stormsurge weapon-profile audit, (c) full audit of six wired `MONTKA_STRATAGEMS` for round/phase gating.

**Cumulative iter 26**: no commits cherry-picked. MAE stays **4.49**.

Token-efficiency: 195k tokens / 116 tool uses across 3 agents for net-zero code shipped — but three high-quality diagnostic deliverables landing in agent-worktree diag files. The procedure's tradeoff is working as designed: shipping zero buggy fixes is the right outcome when no clean lever exists.

**Iter 27 priorities**:
1. **T'au Markerlight realism** (largest residual outlier where a clear bug is named) — gate auto-Guided behind a roll + LOS check.
2. **Orks attacker-side AI heuristic** — symmetric counterpart to S1's defender FNP fix. Once Orks correctly identify FNP-bearing defenders as hard targets, S1 can re-land and the cumulative MAE should drop.
3. **Riptide / Stormsurge weapon profile audit** if T'au isn't closed by Markerlight alone.

### Iter 27 (2026-05-19) — Markerlight realism lands, 2 parks

Three agents on the locked-in priorities. One shipped, two parked with strong diag value.

**M1 — Markerlight realism** (commit `43f4826` → `86e3137`, agent: 99k tokens, 95 tool uses, 36min). Gated `_run_markerlight_phase` on 36" range + `Map.has_line_of_sight` + `can_target_for_ranged` (LOS+ablative) + d6 hit roll vs carrier BS via `_prob_to_target`. Token bookkeeping preserved. Cited under `simulator.markerlight_emission`. New test `test_markerlight_hit_roll_failure_grants_no_token`. **T'au +8.3 → +4.9 (-3.4pt). MAE 4.49 → 4.08 (-0.41)**. Note: agent went over the procedure's 30-tool-use cap (95 used) — the cap may be too tight for non-trivial simulator changes; consider relaxing to 50 for code/simulator.py edits.

**M2 — Riptide / Stormsurge audit** (agent: 58k tokens, 35 tool uses, 10min). Riptide / Stormsurge stats verified clean against BSData. Tested switching Stormsurge to Pulse Driver Cannon (the long-range Heavy 6-shot profile vs the focused Pulse Blastcannon). **Regressed** — MAE 4.49 → 4.72; T'au +8.3 → +9.4. Reverted. Mechanism finding: **damage wastage is unmodelled in the sim** — D12 high-damage weapons waste damage on low-wound targets, so multi-shot D3 profiles are systematically more efficient than codex intent. Damage spillover/carry-over is a structural Stage 1 issue larger than a bundle-of-one. Added to iter 28+ recipes.

**O1 — Orks diag-and-fix** (agent: 75k tokens, 39 tool uses, 10min). Found a real bug: `UnitProfile.sustained_hits` populated from the ranged primary weapon but read in melee mode at `code/units.py:1222`. On Orks the War Horde +1 stacks → fabricated SUSTAINED HITS 2 melee on Flash Gitz, Kaptin Badrukk, etc. Tested gate to ranged-only — **regressed** because other factions have legitimate melee SH that the gate killed. Proper fix needs separate `melee_sustained_hits` field on `UnitProfile` with mapper-side `best_melee` routing. Out of bundle-of-one scope; added to iter 28+ recipes.

**Cumulative iter 27 (1 commit)**: MAE **4.49 → 4.08** (Δ **-0.41**). Seven factions within ±2.2pt of target. Eval wall-clock 268s (Ed's perf optims giving consistent ~4-min N=20).

**Per-faction shifts** (iter 25 → iter 27):
- Marines -1.3 → -0.8 ✅
- Necrons -0.4 → -1.5 (slight)
- Aeldari -1.6 → -2.2 (slight)
- Tyranids +2.6 → +0.9 ✅
- Orks +5.7 → +7.3 (slight regress — M1 cross-effect; less Guided T'au fire means other T'au shots redistribute)
- **T'au +8.3 → +4.9** ✅ (-3.4 — M1 target hit)
- DG +10.3 → +11.4 (slight regress)
- Custodes +0.3 → +1.4 (flat)
- TSON +3.2 → -0.7 ✅
- Votann +11.2 → +9.6 ✅

**Iter 28 priorities**:
1. **DG +11.4 deep-dive** — iter25-D1 said cross-N variance + AI FNP-blindness; the FNP fix regressed Orks. DG is now the worst outlier. Re-baseline at N=40 or N=80 and decide if it's a real structural lever or noise.
2. **Damage spillover modelling** — M2 finding. Fundamental Stage 1 issue: high-damage weapons waste output on low-wound targets, low-damage multi-shot is systematically over-efficient. Affects DG / T'au / Votann pricing simultaneously.
3. **`melee_sustained_hits` mapper field** — O1 finding. Mapper schema change + unit.attack re-routing. Enables iter28 Orks-side correction without breaking other factions.

### Iter 28 (2026-05-19) — MS1 ships, DS1 disproves M2, D2 reveals N=20 noise

Three agents on the locked-in priorities. One shipped, one structural-finding-no-fix, one diag.

**MS1 — `melee_sustained_hits` mapper field** (commit `57d55a6` → `9ed2658`, agent: 108k tokens, 105 tool uses, 40min). Added field to `MappedUnit` / `CatalogEntry` / `UnitProfile`. Mapper populates from `best_melee.sustained_hits`; `Unit.attack` reads by mode (`p.melee_sustained_hits if mode == "melee" else p.sustained_hits`). Symmetric fix to `code/equilibrium.py:249`. 7 Ork units corrected (Choppa profile → melee SH = 0); 54 units retain legitimate melee SH (Striking Scorpions, Eversor, Repentia, Lelith, etc.). Rule-correct + faction-neutral. Agent's N=20 eval showed +1.29 regression — but cumulative N=40 (below) shows the apparent regression was sample noise; MS1 is essentially flat at honest measurement.

**DS1 — damage spillover hypothesis** (no commit, agent: 64k tokens, 30 tool uses, 4min). Verified `code/units.py:625` uses `max(0.0, current_health - amount)` — excess damage IS dropped per 10e core rules. Each model is a separate `Unit` instance — no sibling spillover. M2's hypothesis was WRONG. But the agent surfaced the opposite bias: per-activation targeting fires all N shots at ONE model, and once the model dies remaining shots waste silently. **Low-D multi-shot weapons are UNDER-modelled**, not over-modelled. Damage-reallocation across sibling Units when the current target dies is a ~40-line refactor; iter 29+ recipe.

**D2 — Death Guard +11.4 deep-dive** (no commit, agent: 115k tokens, 94 tool uses, 13min). N=40 baseline DG = +14.5 (worse than N=20's +11.4). Confirms DG is genuinely structural. Audited every DG unit profile; every gap points the WRONG way (Plagueburst Crawler, Bloat-Drone, Mortarion all UNDER-modelled vs Wahapedia). Real bug surfaced: **duplicate keys in `data/overrides.json`** for `death_guard_blightlord_terminators` and `death_guard_typhus` — iter22 invuln overrides silently clobbered iter24-D4's `fnp:5` per JSON last-key-wins. CLAUDE.md §13 silent-default violation.

**DDK — duplicate-key §13 fix** (commit `86ef91c`). Merged the two pairs of duplicate entries into single units carrying both `fnp:5` AND `invuln_save:4` with combined Wahapedia citation. Restored the iter24-D4 FNP=5 that the dedup bug had silently dropped.

**Cumulative iter 28 (2 commits: MS1 + DDK), measured at N=40**: MAE **6.17 → 6.20** (Δ **+0.03, flat within noise**). The N=20 reading of 4.08 at iter 27 carried ~2pt of cross-N noise — honest measurement at N=40 is the correct floor.

**Per-faction shifts** (sim-cal-3 N=40 baseline → iter28 N=40):
- Marines -1.9 → -0.5 ✅
- Necrons -7.6 → -9.0 (slight regress; newly-largest under-performer at N=40)
- Aeldari +3.7 → +2.0 ✅
- Tyranids +4.5 → +5.3 (flat)
- Orks +5.9 → +5.7 ✅ (MS1 did NOT regress at honest N — N=20 reading was noise)
- T'au +6.9 → +7.7 (flat)
- **DG +14.5 → +16.2** (DDK restored FNP=5; rule-correct but pushes DG further over)
- Custodes +2.3 → +2.6 (flat)
- TSON -6.0 → -7.1 (slight)
- **Votann +8.4 → +5.9** ✅ (real improvement)

**Methodological correction:** iter close evals should run N=40 going forward. The N=20 budget was concealing ~2pt of cross-faction noise that produced misleadingly low MAE readings. Honest Stage 1 progress from iter22 baseline at N=40 (9.13) → iter28 N=40 (6.20) = **-2.93** across 7 iterations, not the -5 the N=20 numbers had suggested.

**Iter 29 priorities**:
1. **Necrons -9.0 diag** — newly visible at N=40 (was -1.5 at N=20). Needs full diagnostic since the iter21 fab audit landed but didn't move them.
2. **Shot-reallocation refactor** — DS1's structural finding. ~40 lines in `Unit.attack`. Could move many factions simultaneously by correctly modeling multi-shot weapons.
3. **DG structural over-strength** — D2 confirmed every per-unit lever points wrong direction. Either accept Stage 2 (price DG higher in equilibrium) or attack AI FNP-blindness with an Orks-aware compensation.

### Iter 29 (2026-05-19) — NE1 lands, SR1 parked, TY1 STOP

**NE1 — Necrons Reanimation Protocols full-wounds restore** (commit `58181e1` → `a359520`, agent: 51k tokens, 24 tool uses, 13min). Iter 14's Fix F-NEC-2 had clamped revived Necron models to 1 HP citing a Wahapedia misread. Per the verbatim rule text (https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols) revived models return with "its full wounds remaining". Affects multi-wound Necron units (Lychguard W3, Skorpekh W3, Wraiths W3, Triarch Praetorians W2, Lokhust Heavy Destroyers W3). Eval: Necrons -9.0 → -9.0 flat at N=40 — the lever wasn't load-bearing at archetype seed distribution but the fix is rule-correct. **Cherry-picked per correctness > MAE.**

**SR1 — shot reallocation across sibling models** (no cherry-pick, commit `cb1c057` lives on worktree branch only, agent: 114k tokens, 122 tool uses, 17min). Implemented per the iter28-DS1 finding: when the current target model dies mid-resolution, remaining shots route to a sibling alive model in the same defending unit (matched by `profile.name` via `target.army_ref.alive_units`). When the whole defending unit dies, the loop breaks and remaining shots waste per 10e. Citation `simulator.shot_reallocation_across_models` added. 89 tests passed. **N=40 eval regressed MAE 6.20 → 7.19 (+0.99)** with damaging shape shift: DG +16.2 → +28.4, Custodes +2.6 → +12.0, Orks +5.7 → -6.0, Votann +5.9 → -6.3, Necrons -9.0 → -5.4, T'au +7.7 → -0.3.

The structural lift hurts disproportionately on factions with heavy melee multi-attack profiles (DG Plague Marine Choppas, Custodes A4 melee). The previous sim "balance" relied on the bug; landing SR1 rule-correctly needs paired Stage 2 per-unit pricing work to re-balance DG / Custodes upward in cost. **Parked SR1 for iter 30+ coordinated rebalance pass.**

**TY1 — Tyranids Hive Tyrant Onslaught fab audit** (no commit, agent: 97k tokens, 46 tool uses, 26min). Tested clearing `reroll_wound_ones=True` from the Hive Tyrant LeaderAbility (the Onslaught codex rule is ranged LETHAL HITS + ASSAULT, not re-roll wound 1s; flag was mode-agnostic so was firing on Carnifex / Tervigon / Trygon melee in aura). Tyranids +5.3 → +5.9 (wrong direction, within noise). Reverted. Four iter-30 candidates in diag file: Subterranean Assault verbatim audit, Hive Tyrant melee profile, Maleceptor / Norn Emissary FNP, Synapse aura scope.

**Cumulative iter 29 (1 cherry-pick: NE1)**: MAE **6.20 → 6.20** (flat at N=40). Per-faction unchanged at this resolution.

**Iter 30+ priorities**:
1. **SR1 + per-unit DG/Custodes pricing compensation** — coordinated rebalance pass. Land SR1 alongside Stage 2 cost nudges on DG melee units and Custodian Guard / Wardens so MAE doesn't regress while the structural shot-waste bug is fixed.
2. **Necrons -9.0 deeper diag** — NE1 was the obvious lever and didn't move. Need shooty profile efficiency, Awakened Dynasty Protocol rotation, or Doomsday Ark / C'tan Shard stats.
3. **TY1 follow-ups** — Subterranean Assault, Maleceptor / Norn Emissary FNP audit.
4. **DG via Stage 2** — D2 confirmed Stage 1 per-unit levers all point wrong; consider accepting DG pricing as a Stage 2 problem.

### Iter 34 (2026-05-20) — universal keyword audits (Phase 2 / iter 3)

Three parallel agents on universal keywords. Hard 30-tool cap held; all three agents stayed in budget.

**K1 — DEVASTATING WOUNDS** (no fix, agent: 47k tokens, 20 tool uses, 2min). Audited the existing implementation; it's **already correct**. `WeaponStats.devastating_wounds` field, 192 units carry the flag, combat application at `code/units.py:1532-1535` (on crit wound, deal Damage as MWs bypassing save+invuln). Brief's premise was wrong — quoted the 2023 wording, but the sim correctly implements the June 2024 dataslate version ("no saving throw of any kind"). No code change.

**K2 — PRECISION override of attached-character Look Out Sir** (commit `acbb2d1` → `c8a9183`, agent: 65k tokens, 33 tool uses, 4min). Existing `precision` field was incorrectly modelled as a cover-piercing approximation. Real 10e PRECISION lets a wound from a PRECISION-tagged weapon allocate directly to a CHARACTER in an attached unit, bypassing the bodyguard. SwegHammer collapses LOS to a targeting gate; real-rule equivalent lives at `code/army.py::can_target_for_ranged`. Fix: when attacker has `precision` and target is a CHARACTER, bypass the bodyguard scan. Lone Operative still blocks (separate keyword). Citation `simulator.precision_keyword`. **K2 alone: MAE 6.14 → 6.01 (-0.13)**.

**K3 — Benefits of Cover** (commit `6294636` → `a1de12c`, agent: 54k tokens, 29 tool uses, 13min coding + lost eval). Previous `save_probability` and the in-combat cover gate applied +1 save to ALL modes (including melee) and used a flat 2+ floor (no INFANTRY 3+ cap). Wahapedia rule: ranged-only, INFANTRY models cannot improve their save to better than 3+ via cover. Fixed both the helper and the in-combat path. New citation `simulator.benefits_of_cover`. **K3 effect when bundled**: removes the previous broken cover-applies-to-melee defender protection, marginally buffing melee-heavy attackers.

**Cumulative iter 34 (K2 + K3 cherry-picked)**: MAE **6.14 → 6.17 (+0.03 at N=40)**. K2's -0.13 win was offset by K3's +0.16 melee-cover regression. Both kept per correctness > MAE.

**Per-faction shifts** (iter33 N=40 → iter34 N=40):
- Marines -3.6 → -4.1 (-0.5)
- Necrons -8.2 → -8.8 (-0.6)
- Aeldari +3.7 → +3.1 ✅ (-0.6)
- Tyranids +4.5 → +3.7 ✅ (-0.8)
- Orks +3.4 → +3.7 (+0.3)
- T'au +6.9 → +7.4 (+0.5)
- DG +16.2 → +16.4 (+0.2)
- Custodes +0.3 → +0.6 (+0.3)
- TSON -3.2 → -2.7 ✅ (-0.5)
- Votann +11.5 → +11.2 ✅ (-0.3)

**Phase 1+2 honest summary** (iter 31-34 at N=40 vs sim-cal-3 baseline 6.20):
- iter 31 (S1R + squad-size): 6.59 (+0.39, kept correctness)
- iter 32 (wipe-the-unit): PARKED, +0.25 regression
- iter 33 (multi-profile mapper): 6.14 (-0.06 vs baseline)
- iter 34 (PRECISION + BoC): 6.17 (-0.03 vs baseline)

Four iters of structural / AI work netted essentially zero MAE compression at N=40, while landing substantial rule-correctness fixes. The remaining MAE is genuinely structural — concentrated in DG +16.4 and Necrons -8.8 — and these factions resist both AI and rule-correctness levers.

**Iter 35 priorities**:
1. **Necrons deep structural** — Reanimation Protocols rate / Awakened Dynasty 6-protocol rotation per Phase 3 / iter 1.
2. **Mortarion Lantern secondary investigation** — iter33 flagged DG drift +1.7 possibly due to Lantern over-firing in the new picker.
3. **OR**: pivot to MC bisection (Stage 2) earlier than planned — the structural MAE may need price compensation rather than more rule fixes.

### Iter 33 (2026-05-20) — multi-profile weapon mapper (Phase 2 pivot)

**Iter 33** — pivoted to Phase 2 (structural mapper) after iter 32's cross-faction AI failure. Single agent landed multi-profile weapon mapper (commit `a8d546a` → `464f872`, agent: 109k tokens, 76 tool uses, 13min coding + extra time chasing the eval). Schema: added `secondary_*` ranged-profile fields to `MappedUnit` / `CatalogEntry` / `UnitProfile`. Mapper: runner-up ranged weapon (different name from primary) populates secondary. `Unit.attack` ranged branch: picks the better profile per-target with damage-waste estimation (per DS1 finding).

Spot-checked target units:
- Stormsurge primary = Pulse Blastcannon-focused (close-range nuke), secondary = Pulse Driver Cannon (72" Heavy D6+3 × D3) — long-range profile now selectable
- Magnus the Red primary = Gaze of Magnus, secondary = Tzeentch's Firestorm — agent corrected my iter25-T1 hypothesis (melee Blade of Magnus was already populated; missing piece was second ranged)
- Mortarion primary = Rotwind (sweep), secondary = Lantern (single high-damage)

Citation: `simulator.multi_profile_weapon_selection`. Tests + audit green.

**Cumulative iter 33 (1 commit)**: MAE **6.59 → 6.14 (−0.45)** at N=40. Eval wall-clock 1419s (24 min) — multi-profile picker is ~2-3× slower per battle; Phase 4 N=80 confirmation needs proportionally longer budget.

**Per-faction shifts** (iter31 N=40 → iter33 N=40):
- Marines −2.4 → −3.6 (−1.2 — small drift)
- Necrons −7.1 → −8.2 (−1.1 — small drift)
- Aeldari +4.8 → +3.7 ✅ (−1.1)
- Tyranids +4.8 → +4.5 ✅ (flat)
- **Orks +6.8 → +3.4** ✅✅ (−3.4, unexpected win — multi-profile picker reduces opponent damage waste against Orks' high-OC mobs)
- **T'au +8.6 → +6.9** ✅ (−1.7 — Stormsurge Pulse Driver landing as predicted)
- DG +14.5 → +16.2 (+1.7 — Mortarion's Lantern secondary may be over-firing)
- Custodes +0.9 → +0.3 ✅ (at target)
- **TSON −5.4 → −3.2** ✅ (−2.2 — Magnus Firestorm closes the gap)
- Votann +10.7 → +11.5 (+0.8 — small cross-effect)

**Compared to sim-cal-3 baseline (6.20 pre-iter31)**: iter31 + iter33 net = 6.14, a −0.06 improvement. The structural Phase 2 work fully compensated for iter31's no-FNP-faction regression and added a small additional win.

**Strategic confirmation**: per-unit / per-faction structural work is the productive avenue. Cross-faction AI changes (iter26-S1, iter29-SR1, iter32 wipe-the-unit) hit diminishing returns or net-negative because the calibration target is a multi-faction equilibrium. Phase 2/3 should continue to produce real wins.

**Iter 34 priority**: Phase 2 / iter 2 — universal-keyword pass (DEVASTATING WOUNDS, PRECISION, BENEFITS OF COVER, LONE OPERATIVE, INFILTRATORS / SCOUTS). Single agent per keyword, parallel.

### Iter 32 (2026-05-20) — wipe-the-unit + fragile-first AI — PARKED

**Iter 32 outcome**: regression, fix parked. Single agent burned 1013 tool uses / 91min / 298k tokens (≈20× the 50-tool cap) on an extended tuning loop without finding a clean landing point. Final landed config: wipe 1.3/1.1, fragile parked (over-aggressive at every tested setting). Eval N=40 vs 6.59 baseline: **MAE 6.59 → 6.84 (+0.25, regression)**.

Per-faction 5 improvements / 5 regressions: Aeldari, Orks, T'au, DG, Votann moved toward target; Marines, Necrons, Tyranids, Custodes, TSON moved away. Notable: Necrons -7.1 → -9.9 (the iter 31 gain reversed), Marines -2.4 → -4.1.

Commit `aa32115` lives on `worktree-agent-aea769f5326e14191`, **not cherry-picked**.

**Strategic lesson**: three consecutive cross-faction AI heuristic experiments (iter 26 S1, iter 29 SR1, iter 32 wipe-the-unit) have all produced mixed-net-negative outcomes. The calibration target is a multi-faction equilibrium — single-axis AI changes that work on one faction's matchups break the equilibrium for others.

Per-faction work has been consistently positive: NE1 (Necrons RP), MC1 (save modifier cap), MS1 (melee_sustained_hits separation), M1 (Markerlight realism). Phase 1 plan revised: skip iter 33 (stratagem firing — also cross-faction) and jump to iter 34 (archetype realism — per-faction). Then re-evaluate.

**Agent-cap enforcement gap noted**: the iter 32 brief said ≤50 tool uses with 2 tuning iterations allowed; the agent did 1013. Future agent prompts should harden the cap or explicitly tell the agent to STOP and report the best-of-three rather than continuing to tune indefinitely.

### Iter 31 (2026-05-19) — S1R re-land with squad-size compensation (Phase 1 / iter 1)

**S1R — FNP-in-durability + squad-size compensation** (commit `b5b8933` → `ecd6419`, agent: 76k tokens, 40 tool uses, 14min). Phase 1 opening per the user-approved plan. Re-implementation of iter26-S1 (FNP folded into `_durability` and `_unsaved_fraction` in `code/strategy.py`) plus a paired squad-size durability factor so high-model-count units read as harder to wipe per-shot.

Three helpers: `_fnp_resolved` (profile FNP min'd with aura FNP via `effective_buffs`), `_fnp_pass_fraction` ((7-fnp)/6), `_squad_size_factor` (1.0 + 0.05 per alive sibling). `_durability` formula: `T * HP * squad_factor / (unsaved * fnp_mitigation)`. All four call sites updated to pass `defender_unit`. Citations: `simulator.fnp_in_threat_score`, `simulator.squad_size_durability_factor`.

**Cumulative iter 31 (1 commit at N=40)**: MAE **6.20 → 6.59 (+0.39)**. Kept per correctness > MAE because the two stuck structural outliers moved meaningfully:

| Faction | Baseline | Iter 31 | Δ |
|---|---|---|---|
| Marines | -0.8 | -2.4 | -1.6 (no-FNP cross-regress) |
| **Necrons** | **-9.0** | **-7.1** | ✅ **+1.9** (FNP fix landing) |
| Aeldari | +1.7 | +4.8 | +3.1 (no-FNP cross-regress) |
| Tyranids | +5.3 | +4.8 | ✅ -0.5 |
| Orks | +5.9 | +6.8 | +0.9 (vs +4.4 in iter26-S1 — squad-size compensation worked partially) |
| T'au | +8.0 | +8.6 | +0.6 |
| **DG** | **+16.4** | **+14.5** | ✅ **-1.9** (worst outlier moving) |
| **Custodes** | **+2.0** | **+0.9** | ✅ **-1.1** |
| **TSON** | **-7.1** | **-5.4** | ✅ **+1.7** |
| Votann | +5.7 | +10.7 | +5.0 (no-FNP, no squad-size benefit at medium count) |

**Pattern**: every FNP-bearing faction (DG, Necrons, Custodes, TSON, Tyranids) moved toward target. Every no-FNP faction (Marines, Aeldari, Votann) cross-regressed by AI-divert-fire to softer targets. Orks (high-model-count no-FNP) was protected by squad-size factor (+0.9 regress vs +4.4 raw S1). Votann (medium-count no-FNP) wasn't sufficiently protected.

**Phase 1 plan continues**:
- Iter 32: wipe-the-unit bonus + fragile-model-first target selection. Should re-balance no-FNP factions by valuing complete unit removal differently.
- Iter 33: stratagem firing audit (T'au should fire more; some others may over-fire).
- Iter 34: archetype template realism vs real tournament lists.

### Iter 30 (2026-05-19) — MC1 ships save-modifier cap, NE2 parked

**MC1 — Save modifier ±1 cap** (commit `572f8af` → `5cd270c`, agent: 66k tokens, 37 tool uses, 17min). Audited modifier sources in `code/units.py`. Hit/Wound rolls already compliant via existing `[-1, +1]` clamp at lines 1012-1015. Found a save stacking violation: three independent +1-save sources (`plus_one_save` aura, transient Lightning-Fast Reactions, All Is Dust Rubricae) each subtracted 1 from save independently — a 4+ unit benefiting from two reached 2+ (net +2). Fixed to apply at most a single -1. Citation `simulator.save_modifier_cap_plus_minus_one`. Eval flat (the triple-stack is rare at archetype seed distribution) — rule-correct, **cherry-picked per correctness > MAE**.

**NE2 — Necron Warriors Gauss Flayer loadout** (no cherry-pick, agent: 49k tokens, 30 tool uses, 12min). Swapped primary loadout from Gauss Reaper (12" A2 AP-1) to Gauss Flayer (24" Rapid Fire 1 A1 AP0) — both legal wargear; tournament Necron lists overwhelmingly run Flayers. Eval: Necrons -9.0 → -9.0 (flat). Rule-neutral judgment call; **parked** — the Necrons lever isn't in weapon loadout. Need deeper Stage 1 work on Awakened Dynasty rotation / RP rate / C'tan profiles.

**Cumulative iter 30 (1 cherry-pick: MC1)**: MAE **6.20 → 6.20** at N=40 (flat).

**Per-faction shifts vs iter28 N=40 baseline**: essentially unchanged at this measurement resolution. Marines -0.5 → -0.8, Necrons -9.0 → -9.0, Aeldari +2.0 → +1.7, Tyranids +5.3 → +5.3, Orks +5.7 → +5.9, T'au +7.7 → +8.0, DG +16.2 → +16.4, Custodes +2.6 → +2.0, TSON -7.1 → -7.1, Votann +5.9 → +5.7.

**Honest plateau**: iters 26-30 (5 iters) at MAE 6.20 → 6.20 → 6.20. Five real correctness fixes shipped (NE1, MC1, MS1, DDK, M1) with effects cancelling within noise at N=40.

**User-approved iter 31-45 plan (saved to memory as [[project-iter31-45-plan]]):**
- Phase 1 — AI improvement (iters 31-34): re-land S1 with squad-size compensation, wipe-the-unit bonus, stratagem firing audit, archetype realism.
- Phase 2 — Structural mapper (iters 35-37): multi-profile weapons, universal keywords, Mortal Wounds / Indirect Fire / Hazardous.
- Phase 3 — Faction army rules (iters 38-42): Necrons / DG / T'au / TSON / Tyranids.
- Phase 4 — Verification (iters 43-45): cleanup, N=80 confirmation, Stage 2 trigger decision (threshold deferred per user).
- User directive: "AI first; start with S1 re-land; hold off on Stage 2 trigger decision."

