# Next-session handover — 2026-06-30 (mapper multi-weapon-chassis fix; sim now fires real datasheet weapons)

**START HERE (supersedes every block below).**

**New baseline.** `data/_anchor_sc20a_n80_log.json`, gated mean absolute error **3.26** (a WASH: sc19a 3.22 → 3.26, +0.04 within noise). Lineage: sc18a (3.26) → sc19a (3.22, artillery-hold) → sc20a (mapper weapon fix, wash).

**The mapper now fires units' REAL datasheet weapons.** The single-model weapon picker (`code/bsdata/mapper.py`) was stripping the main guns off ~69 multi-weapon chassis (Titans, Knights, Dreadnoughts, super-heavy tanks, T'au battlesuit Commanders). THREE bugs fixed in `_collect_single_model_weapons` / `_gather_group_candidates`: over-clustering of independent weapon slots (→ per-group `max`-selections picking), lost linked-Library-group candidates, and fixed-weapon re-pick + skipped-ranged-fallback (Forgefiend fired nothing). **69 units restored, 0 regressions, no over-gunning** (max 6/unit). `parsed.json` regenerated. Metric is a WASH (restored firepower cancels across poles); adopted fidelity-first. Full detail: `docs/CURRENT_STATE.md` head + `docs/DECISION_LEDGER.md`.

**Knight Tyrant — FIXED** via a `data/overrides.json` `model_loadouts` override that restores its dropped 72" carapace Gheiststrike missile launcher (kept the real harpoon + meltagun; Chaos-Knights-scoped +0.72, within noise, toward its real 44.7). It still under-fires because the move AI advances it — the metric-blocked advance-discipline piloting issue, not the loadout. The advance-discipline gate (pinned, `SWEG_ADVANCE_DISCIPLINE`) is what would unlock it (and every other under-pole gunline), but it regresses the headline via the durable-survivor over-reward.

**Do NOT re-burn:** the 23 full-suite test failures are PRE-EXISTING (fail on the old frame too — synthetic-profile / non-deterministic tests). The N=80 re-anchor must be run as two N=40 halves (`--seed-start 0/40 --battles 40`, merge the `--log-games`) — an environment governor kills the full 64-minute background job (the frame itself is fine: battles run in <1s, memory healthy).

---

# Next-session handover — 2026-06-30 (artillery-hold adopted fidelity-first; durable-survivor over-reward confirmed #3)

**START HERE (supersedes every block below).**

**New baseline.** `data/_anchor_sc19a_n80_log.json`, gated mean absolute error **3.22** (from sc18a 3.26). Lineage: sc17a (3.45) → sc18a (3.26, Feel-No-Pain batch) → sc19a (3.22).

**`SWEG_ARTILLERY_HOLD` ADOPTED default-on, FIDELITY-FIRST.** Dedicated indirect artillery (Basilisk/Manticore/Plagueburst Crawler/Hive Guard/Exorcist) HOLDS in the backfield and bombards instead of the default AI marching it into melee where it dies by round 3-4. Faithful AI piloting (no real player advances a Basilisk), de-faction-gated via `_dedicated_indirect_artillery` (`code/strategy.py`: model-count-weighted indirect-dominant + ranged>melee + not CHARACTER). Recovered from an abandoned AM-faction-gated version (an EVAL_PROTOCOL §9 forbidden-zone violation). The metric is a **WASH (−0.05)**: Astra Militarum +6.56 (under-pole fills) cancelled by Death Guard +6.90 (its T10/W12/2+ Plagueburst over-scores held alive) — **durable-survivor over-reward confirmation #3** (after the pilot gates and the going-first campaign). Kept on fidelity; `=0` kill-switch reproduces sc18a byte-identically (0 flips). Full detail in `docs/CURRENT_STATE.md` head + `docs/DECISION_LEDGER.md`.

