# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 243 (2026-06-12, CLOSED) — Astra Militarum Voice of Command rebuilt end-to-end (real REGIMENT / SQUADRON keywords, First Rank Fire rapid-fire gate, squad-level Order dispatch) plus per-model primary-flag parity: all four parts faithful and ADOPTED, headline 7.10 → 7.22 at forty battles (every faction flat). The −19 Astra Militarum residual is NOT orders plumbing — the archetype builder drops two of the three officers (diagnostic banked, top next lever).

**1. Part 1 — per-model loadout primary-flag parity (`f37d646`).** The `dataclasses.replace` call
that promotes each model's best ranged weapon in `code/units.py` was not copying `indirect_fire`,
`one_shot`, or `precision` — 168 units carried at least one wrong flag (Wyvern lost its indirect
fire; Rhinos fired the hunter-killer missile every turn). All three flags now copy; `lance` and
`hazardous` deliberately excluded with call-site comments. Five tests. Paired screen at forty
battles: 7.05 → 7.10 (+0.05 wash), Aeldari −2.15 decisively toward target. Adopted on fidelity.

**2. Part 2 — REGIMENT and SQUADRON as first-class keywords (`ead486d`).** The wave-242 root cause
fixed: `code/bsdata/mapper.py` now tracks the real categoryLink keywords (31 units gain REGIMENT,
44 gain SQUADRON), every Voice of Command gate switches off the BATTLELINE proxy, and the
BATTLELINE hard gate in `_is_order_target_eligible` is gone. Screen: headline 7.10 → 7.28 with
Astra Militarum −1.94 AWAY — the fix made things worse, which exposed part 3.

