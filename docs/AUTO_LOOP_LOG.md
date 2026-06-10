# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 203 (2026-06-06) — The Ritual built + a measurement CONFOUND caught & fixed: the CLEAN deck = gated 4.89 (−0.30 vs baseline). Avenue 1 is a faithful WIN after all (was hidden by the confound)

Bounded avenue 1 (watchdog steer): WebFetch-classified the 6 unmodelled primaries (action = The Ritual + Unexploded
Ordnance; pure hold = Linchpin / Hidden Supplies / Supply Drop). Built **The Ritual** (commit, cited
`simulator.primary_the_ritual`): 5 VP per No Man's Land marker controlled (cap 15), home markers score 0 — its place-marker
Action is a noted omission (fixed sim objectives). All-Ritual upper bound was the best yet (gated 4.77) via **over-shooter
compression** (No-Man's-Land-only punishes camping melee armies), not IK-cracking.

Then the 5-mission deck came back BYTE-IDENTICAL to the 4-mission deck — a **measurement confound** I'd introduced:
`_pick_rotation_map` keys the map on `s % 5` and the mission key was `pair_seed % 10 == s % 10`, so (5 | 10) every mission
was LOCKED to one of the five maps; The Ritual only drew the all-No-Man's-Land map, where it equals Take and Hold. **Fixed**
(commit): decode faction indices into the mission key so the draw is independent of `s % 5` — verified every mission spans all
5 maps at the exact 60/10/10/10/10.

**Clean decoupled 5-mission deck (N=80): gated 4.89 — a real −0.30 vs the 5.19 baseline.** The confound had HIDDEN the
rotation's genuine benefit: over-shooters compress toward target (Emperor's Children 7.63→4.79, Thousand Sons 5.11→3.25,
Sororitas 2.44→1.15) AND IK is net-DOWN (70.4 / gated 19.70 vs 71.5 / 20.84) — so Purge's re-inflation is outweighed and the
basis of the (b)-don't-flip ruling is gone. Avenue 1 is a faithful net-positive after all. **Recommended (routed): FLIP
SWEG_PRIMARY_DECK default-ON** (real CA-2025-26 distribution as the production frame, retires the wave-187 all-Take-and-Hold
unfaithfulness, re-bases the headline to ~4.89), skip Unexploded Ordnance (diminishing/complex), then avenue 2. Tests green,
audit clean, cli 0.

## Wave 202 (2026-06-05) — FAIR avenue-1 measurement COMPLETE (Terraform added): 4-mission deck = gated 5.19 (baseline). Scoring rotation is faithfully DONE + metric-neutral by construction → decisive lever is avenue 2 (selective displacement)

Watchdog asked for a FAIR avenue-1 ceiling: keep the Burn (affirmed, default-ON for the Scorched mission), keep the deck
built+gated (NOT flipped — Purge over-inflates IK), and MODEL TERRAFORM, then re-measure the deck. Done:
- **Burn default-ON for the Scorched mission** (commit, SWEG_SCORCHED_BURN=0 disables for A/B; inert in the default eval).
- **Terraform primary + Terraform Action** (commit `a87dd21`, cited `simulator.primary_terraform`): 4 VP/controlled marker
  (cap 12) + 1 VP/marker terraformed by you. The Action mirrors the Burn infra + the `_unit_can_perform_action` contract
  (STARTS on range, COMPLETES on control — WebFetch-verified verbatim). Emergent displacement: a Knight's all-productive
  units terraform ~0, a body army's spare bodies do.
- **All-Terraform upper bound (N=80): IK 71.7→63.6% (gated ~21→12.96, −8) and AM 24.9→32.4 / AdMech 26.8→29.5** — the
  mechanism cracks IK AND lifts the under-pole, the right direction. But it ALSO lifts the over-shooters (WE 15.70, EC 9.40,
  Sororitas) because it's a blanket forward-aggression reward → headline ~neutral (5.28).
- **4-mission deck re-measure (TaH 70% / Purge 10% / Scorched 10% / Terraform 10%, N=80): gated 5.19 = the baseline.** IK
  71.5% (20.84), unchanged. The 1/10 crack dilutes ~10× and Purge re-inflates IK.

