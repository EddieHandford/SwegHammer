# Scoring / victory-point model overhaul — scope + plan (wave 82)

**Date:** 2026-06-01. **Phase:** the user's Q6 ruling (`STAGE1_AUTONOMOUS_GOAL.md`
"Current phase — UPDATED 2026-06-01"; `LOOP_QA.md` Q6 RESOLVED). **Status:** plan only,
no code change — this mirrors the successful wave-73→74 and wave-78 plan→build pattern that
the ruling explicitly mandates ("scope/plan FIRST, then build environment-gated, with
per-matchup win% before/after").

## 1. The goal and the hard rails (from the ruling)

**Goal.** Make a durable camper's objective-holding stop OVER-converting into primary
victory points, by modelling the real 10th-edition Pariah Nexus scoring economy MORE
COMPLETELY — never by reducing scoring for armies "because they over-shoot."

**Why this is the lever.** Three faithful decision-logic levers (value-targeting wave 72,
focus fire wave 79, contest/deny wave 81) plus a sourced list re-fit (wave 80) all regressed
and were reverted with no nerf. The leftover Imperial Knights over-rate (and the durable
over-shooters generally) is a structural victory-points-versus-durability SCORING residual:
the simulator under-models how real tournaments out-score a durable camper through the full
secondary economy and board tempo (`project-faction-residual-rootcause`,
`project-ai-frozen-under-mae-first`).

**The hard rails (this is the sharpest metric-tuning surface in the project — guard hardest):**
- Every scoring change MUST be a faithful model of a REAL 10th-edition rule, CITED per standing
  rule 10 (`data/rule_citations.d/`), applied EVEN-HANDEDLY across all factions.
- The test is unchanged: *would this still be correct if it moved the metric the wrong way?* A
  scoring change whose only justification is the residual direction is metric-tuning — reject it.
- NO per-faction scoring weights. NO durability/camper penalties. NO re-weighting an existing
  card to move a residual.
- Build environment-gated, measured per-matchup on the durable-camper cells (Imperial Knights
  vs Chaos Space Marines / Adeptus Mechanicus / Adeptus Astartes) AND per-faction AND headline.
  Accept a temporary regression that the completed faithful model recovers.

## 2. The current scoring model (verified from the code, 2026-06-01)

Primary objective scoring — `Battle._score_objectives()` (`code/simulator.py:648`):
- 5 victory points per controlled objective (`Objective.vp_per_round`, `code/map.py:76`).
- Per-round cap 15 per side (`code/simulator.py:851`), i.e. at most 3 objectives count. Correct.
- Scores in rounds 2–5 only (`code/simulator.py:560`); game is 5 rounds (`MAX_ROUNDS`,
  `code/simulator.py:159`). Correct.
- Control = strictly-greater summed objective-control characteristic, one objective per squad by
  coherency (`_assign_army_oc`, `code/simulator.py:700`); ties at objective-control > 0 score
  nobody; a sticky owner is used ONLY at the 0–0 tie (`code/simulator.py:794`).
- One fixed map / objective layout every game; no mission variety.

Secondary scoring — assigned 2 Fixed + 2 Tactical once at battle start (`pick_secondaries`,
`code/secondaries.py:575`); total capped at 40 only at `_decide_winner` (`code/simulator.py:635`):
- Fixed (kill) pool of 4: Bring It Down, No Prisoners, Cull the Horde, Assassination
  (`code/secondaries.py:46`).
- Tactical pool of just 4: Engage on All Fronts, Behind Enemy Lines, Cleanse, Sabotage
  (`code/secondaries.py:49`). Engage/Behind-Enemy-Lines alternate by round; Cleanse/Sabotage
  score every round.

Winner — `_decide_winner` (`code/simulator.py:610`): wipe checks, then higher capped victory
points (secondary capped at 40, primary uncapped at game-total level), then a >10% surviving-
points tiebreak. No First Blood / Linebreaker / Slay-the-Warlord / mission bonuses.

## 3. Gap analysis versus real Pariah Nexus (the faithful candidates)

Source for all card text below: the Pariah Nexus mission pack secondary missions, verified
2026-06-01 against `https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-battles/` (cross-checked
names against the Goonhammer Pariah Nexus missions review). Each card listed here that a build
wave implements MUST get a verbatim-quoted `data/rule_citations.d/` entry before that wave commits.

**THE KEY FINDING.** The real Pariah Nexus secondary deck contains a whole family of
OBJECTIVE-HOLDING / BOARD-CONTROL secondaries that the simulator does NOT model — and these
are precisely the scoring paths a body army uses to out-score a durable camper. The simulator
models the two board-spread cards (Engage, Behind Enemy Lines) and two actions (Cleanse,
Sabotage), but NOT the cards that reward *controlling and taking objectives*:

| Real card | Scoring (verbatim-sourced) | What it rewards | In sim? |
|---|---|---|---|
| **Storm Hostile Objective** | 4 VP for controlling an objective the opponent controlled at start of turn | TAKING the camper's objectives | **No** |
| **Secure No Man's Land** | 2 VP one / 5 VP two+ No Man's Land objectives controlled | holding midboard objectives | **No** |
| **Area Denial** | 2 VP (no enemy within 3" of centre) / 5 VP (none within 6") | contesting the centre | **No** |
| **Defend Stronghold** | 3 VP controlling one+ objective in your deployment zone | holding home objectives | **No** |
| **Extend Battle Lines** | 5 VP controlling an objective in your zone AND in No Man's Land | spreading across objectives | **No** |
| **Overwhelming Force** | 3 VP per enemy unit destroyed that started in range of an objective (max 5) | fighting ON objectives | **No** |
| Containment | 3 VP per battlefield edge held (action, max 6) | board-edge spread | No |
| Recover Assets | 3 VP two zones / 6 VP three zones (action, one unit per zone) | multi-zone presence | No |
| Establish Locus | 2 VP near centre / 4 VP in enemy zone (action) | forward action | No |
| Marked for Death | 5 VP if an opponent-selected unit dies this turn | target priority | No |

A 9-to-11-model Imperial Knights army physically cannot complete the board-spread / multi-zone
/ take-and-hold cards as well as a 40-to-60-model army can — that asymmetry is a CONSEQUENCE of
the real rules plus the armies' real model counts, NOT a per-faction weight. Completing the pool
is pure fidelity, and it is even-handed (every army picks from the same pool, by the same rule).

**This also explains why wave-81 contest/deny failed.** In the simulator, taking an Imperial
Knights objective only DENIES it 5 primary victory points — but in real play, taking it ALSO
SCORES the taker 4 victory points (Storm Hostile Objective) plus Secure No Man's Land / Area
Denial. The scoring *reward* for the anti-camper play was missing, so the decision-logic lever
had nothing to bite on. The fix lives in the scoring model, exactly as the diagnosis said.

**Separately, the modelled cards have formula errors versus the real text (fidelity corrections,
direction mixed — implement because correct, measure honestly):**

| Card | Sim now | Real Pariah Nexus | Note |
|---|---|---|---|
| Engage on All Fronts | 2 VP / 3 VP / 5 VP at 2 / 3 / 4 quarters | 2 VP (3 quarters) / 4 VP (4 quarters), 6"+ from centre | sim OVER-scores it and scores at 2 quarters (real needs 3) |
| Behind Enemy Lines | flat 4 VP any unit in enemy zone | 3 VP one unit / 4 VP two+ | sim slightly over-scores single unit |
| Bring It Down | flat 3 VP per MONSTER/VEHICLE | 2 VP +2 (15+ wounds) +2 (20+ wounds) | real rewards BIG models more (a Knight = 6 VP) |
| No Prisoners | 3 VP per unit (max 5) | 2 VP per unit (max 5) | magnitude |
| Cull the Horde | 3 VP per 10+-model unit (max 3) | 5 VP per 20+-model / 25+-wound INFANTRY unit | threshold + magnitude |
| Assassination | 3 VP per character (cap 4) +1 warlord | Fixed 4 VP per character, or Tactical flat 5 VP | formula |
| (per-Fixed-mission cap) | none | max 20 VP per Fixed mission card | sim lacks it |

**Primary-economy candidates:**
- Sticky control should apply on ties at ANY objective-control level (real 10e core rule: a
  marker stays controlled by the last controller until the opponent has STRICTLY greater control),
  not only at 0–0. NOTE the honest direction: this RAISES Imperial Knights (it keeps contested
  objectives for the last holder) — so it is wrong-for-the-metric, which is exactly why it must
  be implemented only as a cited correctness fix, never reached for to move a residual, and why
  it is sequenced LAST and measured in isolation.
- Verify whether the chosen mission applies a game-total primary cap; if a real cap exists, model
  it (the sim currently caps per-round at 15 but not at the game total). Direction: clips runaway
  primary leaders slightly. Low priority; verify the real rule first.

## 4. The build sequence (the next waves)

Each wave: environment-gated, one coherent change, N=40 archetype eval, per-matchup Imperial
Knights cells + per-faction + headline before/after, citation added before commit, keep ON only
if it is a clear fidelity win (and never gate a card on whether it helps the metric).

**Wave 83 — Tier A, the targeted lever: add the objective-holding / board-control secondaries.**
Expand the Tactical pool with the missing take-and-hold cards (Storm Hostile Objective, Secure No
Man's Land, Area Denial, Defend Stronghold, Extend Battle Lines; Overwhelming Force if cheap to
add), scored per the verbatim real text, picked per army by best-fit (the same greedy "take what
you can reliably complete" rule real players use — even-handed, both sides use the identical
function). Apply the per-Fixed-mission 20-victory-point cap so the expansion stays bounded. This
is the faithful root-cause lever and the one the ruling named first. Expected direction: body
armies (the under-shooters — Astra Militarum, Genestealer Cults, Chaos Daemons, Chaos Space
Marines) gain the real scoring paths they use to out-score a camper; the 9-model Imperial Knights
cannot complete them as well. Drill the Imperial-Knights-versus-body-army cells specifically.

**Wave 84 — Tier B, the modelled-card formula corrections.** One card per measurement (or grouped
if clearly independent): Engage on All Fronts → real 3-or-4-quarter / 2-or-4 VP; Behind Enemy
Lines → 3/4; Bring It Down → bracketed 2+2+2; No Prisoners → 2; Cull the Horde → real threshold;
Assassination → real formula. Each is a correctness fix kept if correct; measure direction (some
reward the over-shooters' killing — report honestly, do not gate selectively).

**Wave 85 — Tier C, the primary-economy correctness fixes (measured in isolation, last).** Sticky
control on ties at any objective-control level (flag: raises Imperial Knights — implement because
it is the real core rule, not for direction); game-total primary cap only if a real cap is
verified. These are the candidates whose direction is wrong-for-metric, so they are last and
isolated, and their disposition is "is it the real rule?" not "does it help?".

The interim approved by the watchdog stays available: small clean NON-regressing under-shooter
correctness / datasheet fixes can land in any wave alongside.

## 5. Measurement + acceptance protocol

- Baseline: gated mean absolute error 4.95 (wave 81). Headline target → 0 / per-faction noise floor.
- Each wave reports: headline gated mean absolute error, the Imperial Knights residual, the
  Drukhari residual (the other big over-shooter — watch it does not balloon), the under-shooter
  residuals (Chaos Space Marines, Chaos Daemons, Chaos Knights), and the per-matchup Imperial
  Knights win% on its 100% cells.
- A Tier-A/B card is kept ON only if it is a clear fidelity win; a regression is diagnosed (is a
  later card needed to complete the economy?), not reverted-to-chase-metric and not selectively
  gated. A Tier-C correctness fix is kept if it is the real rule, whatever the direction.
- If completing the secondary economy (Tier A) does NOT bring the durable campers down, that is
  itself a finding — it would mean the residual is in the PRIMARY economy or the model-count
  representation, and the next escalation names that. Report it; do not nerf.

## Wave 83 result — Tier A BUILT + LANDED (gated 4.95 → 4.17, in-band 6 → 9); IK finding sharpened to objective-over-control

Built the five take-and-hold secondaries (`Battle._score_board_secondaries`, env-gated, landed
default-ON after the A/B). Result (N=40): gated mean absolute error **4.95 → 4.17 (−0.78)**,
factions in band **6 → 9** — a clear faithful aggregate win, so kept. Most over-shooters eased
(Drukhari +18.6 → +9.7, Custodes +7.4 → +2.7, Adepta Sororitas +8.4 → +2.8, T'au +5.9 → +0.6,
World Eaters / Emperor's Children down) and the board-control under-shooters rose (Chaos Space
Marines −19.2 → −11.3, Chaos Knights into band).

**But Tier A made Imperial Knights WORSE: +19.1 → +29.2.** The card family rewards objective
CONTROL, and a durable Knight over-controls objectives, so it banks the new board secondaries
itself — the +10 IK jump the instant objective-based scoring was added IS the proof. This
**falsifies the "missing scoring paths" hypothesis for IK** and sharpens the diagnosis: the IK
residual is **objective-OVER-CONTROL** (a durable, high-Objective-Control, low-unit-count army
holds the board uncontested — consistent with wave-81's contest/deny failure), a model-count /
Objective-Control-representation problem, NOT a scoring-economy gap. Per the watchdog's Q7
pre-authorisation this is reported, not nerfed. The next IK lever (supersedes Tier C as the IK
priority) is **objective-takeability / the Objective-Control contest** — verify whether a body
army correctly out-Objective-Controls a Knight on a shared marker, and whether opponents can ever
wrest / block a Knight off objectives. Tiers B (kill-card formula corrections) and C (sticky
control) remain as queued correctness fixes but are no longer expected to be the IK lever.

## 6. Hard-rails self-check (apply before each build wave commits)

For every scoring change, the build wave must be able to answer YES to all:
1. Is it a verbatim-cited real 10th-edition Pariah Nexus rule (`data/rule_citations.d/` entry)?
2. Is the mechanism identical for both armies (no per-faction branch, no keyword-gated weight that
   is not in the real card)?
3. Would I implement it even if it moved the metric the wrong way? (If the only argument is the
   residual direction → reject.)
4. Is the asymmetric effect a CONSEQUENCE of the real rule plus real army composition, not a
   coded preference for the under-shooters?
