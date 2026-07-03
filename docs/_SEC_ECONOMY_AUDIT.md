# The secondary-economy fidelity audit

**Read-only.** Why does the simulator score roughly half the secondary victory
points a real Chapter Approved 2025-26 game produces (sim ~10-12 per player per
game against the real ~22.7 in `docs/REAL_META_SIGNATURES.md`)? This audit
enumerates the printed Secondary Mission rules card by card, replays a
stratified and an anchor-wide sample of anchor games with per-card
instrumentation, and lists every print-versus-simulator divergence ranked by
its expected points-per-game impact. Owner ruling in force: **rules-accurate
only, no knobs** — every fix below is "implement a printed rule the simulator
omits", never a tuning constant.

Base: branch `claude/sec-economy-audit`, cut from `origin/claude/sim-calibration-18`
top commit `cc6f388`. Scratch instrumentation: `scripts/_sec_audit_replay.py`
(per-card capture), `scripts/_sec_audit_aggregate.py` (lean anchor-wide),
`scripts/_sec_audit_analyze.py` (tabulation). Data: `data/_sec_audit_replay.json`
(180 stratified games), `data/_sec_audit_anchor.json` / the aggregate log.

Default gate state audited (production defaults): `SWEG_TAC_DECK` **on**,
`SWEG_TAC_DECK_CONSUMER_FIX` **on**, `SWEG_TACDECK_BIG_GAME` **on**,
`SWEG_TIER_A` **on**, Cleanse/Sabotage **on**; `SWEG_ACTION_ECONOMY` **off**,
`SWEG_SECONDARY` **off**, `SWEG_TAC_VOLUNTARY_DISCARD` **off**,
`SWEG_SECONDARY_HANDCAP` **off**, `SWEG_SECONDARY_PURSUIT` **off**.

## 1. The headline reproduction

| Measure | Anchor-wide (n=600 players) | Stratified (n=360) | Real meta target |
|---|---|---|---|
| Secondary victory points / player / game | **11.29** | 10.25 | **~22.7** |
| — by chosen track: FIXED | 15.92 (24% of players) | 13.60 (17%) | — |
| — by chosen track: TACTICAL | **9.79 (76% of players)** | 9.55 (83%) | — |

The anchor-wide 11.29 reproduces the ~11.7 the task cites. The simulator
under-pays secondaries by ~11 points per player. The whole shortfall lives on
the **Tactical track**, which ~76-83% of armies are routed onto and which scores
only ~9.8 — while the Fixed track scores ~16. The Tactical track is the broken
surface.

### The under-payment inverts the counter-weight the endgame needs

The per-faction secondary split (anchor-wide) ties this audit straight to the
durability endgame. The **durable armies score the MOST secondary** and the
**body armies that should out-score them score the LEAST**:

| Lowest secondary VP/player | | Highest secondary VP/player | |
|---|---|---|---|
| Death Guard | 7.41 | Chaos Knights | 18.56 |
| Orks | 8.14 | Imperial Knights | 17.52 |
| Necrons | 8.57 | Grey Knights | 15.12 |
| Tyranids | 8.64 | Aeldari | 14.80 |
| World Eaters | 8.81 | Adeptus Astartes | 13.97 |

The Knights sit on the **Fixed** track, where their two kill cards score cleanly
every round (15.9 average); the body armies (Death Guard, Orks, Necrons,
Tyranids) sit on the **broken Tactical** track and ossify (9.8 average). This is
exactly backwards from the real-game counter-weight the durability wave
identified: in reality a body army out-*scores* the durable primary-banker on
secondaries, and that is what caps the durable's win probability. The
simulator's broken Tactical track **suppresses the very out-scoring that should
punish durable camping** — Death Guard (the +21.7 top over-pole) is left with the
lowest secondary total in the game precisely because the opponents who should be
beating it on cards cannot cycle their decks. Closing the Tactical-track gap is
therefore not a side-quest; it is the missing half of the durability fix.

## 2. Why the Tactical track under-pays: the 2-card hand ossifies

A Tactical army in the simulator draws a 2-card opening hand and only ever
replaces a card it *achieves* (scores 1+ victory point from). It has no way to
shed a card it cannot score. The instrumentation shows the consequence starkly:

- **71.7%** of all held-card-rounds scored **zero** (2114 of 2949).
- A Tactical army draws only **4.40 distinct cards** out of the 12-card pool
  across the whole game (median 4; some draw only their opening 2 and never
  redraw once).