**Verdict — avenue 1 is faithfully DONE and metric-neutral BY CONSTRUCTION:** a primary-SCORING lever is a blanket
forward-aggression reward; it cannot distinguish the durable Knight we want DOWN from the aggressive melee armies we want
HELD. Three of the ten real CA-2025-26 primaries now score their real rule; all kept (faithful, gated). The decisive lever
is **avenue 2 — selective displacement (maneuver/board-control AI that pushes/removes the un-removable Knight off markers)**,
the user's reserved decide-point (escalated via the watchdog). Tests green, audit clean, cli 0.

## Wave 201 (2026-06-05) — AVENUE 1 (mission/scoring displacement) MEASURED → metric-NEUTRAL; the displacement lever is Avenue 2 (maneuver), not the scoring deck

User greenlit the displacement re-model via 3 avenues (measured/bounded). Avenue 1 = mission/scoring pressure. Built the
**Scorched Earth Burn (Raze) Action** (env-gated `SWEG_SCORCHED_BURN`, commits `62232a1`/`72e3cca`): a controlling unit
Burns a No Man's Land / enemy-DZ marker from round 2, removing it for 5/10 VP — the faithful CA-2025-26 rule (WebFetch-
verified; the reach-vs-CONTROL check caught a flashy-but-unfaithful first build). Refinements: BURN_CAP 2→1 ("ONE unit")
+ round≥2 gate. **All-Scorched upper bound (N=80): IK 71.7→60.7%, gated 20.99→10.00 — the Burn DISPLACES the Knight.**
Then built the **deck-weighted rotation** (`SWEG_PRIMARY_DECK`, commit `fdba060`): each game draws one primary from the real
10-card pack (verified 80% Take-and-Hold / 10% Purge / 10% Scorched; 7 unmodelled cards fall to Take-and-Hold).

**Deck-weighted A/B (N=80): gated 5.27 vs the 5.19 baseline = NEUTRAL (+0.08, within noise).** Decomposition: deck IK 72.4%
is *above* the Take-and-Hold baseline because **1/10 Purge games push IK to ~90%** (kill-weighted, IK out-kills body armies
on unit-count — a FAITHFUL Purge model, 4/4/4/4 cap 12), which out-weighs the 1/10 Scorched crack. The Scorched horde
over-flood diluted out correctly (Tyranids 11.50→4.09, Orks 7.04→1.77). WebFetch-verified the two remaining anti-hold
candidates are NOT levers: **Terraform** is Take-and-Hold-with-a-+1-bonus (IK fine), **The Ritual** scores No Man's Land
markers only (rewards mobile-durable IK pushing forward, would *inflate* it). **Verdict: the real deck has no scoring formula
that cracks IK except the Burn, and at 1/10 it's too dilute — Avenue 1 (scoring) is ~tapped at neutral.** The displacement
the user is after is physical: Avenue 2 (maneuver/board-control AI), applicable every game. Deck + Burn kept GATED (faithful
substrate, not a headline win); avenue-pivot routed to the watchdog. Tests green, audit clean, cli 0.

## Wave 193 (2026-06-05) — FREE-CONTEST extension LANDED default-ON (headline 5.52→5.19): a spare in-range gunline contests a winnable enemy marker WHILE still shooting (zero shot-cost) — recovered the shooty factions the pure contest over-corrected; the over-pole PLATEAUED (IK ~21) → PIVOT to the over-shooter cluster next

Watchdog steer: continue the over-pole via the contest. Wave-193 INSTRUMENT (diag_ocflip free-contest decomposition, commit 03f3503):
of the reachable opponent OC on the still-flippable Knight markers (now 23% with the contest on, down from 35%), **86% is shooty units
that could shoot FROM the marker** (a zero-cost contest), 14% melee, **0% would lose their shots**. The existing #12 OBJECTIVE-AWARE
REPOSITION already free-contests but only to a unit's SINGLE best objective, so a winnable enemy marker that loses the distance-
competition to a closer hold stays uncontested.

