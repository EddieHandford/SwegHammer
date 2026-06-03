# Secondary economy — authenticity rebuild plan (wave 133)

**Date:** 2026-06-03. **Status:** plan-first, build over subsequent waves. **Authorised** by the user
(LOOP_QA, hard requirement) + the watchdog's wave-131/132 sequence. This is the SECOND HALF of the anti-Knight
work — a SEPARATE faithful build (real 10e secondary rules + 3 authenticity layers), NOT an M4 refinement, NOT a
knob. Gated, cited, even-handed, **no Knight penalty, no faction branch, no tuning to force the result**. The
hypothesis (a low-unit army under-scores secondaries) is the TEST, not a target.

## 1. The goal + the hypothesis (why this may break the primary-half inseparability)

The board-control half (M4) washed because its IK-fix and its over-shooter inflation are the SAME massing
mechanism (inseparable). The secondary economy is asymmetric on a **DIFFERENT axis: a low-MODEL army cannot
churn the deck or spare units to perform actions / dedicate to held cards.** The Knight's lack of units is then
punished on BOTH axes (board control AND secondaries). Crucially, several over-shooters M4 inflated are ELITE
LOW-MODEL armies (Chaos Knights, Custodes, alongside Imperial Knights) — the secondary economy would pull THOSE
DOWN too (they can't churn/dedicate either), potentially **counteracting M4's inflation of them where M4-alone
couldn't**, while HIGH-MODEL under-shooters (Daemons, Tyranids, Astra) are rewarded on both axes. Honest caveat:
it might instead inflate the high-model over-shooters (both axes help them) — it is EMPIRICAL. Build it, run the
COMBINED test, measure per-faction secondary-VP + win rate.

## 2. The current architecture (what auto-awards today)

`_score_one_card` (`simulator.py:1487`) routes each card to a scorer that AUTO-AWARDS on a condition:
- **Kill cards** (Bring It Down / No Prisoners / Cull / Assassination) → `score_round_delta` on the kill
  snapshot. Auto-award on kills is AUTHENTIC (they aren't actions) — KEEP.
- **Position cards** (Engage / Behind Enemy Lines) → `score_position_delta` (`secondaries.py:531`) checks whether
  a unit happens to sit in a quarter / the enemy deployment zone at scoring time. **This is the inauthentic
  auto-award — a Knight with a body incidentally in a quarter scores Engage for free.**
- **Action cards** (Cleanse / Sabotage) → already flag a unit to forgo shooting (`_assign_cleanse_actions`
  `simulator.py:1019`). Partly authentic; extend to the full action contract.
- **Board take-and-hold** (Secure / Defend / Extend / Storm / Area Denial) → `_score_board_secondaries` auto on
  Objective Control. Holding IS the condition — but the DEDICATION to GET there is the missing half.

The `pursue_target` flag on units (wave 121) is the substrate for committing a unit to a card; today it only
adds a movement bias ON TOP of auto-scoring — the scoring never CHECKED dedication. The rebuild makes scoring
GATE on dedication.

## 3. The three authenticity layers

### Layer 2 — DELIBERATE DEDICATION (THE CRUX, build first)
Scoring of a position / action / board card counts ONLY units the army DELIBERATELY DEDICATED to it, not units
incidentally present. Mechanism:
- A `dedicated_card` field on `Unit` (like `pursue_target`): set when the AI commits a unit to a held card this
  turn. One unit per card per turn (a card needs one dedicated body).
- An AI **dedication planner** (extend `_assign_card_pursuit`): each of its turns, for each held card the army
  can pursue, assign ONE spare unit (not needed for the army's primary combat/objective plan) as `dedicated_card
  = <card>` and bias its move toward the card's geographic goal. **Spare-unit detection is the even-handed
  pinch:** a 5-6-unit Knight has no spare bodies after its combat/objective commitments → dedicates none →
  scores those cards 0; a broad army dedicates its surplus → scores. No faction branch; the asymmetry is
  emergent from unit count.
- `score_position_delta` (and the board/cleanse scorers) change from "is a unit in the zone?" to "is a
  DEDICATED unit in the zone (and surviving)?" — gate the per-card award on `dedicated_card == <card>` for the
  contributing unit. Incidental presence no longer scores.

### Layer 1 — ACTION CARDS COST A UNIT (build second)
The action cards — existing Cleanse / Sabotage + the NEW **Establish Locus / Recover Assets / A Tempting
Target** (text in `data/reference/wahapedia_ca2025-26.txt`) — score ONLY when a dedicated unit COMPLETES the
action: it forgoes shooting AND charging that turn, stays (does not move off the action point), and SURVIVES to
the end of the turn. Model a `performing_action` flag (the unit can't shoot/charge while performing); if it dies
or is forced off, no score. NEVER auto-award. Cite each card + the 10e "Actions" core rule.

### Layer 3 — TIMING (build third)
Score at the end of EACH PLAYER'S OWN TURN on the cards it holds + the dedications it completed that turn (the
eval runs IGOUGO, so per-turn scoring is available — reuse the `only_for` plumbing from the wave-116
per-Command-phase primary scoring). Replaces the end-of-round both-armies scoring for the Tactical track.

## 4. Build sequence (each gated `SWEG_SECONDARY`, cited, even-handed, A/B at each stage)

- **Stage A — dedication substrate + Layer 2 (the CRUX).** `dedicated_card` field; the dedication planner
  (spare-unit → held card); gate the position + board + cleanse scorers on dedication. A/B N=40 (per-faction
  secondary-VP: does a Knight's secondary VP drop vs a broad army's?). This alone tests the core hypothesis.
- **Stage B — Layer 1 action cards.** The 3 new action cards as real actions (forgo shoot/charge, stay,
  survive); extend Cleanse/Sabotage to the full contract. Cite each.
- **Stage C — Layer 3 per-turn timing.**
- **Stage D — the COMBINED test.** M4-narrow + full-secondary, ABLATED (each gate alone vs combined), N=40 →
  N=80, per-faction secondary-VP + win rate, over-shooter watch. **If COMBINED net-improves → keep + FLAG the
  Stage-2 re-derivation. If COMBINED ALSO washes → the user's hypothesis is tested + exhausted → report the
  floor + STOP** (no knob, no re-fit).

## 5. Hard-rails (every stage)
1. Faithful: real 10e secondary rules (cards, actions, timing) — cite each card + the Actions core rule from
   `data/reference/wahapedia_ca2025-26.txt` / Wahapedia; if a card's text can't be sourced, STOP and ask.
2. Even-handed: NO faction branch, NO Knight penalty; the low-model pinch is EMERGENT from spare-unit count
   (any army short on spare units scores less). Wrong-way test: scoring-from-dedication is the more faithful
   rule even if it moved the metric the wrong way.
3. Gated `SWEG_SECONDARY` (default OFF); OFF path byte-identical; A/B at each stage; confirm N=80 before any
   default decision (the M2/pursuit/N=40 noise lesson).
4. The hypothesis (Knight under-scores secondaries) is the TEST — measure the per-faction secondary-VP split;
   do not tune to force it.