- **~60%** of every deck card is left **undrawn** at game end — the deck barely
  cycles.
- **9.4%** of Tactical players score **zero** secondary victory points for the
  entire game — their two opening cards clogged and never scored.
- 358 held cards sat un-scoring for **3+ consecutive rounds**; 162 of those sat
  the **full five rounds** without ever scoring.

In real Chapter Approved 2025-26 Tactical play a player aggressively sheds
unscoreable cards through THREE printed mechanisms the simulator omits (the
"When Drawn" redraw clause, the end-of-turn voluntary discard, and the New
Orders stratagem) and so cycles ~10-12 cards a game, reliably finding
scoreable ones. The simulator does none of this, so its Tactical hand freezes.

## 3. Divergence list — ranked by expected points-per-game impact

### D1 — The Tactical hand never sheds a dead card (dominant, est. +6 to +9 VP/player)

**Printed rule (three separate clauses the simulator omits):**

*When-Drawn redraw*, per card, e.g. Cull the Horde: "**When Drawn: If there are
no enemy units on the battlefield that satisfy the condition below, you can
discard this card and draw a new Secondary Mission card.**" Behind Enemy Lines /
Defend Stronghold / Storm Hostile Objective / Display of Might: "**When Drawn: If
it is the first battle round, [you can] draw a new Secondary Mission card and
shuffle this card back into your Secondary Mission deck.**" Marked for Death: "…
If there are no units from their army on the battlefield, discard this card and
draw a new Secondary Mission card." (Source:
https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/ ; the Bring
It Down When-Drawn clause is already quoted verbatim in-repo at
`data/rule_citations.d/secondaries_pariah_nexus.json#simulator.tactical_deck_big_game`.)

*End-of-turn voluntary discard*: "**At the end of each player's turn, each player
using Tactical Missions does the following… First, if you scored 1 or more VP
from a Secondary Mission card, discard that card – it is achieved. Then, you can
discard one or more of your active Secondary Mission cards. If you do, and it is
your turn, you gain 1CP.**" (Source: as above; already quoted in-repo at
`…#simulator.tactical_voluntary_discard`.)

**Simulator behaviour:** `Battle._init_tactical_deck` (`code/simulator.py:3687`)
deals two cards blind with no When-Drawn check; `Battle._score_tactical_hand`
(`code/simulator.py:3830`) discards only *achieved* cards and refills. The
voluntary-discard half exists but is gated **off** (`SWEG_TAC_VOLUNTARY_DISCARD`
default off, `_tac_voluntary_discard_enabled`, `code/simulator.py:3662`), and
even when on it discards at most one card per turn and only after a card has been
held a full round. The When-Drawn redraw clause is not modelled at all (the sim
explicitly defers it, see the `tactical_deck_big_game` citation's approximation
note).

**Direction & magnitude:** the simulator holds dead cards a real player would
have shed on draw or at end of turn, freezing the hand at ~4.4 cards seen per
game. Restoring the printed shedding would roughly double the cards a Tactical
army cycles through (to the real ~10-12) and, at the same per-card achievement
rate, roughly double its achievements — lifting Tactical secondary victory
points from ~9.5 toward ~18-20. Evidence: §2 (71.7% zero-holds; 4.4/12 cards
drawn; 9.4% zero-scoring games).

### D2 — Cleanse / Sabotage actions are assigned from the whole pool, not the held hand (est. +2 to +4 VP/player)

**Printed rule:** a unit performs an Action only for a Secondary Mission it is
trying to score, and while performing it "**that unit is not eligible to shoot or
declare a charge**" (Actions core rule, Wahapedia core-rules / reproduced on
https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/ ). Cleanse and
Sabotage both "**START: Your Shooting phase**"; the unit is spent for the turn.

**Simulator behaviour:** `_assign_cleanse_actions` (`code/simulator.py:2015`) and
`_assign_sabotage_actions` (`code/simulator.py:2127`) gate on
`"cleanse"/"sabotage" in active.chosen_secondaries`. For a Tactical army
`chosen_secondaries` is the **entire 12-card pool** (`pick_secondaries` returns
`tuple(TACTICAL_DECK_POOL)`, `code/secondaries.py:1060`), so the sim assigns
these actions **every round regardless of whether the card is in the 2-card
hand**. Scoring, however, only credits the card if it is in the held hand
(`_score_tactical_hand`). The two halves are decoupled.