**Built the free-contest extension (gated SWEG_FREECONTEST, commit 2c9ef19):** a SPARE in-range SHOOTY/HEAVY unit redirects onto a
WINNABLE (bracket-aware effective-OC) + REACHABLE + SHOOTABLE enemy marker even when not its single best, with JUST-ENOUGH (skip a
marker we already winnably contest) + AFFORDABLE (the pre-existing hold-check keeps marginal holders). N=80 A/B → KEEP + FLIP
default-ON (dad5ac3):
| | gated MAE | Imperial Knights | in-band |
|---|---|---|---|
| baseline (wave 192 contest) | 5.52 | 71.9% / 21.19 | 1-2/22 |
| + SWEG_FREECONTEST | **5.19** | 71.7% / 20.99 | **4/22** |

**Value-pull tell PASSED decisively** (the decider): NO shooty faction cratered — the factions the PURE contest had over-corrected
RECOVERED toward target (Aeldari 38.6→44.0 in band, T'au 47.9→51.4 in band, Necrons 49.9→51.1 in band) because their in-range
gunlines now contest WHILE still shooting (faithful — a real mobile gunline does this). So the −0.33 headline is the shooty factions'
faithful objective-game recovery, zero shot-cost. **BUT Imperial Knights barely moved (21.19→20.99): the over-pole has PLATEAUED on
the contest family** (damaged-bracket → contest → free-contest, the full arc 25.63→20.99). New baseline gated **5.19**.

→ PER THE WATCHDOG'S STANDING PLATEAU→PIVOT PLAN: the contest is near its over-pole ceiling. NEXT AXIS = the OVER-SHOOTER CLUSTER
(Thousand Sons 67.7 / Emperor's Children 66.1 / World Eaters 60.7 / Custodes / Sororitas / Votann / Drukhari all systematically over —
a separate elite/aggressive over-modeling residual the TSons diagnosis opened). Instrument-first WHY they're over (combat output vs
list). The under-side (AM 13.9 / AdMech 11.6 gated) is untouched by the contest (gunlines, no spare bodies) — a separate
durable-shooty-vehicle axis for later.

## Wave 192 (2026-06-05) — BALANCED OBJECTIVE-CONTEST AI lever LANDED default-ON: the FIRST lever in many waves to move the over-pole DOWN (IK gated 25.63→21.19, −4.44) — faithfully, via a balanced contest (over-flood tell PASSED), headline 5.71→5.52

The wave-191 damaged-OC generalization gave the opponent a real way to flip the Knight without killing it (a chipped Knight is OC 5,
not 10). The wave-192 OC-flip INSTRUMENT (scripts/diag_ocflip.py, gated read-only, commit acf6cd3) localized the over-hold as a
GENERAL AI-not-contesting gap: of 650 obj-rounds a big Knight/Titanic controls a marker, the opponent had reachable nearby OC to flip
228 (35%) but never committed bodies; the damaged-only slice is tiny (12). Watchdog greenlit the BALANCED contest lever plan-first
(docs/OC_CONTEST_LEVER_PLAN.md, acf3b41) with the wave-95 Stage-E over-flood rail front-and-centre.

**Built (gated SWEG_CONTEST, commit 6e155dc) — refines the EXISTING STEAL value in pick_move_intent, not a new flood system:** an
enemy-held marker's steal value is made WINNABLE + bracket-aware (×1.7 only when our potential EFFECTIVE OC > enemy EFFECTIVE OC
there — new `_effective_oc_value` / `_effective_oc_on_objective` helpers, since raw `_oc_on_objective` misses the bracket; ×0.3 if
unwinnable even by committing this body; ×0.6 JUST-ENOUGH no-pile-on once we already win it). The AFFORDABLE guard is the pre-existing
hold-check — a marginal friendly-marker holder holds and never reaches the contest, so only SPARE bodies contest. Mechanism (diag):
flippable-but-uncontested 34%→27%.

**N=80 A/B → KEEP + FLIP default-ON (2ef7c4c), per the watchdog keep-if-faithful decider:**
| | gated MAE | Imperial Knights | Chaos Knights |
|---|---|---|---|
| baseline (wave 191) | 5.71 | 76.3% / 25.63 | 6.42 |
| SWEG_CONTEST=1 | **5.52** | **71.9% / 21.19 (−4.44)** | **1.29 (in band)** |