**3. Part 3 — First Rank Fire rapid-fire gate (`e265fdf`).** With tanks newly order-eligible, the
slot-priority heuristic fed "First Rank, Fire! Second Rank, Fire!" to Leman Russ variants that own
no Rapid Fire weapon — a verbatim no-op ("Improve the Attacks characteristic of Rapid Fire
weapons … by 1"). New `_unit_has_rapid_fire` helper mirrors exactly the profile set the buff
touches; no-Rapid-Fire targets fall through to Take Aim!. Seven tests. Screen: 7.26, recovering
only +0.6 of the −1.94 — a second mechanism had to exist.

**4. Part 4 — Orders apply to the whole codex unit, not one model (`384c111`).** The second
mechanism: `dispatch_orders` issued each Order to a single Unit INSTANCE, but the simulator stores
one Unit per physical model — an Order to a ten-model lasgun block buffed ONE lasgun (value ÷ squad
size) while a tank got the full effect; no-stacking was enforced per model (wrong scope); and the
Take Cover! damage branch could never fire because casualties remove whole models, leaving
survivors at full health. The dispatcher now groups the eligible pool into codex units by
`squad_id`, applies the Order to every member, counts the squad as ONE no-stacking target, tests
aura range against any member, ranks by squad aggregates (summed per-model points cost plus summed
damage-per-activation), and derives the Take Cover! fraction from squad lost wounds including dead
models. Four tests; citation effect text updated. One-battle probe corroboration: the order stream
now plays like a real Command phase — the lasgun blob draws First Rank Fire, the heavy weapons
squads draw Take Aim!.

**5. Measurement (combined orders frame vs the part-1 flag-parity frame, paired, forty battles,
18,480 matched games).** Headline gated 7.10 → 7.22 (+0.12); ALL twenty-two factions flat. Astra
Militarum 22.9 → 21.9 (−1.05 ± 2.07) on ONE HUNDRED AND ONE flipped games — the Orders now visibly
churn Astra Militarum games at full squad strength, but with no net direction. Verdict: every part
is rule-grounded (cited, tested, probe-corroborated), fidelity-first says adopt. Re-anchor at
eighty battles: gated 6.70, raw 10.05, 5/22 in band (Thousand Sons newly inside) —
`data/_anchor_sc9c_n80_log.json` promoted as the standing anchor (replaces sc9b at 6.52; the +0.18
is the adopted orders frame plus seed noise, consistent with the +0.12 paired read). Astra
Militarum gated 19.01 (was 18.99) — unchanged, exactly as the officer-omission diagnostic predicts.

**6. The honest finding — orders plumbing was real but is NOT the Astra Militarum residual (the
Daemonic Manifestation shape again).** A read-only diagnostic agent traced the built archetype army:
the template seeds the documented real-meta leader stack (Cadian Castellan + Ursula Creed + Lord
Solar Leontus, order ceiling 8 per round) but the `(-count, -cost)` seed walk in
`code/archetypes.py:1444` exhausts the 1100-point seed budget on the tank spine first; the EPIC
HERO anchor then fails its 0.6 overflow cap by 25 points, and only the CHARACTER anchor fires,
rescuing the CHEAPEST officer (Castellan, 55 points, ceiling 2 per round). Compounding: officers
have no leader-attachment (`code/leaders.py` carries no Astra Militarum entries), so the lone
Castellan drifts 8.5–14.2 inches from the nearest eligible squad by round 3 and issues NOTHING
after round 2 — three Orders per battle against a template-intent ceiling of ~8 per round. Next
levers, in order: (a) seed-walk leader-stack priority so the built list matches the template's own
documented composition (list-realism fidelity; touches every faction's build → frame change,
re-base at eighty battles), (b) officer leader-attachment or stay-near-squads piloting (aura
starvation). Dedup block and eligibility logic verified correct.

**7. Wave close and checkpoint.** Wave 244 plan banked (melee weapon-keyword mode routing — ranged
anti-keywords / devastating wounds / twin-linked currently contaminate melee profiles on 242
units). Branch past the hard size cap (eight commits, ~2,400 reviewable lines): checkpoint pull
request opens after this close per rule 14; next waves land on `claude/sim-calibration-10`.

## Wave 242 (2026-06-12, CLOSED) — charge-path legality (the 10e "Charge Move" non-target rule) built, measured at both evaluation sizes, and ADOPTED AS DEFAULT: headline wash (+0.14) with T'au Empire and Imperial Knights both decisively toward target. Astra Militarum root cause found (orders never reach the army); wave-243 build dispatched.

**1. The diagnosis (systemic before per-faction, per the wave-241 ranking).** The charge-target
picker had NO path legality: chargers reached gunlines straight through screening bodies, violating
the verbatim core rule — "Without moving within Engagement Range of any enemy units that were not
a target of the charge" — already flagged in `docs/CORE_RULES_AUDIT.md`. Screens in the simulator
therefore protected nothing, which over-rated melee armies against shooting armies whose real-table
defence is the screen.

**2. The build (`884a8b8`, worktree agent, cherry-picked).** Gated `SWEG_CHARGE_PATH` in
`pick_charge_target` (`code/strategy.py`): (part a) non-FLY chargers are excluded from any candidate
whose straight-line move would pass within Engagement Range (one-inch base-edge gap) of a non-target
enemy — new pure-geometry point-to-segment helper `_charge_path_screen_gap` in
`code/sim/geometry.py`; (part b) ALL chargers including FLY are excluded when the approximate charge
end spot itself sits within Engagement Range of a non-target. Excluded candidates simply fall out of
the scorer, so redirection onto the screen EMERGES from the existing kill-value ranking — no new
behaviour knob. Cited `simulator.charge_path_non_target` (verbatim Wahapedia Charge Move text), zero
extra random draws, gate-off byte-identical, six new tests.

**3. Measurement (paired, like-to-like).** Screen at forty battles per pairing versus the 6.38
anchor (18,480 matched games): headline +0.09 wash; decisive movers T'au Empire +4.75 toward target,
Imperial Knights −7.20 toward target, Death Guard −4.76 toward target; the predicted Astra Militarum
recovery did NOT appear (+0.24 flat — prediction falsified, see item 5). Confirm at eighty battles
per pairing (36,960 matched games): headline gated 6.38 → 6.52 (+0.14, wash); T'au Empire +3.85
toward target (enters the noise band), Imperial Knights −5.46 toward target (gated 10.61 → 5.15);
Genestealer Cults +3.63 AWAY (new carried residual — horde screens now also protect the Cults' own
melee); the Death Guard screen improvement did not confirm (−1.59, flat). Verdict: a verbatim core
rule, cited and tested, at essentially zero headline cost with two decisive structural wins —
fidelity-first doctrine says adopt. **Default flipped ON** (`SWEG_CHARGE_PATH=0` restores the legacy
no-path-check behaviour). New standing anchor `data/_anchor_sc9b_n80_log.json` — gated 6.52, raw
9.88, 4/22 in band — promoted at zero evaluation cost (configuration equality with the confirm run).

**4. Test fallout from the default flip (the wave-241 lesson applied — scenarios spread, gate never
pinned off).** Two incidental failures, both collinear stagings where the new rule legitimately
changes the outcome: `test_charge_baseedge.py::test_charger_does_not_overlap_other_models` (an enemy
bystander parked on the straight approach now makes that charge illegal and the picker redirects
onto the screen — the bystander is now FRIENDLY, which forces the same angular collision search
without the illegality) and `test_charge_picker_wont_crack.py` (brick dead on the squishy's approach
line). Digging into the latter exposed a PRE-EXISTING vacuous-assertion bug: the picker-preference
tests compared `target.uid`, but `uid` is only assigned by `Battle` at start, so every comparison
was `"" == ""` — true whatever the picker chose. With real `assertIs` assertions the
"picks the most damageable among uncrackables" claim turned out NEVER true (the scorer ranks
uncrackables by full charge score — ranged-output value and counter-threat included — under which
the heavier brick's bigger guns win, gate on or off). Tests now pin what the code actually
promises: genuine squishy-preference on legal-path stagings, and no-veto (someone is still picked
when every candidate is uncrackable).

**5. Astra Militarum root cause (the −18.99 under-shooter, biggest single residual).** The screen
falsified the melee-bypass hypothesis, so a read-only diagnostic agent traced the Orders pipeline:
`code/orders.py` proxies the codex REGIMENT / SQUADRON order-target keywords as
BATTLELINE+INFANTRY / BATTLELINE+VEHICLE — but BSData v10.6.0 grants BATTLELINE to almost nothing
(ZERO Astra Militarum vehicles; only Cadian Shock Troops, Catachan Jungle Fighters, and Death Korps
of Krieg infantry). Orchestrator-verified against the BSData cache: the real categoryLinks carry
"Regiment" ×33 and "Squadron" ×45. Net effect today: tank commanders issue zero orders every game,
Lord Solar's SQUADRON and TITANIC legs never fire, and Kasrkin / Tempestus Scions / Heavy Weapons
Squads are never order-eligible — the faction's signature army rule is structurally absent. Hazard
caught at review: do NOT stuff BATTLELINE into vehicles (archetype list generation keys squad caps
on BATTLELINE — that would be a silent frame change). Faithful shape: REGIMENT / SQUADRON as
first-class tracked keywords in the mapper plus an orders-plumbing switch. Wave-243 build agent
dispatched (worktree, Sonnet). Bundling candidate for the same measurement: the Wyvern's primary
weapon is misidentified (the anti-tank-picker-bias class — Heavy bolter chosen over the real Quad
Stormshard Mortar with BLAST and INDIRECT FIRE).

**6. Fork resolution without escalation.** The fight-alternation re-test (melee over-pole cluster:
Adeptus Custodes 19.96, World Eaters 16.27, Death Guard 12.43, Emperor's Children 11.95, Chaos
Daemons 10.03) is already authorised by watchdog queue item 9 — the old "genuinely refuted" tag
predates roughly sixty waves of frame change and the wave-166/168 reject was a doubling confound.
Ranked after the wave-243 work.

