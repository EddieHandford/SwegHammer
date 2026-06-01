# SwegHammer calibration — current state

**Last updated:** Wave 84 close (2026-06-01) — objective-control contest verified FAITHFUL; a
fabricated "damaged-OC" lever was caught + reverted. Headline gated **4.17** (no code change).
The Imperial Knights over-control is body-army positioning, not an objective-control bug.

**Wave 84 investigated the re-aimed Imperial Knights lever** (the objective-control contest). Two
things to record. (1) MISSTEP: mid-wave I built a "damaged Knight loses Objective Control" rule on
a wrong web-source reading; the watchdog caught it as a fabricated, faction-gated metric-tuning
penalty (commit 9f599c0) and I reverted it — 10e Objective Control does NOT change on the damage
bracket (BSData: Knight Paladin OC 10 / Armiger 6 in every profile; the "Damaged" ability gives
Lethal Hits / Lance / +1 to hit, unchanged OC). Lesson: `feedback-verify-stats-against-bsdata`.
(2) The faithful diagnostic: drilled the summed-objective-control contest in IK vs Astra / Tyranids,
comparing credited `a_oc`/`b_oc` to the raw per-model objective control within 3". **credited == raw
everywhere — the contest is FAITHFUL.** The Knight over-controls because body armies have huge TOTAL
objective control (Tyranids ~159 across 111 models) but get almost none onto markers (0–15) while a
Knight parks concentrated objective-control-10 — a positioning / one-Unit-per-model representation
gap, NOT an objective-control-math bug and NOT a Knight penalty. Reported (`LOOP_QA.md` Q9);
memories `project-oc-contest-faithful`, `project-oc-does-not-bracket`. The leftover IK spike is the
positional core; the scoring overhaul (Tier A) already cut the headline to 4.17.

### Earlier — wave 83 (Tier A board-control secondaries built + landed)