**The over-flood TELL PASSED** (the decider): the contesting under-shooters HELD or improved — Astra Militarum 28.7→28.6, AdMech
28.1→28.8, Necrons 46.3→49.9 (toward its 53.5 target) — so IK fell via a BALANCED contest (spare bodies flip winnable markers), NOT a
Stage-E cheap-OC flood (which would crater the contesters' own win rate; it regressed to 6.50 in wave 95). Even-handed side-effect:
Aeldari (+3.2→−2.9) and Chaos Daemons (−1.1→−5.8) fall too because THEIR big holders (Wraithknight, Greater Daemon) now get contested —
faithful, though they overshoot target (a TUNING note: the ×1.7 boost may be slightly hot for those; candidate ×1.5 follow-up, NOT a
reject). New baseline gated **5.52**. The over-pole is finally reachable by faithful objective-game fidelity — the user's "keep hunting,
77% is an unfaithful mechanism not a floor" ruling vindicated.

## Wave 191 (2026-06-05) — keyword instrument REFUTED + the DAMAGED-BRACKET GENERALIZATION LANDED default-ON (even-handed, metric-neutral 5.76→5.71): the real per-datasheet "Damaged" bracket now degrades ALL 260 big models, not just the 6 Knight datasheets

Watchdog priority #1 (keyword instrument) REFUTED: anti-tank keyword coverage (Lethal/Sustained/Devastating/Heavy/Melta) is at
PARITY-or-above BSData on catalogue weapons (catalogue 4/18/14/11/22% vs BSData 2/5/9/12/15%), the mechanics fire in attack(), the
mapper extracts them — so "the opponents' guns are too weak" is false. That closes the anti-tank STRENGTH axis (commit 445638b).

Then built the watchdog-greenlit #77 DAMAGED-BRACKET GENERALIZATION (docs/DAMAGED_BRACKET_GENERALIZATION_PLAN.md), 5 stages:
- **S1 (a51f9e4)** mapper `extract_damaged_bracket` parses the 10e "Damaged: 1-X Wounds Remaining" ability → 4 flat parsed.json
  fields (threshold, oc/hit/attacks penalty), Hit-regex anchored on "this model makes an attack" (excludes the defensive −1-to-be-hit).
- **S1 FIX (c2a9639)** — the pre-flip Knight-coverage check (watchdog's "verify before flip" rule) CAUGHT A REAL BUG: only 1 of 42
  Knights extracted, because the mainline Knights reference a SHARED Damaged profile in a linked Library, not inline. The first A/B
  (5.95) was INVALID (Knights silently lost their penalty → IK spuriously 27.48). Fixed via `_gather_damaged_profiles` resolving
  infoLink/entryLink targetIds through the registry. Knights 1→42 (0 missing); total bracketed units 72→260; strictly additive,
  deterministic.
- **S2 (112c1bf)** plumbed to UnitProfile (flat ints, hashable). **S3+4 (5f47b3c)** data-driven `_effective_oc` + `attack()` gated
  SWEG_DMGBRACKET; citation `simulator.damaged_bracket` (verbatim Stormsurge + Knight) + registered.
- **S5 FLIP (adb3000)** — the corrected N=80 A/B was METRIC-NEUTRAL (gated **5.76 → 5.71**, IK 25.52 → 25.63 unchanged, Chaos Knights
  improved) and strictly more faithful, so per the watchdog flip criterion (faithfulness + correct extraction, NOT metric direction)
  SWEG_DMGBRACKET is now DEFAULT-ON and the Knight-only SWEG_DMGOC/SWEG_DMGHIT heuristic is RETIRED. The default sim now degrades the
  Objective Control + Hit roll of every model with a real bracket (Stormsurge, Custodes/World Eaters dreadnoughts, AdMech/Necron
  vehicles, all Knights). Data-driven Knight values reproduce the retired heuristic exactly. **New baseline: gated 5.71.**

NET: removed a known metric-favorable bias (Knight-only damaged nerf) for an even-handed faithful rule, at neutral metric cost. The
over-pole is UNMOVED (IK still ~25.6 gated) — confirming again the Knight over-rate is NOT a combat/durability mechanic. Watchdog's
named next live axis: the user's OC-FLIP over-HOLD idea (collapse the Knight's objective by reducing its effective OC below
threshold + contesting bodies, no kill needed) — and the generalized damaged-OC bracket is now a faithful substrate for it (a damaged
Knight's OC really does drop). NEXT.


---
*Older waves archived to `docs/AUTO_LOOP_LOG_archive.md`. Decision index: `docs/DECISION_LEDGER.md`.*