**The indirect-fire "no-line-of-sight bug" the block below flags DOES NOT EXIST.** The simulator uses the BUILD-TIME `indirect_fire` flag (re-derived from the best-expected-value weapon, `units.py:5208`), which already fires Wyvern/Field Ordnance mortars indirect — the prior handover read the unused CATALOGUE flag. The "artillery fires zero shots" symptom was the AI *advancing* the gun (now fixed by the hold lever), NOT the indirect flag. Do NOT re-chase the indirect-fire data; the build-time derivation is correct (it even refuses a Cadian Heavy Weapons Squad's autocannons the indirect treatment).

**Harness fix:** `scripts/evaluate_vs_meta.py` re-launch (`os.execvpe` → `subprocess.run`) — the re-exec was segfaulting on this box (the "intermittent screens get killed" failure). Preset `PYTHONHASHSEED=0` on older checkouts.

**Branch state:** `claude/sim-calibration-16`. Artillery-hold lever + harness fix + anchor sc19a + these docs are staged but NOT yet committed/pushed (awaiting user "go").

**NEXT — the strategic wall is now triple-confirmed.** Every faithful AI/piloting improvement that strengthens units (pilot gates, going-second mechanisms, artillery-hold) is metric-blocked by the durable-survivor representation over-reward. The addressable frontier is the **parked structural representation re-model** (a user decision) or thin remaining faithful over-credit removals on the over-pole side. Do NOT re-propose: going-second AI mechanisms, the indirect-fire flag fix, or any faction-gated piloting.

---

# Next-session handover — 2026-06-29 (AM under-pole = under-delivered firepower + the durability over-reward; firepower bugs found)

**START HERE (supersedes the going-first block below).**

The Astra Militarum under-pole investigation (pilot-by-hand + instruments) reached a two-part diagnosis and surfaced concrete, addressable firepower bugs.

**Diagnosis.** AM's −20.7 is (a) the MIRROR of the over-pole — AM craters specifically into the armies the sim over-rates (World Eaters +12.7, Emperor's Children +10.4, Daemons +9.2 …), which are only ~45-48% in reality — AND (b) the sim UNDER-DELIVERS AM's own offense. Quantified vs World Eaters (`scripts/diag_am_firepower.py`, N=10): Orders reach ~1.4/round (≈9% of AM's ~16 squads buffed per turn); AM gets ~30 shoot-actions/game (~half its units ever fire); AM deals ~49 damage and removes only **13 of 53 enemy models (24%)** over 5 rounds — then gets swamped (guns silenced in melee after round 2). A real AM gunline deletes far more of a melee army before contact; that is how AM hits ~45% in reality.

**FIXES SHIPPED (this PR, both default-off / faithful):**
- `SWEG_AM_BATTLELINE_SPECIALS` (`be33e1f`) — restores the special weapons the mapper drops from Cadian Shock Troops + Death Korps of Krieg (1 plasma + 1 meltagun /10). FAITHFUL bug fix; metric is a WASH (+4.1 vs World Eaters / −4.2 vs Orks, net ~0) — kept for fidelity, not as a metric lever.
- `surgical_contest` was REVERTED: the pilot harness's +5.0/+3.3 did NOT survive production validation (−4.2/−2.8, within noise) — an AI heuristic with no fidelity value, so removed.

**ACTIVE LEAD — the dormant artillery bug (being investigated now).** AM's indirect artillery **fires zero shots/game**: Basilisk present in 5/6 games, **0.0 shoot-actions/game**; Wyvern 0.0. A Basilisk (S9, D6, 48"+ indirect, ~140 pts) should bombard every round. This is a concrete AI gap (the shoot-target picker isn't using the indirect-fire path for no-line-of-sight targets) — faithful to fix, almost certainly metric-positive, and the FIRST genuinely-addressable AM lever (unlike the structural snapshot wall). Root-cause + fix in progress.