**Wave 83 built + landed Tier A** (the five real Pariah Nexus objective-holding / board-control
secondaries). N=40: gated **4.95 → 4.17 (−0.78)**, in band **6 → 9** — a clear faithful aggregate
win. Most over-shooters eased (Drukhari +18.6 → +9.7, Custodes/Sororitas/T'au down); board-control
under-shooters rose (Chaos Space Marines −19.2 → −11.3, Chaos Knights into band). It made Imperial
Knights WORSE (+19.1 → +29.2) because a durable Knight over-controls objectives and banks the new
board secondaries itself — which is what wave 84 then diagnosed. Full result + the sharpened
finding: `docs/SCORING_MODEL_OVERHAUL_PLAN.md`.

### Earlier — wave 82 (scoring overhaul scoped)

**Wave 82 scoped the user-authorised scoring-model overhaul** (`LOOP_QA.md` Q6: build the
scoring/victory-point overhaul, diagnose-don't-nerf, plan-first). Deliverable
`docs/SCORING_MODEL_OVERHAUL_PLAN.md`: primary scoring is faithful; the gap was the SECONDARY
economy (only 4 of ~12 tactical secondaries modelled). Wave 83 built Tier A from this plan.

### Earlier — wave 81 (contest/deny tested + reverted; the AI track concluded)

**Wave 81 built + tested redesign step #2 (contest/deny positioning) and it failed — the
diagnosis-predicted outcome.** Env-gated `SWEG_CONTEST`: a cheap chaff unit not on an
objective moves to CONTEST the nearest reachable enemy-controlled objective, to deny the
durable camper (Imperial Knights) its primary VP (naturally asymmetric — IK carries no chaff).
N=40 A/B vs 4.95: gated **4.95 → 5.14 (REGRESSED +0.19)**, **Imperial Knights +19.1 → +18.2
(only −0.9, still grossly over-rated)**, while the OTHER over-shooters got worse (Drukhari
+18.6 → +20.6, Votann +13.4 → +14.9). Reverted. The structural law (3rd confirmation): every
generic faithful AI improvement helps whoever has the better army, and the over-shooters HAVE
the better armies, so sharper play WIDENS the headline. Imperial Knights is a structural
VP-vs-durability SCORING residual, not AI-fixable → escalated as Q6 → user chose the scoring
overhaul (see above).

### Earlier — wave 80 (IK Armiger re-fit tested + reverted)

**Wave 80 ran the user's AI+re-fit hypothesis on the #1 residual (Imperial Knights)
and it failed.** The faithful re-fit toward the real Armiger-heavy tournament list made
IK WORSE — alone (gated 4.95 → 5.66, the efficient Armigers over-perform more in the sim)
and paired with focus fire (5.90, IK +39.5 / 88%). Reverted. **Firm diagnosis:** the IK
over-rate is the objective-HOLDING (the sim over-rates a durable camper because opponents
do not DENY its primary VP) — NOT the list (both shapes over-perform), the stats (current),
the rules (verified), or the shooting AI (a Knight can't be shot off — better targeting
only sharpens IK's own offence, confirmed 3×).

### Earlier — wave 79 (army focus fire built + tested, env-gated, regresses solo)

**Wave 79 built redesign step #1 (army-level focus fire) of the faithful AI track.**
Env-gated `SWEG_FOCUS`: the army nominates the most valuable durable enemy threat it
can hurt and its anti-armour weapons concentrate on it. It regresses solo (4.95 →
5.41): it HELPS the fragile over-shooter Drukhari (+18.6 → +14.2, its Ravagers get
focus-removed) but WORSENS the durable Imperial Knights (+19.1 → +25.9 — a Knight
can't be shot off, so the victims' fire is wasted while IK's own anti-armour sharpens
on the opponents' vehicles). Third confirmation that better SHOOTING AI sharpens the
durable over-shooters. **Next (the user's AI+re-fit path):** (1) rebuild the IK
archetype toward the real Armiger-heavy tournament list (the sim's big-Knight list is
over-gunned; Armigers are fragile so focus fire would remove them → IK down) — test the
re-fit PAIRED with focus fire; (2) build step #2 contest/deny (the real IK lever — deny
its primary VP, don't kill the Knight). Committed env-gated OFF; baseline unchanged.
Full detail: `docs/MATCHUP_FIDELITY_ANALYSIS.md`.

### Earlier — wave 78 (matchup-fidelity diagnosis + faithful-AI plan)

**Wave 78 opened the user-chosen phase (Q4 ruling): the faithful target/positioning
AI track + matchup-fidelity diagnosis.** A diagnosis+plan wave. Drilling per-matchup
(not aggregate) shows the residuals are driven by impossible-in-real-play lopsided
cells: Imperial Knights beat CSM/AdMech/Marines **100%**, Drukhari beat
Tyranids/CSM/AdMech **90%**; CSM loses **0%** to Emperor's Children, Daemons **0%** to
AdMech/Drukhari/TSON. Compared to real May-2026 play, the gap is almost entirely
**bucket (a), the opponent AI** — it does not focus-fire the durable/key threat, contest
and deny the camper's objectives, or allocate units to actions sensibly. Stats/rules
verified faithful (Knight T11/W26 already reflects the Dec-2025 update); one list note
(real winning Knights list is Armiger-heavy — flagged, not pulled). Full diagnosis + the
faithful-AI redesign plan: `docs/MATCHUP_FIDELITY_ANALYSIS.md`. The AI build executes in
the next waves (env-gated A/B; when it exposes an over-shoot, diagnose the faithful cause
— re-fit toward real lists now permitted — never a nerf).

### Earlier — wave 77 (per-unit Advance, metric-neutral; clean levers exhausting)

**Wave 77 was a consolidation wave.** Rotation-gating the tactical secondaries was
tested and REJECTED (Sabotage-off is gated 5.15 vs 4.91 on — the over-scoring is
net-positive, so reducing it regresses). Landed the per-unit Advance roll (real 10e:
one Advance roll per unit, not per model — the same bug class as the wave-76 charge
fix), a faithful correctness fix that is metric-neutral: gated 4.91 → **4.95** (within
N=40 noise) but in-band 5 → 6. **The clean impactful faithful levers are now exhausted**
— the two biggest residuals (Imperial Knights +19.1 durable camper, Drukhari +18.6
fragile) both need the opponent target/positioning AI, which regressed when tried
(wave 72). The strategic fork — take the AI-redesign + re-fit (goal-doc-restricted) vs
bank Stage 1 at ~4.9 — is **escalated to the user** (`LOOP_QA.md` Q4). The watchdog
ruled: do NOT start the AI-redesign + re-fit until the user rules; keep taking small
clean faithful fixes meanwhile (next: the missing Be'lakor datasheet for Chaos Daemons).

### Earlier — wave 76 (per-squad charge roll, gated 5.11 → 4.91)

**Wave 76 landed the per-model activation tax the watchdog mandated — as a
concrete core-rule fix.** Verify-first found the mechanism the prior washes
missed: the per-model over-rate is NOT spread/coherency (hordes cluster), it is the
CHARGE phase — SwegHammer rolled 2D6 *per model*, so an 11-model mob got 11 charge
attempts (~97% to make a 9" charge vs the real ~28%). Real 10e: a unit makes ONE
charge roll. A codex squad now shares one roll per round. Gated 5.11 → **4.91**,
bringing down the melee over-shooters (Orks +10.3→+8.1, Votann +14.7→+12.4) and
pulling Grey Knights back toward band. It works *because it cuts the horde's
effective melee output* — the exact thing the decision-overlay wash could not reach.
A clear core-rule correctness fix. Collateral (re-fit territory): Drukhari / T'au /
Sororitas up (their melee opponents now charge less reliably).

### Earlier — wave 75 (Sabotage + 40-VP secondary cap, gated 5.35 → 5.11)

**Wave 75 extended the proven action-secondary lever (watchdog confirmed).** Two
faithful changes: the real **40-VP total-secondary cap** (the sim never enforced it;
secondary-heavy shapes like Custodes ran past it) and **Sabotage** (a chaff unit
pushed forward performs an action — 3 VP in No Man's Land, 6 in the enemy DZ — with
the shoot/charge lockout). Gated 5.35 → **5.11**, and it dents the #1 residual:
Imperial Knights +23.3 → +18.0 (opponents score forward actions it can't reciprocate);
Custodes, Tyranids, Astra, AdMech, Necrons, Marines all better. **Honest collateral:**
the low-model armies that can't reciprocate over-corrected (CSM −16.6, Chaos Knights
−12.9, Grey Knights −6.6) — faithful in DIRECTION (low-model armies do struggle with
the secondary game) but amplified because cleanse/sabotage aren't rotation-gated yet
(they over-score vs the real draw-1-2/turn cadence). Tempering = a LATER secondary
wave, not wave 76.

**WAVE 76 IS FIRMLY THE PER-MODEL DURABILITY / ACTIVATION TAX** (watchdog-directed,
`LOOP_QA.md` Q3) — the genuine root cause of Imperial Knights +18.0 (still #1) that the
secondaries only chip at. It must be a FAITHFUL mechanic (real action-economy /
objective-count / coherency effects), NOT a metric-driven penalty on low-model armies.
"One more bounded secondary" instead = shying away (the watchdog will flag it).

### Earlier — wave 74 (Cleanse action secondary, gated 5.89 → 5.35)

**Wave 74 built the wave-73 structural lever and it worked.** The
action-economy secondary **Cleanse** (a real Pariah Nexus secondary that was
missing) now counterbalances the kill-secondary asymmetry: a unit performs the
Cleanse action on a controlled objective OUTSIDE its own deployment zone and
cannot shoot/charge that turn (the real action-vs-fight tradeoff), scoring 2 VP
for one / 4 for two. The asymmetry is even-handed — it falls out of unit cost
(`_is_chaff_unit`, <15 pts/model surplus bodies): Imperial Knights (no chaff)
score 0; hordes / MSU and elites with cheap aux score it. Gated MAE 5.89 → **5.35**
with exactly the predicted moves — durable over-shooters ease down (Imperial
Knights +27.9 → +23.3, World Eaters +16.5 → +12.5) and board-control under-shooters
rise (Astra −15.5 → −10.6; AdMech / Daemons / Tyranids / Necrons toward band). Also
fixed the dead Cull the Horde mechanic. In-band dipped 6 → 5 (small margins). This
is a faithful structural fix that moves the metric the right way by being more
correct — the first real win after three small/investigation waves.

### Earlier — wave 73 (investigation: the over/under split is the kill-secondary asymmetry)

**Wave 73 (investigation, no code change, headline unchanged at gated 5.89).** The
user steered the loop off narrow nerf-grinding toward structural levers. Verify-first
overturned the named lever ("secondaries never read") — they ARE counted (added to
`_a_vp`/`_b_vp` since 2026-05-20; `_a_secondary_vp` is a redundant unread tracker; the
literal fix would double-count). The real over/under driver is the **kill-secondary
asymmetry**: durable killers score Bring It Down / No Prisoners / Assassinate against
victims who score ~0 back (a horde scores 0 No Prisoners vs IK — they can't destroy a
durable Knight AS A UNIT under per-model representation). The missing counterbalance is
the **action-economy secondary family** (the sim models NO actions; only 2 of 9
tacticals) — the faithful, even-handed fix that rewards board-control under-shooters
and taxes low-model campers with an action-vs-fight tradeoff. Evidence in
`docs/SECONDARY_SCORING_ANALYSIS.md`; build plan in `docs/ACTION_SECONDARIES_PLAN.md`.
**Wave 74 = build the Cleanse vertical slice per that plan** (+ fix the dead Cull the
Horde mechanic: `_is_horde_unit` reads `starting_strength`/None, should read `max_models`).
Worker questions now route to the gitignored `LOOP_QA.md` watchdog channel, not the user.

### Earlier — wave 72 (Ion Shield ranged-only, gated 5.97 → 5.89)

**Status:** Headline gated MAE **5.89** (raw 9.28), **6/22 in band**. Wave 72
landed a faithful Imperial Knight durability fix (Ion Shield is "5+ invulnerable
**against ranged attacks only**" per BSData — big Knights have no melee invuln; the
sim applied it flat). Imperial Knights +29.0 → +27.9; melee under-shooters edge up.
Modest but the one metric-positive faithful lever found this wave.

**The headline is now firmly AI/structure-gated — TWO findings nail this down.**
(1) The under-shooters lose on VICTORY POINTS WHILE STILL ALIVE (Chaos Daemons lose
6-9/10 with survivors on the board, 0-1 tabled) — so per-faction COMBAT buffs do not
address their loss; it is the same objective/durability complex as the Knights
over-rate, from the under side. (2) Improving the target AI REGRESSES the headline:
a faithful value-based shooting-target picker (anti-armour concentrates on durable
threats, real weapon-target matching) was A/B'd and made it WORSE (5.97 → 6.11, IK
+29 → +32.9) because better targeting sharpens the killy over-shooters' own offence
more than it helps their victims remove un-killable Knights. This is the SECOND AI
lever to regress this session (objgreedy was the first, wave 71), both confirming
`project-ai-frozen-under-mae-first`: AI improvements expose over-tuned over-shooter
stats/lists. **A target-AI redesign will not reduce the headline until the
over-shooters are re-fitted.**

### Earlier — wave 71 (Code Chivalric fidelity fix, gated 5.98 → 5.97)

Wave 71 fixed the one genuine fidelity defect behind the Imperial Knights over-rate
(Code Chivalric was re-rolling all natural 1s; the real rule is one re-roll per
activation) and **proved the rest of that over-rate is a compensating error, not a
rule defect** — Bold Gallantry, Bondsman, all Knight stats and the maps verified
faithful end to end.

**Code Chivalric** (Imperial Knights army rule) was re-rolling EVERY natural 1
army-wide; the real rule is "re-roll ONE Hit and ONE Wound roll" per activation.
Reroll-all-1s over-scales with shot volume (a 20-shot Knight gun got ~3-4
effective re-rolls vs the rule's one). Now a single per-activation re-roll budget
(`code/units.py` `_chiv_hit_reroll`/`_chiv_wound_reroll`), faithful to the
one-Unit-per-model representation. Metric-neutral (the rule existing is the swing,
not the over-scaling) but correct.

**The Imperial Knights +29 over-rate is NOT a rule/stat defect — it is a
compensating error in the opponents' AI.** Everything was verified faithful:
Bold Gallantry (real Valourstrike Lance detachment, ~21pt, correctly gated on
Advance, charge-after-advance correctly blocked), Bondsman/Paladin's Duty (real,
~2.4pt), all Knight stats (OC 10/6, T 11/12, W 26/28 — match BSData), and the
maps (5-objective Leviathan quincunx). IK wins by **VP/objective-holding, not
tabling**. The root cause: the shooting-target AI is a min-HP "finish the weakest"
picker, so opponents shoot the W14 Armigers and chaff first and **never
concentrate fire on a big W26 Knight** — durable Knights sit on objectives
untouched all game. Under-shooters holding objectives better (tested via an
objective-greedy AI tweak — a wash, reverted) doesn't help, because they can't
take objectives FROM the un-killed Knights.

### Earlier — wave 69 (under-performer faction buffs, gated 8.74 → 8.29)

Headline gated MAE was **8.29** (raw 11.57), in-band 5/22. Wave 69 = the
win-win under-performer track: a 6-faction rules deep-dive (5 under-performers + an
over-performer over-buff audit) → implement each under-performer's missing rules
(verify-first against Wahapedia/BSData). Landed (gated 8.74→8.29): **Imperial Knights
−21.8→−16.0** (real Valourstrike Lance detachment + Bold Gallantry + Bondsman
abilities), **Chaos Daemons −19.0→−14.6** (per-god datasheet buffs — Tzeentch 4++
correction, Murderer's Cowl, Penumbral Puppetry/Gloam Rot), plus TOWERING
line-of-sight (cross-faction), Chaos Knights real Iconoclast Fiefdom detachment, and
GSC Patriarch/Primus leaders + Aberrant FNP. All verify-first (the over-performer
audit's "phantom Aeldari invuln" claim was DEBUNKED — Dark Reapers really have a
5++; the Daemons agent correctly corrected only the genuine Tzeentch 4++).

CAUGHT + REVERTED: CSM Dark Pacts per-unit auto-gamble crashed CSM 45.8→24.8% (the
self-inflicted D3 mortal wounds on every squad every round outweigh the buff — real
players are selective; task #36). Chaos Knights barely moved from the detachment
alone — its −38 is dominated by the AI-positional gap (the durable-objective
diagnostic moved CK −38→−8.8), so CK needs the objective AI (#12), not just rules.

### Earlier — wave 68 (core-rules-correctness batch, gated 7.80 → 8.74)

Headline gated MAE was **8.74** (raw 12.05), in-band 5/22. Wave 68 was a
deliberate **fidelity-first** wave from the full 10e core-rules audit
(`docs/CORE_RULES_AUDIT.md`): removed the **Heroic Intervention fabrication** (not a
10e rule — was a free defensive move for every Character) and fixed five real bugs —
Fall Back no longer always rolls Desperate Escape (only when battle-shocked or
crossing enemies); Indirect Fire now applies its unmodified-1-3-auto-fail + Benefit
of Cover; in-engagement (Pistol/Big Guns) and Blast target restrictions; unmodified-6
always hits; disembark can't place within Engagement Range; battle-shocked units
fight first in Remaining Combats. 919 tests green (deleted the HI test file), audit
280/280.

The headline rose +0.94 (7.80 → 8.74) — expected: the fixes move factions away from
a calibration fitted on the old wrong rules. Concentrated on **Chaos Daemons
−13.7 → −19.0** (HI removal correctly weakened a Character-heavy melee army that the
fabrication propped up) and the shooty over-shooters **Aeldari/Sororitas** (Fall Back
fix lets them disengage and keep firing). The **archetype-list re-fit (task #22)** is
now the gating next step and must lift Daemons + Knights while trimming
Aeldari/Sororitas/Thousand Sons.

### Earlier — wave 67 (per-unit-mechanics batch, gated 7.56 → 7.80, in-band 3 → 5)

Headline gated MAE was **7.80** (raw 11.11), **in-band 5/22** (was 3/22).
Wave 67 landed all six top findings from the per-unit-mechanics audit in parallel
(one worktree agent each, cherry-picked to `ba2a8b4`): unit coherency (cluster
squads at deployment + objective control credited per unit), per-unit secondary
scoring (No Prisoners / Cull count destroyed units), Reanimation/Undying Legions
grouped by `squad_id`, stratagem transient buffs applied to the whole squad (60
sites), per-squad battleshock + Mob Rule by squad_id, and the once-per-unit gate
re-keys (Oath, Acts of Faith, Strands, Miracle die, Markerlight, Blood Surge,
Beacons). All rules-correct; 922 tests green; citation 281/281 (new
`simulator.unit_coherency`).

The gated headline rose +0.24 (7.56 → 7.80) even though in-band improved 3→5 and
big structural fixes landed (Necrons +4.2→−1.3 from reanimation; Drukhari
+30.1→+27.8 from coherency). The regression is one faction: **Adepta Sororitas
+10.1→+17.2** (gated 6.3→13.4) — stratagem-buff propagation + the Acts-of-Faith
squad re-key correctly made Sororitas stronger, past a list tuned around the old
bugs. This is the fidelity-then-refit pattern: the sim is now more correct, so the
**archetype-list re-fit (task #22)** is the immediate next step, Sororitas first.

### Earlier — wave 66 (mortal-wound spillover + Deadly Demise + Blast, gated 7.78→7.56)

Wave 66
landed the mortal-wound half of the allocation rule (`Battle._apply_mortal_wounds`:
excess mortal wounds carry to the next model of the unit, unlike normal damage),
fixed **Deadly Demise** to hit each *unit* once (was per-model), and scoped **Blast**
to the targeted unit via `squad_id`. Eval 7.78 → 7.56 (small, rules-correct).

A user question about per-model vs per-unit framing then triggered a four-agent
**per-unit-mechanics audit** (`docs/PER_UNIT_MECHANICS_AUDIT.md`): the per-model
representation pervades the codebase and `squad_id` is the fix key. Top open items
(tasks #23-28): coherency wave (deployment clustering + OC-per-unit — the likely
remaining lever on horde over-shoot), per-unit secondary scoring (No Prisoners /
Cull count models not units), Reanimation profile.name→squad_id pooling, stratagem
transient-buff propagation to squad siblings, per-squad battleshock.

### Earlier this session — wave 65 (damage-allocation spillover, gated 9.27→7.78)

Wave 65 landed the biggest fidelity fix in many waves: **damage-allocation spillover**
(`simulator.damage_allocation_spillover`). The sim previously dumped a whole
volley into ONE model of a multi-model unit and wasted the overkill; now each
unsaved wound allocates to the next surviving same-`squad_id` model, with a
destroyed model's excess damage lost (kills bounded by unsaved-wound count, not
damage total — the actual 10e rule). This was the real "Lever 1" win: it moved
exactly the structural-residual factions (Tyranids −10.4, Imperial Knights +8.0,
Orks −7.2, Drukhari −7.2, Chaos Knights +4.8, AdMech −4.6). Built on the P1
`squad_id` infrastructure (behaviour-neutral) added the same session. See
`docs/RULE_ACCURATE_FIX_DESIGN.md` and memory `project-squad-activation-contained-wash`.

Second-order effect to chase next: elite/MEQ armies (Custodes +9.9, Marines
+10.3, Thousand Sons +21.7, Aeldari +13.5) now clear chaff more efficiently and
drifted further over — candidates for an archetype-list re-fit.

This file is the fast-pickup point for any session continuing the loop.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 59 close (`f1c2825`) | 14.28 | 10.73 | 3/22 |
| Wave 60 close (`e1f3f53`+docs) | 14.27 | 10.71 | 2/22 |
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |
| Wave 63 close (`96fd68e`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 65 close (spillover+docs) | 11.15 | 7.78 | 2/22 |
| Wave 66 close (mortal+demise+blast) | 11.08 | 7.56 | 3/22 |
| Wave 67 close (per-unit batch ×6) | 11.11 | 7.80 | 5/22 |
| Wave 68 close (core-rules batch, fidelity) | 12.05 | 8.74 | 5/22 |
| Wave 69 close (under-performer faction buffs) | 11.57 | 8.29 | 5/22 |
| Wave 70 close (objective-aware AI #12) | 9.47 | 5.98 | 4/22 |
| Wave 71 close (Code Chivalric fidelity fix) | 9.38 | 5.97 | 6/22 |
| Wave 72 close (Ion Shield ranged-only) | 9.28 | 5.89 | 6/22 |
| Wave 73 (investigation only, no code change) | 9.28 | 5.89 | 6/22 |
| Wave 74 close (Cleanse action secondary + Cull-fix) | 8.74 | 5.35 | 6→5/22 |
| Wave 75 close (Sabotage + 40-VP secondary cap) | 8.50 | 5.11 | 5/22 |
| Wave 76 close (per-squad charge roll) | 8.16 | 4.91 | 5/22 |
| **Wave 77 close (per-unit Advance — metric-neutral)** | **8.29** | **4.95** | **6/22** |

Wave 65's lever was a **core-rule fidelity fix** (damage allocation), not AI or
stats — confirming the `project-faction-residual-rootcause` thesis that the big
residuals are structural representation bugs, not tuning. In-band count is flat
at 2/22 but the error *magnitude* dropped sharply (gated −1.49); the improved
factions are still outside their noise floors but much closer.

## Handoff context — wave 61 close

Three fixes landed (all on `claude/sim-calibration-6`, pushed through
`d141a69`; `c4d6da6` is the AI-gate commit, docs/close on top):

- **KNIGHTS-TITANIC-ESCAPE** (`31e477c`): TITANIC/FLY exempt from Desperate
  Escape + threshold 1→1-2 (Wahapedia verbatim).
- **KNIGHTS-DEMISE-D6PLUS2** (`d141a69`): mapper D6+2 parse + 11 chassis
  overrides (Deadly Demise was 1, should be 5).
- **KNIGHTS-AI-FALLBACK** (`c4d6da6`, the dominant lever): melee-primary
  units stay and fight instead of Falling Back. Corrected Knights UP
  (IK +10.1) AND over-shooters DOWN (Votann/AdMech/Orks/Marines/AstraMil).

New over-shoots introduced by the gate (melee units now staying engaged):
**World Eaters +7.1, CSM slightly over** — top carry-forward to re-tune.

## Next ranked levers for wave 77

Current biggest gated errors (wave 76 eval `data/wf_wave76_squadcharge_n40.json`):
Imperial Knights +19.6 (16.6), Drukhari +18.7 (15.3), Chaos Daemons −17.0 (13.8),
CSM −17.3 (14.9), Votann +12.4 (9.3), Chaos Knights −12.4 (9.1).

1. **MORE per-model activation-economy taxes in the charge-vein (the proven wave-76
   pattern).** Per-squad charge (5.11 → 4.91) confirms: find other per-model rolls/events
   that should be per-UNIT in real 10e and fix them. Candidates to verify-first: Desperate
   Escape tests (per model vs per unit), Battle-shock tests, overwatch, any "roll for the
   unit" event the sim does per model. Each is a core-rule correctness fix that cuts
   per-model over-rating.
2. **Rotation-gate the tactical secondaries (the deferred fidelity fix is now due).**
   cleanse/sabotage score every round; the real tactical deck draws ~1-2/turn. Gating them
   (like Engage/BEL via LC-2) would temper the wave-75 over-correction of the low-model
   armies (CSM −17.3, Chaos Knights −12.4) and the cheap-unit over-scoring (Votann,
   Sororitas) — a genuine fidelity fix, no longer pre-empting the per-model tax.
3. **Imperial Knights +19.6 (still #1) is NOT per-model** (1-model units, unaffected by
   per-squad charge) — it is the durable primary-camper over-rate. Its own diagnostic:
   likely the opponents not contesting it off objectives (the AI-targeting fix regressed,
   wave 72) or a durability/scoring angle. Drukhari +18.7 rose this wave (its melee
   opponents charge less reliably) — re-diagnose now that the melee layer changed.
4. **Re-fit candidates (archetype-list care rules):** re-measure after the above.

## Structural track (owns the remaining headline)

- **The over/under split is now understood and single-rooted.** Over-shooters are
  killy/durable elite armies (IK +29, WE +16.5, Drukhari +16.9, TSON +12.8,
  Custodes +10.0, Marines +8.6, Votann +9.0); under-shooters are board-control
  armies (Daemons −20, Astra −15.5, Necrons −9.5, AdMech −8.7, GSC −7.5,
  Tyranids −7.2). Wave 71 proved this is NOT rules/stats/lists (IK verified
  faithful end-to-end) — it is the min-HP target AI never removing durable
  objective-holders. Lever #1 above is the fix.
- The objective-greedy AI tweak (gunline troops claim reachable objectives) was
  tested and shelved as a wash — confirms holding-better is not the bottleneck;
  taking-from-durable-holders is.

NOTE: the IK/CK multi-profile weapon mapper is DONE (shipped pre-wave-60);
do not re-implement it. See memory `project-knights-multiprofile-weapons`.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go".
- Per CLAUDE.md §10: every rule fix needs a Wahapedia/BSData citation. The citation audit is ENFORCING on commit (`BLOCK_ON_MISSING_CITATIONS=True`).
- **Always** prefix the eval: `PYTHONHASHSEED=0 ... python -m scripts.evaluate_vs_meta --battles 40 --use-archetype` (segfault workaround; memory `project-eval-pythonhashseed-segfault`).
- Model tiering (global `~/.claude/CLAUDE.md`): set `model` per Agent dispatch; sonnet for T2 audits, never inherit Opus.
- Verify-first: agent and memory claims have been wrong repeatedly this branch — confirm file:line / rule text before acting.
- cwd-leak into agent worktrees is recurring — `cd` to main worktree and confirm `pwd` before git ops.

## Wave close checklist

1. Cherry-pick agent commits from the main worktree (check cwd).
2. pytest sweep + N=40 eval (`PYTHONHASHSEED=0`, `--use-archetype`).
3. Per-faction diff vs prior eval JSON.
4. Archive oldest wave-close block to `AUTO_LOOP_LOG_archive.md` (keep ~3).
5. Write new wave-close block at top of `AUTO_LOOP_LOG.md`.
6. Update this file with new headline + next levers.
7. `python scripts/loop_cleanup.py`.
8. Commit + push (push only on explicit user "go").
