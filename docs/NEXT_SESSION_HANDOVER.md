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