**FOR-REVIEW-LATER follow-ups (noted, not yet done):**
1. **Order coverage** — only ~1.4 orders/round reach ~9% of AM's squads. Real AM stacks Take Aim / FRFSRF on its key shooters via multiple officers + stratagems. Investigate whether the AI under-issues Orders or whether coverage is structurally capped (prior waves found order *throughput* "exhausted" — but coverage at 9% suggests the cap, not the effect, is the gap). Re-examine with `scripts/diag_am_firepower.py`.
2. **Half of AM never shoots** (~30 shoot-actions for ~16 units over 5 rounds) — units swamped in melee or with no target. Tied to the tempo/snapshot problem.
3. **Run the fire-frequency / firepower-coverage check on the OTHER under-pole armies** (Drukhari, Adeptus Custodes, Grey Knights, Chaos Knights, T'au) — they may have the same dormant-weapon / under-firing bugs the AM artillery check exposed. Generalize `scripts/diag_am_firepower.py` to take the faction and sweep the under-poles; a shared firing bug could be a chunk of the under-pole MAE.

---

# Next-session handover — 2026-06-29 (going-first / tempo campaign → STRUCTURAL FLOOR; branch pushed to sync Ed)

**START HERE (supersedes the earlier 2026-06-29 block below).**

**Baseline unchanged.** `data/_anchor_sc18a_n80_log.json`, gated mean absolute error **3.26**. The going-first campaign adopted nothing — it declared a floor.

**The going-first / tempo axis is a DECLARED STRUCTURAL FLOOR.** Going-first win rate is ~69% (N=150) vs real 49-52%, broad across all five deployments (`scripts/diag_going_first_by_map.py`, 64.9-84.5% at N=60/map). All three faithful going-second mechanisms regress the headline by transferring wins to the durable over-poles: `SWEG_OVERWATCH_MOVE` +0.40, `SWEG_KITE_MOVE` +1.12, `SWEG_PROBE_RESERVE` +1.67 (worst; removed). The going-first over-reward IS the durability over-reward via tempo. Full record: `docs/CURRENT_STATE.md` head + `docs/DECISION_LEDGER.md` REVERTED. **Do NOT re-propose going-second AI mechanisms.**

**Shipped (all default-off, frame byte-identical, no re-anchor):** `SWEG_OVERWATCH_MOVE` (fidelity correction, held); `scripts/diag_going_first_by_map.py` (toolbox); Sweeping Engagement restored at 2000-point 44×60 behind `SWEG_FULL_DEPLOY_ROTATION` (the stock map is 44×90, wrong size for 2K — completing the five-deployment rotation needs an N=80 re-anchor to adopt); `SWEG_CK_DOOM` recovered.

**Branch state:** `claude/sim-calibration-16` committed and **pushed to `origin/claude/sim-calibration-16`** (2026-06-29) to sync with Ed's work. The going-first axis is closed; the remaining open items all need a deliberate re-anchor (adopt the six-map rotation; Stage-2 work), not autonomous lever-hunting.

---

# Next-session handover — 2026-06-29 (Feel No Pain fabrications adopted, re-model empirically closed, lost levers recovered)

**(superseded by the block above).**

**New baseline.** `data/_anchor_sc18a_n80_log.json`, gated mean absolute error **3.26**
(down from 3.45). The improvement is the Feel No Pain fabrication batch, adopted
default-on with `=0` kill-switches (commit `b6029e4`): Adeptus Custodes had a
fabricated faction-wide Feel No Pain (30 datasheets, mapper leaked it from crusade
relics / battle traits), four bodyguard units carried a save that belongs to a
different model, and Chaos Space Marine Legionaries veterans-of-the-long-war was
restored (duplicate override key merged). **Screen new gates paired vs `sc18a`.**

**The "per-model representation re-model" is RETIRED — empirically.** Do not quote it
as a pending solution (full verdict: `docs/STRUCTURAL_REMODEL_PLAN.md` top block).
Squad-frame is done/inert; clustering (`SWEG_MOVEPLAN`, with a collision-default gate
bug fixed this session) was finally screened and **REGRESSES +0.61** (not a wash);
the "fragile-army fix" was never defined.

**Lost-lever recovery (commits `b6029e4`, `6e51aa8`).** A `git log -S` sweep found 41
`SWEG_` gates dropped in past re-anchors (not rejected — lost). Recovered + validated
+ committed: `SWEG_KITE_MOVE` (objective-aware kiting, the going-first lead),
`SWEG_EC_DAEMONETTE_FF` (Emperor's Children +17 fabrication), `SWEG_SECONDARY_HANDCAP`
(secondary two-card cap). **Still-lost recoverables (live path):** `SWEG_DG_DR_PHASE`
+ `SWEG_DG_WORLDBLIGHT_OWN_TURN` (Death Guard +11), `SWEG_DAEMONIC_ROUND` cluster
(Chaos Daemons +12), `SWEG_CK_DOOM` (Chaos Knights −10).

**Strategic verdict — the live path is OVER-POLE FABRICATION FIXES, not the over-count
stack.** The action-economy / going-first / secondary-handcap over-count fixes are a
DEAD END: they prop up the fragile under-pole (Astra Militarum), and the AM under-model
hunt this session found NO unmodeled mechanism (Born Soldiers, Voice of Command Orders,
`SWEG_OFFICER_FOLLOW`, list, cover all modeled) — so removing the props craters AM with
no faithful offset (manual games: kite-move craters AM and all gunline under-poles;
ledger: secondary-handcap craters AM 26.8→15.5). The Feel No Pain win (−0.19) proves
the opposite path works: deflating the over-poles by removing FABRICATIONS lifts the
under-poles via coupling. **Next: confirm the EC Daemonette coupling (screen running),
then recover + screen the Death Guard / Daemons over-pole fabrication gates.** Custodes
is now an *under*-model (sim 46.1 vs real 52.1) — unmodeled Stand Vigil + partial
Martial Ka'tah (task #4 has the build spec). CPU is intermittent; screens get killed —
re-launch when free.

---

# Next-session handover — 2026-06-27 (durability/piloting deep-dive + action-economy build)

**START HERE.** This session went far past wave 260 into the structural root of the
residual. The headline finding: **gated 3.45 is a compensating-errors equilibrium**
— the production simulator's deliberately-crude AI *masks* a representation layer
that over-rewards durability; every faithful improvement (abilities in wave 260,
piloting, representation) *un-masks* it and regresses the metric. The one identified
faithful path that can close it is the **action economy** — now built and screening.

---

## Branch + anchor + the OFF-arm rule

- Working branch `claude/sim-calibration-16`. **Wave 260 is COMMITTED** (10 commits;
  gated mean absolute error 3.45; standing anchor `data/_anchor_sc17a_n80_log.json`).
  Pull request #82 (waves 254-259) still OPEN; #81 merged.
- **Everything after wave 260 is UNCOMMITTED work in the working tree** (inventory
  below). All `SWEG_` gates are default-off and byte-identical-off, i.e. **all gates
  off == sc17a exactly** (confirmed repeatedly with 0/36960 flips).
- **REUSE sc17a as the OFF anchor — do NOT re-run an OFF arm.** Deterministic eval =
  exact. I wasted one OFF run this session and the user (correctly) caught it. Pair an
  ON arm directly: `python -m scripts.paired_delta data/_anchor_sc17a_n80_log.json <ON>.json`.
  A full N=80 takes ~64 min/arm on this box. Gates are all-faction → full N=80 (not scoped).

---

## THE ACTIVE WORK — action-economy build (screening NOW)

`SWEG_ACTION_ECONOMY` (default-off, byte-identical off): the three missing Chapter
Approved 2025-26 Tactical action cards — **Establish Locus, Recover Assets, A Tempting
Target** — all cited (`data/rule_citations.d/secondaries_pariah_nexus.json`, enforced in
`scripts/audit_rules.py` SIMULATOR_RULE_KEYS) and implemented in `code/secondaries.py`
+ `code/simulator.py`. The AI performs actions through the existing
`_unit_can_perform_action` spare-unit contract — **no faction or model-count branch**:
the emergent anti-durability tax. A unit-rich horde (Astra Militarum) has spare bodies
to score the cards; every Imperial Knight is a productive shooter so it qualifies for
zero actions. Verified: cli clean both states, audit green, cards fire (Astra Militarum
scored 9 Recover Assets + 15 A Tempting Target versus Imperial Knights under the gate).

- **SCREEN RUNNING — read `data/_ae_on_paired.txt` when done** (`SWEG_ACTION_ECONOMY=1`,
  full N=80, paired vs sc17a; ON-only, sc17a IS the OFF arm). Background task `b8pc4g8vo`.
- **The signature to read:** does Astra Militarum and the fragile unit-rich under-poles
  LIFT toward their real win rates while the low-model durable over-poles (Imperial
  Knights ~real 47.7, Chaos Knights ~real 44.7) DEFLATE toward 50? **Risk to watch:**
  unit-rich OVER-poles (Tyranids, Chaos Daemons, Orks) also earn action victory points
  — if they spike too, the net washes.
- **If it helps:** next is the COUPLED secondary-over-count correction — now safe because
  Astra Militarum finally has a *faithful* victory-point source (actions) to replace the
  compensating over-count prop. See `docs/DURABILITY_OVERREWARD_INVESTIGATION.md` §3.3.
- **If it washes / over-helps hordes:** the action economy needs the representation
  coupling first; report which, and consider the quick M4-alpha A/B to formally close
  the clustering candidate (it is already built+dormant behind `SWEG_MOVEPLAN`, and
  `diag_overscore` already suggests it is moot — durable wins are 70-94% UNCONTESTED,
  so clustering-for-contested-wins targets the wrong gap).

---

## The two investigations (read these docs)

- **`docs/DURABILITY_OVERREWARD_INVESTIGATION.md` — THE key doc.** Root verdict: the
  over-reward lives in the REPRESENTATION (one-Unit-per-model + survivor-snapshot
  scoring: a durable single-model unit banks full Objective Control at every snapshot
  while a fragile horde that held the marker contributes zero the instant it dies), NOT
  the combat model (faithful floor — do NOT nerf toughness/wounds/saves/invuln/Feel No
  Pain). It is a MISSING MECHANISM, not a floor (real Knights ~47.7% — durability does
  not dominate reality). The faithful counter = the action economy (built) + the missing
  primary missions/secondary coupling. Four open questions for the user at the end.
  **IMPORTANT:** "fractional credit for held-then-died markers" is FORBIDDEN (an
  Objective-Control-to-victory-point knob; real 10e scores all-or-nothing at discrete
  Command-phase moments). The faithful mechanism is the action TAX, not partial credit.
- **`docs/STRUCTURAL_REMODEL_PLAN.md`** — the structural scoping. Step 1: `SWEG_FILL_SQUADS`
  already done (fill path builds coherent squads → inert). Step 2: stranding ratio open
  (2.65-3.01 > 1.3) but the over-reward is uncontested-dominated, so M4-alpha clustering
  is likely moot.
- **`docs/OVERPOLE_UNIT_AUDIT.md`** — the wave-260 over-pole audit (committed).

---

## THE DEFINITIVE FINDING — the pilot experiment

The user's idea (pilot the under-pole by hand vs the AI, find misplays) worked as a
diagnostic and produced the definitive characterization of the wall:

- Found real misplays: Astra Militarum advances its gunline forfeiting shooting; charges
  characters into Knights. Built gated fixes (both default-off, byte-identical off,
  **PINNED per user — "keep the AI"**): `SWEG_ADVANCE_DISCIPLINE` (a shooter holds and
  Normal-moves rather than Advancing when it has a damageable target in reach; excludes
  Assault-weapon units) and `SWEG_CHARGE_DISCIPLINE` (do not charge a melee target you
  cannot damage; characters never).
- These are FAITHFUL improvements (Astra Militarum +8.9, the largest under-pole lift ever)
  but they REGRESS the metric (gated 3.45 → 6.05) because the durable over-poles exploit
  good play MORE (Imperial Knights +18.4, Chaos Knights +21.1). Mobile armies also
  cratered (Drukhari -17, T'au -11) — partly an incomplete Assault-exclusion (detachment
  assault-windows like Knights' Bold Gallantry / T'au Mont'ka are not yet excluded),
  partly their durable opponents benefiting.
- CONCLUSION: AI piloting cannot close the gap (it is symmetric / over-pole-favouring).
  The pilot gates stay pinned default-off as "better AI the metric cannot yet absorb";
  they only become net-positive once the durability over-reward is corrected (action
  economy). A small remaining piloting refinement: exclude the detachment assault-windows
  from `SWEG_ADVANCE_DISCIPLINE` so it stops cratering mobile shooters.

---

## Instruments built this session (uncommitted, keep them)

- `scripts/diag_pilot_am_vs_ik.py` — **the pilot-comparison harness** (KEY TOOL):
  `python -m scripts.diag_pilot_am_vs_ik <seed> "<A faction>" "<B faction>"` runs one
  game, renders per-round board PNGs (`data/_pilot_<tag>_r<n>.png`, view them), and dumps
  a per-round move log (every unit's move/intent/shot/charge + objective outcomes).
- `scripts/diag_stranding.py` + `STRAND_STATS` / `SWEG_STRAND_INSTR` (in `code/simulator.py`
  `_score_objectives` + `code/sim/constants.py`) — the wave-93 3-inch/6-inch stranding drill.
- `scripts/diag_squad_audit.py` — per-faction squad-composition audit (no sim run).

---

## Uncommitted WIP inventory (on -16 — consolidate into scoped commits)

Run `git status` first. Roughly:
- `code/simulator.py`: `SWEG_ADVANCE_DISCIPLINE` gate (~line 10958, in `_do_move`),
  `SWEG_CHARGE_DISCIPLINE` gate (~12615, in `_do_charge`), `SWEG_STRAND_INSTR` hook,
  action-economy assignment (after Movement phase).
- `code/secondaries.py`: the three action cards.
- `code/sim/constants.py`: `STRAND_STATS`.
- `scripts/audit_rules.py`: registered the 3 card citations.
- `data/rule_citations.d/secondaries_pariah_nexus.json`: the 3 card citations.
- Scripts: `diag_pilot_am_vs_ik.py`, `diag_stranding.py`, `diag_squad_audit.py`.
- Docs: `STRUCTURAL_REMODEL_PLAN.md`, `DURABILITY_OVERREWARD_INVESTIGATION.md` (new).
- Plus the usual untracked `data/_*.json` / `data/_pilot_*.png` eval artifacts.

**Consolidation plan (CLAUDE.md §14, small PRs):** (1) action-economy build + citations
+ audit registration as one commit; (2) the two pilot gates as one commit (message must
say: faithful AI, PINNED default-off, metric-regressing alone — kept pending the durability
fix); (3) instruments + the two investigation docs as one or two commits. Do this once the
action-economy screen gives a verdict, so the commit messages can state the outcome.

---

## NEXT STEPS (in order)

1. **Read `data/_ae_on_paired.txt`** (action-economy screen) and interpret per the signature
   above.
2. **If it helps:** build the coupled secondary-over-count correction (DURABILITY doc §3.3),
   then re-screen the combined frame (action economy + corrected secondary) vs sc17a.
3. **If it washes / over-helps the unit-rich over-poles:** report which; the action economy
   then needs the fragile-army representation coupling before it lands. Optionally run the
   M4-alpha A/B (`SWEG_MOVEPLAN`) to formally close the clustering candidate.
4. **Consolidate the WIP** into the scoped commits above.
5. **Standing user direction:** keep iterating AI piloting (Track A) AND the durability fix
   (Track B = the action economy) in parallel; the pilot gates stay pinned.

## Forbidden-zone reminders (do not stray)
No nerfing faithful durability stats; no Objective-Control-to-victory-point knob; no
faction/model-count branch; no fractional-held-credit; no re-fit to win rates; cite every
rule (stop and ask if a citation cannot be found). The combat damage model is a closed
faithful floor.
