# M2 — the real 2-card Tactical secondary deck (plan, wave 118)

Watchdog's now-leading lever after the scoring-timing thread was retired (waves
109-117). This is **plan-first** per the user-approved sequence; the build is the
next wave(s). Env-gated `SWEG_TAC_DECK`, A/B, **keep-if-faithful regardless of the
metric direction** (it is a faithfulness fix — match the real CA-2025-26 deck).

## The problem (instrumented across waves 109-115)

Every faction's residual is the primary board-control axis, and **secondary is
always a 40-cap wash** — but that wash is an ARTEFACT of unfaithful
over-generation, not a faithful result (watchdog mission-pack audit). The sim
scores ~9-11 secondary sources EVERY round simultaneously:

- 2 Fixed (kill: `bring_it_down`, `no_prisoners`, `cull_the_horde`, `assassination` — pick 2),
- 2 position Tactical (`engage_on_all_fronts`, `behind_enemy_lines`),
- `cleanse` + `sabotage` (action), and
- all 5 Board Tier-A cards (`SWEG_TIER_A` default ON: `secure_no_mans_land`,
  `defend_stronghold`, `extend_battle_lines`, `storm_hostile_objective`, `area_denial`).

`pick_secondaries` (code/secondaries.py:646) returns the union of all of these;
`Battle._score_secondaries` (code/simulator.py:~1310) scores all the chosen ones
every round. Both armies trivially exceed 40 → the cap flattens them to 40 each →
secondary never differentiates. **This hands the durable Knight back its single
biggest real-world weakness:** a Knight army (5-6 units, no cheap action-doers, no
screens) genuinely CANNOT churn a 2-card Tactical deck to 40, while a broad army
does it easily.

## The real rule (CA-2025-26 v1.5, the May-2026 target's deck)

Verbatim (captured in `data/reference/wahapedia_ca2025-26.txt`): at game start each
player secretly chooses **Fixed** OR **Tactical** Missions (not both).

- **Fixed:** pick 2 cards; they remain all game, can be achieved repeatedly; **max
  20 VP per Fixed card** (so ≤40 total). The kill cards are the Fixed pool.
- **Tactical:** "At the start of your first Command phase, draw two cards … those
  two … are active for you until you achieve them. At the start of each of your
  subsequent Command phases, if you have fewer than two active … draw … until you
  have two … if you scored 1 or more VP from a Secondary Mission card, discard
  that card – it is achieved." So you **hold at most 2** Tactical cards; achieving
  one scores it and replaces it. (Plus the New Orders stratagem: 1 CP to discard
  one active card and draw a new one, end of Command phase.)
- Total Secondary cap 40/game (already modelled, `secondary_vp_cap_40`).

So a faithful army scores at most its **2 Fixed** OR its **2 held Tactical** cards
per round — NOT 9-11 sources.

## Build (staged; env-gated `SWEG_TAC_DECK`; OFF reproduces today byte-for-byte)

**Stage A — the Tactical-deck state machine (the core).**
- Per army, a `tactical_hand: List[str]` (≤2) and a `tactical_deck` (the shuffled
  remaining pool), seeded deterministically from the battle seed so PYTHONHASHSEED=0
  reproduces. Initialise in `_score_secondaries`'s setup (or a new `_init_tac_deck`
  at battle start): draw 2 into the hand.
- Each round (the Command phase already modelled per round): for each card in the
  hand, run its existing per-card scoring check (the SAME logic the current scorer
  uses — `score_round_delta` for kills, `score_position_delta` for Engage/BEL,
  `_score_cleanse`/`_score_sabotage`/`_score_board_secondaries` for the rest). If a
  card scores ≥1 VP → award it, DISCARD it (achieved), and redraw from the deck to
  refill the hand to 2. Score ONLY the hand.
- The pool the deck draws from = the full Tactical/Board/action set (the 9 the sim
  has + the 6 added in Stage C). The 4 kill cards stay the FIXED pool (see Stage B).

**Stage B — the Fixed/Tactical choice.**
- `pick_secondaries` chooses, per army, FIXED (the 2 best kill cards — today's
  Fixed pick logic) or TACTICAL (the 2-card rotating hand). A faithful, even-handed
  heuristic (no faction awareness): a low-model army with no spare action-doers
  leans FIXED kill (it can't churn Tactical); a broad army with chaff leans
  TACTICAL — exactly the real choice, falling out of unit count. Reuse the existing
  `_own_chaff_count` / unit-count signals. (Knight → Fixed kill; horde → Tactical.)
- A FIXED army scores its 2 kill cards every round (each ≤20/game). A TACTICAL army
  runs the Stage-A hand. Score ONLY the chosen track — not both, not the board pile.

**Stage C — add the ~6 missing real Tactical cards (the broad army's tools).**
The audit found the deck is missing several ACTION-based cards that a broad army
uses and a Knight cannot: **Establish Locus, Recover Assets, A Tempting Target**
(and confirm the rest of the CA-2025-26 Tactical list). Add each as a real card
(faithful text + scoring check, cited) into the Tactical pool. These are the cards
that make the broad army's Tactical churn out-score a Knight's.

**Stage D — measure + decide.**
- A/B `SWEG_TAC_DECK` OFF (today) vs ON (the deck), N=40 then N=80. Read the
  per-faction secondary totals: the hypothesis is the Knight's secondary drops
  relative to broad armies (it can't churn a 2-card deck), narrowing +27.
- **Keep-if-faithful** regardless of direction (it is the real rule). If it WASHES
  (both still hit similar totals), that is also a real finding — it means the
  secondary game is NOT where the Knight's gap bites, and the next candidate is the
  one-Unit-per-model board-control representation (M4-adjacent). Do NOT tune the
  deck contents to hit a number.

## Risks / de-risks

1. **The AI must "play toward" a held Tactical card** (do the action / spread it
   needs), else a drawn card never scores and the hand stalls. Today the AI does
   Cleanse/Sabotage/Engage opportunistically; check it still satisfies a held card
   often enough to be realistic. If the AI can't pursue a card, model achievement
   on the existing opportunistic checks (don't fabricate an achievement). A stalled
   hand for a Knight is FAITHFUL (it genuinely can't do those actions).
2. **Determinism** — seed the deck shuffle + draws from the battle seed; verify
   double-run reproducibility under PYTHONHASHSEED=0.
3. **The 40 total cap + per-card caps** interact — keep the 40 cap; the per-card
   caps become per-Fixed-card 20 caps (Stage B) / natural per-achievement values.
4. **OFF path byte-identical** — gate the whole deck behind `SWEG_TAC_DECK`; unset
   → today's `pick_secondaries` + `_score_secondaries` unchanged.

## Critical files
- `code/secondaries.py` — `pick_secondaries` (Fixed/Tactical choice), the card
  pool, the new card scoring checks (Stage C), the deck/hand helpers.
- `code/simulator.py` — `_score_secondaries` (~1310): the per-round hand
  scoring + draw/achieve/redraw loop; deck init at battle start; `SWEG_TAC_DECK` gate.
- `data/rule_citations.d/` — `simulator.tactical_secondary_deck` + one entry per
  added card (faithful CA-2025-26 text).
- `tests/` — deck state machine (draw 2, achieve→discard→redraw, ≤2 held, score
  only hand); OFF==baseline; determinism.

Cited as `simulator.tactical_secondary_deck`.