**Direction & magnitude:** units are pulled out of shooting/charging to perform
actions for cards the army does not hold and can never score. Evidence: across
180 games the sim assigned **958 Cleanse** and **2260 Sabotage** unit-actions,
which realised only **172** and **300** victory points — a conversion of ~0.18
and ~0.13 VP per action. Most assignments are for un-held cards: pure waste that
also depresses the army's kills (and therefore its kill-card scoring). This is
the quantified form of the previously-noted "spare bodies do not convert"
finding — they convert at a near-zero rate, and the wasted shooting is a
second-order drag on every other secondary.

### D3 — The drawable deck is 12 cards; the printed deck is 19 (est. +1 to +3 VP/player)

**Printed deck (Chapter Approved 2025-26, 19 cards):** Behind Enemy Lines, Storm
Hostile Objective, Engage on All Fronts, Establish Locus, Cleanse, Assassination,
No Prisoners, Cull the Horde, Bring It Down, Defend Stronghold, **Marked for
Death**, Secure No Man's Land, Sabotage, Area Denial, Recover Assets, A Tempting
Target, Extend Battle Lines, **Overwhelming Force**, **Display of Might**.
(Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/ .)

**Simulator behaviour:** `TACTICAL_DECK_POOL` (`code/secondaries.py:224`) has 12
cards at production defaults. Missing:

- **Three implemented but gated off:** Establish Locus, Recover Assets, A Tempting
  Target (added only when `SWEG_ACTION_ECONOMY=1`, default off — the keys are
  absent from the pool, `code/secondaries.py:186`).
- **Three not implemented at all:** Marked for Death ("**One or more of your Alpha
  Target units were destroyed … this turn**" — 5VP / 2VP), Overwhelming Force
  ("**Each time an enemy unit that started the turn within range of an objective
  marker is destroyed**" — 3VP up to 5VP), Display of Might ("**There are more
  units from your army than from your opponent's army wholly within No Man's
  Land**" — 4VP).

**Direction & magnitude:** several missing cards are *easy* scorers (A Tempting
Target 5VP for holding one marker; Display of Might 4VP for out-massing the mid
board; Overwhelming Force 3VP per kill near an objective) — precisely the cards a
body army would achieve. Their absence shrinks and hardens the drawable pool.
Adding the printed 19-card deck raises the achievable fraction; magnitude
moderate because it compounds with D1 (a bigger deck only helps if the hand can
cycle).

### D4 — Command-point generation is halved (est. +1 to +2 VP/player, mostly via enabling D1/defensive play)

**Printed rule:** "**At the start of your Command phase, before doing anything
else, both players gain 1CP.**" (Verified this session against the primary source,
https://wahapedia.ru/wh40k10ed/the-rules/core-rules/ .) There are two Command
phases per battle round, so **each player gains 2 CP per round**. A separate cap:
"**Outside of the 1CP players gain at the start of the Command phase, each player
can only gain a total of 1CP per battle round, regardless of the source.**"

**Simulator behaviour:** `award_command_phase_cp` (`code/stratagems.py:1621`,
`CP_PER_COMMAND_PHASE = 1`) is called once per army per round from
`Battle._run_round` (`code/simulator.py:10920-10921`) — **+1 per round per
player**, half the printed rate.

**Direction & magnitude:** the simulator gives each army ~5 command-phase points
over a game where the real rule gives ~10 (both banked to a cap of 6). Its
direct effect on secondaries is latent today (the sim models neither the New
Orders stratagem — 1 CP to discard one active card and draw a new one, the
canonical dead-card-cycling tool — nor, by default, the voluntary discard), but
the halved budget is the reason defensive stratagems starve: **Smokescreen never
fires once in the entire command-point census** (§4), confirming the durability
wave's finding. Fixing D1's New Orders path depends on this budget existing.

### D5 — The Fixed pool is 3 cards; the printed Fixed pool is 5 (est. +0 to +1 VP/player)

**Printed rule:** the five Fixed Secondary Missions are **Assassination, No
Prisoners, Cull the Horde, Bring It Down, and Cleanse** — a Fixed player picks
two (Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/ ).

**Simulator behaviour:** `FIXED_SECONDARY_KEYS = (bring_it_down, cull_the_horde,
assassination)` (`code/secondaries.py:79`). No Prisoners is excluded on the
claim it is "banned as a Fixed pick" and Cleanse is excluded entirely.
`_pick_fixed_kill_pair` (`code/secondaries.py:949`) can resolve **both** slots to
`cull_the_horde` against a low-monster, low-character enemy, running two copies
of one card (the scorer collapses them, so the army effectively brings **one**
scoring card).

**Direction & magnitude:** low priority — Fixed is only 17% of the field and
already out-scores Tactical (13.6). But the degenerate double-Cull case and the
missing No Prisoners / Cleanse options do cap a Fixed army's ceiling against
certain matchups. Note: whether No Prisoners is genuinely banned as a Fixed pick
in the *specific* Warp Friends tournament the calibration targets should be
confirmed before "fixing" its exclusion — the base rule includes it.

### D6 — Track routing sends 83% of armies onto the broken Tactical track (amplifier, not an independent divergence)

`_choose_secondary_track` (`code/secondaries.py:983`) routes an army to TACTICAL
when it has ≥2 chaff and ≥8 units, else FIXED. In the sample this put **82.8%**
of players on Tactical. Track choice is a legitimate real-player decision, so
this is not itself a print divergence — but because the Tactical track is the
broken one (D1), routing the bulk of the field onto it maximises D1's damage. It
becomes benign once D1 is fixed and the two tracks pay comparably (as they do in
reality).

## 4. Command-point spend census

Total 2766 command points spent across 180 games = **15.4 CP/game across both
armies (~7.7 per player)**, against a generation of ~8 per player (starting 3 +
5×1). At the printed generation rate (~13 per player) the budget would be far
looser. Breakdown of what the simulator spends command points on:

| Category | CP/game (both armies) | Share |
|---|---|---|
| Stratagems (offensive, detachment + universal) | 10.78 | 70.2% |
| Go To Ground | 3.86 | 25.1% |
| Overwatch | 0.72 | 4.7% |
| **Smokescreen** | **0.00** | **0.0%** |
| Secondary-deck cycling (New Orders / voluntary discard) | 0.00 | 0.0% |

Two divergences from a real command-point budget: (a) **Smokescreen never fires**
— offensive stratagems and Go To Ground exhaust the (halved, D4) budget first, so
the durable-army defensive layer the durability wave flagged is starved; (b) the
simulator spends **nothing** on cycling secondary cards, because neither the New
Orders stratagem nor (by default) the voluntary discard exists — the exact
mechanisms a real Tactical player pays command points for. No stratagem was
observed spending at a printed-illegal rate or timing; the divergence is
under-generation and under-use, not over-spend.

## 5. Per-card empirical scoring table (Tactical track, 180 games)

`held-passes` = times the card was scored while in a held hand (one per round it
sat in hand); `ach%` = fraction of those passes that scored 1+ VP; `VP/held` =
mean victory points per round the card occupies a hand slot; `VP/score` = mean
victory points on a scoring round.

| Card | held-passes | scored>0 | ach% | VP/held | VP/score |
|---|---|---|---|---|---|
| secure_no_mans_land | 141 | 114 | 80.9 | 2.85 | 3.53 |
| engage_on_all_fronts | 200 | 134 | 67.0 | 1.82 | 2.72 |
| sabotage | 175 | 95 | 54.3 | 1.71 | 3.16 |
| no_prisoners | 215 | 114 | 53.0 | 1.77 | 3.33 |
| bring_it_down | 302 | 82 | 27.2 | 1.09 | 4.00 |
| cleanse | 265 | 67 | 25.3 | 0.65 | 2.57 |
| area_denial | 284 | 61 | 21.5 | 0.68 | 3.18 |
| behind_enemy_lines | 339 | 70 | 20.6 | 0.75 | 3.63 |
| assassination | 325 | 61 | 18.8 | 0.94 | 5.00 |
| extend_battle_lines | 341 | 49 | 14.4 | 0.57 | 4.00 |
| storm_hostile_objective | 319 | 43 | 13.5 | 0.54 | 4.00 |
| defend_stronghold | 342 | 45 | 13.2 | 0.39 | 3.00 |

Reading the table: the cards at the bottom are not intrinsically hard — they are
the cards that, once drawn against a board state that does not suit them, **clog
the hand for the rest of the game** (each clogged round adds a zero-scoring
held-pass, dragging the rate down and inflating the denominator). `bring_it_down`
(302 passes, 27%) and `assassination` (325 passes, 19%) are the clearest: both
carry printed **When-Drawn redraw clauses** (D1/D3) that would prevent a real
army ever holding them against an enemy with no MONSTER/VEHICLE or CHARACTER,
yet the sim holds them for the whole game. `defend_stronghold` at 13% is a body
army holding a home-objective card while it has pushed off its own deployment
zone — again a card a real player would have shed.

## 6. Faithful list — what the simulator gets right

These were checked against the printed cards and are accurate; no change needed:

- **Kill-card victory-point values** all match Chapter Approved 2025-26: Bring It
  Down Fixed 2 (+2 at 15+ wounds, +2 at 20+, max 6) and Tactical flat 4;
  Assassination Fixed 4 (4+ wounds) / 3 (<4) and Tactical flat 5; Cull the Horde
  5 at Starting Strength 13+; No Prisoners 2 per unit up to 5/turn. (`code/secondaries.py:254-302`.)
- **Engage on All Fronts** 1 / 2 / 4 VP for 2 / 3 / 4 quarters — matches the new
  CA2025-26 three-tier structure (the sim was updated off the old 2/3/5).
- **Behind Enemy Lines** 3 VP (one unit) / 4 VP (two or more) — matches.
- **Board take-and-hold values** — Secure No Man's Land 2/5, Defend Stronghold 3,
  Extend Battle Lines 4 (correctly reduced from the Pariah Nexus 5), Storm
  Hostile Objective 4, Area Denial 2/5 — all match the printed cards.
- **The achieve→discard→redraw for *scored* cards** is the faithful half of the
  Tactical mechanic; the deterministic, global-RNG-free deck shuffle is sound.
- **The 40-VP secondary total ceiling** (`_capped_vp_pair`, `code/simulator.py:982`)
  matches the printed cap (though at ~11 VP it never binds).
- The **wholly-within squad-granularity** refinement for Engage / Behind Enemy
  Lines (`SWEG_SECONDARY`, `code/secondaries.py:781`) is the faithful direction,
  though gated off.

## 7. Ranked fix plan — how to close the ~11-point gap honestly

Every item is "implement a printed rule the simulator currently omits", in
descending expected impact. Each should be built gated, cited, and validated
byte-identical-off per the standing eval protocol.

1. **Restore the Tactical deck's card-shedding (D1) — the single biggest lever.**
   Three printed sub-rules, buildable in order of impact:
   a. **When-Drawn redraw at draw time** — when `_init_tactical_deck` deals a card
      whose When-Drawn condition is unmet (no MONSTER/VEHICLE for Bring It Down,
      no 13+ INFANTRY for Cull, first-round positional cards, no targets for
      Marked for Death), discard and draw the next. Each clause is printed and
      per-card; this is the de-clog mechanism.
   b. **End-of-turn voluntary discard on by default**, using the achievability
      test (`_tac_discard_card_cannot_pay`) rather than the age-only heuristic,
      and allowing the printed "one or more" cards per turn — the
      `SWEG_SECONDARY_PURSUIT` build already contains the better version; the task
      is to make the faithful behaviour the default, not a gated experiment.
   c. **The New Orders core stratagem** (1 CP: end of Command phase, discard one
      active card, draw one) — needs the command-point budget from item 4.

2. **Gate Cleanse / Sabotage action assignment on the held hand, not the pool
   (D2).** Change the `"cleanse" in chosen_secondaries` test in
   `_assign_cleanse_actions` / `_assign_sabotage_actions` to read the Tactical
   `tactical_hand` (or the Fixed chosen pair) so a unit only spends its shooting
   on an action the army can actually score. Recovers wasted actions and the
   kills they cost.

3. **Add the printed 19-card deck (D3).** Turn on the three implemented action
   cards (Establish Locus / Recover Assets / A Tempting Target) by default, and
   implement the three missing cards (Marked for Death, Overwhelming Force,
   Display of Might) with their cited text. Best done after item 1 so the larger
   deck can actually cycle.

4. **Command-point generation to the printed 2 per round per player (D4).** Grant
   the command-phase point for both players in each of the two Command phases per
   round (respecting the CP_CAP=6 bank and the separate 1-per-round non-command-
   phase cap). This unblocks New Orders (1c) and the starved defensive
   stratagems (Smokescreen).

5. **Restore the printed 5-card Fixed pool (D5).** Add No Prisoners (pending the
   tournament-ban check) and Cleanse as valid Fixed picks and remove the
   degenerate double-Cull. Lowest priority — Fixed already over-performs.

The dominant recovery is item 1: it targets the 83% of the field on the Tactical
track, whose 9.5 → ~18-20 shift alone recovers the bulk of the ~11-point gap.
Items 2-4 are compounding corrections; item 5 is a tidy-up.
